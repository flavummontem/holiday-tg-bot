import requests
import json
import time
import os
from datetime import datetime

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")

ALERT_DAYS = [14, 7, 3, 1]

# ======= КОНТУРЫ СТРАН =======

BUSINESS_COUNTRIES = [
    "AO","AR","AM","AZ","BY","BJ","BO","BW","KH","CM","CO","CD",
    "EG","ET","GE","GH","GT","IL","CI","KZ","KE","MU","MD","MA",
    "MZ","NA","NP","NG","NO","OM","PK","PY","PE","RU","SN","RS",
    "TG","TR","AE","UZ","VE","ZM","ZW"
]

EMPLOYEE_COUNTRIES = BUSINESS_COUNTRIES.copy()

ALL_COUNTRIES = sorted(set(BUSINESS_COUNTRIES + EMPLOYEE_COUNTRIES))


# ======= ФАЙЛЫ =======

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


# ======= TELEGRAM =======

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


# ======= CALENDARIFIC =======

def get_holidays(country):
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
            "localName": h["name"]
        })

    return result


# ======= ОБРАБОТКА КОМАНД =======

def handle_update(update):
    subs = load_json("subscriptions.json")

    if "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        subs.setdefault(chat_id, {
            "business": False,
            "employee": False,
            "custom": []
        })

        # ===== START MENU =====
        if text == "/start":

            keyboard = {
                "keyboard": [
                    ["🏢 Business Presence"],
                    ["👥 Employee Presence"],
                    ["🌍 Select Specific Country"],
                    ["📋 My Subscriptions"],
                    ["❌ Unsubscribe All"]
                ],
                "resize_keyboard": True
            }

            send_message(
                chat_id,
                "👋 Welcome to Global Holiday Radar\n\n"
                "Built by the International Support team to help you stay ahead of public holidays worldwide.\n\n"
                "This bot keeps you informed about upcoming holidays in:\n\n"
                "🏢 Countries where we operate (Business Presence)\n"
                "👥 Countries where our employees are based (Employee Presence)\n\n"
                "You’ll receive alerts 14 / 7 / 3 / 1 days before each public holiday.\n\n"
                "Questions or ideas?\n"
                "@rubbeldiekatz",
                reply_markup=keyboard
            )

        elif text == "🏢 Business Presence":
            subs[chat_id]["business"] = True
            save_json("subscriptions.json", subs)
            send_message(chat_id, "✅ Subscribed to Business Presence countries")

        elif text == "👥 Employee Presence":
            subs[chat_id]["employee"] = True
            save_json("subscriptions.json", subs)
            send_message(chat_id, "✅ Subscribed to Employee Presence countries")

        elif text == "🌍 Select Specific Country":

            keyboard = {
                "inline_keyboard": [
                    [{"text": code, "callback_data": f"country:{code}"}]
                    for code in ALL_COUNTRIES
                ]
            }

            send_message(chat_id, "Select a country:", keyboard)

        elif text == "📋 My Subscriptions":
            send_message(chat_id, json.dumps(subs[chat_id], indent=2))

        elif text == "❌ Unsubscribe All":
            subs[chat_id] = {
                "business": False,
                "employee": False,
                "custom": []
            }
            save_json("subscriptions.json", subs)
            send_message(chat_id, "All subscriptions cleared.")

    if "callback_query" in update:
        chat_id = str(update["callback_query"]["message"]["chat"]["id"])
        data = update["callback_query"]["data"]

        subs.setdefault(chat_id, {
            "business": False,
            "employee": False,
            "custom": []
        })

        if data.startswith("country:"):
            code = data.split(":")[1]
            if code not in subs[chat_id]["custom"]:
                subs[chat_id]["custom"].append(code)
                save_json("subscriptions.json", subs)
                send_message(chat_id, f"✅ Subscribed to {code}")


# ======= АЛЕРТЫ =======

def check_and_notify():
    subs = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")

    today = datetime.utcnow().date()

    for chat_id, data in subs.items():

        countries = set(data["custom"])

        if data["business"]:
            countries.update(BUSINESS_COUNTRIES)

        if data["employee"]:
            countries.update(EMPLOYEE_COUNTRIES)

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


# ======= MAIN LOOP =======

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
