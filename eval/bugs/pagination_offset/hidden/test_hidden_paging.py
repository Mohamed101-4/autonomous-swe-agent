from search.paging import paginate


def test_pages():
    items = list(range(7))
    assert paginate(items, 1, 3) == [0, 1, 2]
    assert paginate(items, 3, 3) == [6]
    assert paginate(items, 4, 3) == []
