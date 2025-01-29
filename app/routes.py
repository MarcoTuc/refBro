import os
import traceback
from datetime import datetime
import requests

from flask import jsonify, request, render_template, url_for
from flask_mail import Message
import jwt
from app import app, mail
from app.logging_utils import track_memory
from app._topicmod import rank_results
from app._openai import keywords_from_abstracts
from app._zotero import (
    get_request_token, 
    get_authorization_url, 
    get_access_token, 
    get_zotero_library, 
    get_zotero_collections,
    get_zotero_collection_items,
    parse_doi_from_zotero_item
    )
from app._supabase import supabase_test_insert, get_zotero_credentials
from app._google import append_to_sheet, EMAILS_SPREADSHEET_ID, FEEDBACK_SPREADSHEET_ID
from app._openalex import (
    multi_search,
    get_papers_from_dois,
    reconstruct_abstract, 
    fetch_all_citation_networks, 
    format_recommendations
    )

oauth_token_store = {}

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/queries", methods=["POST"])
@track_memory
async def queries():
    try:
        dois = request.json.get("queries", [])        
        if not dois:
            return jsonify({"error": "No queries provided"}), 400
        
        include_unranked = request.json.get("include_unranked", False)
        
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

        recomm = rank_results(search, top_k=100, exclude_dois=dois)
        
        app.logger.info("extracting abstract")
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        
        try:
            formatted_recommendations = format_recommendations(recomm)
        except KeyError as e:
            return jsonify({"error": f"Invalid data structure in results: missing {e}"}), 500
        if not formatted_recommendations:
            return jsonify({"error": "Failed to format any recommendations"}), 500

        app.logger.info(f"{len(formatted_recommendations)} Recommendations formatted correctly")
        response_data = {"recommendations": formatted_recommendations}
        if include_unranked:
            response_data["unranked_dois"] = unranked_dois
            
        return jsonify(response_data)
    
    except Exception as e:
        app.logger.error(f"Error in queries endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "error": f"Failed to process citation networks: {str(e)}",
            "dois_attempted": dois,
            "traceback": traceback.format_exc()
        }), 500
    

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
        recomm = rank_results(search, top_k=100, exclude_dois=dois)
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        
        try:
            formatted_recommendations = format_recommendations(recomm)
        except KeyError as e:
            return jsonify({"error": f"Invalid data structure in results: missing {e}"}), 500
        if not formatted_recommendations:
            return jsonify({"error": "Failed to format any recommendations"}), 500

        app.logger.info(f"{len(formatted_recommendations)} Recommendations formatted correctly")
        response_data = {"recommendations": formatted_recommendations}
        if include_unranked:
            response_data["unranked_dois"] = unranked_dois
            
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in colab endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "error": f"Failed to process citation networks: {str(e)}",
            "dois_attempted": dois,
            "traceback": traceback.format_exc()
        }), 500
    
@app.route("/v1/mixed", methods=["GET", "POST"])
def mixed():
    headers = {
        "Content-Type": "application/json"
    }
    
    name_1 = "colab"
    name_2 = "queries"

    # Get the JSON data once
    json_data = request.get_json()
    if not json_data:
        return jsonify({"error": "No JSON data provided"}), 400

    try:
        # Make both requests with the same JSON data
        url_1 = url_for(name_1, _external=True)
        response_1 = requests.post(url_1, json=json_data, headers=headers)
        response_1.raise_for_status()
        
        url_2 = url_for(name_2, _external=True)
        response_2 = requests.post(url_2, json=json_data, headers=headers)
        response_2.raise_for_status()
        
        return jsonify({
            f"{name_1}_response": response_1.json(),
            f"{name_2}_response": response_2.json()
        })
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error in mixed endpoint: {str(e)}")
        return jsonify({
            "error": "Failed to get recommendations",
            "details": str(e)
        }), 500

@app.route("/zotero/collections/recommendations", methods=["POST"])
def zotero_collection_recommendations():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        collection_keys = data.get('collection_keys')
        email = data.get('email')
        endpoint = data.get("endpoint")
        
        app.logger.info(f"endpoint is {endpoint}")
        
        if not collection_keys or not isinstance(collection_keys, list):
            return jsonify({"error": "collection_keys must be a non-empty array"}), 400
        
        # Retrieve Zotero credentials
        zotero_access_token, zotero_access_secret, zotero_user_id = get_zotero_credentials(email)
        
        # Collect DOIs from all collections
        all_dois = []
        for collection_key in collection_keys:
            collection_items = get_zotero_collection_items(
                collection_key, 
                zotero_access_token, 
                zotero_access_secret, 
                zotero_user_id
            )
            collection_dois = [parse_doi_from_zotero_item(item) for item in collection_items]
            all_dois.extend(collection_dois)
        
        # Remove duplicates while preserving order
        unique_dois = list(dict.fromkeys(all_dois))
        
        # Prepare the payload for the endpoint
        payload = {
            "queries": unique_dois,
            "include_unranked": data.get("include_unranked", False)
        }
        
        # Make request to the specified endpoint
        endpoint_url = url_for(endpoint, _external=True)
        response = requests.post(
            endpoint_url, 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        app.logger.error(f"Error calling endpoint: {str(e)}")
        return jsonify({
            "error": "Failed to get recommendations",
            "details": str(e)
        }), 500

@app.route("/zotero-data", methods=["POST"])
def zotero_library():
    app.logger.info(f"Request Headers: {request.headers}")
    app.logger.info(f"Request Body: {request.data}")
    data = request.json
    email = data.get('email')
    zotero_access_token, zotero_access_secret, zotero_user_id = get_zotero_credentials(email)
    zotero_data = get_zotero_library(email, zotero_access_token, zotero_access_secret, zotero_user_id)

    return jsonify({"message": "Zotero data retrieved successfully", "zotero_data": zotero_data}), 200
    
@app.route("/zotero/collections", methods=["POST"])
def zotero_collections():
    data = request.json
    email = data.get('email')
    zotero_access_token, zotero_access_secret, zotero_user_id = get_zotero_credentials(email)
    zotero_collections = get_zotero_collections(zotero_access_token, zotero_access_secret, zotero_user_id)
    return jsonify({"message": "Zotero collections retrieved successfully", "zotero_collections": zotero_collections}), 200


########################################################################################################################
#################### USER-AUTH RELATED ROUTES

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
                app.logger.error(f"Error saving to sheet: {str(e)}")
        
        return jsonify({"message": "Results sent successfully"}), 200
        
    except Exception as e:
        app.logger.error(f"Error sending email: {str(e)}", exc_info=True)
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
                app.logger.error(f"Error saving to sheet: {str(e)}")
        
        return jsonify({"message": "Feedback received successfully"}), 200
        
    except Exception as e:
        app.logger.error(f"Error processing feedback: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    

@app.route("/zotero/request-token", methods=["GET"])
def zotero_request_token():
    try:
        # Get the request token from Zotero
        request_token, request_token_secret = get_request_token()

        # Save the token and its secret in the global dictionary
        oauth_token_store[request_token] = request_token_secret
        app.logger.debug(f"Stored token: {request_token} with secret: {request_token_secret}")


        # Generate the Zotero authorization URL
        authorization_url = get_authorization_url(request_token)

        # Return the URL as JSON instead of a redirect
        return jsonify({"authorization_url": authorization_url}), 200
    except Exception as e:
        app.logger.error(f"Error in Zotero OAuth flow: {str(e)}")
        return jsonify({"error": "Failed to initiate Zotero OAuth"}), 500


@app.route("/zotero-success", methods=["POST"])
def zotero_callback():
    try:
        data = request.json

        oauth_token = data.get("oauthToken")
        oauth_verifier = data.get("oauthVerifier")
        email = data.get("email")
        app.logger.info(f"oauth_token={oauth_token}, oauth_verifier={oauth_verifier}")

        if not oauth_token or not oauth_verifier:
            return jsonify({"error": "Missing oauth_token or oauth_verifier"}), 400

        if not email:
            app.logger.error(f"Missing email in request: {data}")
            return jsonify({"error": "Email missing in request body"}), 400

        # Retrieve the secret for this token
        oauth_token_secret = oauth_token_store.pop(oauth_token, None)
        if not oauth_token_secret:
            return jsonify({"error": "Invalid or expired oauth_token"}), 400

        # Exchange the request token for an access token
        access_token, access_secret, zotero_user_id = get_access_token(oauth_token, oauth_verifier, oauth_token_secret)
        app.logger.info(f"Generated token: {access_token}, secret: {access_secret}")

        app.logger.info("Successfully retrieved Zotero access token and secret. Preparing to save.")
        # Log before saving to database
        app.logger.info(f"Saving to database: email={email}, access_token={access_token}, user_id={zotero_user_id}")

        try:
            supabase_test_insert(email, access_token, access_secret, zotero_user_id)
        except Exception as e:
            app.logger.error(f"Error in supabase_test_insert: {e}")
            return jsonify({"error": str(e)}), 500

        return jsonify({"message": "Zotero account successfully connected!"}), 200
    except Exception as e:
        app.logger.error(f"Error during Zotero callback: {str(e)}")
        return jsonify({"error": "Failed to connect Zotero"}), 500
    
@app.route("/v1/profile", methods=["POST", "OPTIONS"])
def profile():
    logger = app.logger
    
    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    logger.info("Starting profile endpoint processing")
    
    # Log request data
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request body: {request.get_json()}")
    
    try:
        data = request.json
        email = data.get('email')
        logger.info(f"Attempting to get Zotero credentials for email: {email}")
        
        zotero_access_token, zotero_access_secret, zotero_user_id = get_zotero_credentials(email)
        logger.info(f"Successfully retrieved Zotero credentials: {zotero_access_token}, {zotero_access_secret}, {zotero_user_id}")
        
        return jsonify({"message": "Zotero data retrieved successfully", "zotero_user_id": zotero_user_id}), 200
    except Exception as e:
        logger.error(f"Error in profile endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    
@app.route("/supabase-test", methods=["POST"])
def supabase_test():
    app.logger.info(f"Request Headers: {request.headers}")
    app.logger.info(f"Request Body: {request.data}")

    data = request.json
    email = data.get('email')
    zotero_access_token = data.get('zotero_access_token')
    zotero_access_secret = data.get('zotero_access_secret')
    zotero_user_id = data.get('zotero_user_id')

    if not email or not zotero_access_token or not zotero_access_secret:
        app.logger.error("Missing email or zotero_access_token or zotero_access_secret in request body")
        return jsonify({"error": "Missing email or zotero_access_token or zotero_access_secret"}), 400

    try: 
        app.logger.info(f"calling supabase_test_insert")
        supabase_test_insert(email, zotero_access_token, zotero_access_secret, zotero_user_id)
        return jsonify({"message": "Supabase test insert successful"}), 200
    except Exception as e:
        app.logger.error(f"Error in Supabase test: {str(e)}")
        return jsonify({"error": str(e)}), 400