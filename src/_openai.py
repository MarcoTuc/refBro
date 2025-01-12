import os
from dotenv import load_dotenv
import pandas as pd

from pydantic import BaseModel
from openai import OpenAI
from flask import current_app
from prompting.systemprompts import *

# Load environment variables from .env file
load_dotenv()

client_oai = OpenAI(api_key=os.environ.get("OPENAI_REFBRO_KEY"))


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
    try:
        current_app.logger.info("Sending request to OpenAI API")
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
        current_app.logger.info(f"Generated {len(completion.choices[0].message.parsed.queries)} search queries")
        return completion.choices[0].message.parsed.queries
    except Exception as e: 
        current_app.logger.error(f"OpenAI API error: {str(e)}")
        raise