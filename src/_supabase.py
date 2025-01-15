from supabase import create_client
from flask import current_app

# Supabase URL and Key
SUPABASE_URL = "https://wyrflssqbzxklzeowjjn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind5cmZsc3NxYnp4a2x6ZW93ampuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzY4ODEzNTQsImV4cCI6MjA1MjQ1NzM1NH0.ffQli-xxRUPFsNO8nk2wndpY-ShatAeCmAfD2uHRZcA"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_to_database(user_id, access_token, access_secret):
    """
    Save Zotero credentials to the Supabase profiles table.
    """
    try:
        current_app.logger.debug(f"Attempting to save to database: user_id={user_id}, access_token={access_token}, access_secret={access_secret}")

        # Use upsert to insert or update the record
        response = supabase.table("profiles").upsert({
            "id": user_id,  # Primary key
            "zotero_access_token": access_token,
            "zotero_access_secret": access_secret,
        }, on_conflict=["id"]).execute()

        # Check for errors in the response
        if response.get("error"):
            current_app.logger.error(f"Error updating/inserting database: {response['error']}")
            raise Exception(f"Error updating/inserting database: {response['error']}")

        # Log the successful response
        current_app.logger.debug(f"Database upsert successful: {response.get('data')}")

        return response.get("data")
    except Exception as e:
        current_app.logger.error(f"Error saving to database: {e}")
        raise
