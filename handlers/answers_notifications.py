import logging
import db

logger = logging.getLogger(__name__)

async def notify_about_new_answers(app):
    admins = db.get_admins_with_unnotified_responses()

    if not admins:
        logger.info("Новых неуведомлённых ответов нет")
        return

    for item in admins:
        admin_chat_id = item["admin_chat_id"]
        new_count = item["new_count"]

        text = (
            f"🔔 Поступили новые ответы по рассылке: {new_count} шт.\n\n"
            f"Нажмите кнопку «Получить ответы», чтобы посмотреть."
        )

        try:
            await app.bot.send_message(chat_id=admin_chat_id, text=text)
            db.mark_notifications_sent_for_admin(admin_chat_id)
            logger.info(f"Отправлено уведомление админу {admin_chat_id}")
        except Exception as e:
            logger.exception(f"Не удалось отправить уведомление админу {admin_chat_id}: {e}")