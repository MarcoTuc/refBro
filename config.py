import os 
import dotenv

env_vars = dotenv.dotenv_values()

class Config:
    def __init__(self):
        self._config = {}
        for key in env_vars:
            value = os.environ.get(key) or "you-shall-not-pass"
            setattr(self, key, value)
            self._config[key] = value
            
    def __getitem__(self, key):
        return self._config[key]
    
config = Config()

if __name__ == "__main__":
    config = Config()
    print(config.ZOTERO_KEY)
    print(config["ZOTERO_KEY"])