from notes.models import Note


def create_note(title: str, body: str = "", tags: list[str] = []) -> Note:
    note = Note(title=title, body=body, tags=tags)
    return note


def tag_note(note: Note, tag: str) -> Note:
    if tag not in note.tags:
        note.tags.append(tag)
    return note
