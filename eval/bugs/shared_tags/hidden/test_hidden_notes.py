from notes.service import create_note, tag_note


def test_many_notes_independent():
    notes = [create_note(str(i)) for i in range(3)]
    tag_note(notes[0], "a")
    tag_note(notes[1], "b")
    assert [n.tags for n in notes] == [["a"], ["b"], []]


def test_passed_list_still_used():
    tags = ["k"]
    assert create_note("x", tags=tags).tags == ["k"]
