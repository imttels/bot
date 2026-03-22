from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_CHAT_IDS, FOLDER_ID
from drive_client import get_drive_service, get_years
from handlers.admin_handlers import get_admin_keyboard, broadcast_start, send_pending_responses
from handlers.button_handlers import year_keyboard
from handlers.user_handlers import list_employees, send_month_for_date
import db

BROADCAST_REPLY_HINT = (
    "\n\nПожалуйста, ответьте именно на это сообщение — "
    "ваш ответ сохранится и будет отправлен администратору."
)

def _clear_broadcast_context(context: ContextTypes.DEFAULT_TYPE):
    for key in (
        "moscow_recipients",
        "awaiting_moscow_text",
        "broadcast_employees",
        "selected_employees",
        "awaiting_broadcast_text",
        "current_page",
    ):
        context.user_data.pop(key, None)


async def _send_collectible_broadcast(
    context: ContextTypes.DEFAULT_TYPE,
    admin_chat_id: int,
    recipients: dict[str, int],
    text: str,
):
    broadcast_id = db.create_broadcast(admin_chat_id, text)
    success = []
    failed = []
    message_text = text + BROADCAST_REPLY_HINT

    for name, chat_id in recipients.items():
        try:
            sent_message = await context.bot.send_message(chat_id=chat_id, text=message_text)
            db.add_broadcast_recipient(broadcast_id, chat_id, name, sent_message.message_id)
            success.append(name)
        except Exception as e:
            failed.append(f"{name} (ошибка: {e})")

    return broadcast_id, success, failed


async def reply_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_moscow_text"):
        text = update.message.text
        if text == "/cancel":
            await update.message.reply_text("❌ Рассылка отменена.")
            _clear_broadcast_context(context)
            return

        recipients = context.user_data.get("moscow_recipients", {})
        broadcast_id, success, failed = await _send_collectible_broadcast(
            context,
            update.effective_chat.id,
            recipients,
            text,
        )

        report = (
            f"📨 Рассылка #{broadcast_id} создана.\n"
            f"✅ Отправлено {len(success)}:\n" + "\n".join(success)
            if success
            else f"📨 Рассылка #{broadcast_id} создана.\n✅ Отправлено 0"
        )
        if failed:
            report += f"\n❌ Не удалось отправить {len(failed)}:\n" + "\n".join(failed)

        await update.message.reply_text(report)
        _clear_broadcast_context(context)
        return

    if context.user_data.get("awaiting_custom_text"):
        month = context.user_data.get("selected_month")
        if not month:
            await update.message.reply_text("Ошибка: месяц не найден. Начните заново.")
            context.user_data.clear()
            return

        custom_text = update.message.text
        await update.message.reply_text(f"Текст принят. Отправляю расчётки за {month}...")
        await send_month_for_date(update, context, month, update.message, custom_caption=custom_text)
        context.user_data.pop("awaiting_custom_text", None)
        context.user_data.pop("selected_month", None)
        return

    if context.user_data.get("awaiting_broadcast_text"):
        text = update.message.text
        if text == "/cancel":
            await update.message.reply_text("❌ Рассылка отменена.")
            _clear_broadcast_context(context)
            return

        selected_names = context.user_data.get("selected_employees", set())
        employees = context.user_data.get("broadcast_employees", {})
        recipients = {name: employees[name] for name in selected_names if name in employees}

        broadcast_id, success, failed = await _send_collectible_broadcast(
            context,
            update.effective_chat.id,
            recipients,
            text,
        )

        report = (
            f"📨 Рассылка #{broadcast_id} создана.\n"
            f"✅ Отправлено {len(success)}:\n" + "\n".join(success)
            if success
            else f"📨 Рассылка #{broadcast_id} создана.\n✅ Отправлено 0"
        )
        if failed:
            report += f"\n❌ Не удалось отправить {len(failed)}:\n" + "\n".join(failed)

        await update.message.reply_text(report)
        _clear_broadcast_context(context)
        return

    chat_id = update.effective_chat.id
    text = update.message.text

    if chat_id not in ADMIN_CHAT_IDS:
        employee_name = db.get_employee_name_by_chat_id(chat_id)
        if not employee_name:
            await update.message.reply_text(
                "Вы не администратор. Для регистрации отправьте /reg Имя Фамилия"
            )
            return

        reply_to_message = update.message.reply_to_message
        if not reply_to_message:
            await update.message.reply_text(
                "Чтобы ответ попал в рассылку, ответьте именно на сообщение бота."
            )
            return

        broadcast = db.get_broadcast_for_reply(chat_id, reply_to_message.message_id)
        if not broadcast:
            await update.message.reply_text(
                "Не удалось определить рассылку. Ответьте именно на сообщение с рассылкой."
            )
            return

        db.save_broadcast_response(
            broadcast_id=broadcast["broadcast_id"],
            employee_chat_id=chat_id,
            employee_name=employee_name,
            response_text=text,
        )
        await update.message.reply_text(
            "✅ Ответ сохранён."
        )
        return

    if not context.user_data.get("keyboard_sent"):
        await update.message.reply_text("Используйте кнопки меню", reply_markup=get_admin_keyboard())
        context.user_data["keyboard_sent"] = True

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

    elif text == "📥 Получить ответы":
        await send_pending_responses(update, context)

    elif text == "❓ Помощь":
        help_text = (
            "Команды администратора:\n"
            "/send_user Имя Фамилия YYYY-MM — отправить расчетку конкретному сотруднику\n"
            "/send_month YYYY-MM — отправить расчетки всем за месяц\n"
            "/list — список зарегистрированных сотрудников\n"
            "/unreg Имя Фамилия — удалить сотрудника\n"
            "/reg — регистрация для обычного пользователя\n"
            "/set_caption — установка сообщения по умолчанию\n"
            "/answers — получить новые ответы на рассылки"
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