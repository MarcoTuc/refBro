from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from main import multi_search, rank_results
from _openai import keywords_from_abstracts
from _openalex import get_papers_from_dois, reconstruct_abstract

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://localhost:3000", "https://refbro-ui.vercel.app"]  # Add any other frontend origins you need
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
        papers = get_papers_from_dois(dois)
        kwords = keywords_from_abstracts(papers)
        search = await multi_search(kwords)
        recomm = rank_results(search, top_k=20)
        recomm["abstract"] = recomm["abstract_inverted_index"].apply(reconstruct_abstract)
        top_re = recomm[[
            "title", 
            "abstract",
            "doi", 
            "authorships",
            "publication_year", 
            "primary_location",
            "score",
        ]].to_dict("records")
        return jsonify({"recommendations": top_re})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000, debug=True)