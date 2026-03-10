from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import FOLDER_ID, ADMIN_CHAT_IDS
from drive_client import get_drive_service, get_years, find_month_folder, list_pdfs_in_folder
import db
import logging
from handlers.user_handlers import send_month_for_date
import math


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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "send_all":
        service = get_drive_service()
        years = get_years(service, FOLDER_ID)
        await query.edit_message_text("Выберите год", reply_markup=year_keyboard(years))
    elif data.startswith("year_"):
        year = data.split("_")[1]
        service = get_drive_service()
        months = get_months(service, FOLDER_ID, year)
        await query.edit_message_text(f"Выберите месяц {year}", reply_markup=month_keyboard(year, months))
    elif data.startswith("month_"):
        month = data.split("_")[1]
        context.user_data['selected_month'] = month
        keyboard = [
            [InlineKeyboardButton("✅ Использовать стандартный текст", callback_data="use_default")],
            [InlineKeyboardButton("✏️ Ввести свой текст", callback_data="enter_custom")]
        ]
        await query.edit_message_text(
            f"Выбран месяц {month}. Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "use_default":
        month = context.user_data.get('selected_month')
        if not month:
            await query.edit_message_text("Ошибка: месяц не выбран. Начните заново.")
            return
        await query.edit_message_text(f"Отправляю расчётки за {month} со стандартным текстом...")
        await send_month_for_date(update, context, month, query.message, custom_caption=None)
        context.user_data.pop('selected_month', None)

    elif data == "enter_custom":
        await query.edit_message_text("Введите текст сообщения (отправьте одним сообщением):")
        context.user_data['awaiting_custom_text'] = True

        

    if data.startswith("toggle_"):
        name = data[7:]  # убираем "toggle_"
        selected = context.user_data['selected_employees']
        if name in selected:
            selected.remove(name)
        else:
            selected.add(name)
        # Обновляем текущую страницу (извлекаем номер страницы из состояния)
        page = context.user_data.get('current_page', 0)
        await show_employees_page(update, context, page)

    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        context.user_data['current_page'] = page
        await show_employees_page(update, context, page)

    elif data == "broadcast_done":
        selected = context.user_data.get('selected_employees', set())
        if not selected:
            await query.edit_message_text("❌ Никто не выбран. Рассылка отменена.")
            context.user_data.clear()
            return
        await query.edit_message_text(
            f"Выбрано сотрудников: {len(selected)}.\n"
            "Введите текст сообщения для отправки (или отправьте /cancel для отмены)."
        )
        context.user_data['awaiting_broadcast_text'] = True

    elif data == "broadcast_cancel":
        await query.edit_message_text("❌ Рассылка отменена.")
        context.user_data.clear()


def build_employees_keyboard(employees_dict, selected_set, page=0, items_per_page=5):
    """Строит inline-клавиатуру для выбора сотрудников с чекбоксами."""
    names = sorted(employees_dict.keys())
    total_pages = math.ceil(len(names) / items_per_page)
    start = page * items_per_page
    end = start + items_per_page
    page_names = names[start:end]

    keyboard = []
    for name in page_names:
        status = "✅" if name in selected_set else "⬜"
        keyboard.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"toggle_{name}")])

    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопки действий
    keyboard.append([
        InlineKeyboardButton("✅ Готово", callback_data="broadcast_done"),
        InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)

async def show_employees_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    """Отображает страницу со списком сотрудников."""
    employees = context.user_data['broadcast_employees']
    selected = context.user_data['selected_employees']
    keyboard = build_employees_keyboard(employees, selected, page)
    text = f"Выберите сотрудников (страница {page+1}):\nТекущий выбор: {', '.join(selected) if selected else 'никто'}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)