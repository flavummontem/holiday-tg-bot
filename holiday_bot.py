import requests
import json
import time
import os
from datetime import datetime

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")
ADMIN_USERNAME = "rubbeldiekatz"

ALERT_DAYS = [14, 7, 3, 1]

COUNTRIES = {
    "AO": "🇦🇴 Angola", "AR": "🇦🇷 Argentina", "AM": "🇦🇲 Armenia",
    "AZ": "🇦🇿 Azerbaijan", "BY": "🇧🇾 Belarus", "BJ": "🇧🇯 Benin",
    "BO": "🇧🇴 Bolivia", "BW": "🇧🇼 Botswana", "KH": "🇰🇭 Cambodia",
    "CM": "🇨🇲 Cameroon", "CO": "🇨🇴 Colombia", "CD": "🇨🇩 Congo",
    "EG": "🇪🇬 Egypt", "ET": "🇪🇹 Ethiopia", "GE": "🇬🇪 Georgia",
    "GH": "🇬🇭 Ghana", "GT": "🇬🇹 Guatemala", "IL": "🇮🇱 Israel",
    "CI": "🇨🇮 Ivory Coast", "KZ": "🇰🇿 Kazakhstan",
    "KE": "🇰🇪 Kenya", "MU": "🇲🇺 Mauritius",
    "MD": "🇲🇩 Moldova", "MA": "🇲🇦 Morocco",
    "MZ": "🇲🇿 Mozambique", "NA": "🇳🇦 Namibia",
    "NP": "🇳🇵 Nepal", "NG": "🇳🇬 Nigeria",
    "NO": "🇳🇴 Norway", "OM": "🇴🇲 Oman",
    "PK": "🇵🇰 Pakistan", "PY": "🇵🇾 Paraguay",
    "PE": "🇵🇪 Peru", "RU": "🇷🇺 Russia",
    "SN": "🇸🇳 Senegal", "RS": "🇷🇸 Serbia",
    "TG": "🇹🇬 Togo", "TR": "🇹🇷 Turkey",
    "AE": "🇦🇪 UAE", "UZ": "🇺🇿 Uzbekistan",
    "VE": "🇻🇪 Venezuela", "ZM": "🇿🇲 Zambia",
    "ZW": "🇿🇼 Zimbabwe"
}

# ========= FILE UTILS =========

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

# ========= TELEGRAM =========

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    requests.post(url, data=payload)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()

# ========= CACHE =========

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

# ========= CALENDARIFIC =========

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

# ========= KEYBOARDS =========

def build_country_keyboard(sub_type):
    buttons = []
    items = list(COUNTRIES.items())

    for i in range(0, len(items), 2):
        row = []
        row.append({
            "text": items[i][1],
            "callback_data": f"add:{sub_type}:{items[i][0]}"
        })
        if i + 1 < len(items):
            row.append({
                "text": items[i+1][1],
                "callback_data": f"add:{sub_type}:{items[i+1][0]}"
            })
        buttons.append(row)

    return {"inline_keyboard": buttons}

def build_remove_keyboard(entries):
    buttons = []
    for i, entry in enumerate(entries):
        icon = "🏢" if entry["type"] == "business" else "👥" if entry["type"] == "employee" else "🌍"
        label = f"{icon} {COUNTRIES[entry['country']]}"
        buttons.append([{
            "text": label,
            "callback_data": f"remove:{i}"
        }])
    return {"inline_keyboard": buttons}

# ========= HANDLER =========

def handle_update(update):
    subs = load_json("subscriptions.json")

    if "message" in update:
        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "")
        username = msg["from"].get("username", "")

        subs.setdefault(chat_id, [])

        if text == "/start":

            keyboard = {
                "keyboard": [
                    ["🏢 Where We Operate (Business Presence Countries)"],
                    ["👥 Where Our Employees Are (Employee Presence Countries)"],
                    ["🌍 Choose a Country"],
                    ["📋 My Subscriptions"],
                    ["➖ Remove a Subscription"],
                    ["❌ Unsubscribe All"]
                ],
                "resize_keyboard": True
            }

            send_message(
                chat_id,
                "*👋 Welcome to Global Holiday Radar*\n\n"
                "Stay ahead of public holidays worldwide.\n\n"
                "You’ll receive alerts 14 / 7 / 3 / 1 days in advance.\n\n"
                "Questions? @rubbeldiekatz",
                keyboard
            )

        elif text.startswith("🏢 Where We Operate"):
            send_message(chat_id, "Select a country:", build_country_keyboard("business"))

        elif text.startswith("👥 Where Our Employees"):
            send_message(chat_id, "Select a country:", build_country_keyboard("employee"))

        elif text == "🌍 Choose a Country":
            send_message(chat_id, "Select a country:", build_country_keyboard("custom"))

        elif text == "📋 My Subscriptions":
            if not subs[chat_id]:
                send_message(chat_id, "You have no active subscriptions.")
            else:
                message = "*📋 Your Subscriptions*\n\n"
                for entry in subs[chat_id]:
                    icon = "🏢" if entry["type"] == "business" else "👥" if entry["type"] == "employee" else "🌍"
                    message += f"{icon} {COUNTRIES[entry['country']]}\n"
                send_message(chat_id, message)

        elif text == "➖ Remove a Subscription":
            if not subs[chat_id]:
                send_message(chat_id, "No subscriptions to remove.")
            else:
                send_message(chat_id, "Select a subscription to remove:", build_remove_keyboard(subs[chat_id]))

        elif text == "❌ Unsubscribe All":
            subs[chat_id] = []
            save_json("subscriptions.json", subs)
            send_message(chat_id, "All subscriptions cleared.")

        elif text == "/stats" and username == ADMIN_USERNAME:
            total_users = len(subs)
            total_subs = sum(len(v) for v in subs.values())
            send_message(chat_id,
                f"*📊 Global Holiday Radar Stats*\n\n"
                f"Users: {total_users}\n"
                f"Total Subscriptions: {total_subs}"
            )

    if "callback_query" in update:
        chat_id = str(update["callback_query"]["message"]["chat"]["id"])
        data = update["callback_query"]["data"]

        subs.setdefault(chat_id, [])

        if data.startswith("add:"):
            _, sub_type, country = data.split(":")
            entry = {"country": country, "type": sub_type}
            if entry not in subs[chat_id]:
                subs[chat_id].append(entry)
                save_json("subscriptions.json", subs)
                send_message(chat_id, f"✅ Subscribed to {COUNTRIES[country]}")

        elif data.startswith("remove:"):
            index = int(data.split(":")[1])
            removed = subs[chat_id].pop(index)
            save_json("subscriptions.json", subs)
            send_message(chat_id, f"Removed {COUNTRIES[removed['country']]}")

# ========= ALERT ENGINE =========

def check_and_notify():
    subs = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")

    today = datetime.utcnow().date()

    for chat_id, entries in subs.items():
        for entry in entries:

            country = entry["country"]
            sub_type = entry["type"]

            holidays = get_cached_holidays(country)

            for holiday in holidays:
                holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
                delta = (holiday_date - today).days

                if delta in ALERT_DAYS:
                    key = f"{chat_id}-{country}-{sub_type}-{holiday['date']}-{delta}"

                    if key not in sent:

                        formatted_date = holiday_date.strftime("%d %B %Y")

                        header = "🌍 HOLIDAY ALERT"
                        if sub_type == "business":
                            header = "🚖 BUSINESS HOLIDAY ALERT"
                        elif sub_type == "employee":
                            header = "👥 EMPLOYEE HOLIDAY ALERT"

                        message = (
                            f"*{header}*\n\n"
                            f"{COUNTRIES[country]}\n"
                            f"🎉 *{holiday['localName']}*\n"
                            f"📅 {formatted_date}\n"
                            f"⏳ In {delta} days\n\n"
                            f"{holiday['description'] or 'Public holiday. Government institutions may be closed.'}"
                        )

                        send_message(chat_id, message)
                        sent[key] = True

    save_json("sent_alerts.json", sent)

# ========= MAIN LOOP =========

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
