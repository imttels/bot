from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS, SPREADSHEET_ID
import db
from handlers.button_handlers import show_employees_page, show_broadcasts_page
from services.sheets_client import read_curators
import logging


logger = logging.getLogger(__name__)


def get_admin_keyboard():
    keyboard = [
        ["📄 Отправить расчетки всем"],
        ["👤 Отправить расчетку сотруднику"],
        ["📋 Список сотрудников"],
        ["📨 Отправить сообщение выбранным"], 
        ["📍 Отправить сообщение Москва"],
        ["📥 Получить ответы"],
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def _truncate_text(text: str, limit: int = 45) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit - 1] + "…"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in ADMIN_CHAT_IDS:
        await update.message.reply_text(
            "Главное меню администратора",
            reply_markup=get_admin_keyboard()
        )
        context.user_data['keyboard_sent'] = True
    else:
        await update.message.reply_text(
            "Вы не являетесь администратором. Для регистрации используйте /reg Имя Фамилия.",
            reply_markup=ReplyKeyboardRemove()
        )

async def set_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён.")
        return
    if not context.args:
        await update.message.reply_text(
            "Укажите текст. Используйте {month} для подстановки месяца.\n"
            "Пример: /set_caption Расчётка за {month}"
        )
        return
    caption = " ".join(context.args)
    db.set_setting("default_caption", caption)
    await update.message.reply_text(f"✅ Текст по умолчанию установлен:\n{caption}")

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён.")
        return

    employees = db.get_all_employees()
    if not employees:
        await update.message.reply_text("Нет зарегистрированных сотрудников.")
        return

    context.user_data['broadcast_employees'] = {name: chat_id for chat_id, name in employees}
    context.user_data['selected_employees'] = set()

    await show_employees_page(update, context, page=0)





from services.sheets_client import read_curators  

async def update_cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён.")
        return

    await update.message.reply_text("Синхронизация городов начата...")
    curators = read_curators(SPREADSHEET_ID)  
    if not curators:
        await update.message.reply_text("Не удалось получить данные из таблицы.")
        return

    updated = 0
    not_found = []
    for curator in curators:
        name = curator['name']
        city = curator['city']
        chat_id = db.get_employee_by_name(name)  
        if chat_id:
            db.update_employee_city(name, city)
            updated += 1
        else:
            not_found.append(name)

    report = f"✅ Обновлено городов: {updated}\n"
    if not_found:
        report += f"❌ Не найдены в базе: {', '.join(not_found[:10])}"
        if len(not_found) > 10:
            report += f" и ещё {len(not_found)-10}"
    await update.message.reply_text(report)



def _truncate_text(text, limit: int = 140):
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _split_message(text: str, limit: int = 3500) :
    if len(text) <= limit:
        return [text]

    parts = []
    current = []
    current_len = 0

    for block in text.split("\n\n"):
        block_len = len(block) + 2
        if current and current_len + block_len > limit:
            parts.append("\n\n".join(current))
            current = [block]
            current_len = len(block)
        else:
            current.append(block)
            current_len += block_len

    if current:
        parts.append("\n\n".join(current))

    return parts


async def send_pending_responses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_chat_id = update.effective_chat.id

    if admin_chat_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён.")
        return

    broadcasts = db.get_broadcasts_for_admin(admin_chat_id)

    if not broadcasts:
        await update.message.reply_text("У вас пока нет рассылок.")
        return

    context.user_data["answers_broadcasts"] = broadcasts
    context.user_data["answers_page"] = 0

    await show_broadcasts_page(update, context, page=0)
