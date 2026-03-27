import os
import pickle
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google.oauth2 import service_account

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_sheets_service():

    creds = None
    if os.path.exists('token_sheets.pickle'):
        with open('token_sheets.pickle', 'rb') as token:
            creds = pickle.load(token) 
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token_sheets.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('sheets', 'v4', credentials=creds)
        return service
    except HttpError as err:
        logger.error(f"Ошибка создания sheets service: {err}")
        return None

def read_curators(spreadsheet_id):
    service = get_sheets_service()
    if not service:
        return []

    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        if not sheets:
            logger.error("В таблице нет листов")
            return []
        first_sheet_title = sheets[0]['properties']['title']

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{first_sheet_title}'!A:F" 
        ).execute()
        rows = result.get('values', [])

        if not rows:
            logger.info("Таблица пуста")
            return []

        curators = []
        for row in rows[1:]:
            while len(row) < 6:
                row.append('')
            curator = {
                'name': row[0].strip(),
                'telegram_nick': row[1].strip(),
                'city': row[2].strip(),
                'birth_date': row[3].strip(),
                'phone': row[4].strip(),
                'status': row[5].strip().lower()
            }
            if curator['name']:
                curators.append(curator)
        return curators

    except HttpError as err:
        logger.error(f"Ошибка чтения таблицы: {err}")
        return []