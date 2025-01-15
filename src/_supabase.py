from supabase import create_client
from flask import current_app, request, jsonify

SUPABASE_URL = "https://wyrflssqbzxklzeowjjn.supabase.co"

def get_supabase_client():
    """Dynamically initialize Supabase client with user's JWT."""
    auth_header = request.headers.get("Authorization")
    current_app.logger.debug(f"Authorization header: {auth_header}")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise Exception("Missing or invalid Authorization header")
    
    jwt_token = auth_header.split("Bearer ")[1]  # Extract the JWT
    return create_client(SUPABASE_URL, jwt_token)

def save_to_database(user_id, access_token, access_secret):
    """
    Save Zotero credentials to the Supabase profiles table.
    """
    try:
        current_app.logger.debug(f"Attempting to save to database: user_id={user_id}, access_token={access_token}, access_secret={access_secret}")
        
        # Initialize Supabase client with the user's JWT
        try:
            supabase = get_supabase_client()
        except Exception as e:
            current_app.logger.error(f"Supabase client initialization failed: {e}")
            return jsonify({"error": "Authorization failed"}), 401

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
