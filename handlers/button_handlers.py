from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import FOLDER_ID, ADMIN_CHAT_IDS
from drive_client import get_drive_service, get_years, find_month_folder, list_pdfs_in_folder
import db
import logging
from handlers.user_handlers import send_month_for_date
import math
from telegram.error import BadRequest


logger = logging.getLogger(__name__)

def get_months(service, parent_folder_id, year):
    query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
    results = service.files().list(q=query, fields="files(name)").execute()
    folders = results.get("files", [])
    months = []
    for folder in folders:
        name = folder["name"]
        if name.startswith(f"расчетки-{year}-"):
            month = name.split("-")[2]
            months.append(month)
    return sorted(months)

def year_keyboard(years):
    keyboard = []
    row = []
    for year in years:
        row.append(InlineKeyboardButton(year, callback_data=f"year_{year}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def month_keyboard(year, months):
    keyboard = []
    row = []
    for month in months:
        row.append(InlineKeyboardButton(month, callback_data=f"month_{year}-{month}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


ANSWERS_PAGE_SIZE = 5


def _short_text(text: str, limit: int = 38) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit - 1] + "…"


def build_broadcasts_keyboard(broadcasts, page=0, items_per_page=ANSWERS_PAGE_SIZE):
    total_pages = max(1, math.ceil(len(broadcasts) / items_per_page))
    start = page * items_per_page
    end = start + items_per_page
    page_items = broadcasts[start:end]

    keyboard = []

    for item in page_items:
        preview = _short_text(item["message_text"], limit=22)

        if item["new_responses"] > 0:
            title = (
                f"{item['total_responses']} отв. (+{item['new_responses']}) | "
                f"{preview}"
            )
        else:
            title = (
                f"{item['total_responses']} отв. | "
                f"{preview}"
            )

        keyboard.append([
            InlineKeyboardButton(
                title,
                callback_data=f"answers_open_{item['broadcast_id']}_{page}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"answers_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"answers_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton("🔄 Обновить список", callback_data=f"answers_page_{page}")
    ])

    return InlineKeyboardMarkup(keyboard)


async def show_broadcasts_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    admin_chat_id = update.effective_chat.id
    broadcasts = db.get_broadcasts_for_admin(admin_chat_id)

    context.user_data["answers_broadcasts"] = broadcasts
    context.user_data["answers_page"] = page

    keyboard = build_broadcasts_keyboard(broadcasts, page=page)
    text = "Выберите рассылку, чтобы посмотреть ответы:"

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await update.callback_query.answer("Новых изменений пока нет", show_alert=False)
                return
            raise
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def show_broadcast_details(update: Update, context: ContextTypes.DEFAULT_TYPE, broadcast_id: int, back_page: int = 0):
    query = update.callback_query
    admin_chat_id = update.effective_chat.id

    details = db.get_broadcast_details_for_admin(admin_chat_id, broadcast_id)
    if not details:
        await query.edit_message_text("Рассылка не найдена.")
        return

    responses = db.get_broadcast_responses_for_admin(admin_chat_id, broadcast_id)

    lines = [
        f"📨 Рассылка #{details['broadcast_id']}",
        f"🕒 Создана: {details['created_at']}",
        f"👥 Получателей: {details['recipients_count']}",
        f"💬 Ответов всего: {details['total_responses']}",
        f"🆕 Новых ответов: {details['new_responses']}",
        "",
        "Текст рассылки:",
        details["message_text"],
        "",
        "Ответы:",
    ]

    if not responses:
        lines.append("Пока ответов нет.")
    else:
        for i, item in enumerate(responses, start=1):
            new_mark = " 🆕" if item["delivered_to_admin"] == 0 else ""
            lines.append(
                f"{i}. {item['employee_name']} — {item['created_at']}{new_mark}\n"
                f"{item['response_text']}"
            )
            lines.append("")

    text = "\n".join(lines).strip()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data=f"answers_open_{broadcast_id}_{back_page}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"answers_delete_confirm_{broadcast_id}_{back_page}")],
        [InlineKeyboardButton("⬅️ К списку", callback_data=f"answers_page_{back_page}")]
    ])

    try:
        await query.edit_message_text(text, reply_markup=keyboard)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

    db.mark_broadcast_responses_delivered(admin_chat_id, broadcast_id)


async def show_delete_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, broadcast_id: int, back_page: int = 0):
    query = update.callback_query
    admin_chat_id = update.effective_chat.id

    details = db.get_broadcast_details_for_admin(admin_chat_id, broadcast_id)
    if not details:
        await query.edit_message_text("Рассылка не найдена.")
        return

    preview = _short_text(details["message_text"], limit=60)

    text = (
        f"Удалить рассылку #{broadcast_id}?\n\n"
        f"Текст: {preview}\n"
        f"Ответов: {details['total_responses']}\n\n"
        f"Это действие нельзя отменить."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"answers_delete_yes_{broadcast_id}_{back_page}")
        ],
        [
            InlineKeyboardButton("⬅️ Отмена", callback_data=f"answers_open_{broadcast_id}_{back_page}")
        ]
    ])

    try:
        await query.edit_message_text(text, reply_markup=keyboard)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "send_all":
        service = get_drive_service()
        years = get_years(service, FOLDER_ID)
        await query.edit_message_text(
            "Выберите год",
            reply_markup=year_keyboard(years)
        )

    elif data.startswith("year_"):
        year = data.split("_")[1]
        service = get_drive_service()
        months = get_months(service, FOLDER_ID, year)
        await query.edit_message_text(
            f"Выберите месяц {year}",
            reply_markup=month_keyboard(year, months)
        )

    elif data.startswith("month_"):
        month = data.split("_")[1]
        context.user_data["selected_month"] = month

        keyboard = [
            [InlineKeyboardButton("✅ Использовать стандартный текст", callback_data="use_default")],
            [InlineKeyboardButton("✏️ Ввести свой текст", callback_data="enter_custom")],
        ]

        await query.edit_message_text(
            f"Выбран месяц {month}.\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "use_default":
        month = context.user_data.get("selected_month")
        if not month:
            await query.edit_message_text("Ошибка: месяц не выбран.\nНачните заново.")
            return

        await query.edit_message_text(
            f"Отправляю расчётки за {month} со стандартным текстом..."
        )
        await send_month_for_date(update, context, month, query.message, custom_caption=None)
        context.user_data.pop("selected_month", None)

    elif data == "enter_custom":
        context.user_data["awaiting_custom_text"] = True
        await query.edit_message_text(
            "Введите текст сообщения (отправьте одним сообщением):"
        )

    elif data.startswith("answers_page_"):
        page = int(data.split("_")[2])
        await show_broadcasts_page(update, context, page=page)

    elif data.startswith("answers_open_"):
        parts = data.split("_")
        broadcast_id = int(parts[2])
        back_page = int(parts[3]) if len(parts) > 3 else 0
        await show_broadcast_details(update, context, broadcast_id, back_page=back_page)

    elif data.startswith("answers_delete_confirm_"):
        parts = data.split("_")
        broadcast_id = int(parts[3])
        back_page = int(parts[4]) if len(parts) > 4 else 0
        await show_delete_broadcast_confirm(update, context, broadcast_id, back_page=back_page)

    elif data.startswith("answers_delete_yes_"):
        parts = data.split("_")
        broadcast_id = int(parts[3])
        back_page = int(parts[4]) if len(parts) > 4 else 0

        admin_chat_id = update.effective_chat.id
        deleted = db.delete_broadcast_for_admin(admin_chat_id, broadcast_id)

        if deleted:
            try:
                await update.callback_query.answer("Рассылка удалена", show_alert=False)
            except Exception:
                pass
            await show_broadcasts_page(update, context, page=back_page)
        else:
            await update.callback_query.answer("Не удалось удалить рассылку", show_alert=False)

    elif data.startswith("toggle_"):
        name = data[7:]
        selected = context.user_data["selected_employees"]

        if name in selected:
            selected.remove(name)
        else:
            selected.add(name)

        page = context.user_data.get("current_page", 0)
        await show_employees_page(update, context, page)

    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        context.user_data["current_page"] = page
        await show_employees_page(update, context, page)

    elif data == "broadcast_done":
        selected = context.user_data.get("selected_employees", set())

        if not selected:
            await query.edit_message_text("❌ Никто не выбран.\nРассылка отменена.")
            context.user_data.clear()
            return

        await query.edit_message_text(
            f"Выбрано сотрудников: {len(selected)}.\n"
            "Введите текст сообщения для отправки (или отправьте /cancel для отмены)."
        )
        context.user_data["awaiting_broadcast_text"] = True

    elif data == "broadcast_cancel":
        await query.edit_message_text("❌ Рассылка отменена.")
        context.user_data.clear()
    
    elif data == "broadcast_mode_active":
        employees = db.get_active_employees()

        if not employees:
            await query.edit_message_text("Нет работающих сотрудников.")
            return

        context.user_data['broadcast_employees'] = {name: chat_id for chat_id, name in employees}
        context.user_data['selected_employees'] = set()
        context.user_data['current_page'] = 0
        context.user_data['broadcast_filter_mode'] = 'active_only'

        await show_employees_page(update, context, page=0)

    elif data == "broadcast_mode_all":
        employees = db.get_all_employees()

        if not employees:
            await query.edit_message_text("Нет зарегистрированных сотрудников.")
            return

        context.user_data['broadcast_employees'] = {name: chat_id for chat_id, name in employees}
        context.user_data['selected_employees'] = set()
        context.user_data['current_page'] = 0
        context.user_data['broadcast_filter_mode'] = 'all'

        await show_employees_page(update, context, page=0)

    elif data == "moscow_mode_active":
        employees = db.get_active_employees_by_city("Москва")

        if not employees:
            await query.edit_message_text("Нет работающих сотрудников из Москвы.")
            return

        context.user_data["moscow_recipients"] = {name: chat_id for chat_id, name in employees}
        context.user_data["awaiting_moscow_text"] = True
        context.user_data["moscow_filter_mode"] = "active_only"

        await query.edit_message_text(
            f"Выбрано получателей: {len(employees)}\n\n"
            "Введите текст сообщения для отправки (или отправьте /cancel для отмены)."
        )
        return

    elif data == "moscow_mode_all":
        employees = db.get_employees_by_city("Москва")

        if not employees:
            await query.edit_message_text("Нет зарегистрированных сотрудников из Москвы.")
            return

        context.user_data["moscow_recipients"] = {name: chat_id for chat_id, name in employees}
        context.user_data["awaiting_moscow_text"] = True
        context.user_data["moscow_filter_mode"] = "all"

        await query.edit_message_text(
            f"Выбрано получателей: {len(employees)}\n\n"
            "Введите текст сообщения для отправки (или отправьте /cancel для отмены)."
        )
        return

   


def build_employees_keyboard(employees_dict, selected_set, page=0, items_per_page=5):
    names = sorted(employees_dict.keys())
    total_pages = math.ceil(len(names) / items_per_page)
    start = page * items_per_page
    end = start + items_per_page
    page_names = names[start:end]

    keyboard = []
    for name in page_names:
        status = "✅" if name in selected_set else "⬜"
        keyboard.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"toggle_{name}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([
        InlineKeyboardButton("✅ Готово", callback_data="broadcast_done"),
        InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)

async def show_employees_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    employees = context.user_data['broadcast_employees']
    selected = context.user_data['selected_employees']
    keyboard = build_employees_keyboard(employees, selected, page)
    text = f"Выберите сотрудников (страница {page+1}):\nТекущий выбор: {', '.join(selected) if selected else 'никто'}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)