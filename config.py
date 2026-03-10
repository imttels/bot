import os
import logging
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
FOLDER_ID = os.getenv("PARENT_FOLDER_ID")

ADMIN_CHAT_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_CHAT_IDS = [int(x.strip()) for x in ADMIN_CHAT_IDS_STR.split(",") if x.strip()]

if not ADMIN_CHAT_IDS:
    raise ValueError("ADMIN_IDS не указан")
    

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise ValueError("SPREADSHEET_ID не указан в .env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)