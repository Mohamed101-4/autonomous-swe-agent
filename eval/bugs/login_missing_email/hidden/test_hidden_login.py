from app.auth import login, register
from app.storage import UserStore


def test_empty_string_email():
    store = UserStore()
    register(store, {"email": "a@b.co", "password": "secret123"})
    result = login(store, {"email": "", "password": "secret123"})
    assert not result.ok and result.error == "email is required"


def test_normal_login_still_works():
    store = UserStore()
    register(store, {"email": "a@b.co", "password": "secret123"})
    assert login(store, {"email": "A@B.co", "password": "secret123"}).ok
