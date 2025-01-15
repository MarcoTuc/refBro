from app import app
from flask_cors import CORS

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

if __name__ == "__main__":
    app.run(debug=True)