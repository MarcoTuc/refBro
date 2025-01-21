# import os
import logging
from flask import Flask
from flask_mail import Mail
from supabase import create_client
from config import Config

app = Flask(__name__)
app.config.from_object(Config())
app.logger.setLevel(logging.INFO)
mail = Mail(app)
supabase = create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_KEY"])

from app import routes