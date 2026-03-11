from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS, FOLDER_ID
from drive_client import get_drive_service, get_years
from handlers.admin_handlers import get_admin_keyboard
from handlers.button_handlers import year_keyboard
from handlers.user_handlers import list_employees
from handlers.user_handlers import send_month_for_date 
from handlers.admin_handlers import broadcast_start
import db



async def reply_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_moscow_text'):
        text = update.message.text
        if text == '/cancel':
            await update.message.reply_text("❌ Рассылка отменена.")
            context.user_data.clear()
            return

        recipients = context.user_data.get('moscow_recipients', {})
        success = []
        failed = []
        for name, chat_id in recipients.items():
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
                success.append(name)
            except Exception as e:
                failed.append(f"{name} (ошибка: {e})")

        report = f"✅ Отправлено {len(success)}:\n" + "\n".join(success) if success else ""
        if failed:
            report += f"\n❌ Не удалось отправить {len(failed)}:\n" + "\n".join(failed)
        await update.message.reply_text(report or "Никому не отправлено.")
        context.user_data.clear()
        return

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
    
    if context.user_data.get('awaiting_broadcast_text'):
        text = update.message.text
        if text == '/cancel':
            await update.message.reply_text("❌ Рассылка отменена.")
            context.user_data.clear()
            return

        selected_names = context.user_data.get('selected_employees', set())
        employees = context.user_data.get('broadcast_employees', {})
        success = []
        failed = []
        for name in selected_names:
            chat_id = employees.get(name)
            if chat_id:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                    success.append(name)
                except Exception as e:
                    failed.append(f"{name} (ошибка: {e})")
            else:
                failed.append(f"{name} (chat_id не найден)")

        report = f"✅ Отправлено {len(success)}:\n" + "\n".join(success) if success else ""
        if failed:
            report += f"\n❌ Не удалось отправить {len(failed)}:\n" + "\n".join(failed)
        await update.message.reply_text(report or "Никому не отправлено.")
        context.user_data.clear()
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
    elif text == "📨 Отправить сообщение выбранным":
        await broadcast_start(update, context)
    elif text == "📍 Отправить сообщение Москва":
        await broadcast_to_moscow(update, context)
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





async def broadcast_to_moscow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён.")
        return

    moscow_employees = db.get_employees_by_city("Москва")
    if not moscow_employees:
        await update.message.reply_text("Нет сотрудников из Москвы.")
        return

    context.user_data['moscow_recipients'] = {name: chat_id for chat_id, name in moscow_employees}
    context.user_data['awaiting_moscow_text'] = True
    await update.message.reply_text(
        f"Найдено сотрудников в Москве: {len(moscow_employees)}.\n"
        "Введите текст сообщения для отправки (или /cancel для отмены)."
    )