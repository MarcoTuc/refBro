import json
import requests
import pandas as pd

BASE_OPENALEX = "https://api.openalex.org"

def search_papers(query, max_results=1000):
    query = "%20".join(query.split(" "))
    all_results = []
    page = 1
    per_page = 200  # OpenAlex allows up to 200 results per page
    
    while True:
        url = f"{BASE_OPENALEX}/works?search={query}&per_page={per_page}&page={page}"
        response = requests.get(url)
        data = response.json()
        
        if not data.get("results"):
            break
            
        all_results.extend(data["results"])
        
        # Stop if we've reached max_results or no more results available
        if len(all_results) >= max_results or len(data["results"]) < per_page:
            break
            
        page += 1
    
    return all_results

if __name__ == "__main__":
    
    query = "dna kinetics"
    results = search_papers(query)
    # print(json.dumps(results["results"], indent=2))
    print(len(results))