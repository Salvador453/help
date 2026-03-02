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

# ====== ОБРАБОТЧИКИ КОМАНД ======

# Заменили /start на /go
@dp.message(Command("go"))
async def go_handler(message: Message):
    await message.answer(
        "<b>Бот запущен!</b> 🚀\n\nЯ мониторю воздушную тревогу в <b>Запорожье</b> в реальном времени.\n"
        "Используйте команду /status, чтобы узнать текущую обстановку.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Карта тревог 🗺", url="https://map.ukrainealarm.com/")]
        ])
    )

# Команда для проверки статуса
@dp.message(Command("status"))
async def status_handler(message: Message):
    if LAST_ZP_STATE["alertnow"]:
        status_icon = "🚨"
        status_text = "ВНИМАНИЕ! В Запорожье сейчас ТРЕВОГА!"
    else:
        status_icon = "✅"
        status_text = "В Запорожье сейчас ОТБОЙ. Все спокойно."
    
    await message.answer(
        f"{status_icon} <b>Статус:</b> {status_text}\n"
        f"🕒 <b>Последнее изменение:</b> {LAST_ZP_STATE['changed']}"
    )

# ====== МИНИ-ВЕБСЕРВЕР ДЛЯ RENDER ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот живий! Слідкую за тривогами в Запоріжжі 🚨"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ====== ЛОГИКА МОНИТОРИНГА API ======
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

            # Если включилась тревога
            if is_active_now and not LAST_ZP_STATE["alertnow"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = f"🚨 <b>ПОВІТРЯНА ТРИВОГА В ЗАПОРІЖЖІ!</b>\n\n🕒 Початок: {time_str}"
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)
                
            # Если произошел отбой
            elif not is_active_now and LAST_ZP_STATE["alertnow"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = f"✅ <b>Відбій тривоги в Запоріжжі</b>\n\n🕒 Відбій: {time_str}"
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)

            LAST_ZP_STATE = {"alertnow": is_active_now, "changed": changed_time}
        except Exception as e:
            logger.error(f"Ошибка API: {e}")
        
        await asyncio.sleep(20) # Проверка каждые 20 секунд

# ====== ЗАПУСК ======
async def main():
    # Запуск Flask для Render в потоке
    threading.Thread(target=run_flask, daemon=True).start()
    # Запуск фонового цикла проверки тревог
    asyncio.create_task(check_zaporizhzhia_alert())
    # Запуск приема сообщений (команд)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
