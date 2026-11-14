from search.paging import page_count, paginate


def search(docs: list[str], query: str, page: int = 1, per_page: int = 10) -> dict:
    hits = [doc for doc in docs if query.lower() in doc.lower()]
    return {
        "results": paginate(hits, page, per_page),
        "pages": page_count(len(hits), per_page),
        "total": len(hits),
    }
