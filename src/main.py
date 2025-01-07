from typing import List

import aiohttp
import asyncio

import pandas as pd 

BASE_OPENALEX = "https://api.openalex.org"

# Async version
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