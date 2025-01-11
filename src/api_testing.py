import asyncio
import json
import logging
from refbro import app  # Import the Flask app from refbro.py

def test_queries():
    # Configure logging to show in terminal
    app.logger.setLevel(logging.INFO)  # Set Flask logger level
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    
    # Test data
    dois = [
        "10.48550/arXiv.2411.19865",
        "10.48550/arXiv.2009.13207",
        "10.1007/s11047-013-9380-y"
    ]
    
    # Create application and request context
    with app.app_context(), app.test_client() as client:
        response = client.post('/queries', 
                            json={
                                'queries': dois,
                                'include_unranked': False
                                },
                            content_type='application/json')
        
        print("\nAPI Response:")
        print(json.dumps(response.json, indent=2))
        
        return response.json

if __name__ == "__main__":
    recommendations = test_queries()



