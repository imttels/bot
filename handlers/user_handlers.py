from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS, FOLDER_ID
import db
from drive_client import get_drive_service, find_file_by_name, download_file, find_month_folder,list_pdfs_in_folder, get_years
import logging
import re
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


async def send_month_for_date(update: Update, context: ContextTypes.DEFAULT_TYPE, month: str, target_message):
    sender_id = update.effective_chat.id
    if sender_id not in ADMIN_CHAT_IDS:
        await target_message.reply_text("Доступ запрещён. Только администратор.")
        return

    if not re.match(r'^\d{4}-\d{2}$', month):
        await target_message.reply_text("Месяц должен быть в формате YYYY-MM.")
        return

    service = get_drive_service()
    month_folder_id = find_month_folder(service, FOLDER_ID, f"расчетки-{month}")

    if not month_folder_id:
        await target_message.reply_text(f"Папка 'расчетки-{month}' не найдена.")
        return

    all_employees = db.get_all_employees()
    registered_names = {name for _, name in all_employees}

    files = list_pdfs_in_folder(service, month_folder_id)

    success = []
    failed_no_file = []
    failed_send_error = []
    unregistered = []

    for chat_id, name in all_employees:
        file = find_file_by_name(service, month_folder_id, name)

        if not file:
            failed_no_file.append(name)
            logger.warning(f"Файл не найден для зарегистрированного: {name}")
            continue

        original_filename = file["name"]
        try:
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(
                    executor, download_file, service, file["id"], original_filename
                )

            with open(original_filename, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=original_filename,
                    caption=f"Расчётка за {month}"
                )
            success.append(name)
            logger.info(f"Отправлено: {name} за {month}")
        except Exception as e:
            failed_send_error.append(f"{name} (ошибка: {str(e)})")
            logger.error(f"Ошибка отправки {name}: {str(e)}")
        finally:
            if os.path.exists(original_filename):
                os.remove(original_filename)

        await asyncio.sleep(1)

    for file in files:
        match = re.match(r'^(.+?)_\d{4}-\d{2}', file["name"])
        name_from_file = match.group(1).strip() if match else None

        if not name_from_file:
            unregistered.append(f"Неверное имя файла: {file['name']}")
            continue

        if name_from_file not in registered_names:
            unregistered.append(name_from_file)
            logger.warning(f"Незарегистрированный сотрудник в файле: {name_from_file}")

    total_registered = len(all_employees)
    total_files = len(files)

    report_lines = []
    report_lines.append(f"Месяц: {month}")
    report_lines.append(f"Зарегистрировано в боте: {total_registered}")
    report_lines.append(f"Найдено PDF-файлов: {total_files}")
    report_lines.append("─" * 40)

    if success:
        report_lines.append(f"✅ Успешно отправлено ({len(success)}):")
        report_lines.append(", ".join(success))
    else:
        report_lines.append("✅ Отправлено: —")

    if failed_no_file:
        report_lines.append(f"⚠️ Зарегистрированы, но файла нет ({len(failed_no_file)}):")
        report_lines.append(", ".join(failed_no_file))

    if failed_send_error:
        report_lines.append(f"❌ Ошибка при отправке ({len(failed_send_error)}):")
        report_lines.append(", ".join(failed_send_error))

    if unregistered:
        report_lines.append(f"⚠️ Файлы есть, но не зарегистрированы ({len(unregistered)}):")
        report_lines.append(", ".join(unregistered))

    if not (success or failed_no_file or failed_send_error or unregistered):
        report_lines.append("Ничего не обработано (папка пуста или ошибка доступа)")

    report = "\n".join(report_lines)
    await target_message.reply_text(report)


async def reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Напиши так: /reg Имя Фамилия")
        return
    name = " ".join(context.args).strip()
    success = db.add_employee(chat_id, name)
    if not success:
        await update.message.reply_text("Это имя уже занято другим пользователем.")
        return
    logger.info(f"Регистрация: chat_id={chat_id}, name={name}")
    await update.message.reply_text(f"Ты зарегистрирован! как: {name}")

async def send_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_chat.id
    if sender_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён. Только администратор.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /send_user Имя Фамилия 2026-01")
        return
    month = context.args[-1]
    name = " ".join(context.args[:-1]).strip()
    if not re.match(r'^\d{4}-\d{2}$', month):
        await update.message.reply_text("Месяц должен быть в формате YYYY-MM.")
        return
    service = get_drive_service()
    month_folder_id = find_month_folder(service, FOLDER_ID, f"расчетки-{month}")
    if not month_folder_id:
        await update.message.reply_text(f"Папка 'расчетки-{month}' не найдена.")
        return
    target_chat_id = db.get_employee_by_name(name)
    if not target_chat_id:
        await update.message.reply_text(f"Сотрудник '{name}' не найден в базе.")
        return
    file = find_file_by_name(service, month_folder_id, name)
    if not file:
        await update.message.reply_text(f"Файл для '{name}' не найден.")
        return
    original_filename = file["name"]
    try:
        with ThreadPoolExecutor() as executor:
            await asyncio.get_event_loop().run_in_executor(executor, download_file, service, file["id"], original_filename)
        with open(original_filename, "rb") as f:
            await context.bot.send_document(
                chat_id=target_chat_id,
                document=f,
                filename=original_filename,
                caption=f"Расчётка за {month}"
            )
        logger.info(f"Отправлено: {name} за {month} админом {sender_id}")
        await update.message.reply_text("Отправлено.")
    except Exception as e:
        logger.error(f"Ошибка отправки {name}: {str(e)}")
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        if os.path.exists(original_filename):
            os.remove(original_filename)

async def send_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажи месяц: /send_month 2026-01")
        return
    month = context.args[0]
    await send_month_for_date(update, context, month, update.message)

async def list_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён. Только администратор.")
        return
    employees = db.get_all_employees()
    if not employees:
        await update.message.reply_text("Нет зарегистрированных сотрудников.")
        return
    msg = "\n".join(f"{name} (chat_id: {cid})" for cid, name in employees)
    await update.message.reply_text(msg)

async def unreg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_chat.id
    if sender_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён. Только администратор.")
        return
    if not context.args:
        await update.message.reply_text("Укажи имя: /unreg Имя Фамилия")
        return
    name = " ".join(context.args).strip()
    employee_chat_id = db.get_employee_by_name(name)
    if not employee_chat_id:
        await update.message.reply_text(f"Сотрудник '{name}' не найден.")
        return
    success = db.remove_employee(name, admin_chat_ids=ADMIN_CHAT_IDS)
    if success:
        logger.info(f"Удалён: {name} (chat_id={employee_chat_id})")
        await update.message.reply_text(f"Сотрудник '{name}' успешно удалён.")
    else:
        if employee_chat_id in ADMIN_CHAT_IDS:
            await update.message.reply_text(f"Нельзя удалить '{name}' — это администратор.")
        else:
            await update.message.reply_text(f"Сотрудник '{name}' не найден или уже удалён.")
