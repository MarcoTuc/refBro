import requests
from flask import current_app
import pandas as pd

BASE_OPENALEX = "https://api.openalex.org"
OPENALEX_EMAIL = "ostmanncarla@gmail.com"


def get_papers_from_dois(dois_list: list[str]) -> pd.DataFrame:
    current_app.logger.info(f"Fetching {len(dois_list)} papers from OpenAlex")
    results = []
    try:
        for doi in dois_list:
            try:
                paper = get_paper_from_doi(doi)
                if paper:
                    results.append(paper)
            except Exception as e:
                current_app.logger.error(f"Failed to fetch DOI {doi}: {str(e)}")
                continue
        
        if not results:
            raise Exception("None of the provided DOIs were found in OpenAlex")
            
        current_app.logger.info(f"Successfully fetched {len(results)} papers")
        return pd.DataFrame(results)
    except Exception as e: 
        current_app.logger.error(f"Problem with fetching DOIs: {str(e)}")
        raise

def get_paper_from_doi(doi: str) -> list[dict]:
    base_doi = "https://doi.org"
    # Clean the DOI to handle various input formats
    clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi_url = f"{base_doi}/{clean_doi}"
    url = f"{BASE_OPENALEX}/works/{doi_url}?mailto={OPENALEX_EMAIL}"
    
    try:
        response = requests.get(url)
        if response.status_code == 404:
            current_app.logger.warning(f"DOI not found in OpenAlex: {doi_url}. Full URL: {url}")
            return None
        
        response.raise_for_status()
        data = response.json()
        
        if "abstract_inverted_index" not in data:
            current_app.logger.warning(f"No abstract found for DOI: {doi}")
            data["abstract"] = "MISSING_ABSTRACT"
        else:
            data["abstract"] = reconstruct_abstract(data["abstract_inverted_index"])
        return data
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Request failed for DOI {doi}: {str(e)}")
        raise
    except ValueError as e:
        current_app.logger.error(f"Invalid JSON response for DOI {doi}: {str(e)}")
        current_app.logger.debug(f"Response content: {response.text}")
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error processing DOI {doi}: {str(e)}")
        raise

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
