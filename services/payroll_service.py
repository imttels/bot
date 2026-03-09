import re
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import db

from drive_client import (
    get_drive_service,
    find_file_by_name,
    download_file,
    find_month_folder,
    list_pdfs_in_folder
)


async def send_month_for_date(update, context, month, target_message, folder_id, admin_ids):

    sender_id = update.effective_chat.id

    if sender_id not in admin_ids:
        await target_message.reply_text("Доступ запрещён. Только администратор.")
        return

    if not re.match(r'^\d{4}-\d{2}$', month):
        await target_message.reply_text("Месяц должен быть в формате YYYY-MM.")
        return

    service = get_drive_service()

    month_folder_id = find_month_folder(service, folder_id, f"расчетки-{month}")

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
            continue

        original_filename = file["name"]

        try:

            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(
                    executor,
                    download_file,
                    service,
                    file["id"],
                    original_filename
                )

            with open(original_filename, "rb") as f:

                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=original_filename,
                    caption=f"Расчётка за {month}"
                )

            success.append(name)

        except Exception as e:

            failed_send_error.append(f"{name} ({str(e)})")

        finally:

            if os.path.exists(original_filename):
                os.remove(original_filename)

        await asyncio.sleep(1)

    for file in files:

        import re

        match = re.match(r'^(.+?)_\d{4}-\d{2}', file["name"])

        name_from_file = match.group(1).strip() if match else None

        if not name_from_file:
            unregistered.append(f"Неверное имя файла: {file['name']}")
            continue

        if name_from_file not in registered_names:
            unregistered.append(name_from_file)

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
        report_lines.append(f"❌ Ошибка отправки ({len(failed_send_error)}):")
        report_lines.append(", ".join(failed_send_error))

    if unregistered:
        report_lines.append(f"⚠️ Файлы есть, но не зарегистрированы ({len(unregistered)}):")
        report_lines.append(", ".join(unregistered))

    if not (success or failed_no_file or failed_send_error or unregistered):
        report_lines.append("Ничего не обработано")

    report = "\n".join(report_lines)

    await target_message.reply_text(report)