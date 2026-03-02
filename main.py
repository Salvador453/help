import asyncio
import requests
import logging
import os
import threading
from datetime import datetime
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен и настройки
BOT_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM" 
ALERT_CHAT_IDS = ["-1003088722284"]
API_URL = "https://ubilling.net.ua/aerialalerts/"
ZAPORIZHZHIA_REGION = "Запорізька область"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
LAST_ZP_STATE = {"alertnow": False, "changed": "1970-01-01 00:00:00"}

# ====== Обработчики команд ======

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "<b>Привіт!</b>\nЯ бот, який сповіщає про тривоги в <b>Запоріжжі</b>.\n\n"
        "Я працюю автоматично и повідомлю вас тут або в каналі.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Карта тривог", url="https://map.ukrainealarm.com/")]
        ])
    )

@dp.message(Command("status"))
async def status_handler(message: Message):
    status_text = "🚨 ТРИВОГА" if LAST_ZP_STATE["alertnow"] else "✅ ВІДБІЙ"
    await message.answer(
        f"<b>Поточний статус:</b> {status_text}\n"
        f"<b>Остання зміна:</b> {LAST_ZP_STATE['changed']}"
    )

# ====== Мини-вебсервер для Render ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот живий! Слідкую за тривогами в Запоріжжі 🚨"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ====== Логика уведомлений ======
async def check_zaporizhzhia_alert():
    global LAST_ZP_STATE
    while True:
        try:
            r = requests.get(API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            zp_info = data.get("states", {}).get(ZAPORIZHZHIA_REGION, {})

            is_active_now = zp_info.get("alertnow", False)
            changed_time = zp_info.get("changed", "невідомо")

            if is_active_now and not LAST_ZP_STATE["alertnow"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = f"🚨 <b>ПОВІТРЯНА ТРИВОГА В ЗАПОРІЖЖІ!</b>\n\n🕒 Початок: {time_str}"
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)
                logger.info("Alert ON sent")
                
            elif not is_active_now and LAST_ZP_STATE["alertnow"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = f"✅ <b>Відбій тривоги в Запоріжжі</b>\n\n🕒 Відбій: {time_str}"
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)
                logger.info("Alert OFF sent")

            LAST_ZP_STATE = {"alertnow": is_active_now, "changed": changed_time}
        except Exception as e:
            logger.error(f"Ошибка API: {e}")
        await asyncio.sleep(20)

# ====== Запуск ======
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(check_zaporizhzhia_alert())
    logger.info("Бот запущен и ожидает сообщений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
