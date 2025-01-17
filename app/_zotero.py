import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
from requests_oauthlib import OAuth1
from app import app


# Our Zotero API keys
client_key = app.config["ZOTERO_CLIENT_KEY"]
client_secret = app.config["ZOTERO_CLIENT_SECRET"]
callback_url = app.config["ZOTERO_CALLBACK_URL"] # maybe this one can be public?

# Zotero API endpoints
request_token_endpoint = 'https://www.zotero.org/oauth/request'
zotero_authorize_endpoint = 'https://www.zotero.org/oauth/authorize'
access_token_endpoint = 'https://www.zotero.org/oauth/access'

def generate_oauth_signature(base_string, signing_key):
    """Generates an HMAC-SHA1 signature."""
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    return base64.b64encode(hashed.digest()).decode()

def get_request_token():
    """Requests an OAuth request token from Zotero."""
    # OAuth parameters
    oauth_params = {
        "oauth_consumer_key": client_key,
        "oauth_nonce": str(int(time.time() * 1000)),  # Unique nonce
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_callback": callback_url,
        "oauth_version": "1.0",
    }

    # Create the base string for signing
    base_string = "POST&" + urllib.parse.quote(request_token_endpoint, "") + "&" + urllib.parse.quote(
        "&".join(f"{urllib.parse.quote(k, '')}={urllib.parse.quote(v, '')}" for k, v in sorted(oauth_params.items())), "")

    # Create the signing key
    signing_key = f"{client_secret}&"

    # Generate the signature
    oauth_params["oauth_signature"] = generate_oauth_signature(base_string, signing_key)

    # Make the POST request to Zotero
    headers = {"Authorization": "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(v)}"' for k, v in oauth_params.items())}

    response = requests.post(request_token_endpoint, headers=headers)
    if response.status_code == 200:
        # Parse the response to get the request token
        token_data = dict(urllib.parse.parse_qsl(response.text))
        return token_data.get("oauth_token"), token_data.get("oauth_token_secret")
    else:
        raise Exception(f"Failed to get request token: {response.text}")

def get_authorization_url(request_token):
    """Generates the Zotero authorization URL."""
    return f"{zotero_authorize_endpoint}?oauth_token={request_token}"

def get_access_token(oauth_token, oauth_verifier, oauth_token_secret):
    """Exchanges the request token and verifier for an access token."""
    oauth = OAuth1(
        client_key,
        client_secret,
        resource_owner_key=oauth_token,
        resource_owner_secret=oauth_token_secret,  # Include the token secret
        verifier=oauth_verifier
    )

    response = requests.post(access_token_endpoint, auth=oauth)

    if response.status_code != 200:
        app.logger.error(f"Failed to get access token from Zotero. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to get access token from Zotero")

    app.logger.info(f"Zotero response: {response.text}")

    # Parse the access token and secret from the response
    data = dict(item.split("=") for item in response.text.split("&"))
    access_token = data.get("oauth_token")
    access_secret = data.get("oauth_token_secret")
    zotero_user_id = data.get("userID")

    if not access_token or not access_secret:
        raise Exception("Invalid access token response from Zotero")

    return access_token, access_secret, zotero_user_id


def get_zotero_library(email, zotero_access_token, zotero_access_secret, zotero_user_id):
    """Fetches the entire Zotero library data for a given user, meaning all items."""
    
    # Zotero API URL to get the user's items
    zotero_api_url = f"https://api.zotero.org/users/{zotero_user_id}/items?key={zotero_access_secret}"

    # Make the API request to Zotero
    response = requests.get(zotero_api_url, headers={
        "Authorization": f"Bearer {zotero_access_token}"  # Add the OAuth access token in the header
    })

    if response.status_code != 200:
        # If the response is not successful, log and raise an exception
        app.logger.error(f"Failed to retrieve Zotero data. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to retrieve Zotero library data.")

    # Parse the JSON response from Zotero
    zotero_data = response.json()

    # Optionally, log or process the retrieved data
    app.logger.info(f"Retrieved Zotero data for {email}: {zotero_data}")

    # Return the Zotero data (or modify it if necessary)
    return zotero_data

def get_zotero_collections(zotero_access_token, zotero_access_secret, zotero_user_id):
    """Fetches the Zotero collections for a given user."""

    api_url = f"https://api.zotero.org/users/{zotero_user_id}/collections?limit=200?key={zotero_access_secret}"

    try: 
        response = requests.get(api_url, headers={
            "Authorization": f"Bearer {zotero_access_token}"  # Add the OAuth access token in the header
        })
    except Exception as e:
        app.logger.error(f"Failed to retrieve Zotero collections. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to retrieve Zotero collections.")
    
    if response.status_code != 200:
        app.logger.error(f"Failed to retrieve Zotero collections. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to retrieve Zotero collections.")
    
    zotero_collections = response.json()
    response = format_zotero_collections(zotero_collections)
    return response

def get_zotero_collection_items(collection_key, zotero_access_token, zotero_access_secret, zotero_user_id):
    """Fetches the Zotero collection items for a given user."""
    
    api_url = f"https://api.zotero.org/users/{zotero_user_id}/collections/{collection_key}/items?key={zotero_access_secret}"

    try: 
        response = requests.get(api_url, headers={
            "Authorization": f"Bearer {zotero_access_token}"  # Add the OAuth access token in the header
        })
    except Exception as e:
        app.logger.error(f"Failed to retrieve Zotero collection items. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to retrieve Zotero collection items.")
    
    if response.status_code != 200:
        app.logger.error(f"Failed to retrieve Zotero collection items. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Failed to retrieve Zotero collection items.")
    
    zotero_collection_items = response.json()
    return zotero_collection_items

def parse_doi_from_zotero_item(item):
    """Parses the DOI from a Zotero item."""
    # Using the get method to safely access nested dictionaries and avoid KeyError
    doi = item.get("data", {}).get("DOI")
    return doi

def format_zotero_collections(collections):
    """Formats Zotero collections into a nested tree structure.
    
    Args:
        collections (list): Raw Zotero collections response
        
    Returns:
        list: List of top-level collections with nested children
    """
    # First, create a mapping of collection key to formatted collection
    collection_map = {}
    
    # Initialize formatted collections
    for collection in collections:
        collection_map[collection['key']] = {
            'key': collection['key'],
            'name': collection['data']['name'],  # Including name for easier debugging
            'numCollections': collection['meta'].get('numCollections', 0),
            'numItems': collection['meta'].get('numItems', 0),
            'link': f"/collections/{collection['key']}",  # Adjust link format as needed
            'children': []
        }

    # Build the tree structure
    root_collections = []
    for collection in collections:
        formatted_collection = collection_map[collection['key']]
        
        # If collection has a parent, add it as a child
        if 'parentCollection' in collection['data'] and collection['data']['parentCollection']:
            parent_key = collection['data']['parentCollection']
            if parent_key in collection_map:
                collection_map[parent_key]['children'].append(formatted_collection)
        else:
            # If no parent, it's a root collection
            root_collections.append(formatted_collection)

    # Recursively calculate total items and sort children
    def calculate_total_items_and_sort(collection):
        total = collection['numItems']
        for child in collection['children']:
            total += calculate_total_items_and_sort(child)
        collection['numItems'] = total
        
        # Only move 0-item collections to bottom, preserve original order otherwise
        collection['children'].sort(key=lambda x: x['numItems'] == 0)
        return total

    # Calculate totals and sort root collections
    for collection in root_collections:
        calculate_total_items_and_sort(collection)
    
    # Only move 0-item collections to bottom for root collections
    root_collections.sort(key=lambda x: x['numItems'] == 0)

    return root_collections

    