import asyncio
import aiohttp
import telebot
import threading
from flask import Flask
import os

# =========================
# 🔧 НАСТРОЙКИ
# =========================

TELEGRAM_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM"
UKRAINEALARM_TOKEN = "14d49bd6:19c6d5a643e2fddfb2a473e9c4c08ccd"

CITY_ID = 564  # Запорожье (город)
GROUP_ID = -1003088722284  # твоя приватная группа

CHECK_INTERVAL = 20  # проверка каждые 20 секунд

# =========================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

current_status = None


@app.route("/")
def home():
    return "Bot is running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


async def check_alarm():
    global current_status

    url = f"https://api.ukrainealarm.com/api/v3/alerts/{CITY_ID}"

    headers = {
        "Authorization": UKRAINEALARM_TOKEN
    }

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        alarm_active = data.get("activeAlerts", [])

                        if alarm_active:
                            if current_status != "ALARM":
                                current_status = "ALARM"
                                bot.send_message(
                                    GROUP_ID,
                                    "🚨 ВОЗДУШНАЯ ТРЕВОГА В ЗАПОРОЖЬЕ!"
                                )
                        else:
                            if current_status != "CLEAR":
                                current_status = "CLEAR"
                                bot.send_message(
                                    GROUP_ID,
                                    "✅ Отбой тревоги"
                                )
                    else:
                        print("Ошибка API:", resp.status)

        except Exception as e:
            print("Ошибка:", e)

        await asyncio.sleep(CHECK_INTERVAL)


def start_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_alarm())


if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    threading.Thread(target=start_async_loop).start()
    bot.infinity_polling()
