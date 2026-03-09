# import os
# import re
# import logging
# import asyncio
# from concurrent.futures import ThreadPoolExecutor
# from dotenv import load_dotenv
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import (
#     ApplicationBuilder,
#     CommandHandler,
#     ContextTypes,
#     CallbackQueryHandler,
#     MessageHandler,
#     filters,
# )
# import db
# from drive_client import (
#     get_drive_service,
#     find_file_by_name,
#     download_file,
#     find_month_folder,
#     list_pdfs_in_folder,
#     get_years,
# )
# from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove


# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# load_dotenv()
# TOKEN = os.getenv("BOT_TOKEN")
# FOLDER_ID = os.getenv("PARENT_FOLDER_ID")

# ADMIN_CHAT_IDS_STR = os.getenv("ADMIN_IDS", "")
# ADMIN_CHAT_IDS = [int(id.strip()) for id in ADMIN_CHAT_IDS_STR.split(",") if id.strip()]
# if not ADMIN_CHAT_IDS:
#     raise ValueError("ADMIN_IDS не указан в .env")

# db.init_db()

# # ---------- Вспомогательные функции для клавиатур и месяцев ----------
# def get_months(service, parent_folder_id, year):
#     """Возвращает список месяцев для указанного года на основе папок расчетки-ГГГГ-ММ."""
#     query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
#     results = service.files().list(q=query, fields="files(name)").execute()
#     folders = results.get("files", [])
#     months = []
#     for folder in folders:
#         name = folder["name"]
#         if name.startswith(f"расчетки-{year}-"):
#             month = name.split("-")[2]
#             months.append(month)
#     return sorted(months)

# def year_keyboard(years):
#     keyboard = []
#     row = []
#     for year in years:
#         row.append(InlineKeyboardButton(year, callback_data=f"year_{year}"))
#         if len(row) == 3:
#             keyboard.append(row)
#             row = []
#     if row:
#         keyboard.append(row)
#     return InlineKeyboardMarkup(keyboard)

# def month_keyboard(year, months):
#     keyboard = []
#     row = []
#     for month in months:
#         row.append(InlineKeyboardButton(month, callback_data=f"month_{year}-{month}"))
#         if len(row) == 4:
#             keyboard.append(row)
#             row = []
#     if row:
#         keyboard.append(row)
#     return InlineKeyboardMarkup(keyboard)

# def main_menu():
#     keyboard = [
#         [InlineKeyboardButton("📄 Отправить расчетки всем", callback_data="send_all")],
#         [InlineKeyboardButton("👤 Отправить расчетку сотруднику", callback_data="send_user")],
#         [InlineKeyboardButton("📋 Список сотрудников", callback_data="employees")]
#     ]
#     return InlineKeyboardMarkup(keyboard)

# # ---------- Основная логика отправки за месяц (с возможностью указать целевое сообщение для ответа) ----------
# async def send_month_for_date(update: Update, context: ContextTypes.DEFAULT_TYPE, month: str, target_message):
#     """Отправляет расчетки всем сотрудникам за месяц, результат пишет в target_message."""
#     sender_id = update.effective_chat.id
#     if sender_id not in ADMIN_CHAT_IDS:
#         await target_message.reply_text("Доступ запрещён. Только администратор.")
#         return

#     if not re.match(r'^\d{4}-\d{2}$', month):
#         await target_message.reply_text("Месяц должен быть в формате YYYY-MM.")
#         return

#     service = get_drive_service()
#     month_folder_id = find_month_folder(service, FOLDER_ID, f"расчетки-{month}")

#     if not month_folder_id:
#         await target_message.reply_text(f"Папка 'расчетки-{month}' не найдена.")
#         return

#     all_employees = db.get_all_employees()
#     registered_names = {name for _, name in all_employees}

#     files = list_pdfs_in_folder(service, month_folder_id)

#     success = []
#     failed_no_file = []
#     failed_send_error = []
#     unregistered = []

#     for chat_id, name in all_employees:
#         file = find_file_by_name(service, month_folder_id, name)

#         if not file:
#             failed_no_file.append(name)
#             logger.warning(f"Файл не найден для зарегистрированного: {name}")
#             continue

#         original_filename = file["name"]
#         try:
#             with ThreadPoolExecutor() as executor:
#                 await asyncio.get_event_loop().run_in_executor(
#                     executor, download_file, service, file["id"], original_filename
#                 )

#             with open(original_filename, "rb") as f:
#                 await context.bot.send_document(
#                     chat_id=chat_id,
#                     document=f,
#                     filename=original_filename,
#                     caption=f"Расчётка за {month}"
#                 )
#             success.append(name)
#             logger.info(f"Отправлено: {name} за {month}")
#         except Exception as e:
#             failed_send_error.append(f"{name} (ошибка: {str(e)})")
#             logger.error(f"Ошибка отправки {name}: {str(e)}")
#         finally:
#             if os.path.exists(original_filename):
#                 os.remove(original_filename)

#         await asyncio.sleep(1)

#     for file in files:
#         match = re.match(r'^(.+?)_\d{4}-\d{2}', file["name"])
#         name_from_file = match.group(1).strip() if match else None

#         if not name_from_file:
#             unregistered.append(f"Неверное имя файла: {file['name']}")
#             continue

#         if name_from_file not in registered_names:
#             unregistered.append(name_from_file)
#             logger.warning(f"Незарегистрированный сотрудник в файле: {name_from_file}")

#     total_registered = len(all_employees)
#     total_files = len(files)

#     report_lines = []
#     report_lines.append(f"Месяц: {month}")
#     report_lines.append(f"Зарегистрировано в боте: {total_registered}")
#     report_lines.append(f"Найдено PDF-файлов: {total_files}")
#     report_lines.append("─" * 40)

#     if success:
#         report_lines.append(f"✅ Успешно отправлено ({len(success)}):")
#         report_lines.append(", ".join(success))
#     else:
#         report_lines.append("✅ Отправлено: —")

#     if failed_no_file:
#         report_lines.append(f"⚠️ Зарегистрированы, но файла нет ({len(failed_no_file)}):")
#         report_lines.append(", ".join(failed_no_file))

#     if failed_send_error:
#         report_lines.append(f"❌ Ошибка при отправке ({len(failed_send_error)}):")
#         report_lines.append(", ".join(failed_send_error))

#     if unregistered:
#         report_lines.append(f"⚠️ Файлы есть, но не зарегистрированы ({len(unregistered)}):")
#         report_lines.append(", ".join(unregistered))

#     if not (success or failed_no_file or failed_send_error or unregistered):
#         report_lines.append("Ничего не обработано (папка пуста или ошибка доступа)")

#     report = "\n".join(report_lines)
#     await target_message.reply_text(report)

# # ---------- Обработчики команд ----------


# async def reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     chat_id = update.effective_chat.id
#     if not context.args:
#         await update.message.reply_text("Напиши так: /reg Имя Фамилия")
#         return
#     name = " ".join(context.args).strip()
#     success = db.add_employee(chat_id, name)
#     if not success:
#         await update.message.reply_text("Это имя уже занято другим пользователем.")
#         return
#     logger.info(f"Регистрация: chat_id={chat_id}, name={name}")
#     await update.message.reply_text(f"Ты зарегистрирован! как: {name}")

# async def send_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     sender_id = update.effective_chat.id
#     if sender_id not in ADMIN_CHAT_IDS:
#         await update.message.reply_text("Доступ запрещён. Только администратор.")
#         return
#     if len(context.args) < 2:
#         await update.message.reply_text("Используй: /send_user Имя Фамилия 2026-01")
#         return
#     month = context.args[-1]
#     name = " ".join(context.args[:-1]).strip()
#     if not re.match(r'^\d{4}-\d{2}$', month):
#         await update.message.reply_text("Месяц должен быть в формате YYYY-MM.")
#         return
#     service = get_drive_service()
#     month_folder_id = find_month_folder(service, FOLDER_ID, f"расчетки-{month}")
#     if not month_folder_id:
#         await update.message.reply_text(f"Папка 'расчетки-{month}' не найдена.")
#         return
#     target_chat_id = db.get_employee_by_name(name)
#     if not target_chat_id:
#         await update.message.reply_text(f"Сотрудник '{name}' не найден в базе.")
#         return
#     file = find_file_by_name(service, month_folder_id, name)
#     if not file:
#         await update.message.reply_text(f"Файл для '{name}' не найден.")
#         return
#     original_filename = file["name"]
#     try:
#         with ThreadPoolExecutor() as executor:
#             await asyncio.get_event_loop().run_in_executor(executor, download_file, service, file["id"], original_filename)
#         with open(original_filename, "rb") as f:
#             await context.bot.send_document(
#                 chat_id=target_chat_id,
#                 document=f,
#                 filename=original_filename,
#                 caption=f"Расчётка за {month}"
#             )
#         logger.info(f"Отправлено: {name} за {month} админом {sender_id}")
#         await update.message.reply_text("Отправлено.")
#     except Exception as e:
#         logger.error(f"Ошибка отправки {name}: {str(e)}")
#         await update.message.reply_text(f"Ошибка: {str(e)}")
#     finally:
#         if os.path.exists(original_filename):
#             os.remove(original_filename)

# async def send_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Обработчик команды /send_month YYYY-MM"""
#     if not context.args:
#         await update.message.reply_text("Укажи месяц: /send_month 2026-01")
#         return
#     month = context.args[0]
#     await send_month_for_date(update, context, month, update.message)

# async def list_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.effective_chat.id not in ADMIN_CHAT_IDS:
#         await update.message.reply_text("Доступ запрещён. Только администратор.")
#         return
#     employees = db.get_all_employees()
#     if not employees:
#         await update.message.reply_text("Нет зарегистрированных сотрудников.")
#         return
#     msg = "\n".join(f"{name} (chat_id: {cid})" for cid, name in employees)
#     await update.message.reply_text(msg)

# async def unreg(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     sender_id = update.effective_chat.id
#     if sender_id not in ADMIN_CHAT_IDS:
#         await update.message.reply_text("Доступ запрещён. Только администратор.")
#         return
#     if not context.args:
#         await update.message.reply_text("Укажи имя: /unreg Имя Фамилия")
#         return
#     name = " ".join(context.args).strip()
#     employee_chat_id = db.get_employee_by_name(name)
#     if not employee_chat_id:
#         await update.message.reply_text(f"Сотрудник '{name}' не найден.")
#         return
#     success = db.remove_employee(name, admin_chat_ids=ADMIN_CHAT_IDS)
#     if success:
#         logger.info(f"Удалён: {name} (chat_id={employee_chat_id})")
#         await update.message.reply_text(f"Сотрудник '{name}' успешно удалён.")
#     else:
#         if employee_chat_id in ADMIN_CHAT_IDS:
#             await update.message.reply_text(f"Нельзя удалить '{name}' — это администратор.")
#         else:
#             await update.message.reply_text(f"Сотрудник '{name}' не найден или уже удалён.")

# async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Выберите действие", reply_markup=main_menu())

# # ---------- Обработчик инлайн-кнопок ----------
# async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     data = query.data

#     if data == "send_all":
#         service = get_drive_service()
#         years = get_years(service, FOLDER_ID)
#         await query.edit_message_text(
#             "Выберите год",
#             reply_markup=year_keyboard(years)
#         )
#     elif data.startswith("year_"):
#         year = data.split("_")[1]
#         service = get_drive_service()
#         months = get_months(service, FOLDER_ID, year)
#         await query.edit_message_text(
#             f"Выберите месяц {year}",
#             reply_markup=month_keyboard(year, months)
#         )
#     elif data.startswith("month_"):
#         month = data.split("_")[1]  # формат YYYY-MM
#         await query.edit_message_text(f"Отправляю расчетки за {month}...")
#         # Используем query.message как целевое сообщение для отчёта
#         await send_month_for_date(update, context, month, query.message)


# def get_admin_keyboard():
#     """Возвращает reply-клавиатуру для администратора."""
#     keyboard = [
#         ["📄 Отправить расчетки всем"],
#         ["👤 Отправить расчетку сотруднику"],
#         ["📋 Список сотрудников"],
#         ["❓ Помощь"]
#     ]
#     return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     chat_id = update.effective_chat.id
#     if chat_id in ADMIN_CHAT_IDS:
#         await update.message.reply_text(
#             "Главное меню администратора",
#             reply_markup=get_admin_keyboard()
#         )
#         context.user_data['keyboard_sent'] = True
#     else:
#         await update.message.reply_text(
#             "Вы не являетесь администратором. Для регистрации используйте /reg Имя Фамилия.",
#             reply_markup=ReplyKeyboardRemove()
#         )

# async def reply_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Обрабатывает все текстовые сообщения (кроме команд)."""
#     chat_id = update.effective_chat.id
#     text = update.message.text

#     # Если пользователь не администратор — только регистрация
#     if chat_id not in ADMIN_CHAT_IDS:
#         # Можно предложить зарегистрироваться, если сообщение не /reg
#         await update.message.reply_text(
#             "Вы не администратор. Для регистрации отправьте /reg Имя Фамилия"
#         )
#         return

#     # Администратор: проверяем, отправляли ли уже клавиатуру
#     if not context.user_data.get('keyboard_sent'):
#         # Отправляем клавиатуру в первый раз
#         await update.message.reply_text(
#             "Используйте кнопки меню",
#             reply_markup=get_admin_keyboard()
#         )
#         context.user_data['keyboard_sent'] = True

#     # Теперь проверяем, является ли сообщение нажатием на кнопку
#     if text == "📄 Отправить расчетки всем":
#         service = get_drive_service()
#         years = get_years(service, FOLDER_ID)
#         await update.message.reply_text(
#             "Выберите год",
#             reply_markup=year_keyboard(years)
#         )
#     elif text == "👤 Отправить расчетку сотруднику":
#         await update.message.reply_text(
#             "Используйте команду /send_user Имя Фамилия YYYY-MM\n"
#             "Например: /send_user Иван Петров 2026-01"
#         )
#     elif text == "📋 Список сотрудников":
#         await list_employees(update, context)
#     elif text == "❓ Помощь":
#         help_text = (
#             "Команды администратора:\n"
#             "/send_user Имя Фамилия YYYY-MM — отправить расчетку конкретному сотруднику\n"
#             "/send_month YYYY-MM — отправить расчетки всем за месяц\n"
#             "/list — список зарегистрированных сотрудников\n"
#             "/unreg Имя Фамилия — удалить сотрудника\n"
#             "/reg — регистрация (для обычных пользователей)"
#         )
#         await update.message.reply_text(help_text)
#     else:
#         # Если текст не совпадает с кнопками — ничего не делаем (клавиатура уже висит)
#         pass

# # ---------- Запуск бота ----------
# def main():
#     app = ApplicationBuilder().token(TOKEN).build()

#     app.add_handler(CommandHandler("start", start))
#     app.add_handler(CommandHandler("reg", reg))
#     app.add_handler(CommandHandler("send_user", send_user))
#     app.add_handler(CommandHandler("send_month", send_month))
#     app.add_handler(CommandHandler("list", list_employees))
#     app.add_handler(CommandHandler("unreg", unreg))
#     # Новый обработчик для reply-кнопок (должен быть перед общим обработчиком не-команд)
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_button_handler))
#     # Убираем старый show_menu, потому что reply_button_handler покрывает все некомандные сообщения
#     app.add_handler(CallbackQueryHandler(button_handler))

#     app.run_polling()

# if __name__ == "__main__":
#     main()




from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import TOKEN

from handlers.user_handlers import reg
from handlers.admin_handlers import start
from handlers.button_handlers import button_handler


def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reg", reg))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()


if __name__ == "__main__":
    main()