import os
from typing import List, Tuple
import aiohttp
import asyncio
import pandas as pd 
import numpy as np 
from itertools import combinations
from flask import current_app

BASE_OPENALEX = "https://api.openalex.org"

def get_logger():
    try:
        from flask import current_app
        return current_app.logger
    except (ImportError, RuntimeError):
        import logging
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)

# TODO: move to openalex.py
async def fetch_papers_async(query: str, n_results=50):
    logger = get_logger()
    query = "%20".join(query.split(" "))
    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            per_page = 50
            pages = (n_results // per_page) + 1
            for page in range(1, pages + 1):
                url = f"{BASE_OPENALEX}/works?search={query}&per-page={per_page}&page={page}"
                tasks.append(session.get(url))
            responses = await asyncio.gather(*tasks)
            results = []
            for response in responses:
                data = await response.json()
                results.extend(data['results'])
        return pd.DataFrame(results)
    except Exception as e:
        # current_app.logger.info(f"Problem with fetching papers: {str(e)}")
        logger.info(f"Problem with fetching papers: {str(e)}")
        return pd.DataFrame()

# TODO: move to openalex.py
async def multi_search(queries: List[str], n_results=50) -> pd.DataFrame:
    logger = get_logger()
    try:
        # Create tasks for all queries at once
        tasks = [fetch_papers_async(query, n_results=n_results) for query in queries]
        # Execute all queries in parallel
        results = await asyncio.gather(*tasks)
        return pd.concat(results, ignore_index=True)
    except Exception as e: 
        # current_app.logger.info(f"Problem with multi_search: {str(e)}")
        logger.info(f"Problem with multi_search: {str(e)}")
        return pd.DataFrame()

def get_topics_set(results: pd.DataFrame):
    topics = results["topics"]
    topic_ids = []
    for topic in topics:
        for t in topic: 
            topic_ids.append(t["id"])
    return set(topic_ids)

def topic_idx_association(topics: set) -> List[dict]: 
    idx_t = {t:i for i,t in enumerate(topics)}
    # t_idx = {i:t for t,i in idx_t.items()}
    return idx_t #, t_idx

def get_npmimatrix(results: pd.DataFrame, return_idx=True) -> np.ndarray:
    topics = get_topics_set(results)
    idx_t = topic_idx_association(topics)
    # create a matrix to index through topics 
    mutualmatrix = np.zeros([len(topics), len(topics)])
    for _, res in results.iterrows():
        # get p(x)
        for t in res["topics"]:
            id = idx_t[t["id"]]
            mutualmatrix[id, id] = mutualmatrix[id, id] + 1
        # get p(x,y)
        for ti, tj in combinations(res["topics"], r=2):
            idi, idj = idx_t[ti["id"]], idx_t[tj["id"]]
            mutualmatrix[idi, idj] = mutualmatrix[idi, idj] + 1
            mutualmatrix[idj, idi] = mutualmatrix[idj, idi] + 1
    probmatrix = mutualmatrix / len(mutualmatrix)
    npmimatrix = np.zeros_like(probmatrix)
    for i,j in combinations(range(probmatrix.shape[0]), r=2):
        if probmatrix[i,j] > 0:
            npmimatrix[i,j] = np.log2(probmatrix[i,j]/(probmatrix[i,i]*probmatrix[j,j]))/(-np.log2(probmatrix[i,j]))
            npmimatrix[j,i] = npmimatrix[i,j]
    if return_idx: 
        return npmimatrix, idx_t
    else: 
        return npmimatrix

def rank_results(results: pd.DataFrame, top_k=20) -> pd.DataFrame: 
    npmimatrix, idx_t = get_npmimatrix(results, return_idx=True)
    results["score"] = 0.0
    for i, work in results.iterrows():
        topics = work["topics"]
        for ti, tj in combinations(topics, r=2):
            # Fix: use ti and tj for the two different indices
            results.loc[i, "score"] += npmimatrix[idx_t[ti["id"]], idx_t[tj["id"]]]
    results = results.sort_values(by="score", ascending=True)
    return results[:top_k]

