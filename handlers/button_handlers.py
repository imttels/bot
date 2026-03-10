from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import FOLDER_ID, ADMIN_CHAT_IDS
from drive_client import get_drive_service, get_years, find_month_folder, list_pdfs_in_folder
import db
import logging
from handlers.user_handlers import send_month_for_date 

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