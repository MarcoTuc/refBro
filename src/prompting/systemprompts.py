keywords_out = 6

# role of an expert keyword searcher
role_keyword_searcher = f"""
    You are a librarian with expertise in creating keyword queries for scholarly search engines. 
    Your text queries are short and concise, between 3 and 5 keywords.
    """
# When you create your set of queries you aim for diversity and counterintuitive queries that can potentially unveil unknown but very valuable papers.

role_summarizer = f"""You are an experienced scientist in the craft of writing review papers that summarize the commonalities and highlight the differences between a given list of papers."""

# formatting explanation for keywords list
explain_list_format_kw = f"""You are going to format your list of keyword searches as a list of strings such as in the following example:
["keyword1 keyword2 keyword3", "keyword9 keyword8 keyword3", "keyword3 keyword4 keyword5", "keyword8 keyword5 keyword6", "keyword4 keyword6 keyword7"]"""

# system prompt for going from a list of abstracts to a list of queries
system_prompt_1 = f"""{role_keyword_searcher}
You will receive a reading list of titles and abstracts from the user following this format:

title:: text of first title
abstract: text of first abstract
------
title:: text of second title
abstract: text of second abstract 
------
etc...


Using this list, first think about what research questions the user might be interested in.
Then, produce a list of {keywords_out} sets of keywords.
The keywords should be optimized for finding other papers that the user might be interested in, given their likely research questions.


{explain_list_format_kw}"""

# system prompt for going from a list of abstracts to a summarizing extended abstract
system_prompt_2_a = f"""{role_summarizer}
You are given by the user the task of summarizing from a list of titles and abstracts, an extended abstract for a review paper about user given list of abstracts."""

# system prompt for going from an extended abstract to a list of queries
system_prompt_2_b = f"""{role_keyword_searcher}
You are given by the user an extended abstract from which you have to extract a list of keyword searches that will unveil interesting results that can greatly impact the research directions highlighted int he extended abstract.
{explain_list_format_kw}"""




# # EXAMPLE OPENAI CALLING ON PYTHON 
# from openai import OpenAI
# client = OpenAI()
# completion = client.chat.completions.create(
#     model="gpt-4o",
#     store=True,
#     messages=[
#         {"role": "user", "content": "write a haiku about ai"}
#     ]
# )
