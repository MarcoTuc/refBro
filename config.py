import os
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv(".env")

class Config:    
    # Torch device
    DEVICE = "cuda:0"
    # Scientific Citation Network Embedding Model huggingface path
    SCI_EMB_MODEL = "sentence-transformers/allenai-specter"
    # OpenAlex fields to keep
    OPENALEX_PAPER_FIELDS = ",".join(
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
    OPENALEX_DOI_MINIMAL_FIELDS = ",".join(
        [
            "cited_by_api_url",
            "referenced_works"
        ]
    )

    def __init__(self):
        for key in os.environ:
            setattr(self, key, os.getenv(key, "you-shall-not-pass"))

