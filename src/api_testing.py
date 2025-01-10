import asyncio
from main import multi_search, rank_results
from _openai import keywords_from_abstracts
from _openalex import get_papers_from_dois


async def queries_test():
    dois = [
        "https://doi.org/10.48550/arXiv.2411.19865",
        "https://doi.org/10.48550/arXiv.2009.13207",
        "https://doi.org/10.1007/s11047-013-9380-y"
    ]

    import time
    start = time.time()
    papers = get_papers_from_dois(dois)
    print(f"OPENALEX:       Getting papers took {time.time() - start:.2f} seconds")

    start = time.time()
    kwords = keywords_from_abstracts(papers)
    print(f"OPENAI:         Generating keywords took {time.time() - start:.2f} seconds")

    start = time.time()
    search = await multi_search(kwords)
    print(f"OPENALEX:       Searching papers took {time.time() - start:.2f} seconds")

    start = time.time()
    recomm = rank_results(search)
    print(f"MATRIX STUFF:   Ranking results took {time.time() - start:.2f} seconds")
    return recomm

if __name__ == "__main__":
    recomm = asyncio.run(queries_test())
    return_values = [
        "title", 
        "abstract",
        "doi", 
        "authorships"
        "publication_year", 
        "score"
        ]
    print(recomm)



