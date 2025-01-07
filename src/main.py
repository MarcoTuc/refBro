from typing import List, Tuple
import aiohttp
import asyncio
import pandas as pd 
import numpy as np 
from itertools import combinations


BASE_OPENALEX = "https://api.openalex.org"

async def fetch_papers_async(query: str, n_results=1000):
    query = "%20".join(query.split(" "))
    async with aiohttp.ClientSession() as session:
        tasks = []
        per_page = 200
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

async def multi_search(queries: List[str], n_results=400) -> pd.DataFrame:
    """ Returns a dataframe with all retrieved papers for all queries """
    results = {}
    for query in queries: 
        results[query] = await fetch_papers_async(query, n_results=n_results)
    return pd.concat(list(results.values()), ignore_index=True)

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

def rank_results(results, top_k=20): 
    npmimatrix, idx_t = get_npmimatrix(results, return_idx=True)
    results["score"] = 0
    for i, work in results.iterrows():
        topics = work["topics"]
        for ti, tj in combinations(topics, r=2):
            # Fix: use ti and tj for the two different indices
            results.loc[i, "score"] += npmimatrix[idx_t[ti["id"]], idx_t[tj["id"]]]
    results = results.sort_values(by="score", ascending=True)
    return results[:top_k]

