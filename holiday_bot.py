import requests
import json
import time
import os
from datetime import datetime

TOKEN = os.getenv("TOKEN")

ALERT_DAYS = [14, 7, 3, 1]

PRODUCTS = {
    "Taxi B2C": [
        "UZ","AM","AZ","GE","TR","MD","RS","ET","ZW","BW","GH","ZM",
        "BJ","TG","SN","CI","BO","CO","PE","VE","GT","PK","NP",
        "AE","OM","MA","IL"
    ],
    "Taxi B2B": [
        "PE","ZM","AZ","AE","CI","AM","UZ","RS","BO"
    ],
    "Drive": [
        "AE","KZ","RU"
    ],
    "YangoPay": [
        "CI","ZM"
    ],
    "Buy&Sell": [
        "CI"
    ],
    "Scooters": [
        "UZ","CO","AM","GE","RS","AE","PE","TR","AZ"
    ],
    "Beri Zaryad": [
        "UZ","AE","CO","AM","RS","GE"
    ]
}

ALL_COUNTRIES = sorted(set(
    c for arr in PRODUCTS.values() for c in arr
))

# ---------------- FILE HELPERS ----------------

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# ---------------- TELEGRAM ----------------

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    requests.post(url, data=payload)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()

# ---------------- HOLIDAYS ----------------

def get_holidays(country):
    year = datetime.utcnow().year
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
    r = requests.get(url)
    if r.status_code != 200:
        return []
    return r.json()

# ---------------- COMMANDS ----------------

def handle_update(update):
    subs = load_json("subscriptions.json")

    if "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        subs.setdefault(chat_id, {"countries": [], "products": []})

        if text == "/start":
            send_message(chat_id,
                "Holiday bot.\n"
                "/subscribe_country\n"
                "/subscribe_product\n"
                "/list\n"
                "/clear"
            )

        elif text == "/subscribe_country":
            keyboard = {
                "inline_keyboard": [
                    [{"text": code, "callback_data": f"country:{code}"}]
                    for code in ALL_COUNTRIES
                ]
            }
            send_message(chat_id, "Choose country:", keyboard)

        elif text == "/subscribe_product":
            keyboard = {
                "inline_keyboard": [
                    [{"text": name, "callback_data": f"product:{name}"}]
                    for name in PRODUCTS.keys()
                ]
            }
            send_message(chat_id, "Choose product:", keyboard)

        elif text == "/list":
            send_message(chat_id, json.dumps(subs[chat_id], indent=2))

        elif text == "/clear":
            subs[chat_id] = {"countries": [], "products": []}
            save_json("subscriptions.json", subs)
            send_message(chat_id, "Subscriptions cleared")

    if "callback_query" in update:
        chat_id = str(update["callback_query"]["message"]["chat"]["id"])
        data = update["callback_query"]["data"]

        subs.setdefault(chat_id, {"countries": [], "products": []})

        if data.startswith("country:"):
            code = data.split(":")[1]
            if code not in subs[chat_id]["countries"]:
                subs[chat_id]["countries"].append(code)
                send_message(chat_id, f"Subscribed to {code}")

        if data.startswith("product:"):
            name = data.split("product:")[1]
            if name not in subs[chat_id]["products"]:
                subs[chat_id]["products"].append(name)
                send_message(chat_id, f"Subscribed to {name}")

        save_json("subscriptions.json", subs)

# ---------------- ALERTS ----------------

def check_and_notify():
    subs = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")

    today = datetime.utcnow().date()

    for chat_id, data in subs.items():

        countries = set(data["countries"])

        for product in data["products"]:
            countries.update(PRODUCTS.get(product, []))

        for country in countries:
            holidays = get_holidays(country)

            for holiday in holidays:
                holiday_date = datetime.strptime(
                    holiday["date"], "%Y-%m-%d"
                ).date()

                delta = (holiday_date - today).days

                if delta in ALERT_DAYS:
                    key = f"{chat_id}-{country}-{holiday['date']}-{delta}"

                    if key not in sent:
                        message = (
                            f"{country}\n"
                            f"{holiday['localName']}\n"
                            f"{holiday['date']}\n"
                            f"In {delta} days"
                        )
                        send_message(chat_id, message)
                        sent[key] = True

    save_json("sent_alerts.json", sent)

# ---------------- MAIN ----------------

if __name__ == "__main__":
    offset = None
    last_check = None

    while True:
        data = get_updates(offset)

        for update in data.get("result", []):
            offset = update["update_id"] + 1
            handle_update(update)

        today = datetime.utcnow().date()

        if last_check != today:
            check_and_notify()
            last_check = today

        time.sleep(5)
