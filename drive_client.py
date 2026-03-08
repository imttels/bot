import os
import io
import sys
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

_service = None

def get_drive_service():
    global _service
    if _service is not None:
        return _service

    if not os.path.exists("credentials.json"):
        sys.exit("credentials.json не найден. Скачайте из Google Cloud Console.")

    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    _service = build("drive", "v3", credentials=creds)
    return _service

def find_file_by_name(service, folder_id, employee_name):
    query = (
        f"'{folder_id}' in parents "
        f"and name contains '{employee_name}' "
        f"and mimeType='application/pdf'"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    files = results.get("files", [])

    if not files:
        return None

    return files[0]

def find_month_folder(service, parent_folder_id, month_name):
    query = (
        f"'{parent_folder_id}' in parents "
        f"and name = '{month_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder'"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    folders = results.get("files", [])

    if not folders:
        return None

    return folders[0]["id"]

def download_file(service, file_id, filename):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(filename, "wb")

    downloader = MediaIoBaseDownload(fh, request)
    done = False

    while not done:
        status, done = downloader.next_chunk()

    fh.close()

def list_pdfs_in_folder(service, folder_id):
    query = (
        f"'{folder_id}' in parents "
        f"and mimeType='application/pdf'"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    return results.get("files", [])