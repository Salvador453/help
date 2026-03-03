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

# Заголовки для авторизации
HEADERS = {
    "Authorization": API_KEY
}

# ID региона для города Запорожье (получается динамически при старте)
ZAPORIZHZHIA_CITY_ID = None
ZAPORIZHZHIA_REGION_NAME = "Запорізька область"
ZAPORIZHZHIA_CITY_NAME = "Запоріжжя"

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

async def get_regions():
    """Получить список всех регионов и найти ID города Запорожье"""
    global ZAPORIZHZHIA_CITY_ID
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/regions",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Ищем Запорожскую область
                    for region in data:
                        if region.get("regionName") == ZAPORIZHZHIA_REGION_NAME:
                            # Ищем город Запорожье в списке населенных пунктов
                            for location in region.get("regionChildIds", []):
                                if location.get("regionName") == ZAPORIZHZHIA_CITY_NAME:
                                    ZAPORIZHZHIA_CITY_ID = location.get("regionId")
                                    logger.info(f"✅ Найден ID города Запорожье: {ZAPORIZHZHIA_CITY_ID}")
                                    return True
                            
                            # Если не нашли город отдельно, используем ID области как fallback
                            # (но лучше найти именно город)
                            logger.warning("⚠️ Город Запорожье не найден отдельно, ищем более точное совпадение...")
                    
                    # Альтернативный поиск по всем регионам
                    for region in data:
                        if ZAPORIZHZHIA_CITY_NAME in region.get("regionName", ""):
                            ZAPORIZHZHIA_CITY_ID = region.get("regionId")
                            logger.info(f"✅ Найден ID региона (альтернативный поиск): {ZAPORIZHZHIA_CITY_ID}")
                            return True
                    
                    logger.error("❌ Не удалось найти ID для города Запорожье")
                    return False
                else:
                    logger.error(f"❌ Ошибка API при получении регионов: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Исключение при получении регионов: {e}")
        return False

async def get_alert_status(region_id):
    """Получить статус тревоги для конкретного региона"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/alerts/{region_id}",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.warning(f"⚠️ Регион {region_id} не найден в API")
                    return None
                else:
                    logger.error(f"❌ Ошибка API: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе статуса: {e}")
        return None

async def check_alerts():
    """Проверить все активные тревоги и найти статус для Запорожья"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/alerts",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Ищем тревогу для Запорожья
                    for alert in data:
                        if alert.get("regionId") == ZAPORIZHZHIA_CITY_ID:
                            return {
                                "active": True,
                                "alert_type": alert.get("alertType"),
                                "changed_at": alert.get("changed")
                            }
                    
                    # Если не нашли в активных - значит отбой
                    return {"active": False, "alert_type": None, "changed_at": None}
                else:
                    logger.error(f"❌ Ошибка API при получении алертов: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке алертов: {e}")
        return None

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "🚀 <b>Бот мониторинга воздушных тревог запущен!</b>\n\n"
        f"📍 <b>Местоположение:</b> {ZAPORIZHZHIA_CITY_NAME}\n"
        f"🆔 <b>ID региона:</b> <code>{ZAPORIZHZHIA_CITY_ID}</code>\n\n"
        "Я отслеживаю официальные данные с api.ukrainealarm.com\n"
        "Используйте /status для проверки текущей ситуации.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Карта тревог", url="https://map.ukrainealarm.com/")],
            [InlineKeyboardButton(text="📊 История тревог", url="https://air-alarms.in.ua/")]
        ])
    )

@dp.message(Command("go"))
async def go_handler(message: Message):
    """Алиас для /start"""
    await start_handler(message)

@dp.message(Command("status"))
async def status_handler(message: Message):
    """Проверка текущего статуса"""
    status = await check_alerts()
    
    if status is None:
        await message.answer("❌ <b>Ошибка получения данных</b>\nПопробуйте позже.")
        return
    
    if status["active"]:
        icon = "🚨"
        text_status = "<b>ВНИМАНИЕ! ТРЕВОГА!</b>"
        alert_type = status.get("alert_type", "Повітряна тривога")
    else:
        icon = "✅"
        text_status = "<b>ОТБОЙ</b>\nВсе спокойно в городе."
        alert_type = "Нет угрозы"
    
    changed_time = status.get("changed_at") or "Нет данных"
    
    await message.answer(
        f"{icon} <b>Статус в {ZAPORIZHZHIA_CITY_NAME}:</b>\n\n"
        f"{text_status}\n"
        f"📋 <b>Тип:</b> {alert_type}\n"
        f"🕒 <b>Обновлено:</b> {changed_time}\n\n"
        f"<i>Данные: api.ukrainealarm.com</i>"
    )

@dp.message(Command("regions"))
async def regions_handler(message: Message):
    """Отладочная команда для просмотра ID региона"""
    await message.answer(
        f"📍 <b>Текущие настройки:</b>\n\n"
        f"Город: {ZAPORIZHZHIA_CITY_NAME}\n"
        f"ID региона: <code>{ZAPORIZHZHIA_CITY_ID}</code>\n"
        f"API URL: {API_BASE_URL}"
    )

# ========== МИНИ-ВЕБСЕРВЕР ДЛЯ RENDER ==========
app = Flask(__name__)

@app.route("/")
def home():
    status_icon = "🚨" if LAST_ALERT_STATE["active"] else "✅"
    return f"""
    <html>
        <head><title>Air Alert Bot - Zaporizhzhia</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1>{status_icon} Бот мониторинга тревог</h1>
            <h2>Город: Запорожье</h2>
            <p>Статус: <b>{'ТРЕВОГА' if LAST_ALERT_STATE['active'] else 'ОТБОЙ'}</b></p>
            <p>ID региона: {ZAPORIZHZHIA_CITY_ID}</p>
            <p>Последнее обновление: {datetime.now().strftime('%H:%M:%S')}</p>
            <hr>
            <p><i>Источник: api.ukrainealarm.com</i></p>
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
    
    # Сначала получаем ID региона
    if not await get_regions():
        logger.error("❌ Не удалось инициализировать ID региона. Пробуем продолжить...")
        # Используем известный ID Запорожской области как fallback
        # (обычно это не рекомендуется, но для работоспособности)
        ZAPORIZHZHIA_CITY_ID = "14"  # Примерный ID, лучше получить динамически
    
    logger.info("🔍 Начинаю мониторинг тревог...")
    
    while True:
        try:
            current_status = await check_alerts()
            
            if current_status is None:
                await asyncio.sleep(30)
                continue
            
            is_active_now = current_status["active"]
            changed_time = current_status.get("changed_at")
            
            # Проверяем изменение состояния
            if is_active_now and not LAST_ALERT_STATE["active"]:
                # Началась тревога
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                alert_type = current_status.get("alert_type", "Повітряна тривога")
                
                text = (
                    f"🚨 <b>ПОВІТРЯНА ТРИВОГА В ЗАПОРІЖЖІ!</b>\n\n"
                    f"📍 <b>Місце:</b> {ZAPORIZHZHIA_CITY_NAME}\n"
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
                
                text = (
                    f"✅ <b>ВІДБІЙ ТРИВОГИ В ЗАПОРІЖЖІ</b>\n\n"
                    f"📍 <b>Місце:</b> {ZAPORIZHZHIA_CITY_NAME}\n"
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
        
        # Проверка каждые 20 секунд
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
    logger.info("🤖 Бот запущен и готов к работе")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
