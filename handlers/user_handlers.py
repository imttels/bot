from telegram import Update
from telegram.ext import ContextTypes
import db

async def reg(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Используй: /reg Имя Фамилия")
        return

    name = " ".join(context.args)

    success = db.add_employee(chat_id, name)

    if success:
        await update.message.reply_text("Регистрация успешна")
    else:
        await update.message.reply_text("Имя уже занято")