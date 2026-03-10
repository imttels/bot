from telegram.ext import Application
from config import ADMIN_CHAT_IDS
from services.birthday import get_today_birthdays, get_tomorrow_birthdays
import logging

logger = logging.getLogger(__name__)

async def send_today_birthdays(app: Application):
    logger.info("Проверка сегодняшних именинников...")
    birthdays = get_today_birthdays()
    logger.info(f"Найдено именинников: {len(birthdays)}")
    if not birthdays:
        logger.info("Сегодня именинников нет")
        return
    message = "🎉 **Сегодня день рождения у:**\n\n"
    for b in birthdays:
        message += f"• {b['name']} (@{b['telegram_nick']}, тел: {b['phone']})\n"
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await app.bot.send_message(chat_id=admin_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

async def send_tomorrow_birthdays(app: Application):
    birthdays = get_tomorrow_birthdays()
    if not birthdays:
        logger.info("Завтра именинников нет")
        return
    message = "⏰ **Завтра день рождения у:**\n\n"
    for b in birthdays:
        message += f"• {b['name']} (@{b['telegram_nick']}, тел: {b['phone']})\n"
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await app.bot.send_message(chat_id=admin_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")