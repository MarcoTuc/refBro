import os
from flask import Flask, jsonify, request, render_template, current_app
from flask_cors import CORS
import tracemalloc

from main import multi_search, rank_results
from _openai import keywords_from_abstracts
from _openalex import get_papers_from_dois, reconstruct_abstract

os.environ["PYTHONUNBUFFERED"] = "0"

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173", 
            "http://localhost:3000", 
            "https://refbro-ui.vercel.app",
            "https://refbro.onrender.com/", 
            "https://oshimascience.com",
            ]  # Add any other frontend origins you need
    }
})

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
async def get_recommendations():
    # Start memory tracking
    tracemalloc.start()
    
    dois = request.json.get("queries", [])
    include_unranked = request.json.get("include_unranked", False)
    
    if not dois:
        return jsonify({"error": "No queries provided"}), 400
    try: 
        papers = get_papers_from_dois(dois)
        if papers.empty:
            return jsonify({"error": "No valid papers found for the provided DOIs"}), 400

        kwords = keywords_from_abstracts(papers)
        if not kwords:
            return jsonify({"error": "Failed to generate keywords from papers"}), 500

        search = await multi_search(kwords, n_results=500, per_page=200)
        if search.empty:
            return jsonify({"error": "No search results found"}), 404
        
        unranked_dois = search['doi'].tolist() if include_unranked else None

        recomm = rank_results(search, top_k=20)
        
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
            
        # Take a snapshot after the main operations
        current, peak = tracemalloc.get_traced_memory()
        
        # Get detailed memory statistics
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        # Log memory usage
        current_app.logger.info(f"Current memory usage: {current / 10**6:.1f}MB")
        current_app.logger.info(f"Peak memory usage: {peak / 10**6:.1f}MB")
        
        # Log top 3 memory blocks
        current_app.logger.info("Top 3 memory blocks:")
        for stat in top_stats[:3]:
            current_app.logger.info(stat)
            
        # Stop tracking at the end
        tracemalloc.stop()
        
        return jsonify(response_data)
    except Exception as e:
        tracemalloc.stop()  # Make sure to stop tracking even if there's an error
        current_app.logger.error(f"Error in get_recommendations: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))  # Use PORT env var, default to 5000 for local dev
    app.run(host="0.0.0.0", port=port, debug=True)