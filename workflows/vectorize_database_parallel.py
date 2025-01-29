import os
import sys
import json
sys.path.append(os.path.abspath(os.curdir))

import glob
from itertools import batched
from multiprocessing import Process, Queue
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

def embed_dataframe(df, model, separation_token):
    """Embed a dataframe using the model"""
    df["concat"] = df[title_key] + separation_token + df[abstract_key]
    df["concat"] = df["concat"].astype(str)
    df["embedding"] = df["concat"].progress_apply(model.encode, desc="embedding...", position=0)
    return df

def upsert_process(queue, index, pinecone_index_name):
    """Process that handles upserting to Pinecone"""

    checkpointing_path = "workflows/checkpoint.json"

    while True:
        df, pickle = queue.get()
        if df is None:  # Poison pill to stop the process
            break
            
        new_embeddings = [
            {
                "id": row["doi"],
                "values": row["embedding"].tolist(),
            }
            for _, row in df.dropna(subset=["doi"]).iterrows()
        ]    
        
        for batch in tqdm(batched(new_embeddings, up_batch_size), 
                         total=len(new_embeddings)//up_batch_size+1, 
                         desc="upserting...",
                         position=1,
                         leave=True,
                         file=sys.stdout):
            response = index.upsert(
                vectors=batch,
                namespace=pinecone_index_name,
                _check_type=True
            )

        checkpoint = json.load(open(checkpointing_path, "r"))
        checkpoint["pickle_files"].append(pickle)
        json.dump(checkpoint, open(checkpointing_path, "w"), indent=2)

if __name__ == "__main__":
    
    checkpoint = json.load(open(checkpointing_path, "r"))
    checkpoint["upload_batch_size"] = up_batch_size

    tqdm.write("Reading available data files...")
    pickle_files = sorted(glob.glob(os.path.join(data_path,"*.pkl")), reverse=False)
    
    tqdm.write("Removing checkpointed files")
    if checkpoint["pickle_files"]:
        if len(checkpoint["pickle_files"]) > 0:
            for file in checkpoint["pickle_files"]:
                pickle_files.remove(file)
    
    tqdm.write("Loading scientific embedding model...")
    model = SentenceTransformer(scientific_embedding_model, device=device)
    separation_token = model.tokenizer.sep_token
    tqdm.write(f"Using separation token: {separation_token}")
    tqdm.write("Initializing Pinecone client...")
    pc = Pinecone(api_key=app.config["PINECONE_KEY"])
    index = pc.Index(host=app.config["PINECONE_HOST"])
    tqdm.write("Pinecone client initialized successfully")
    
    # Create queue and start upsert process
    queue = Queue(maxsize=1)  # Only allow 1 item to ensure coordination    
    upsert_proc = Process(target=upsert_process, args=(queue, index, pinecone_index_name))
    upsert_proc.start()
    
    for pickle in pickle_files:

        checkpoint = json.load(open(checkpointing_path, "r"))
        checkpoint["being_processes"] = pickle
        json.dump(checkpoint, open(checkpointing_path, "w"), indent=2)

        tqdm.write(f"Reading data from {pickle}...")
        df = pd.read_pickle(pickle).drop_duplicates(subset=["doi"])
        tqdm.write(f"Loaded {len(df)} papers")
        
        # Embed the dataframe
        df_embedded = embed_dataframe(df, model, separation_token)
        
        # Send to upsert process and wait until it's taken
        queue.put((df_embedded, pickle))
        
    
    # Send poison pill and wait for upsert process to finish
    queue.put((None, None))
    upsert_proc.join()