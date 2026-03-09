from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS

def get_admin_keyboard():
    keyboard = [
        ["📄 Отправить расчетки всем"],
        ["👤 Отправить расчетку сотруднику"],
        ["📋 Список сотрудников"],
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