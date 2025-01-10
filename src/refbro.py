import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

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
            "https://oshimascience.com/",
            ]  # Add any other frontend origins you need
    }
})

@app.route("/")
def home():
    return render_template("index.html")

def format_authors(authorships):
    authors = []
    for auth in authorships:
        if 'author' in auth and 'display_name' in auth['author']:
            authors.append(auth['author']['display_name'])
    if len(authors) > 3:
        return f"{authors[0]}, {authors[1]} et al."
    return ", ".join(authors)

def format_journal(primary_location):
    if not primary_location or 'source' not in primary_location:
        return "Unknown Journal"
    source = primary_location['source']
    return source.get('display_name', 'Unknown Journal')

@app.route("/queries", methods=["POST"])
async def get_recommendations():
    dois = request.json.get("queries", [])
    if not dois:
        return jsonify({"error": "No queries provided"}), 400
    try: 
        # convert dois into dataframe of papers
        app.logger.info("retrieving papers from dois")
        papers = get_papers_from_dois(dois)
        if papers.empty:
            return jsonify({"error": "No valid papers found for the provided DOIs"}), 400

        app.logger.info("extracting keywords with oai")
        kwords = keywords_from_abstracts(papers)
        if not kwords:
            return jsonify({"error": "Failed to generate keywords from papers"}), 500

        app.logger.info("keywords search on openalex")
        search = await multi_search(kwords)
        if search.empty:
            return jsonify({"error": "No search results found"}), 404

        app.logger.info("ranking the results")
        recomm = rank_results(search, top_k=20)
        
        app.logger.info("extracting abstract")
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        
        app.logger.info("retrieving papers from dois")
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
            app.logger.error(f"Missing required column in results: {e}")
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
                app.logger.error(f"Error formatting paper: {str(e)}")
                continue

        if not formatted_recommendations:
            return jsonify({"error": "Failed to format any recommendations"}), 500

        app.logger.info(f"{len(formatted_recommendations)} Recommendations formatted correctly")
        return jsonify({"recommendations": formatted_recommendations})
    except Exception as e:
        app.logger.error(f"Error in get_recommendations: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000, debug=True)