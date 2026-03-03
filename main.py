import asyncio
import aiohttp
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM"
ALERT_CHAT_IDS = ["-1003088722284"]

# Официальный API Ukraine Alarm
API_BASE_URL = "https://api.ukrainealarm.com/api/v3"
API_KEY = "14d49bd6:19c6d5a643e2fddfb2a473e9c4c08ccd"

# ID города Запорожье (Запорізька територіальна громада)
ZAPORIZHZHIA_CITY_ID = "564"
ZAPORIZHZHIA_CITY_NAME = "м. Запоріжжя"

# ИСПРАВЛЕНО: БЕЗ префикса Bearer — просто ключ как есть!
HEADERS = {
    "Authorization": API_KEY,  # Без Bearer!
    "Accept": "application/json"
}

# Состояние тревоги
LAST_ALERT_STATE = {
    "active": False,
    "changed_at": None,
    "alert_type": None
}

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ========== API ФУНКЦИИ ==========

async def get_alert_by_region(region_id):
    """Получить статус тревоги для конкретного региона"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}/alerts/{region_id}"
            logger.info(f"🌐 Запрос: {url}")
            
            async with session.get(
                url,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                logger.info(f"📊 Статус: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data and len(data) > 0:
                        alert = data[0]
                        return {
                            "active": True,
                            "alert_type": alert.get("alertType", "Повітряна тривога"),
                            "changed_at": alert.get("changed"),
                            "location": alert.get("locationTitle", ZAPORIZHZHIA_CITY_NAME)
                        }
                    else:
                        return {"active": False, "alert_type": None, "changed_at": None}
                        
                elif response.status == 401:
                    text = await response.text()
                    logger.error(f"❌ 401: {text}")
                    return None
                else:
                    text = await response.text()
                    logger.error(f"❌ Ошибка {response.status}: {text}")
                    return None
                    
    except Exception as e:
        logger.error(f"❌ Исключение: {e}")
        return None

async def test_api_connection():
    """Тест подключения"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/regions",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                logger.info(f"🧪 Тест: {response.status}")
                if response.status == 200:
                    return True
                else:
                    text = await response.text()
                    logger.error(f"❌ Тест: {response.status} - {text}")
                    return False
    except Exception as e:
        logger.error(f"❌ Тест исключение: {e}")
        return False

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "🚀 <b>Бот мониторинга воздушных тревог!</b>\n\n"
        f"📍 <b>Местоположение:</b> {ZAPORIZHZHIA_CITY_NAME}\n"
        f"🆔 <b>ID:</b> <code>{ZAPORIZHZHIA_CITY_ID}</code>\n\n"
        "/status - текущая ситуация\n"
        "/test - проверить API",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Карта", url="https://map.ukrainealarm.com/")]
        ])
    )

@dp.message(Command("go"))
async def go_handler(message: Message):
    await start_handler(message)

@dp.message(Command("test"))
async def test_handler(message: Message):
    await message.answer("🧪 Проверяю API...")
    
    success = await test_api_connection()
    
    if success:
        await message.answer("✅ <b>API работает!</b>")
    else:
        await message.answer("❌ <b>Ошибка API</b>\nПроверьте ключ.")

@dp.message(Command("status"))
async def status_handler(message: Message):
    await message.answer("🔄 Получаю данные...")
    
    status = await get_alert_by_region(ZAPORIZHZHIA_CITY_ID)
    
    if status is None:
        await message.answer("❌ <b>Ошибка получения данных</b>\nПопробуйте /test")
        return
    
    if status["active"]:
        icon = "🚨"
        text_status = "<b>ТРИВОГА!</b>"
        alert_type = status.get("alert_type", "Повітряна тривога")
    else:
        icon = "✅"
        text_status = "<b>ВІДБІЙ</b> - все спокійно"
        alert_type = "Немає загрози"
    
    changed_time = status.get("changed_at") or "Немає даних"
    
    await message.answer(
        f"{icon} <b>Статус:</b> {text_status}\n"
        f"📋 {alert_type}\n"
        f"🕒 {changed_time}"
    )

# ========== ВЕБСЕРВЕР ==========
app = Flask(__name__)

@app.route("/")
def home():
    status_icon = "🚨" if LAST_ALERT_STATE["active"] else "✅"
    return f"<h1>{status_icon} Бот работает</h1><p>ID: {ZAPORIZHZHIA_CITY_ID}</p>"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ========== МОНИТОРИНГ ==========

async def monitor_alerts():
    global LAST_ALERT_STATE
    
    logger.info(f"🔍 Мониторинг ID: {ZAPORIZHZHIA_CITY_ID}")
    await asyncio.sleep(5)
    
    while True:
        try:
            current = await get_alert_by_region(ZAPORIZHZHIA_CITY_ID)
            
            if current is None:
                await asyncio.sleep(30)
                continue
            
            is_active = current["active"]
            
            # Тревога началась
            if is_active and not LAST_ALERT_STATE["active"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = f"🚨 <b>ТРИВОГА!</b>\n🕒 {time_str}\n📍 {ZAPORIZHZHIA_CITY_NAME}"
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)
            
            # Отбой
            elif not is_active and LAST_ALERT_STATE["active"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = f"✅ <b>ВІДБІЙ</b>\n🕒 {time_str}\n📍 {ZAPORIZHZHIA_CITY_NAME}"
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)
            
            LAST_ALERT_STATE = {
                "active": is_active,
                "changed_at": current.get("changed_at"),
                "alert_type": current.get("alert_type")
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
        
        await asyncio.sleep(20)

# ========== ЗАПУСК ==========

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(monitor_alerts())
    logger.info("🤖 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
