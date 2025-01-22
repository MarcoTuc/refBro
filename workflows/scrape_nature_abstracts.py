import os
import sys
sys.path.append(os.path.abspath(os.curdir))

import glob
import pandas as pd
from tqdm import tqdm
from utils.scraping import Nature
import nest_asyncio
import asyncio
nest_asyncio.apply()


original_dir = "/home/marco/Desktop/Coding/Oshima/refBro-main/data/publishers/Nature_Portfolio"
save_dir = "/home/marco/Desktop/Coding/Oshima/refBro-main/data/publishers/nature_scraped"
os.makedirs(save_dir, exist_ok=True)
files = glob.glob(f"{original_dir}/*.pkl")
files.remove("/home/marco/Desktop/Coding/Oshima/refBro-main/data/publishers/Nature_Portfolio/slice_1.pkl") #already processed

async def process_files():
    bar = tqdm(files, position=0)
    for path in bar: 
        # Read the pickle file and append DOIs to urls list
        temp_df = pd.read_pickle(path)
        name_file = os.path.basename(path)
        bar.set_description(f"processing file {name_file}")

        tqdm.write(f"Extracting abstracts...")
        temp_df = temp_df.dropna(subset=["doi"])
        abstracts = await Nature().scrape_abstracts(temp_df['doi'].tolist())
        temp_df["scraped_abstracts"] = abstracts
        temp_df = temp_df.dropna(subset=["scraped_abstracts"])
        tqdm.write(f"saving {len(temp_df)} newly scraped abstracts")
        save_name = name_file
        save_path = os.path.join(save_dir, save_name)
        temp_df.to_pickle(save_path)

asyncio.run(process_files())