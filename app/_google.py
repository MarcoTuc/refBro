import os
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app import app, mail 

# Email configuration
app.config['MAIL_SERVER'] = app.config['MAIL_SERVER']
app.config['MAIL_PORT'] = int(app.config['MAIL_PORT'])
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = app.config['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = app.config['MAIL_PASSWORD']
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_DEFAULT_SENDER']

oauth_token_store = {}

# Google Sheets configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
EMAILS_SPREADSHEET_ID = app.config["EMAILS_SPREADSHEET_ID"]
FEEDBACK_SPREADSHEET_ID = app.config['FEEDBACK_SPREADSHEET_ID']

def get_google_sheets_service():
    try:
        # Check if we have the JSON directly in environment (production)
        creds_json = app.config['GOOGLE_CREDENTIALS_JSON']
        if creds_json:
            creds_dict = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES)
        else:
            # Fallback to file (local development)
            credentials = service_account.Credentials.from_service_account_file(
                os.getenv('GOOGLE_CREDENTIALS_PATH', 'google-credentials.json'), 
                scopes=SCOPES)
            
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        app.logger.error(f"Error creating Google Sheets service: {str(e)}")
        return None

def append_to_sheet(spreadsheet_id, values):
    try:
        service = get_google_sheets_service()
        if not service:
            raise Exception("Could not initialize Google Sheets service")
            
        body = {
            'values': [values]
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        return result
    except Exception as e:
        app.logger.error(f"Error appending to sheet: {str(e)}")
        raise
