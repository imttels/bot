from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from config import TOKEN
import db
from handlers.user_handlers import reg, send_user, send_month, list_employees, unreg
from handlers.admin_handlers import start, set_caption, broadcast_start, update_cities, send_pending_responses
from handlers.button_handlers import button_handler
from handlers.reply_handlers import reply_button_handler, cancel_action
from handlers.birthday_notification import send_today_birthdays, send_tomorrow_birthdays


async def start_scheduler(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_today_birthdays,
        trigger=CronTrigger(hour=7, minute=0), 
        args=[app],
        id='today_birthdays'
    )
    scheduler.add_job(
        send_tomorrow_birthdays,
        trigger=CronTrigger(hour=23, minute=24),  
        args=[app],
        id='tomorrow_birthdays'
    )
    scheduler.start()
    logging.info("Планировщик дней рождения запущен")



def main():
    db.init_db()

    app = ApplicationBuilder().token(TOKEN).post_init(start_scheduler).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reg", reg))
    app.add_handler(CommandHandler("send_user", send_user))
    app.add_handler(CommandHandler("send_month", send_month))
    app.add_handler(CommandHandler("list", list_employees))
    app.add_handler(CommandHandler("unreg", unreg))
    app.add_handler(CommandHandler("set_caption", set_caption))
    app.add_handler(CommandHandler("broadcast", broadcast_start))
    app.add_handler(CommandHandler("update_cities", update_cities))
    app.add_handler(CommandHandler("answers", send_pending_responses))
    app.add_handler(CommandHandler("cancel", cancel_action))




    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_button_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()