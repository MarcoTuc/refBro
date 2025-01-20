import os
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv(".env")

class Config:

    # TEST_VAR = "TEST_VAR"
    # You can manually add variables here that don't have to be in .env

    def __init__(self):
        self._config = {}
        # Load environment variables into the config
        for key in os.environ:
            self._config[key] = os.getenv(key, "you-shall-not-pass")
            setattr(self, key, self._config[key])
            
    def __getitem__(self, key):
        return self._config[key]

config = Config()

# if __name__ == "__main__":
#     print(config.ZOTERO_CLIENT_KEY)
#     print(config["ZOTERO_CLIENT_KEY"])