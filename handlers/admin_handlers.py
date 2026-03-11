from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS, SPREADSHEET_ID
import db
from handlers.button_handlers import show_employees_page
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
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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