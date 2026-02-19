import requests
import json
import time
import os
from datetime import datetime

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")

ALERT_DAYS = [14, 7, 3, 1]

# ======= СТРАНЫ С ФЛАГАМИ =======

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
    "CD": "🇨🇩 Congo",
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

BUSINESS_COUNTRIES = list(COUNTRIES.keys())
EMPLOYEE_COUNTRIES = list(COUNTRIES.keys())


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
            "localName": h["name"],
            "description": h.get("description", "")
        })

    return result


# ======= МЕНЮ СТРАН =======

def build_country_keyboard():
    buttons = []
    items = list(COUNTRIES.items())

    for i in range(0, len(items), 2):
        row = []

        row.append({
            "text": items[i][1],
            "callback_data": f"country:{items[i][0]}"
        })

        if i + 1 < len(items):
            row.append({
                "text": items[i+1][1],
                "callback_data": f"country:{items[i+1][0]}"
            })

        buttons.append(row)

    return {"inline_keyboard": buttons}


# ======= ОБРАБОТКА =======

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
                "This bot was built by the International Support team\n"
                "to help you stay ahead of public holidays worldwide.\n\n"
                "What can it do?\n\n"
                "🏢 Track holidays in countries where we operate\n"
                "👥 Track holidays in countries where our employees are based\n"
                "🌍 Track specific countries of your choice\n\n"
                "You’ll receive alerts\n"
                "14 / 7 / 3 / 1 days before each public holiday.\n\n"
                "Use the menu below to subscribe.\n\n"
                "Questions, feedback or improvements?\n"
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
            send_message(chat_id, "Select a country:", build_country_keyboard())

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
                send_message(chat_id, f"✅ Subscribed to {COUNTRIES[code]}")


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
                            f"{COUNTRIES[country]}\n"
                            f"🎉 {holiday['localName']}\n"
                            f"📅 {holiday['date']}\n"
                            f"⏳ In {delta} days\n\n"
                            f"{holiday['description'] or 'Public holiday. Government institutions may be closed.'}"
                        )
                        send_message(chat_id, message)
                        sent[key] = True

    save_json("sent_alerts.json", sent)


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
