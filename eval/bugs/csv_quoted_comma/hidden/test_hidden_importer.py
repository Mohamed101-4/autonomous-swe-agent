from contacts.importer import parse_csv


def test_escaped_quotes_and_blank_lines():
    text = 'name,note\n"A","say ""hi"""\n\nB,plain\n'
    assert parse_csv(text) == [{"name": "A", "note": 'say "hi"'}, {"name": "B", "note": "plain"}]
