from flask import Flask

app = Flask("refBro")

queries = [
    "dna kinetics",
    "graph theory",
    "dynamical systems",
    "monte carlo simulations",
    "origins of life",
    "stochastic processes",
    "polymer physics"
]

@app.route("/results", methods=["GET"])
async def get_recommendations(queries):

if __name__ == '__main__':
    app.run(debug=True)