# ==========================================
# GLOBAL HOLIDAY RADAR v8 – PRODUCTION
# Full Enterprise Monolith (Render Safe)
# ==========================================

import requests
import json
import time
import os
import pytz
from datetime import datetime, timedelta

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")
ADMIN_USERNAME = "rubbeldiekatz"

DEFAULT_ALERT_PRESET = "standard"
ALERT_PRESETS = {
    "standard": [14, 7, 3, 1],
    "medium": [7, 3, 1],
    "last_day": [1]
}

PAGE_SIZE = 6

# ================= COUNTRIES =================

COUNTRIES = {
    "UZ": "🇺🇿 Uzbekistan",
    "AE": "🇦🇪 UAE",
    "GE": "🇬🇪 Georgia",
    "KZ": "🇰🇿 Kazakhstan",
    "TR": "🇹🇷 Turkey",
    "PK": "🇵🇰 Pakistan",
    "PE": "🇵🇪 Peru",
    "CO": "🇨🇴 Colombia",
    "RS": "🇷🇸 Serbia",
    "MA": "🇲🇦 Morocco",
    "NG": "🇳🇬 Nigeria",
    "SN": "🇸🇳 Senegal",
    "IL": "🇮🇱 Israel"
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
    with open(name, "r") as f:
        try:
            return json.load(f)
        except:
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
    return data

# ================= TELEGRAM =================

def send_message(chat_id, text, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Send message error:", e)

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset
        return requests.get(url, params=params, timeout=35).json()
    except:
        return {"result": []}

# ================= CACHE =================

def get_cached_holidays(country):
    cache = load_json("holiday_cache.json")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if country in cache and cache[country]["date"] == today_str:
        return cache[country]["holidays"]

    holidays = fetch_holidays(country)
    cache[country] = {"date": today_str, "holidays": holidays}
    save_json("holiday_cache.json", cache)
    return holidays

def fetch_holidays(country):
    try:
        url = "https://calendarific.com/api/v2/holidays"
        params = {
            "api_key": CALENDARIFIC_KEY,
            "country": country,
            "year": datetime.utcnow().year
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        holidays = data.get("response", {}).get("holidays", [])
        result = []
        for h in holidays:
            result.append({
                "date": h["date"]["iso"].split("T")[0],
                "name": h["name"],
                "description": h.get("description", "")
            })
        return result
    except Exception as e:
        print("Holiday fetch error:", e)
        return []

# ================= KEYBOARDS =================

def main_menu():
    return {
        "keyboard": [
            ["🏢 Business Countries"],
            ["👥 Employee Countries"],
            ["🌍 Custom Country"],
            ["📋 My Subscriptions"],
            ["➖ Remove Subscription"],
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

# ================= SETTINGS =================

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

def show_settings(chat_id):
    data = load_json("subscriptions.json")
    user = data[chat_id]

    mute_status = user["mute_until"] if user["mute_until"] else "Active"

    text = (
        "*⚙️ Settings*\n\n"
        f"🌍 Timezone: {user['timezone']}\n"
        f"🔔 Alert preset: {user['alert_preset']}\n"
        f"🔕 Status: {mute_status}"
    )

    send_message(chat_id, text, settings_keyboard())

# ================= ALERTS =================

def send_daily_alerts():
    data = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")

    for chat_id, user in data.items():

        tz = pytz.timezone(user["timezone"])
        today = datetime.now(tz).date()

        if user["mute_until"]:
            if today <= datetime.strptime(user["mute_until"], "%Y-%m-%d").date():
                continue

        alert_days = ALERT_PRESETS[user["alert_preset"]]

        for country, mode in user["subscriptions"].items():
            holidays = get_cached_holidays(country)

            for h in holidays:
                h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                delta = (h_date - today).days

                if delta in alert_days:
                    key = f"{chat_id}-{country}-{h['date']}-{delta}"
                    if key not in sent:
                        msg = (
                            f"*🌍 Holiday Alert*\n\n"
                            f"{COUNTRIES[country]}\n"
                            f"🎉 *{h['name']}*\n"
                            f"📅 {h_date.strftime('%d %B %Y')}\n"
                            f"⏳ In {delta} days\n\n"
                            f"{h['description'] or 'Public holiday.'}"
                        )
                        send_message(chat_id, msg)
                        sent[key] = True

    save_json("sent_alerts.json", sent)

def send_weekly_digest():
    data = load_json("subscriptions.json")

    for chat_id, user in data.items():
        tz = pytz.timezone(user["timezone"])
        today = datetime.now(tz).date()

        upcoming = []

        for country in user["subscriptions"]:
            holidays = get_cached_holidays(country)
            for h in holidays:
                h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                if 0 <= (h_date - today).days <= 14:
                    upcoming.append((h_date, country, h["name"]))

        msg = "*📅 Weekly Holiday Digest*\n\n"

        if upcoming:
            upcoming.sort()
            for d, c, name in upcoming:
                msg += f"{COUNTRIES[c]} — {name} ({d.strftime('%d %b')})\n"
        else:
            msg += "No upcoming holidays in next 14 days."

        send_message(chat_id, msg)

# ================= MAIN LOOP =================

if __name__ == "__main__":

    offset = None
    last_day = None

    while True:
        updates = get_updates(offset)

        for u in updates.get("result", []):
            offset = u["update_id"] + 1

            if "message" in u:
                chat_id = str(u["message"]["chat"]["id"])
                text = u["message"].get("text", "")
                username = u["message"]["from"].get("username")

                data = ensure_user(chat_id)

                if text == "/start":
                    send_message(chat_id, "Welcome to Global Holiday Radar.", main_menu())

                elif text == "⚙️ Settings":
                    show_settings(chat_id)

                elif text == "/stats" and username == ADMIN_USERNAME:
                    users = len(data)
                    subs = sum(len(v["subscriptions"]) for v in data.values())
                    send_message(chat_id, f"*Users:* {users}\n*Subscriptions:* {subs}")

            if "callback_query" in u:
                chat_id = str(u["callback_query"]["message"]["chat"]["id"])
                data_cb = u["callback_query"]["data"]
                data = load_json("subscriptions.json")

                if data_cb.startswith("sub:"):
                    _, mode, country = data_cb.split(":")
                    data[chat_id]["subscriptions"][country] = mode

                elif data_cb == "mute_7":
                    data[chat_id]["mute_until"] = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

                elif data_cb == "mute_30":
                    data[chat_id]["mute_until"] = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

                elif data_cb == "unmute":
                    data[chat_id]["mute_until"] = None

                elif data_cb == "settings_tz":
                    tz_buttons = [[{
                        "text": tz,
                        "callback_data": f"tz:{tz}"
                    }] for tz in POPULAR_TIMEZONES]
                    send_message(chat_id, "Select timezone:", {"inline_keyboard": tz_buttons})

                elif data_cb.startswith("tz:"):
                    tz = data_cb.split(":")[1]
                    data[chat_id]["timezone"] = tz

                save_json("subscriptions.json", data)

        today_utc = datetime.utcnow().date()
        if last_day != today_utc:
            send_daily_alerts()
            send_weekly_digest()
            last_day = today_utc

        time.sleep(5)
