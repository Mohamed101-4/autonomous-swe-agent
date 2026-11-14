import pytest

from app.auth import login, register
from app.storage import UserStore


@pytest.fixture
def store():
    s = UserStore()
    register(s, {"email": "alice@example.com", "password": "secret123"})
    return s


def test_login_success(store):
    result = login(store, {"email": "  Alice@Example.com ", "password": "secret123"})
    assert result.ok
    assert result.email == "alice@example.com"


def test_login_wrong_password(store):
    result = login(store, {"email": "alice@example.com", "password": "nope"})
    assert not result.ok
    assert result.error == "invalid credentials"


def test_login_unknown_user(store):
    result = login(store, {"email": "bob@example.com", "password": "secret123"})
    assert not result.ok


def test_login_missing_email(store):
    result = login(store, {"password": "secret123"})
    assert not result.ok
    assert result.error == "email is required"


def test_login_none_email(store):
    result = login(store, {"email": None, "password": "secret123"})
    assert not result.ok
    assert result.error == "email is required"
