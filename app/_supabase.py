from supabase import create_client
from flask import request, jsonify
from app import app, supabase
import requests
import jwt


def supabase_test_insert(email, zotero_access_token, zotero_access_secret, zotero_user_id):
    logger = app.logger
    logger.info(f"Email: {email}")
    logger.info(f"Zotero Access Token: {zotero_access_token}")
    logger.info(f"Zotero Access Secret: {zotero_access_secret}")

    try:
        response = supabase.table('zotero') \
            .upsert({
                'email': email,
                'zotero_access_token': zotero_access_token,
                'zotero_access_secret': zotero_access_secret,
                'zotero_user_id': zotero_user_id
            }) \
            .execute()
        logger.info(f"Response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in Supabase test: {str(e)}")
        raise e
    