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
            "https://refbro.onrender.com/"]  # Add any other frontend origins you need
    }
})

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/queries", methods=["POST"])
async def get_recommendations():
    dois = request.json.get("queries", []) # this will eventually be handled by the backend and we will recieve a list of DOIs from the frontend
    if not dois:
        return jsonify({"error": "No queries provided"}), 400
    try: 
        # convert dois into dataframe of papers
        print("retrieving papers from dois")
        papers = get_papers_from_dois(dois)
        print("extracting keywords with oai")
        kwords = keywords_from_abstracts(papers)
        print("keywords search on openalex")
        search = await multi_search(kwords)
        print("ranking the results")
        recomm = rank_results(search, top_k=20)
        print("extracting abstract")
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        print("retrieving papers from dois")
        recommendations = recomm[[
            "title", 
            "abstract",
            "doi", 
            "authorships",
            "publication_year", 
            "primary_location",
            "score",
        ]].to_dict("records")
        print(f"{len(recommendations)} Recommendations retrieved correctly:")
        print("Sending recommendations to the frontend")
        return jsonify({"recommendations": recommendations})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000, debug=True)