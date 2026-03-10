from datetime import datetime, timedelta
import logging
from services.sheets_client import read_curators
from config import SPREADSHEET_ID 

logger = logging.getLogger(__name__)

def parse_birthday(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    for sep in ['.']:
        if sep in date_str:
            parts = date_str.split(sep)
            if len(parts) >= 2:
                try:
                    day = int(parts[0])
                    month = int(parts[1])
                    return (month, day)
                except ValueError:
                    continue
    logger.warning(f"Не удалось распознать дату: {date_str}")
    return None

def get_birthday_people(target_date):
    curators = read_curators(SPREADSHEET_ID)
    result = []
    for curator in curators:
        bd = parse_birthday(curator['birth_date'])
        if bd:
            month, day = bd
            if month == target_date.month and day == target_date.day:
                result.append(curator)
    return result

def get_today_birthdays():
    today = datetime.now().date()
    logger.info(f"Поиск именинников на {today}")
    curators = read_curators(SPREADSHEET_ID)
    logger.info(f"Загружено кураторов: {len(curators)}")
    return get_birthday_people(today)

def get_tomorrow_birthdays():
    tomorrow = datetime.now().date() + timedelta(days=1)
    return get_birthday_people(tomorrow)