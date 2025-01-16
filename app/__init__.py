from dotenv import dotenv_values
from flask import Flask
from flask_mail import Mail
import logging
from supabase import create_client
import os
app = Flask(__name__)


app.config['SUPABASE_URL'] = os.getenv('SUPABASE_URL')
app.config['SUPABASE_KEY'] = os.getenv('SUPABASE_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))  # Default to 587 if not set
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['ZOTERO_CLIENT_KEY'] = os.getenv('ZOTERO_CLIENT_KEY')
app.config['ZOTERO_CLIENT_SECRET'] = os.getenv('ZOTERO_CLIENT_SECRET')
app.config['ZOTERO_CALLBACK_URL'] = os.getenv('ZOTERO_CALLBACK_URL')
app.config['OPENAI_KEY'] = os.getenv('OPENAI_KEY')
app.config['OPENALEX_EMAIL'] = os.getenv('OPENALEX_EMAIL')
app.config['EMAILS_SPREADSHEET_ID'] = os.getenv('EMAILS_SPREADSHEET_ID')
app.config['FEEDBACK_SPREADSHEET_ID'] = os.getenv('FEEDBACK_SPREADSHEET_ID')



app.config.from_mapping(dotenv_values())
app.logger.setLevel(logging.INFO)

mail = Mail(app)

SUPABASE_URL = app.config["SUPABASE_URL"]
SUPABASE_KEY = app.config["SUPABASE_KEY"]
# Initialize the Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

from app import routes
