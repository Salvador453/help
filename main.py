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

# Правильные заголовки для авторизации (ВАЖНО: Bearer + ключ)
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
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
            logger.info(f"🌐 Запрос к API: {url}")
            logger.info(f"🔑 Заголовки: {HEADERS}")
            
            async with session.get(
                url,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                logger.info(f"📊 Статус ответа: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📦 Данные: {data}")
                    
                    # API возвращает список активных тревог для региона
                    if data and len(data) > 0:
                        # Берем первую активную тревогу
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
                    logger.error("❌ Ошибка 401: Неверный API ключ или формат авторизации")
                    text = await response.text()
                    logger.error(f"Ответ сервера: {text}")
                    return None
                elif response.status == 404:
                    logger.warning(f"⚠️ Регион {region_id} не найден")
                    return None
                else:
                    text = await response.text()
                    logger.error(f"❌ Ошибка API {response.status}: {text}")
                    return None
                    
    except Exception as e:
        logger.error(f"❌ Исключение при запросе: {e}")
        return None

async def test_api_connection():
    """Тестовое подключение к API"""
    try:
        async with aiohttp.ClientSession() as session:
            # Пробуем получить список регионов
            async with session.get(
                f"{API_BASE_URL}/regions",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                logger.info(f"🧪 Тест API /regions: {response.status}")
                if response.status == 200:
                    logger.info("✅ API ключ работает!")
                    return True
                else:
                    text = await response.text()
                    logger.error(f"❌ Тест не пройден: {response.status} - {text}")
                    return False
    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}")
        return False

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "🚀 <b>Бот мониторинга воздушных тревог запущен!</b>\n\n"
        f"📍 <b>Местоположение:</b> {ZAPORIZHZHIA_CITY_NAME}\n"
        f"🆔 <b>ID региона:</b> <code>{ZAPORIZHZHIA_CITY_ID}</code>\n\n"
        "✅ <b>Это именно город Запорожье</b>, а не вся область!\n\n"
        "Используйте:\n"
        "/status - проверить текущую ситуацию\n"
        "/test - проверить подключение к API",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Карта тревог", url="https://map.ukrainealarm.com/")]
        ])
    )

@dp.message(Command("go"))
async def go_handler(message: Message):
    """Алиас для /start"""
    await start_handler(message)

@dp.message(Command("test"))
async def test_handler(message: Message):
    """Тест API подключения"""
    await message.answer("🧪 Проверяю подключение к API...")
    
    success = await test_api_connection()
    
    if success:
        await message.answer("✅ <b>API подключение успешно!</b>\nКлюч работает.")
    else:
        await message.answer(
            "❌ <b>Ошибка подключения к API</b>\n"
            "Проверьте правильность ключа и формат авторизации."
        )

@dp.message(Command("status"))
async def status_handler(message: Message):
    """Проверка текущего статуса"""
    await message.answer("🔄 Получаю данные...")
    
    status = await get_alert_by_region(ZAPORIZHZHIA_CITY_ID)
    
    if status is None:
        await message.answer(
            "❌ <b>Ошибка получения данных</b>\n\n"
            "Возможные причины:\n"
            "• Неверный API ключ\n"
            "• Проблемы с сетью\n"
            "• API временно недоступен\n\n"
            "Попробуйте /test для диагностики"
        )
        return
    
    if status["active"]:
        icon = "🚨"
        text_status = "<b>УВАГА! ТРИВОГА!</b>"
        alert_type = status.get("alert_type", "Повітряна тривога")
        location = status.get("location", ZAPORIZHZHIA_CITY_NAME)
    else:
        icon = "✅"
        text_status = "<b>ВІДБІЙ</b>\nВсе спокійно у місті."
        alert_type = "Немає загрози"
        location = ZAPORIZHZHIA_CITY_NAME
    
    changed_time = status.get("changed_at") or "Немає даних"
    
    await message.answer(
        f"{icon} <b>Статус у {location}:</b>\n\n"
        f"{text_status}\n"
        f"📋 <b>Тип:</b> {alert_type}\n"
        f"🕒 <b>Оновлено:</b> {changed_time}\n\n"
        f"<i>Джерело: api.ukrainealarm.com</i>"
    )

@dp.message(Command("info"))
async def info_handler(message: Message):
    """Информация о регионе мониторинга"""
    await message.answer(
        f"ℹ️ <b>Информация о мониторинге:</b>\n\n"
        f"📍 <b>Регион:</b> {ZAPORIZHZHIA_CITY_NAME}\n"
        f"🆔 <b>ID:</b> <code>{ZAPORIZHZHIA_CITY_ID}</code>\n"
        f"🔑 <b>API ключ:</b> <code>{API_KEY[:8]}...</code>\n"
        f"📡 <b>URL:</b> <code>{API_BASE_URL}</code>\n\n"
        f"<b>Заголовки:</b>\n"
        f"<code>Authorization: Bearer {API_KEY[:15]}...</code>\n"
        f"<code>Accept: application/json</code>"
    )

# ========== МИНИ-ВЕБСЕРВЕР ДЛЯ RENDER ==========
app = Flask(__name__)

@app.route("/")
def home():
    status_icon = "🚨" if LAST_ALERT_STATE["active"] else "✅"
    status_text = "ТРИВОГА" if LAST_ALERT_STATE["active"] else "ВІДБІЙ"
    
    return f"""
    <html>
        <head>
            <title>Air Alert Bot - Zaporizhzhia</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f0f0; }}
                .container {{ background: white; padding: 40px; border-radius: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }}
                .status {{ font-size: 48px; margin: 20px 0; }}
                .alert {{ color: #d32f2f; }}
                .safe {{ color: #388e3c; }}
                h1 {{ color: #333; }}
                .info {{ color: #666; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="status {'alert' if LAST_ALERT_STATE['active'] else 'safe'}">{status_icon}</div>
                <h1>{status_text}</h1>
                <h2>м. Запоріжжя</h2>
                <p class="info">Останнє оновлення: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</p>
                <p class="info">ID регіону: {ZAPORIZHZHIA_CITY_ID}</p>
                <hr>
                <p><i>Джерело: api.ukrainealarm.com</i></p>
            </div>
        </body>
    </html>
    """

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ========== ЛОГИКА МОНИТОРИНГА ==========

async def monitor_alerts():
    """Фоновая задача мониторинга тревог"""
    global LAST_ALERT_STATE
    
    logger.info(f"🔍 Начинаю мониторинг тревог для ID: {ZAPORIZHZHIA_CITY_ID}")
    
    # Тестируем API перед стартом
    await test_api_connection()
    
    # Небольшая задержка при старте
    await asyncio.sleep(5)
    
    while True:
        try:
            current_status = await get_alert_by_region(ZAPORIZHZHIA_CITY_ID)
            
            if current_status is None:
                logger.warning("⚠️ Не удалось получить статус, повтор через 30 сек...")
                await asyncio.sleep(30)
                continue
            
            is_active_now = current_status["active"]
            changed_time = current_status.get("changed_at")
            
            # Проверяем изменение состояния
            if is_active_now and not LAST_ALERT_STATE["active"]:
                # Началась тревога
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                alert_type = current_status.get("alert_type", "Повітряна тривога")
                location = current_status.get("location", ZAPORIZHZHIA_CITY_NAME)
                
                text = (
                    f"🚨 <b>ПОВІТРЯНА ТРИВОГА!</b>\n\n"
                    f"📍 <b>Місце:</b> {location}\n"
                    f"📋 <b>Тип:</b> {alert_type}\n"
                    f"🕒 <b>Початок:</b> {time_str}\n\n"
                    f"⚠️ <b>Пройдіть в укриття!</b>"
                )
                
                for chat_id in ALERT_CHAT_IDS:
                    try:
                        await bot.send_message(chat_id, text)
                        logger.info(f"✅ Отправлено уведомление о тревоге в {chat_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
                
            elif not is_active_now and LAST_ALERT_STATE["active"]:
                # Отбой тревоги
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                location = current_status.get("location", ZAPORIZHZHIA_CITY_NAME)
                
                text = (
                    f"✅ <b>ВІДБІЙ ТРИВОГИ!</b>\n\n"
                    f"📍 <b>Місце:</b> {location}\n"
                    f"🕒 <b>Відбій:</b> {time_str}\n\n"
                    f"🟢 <b>Небезпека минула</b>"
                )
                
                for chat_id in ALERT_CHAT_IDS:
                    try:
                        await bot.send_message(chat_id, text)
                        logger.info(f"✅ Отправлено уведомление об отбое в {chat_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
            
            # Обновляем состояние
            LAST_ALERT_STATE = {
                "active": is_active_now,
                "changed_at": changed_time or datetime.now().isoformat(),
                "alert_type": current_status.get("alert_type")
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле мониторинга: {e}")
        
        await asyncio.sleep(20)

# ========== ЗАПУСК ==========

async def main():
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Веб-сервер запущен")
    
    # Запускаем мониторинг тревог
    asyncio.create_task(monitor_alerts())
    
    # Запускаем бота
    logger.info("🤖 Бот запущен")
    logger.info(f"📍 Мониторинг: {ZAPORIZHZHIA_CITY_NAME} (ID: {ZAPORIZHZHIA_CITY_ID})")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
