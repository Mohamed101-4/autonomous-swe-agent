from app.validators import is_strong_password, is_valid_email, normalize_email


def test_normalize_email():
    assert normalize_email("  Bob@Example.COM ") == "bob@example.com"


def test_is_valid_email():
    assert is_valid_email("a@b.co")
    assert not is_valid_email("not-an-email")


def test_password_rules():
    assert is_strong_password("abcdefg1")
    assert not is_strong_password("short1")
