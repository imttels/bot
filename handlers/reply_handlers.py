from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS, FOLDER_ID
from drive_client import get_drive_service, get_years
from handlers.admin_handlers import get_admin_keyboard
from handlers.button_handlers import year_keyboard
from handlers.user_handlers import list_employees
from handlers.user_handlers import send_month_for_date 


async def reply_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get('awaiting_custom_text'):
        month = context.user_data.get('selected_month')
        if not month:
            await update.message.reply_text("Ошибка: месяц не найден. Начните заново.")
            context.user_data.clear()
            return
        custom_text = update.message.text
        await update.message.reply_text(f"Текст принят. Отправляю расчётки за {month}...")
        await send_month_for_date(update, context, month, update.message, custom_caption=custom_text)
        context.user_data.pop('awaiting_custom_text', None)
        context.user_data.pop('selected_month', None)
        return

    chat_id = update.effective_chat.id
    text = update.message.text

    if chat_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Вы не администратор. Для регистрации отправьте /reg Имя Фамилия")
        return

    if not context.user_data.get('keyboard_sent'):
        await update.message.reply_text("Используйте кнопки меню", reply_markup=get_admin_keyboard())
        context.user_data['keyboard_sent'] = True

    if text == "📄 Отправить расчетки всем":
        service = get_drive_service()
        years = get_years(service, FOLDER_ID)
        await update.message.reply_text("Выберите год", reply_markup=year_keyboard(years))
    elif text == "👤 Отправить расчетку сотруднику":
        await update.message.reply_text("Используйте команду /send_user Имя Фамилия YYYY-MM\nНапример: /send_user Иван Петров 2026-01")
    elif text == "📋 Список сотрудников":
        await list_employees(update, context)
    elif text == "❓ Помощь":
        help_text = (
            "Команды администратора:\n"
            "/send_user Имя Фамилия YYYY-MM — отправить расчетку конкретному сотруднику\n"
            "/send_month YYYY-MM — отправить расчетки всем за месяц\n"
            "/list — список зарегистрированных сотрудников\n"
            "/unreg Имя Фамилия — удалить сотрудника\n"
            "/reg — регистрация (для обычных пользователей\n"
            "/set_caption — установка сообщения по умолчанию"

        )
        await update.message.reply_text(help_text)