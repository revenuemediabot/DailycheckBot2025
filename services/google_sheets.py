# services/google_sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import GOOGLE_SHEET_ID, BASE_DIR
import logging

def get_sheets_client():
    try:
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(BASE_DIR / 'service_account.json'), scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logging.error(f"Ошибка авторизации Google Sheets: {e}")
        return None

def write_user_stats(user_id: int, stats: dict):
    client = get_sheets_client()
    if client is None:
        return False
    try:
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("users")
        # TODO: Запись статистики по user_id
        return True
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")
        return False
