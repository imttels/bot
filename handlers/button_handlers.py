from telegram import Update
from telegram.ext import ContextTypes

from config import FOLDER_ID
from drive_client import get_drive_service, get_years
from keyboards.inline_keyboards import year_keyboard, month_keyboard


def get_months(service, parent_folder_id, year):

    query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"

    results = service.files().list(
        q=query,
        fields="files(name)"
    ).execute()

    folders = results.get("files", [])

    months = []

    for folder in folders:

        name = folder["name"]

        if name.startswith(f"расчетки-{year}-"):

            month = name.split("-")[2]

            months.append(month)

    return sorted(months)


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