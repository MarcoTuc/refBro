from supabase import create_client
from flask import request, jsonify
from app import app

SUPABASE_URL = app.config["SUPABASE_URL"]
SUPABASE_KEY = app.config["SUPABASE_KEY"]

def get_supabase_client():
    """
    Initialize Supabase client with the service role key.
    This key bypasses RLS and is used for server-side operations.
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def save_to_database(user_id, access_token, access_secret):
    """
    Save Zotero credentials to the Supabase profiles table.
    """
    try:
        app.logger.debug(f"Attempting to save to database: user_id={user_id}, access_token={access_token}, access_secret={access_secret}")
        
        # Initialize Supabase client with the user's JWT
        try:
            supabase = get_supabase_client()
        except Exception as e:
            app.logger.error(f"Supabase client initialization failed: {e}")
            return jsonify({"error": "Authorization failed"}), 401

        # Use upsert to insert or update the record
        response = supabase.table("profiles").upsert({
            "id": user_id,  # Primary key
            "zotero_access_token": access_token,
            "zotero_access_secret": access_secret,
        }, on_conflict=["id"]).execute()

        current_app.logger.debug(f"Supabase request payload: {response}")

        # Check for errors in the response
        if response.get("error"):
            app.logger.error(f"Error updating/inserting database: {response['error']}")
            raise Exception(f"Error updating/inserting database: {response['error']}")

        # Log the successful response
        app.logger.debug(f"Database upsert successful: {response.get('data')}")

        return response.get("data")
    except Exception as e:
        app.logger.error(f"Error saving to database: {e}")
        raise
