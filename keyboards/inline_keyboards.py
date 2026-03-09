from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def year_keyboard(years):

    keyboard = []
    row = []

    for year in years:

        row.append(
            InlineKeyboardButton(year, callback_data=f"year_{year}")
        )

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

        row.append(
            InlineKeyboardButton(month, callback_data=f"month_{year}-{month}")
        )

        if len(row) == 4:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)