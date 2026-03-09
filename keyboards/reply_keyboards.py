from telegram import ReplyKeyboardMarkup

def get_admin_keyboard():
    keyboard = [
        ["📄 Отправить расчетки всем"],
        ["👤 Отправить расчетку сотруднику"],
        ["📋 Список сотрудников"],
        ["❓ Помощь"]
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)