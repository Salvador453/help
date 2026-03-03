import asyncio
import aiohttp
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from flask import Flask
import threading
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен твоего бота
BOT_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM"
ALERT_CHAT_IDS = ["-1003088722284"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Состояние тревоги в Запорожье (город)
LAST_ZP_STATE = {"alertnow": False, "changed": "1970-01-01 00:00:00"}

# ID города Запорожье в API
ZAPORIZHZHIA_CITY_ID = "564"  # ← Твой regionId!

# API с детализацией по ТГ (территориальным громадам)
API_URL = "https://api.ukrainealarm.com/api/v3/alerts"

ALERT_ON = "🚨 <b>ПОВІТРЯНА ТРИВОГА В ЗАПОРІЖЖІ!</b>\n\n❗️ Увага! Напрямок до укриття!\n\n🕒 Початок: {time}"
ALERT_OFF = "✅ <b>Відбій тривоги в Запоріжжі</b>\n\nМожна виходити. Бережіть себе!\n🕒 Відбій: {time}"

async def check_zaporizhzhia_alert():
    global LAST_ZP_STATE
    
    # Заголовки для API (если нужен ключ, укажи здесь)
    headers = {
        "Accept": "application/json"
        # "Authorization": "Bearer ТВОЙ_КЛЮЧ"  # Раскомментируй если нужен API ключ
    }
    
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"API вернул статус {response.status}")
                        await asyncio.sleep(15)
                        continue
                    
                    data = await response.json()
                    
                    # Ищем именно город Запорожье по regionId
                    is_active_now = False
                    changed_time = "невідомо"
                    
                    # API возвращает список активных тревог или структуру с regionId
                    if isinstance(data, list):
                        # Формат: список активных тревог
                        for alert in data:
                            if str(alert.get("regionId")) == ZAPORIZHZHIA_CITY_ID:
                                is_active_now = True
                                changed_time = alert.get("startedAt", datetime.now().isoformat())
                                break
                    elif isinstance(data, dict) and "alerts" in data:
                        # Альтернативный формат
                        for alert in data["alerts"]:
                            if str(alert.get("regionId")) == ZAPORIZHZHIA_CITY_ID:
                                is_active_now = True
                                changed_time = alert.get("changed", "невідомо")
                                break
                    
                    # Проверяем изменение состояния
                    if is_active_now and not LAST_ZP_STATE["alertnow"]:
                        time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                        text = ALERT_ON.format(time=time_str)
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="Карта укриттів", url="https://map.ukrainealarm.com/")]
                        ])
                        for chat_id in ALERT_CHAT_IDS:
                            await bot.send_message(chat_id, text, reply_markup=keyboard, disable_web_page_preview=True)
                        logger.info(f"🚨 Тривога в Запоріжжі (місто)! Надіслано в {len(ALERT_CHAT_IDS)} чатів")
                        
                    elif not is_active_now and LAST_ZP_STATE["alertnow"]:
                        time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                        text = ALERT_OFF.format(time=time_str)
                        for chat_id in ALERT_CHAT_IDS:
                            await bot.send_message(chat_id, text)
                        logger.info("✅ Відбій тривоги в Запоріжжі (місто)!")
                    
                    LAST_ZP_STATE = {"alertnow": is_active_now, "changed": changed_time}
                    
        except Exception as e:
            logger.error(f"Помилка перевірки API: {e}")
        
        await asyncio.sleep(15)  # Проверяем каждые 15 секунд

@dp.message(Command("start"))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Карта укриттів", url="https://map.ukrainealarm.com/")],
        [InlineKeyboardButton(text="Статус тривоги", callback_data="status")]
    ])
    await message.answer(
        "<b>Привіт!</b>\nЯ бот, який сповіщає тільки про тривоги в місті <b>Запоріжжя</b> (не область).\n\n"
        "Тривоги надсилаються автоматично.\n\n"
        "Підтримуй Україну! 🇺🇦",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

@dp.message(Command("status"))
async def status(message: Message):
    status_text = "🚨 Тривога!" if LAST_ZP_STATE["alertnow"] else "✅ Тривоги немає"
    await message.answer(f"{status_text}\nОстаннє оновлення: {LAST_ZP_STATE['changed']}")

# Flask для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот живий! Слідкую за тривогами в Запоріжжі (місто) 🚨"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

async def main():
    asyncio.create_task(check_zaporizhzhia_alert())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
