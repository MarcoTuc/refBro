import os
import pandas as pd

from pydantic import BaseModel
from openai import OpenAI

from prompting.systemprompts import *


client_oai = OpenAI(api_key=os.getenv("OPENAI_REFBRO_KEY"))


class SearchList(BaseModel):
    queries: list[str]


def format_abstracts_for_oai_userprompt(papers: pd.DataFrame) -> str:
    papers = papers[papers["abstract"] != "MISSING_ABSTRACT"]
    user_prompt = "\n------\n".join(
        f"title:: {pap['title']}\nabstract:: {pap['abstract']}"
        for _, pap in papers.iterrows()
        ) + "\n------\n"
    return user_prompt

def keywords_from_abstracts(papers: pd.DataFrame):
    user_prompt = format_abstracts_for_oai_userprompt(papers)
    completion = client_oai.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": f"{system_prompt_1}"
            },
            {
                "role": "user", 
                "content": f"{user_prompt}"
            },
        ],
        response_format=SearchList,
    )
    return completion.choices[0].message.parsed.queries