import requests
import json
import time
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
CALENDARIFIC_KEY = os.getenv("CALENDARIFIC_KEY")
ADMIN_USERNAME = "rubbeldiekatz"

ALERT_DAYS = [14, 7, 3, 1]
PAGE_SIZE = 10

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

    cache[country] = {"date": today_str, "holidays": holidays}
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

# ========= PAGINATED COUNTRY KEYBOARD =========

def build_country_keyboard(sub_type, page=0):
    items = list(COUNTRIES.items())
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    slice_items = items[start:end]

    buttons = []

    for code, label in slice_items:
        buttons.append([{
            "text": label,
            "callback_data": f"add:{sub_type}:{code}"
        }])

    nav = []
    if start > 0:
        nav.append({"text": "⬅️ Prev", "callback_data": f"page:{sub_type}:{page-1}"})
    if end < len(items):
        nav.append({"text": "Next ➡️", "callback_data": f"page:{sub_type}:{page+1}"})

    if nav:
        buttons.append(nav)

    return {"inline_keyboard": buttons}

# ========= WEEKLY DIGEST =========

def send_weekly_digest():
    subs = load_json("subscriptions.json")
    today = datetime.utcnow().date()

    if today.weekday() != 0:  # Monday
        return

    for chat_id, entries in subs.items():
        upcoming = []

        for entry in entries:
            holidays = get_cached_holidays(entry["country"])
            for holiday in holidays:
                holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
                if 0 <= (holiday_date - today).days <= 14:
                    upcoming.append((holiday_date, entry["country"], holiday["localName"]))

        if upcoming:
            upcoming.sort()
            message = "*📅 Weekly Holiday Digest*\n\nUpcoming in next 14 days:\n\n"
            for date, country, name in upcoming:
                message += f"{COUNTRIES[country]} — {name} ({date.strftime('%d %b')})\n"

            send_message(chat_id, message)

# ========= ALERT ENGINE =========

def check_and_notify():
    subs = load_json("subscriptions.json")
    sent = load_json("sent_alerts.json")
    today = datetime.utcnow().date()

    for chat_id, entries in subs.items():
        for entry in entries:
            holidays = get_cached_holidays(entry["country"])

            for holiday in holidays:
                holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
                delta = (holiday_date - today).days

                if delta in ALERT_DAYS:
                    key = f"{chat_id}-{entry['country']}-{entry['type']}-{holiday['date']}-{delta}"

                    if key not in sent:
                        formatted_date = holiday_date.strftime("%d %B %Y")
                        header = "🌍 HOLIDAY ALERT"
                        if entry["type"] == "business":
                            header = "🚖 BUSINESS HOLIDAY ALERT"
                        elif entry["type"] == "employee":
                            header = "👥 EMPLOYEE HOLIDAY ALERT"

                        message = (
                            f"*{header}*\n\n"
                            f"{COUNTRIES[entry['country']]}\n"
                            f"🎉 *{holiday['localName']}*\n"
                            f"📅 {formatted_date}\n"
                            f"⏳ In {delta} days\n\n"
                            f"{holiday['description'] or 'Public holiday.'}"
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

            if "callback_query" in update:
                data_cb = update["callback_query"]["data"]
                chat_id = str(update["callback_query"]["message"]["chat"]["id"])

                if data_cb.startswith("page:"):
                    _, sub_type, page = data_cb.split(":")
                    send_message(chat_id, "Select a country:",
                                 build_country_keyboard(sub_type, int(page)))

                elif data_cb.startswith("add:"):
                    _, sub_type, country = data_cb.split(":")
                    subs = load_json("subscriptions.json")
                    subs.setdefault(chat_id, [])
                    entry = {"country": country, "type": sub_type}
                    if entry not in subs[chat_id]:
                        subs[chat_id].append(entry)
                        save_json("subscriptions.json", subs)
                        send_message(chat_id, f"✅ Subscribed to {COUNTRIES[country]}")

        today = datetime.utcnow().date()

        if last_check != today:
            check_and_notify()
            send_weekly_digest()
            last_check = today

        time.sleep(5)
