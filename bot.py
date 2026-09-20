import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

TZ = ZoneInfo("Europe/Moscow")


def get_holidays():
    today = datetime.now(TZ)

    url = (
        f"https://www.calend.ru/day/"
        f"{today.year}-{today.month}-{today.day}/"
    )

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    holidays = []

    # Находим раздел «Праздники»
    heading = soup.find(
        lambda tag: tag.name in ["h1", "h2", "h3"]
        and "Праздники" in tag.get_text()
    )

    if heading:
        for element in heading.find_all_next(["h3", "h4"]):
            text = element.get_text(" ", strip=True)

            if text:
                if text in [
                    "В народном календаре",
                    "Именины",
                    "Хроника",
                    "Персоны"
                ]:
                    break

                if text not in holidays:
                    holidays.append(text)

    return holidays[:10]


def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        },
        timeout=30
    )

    response.raise_for_status()


def main():
    today = datetime.now(TZ)

    months = [
        "января", "февраля", "марта", "апреля",
        "мая", "июня", "июля", "августа",
        "сентября", "октября", "ноября", "декабря"
    ]

    holidays = get_holidays()

    message = (
        f"☀️ <b>Доброе утро!</b>\n\n"
        f"📅 Сегодня {today.day} {months[today.month - 1]} "
        f"{today.year} года\n\n"
        f"🎉 <b>Праздники сегодня:</b>\n"
    )

    if holidays:
        for holiday in holidays:
            message += f"• {holiday}\n"
    else:
        message += "• Праздники не найдены.\n"

    send_message(message)


if __name__ == "__main__":
    main()
