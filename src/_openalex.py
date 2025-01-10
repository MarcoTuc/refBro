import requests
from flask import current_app
import pandas as pd

BASE_OPENALEX = "https://api.openalex.org"

def get_papers_from_dois(dois_list: list[str]) -> pd.DataFrame:
    results = []
    try:
        for doi in dois_list:
            results.append(get_paper_from_doi(doi))
        return pd.DataFrame(results)
    except Exception as e: 
        current_app.logger.info(f"problem with fetching DOIs: {str(e)}")

def get_paper_from_doi(doi: str) -> list[dict]:
    base_doi = "https://doi.org"
    if doi[:15] != base_doi: doi = f"{base_doi}/{doi}"
    url = f"{BASE_OPENALEX}/works/{doi}"
    response = requests.get(url).json()
    response["abstract"] = reconstruct_abstract(response["abstract_inverted_index"])
    return response

def reconstruct_abstract(index: dict) -> str:
    if isinstance(index, type(None)): return "MISSING_ABSTRACT" # TODO: expand with scraping methods TODO: decide if to return None instead
    max_position_sum = sum([len(position)+1 for position in index.values()]) + 500 # + 500 for safety 
    abstract_array = max_position_sum*[None]
    for word, positions in index.items():
        for position in positions:
            abstract_array[position] = word
    abstract_array = [i for i in abstract_array if i is not None]
    abstract_string = ' '.join(abstract_array)
    abstract_string = abstract_string.replace(r'^abstract\s+', '')
    return abstract_string
