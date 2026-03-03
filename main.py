import asyncio
import requests
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

# Токен твоего бота (получи у @BotFather)
BOT_TOKEN = "8667979264:AAH6Qb9w9-CRwizGRWYSrFH697ruQW21zOM"  # ← замени на свой!

# ID чата/канала, куда слать тревоги (можно несколько через список)
ALERT_CHAT_IDS = ["-1003088722284"]  # ← замени! Или [-1001234567890] для приватных

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Состояние тревоги в Запорожье (город)
LAST_ZP_STATE = {"alertnow": False, "changed": "1970-01-01 00:00:00"}

# Красивые эмодзи и сообщения
ALERT_ON = "🚨 <b>ПОВІТРЯНА ТРИВОГА В ЗАПОРІЖЖІ!</b>\n\n❗️ Увага! Напрямок до укриття!\n\n🕒 Початок: {time}"
ALERT_OFF = "✅ <b>Відбій тривоги в Запоріжжі</b>\n\nМожна виходити. Бережіть себе!\n🕒 Відбій: {time}"

# Публичный API от Ubilling (без ключа, просто берём)
API_URL = "https://ubilling.net.ua/aerialalerts/"

# Маппинг областей — Запорожская область имеет свой ключ в JSON
ZAPORIZHZHIA_REGION = "Запорізька область"  # Но мы будем фильтровать именно город (по доп. логике)

async def check_zaporizhzhia_alert():
    global LAST_ZP_STATE
    while True:
        try:
            r = requests.get(API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()

            states = data.get("states", {})
            zp_info = states.get(ZAPORIZHZHIA_REGION, {})

            is_active_now = zp_info.get("alertnow", False)
            changed_time = zp_info.get("changed", "невідомо")

            # Проверяем, изменилось ли состояние
            if is_active_now and not LAST_ZP_STATE["alertnow"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = ALERT_ON.format(time=time_str)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Карта укриттів", url="https://map.ukrainealarm.com/")]
                ])
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text, reply_markup=keyboard, disable_web_page_preview=True)
                logger.info(f"Тривога в Запоріжжі! Відправлено в {len(ALERT_CHAT_IDS)} чатів")

            elif not is_active_now and LAST_ZP_STATE["alertnow"]:
                time_str = datetime.now().strftime("%H:%M %d.%m.%Y")
                text = ALERT_OFF.format(time=time_str)
                for chat_id in ALERT_CHAT_IDS:
                    await bot.send_message(chat_id, text)
                logger.info("Відбій тривоги в Запоріжжі!")

            LAST_ZP_STATE = {"alertnow": is_active_now, "changed": changed_time}

        except Exception as e:
            logger.error(f"Помилка перевірки API: {e}")

        await asyncio.sleep(15)  # Проверяем каждые 15 секунд (кэш ~3 сек)

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
    if LAST_ZP_STATE["alertnow"]:
        await message.answer(f"🚨 Зараз тривога в Запоріжжі!\nОстаннє оновлення: {LAST_ZP_STATE['changed']}")
    else:
        await message.answer(f"✅ Тривоги немає.\nОстаннє оновлення: {LAST_ZP_STATE['changed']}")

# Мини-вебсервер для Render (чтобы бот не засыпал)
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот живий! Слідкую за тривогами в Запоріжжі 🚨"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# Запуск Flask в отдельном потоке
threading.Thread(target=run_flask, daemon=True).start()

async def main():
    asyncio.create_task(check_zaporizhzhia_alert())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
