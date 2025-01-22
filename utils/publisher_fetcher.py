import os
import sys
import aiohttp
import pandas as pd
from tqdm import tqdm
from app import app
pub_base_path = "/home/marco/Desktop/Coding/Oshima/refBro-main/data/publishers"



###############################################################################################
filter_source = "https://api.openalex.org/publishers/P4310319908" # Nature Portfolio
save_name = "NEW_PUBLISHER_NAME"
save_path = os.path.join(pub_base_path, save_name)
save_every = 20000



###############################################################################################
os.makedirs(save_path, exist_ok=True)

BASE_OPENALEX = "https://api.openalex.org"
OPENALEX_EMAIL = "marco.tuccio95@gmail.com"
paper_fields = ",".join(
        [
            "title",
            "abstract_inverted_index",
            "doi",
            "authorships",
            "publication_year",
            "primary_location",
            "topics"
        ]
    )

async def main():

    res_all = []
    cut_every = save_every
    per_page = 200
    _slice = 0
    async with aiohttp.ClientSession() as session:
        url = f"{BASE_OPENALEX}/works"
        cursor = "*"
        params = {
                'filter': f"primary_location.source.publisher_lineage:{filter_source}",
                'select': paper_fields,
                'per-page': per_page,
                'cursor': cursor,
                # 'page': 1,
                'mailto': OPENALEX_EMAIL
            }
        # get the first page
        async with session.get(url, params=params) as response:
            results = await response.json()
        res_all.extend(results["results"])
        tot_results = results["meta"]["count"]
        print(f"There's a total of {tot_results} to be retrieved")
        tot_pages = tot_results//per_page + (1 if tot_results % per_page else 0)
        print(f"going to retrieve {tot_pages} pages")
        page = 1
        while params["cursor"]:
            page += 1
            # print(results)
            params["cursor"] = results["meta"]["next_cursor"]
            # params["page"] = page
            async with session.get(url, params=params) as response:
                results = await response.json()
                res_all.extend(results["results"])
                print(f"retrieved {(page+1)}/{tot_pages} pages ({(page+1)*200} results)", end="\r")
            if (page*per_page) % cut_every == 0:
                _slice += 1
                pd.DataFrame(res_all).to_pickle(os.path.join(save_path, f"slice_{_slice}.pkl"))
                res_all = []
            elif res_all != []:
                _slice += 1
                pd.DataFrame(res_all).to_pickle(os.path.join(save_path, f"slice_{_slice}.pkl"))
                res_all = []
