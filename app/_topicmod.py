import os
from typing import List, Tuple, Optional
import aiohttp
import asyncio
import pandas as pd 
import numpy as np 
from itertools import combinations
from app import app
import time



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

def rank_results(results: pd.DataFrame, top_k=20, exclude_dois: List[str] = None) -> pd.DataFrame: 
    npmimatrix, idx_t = get_npmimatrix(results, return_idx=True)
    results["score"] = 0.0
    for i, work in results.iterrows():
        topics = work["topics"]
        for ti, tj in combinations(topics, r=2):
            results.loc[i, "score"] += npmimatrix[idx_t[ti["id"]], idx_t[tj["id"]]]
    # Drop duplicates and exclude input DOIs
    results = results.drop_duplicates(subset=['doi'])
    if exclude_dois:
        results = results[~results['doi'].isin(exclude_dois)]
    results = results.sort_values(by="score", ascending=True)
    return results[:top_k]

