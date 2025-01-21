import os
import sys
sys.path.append(os.path.abspath(os.curdir))

import glob
from tqdm import tqdm
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from app import app 

tqdm.pandas()

#### manually configurable parameters
eb_batch_size = 1000 # how many papers to embed per batch
up_batch_size = eb_batch_size # how many papers to upload per batch

data_path = "data/publishers/nature_filtered"

device = app.config["DEVICE"]
scientific_embedding_model = app.config["SCI_EMB_MODEL"]
pinecone_index_name = "nature_filtered_200K"


if __name__ == "__main__":
    
    print("Reading available data files...")
    pickle_files = glob.glob(os.path.join(data_path,"*.pkl"))
    print("Loading scientific embedding model...")
    model = SentenceTransformer(scientific_embedding_model, device=device)
    separation_token = model.tokenizer.sep_token
    print(f"Using separation token: {separation_token}")
    print("Initializing Pinecone client...")
    pc = Pinecone(api_key=app.config["PINECONE_KEY"])
    index = pc.Index(host=app.config["PINECONE_HOST"])
    print("Pinecone client initialized successfully")

    for pickle in tqdm(pickle_files, position=0, leave=True):
        
        print(f"Reading data from {pickle}...")
        df = pd.read_pickle(pickle)
        print(f"Loaded {len(df)} papers")
        print("Concatenating titles and abstracts...")
        df["concat"] = df["title"] + separation_token + df["abstract"]
        # Create a progress bar for chunks
        chunk_iterator = tqdm(np.array_split(df, len(df) // eb_batch_size), desc="Processing chunks", position=1, leave=False)
        
        for chunk in chunk_iterator:
            chunk_iterator.set_description(f"Processing chunk of {len(chunk)} papers")
        
            # Create embeddings with a separate progress bar
            embeddings = []
            for _, row in tqdm(chunk.iterrows(), total=len(chunk), desc="Embedding papers", position=2, leave=False):
                embedding = model.encode(row["concat"])
                embeddings.append(embedding)
            
            chunk["embedding"] = embeddings
            
            # Create batch for upload
            new_embeddings = [
                {
                    "id": row["doi"],
                    "values": row["embedding"].tolist(),
                }
                for _, row in chunk.iterrows()
            ]    
            # Upload with progress indication
            chunk_iterator.set_description(f"Uploading {len(new_embeddings)} embeddings")
            index._upsert_batch(
                new_embeddings, 
                namespace=pinecone_index_name, 
                _check_type=True
            )
