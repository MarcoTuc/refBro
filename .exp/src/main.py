import json
import requests
import pandas as pd

BASE_OPENALEX = "https://api.openalex.org"

def search_topics(topic_name, get_ids=False):
    url = f"{BASE_OPENALEX}/topics"
    params = {
        "filter": f"default.search:{topic_name}"
    }
    response = requests.get(url, params=params)
    return response.json()

def get_works_from_topics(search_topic_results):
    ids_list = [r["id"].split("/")[-1] for r in search_topic_results["results"]]
    for id in ids_list:
        pass


def reconstruct_abstract(index: dict) -> str:
    # max_position_max = max([positions for positions in index.values()])[0]
    max_position_sum = sum([len(position)+1 for position in index.values()])
    # abstract_array = (max(max_position_max, max_position_sum)+20)*[None]
    abstract_array = max_position_sum*[None]
    for word, positions in index.items():
        for position in positions:
            abstract_array[position] = word
    abstract_array = [i for i in abstract_array if i is not None]
    abstract_string = ' '.join(abstract_array)
    abstract_string = abstract_string.replace('^abstract\s+', '')
    return abstract_string


if __name__ == "__main__":
    print(search_topics("Cognitive Psychology"))