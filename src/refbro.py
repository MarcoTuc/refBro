import os
from flask import Flask, jsonify, request, render_template, current_app, redirect
from flask_cors import CORS
import tracemalloc
import traceback
from functools import wraps
from flask_mail import Mail, Message
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

from main import multi_search, rank_results
from _openai import keywords_from_abstracts
from _openalex import get_papers_from_dois, reconstruct_abstract, fetch_all_citation_networks
from _zotero import get_request_token, get_authorization_url, get_access_token
from _supabase import save_to_database

os.environ["PYTHONUNBUFFERED"] = "0"

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "https://refbro-ui.vercel.app",
    "https://refbro.onrender.com",
    "https://oshimascience.com",
    "https://www.oshimascience.com"
], 
allow_headers=["Content-Type"], 
methods=["GET", "POST", "OPTIONS"],  # Make sure GET is here
expose_headers=["Content-Type"],
)


# Add environment variable for memory tracking
ENABLE_MEMORY_TRACKING = os.getenv('DISABLE_MEMORY_TRACKING', 'false').lower() != 'true'

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)
oauth_token_store = {}


# Google Sheets configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
EMAILS_SPREADSHEET_ID = os.getenv('EMAILS_SPREADSHEET_ID')
FEEDBACK_SPREADSHEET_ID = os.getenv('FEEDBACK_SPREADSHEET_ID')

def get_google_sheets_service():
    try:
        # Check if we have the JSON directly in environment (production)
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_dict = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES)
        else:
            # Fallback to file (local development)
            credentials = service_account.Credentials.from_service_account_file(
                os.getenv('GOOGLE_CREDENTIALS_PATH', 'google-credentials.json'), 
                scopes=SCOPES)
            
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        current_app.logger.error(f"Error creating Google Sheets service: {str(e)}")
        return None

def append_to_sheet(spreadsheet_id, values):
    try:
        service = get_google_sheets_service()
        if not service:
            raise Exception("Could not initialize Google Sheets service")
            
        body = {
            'values': [values]
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        return result
    except Exception as e:
        current_app.logger.error(f"Error appending to sheet: {str(e)}")
        raise

def track_memory(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not ENABLE_MEMORY_TRACKING:
            return await func(*args, **kwargs)
            
        tracemalloc.start()
        try:
            result = await func(*args, **kwargs)
            
            # Memory tracking
            current, peak = tracemalloc.get_traced_memory()
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            current_app.logger.info(f"Memory usage for {func.__name__}:")
            current_app.logger.info(f"Current: {current / 10**6:.1f}MB")
            current_app.logger.info(f"Peak: {peak / 10**6:.1f}MB")
            current_app.logger.info("Top 3 memory blocks:")
            for stat in top_stats[:3]:
                current_app.logger.info(stat)
                
            return result
        finally:
            tracemalloc.stop()
    return wrapper

@app.before_request
def log_request_info():
    current_app.logger.info(f"Request Origin: {request.headers.get('Origin')}")
    current_app.logger.info(f"Request Method: {request.method}")
    current_app.logger.info(f"Request Headers: {dict(request.headers)}")

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, User-Id"
    response.headers["Access-Control-Expose-Headers"] = "Content-Type"
    current_app.logger.info(f"Final Response Headers: {response.headers}")
    return response


@app.route("/")
def home():
    return render_template("index.html")

def format_authors(authorships):
    if not authorships:  # Handle None or empty list
        return "Unknown Authors"
    
    authors = []
    for auth in authorships or []:  # Use empty list if None
        if isinstance(auth, dict) and 'author' in auth:  # Check if dict and has author
            author_data = auth['author']
            if isinstance(author_data, dict) and 'display_name' in author_data:
                authors.append(author_data['display_name'])
    
    if not authors:  # If no valid authors found
        return "Unknown Authors"
    if len(authors) > 3:
        return f"{authors[0]}, {authors[1]} et al."
    return ", ".join(authors)

def format_journal(primary_location):
    if not primary_location:  # Handle None
        return "Unknown Journal"
    
    if not isinstance(primary_location, dict):  # Check if dict
        return "Unknown Journal"
        
    source = primary_location.get('source', {})
    if not isinstance(source, dict):  # Check if source is dict
        return "Unknown Journal"
        
    return source.get('display_name', 'Unknown Journal')

@app.route("/queries", methods=["POST"])
@track_memory
async def get_recommendations():
    dois = request.json.get("queries", [])
    include_unranked = request.json.get("include_unranked", False)
    
    if not dois:
        return jsonify({"error": "No queries provided"}), 400
    try: 
        papers = await get_papers_from_dois(dois)
        if papers.empty:
            return jsonify({"error": "No valid papers found for the provided DOIs"}), 400

        kwords = keywords_from_abstracts(papers)
        if not kwords:
            return jsonify({"error": "Failed to generate keywords from papers"}), 500

        search = await multi_search(kwords, n_results=500, per_page=200)
        if search.empty:
            return jsonify({"error": "No search results found"}), 404
        
        unranked_dois = search['doi'].tolist() if include_unranked else None

        recomm = rank_results(search, top_k=20, exclude_dois=dois)
        
        current_app.logger.info("extracting abstract")
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        
        try:
            recommendations = recomm[[
                "title", 
                "abstract",
                "doi", 
                "authorships",
                "publication_year", 
                "primary_location",
                "score",
            ]].to_dict("records")
        except KeyError as e:
            current_app.logger.error(f"Missing required column in results: {e}")
            return jsonify({"error": f"Invalid data structure in results: missing {e}"}), 500

        formatted_recommendations = []
        for paper in recommendations:
            try:
                formatted_paper = {
                    'title': paper['title'],
                    'abstract': paper['abstract'],
                    'doi': paper['doi'],
                    'authors': format_authors(paper['authorships']),
                    'journal': format_journal(paper['primary_location']),
                    'year': paper['publication_year'],
                    'score': paper['score']
                }
                formatted_recommendations.append(formatted_paper)
            except Exception as e:
                current_app.logger.error(f"Error formatting paper: {str(e)}")
                continue

        if not formatted_recommendations:
            return jsonify({"error": "Failed to format any recommendations"}), 500

        current_app.logger.info(f"{len(formatted_recommendations)} Recommendations formatted correctly")
        response_data = {"recommendations": formatted_recommendations}
        if include_unranked:
            response_data["unranked_dois"] = unranked_dois
            
        return jsonify(response_data)
    except Exception as e:
        current_app.logger.error(f"Error in get_recommendations: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    
@app.route("/v1/colab", methods=["POST"])
@track_memory
async def colab():
    try:
        dois = request.json.get("queries", [])
        if not dois:
            return jsonify({"error": "No queries provided"}), 400
            
        search = await fetch_all_citation_networks(dois, total_max_papers=2000)
        
        if search is None:
            return jsonify({"error": "Citation network fetch returned None"}), 500
            
        include_unranked = request.json.get("include_unranked", False)
        unranked_dois = search['doi'].tolist() if include_unranked else None
        
        # Use existing ranking method
        recomm = rank_results(search, top_k=20, exclude_dois=dois)
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        
        try:
            recommendations = recomm[[
                "title", "abstract", "doi", "authorships",
                "publication_year", "primary_location", "score",
            ]].to_dict("records")
        except KeyError as e:
            return jsonify({"error": f"Invalid data structure in results: missing {e}"}), 500

        formatted_recommendations = []
        for paper in recommendations:
            try:
                formatted_paper = {
                    'title': paper['title'],
                    'abstract': paper['abstract'],
                    'doi': paper['doi'],
                    'authors': format_authors(paper['authorships']),
                    'journal': format_journal(paper['primary_location']),
                    'year': paper['publication_year'],
                    'score': paper['score']
                }
                formatted_recommendations.append(formatted_paper)
            except Exception as e:
                current_app.logger.error(f"Error formatting paper: {str(e)}")
                continue

        if not formatted_recommendations:
            return jsonify({"error": "Failed to format any recommendations"}), 500

        current_app.logger.info(f"{len(formatted_recommendations)} Recommendations formatted correctly")
        response_data = {"recommendations": formatted_recommendations}
        if include_unranked:
            response_data["unranked_dois"] = unranked_dois
            
        return jsonify(response_data)
        
    except Exception as e:
        current_app.logger.error(f"Error in colab endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "error": f"Failed to process citation networks: {str(e)}",
            "dois_attempted": dois,
            "traceback": traceback.format_exc()
        }), 500

@app.route("/send-results", methods=["POST"])
def send_results():
    try:
        data = request.json
        if not data or 'email' not in data or 'papers' not in data:
            return jsonify({"error": "Missing email or papers in request"}), 400
            
        recipient_email = data['email']
        papers = data['papers']
        
        if not isinstance(papers, list) or not papers:
            return jsonify({"error": "Papers must be a non-empty list"}), 400
            
        msg = Message(
            subject="Your RefBro Paper Results",
            recipients=[recipient_email],
            html=render_template('email/paper_results.html', papers=papers)
        )
        
        mail.send(msg)
        
        # Save to Google Sheet
        if EMAILS_SPREADSHEET_ID:
            try:
                timestamp = datetime.now().isoformat()
                row_data = [
                    timestamp,
                    recipient_email,
                    len(papers),
                    ', '.join(p.get('doi', '') for p in papers)
                ]
                append_to_sheet(EMAILS_SPREADSHEET_ID, row_data)
            except Exception as e:
                current_app.logger.error(f"Error saving to sheet: {str(e)}")
        
        return jsonify({"message": "Results sent successfully"}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/feedback", methods=["POST"])
def feedback():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No feedback data provided"}), 400
            
        rating = data.get('rating')
        feedback_text = data.get('feedback')
        user_email = data.get('email', 'Anonymous')
        
        # Create email content
        feedback_content = f"""
        New Feedback Received:
        
        Rating: {rating if rating else 'Not provided'}
        Email: {user_email}
        Feedback: {feedback_text if feedback_text else 'Not provided'}
        """
        
        msg = Message(
            subject="New RefBro Feedback Received",
            recipients=["ostmanncarla@gmail.com"],
            body=feedback_content
        )
        
        mail.send(msg)
        
        # Save to Google Sheet
        if FEEDBACK_SPREADSHEET_ID:
            try:
                timestamp = datetime.now().isoformat()
                row_data = [
                    timestamp,
                    rating or 'Not provided',
                    feedback_text or 'Not provided',
                    user_email
                ]
                append_to_sheet(FEEDBACK_SPREADSHEET_ID, row_data)
            except Exception as e:
                current_app.logger.error(f"Error saving to sheet: {str(e)}")
        
        return jsonify({"message": "Feedback received successfully"}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error processing feedback: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    
@app.route("/zotero/request-token", methods=["GET"])
def zotero_request_token():
    try:
        # Get the request token from Zotero
        request_token, request_token_secret = get_request_token()

        # Save the token and its secret in the global dictionary
        oauth_token_store[request_token] = request_token_secret
        current_app.logger.debug(f"Stored token: {request_token} with secret: {request_token_secret}")


        # Generate the Zotero authorization URL
        authorization_url = get_authorization_url(request_token)

        # Return the URL as JSON instead of a redirect
        return jsonify({"authorization_url": authorization_url}), 200
    except Exception as e:
        current_app.logger.error(f"Error in Zotero OAuth flow: {str(e)}")
        return jsonify({"error": "Failed to initiate Zotero OAuth"}), 500


@app.route("/zotero-success", methods=["POST"])
def zotero_callback():
    try:
        data = request.json

        oauth_token = data.get("oauthToken")
        oauth_verifier = data.get("oauthVerifier")
        user_id = data.get("userId")
        current_app.logger.info(f"oauth_token={oauth_token}, oauth_verifier={oauth_verifier}")

        if not oauth_token or not oauth_verifier:
            return jsonify({"error": "Missing oauth_token or oauth_verifier"}), 400

        if not user_id:
            current_app.logger.error(f"Missing user_id in request: {data}")
            return jsonify({"error": "User ID missing in request body"}), 400

        # Retrieve the secret for this token
        oauth_token_secret = oauth_token_store.pop(oauth_token, None)
        if not oauth_token_secret:
            return jsonify({"error": "Invalid or expired oauth_token"}), 400

        # Exchange the request token for an access token
        access_token, access_secret = get_access_token(oauth_token, oauth_verifier, oauth_token_secret)
        current_app.logger.info(f"Generated token: {access_token}, secret: {access_secret}")

        current_app.logger.info("Successfully retrieved Zotero access token and secret. Preparing to save.")
        # Log before saving to database
        current_app.logger.info(f"Saving to database: user_id={user_id}, access_token={access_token}")

        try:
            response = save_to_database(user_id, access_token, access_secret)
        except Exception as e:
            current_app.logger.error(f"Error in save_to_database: {e}")
            return jsonify({"error": str(e)}), 500


        # Log the response from Supabase
        current_app.logger.info(f"Supabase response: {response}")

        return jsonify({"message": "Zotero account successfully connected!"}), 200
    except Exception as e:
        current_app.logger.error(f"Error during Zotero callback: {str(e)}")
        return jsonify({"error": "Failed to connect Zotero"}), 500



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))  # Use PORT env var, default to 5000 for local dev
    app.run(host="0.0.0.0", port=port, debug=True)