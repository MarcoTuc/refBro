import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
from requests_oauthlib import OAuth1


# Our Zotero API keys
client_key = "962a6a380e931fd4a2d0"
client_secret = "a3506e647b0927d9ecfa"
callback_url = "https://oshimascience.com/zotero-success"

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

def get_access_token(oauth_token, oauth_verifier):
    oauth = OAuth1(client_key, client_secret, resource_owner_key=oauth_token, verifier=oauth_verifier)

    response = requests.post(access_token_endpoint, auth=oauth)

    if response.status_code != 200:
        raise Exception("Failed to get access token from Zotero")

    # Parse the access token and secret from the response
    data = dict(item.split("=") for item in response.text.split("&"))
    access_token = data.get("oauth_token")
    access_secret = data.get("oauth_token_secret")

    if not access_token or not access_secret:
        raise Exception("Invalid access token response from Zotero")

    return access_token, access_secret