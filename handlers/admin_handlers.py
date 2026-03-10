from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS
import db
from handlers.button_handlers import show_employees_page


def get_admin_keyboard():
    keyboard = [
        ["📄 Отправить расчетки всем"],
        ["👤 Отправить расчетку сотруднику"],
        ["📋 Список сотрудников"],
        ["📨 Отправить сообщение выбранным"], 
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