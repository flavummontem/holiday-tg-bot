# ==========================================
# GLOBAL HOLIDAY RADAR v10 – FINAL STABLE
# Full Enterprise Monolith
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
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
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

# ================= MENUS =================

def main_menu():
    return {
        "keyboard": [
            ["🏢 Where We Operate (Business Presence Countries)"],
            ["👥 Where Our Team Is Located (Team Presence Countries)"],
            ["🌍 Choose a Country"],
            ["📆 This Month Holidays"],
            ["📋 My Subscriptions"],
            ["➖ Remove a Subscription"],
            ["⚙️ Settings"]
        ],
        "resize_keyboard": True
    }

def paginated_countries(mode, page=0):
    items = list(COUNTRIES.items())
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = items[start:end]

    buttons = []
    for code, label in chunk:
        buttons.append([{
            "text": label,
            "callback_data": f"sub:{mode}:{code}"
        }])

    nav = []
    if start > 0:
        nav.append({"text": "⬅️ Prev", "callback_data": f"page:{mode}:{page-1}"})
    if end < len(items):
        nav.append({"text": "Next ➡️", "callback_data": f"page:{mode}:{page+1}"})

    if nav:
        buttons.append(nav)

    return {"inline_keyboard": buttons}

def remove_subscriptions_menu(chat_id):
    data = load_json("subscriptions.json")
    subs = data[chat_id]["subscriptions"]

    if not subs:
        return None

    buttons = []
    for country in subs:
        buttons.append([{
            "text": COUNTRIES[country],
            "callback_data": f"remove:{country}"
        }])

    return {"inline_keyboard": buttons}

def settings_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🌍 Change Timezone", "callback_data": "settings_tz"}],
            [{"text": "🔔 Change Alert Frequency", "callback_data": "settings_freq"}],
            [{"text": "🔕 Mute 7 days", "callback_data": "mute_7"}],
            [{"text": "🔕 Mute 30 days", "callback_data": "mute_30"}],
            [{"text": "🔊 Unmute", "callback_data": "unmute"}]
        ]
    }

def alert_preset_menu():
    return {
        "inline_keyboard": [
            [{"text": "Standard (14/7/3/1)", "callback_data": "preset:standard"}],
            [{"text": "Medium (7/3/1)", "callback_data": "preset:medium"}],
            [{"text": "Last Day Only", "callback_data": "preset:last_day"}]
        ]
    }
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
                holiday_types = [t.lower() for t in h.get("type", [])]

                if not any(
                    "public" in t
                    or "national" in t
                    or "religious" in t
                    for t in holiday_types
                ):
                    continue

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
                            "employee": "👥 TEAM LOCATION HOLIDAY ALERT",
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
            continue

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

def send_monthly_overview(chat_id):
    data = load_json("subscriptions.json")
    user = data.get(chat_id)

    if not user or not user["subscriptions"]:
        send_message(chat_id, "You have no active subscriptions.", main_menu())
        return

    tz = safe_timezone(user["timezone"])
    today = datetime.now(tz).date()
    current_month = today.month
    current_year = today.year

    result = {}

    for country in user["subscriptions"]:
        holidays = get_cached_holidays(country)

        for h in holidays:
            h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()

            if 0 <= (h_date - today).days <= 31:
                result.setdefault(country, []).append((h_date, h["name"]))
    if not result:
        send_message(
            chat_id,
            "No public holidays scheduled for this month in your selected countries.",
            main_menu()
        )
        return

    month_name = today.strftime("%B %Y")

    msg = f"📆 *Public Holidays — {month_name}*\n\n"

    for country, holidays in sorted(result.items()):
        msg += f"{COUNTRIES[country]}\n"
        for d, name in sorted(holidays):
            msg += f"• {d.strftime('%d %b')} — {name}\n"
        msg += "\n"

    send_message(chat_id, msg, main_menu())

# ================= MAIN LOOP =================

if __name__ == "__main__":

    offset = None
    last_day = None

    while True:
        updates = get_updates(offset)

        for u in updates.get("result", []):
            offset = u["update_id"] + 1

            # ===== CALLBACKS =====

            if "callback_query" in u:
                callback = u["callback_query"]
                chat_id = str(callback["message"]["chat"]["id"])
                data_cb = callback["data"]
                answer_callback(callback["id"])

                data = load_json("subscriptions.json")

                if data_cb.startswith("sub:"):
                    _, mode, country = data_cb.split(":")
                    data[chat_id]["subscriptions"][country] = mode
                    send_message(
                        chat_id,
                        f"✅ Subscribed to {COUNTRIES[country]}",
                        main_menu()
                    )

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
                    send_message(
                        chat_id,
                        f"❌ Removed {COUNTRIES[country]}",
                        main_menu()
                    )

                elif data_cb.startswith("tz:"):
                    tz = data_cb.split(":")[1]
                    data[chat_id]["timezone"] = tz
                    send_message(
                        chat_id,
                        f"🌍 Timezone updated to {tz}",
                        main_menu()
                    )

                elif data_cb.startswith("preset:"):
                    preset = data_cb.split(":")[1]
                    data[chat_id]["alert_preset"] = preset
                    send_message(
                        chat_id,
                        f"🔔 Alert preset updated to {preset}",
                        main_menu()
                    )

                elif data_cb == "mute_7":
                    data[chat_id]["mute_until"] = (
                        datetime.utcnow() + timedelta(days=7)
                    ).strftime("%Y-%m-%d")
                    send_message(chat_id, "🔕 Muted for 7 days", main_menu())

                elif data_cb == "mute_30":
                    data[chat_id]["mute_until"] = (
                        datetime.utcnow() + timedelta(days=30)
                    ).strftime("%Y-%m-%d")
                    send_message(chat_id, "🔕 Muted for 30 days", main_menu())

                elif data_cb == "unmute":
                    data[chat_id]["mute_until"] = None
                    send_message(chat_id, "🔊 Notifications unmuted", main_menu())

                elif data_cb == "settings_tz":
                    tz_buttons = [[{
                        "text": tz,
                        "callback_data": f"tz:{tz}"
                    }] for tz in POPULAR_TIMEZONES]
                    send_message(
                        chat_id,
                        "Select timezone:",
                        {"inline_keyboard": tz_buttons}
                    )

                elif data_cb == "settings_freq":
                    send_message(
                        chat_id,
                        "Select alert frequency:",
                        alert_preset_menu()
                    )

                save_json("subscriptions.json", data)

            # ===== TEXT COMMANDS =====

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
                        "👥 Track holidays in countries where our support teams operate\n"
                        "🌍 Track specific countries of your choice\n\n"
                        "You’ll receive alerts\n"
                        "14 / 7 / 3 / 1 days before each public holiday.\n\n"
                        "Use the menu below to subscribe.\n\n"
                        "Questions, feedback or improvements?\n"
                        "@rubbeldiekatz"
                    )
                    send_message(chat_id, welcome_text, main_menu())

                elif text.startswith("🏢"):
                    send_message(
                        chat_id,
                        "🌍 Select country:",
                        paginated_countries("business", 0)
                    )

                elif text.startswith("👥"):
                    send_message(
                        chat_id,
                        "🌍 Select country:",
                        paginated_countries("employee", 0)
                    )
                elif text.startswith("📆"):
                    send_monthly_overview(chat_id)

                elif text.startswith("🌍"):
                    send_message(
                        chat_id,
                        "🌍 Select country:",
                        paginated_countries("custom", 0)
                    )

                elif text.startswith("📋"):
                    subs = data[chat_id]["subscriptions"]
                    if not subs:
                        send_message(chat_id, "You have no active subscriptions.", main_menu())
                    else:
                        msg = "📋 *Your Subscriptions:*\n\n"
                        for c, mode in subs.items():
                            msg += f"{COUNTRIES[c]} ({mode})\n"
                        send_message(chat_id, msg, main_menu())

                elif text.startswith("➖"):
                    menu = remove_subscriptions_menu(chat_id)
                    if not menu:
                        send_message(chat_id, "No subscriptions to remove.", main_menu())
                    else:
                        send_message(chat_id, "Select subscription to remove:", menu)

                elif text.startswith("⚙️"):
                    send_message(chat_id, "⚙️ Settings", settings_keyboard())

                elif text == "/stats" and username == ADMIN_USERNAME:
                    users = len(data)
                    subs = sum(len(v["subscriptions"]) for v in data.values())
                    send_message(
                        chat_id,
                        f"📊 *Global Holiday Radar Stats*\n\n"
                        f"👤 Active Users: {users}\n"
                        f"🌍 Total Subscriptions: {subs}"
                    )

        # ===== DAILY TASKS =====

        today_utc = datetime.utcnow().date()

        if last_day != today_utc:
            clean_sent_alerts()
            clean_cache()
            send_daily_alerts()
            send_weekly_digest()
            last_day = today_utc

        time.sleep(5)
