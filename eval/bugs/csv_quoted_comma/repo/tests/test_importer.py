from contacts.directory import load_directory

SIMPLE = "name,email\nBob,bob@example.com\n"
QUOTED = 'name,email\n"Smith, Jane",jane@example.com\n'


def test_simple():
    assert load_directory(SIMPLE) == {"Bob": "bob@example.com"}


def test_quoted_comma():
    assert load_directory(QUOTED) == {"Smith, Jane": "jane@example.com"}
