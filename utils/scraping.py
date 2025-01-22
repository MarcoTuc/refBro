import aiohttp
import asyncio
from bs4 import BeautifulSoup
from tqdm import tqdm
from itertools import batched

class Nature:

    """ Provide a list of doi urls and get back the scraped abstracts from Nature """

    tags = ['Abs1-content', 'Abs2-content']

    
    async def get_abstract(self, url, session):
        try:
            async with session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                try:
                    abstract = soup.select(f"div#{self.tags[0]}")[0].text.strip() #to use with parser lxml
                    # abstract = soup.find(id=self.abstract_tags[0]).text.strip() #to use with parser html.parser
                except AttributeError:
                    try:
                        abstract = soup.select(f"div#{self.tags[1]}")[0].text.strip() #to use with parser lxml
                        # abstract = soup.find(id=self.abstract_tags[1]).text.strip() #to use with parser html.parser
                    except AttributeError as e:
                        abstract = None
                return abstract
        except Exception as e:
            pass

    async def scrape_abstracts(self, urls):
        abstracts = []
        batch_size = 200  # Increased batch size
        connector = aiohttp.TCPConnector(limit=100)  # Increase connection limit
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            bar = tqdm(batched(urls, batch_size), total=len(urls)//batch_size, leave=True, position=1)
            for batch in bar:
                tasks = [self.get_abstract(url, session) for url in batch]
                new_abs = await asyncio.gather(*tasks)
                bar.set_description(f"found {len([n for n in new_abs if n is not None])} new abstracts")
                abstracts.extend(new_abs)
        
        return abstracts