from flask import Flask, jsonify, request, render_template
from main import multi_search, rank_results
import asyncio

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/queries", methods=["POST"])
async def get_recommendations():
    queries = request.json.get("queries", []) # this will eventually be handled by the backend and we will recieve a list of DOIs from the frontend
    if not queries:
        return jsonify({"error": "No queries provided"}), 400
    try:
        results_df = await multi_search(queries)
        top_recommendations = rank_results(results_df)
        recommendations = top_recommendations[["title", "doi", "publication_year", "score"]].to_dict("records")
        return jsonify({"recommendations": recommendations})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000, debug=True)