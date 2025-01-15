from supabase import create_client

# Supabase URL and Key
SUPABASE_URL = "https://wyrflssqbzxklzeowjjn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind5cmZsc3NxYnp4a2x6ZW93ampuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzY4ODEzNTQsImV4cCI6MjA1MjQ1NzM1NH0.ffQli-xxRUPFsNO8nk2wndpY-ShatAeCmAfD2uHRZcA"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_to_database(user_id, access_token, access_secret):
    """
    Save Zotero credentials to the Supabase profiles table.
    """
    try:
        response = supabase.table("profiles").update({
            "zotero_access_token": access_token,
            "zotero_access_secret": access_secret,
        }).eq("id", user_id).execute()

        if response.status_code != 200:
            raise Exception(f"Error updating database: {response.json()}")

        return response.data
    except Exception as e:
        print(f"Error saving to database: {e}")
        raise
