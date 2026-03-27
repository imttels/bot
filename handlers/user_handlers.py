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


async def send_month_for_date(update: Update, context: ContextTypes.DEFAULT_TYPE, month: str, target_message, custom_caption=None):
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

    active_employees = db.get_active_employees()
    inactive_employees = db.get_inactive_employees()

    active_names = {name for _, name in active_employees}
    inactive_names = {name for _, name in inactive_employees}
    all_registered_names = active_names | inactive_names

    default_caption = db.get_setting("default_caption", "Расчётка за {month}")
    if custom_caption is not None:
        caption_text = custom_caption
    else:
        caption_text = default_caption.replace("{month}", month)

    files = list_pdfs_in_folder(service, month_folder_id)

    success = []
    failed_no_file = []
    failed_send_error = []
    inactive_skipped = sorted(inactive_names)
    unregistered = []

    for chat_id, name in active_employees:
        file = find_file_by_name(service, month_folder_id, name)

        if not file:
            failed_no_file.append(name)
            logger.warning(f"Файл не найден для активного сотрудника: {name}")
            continue

        original_filename = file["name"]

        try:
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(
                    executor, download_file, service, file["id"], original_filename
                )

            if "broadcast_id" not in context.user_data:
                broadcast_id = db.create_broadcast(sender_id, caption_text)
                context.user_data["broadcast_id"] = broadcast_id
            else:
                broadcast_id = context.user_data["broadcast_id"]

            message_text = caption_text + "\n\nОтветьте на это сообщение, если есть ошибка."

            with open(original_filename, "rb") as f:
                sent_message = await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=original_filename,
                    caption=message_text
                )

            db.add_broadcast_recipient(
                broadcast_id,
                chat_id,
                name,
                sent_message.message_id
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

        if name_from_file not in all_registered_names:
            unregistered.append(name_from_file)
            logger.warning(f"Незарегистрированный сотрудник в файле: {name_from_file}")

    total_active = len(active_employees)
    total_inactive = len(inactive_employees)
    total_registered = total_active + total_inactive
    total_files = len(files)

    report_lines = []
    report_lines.append(f"Месяц: {month}")
    report_lines.append(f"Всего зарегистрировано в боте: {total_registered}")
    report_lines.append(f"Работают: {total_active}")
    report_lines.append(f"Не работают: {total_inactive}")
    report_lines.append(f"Найдено PDF-файлов: {total_files}")
    report_lines.append("─" * 40)

    if success:
        report_lines.append(f"✅ Успешно отправлено ({len(success)}):")
        report_lines.append(", ".join(sorted(success)))
    else:
        report_lines.append("✅ Отправлено: —")

    if failed_no_file:
        report_lines.append(f"⚠️ Работают, но файла нет ({len(failed_no_file)}):")
        report_lines.append(", ".join(sorted(failed_no_file)))

    if failed_send_error:
        report_lines.append(f"❌ Ошибка при отправке ({len(failed_send_error)}):")
        report_lines.append(", ".join(failed_send_error))

    if inactive_skipped:
        report_lines.append(f"⏸ Не отправлено, сотрудник не работает ({len(inactive_skipped)}):")
        report_lines.append(", ".join(sorted(inactive_skipped)))

    if unregistered:
        report_lines.append(f"⚠️ Файлы есть, но сотрудник не зарегистрирован в боте ({len(unregistered)}):")
        report_lines.append(", ".join(sorted(set(unregistered))))

    if not (success or failed_no_file or failed_send_error or inactive_skipped or unregistered):
        report_lines.append("Ничего не обработано (папка пуста или ошибка доступа)")

    report = "\n".join(report_lines)
    context.user_data.pop("broadcast_id", None)
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
        
        default_caption = db.get_setting("default_caption", "Расчётка за {month}")
        caption_text = default_caption.replace("{month}", month)

        message_text = caption_text + "\n\nОтветьте на это сообщение, если есть ошибка."

        broadcast_id = db.create_broadcast(sender_id, name+" "+caption_text)

        with open(original_filename, "rb") as f:
            doc_msg = await context.bot.send_document(
                chat_id=target_chat_id,
                document=f,
                filename=original_filename,
                caption=message_text
            )

    

        db.add_broadcast_recipient(
            broadcast_id,
            target_chat_id,
            name,
            doc_msg.message_id
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

async def remove_inactive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_chat.id
    if sender_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён. Только администратор.")
        return

    deleted_count, deleted_names = db.remove_inactive_employees()

    if deleted_count == 0:
        await update.message.reply_text("Неработающих сотрудников в базе нет.")
        return

    report_lines = [
        f"Удалено неработающих сотрудников: {deleted_count}"
    ]

    if deleted_names:
        report_lines.append("")
        report_lines.append(", ".join(sorted(deleted_names)))

    await update.message.reply_text("\n".join(report_lines))
