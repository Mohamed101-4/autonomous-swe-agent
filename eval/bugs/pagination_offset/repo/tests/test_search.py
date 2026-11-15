from search.engine import search

DOCS = [f"item {i}" for i in range(25)]


def test_total_and_pages():
    out = search(DOCS, "item")
    assert out["total"] == 25 and out["pages"] == 3


def test_first_page_starts_at_first_item():
    assert search(DOCS, "item", page=1, per_page=10)["results"][0] == "item 0"
