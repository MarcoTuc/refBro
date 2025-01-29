import os
import sys
import json
sys.path.append(os.path.abspath(os.curdir))

import glob
from itertools import batched
from tqdm import tqdm
tqdm.pandas()

import pandas as pd
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

from app import app 

##################################################################
###### MANUAL CONFIGURATION OF PARAMETERS

eb_batch_size = 500 # how many papers to embed per batch
up_batch_size = 800 # how many papers to upload per batch

data_path = "data/publishers/nature_scraped"
title_key = "title"
abstract_key = "scraped_abstracts"
checkpointing_path = "workflows/checkpoint.json"

device = app.config["DEVICE"]
scientific_embedding_model = app.config["SCI_EMB_MODEL"]
pinecone_index_name = "nature_scraped"


##################################################################
###### Vectorize + upsert script

if __name__ == "__main__":
    
    checkpoint = json.load(open(checkpointing_path, "r"))
    checkpoint["upload_batch_size"] = up_batch_size

    print("Reading available data files...")
    pickle_files = glob.glob(os.path.join(data_path,"*.pkl"))
    
    print("Removing checkpointed files")
    if checkpoint["pickle_files"]:
        if len(checkpoint["pickle_files"]) > 0:
            for file in checkpoint["pickle_files"]:
                pickle_files.remove(file)
    
    print("Loading scientific embedding model...")
    model = SentenceTransformer(scientific_embedding_model, device=device)
    separation_token = model.tokenizer.sep_token
    print(f"Using separation token: {separation_token}")
    print("Initializing Pinecone client...")
    pc = Pinecone(api_key=app.config["PINECONE_KEY"])
    index = pc.Index(host=app.config["PINECONE_HOST"])
    print("Pinecone client initialized successfully")
    
    totdf = pd.DataFrame()
    
    for pickle in pickle_files:
        
        checkpoint["being_processes"] = pickle
        json.dump(checkpoint, open(checkpointing_path, "w"), indent=2)

        print(f"Reading data from {pickle}...")
        df = pd.read_pickle(pickle).drop_duplicates(subset=["doi"])
        print(f"Loaded {len(df)} papers")
        print("Concatenating titles and abstracts...")
        df["concat"] = df[title_key] + separation_token + df[abstract_key]
        print("Embedding papers")
        df["embedding"] = df["concat"].progress_apply(model.encode, desc="embedding...")    
        # Create batch for upload
        totdf = pd.concat([totdf, df])

        new_embeddings = [
            {
                "id": row["doi"],
                "values": row["embedding"].tolist(),
            }
            for _, row in totdf.dropna(subset=["doi"]).iterrows()
        ]    
        
        for batch in tqdm(batched(new_embeddings, up_batch_size), total=len(new_embeddings)//up_batch_size+1, desc="upserting..."):

            response = index.upsert(
                    vectors=batch, 
                    namespace=pinecone_index_name, 
                    _check_type=True
                )
            
            tqdm.write(str(response))
        
        checkpoint["pickle_files"].append(pickle)
        json.dump(checkpoint, open(checkpointing_path, "w"), indent=2)