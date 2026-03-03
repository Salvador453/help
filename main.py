import telebot
import threading
import requests
from flask import Flask
import os
import time

# =========================
# 🔧 НАСТРОЙКИ
# =========================

TELEGRAM_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM"
UKRAINEALARM_TOKEN = "14d49bd6:19c6d5a643e2fddfb2a473e9c4c08ccd"

CITY_ID = 564
GROUP_ID = -1003088722284

CHECK_INTERVAL = 20

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


def check_alarm():
    global current_status

    url = f"https://api.ukrainealarm.com/api/v3/alerts/{CITY_ID}"
    headers = {"Authorization": UKRAINEALARM_TOKEN}

    while True:
        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
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
                            "✅ Отбой тревоги в Запорожье"
                        )

            else:
                print("Ошибка API:", response.status_code)

        except Exception as e:
            print("Ошибка:", e)

        time.sleep(CHECK_INTERVAL)


# =========================
# 📌 /status
# =========================

@bot.message_handler(commands=['status'])
def status_command(message):
    if current_status is None:
        bot.reply_to(message, "⏳ Бот запускается, ожидаем данные...")
    elif current_status == "ALARM":
        bot.reply_to(message, "🚨 Сейчас тревога в Запорожье")
    else:
        bot.reply_to(message, "✅ Сейчас отбоя тревоги в Запорожье")


if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    threading.Thread(target=check_alarm).start()
    bot.infinity_polling()
