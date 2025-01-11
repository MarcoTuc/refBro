import aiohttp
import asyncio
from flask import current_app
import pandas as pd
from typing import Dict, Set, List, Optional

BASE_OPENALEX = "https://api.openalex.org"
OPENALEX_EMAIL = "ostmanncarla@gmail.com"
DOI_MINIMAL_FIELDS = "cited_by_api_url,referenced_works"  # Only network info
PAPER_FIELDS = "title,abstract_inverted_index,doi,authorships,publication_year,primary_location,topics"

async def get_paper_network_info(doi: str) -> Optional[dict]:
    """Get only citation network information for a paper"""
    base_doi = "https://doi.org"
    clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi_url = f"{base_doi}/{clean_doi}"
    url = f"{BASE_OPENALEX}/works/{doi_url}?select={DOI_MINIMAL_FIELDS}&mailto={OPENALEX_EMAIL}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 404:
                    current_app.logger.warning(f"DOI not found in OpenAlex: {doi_url}")
                    return None
                
                response.raise_for_status()
                return await response.json()
                
        except Exception as e:
            current_app.logger.error(f"Error fetching network info for DOI {doi}: {str(e)}")
            raise

async def fetch_papers_batch(openalex_ids: List[str]) -> List[dict]:
    """Fetch paper metadata for a batch of OpenAlex IDs"""
    if not openalex_ids:
        return []
        
    ids_filter = "|".join(openalex_ids)
    url = f"{BASE_OPENALEX}/works?filter=openalex_id:{ids_filter}&select={PAPER_FIELDS}&mailto={OPENALEX_EMAIL}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                results = data.get('results', [])
                
                for paper in results:
                    # Ensure topics is a list
                    if 'topics' not in paper:
                        paper['topics'] = []
                    
                    if "abstract_inverted_index" not in paper:
                        paper["abstract"] = "MISSING_ABSTRACT"
                    else:
                        paper["abstract"] = reconstruct_abstract(paper["abstract_inverted_index"])
                        
                return results
                
        except Exception as e:
            current_app.logger.error(f"Error fetching batch of papers: {str(e)}")
            raise

async def fetch_cited_by_papers(cited_by_url: str, max_results: int = 500) -> List[dict]:
    """Fetch papers that cite the given paper"""
    results = []
    page = 1
    per_page = 200  # OpenAlex max
    
    async with aiohttp.ClientSession() as session:
        while len(results) < max_results:
            paginated_url = f"{cited_by_url}&page={page}&per-page={per_page}"
            try:
                async with session.get(paginated_url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if not data.get('results'):
                        break
                        
                    for paper in data['results']:
                        # Ensure topics is a list
                        if 'topics' not in paper:
                            paper['topics'] = []
                            
                        if "abstract_inverted_index" not in paper:
                            paper["abstract"] = "MISSING_ABSTRACT"
                        else:
                            paper["abstract"] = reconstruct_abstract(paper["abstract_inverted_index"])
                    
                    results.extend(data['results'])
                    
                    if len(data['results']) < per_page:  # Last page
                        break
                        
                    page += 1
                    
            except Exception as e:
                current_app.logger.error(f"Error fetching cited_by papers: {str(e)}")
                break
                
            await asyncio.sleep(0.1)  # Rate limiting
            
    return results[:max_results]

async def fetch_citation_network(doi: str, max_papers: int) -> pd.DataFrame:
    """Fetch citation network for a single paper"""
    current_app.logger.info(f"Starting fetch_citation_network for DOI: {doi}")
    paper_data = {}
    
    try:
        # Get initial paper network info
        network_info = await get_paper_network_info(doi)
        if not network_info:
            raise ValueError(f"Could not fetch network info for paper: {doi}")
        
        # Get cited_by papers
        cited_by_url = network_info.get('cited_by_api_url')
        if cited_by_url:
            current_app.logger.info(f"Fetching cited_by papers for DOI: {doi}")
            cited_by_papers = await fetch_cited_by_papers(cited_by_url, max_results=max_papers//2)
            for paper in cited_by_papers:
                if paper.get('doi'):
                    paper_data[paper['doi']] = paper
        
        # Get referenced works
        referenced_works = network_info.get('referenced_works', [])
        if referenced_works:
            current_app.logger.info(f"Fetching {len(referenced_works)} referenced works for DOI: {doi}")
            # Process in batches of 50
            batch_size = 50
            for i in range(0, len(referenced_works), batch_size):
                batch = referenced_works[i:i + batch_size]
                referenced_papers = await fetch_papers_batch(batch)
                for paper in referenced_papers:
                    if paper.get('doi'):
                        paper_data[paper['doi']] = paper
                
                if len(paper_data) >= max_papers:
                    break
        
        if not paper_data:
            raise ValueError(f"No papers found in citation network for DOI: {doi}")
            
        return pd.DataFrame(list(paper_data.values()))
        
    except Exception as e:
        current_app.logger.error(f"Error in fetch_citation_network for DOI {doi}: {str(e)}")
        raise

async def fetch_all_citation_networks(dois: List[str], total_max_papers: int = 2000) -> pd.DataFrame:
    """Fetch two layers of citation networks for multiple papers"""
    papers_per_layer = total_max_papers // 2  # Split limit between layers
    
    try:
        # Layer 1: Full citation networks (cited_by + references) for input DOIs
        papers_per_doi = papers_per_layer // len(dois)
        tasks = [fetch_citation_network(doi, papers_per_doi) for doi in dois]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process Layer 1 results
        layer1_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                current_app.logger.error(f"Failed to fetch network for DOI {dois[i]}: {str(result)}")
            elif isinstance(result, pd.DataFrame) and not result.empty:
                layer1_results.append(result)
        
        if not layer1_results:
            raise Exception(f"Failed to fetch citation networks for all {len(dois)} DOIs")
            
        # Combine Layer 1 results and remove duplicates
        layer1_df = pd.concat(layer1_results, ignore_index=True).drop_duplicates(subset=['doi'])
        
        # Layer 2: Fetch only cited_by papers for Layer 1 results
        papers_per_source = papers_per_layer // len(layer1_df)
        layer2_tasks = []
        
        for _, paper in layer1_df.iterrows():
            if 'cited_by_api_url' in paper:
                task = fetch_cited_by_papers(paper['cited_by_api_url'], max_results=papers_per_source)
                layer2_tasks.append(task)
        
        if layer2_tasks:
            layer2_results = await asyncio.gather(*layer2_tasks, return_exceptions=True)
            valid_layer2_results = []
            
            for result in layer2_results:
                if isinstance(result, list) and result:  # Skip exceptions and empty results
                    valid_layer2_results.extend(result)
            
            if valid_layer2_results:
                layer2_df = pd.DataFrame(valid_layer2_results).drop_duplicates(subset=['doi'])
                # Combine both layers, removing duplicates
                final_df = pd.concat([layer1_df, layer2_df], ignore_index=True).drop_duplicates(subset=['doi'])
            else:
                final_df = layer1_df
        else:
            final_df = layer1_df
        
        current_app.logger.info(f"Final combined DataFrame has {len(final_df)} papers")
        return final_df
        
    except Exception as e:
        current_app.logger.error(f"Error in fetch_all_citation_networks: {str(e)}")
        raise

def reconstruct_abstract(index: dict) -> str:
    """Reconstruct abstract from inverted index"""
    if isinstance(index, type(None)):
        return "MISSING_ABSTRACT"
    
    max_position_sum = sum([len(position)+1 for position in index.values()]) + 500 # + 500 for safety 
    abstract_array = max_position_sum*[None]
    for word, positions in index.items():
        for position in positions:
            abstract_array[position] = word
    abstract_array = [i for i in abstract_array if i is not None]
    abstract_string = ' '.join(abstract_array)
    abstract_string = abstract_string.replace(r'^abstract\s+', '')
    return abstract_string

async def get_papers_from_dois(dois: List[str]) -> pd.DataFrame:
    """Get paper metadata for a list of DOIs"""
    paper_data = []
    
    async with aiohttp.ClientSession() as session:
        for doi in dois:
            base_doi = "https://doi.org"
            clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
            doi_url = f"{base_doi}/{clean_doi}"
            url = f"{BASE_OPENALEX}/works/{doi_url}?select={PAPER_FIELDS}&mailto={OPENALEX_EMAIL}"
            
            try:
                async with session.get(url) as response:
                    if response.status == 404:
                        current_app.logger.warning(f"DOI not found in OpenAlex: {doi_url}")
                        continue
                        
                    response.raise_for_status()
                    paper = await response.json()
                    
                    if "abstract_inverted_index" not in paper:
                        paper["abstract"] = "MISSING_ABSTRACT"
                    else:
                        paper["abstract"] = reconstruct_abstract(paper["abstract_inverted_index"])
                        
                    paper_data.append(paper)
                    
            except Exception as e:
                current_app.logger.error(f"Error fetching paper for DOI {doi}: {str(e)}")
                continue
                
            await asyncio.sleep(0.1)  # Rate limiting
    
    if not paper_data:
        return pd.DataFrame()
        
    return pd.DataFrame(paper_data)
