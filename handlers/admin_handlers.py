from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_CHAT_IDS
from keyboards.reply_keyboards import get_admin_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id in ADMIN_CHAT_IDS:

        await update.message.reply_text(
            "Меню администратора",
            reply_markup=get_admin_keyboard()
        )

        context.user_data["keyboard_sent"] = True

    else:

        await update.message.reply_text(
            "Вы не администратор. Используйте /reg"
        )