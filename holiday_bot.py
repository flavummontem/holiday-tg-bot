# ==========================================
# GLOBAL HOLIDAY RADAR v9 – PRODUCTION SAFE
# Full Enterprise Monolith (Render Safe)
# ==========================================

import requests
import json
import time
import os
import pytz
import logging
from datetime import datetime, timedelta

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")
ADMIN_USERNAME = "rubbeldiekatz"

if not TOKEN:
    raise Exception("TOKEN not set")

if not CALENDARIFIC_KEY:
    raise Exception("CALENDARIFIC_KEY not set")

DEFAULT_ALERT_PRESET = "standard"

ALERT_PRESETS = {
    "standard": [14, 7, 3, 1],
    "medium": [7, 3, 1],
    "last_day": [1]
}

PAGE_SIZE = 6
SENT_ALERT_RETENTION_DAYS = 60
CACHE_RETENTION_DAYS = 3

# ================= COUNTRIES =================

COUNTRIES = {
    "AO": "🇦🇴 Angola",
    "AR": "🇦🇷 Argentina",
    "AM": "🇦🇲 Armenia",
    "AZ": "🇦🇿 Azerbaijan",
    "BY": "🇧🇾 Belarus",
    "BJ": "🇧🇯 Benin",
    "BO": "🇧🇴 Bolivia",
    "BW": "🇧🇼 Botswana",
    "KH": "🇰🇭 Cambodia",
    "CM": "🇨🇲 Cameroon",
    "CO": "🇨🇴 Colombia",
    "CD": "🇨🇩 Congo K",
    "EG": "🇪🇬 Egypt",
    "ET": "🇪🇹 Ethiopia",
    "GE": "🇬🇪 Georgia",
    "GH": "🇬🇭 Ghana",
    "GT": "🇬🇹 Guatemala",
    "IL": "🇮🇱 Israel",
    "CI": "🇨🇮 Ivory Coast",
    "KZ": "🇰🇿 Kazakhstan",
    "KE": "🇰🇪 Kenya",
    "MU": "🇲🇺 Mauritius",
    "MD": "🇲🇩 Moldova",
    "MA": "🇲🇦 Morocco",
    "MZ": "🇲🇿 Mozambique",
    "NA": "🇳🇦 Namibia",
    "NP": "🇳🇵 Nepal",
    "NG": "🇳🇬 Nigeria",
    "NO": "🇳🇴 Norway",
    "OM": "🇴🇲 Oman",
    "PK": "🇵🇰 Pakistan",
    "PY": "🇵🇾 Paraguay",
    "PE": "🇵🇪 Peru",
    "RU": "🇷🇺 Russia",
    "SN": "🇸🇳 Senegal",
    "RS": "🇷🇸 Serbia",
    "TG": "🇹🇬 Togo",
    "TR": "🇹🇷 Turkey",
    "AE": "🇦🇪 UAE",
    "UZ": "🇺🇿 Uzbekistan",
    "VE": "🇻🇪 Venezuela",
    "ZM": "🇿🇲 Zambia",
    "ZW": "🇿🇼 Zimbabwe"
}

POPULAR_TIMEZONES = [
    "UTC",
    "Europe/Berlin",
    "Asia/Dubai",
    "Asia/Tashkent",
    "Asia/Karachi",
    "Europe/Belgrade",
    "Africa/Casablanca",
    "Africa/Lagos",
    "America/Lima",
    "America/Bogota"
]

# ================= FILE UTILS =================

def load_json(name):
    if not os.path.exists(name):
        return {}
    try:
        with open(name, "r") as f:
            return json.load(f)
    except:
        logging.warning(f"{name} corrupted, resetting")
        return {}

def save_json(name, data):
    with open(name, "w") as f:
        json.dump(data, f, indent=2)

# ================= USER MODEL =================

def ensure_user(chat_id):
    data = load_json("subscriptions.json")
    if chat_id not in data:
        data[chat_id] = {
            "subscriptions": {},
            "timezone": "UTC",
            "alert_preset": DEFAULT_ALERT_PRESET,
            "mute_until": None
        }
        save_json("subscriptions.json", data)
    return load_json("subscriptions.json")

# ================= TELEGRAM =================

def send_message(chat_id, text, reply_markup=None):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data=payload,
            timeout=10
        )
    except Exception as e:
        logging.error(f"Send message error: {e}")

def answer_callback(callback_id):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
            data={"callback_query_id": callback_id}
        )
    except:
        pass

def get_updates(offset=None):
    try:
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset
        r = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params=params,
            timeout=35
        )
        return r.json()
    except:
        return {"result": []}

# ================= CACHE CLEAN =================

def clean_sent_alerts():
    sent = load_json("sent_alerts.json")
    cutoff = datetime.utcnow() - timedelta(days=SENT_ALERT_RETENTION_DAYS)

    new_sent = {}
    for key in sent:
        try:
            date_part = key.split("-")[2]
            d = datetime.strptime(date_part, "%Y-%m-%d")
            if d >= cutoff:
                new_sent[key] = True
        except:
            continue

    save_json("sent_alerts.json", new_sent)

def clean_cache():
    cache = load_json("holiday_cache.json")
    today = datetime.utcnow()

    new_cache = {}
    for country, data in cache.items():
        try:
            cache_date = datetime.strptime(data["date"], "%Y-%m-%d")
            if (today - cache_date).days <= CACHE_RETENTION_DAYS:
                new_cache[country] = data
        except:
            continue

    save_json("holiday_cache.json", new_cache)

# ================= HOLIDAYS =================

def fetch_holidays(country):
    try:
        holidays = []
        current_year = datetime.utcnow().year

        for year in [current_year, current_year + 1]:
            params = {
                "api_key": CALENDARIFIC_KEY,
                "country": country,
                "year": year
            }

            r = requests.get(
                "https://calendarific.com/api/v2/holidays",
                params=params,
                timeout=15
            )

            data = r.json()
            items = data.get("response", {}).get("holidays", [])

            for h in items:
                holidays.append({
                    "date": h["date"]["iso"].split("T")[0],
                    "name": h["name"],
                    "description": h.get("description", "")
                })

        return holidays

    except Exception as e:
        logging.error(f"Holiday fetch error {country}: {e}")
        return []

def get_cached_holidays(country):
    cache = load_json("holiday_cache.json")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if country in cache and cache[country]["date"] == today_str:
        return cache[country]["holidays"]

    holidays = fetch_holidays(country)
    cache[country] = {"date": today_str, "holidays": holidays}
    save_json("holiday_cache.json", cache)
    return holidays

# ================= ALERTS =================

def safe_timezone(tz_name):
    try:
        return pytz.timezone(tz_name)
    except:
        return pytz.UTC

def send_daily_alerts():
    data = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")

    for chat_id, user in data.items():

        tz = safe_timezone(user["timezone"])
        today = datetime.now(tz).date()

        if user["mute_until"]:
            if today <= datetime.strptime(user["mute_until"], "%Y-%m-%d").date():
                continue

        alert_days = ALERT_PRESETS.get(user["alert_preset"], [14,7,3,1])

        for country, mode in user["subscriptions"].items():
            holidays = get_cached_holidays(country)

            for h in holidays:
                h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                delta = (h_date - today).days

                if delta in alert_days:
                    key = f"{chat_id}-{country}-{h['date']}-{delta}"
                    if key not in sent:

                        mode_label = {
                            "business": "🚖 BUSINESS HOLIDAY ALERT",
                            "employee": "👥 EMPLOYEE LOCATION HOLIDAY ALERT",
                            "custom": "🌍 COUNTRY HOLIDAY ALERT"
                        }

                        msg = (
                            f"{mode_label.get(mode, '🌍 HOLIDAY ALERT')}\n\n"
                            f"{COUNTRIES[country]}\n"
                            f"🎉 *{h['name']}*\n"
                            f"📅 {h_date.strftime('%d %B %Y')}\n"
                            f"⏳ In {delta} days\n\n"
                            f"{h['description'] or 'Public institutions and many businesses may be closed.'}"
                        )

                        send_message(chat_id, msg)
                        sent[key] = True

    save_json("sent_alerts.json", sent)

def send_weekly_digest():
    data = load_json("subscriptions.json")

    for chat_id, user in data.items():
        tz = safe_timezone(user["timezone"])
        today = datetime.now(tz).date()

        if today.weekday() != 0:  # Monday only
            return

        upcoming = []

        for country in user["subscriptions"]:
            holidays = get_cached_holidays(country)
            for h in holidays:
                h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                if 0 <= (h_date - today).days <= 14:
                    upcoming.append((h_date, country, h["name"]))

        msg = (
            "📅 *Global Holiday Radar — Weekly Digest*\n\n"
            "Here’s what’s coming in the next 14 days:\n\n"
        )

        if upcoming:
            upcoming.sort()
            for d, c, name in upcoming:
                msg += f"{COUNTRIES[c]} — {name} ({d.strftime('%d %b')})\n"
        else:
            msg += "No public holidays scheduled in your selected countries over the next 14 days."

        send_message(chat_id, msg)

# ================= MAIN LOOP =================

if __name__ == "__main__":

    offset = None
    last_day = None

    while True:
        updates = get_updates(offset)

        for u in updates.get("result", []):
            offset = u["update_id"] + 1

            if "callback_query" in u:
                callback = u["callback_query"]
                chat_id = str(callback["message"]["chat"]["id"])
                data_cb = callback["data"]
                answer_callback(callback["id"])

                data = load_json("subscriptions.json")

                if data_cb.startswith("sub:"):
                    _, mode, country = data_cb.split(":")
                    data[chat_id]["subscriptions"][country] = mode

                elif data_cb.startswith("page:"):
                    _, mode, page = data_cb.split(":")
                    page = int(page)
                    send_message(
                        chat_id,
                        "🌍 Select country:",
                        paginated_countries(mode, page)
                    )

                elif data_cb.startswith("remove:"):
                    country = data_cb.split(":")[1]
                    data[chat_id]["subscriptions"].pop(country, None)

                elif data_cb.startswith("tz:"):
                    tz = data_cb.split(":")[1]
                    data[chat_id]["timezone"] = tz

                save_json("subscriptions.json", data)

            if "message" in u:
                chat_id = str(u["message"]["chat"]["id"])
                text = u["message"].get("text", "")
                username = u["message"]["from"].get("username")

                data = ensure_user(chat_id)

                if text == "/start":
                    welcome_text = (
                        "👋 *Welcome to Global Holiday Radar*\n\n"
                        "This bot was built by the International Support team\n"
                        "to help you stay ahead of public holidays worldwide.\n\n"
                        "*What can it do?*\n\n"
                        "🏢 Track holidays in countries where we operate\n"
                        "👥 Track holidays in countries where our employees are based\n"
                        "🌍 Track specific countries of your choice\n\n"
                        "You’ll receive alerts\n"
                        "14 / 7 / 3 / 1 days before each public holiday.\n\n"
                        "Use the menu below to subscribe.\n\n"
                        "Questions, feedback or improvements?\n"
                        "@rubbeldiekatz"
                    )
                    send_message(chat_id, welcome_text)

                elif text == "/stats" and username == ADMIN_USERNAME:
                    users = len(data)
                    subs = sum(len(v["subscriptions"]) for v in data.values())
                    send_message(
                        chat_id,
                        f"📊 *Global Holiday Radar Stats*\n\n"
                        f"👤 Active Users: {users}\n"
                        f"🌍 Total Subscriptions: {subs}"
                    )

        today_utc = datetime.utcnow().date()

        if last_day != today_utc:
            clean_sent_alerts()
            clean_cache()
            send_daily_alerts()
            send_weekly_digest()
            last_day = today_utc

        time.sleep(5)
