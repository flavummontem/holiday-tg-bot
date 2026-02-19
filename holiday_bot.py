# ===============================
# GLOBAL HOLIDAY RADAR v6
# Full SaaS Mode
# ===============================

import requests
import json
import time
import os
import pytz
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")
ADMIN_USERNAME = "rubbeldiekatz"

DEFAULT_ALERT_DAYS = [14, 7, 3, 1]
PAGE_SIZE = 8

# ===============================
# COUNTRIES
# ===============================

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

# ===============================
# FILE UTILS
# ===============================

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# ===============================
# MIGRATION
# ===============================

def migrate_data():
    data = load_json("subscriptions.json")
    changed = False

    for user_id in list(data.keys()):
        if isinstance(data[user_id], list):
            data[user_id] = {
                "subscriptions": data[user_id],
                "alert_days": DEFAULT_ALERT_DAYS,
                "mute_until": None,
                "timezone": "UTC"
            }
            changed = True

    if changed:
        save_json("subscriptions.json", data)

# ===============================
# TELEGRAM
# ===============================

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, data=payload)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()

# ===============================
# CALENDARIFIC CACHE
# ===============================

def get_cached_holidays(country):
    cache = load_json("holiday_cache.json")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if country in cache and cache[country]["date"] == today_str:
        return cache[country]["holidays"]

    holidays = fetch_holidays(country)

    cache[country] = {
        "date": today_str,
        "holidays": holidays
    }

    save_json("holiday_cache.json", cache)
    return holidays

def fetch_holidays(country):
    year = datetime.utcnow().year
    url = "https://calendarific.com/api/v2/holidays"

    params = {
        "api_key": CALENDARIFIC_KEY,
        "country": country,
        "year": year
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return []

    data = response.json()
    if "response" not in data:
        return []

    holidays = data["response"].get("holidays", [])

    result = []
    for h in holidays:
        result.append({
            "date": h["date"]["iso"].split("T")[0],
            "localName": h["name"],
            "description": h.get("description", "")
        })

    return result

# ===============================
# SETTINGS UI
# ===============================

def build_settings_keyboard():
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
    user = data.get(chat_id)

    if not user:
        send_message(chat_id, "Use /start first.")
        return

    tz = user["timezone"]
    freq = "/".join(map(str, user["alert_days"]))
    mute = user["mute_until"]

    mute_status = f"Muted until {mute}" if mute else "Active"

    text = (
        "*⚙️ Settings*\n\n"
        f"🌍 Timezone: {tz}\n"
        f"🔔 Alert frequency: {freq}\n"
        f"🔕 Status: {mute_status}\n\n"
        "Choose an option:"
    )

    send_message(chat_id, text, build_settings_keyboard())

# ===============================
# ALERT ENGINE
# ===============================

def check_and_notify():
    data = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")

    for chat_id, user in data.items():

        tz = pytz.timezone(user["timezone"])
        now_local = datetime.now(tz).date()

        if user["mute_until"]:
            mute_date = datetime.strptime(user["mute_until"], "%Y-%m-%d").date()
            if now_local <= mute_date:
                continue

        for entry in user["subscriptions"]:
            holidays = get_cached_holidays(entry["country"])

            for holiday in holidays:
                holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
                delta = (holiday_date - now_local).days

                if delta in user["alert_days"]:

                    key = f"{chat_id}-{entry['country']}-{holiday['date']}-{delta}"

                    if key not in sent:

                        message = (
                            f"*🌍 HOLIDAY ALERT*\n\n"
                            f"{COUNTRIES[entry['country']]}\n"
                            f"🎉 *{holiday['localName']}*\n"
                            f"📅 {holiday_date.strftime('%d %B %Y')}\n"
                            f"⏳ In {delta} days\n\n"
                            f"{holiday['description'] or 'Public holiday.'}"
                        )

                        send_message(chat_id, message)
                        sent[key] = True

    save_json("sent_alerts.json", sent)

# ===============================
# MAIN LOOP
# ===============================

if __name__ == "__main__":
    migrate_data()

    offset = None
    last_check = None

    while True:
        data = get_updates(offset)

        for update in data.get("result", []):
            offset = update["update_id"] + 1

            if "message" in update:
                chat_id = str(update["message"]["chat"]["id"])
                text = update["message"].get("text", "")
                username = update["message"]["from"].get("username")

                data_users = load_json("subscriptions.json")
                data_users.setdefault(chat_id, {
                    "subscriptions": [],
                    "alert_days": DEFAULT_ALERT_DAYS,
                    "mute_until": None,
                    "timezone": "UTC"
                })
                save_json("subscriptions.json", data_users)

                if text == "/settings":
                    show_settings(chat_id)

                if text == "/stats" and username == ADMIN_USERNAME:
                    users = len(data_users)
                    subs = sum(len(v["subscriptions"]) for v in data_users.values())
                    send_message(chat_id,
                        f"*📊 Radar Stats*\n\nUsers: {users}\nSubscriptions: {subs}"
                    )

            if "callback_query" in update:
                chat_id = str(update["callback_query"]["message"]["chat"]["id"])
                data_cb = update["callback_query"]["data"]
                data_users = load_json("subscriptions.json")

                if data_cb == "mute_7":
                    data_users[chat_id]["mute_until"] = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

                elif data_cb == "mute_30":
                    data_users[chat_id]["mute_until"] = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

                elif data_cb == "unmute":
                    data_users[chat_id]["mute_until"] = None

                elif data_cb == "settings_tz":
                    buttons = []
                    for tz in POPULAR_TIMEZONES:
                        buttons.append([{
                            "text": tz,
                            "callback_data": f"tz_{tz}"
                        }])
                    send_message(chat_id, "Select timezone:", {"inline_keyboard": buttons})

                elif data_cb.startswith("tz_"):
                    tz = data_cb.replace("tz_", "")
                    data_users[chat_id]["timezone"] = tz

                save_json("subscriptions.json", data_users)

        today = datetime.utcnow().date()
        if last_check != today:
            check_and_notify()
            last_check = today

        time.sleep(5)
