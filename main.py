import asyncio
import aiohttp
import logging
import os
import threading
from datetime import datetime
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

# ================= НАСТРОЙКИ =================

BOT_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM"
ALERT_CHAT_IDS = ["-1003088722284"]

API_BASE_URL = "https://api.ukrainealarm.com/api/v3"
API_KEY = "14d49bd6:19c6d5a643e2fddfb2a473e9c4c08ccd"

REGION_ID = "564"
REGION_NAME = "м. Запоріжжя"

HEADERS = {
    "Authorization": API_KEY,
    "Accept": "application/json"
}

# ================= ЛОГИ =================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= СОСТОЯНИЕ =================

LAST_ALERT_STATE = False
session = None

# ================= API =================

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

async def get_alert_status(region_id):
    try:
        session = await get_session()
        url = f"{API_BASE_URL}/alerts/{region_id}"

        async with session.get(url, headers=HEADERS, timeout=10) as response:

            if response.status == 200:
                data = await response.json()

                if not data:
                    return False

                return data[0].get("isActive", False)

            else:
                text = await response.text()
                logger.error(f"API ERROR {response.status}: {text}")
                return "error"

    except Exception as e:
        logger.error(f"API EXCEPTION: {e}")
        return "error"

# ================= БОТ =================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        f"🚀 <b>Бот тревог</b>\n\n"
        f"📍 {REGION_NAME}\n"
        f"/status — статус"
    )

@dp.message(Command("status"))
async def status_handler(message: Message):
    await message.answer("🔄 Проверяю...")

    status = await get_alert_status(REGION_ID)

    if status == "error":
        await message.answer("⚠️ Временная ошибка API, попробуйте позже")
        return

    if status:
        await message.answer("🚨 <b>ТРИВОГА</b>")
    else:
        await message.answer("✅ <b>ВІДБІЙ</b>")

# ================= МОНИТОРИНГ =================

async def monitor_alerts():
    global LAST_ALERT_STATE

    await asyncio.sleep(5)
    logger.info("Мониторинг запущен")

    while True:
        current_state = await get_alert_status(REGION_ID)

        if current_state == "error":
            await asyncio.sleep(30)
            continue

        if current_state and not LAST_ALERT_STATE:
            text = f"🚨 <b>ТРИВОГА!</b>\n🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}\n📍 {REGION_NAME}"
            for chat_id in ALERT_CHAT_IDS:
                await bot.send_message(chat_id, text)

        if not current_state and LAST_ALERT_STATE:
            text = f"✅ <b>ВІДБІЙ</b>\n🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}\n📍 {REGION_NAME}"
            for chat_id in ALERT_CHAT_IDS:
                await bot.send_message(chat_id, text)

        LAST_ALERT_STATE = current_state
        await asyncio.sleep(20)

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def home():
    icon = "🚨" if LAST_ALERT_STATE else "✅"
    return f"<h1>{icon} Бот работает</h1>"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ================= ЗАПУСК =================

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(monitor_alerts())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
