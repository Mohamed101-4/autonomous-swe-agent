def paginate(items: list, page: int, per_page: int = 10) -> list:
    """Return the items on a 1-indexed page."""
    if page < 1 or per_page < 1:
        raise ValueError("page and per_page must be >= 1")
    start = page * per_page
    return items[start : start + per_page]


def page_count(total: int, per_page: int = 10) -> int:
    return (total + per_page - 1) // per_page
