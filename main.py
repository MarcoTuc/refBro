def embed_papers(model, papers):
    sep = model.tokenizer.sep_token
    title_abstract_concat = [d["title"] + sep + d["abstract"] for d in papers]
    return model.encode(title_abstract_concat)