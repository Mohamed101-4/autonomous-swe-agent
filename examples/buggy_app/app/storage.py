"""In-memory user store with salted password hashes."""

import hashlib
from dataclasses import dataclass


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


@dataclass
class User:
    email: str
    password_hash: str
    salt: str


class UserStore:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def add(self, email: str, password: str) -> User:
        salt = hashlib.sha256(email.encode()).hexdigest()[:8]
        user = User(email=email, password_hash=hash_password(password, salt), salt=salt)
        self._users[email] = user
        return user

    def get(self, email: str) -> User | None:
        return self._users.get(email)
