from notes.service import create_note, tag_note


def test_create_with_tags():
    note = create_note("a", tags=["x"])
    assert note.tags == ["x"]


def test_tags_are_not_shared():
    first = create_note("first")
    second = create_note("second")
    tag_note(first, "urgent")
    assert second.tags == []
