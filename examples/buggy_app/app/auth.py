"""Login and registration."""

from dataclasses import dataclass

from app.storage import UserStore, hash_password
from app.validators import is_strong_password, is_valid_email, normalize_email


@dataclass
class LoginResult:
    ok: bool
    error: str | None = None
    email: str | None = None


def register(store: UserStore, data: dict) -> LoginResult:
    email = data.get("email")
    password = data.get("password") or ""
    if not email:
        return LoginResult(ok=False, error="email is required")
    email = normalize_email(email)
    if not is_valid_email(email):
        return LoginResult(ok=False, error="invalid email")
    if not is_strong_password(password):
        return LoginResult(ok=False, error="weak password")
    if store.get(email):
        return LoginResult(ok=False, error="user already exists")
    store.add(email, password)
    return LoginResult(ok=True, email=email)


def login(store: UserStore, data: dict) -> LoginResult:
    # BUG: assumes "email" is always present and is a string.
    email = normalize_email(data["email"])
    password = data.get("password") or ""

    user = store.get(email)
    if user is None:
        return LoginResult(ok=False, error="invalid credentials")
    if hash_password(password, user.salt) != user.password_hash:
        return LoginResult(ok=False, error="invalid credentials")
    return LoginResult(ok=True, email=email)
