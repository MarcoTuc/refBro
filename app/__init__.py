# import os
from dotenv import dotenv_values
from flask import Flask
from flask_mail import Mail
import logging
from supabase import create_client

app = Flask(__name__)

app.config.from_mapping(dotenv_values())
app.logger.setLevel(logging.INFO)

mail = Mail(app)

# Initialize the Supabase client
supabase = create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_KEY"])

from app import routes
