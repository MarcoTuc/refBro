from dotenv import dotenv_values
from flask import Flask
from flask_mail import Mail
import logging

app = Flask(__name__)
app.config.from_mapping(dotenv_values())
app.logger.setLevel(logging.INFO)

mail = Mail(app)

from app import routes
