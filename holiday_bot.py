import requests
import json
import time
from datetime import datetime

TOKEN = "8565694614:AAG8Z_6RkgSs14i_rbREV4-A0_MJkKJMqZk"

COUNTRIES = {
    "KZ": "Kazakhstan",
    "US": "United States",
    "DE": "Germany",
    "AE": "UAE",
    "PK": "Pakistan"
}

ALERT_DAYS = [14, 7, 3, 1]

# ---------------- TELEGRAM ----------------

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
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

# ---------------- SUBSCRIPTIONS ----------------

def load_subscriptions():
    with open("subscriptions.json", "r") as f:
        return json.load(f)

def save_subscriptions(data):
    with open("subscriptions.json", "w") as f:
        json.dump(data, f, indent=2)

# ---------------- HOLIDAYS ----------------

def get_holidays(country):
    year = datetime.now().year
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
    r = requests.get(url)
    if r.status_code != 200:
        return []
    return r.json()

# ---------------- HANDLE COMMANDS ----------------

def handle_update(update):
    subscriptions = load_subscriptions()

    if "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "Welcome! Use /subscribe to choose countries.")

        elif text == "/subscribe":
            keyboard = {
                "inline_keyboard": [
                    [{"text": f"{code} - {name}", "callback_data": code}]
                    for code, name in COUNTRIES.items()
                ]
            }
            send_message(chat_id, "Choose country:", keyboard)

        elif text == "/list":
            user_subs = subscriptions.get(chat_id, [])
            send_message(chat_id, f"Your subscriptions: {user_subs}")

    if "callback_query" in update:
        chat_id = str(update["callback_query"]["message"]["chat"]["id"])
        country = update["callback_query"]["data"]

        subscriptions.setdefault(chat_id, [])

        if country not in subscriptions[chat_id]:
            subscriptions[chat_id].append(country)
            save_subscriptions(subscriptions)
            send_message(chat_id, f"Subscribed to {country}")

# ---------------- DAILY CHECK ----------------

def check_and_notify():
    today = datetime.now().date()
    subscriptions = load_subscriptions()

    for chat_id, countries in subscriptions.items():
        for country in countries:
            holidays = get_holidays(country)

            for holiday in holidays:
                holiday_date = datetime.strptime(
                    holiday["date"], "%Y-%m-%d"
                ).date()

                delta = (holiday_date - today).days

                if delta in ALERT_DAYS:
                    message = (
                        f"🌍 {country}\n"
                        f"🎉 {holiday['localName']}\n"
                        f"📅 {holiday['date']}\n"
                        f"⏳ In {delta} days"
                    )
                    send_message(chat_id, message)

# ---------------- MAIN LOOP ----------------

if __name__ == "__main__":
    print("Bot is running...")

    offset = None

    while True:
        data = get_updates(offset)

        for update in data.get("result", []):
            offset = update["update_id"] + 1
            handle_update(update)

        time.sleep(1)
