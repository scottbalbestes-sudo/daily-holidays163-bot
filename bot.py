import os
import html
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

TZ = ZoneInfo("Europe/Moscow")

MAX_HOLIDAYS = 15   # сколько праздников показывать
MAX_WORLD = 0       # праздники других стран (0 = не показывать, например 5)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}

SRC_MAIN = ("kakoysegodnyaprazdnik.ru", "https://kakoysegodnyaprazdnik.ru/")
SRC_BACKUP = ("calend.ru", "https://www.calend.ru/")


def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def from_kakoysegodnyaprazdnik():
    soup = fetch("https://kakoysegodnyaprazdnik.ru/")

    listing = soup.select_one("div.listing_wr")
    if listing is None:
        print("kakoysegodnyaprazdnik: не найден блок listing_wr")
        return [], []

    # Всё, что идёт после div#national — праздники других стран
    marker = listing.find(id="national")
    foreign_ids = set()
    if marker is not None:
        foreign_ids = {
            id(tag) for tag in marker.find_all_next("div", class_="main")
        }

    main, world = [], []

    for block in listing.find_all("div", class_="main"):
        span = block.find("span", itemprop="text")
        if span is None:
            continue

        text = span.get_text(" ", strip=True)
        if not text or text.startswith("Именины"):
            continue

        if id(block) in foreign_ids:
            if " - " in text and text not in world:
                world.append(text)
            continue

        if text not in main:
            main.append(text)

    print("kakoysegodnyaprazdnik: найдено", len(main), "и", len(world))
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
        holidays, world = from_kakoysegodnyaprazdnik()
        if holidays:
            return holidays, world, SRC_MAIN
    except Exception as e:
        print("kakoysegodnyaprazdnik не сработал:", repr(e))

    try:
        holidays = from_calend()
        if holidays:
            return holidays, [], SRC_BACKUP
    except Exception as e:
        print("calend.ru не сработал:", repr(e))

    return [], [], None


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


def main():
    today = datetime.now(TZ)

    months = [
        "января", "февраля", "марта", "апреля",
        "мая", "июня", "июля", "августа",
        "сентября", "октября", "ноября", "декабря",
    ]

    holidays, world, source = get_holidays()

    message = (
        f"☀️ <b>Доброе утро!</b>\n\n"
        f"📅 Сегодня {today.day} {months[today.month - 1]} "
        f"{today.year} года\n\n"
        f"🎉 <b>Праздники сегодня:</b>\n"
    )

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
