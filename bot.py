import os
import html
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

TZ = ZoneInfo("Europe/Samara")

MAX_HOLIDAYS = 15   # сколько праздников показывать
MAX_WORLD = 0       # праздники других стран (0 = не показывать, например 5)

# Новокуйбышевск
LAT, LON = 53.10, 49.95

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}

SRC_MAIN = ("my-calend.ru", "https://my-calend.ru/holidays")
SRC_BACKUP = ("calend.ru", "https://www.calend.ru/")

# «День таможенника – Беларусь»: длинное тире с пробелами и страна в конце
FOREIGN = re.compile(r"\s[–—]\s\S")


def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def from_my_calend():
    soup = fetch("https://my-calend.ru/holidays")

    heading = None
    for h in soup.find_all(["h1", "h2", "h3"]):
        if "Праздники сегодня" in h.get_text():
            heading = h
            break

    if heading is None:
        print("my-calend: не найден заголовок «Праздники сегодня»")
        return [], []

    ul = heading.find_next("ul")
    if ul is None:
        print("my-calend: после заголовка нет списка")
        return [], []

    main, world = [], []

    for li in ul.find_all("li"):
        text = li.get_text(" ", strip=True)
        # справа от названия стоит число (рейтинг) — убираем его
        text = re.sub(r"\s*\d+\s*$", "", text).strip()

        if not text:
            continue

        if FOREIGN.search(text):
            if text not in world:
                world.append(text)
        elif text not in main:
            main.append(text)

    print("my-calend: найдено", len(main), "и", len(world))
    return main[:MAX_HOLIDAYS], world[:MAX_WORLD]


HOLIDAY_LINK = re.compile(r"/holidays/0/0/\d+/?$")


def from_calend():
    today = datetime.now(TZ)
    soup = fetch(
        f"https://www.calend.ru/day/{today.year}-{today.month}-{today.day}/"
    )

    start = soup.find("h1")
    if start is None:
        return []

    holidays = []
    for a in start.find_all_next("a", href=True):
        href = a["href"]
        if href.rstrip("/").endswith("/narod"):
            break
        if not HOLIDAY_LINK.search(href):
            continue
        text = a.get_text(" ", strip=True)
        if not text or len(text) > 100:
            continue
        if text not in holidays:
            holidays.append(text)

    print("calend.ru: найдено", len(holidays))
    return holidays[:MAX_HOLIDAYS]


def get_holidays():
    try:
        holidays, world = from_my_calend()
        if holidays:
            return holidays, world, SRC_MAIN
    except Exception as e:
        print("my-calend не сработал:", repr(e))

    try:
        holidays = from_calend()
        if holidays:
            return holidays, [], SRC_BACKUP
    except Exception as e:
        print("calend.ru не сработал:", repr(e))

    return [], [], None


def get_weather():
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": LAT,
                "longitude": LON,
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,precipitation_sum"
                ),
                "timezone": "Europe/Samara",
                "forecast_days": 1,
            },
            timeout=30,
        )
        response.raise_for_status()
        d = response.json()["daily"]

        t_max = round(d["temperature_2m_max"][0])
        t_min = round(d["temperature_2m_min"][0])
        prob = d["precipitation_probability_max"][0] or 0
        rain = d["precipitation_sum"][0] or 0
    except Exception as e:
        print("погода не получена:", repr(e))
        return None

    if prob >= 50 or rain >= 1:
        verdict = "☔ Будет дождь, возьмите зонт"
    elif prob >= 30:
        verdict = "🌂 Дождь возможен, зонт лучше взять"
    else:
        verdict = "😎 Дождя не ожидается, зонт не нужен"

    print("погода:", t_min, t_max, prob, rain)
    return f"{verdict} (осадки: {prob}%)\n🌡 {t_min:+d}…{t_max:+d} °C"


def send_message(text):
    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()


def wait_until(hour, minute):
    now = datetime.now(TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delay = (target - now).total_seconds()
    if 0 < delay <= 3600:
        print("Жду", int(delay), "сек до", hour, ":", minute)
        time.sleep(delay)


def main():
    today = datetime.now(TZ)

    months = [
        "января", "февраля", "марта", "апреля",
        "мая", "июня", "июля", "августа",
        "сентября", "октября", "ноября", "декабря",
    ]

    holidays, world, source = get_holidays()
    weather = get_weather()
    wait_until(6, 30)

    message = (
        f"☀️ <b>Доброе утро!</b>\n\n"
        f"📅 Сегодня {today.day} {months[today.month - 1]} "
        f"{today.year} года\n\n"
    )

    if weather:
        message += f"🌤 <b>Погода в Новокуйбышевске:</b>\n{weather}\n\n"

    message += "🎉 <b>Праздники сегодня:</b>\n"

    if holidays:
        for holiday in holidays:
            message += f"• {html.escape(holiday)}\n"
    else:
        message += "• Праздники не найдены.\n"

    if world:
        message += "\n🌍 <b>В мире:</b>\n"
        for holiday in world:
            message += f"• {html.escape(holiday)}\n"

    if source:
        name, url = source
        message += f'\n<i>Источник: <a href="{url}">{name}</a></i>'

    send_message(message)


if __name__ == "__main__":
    main()
