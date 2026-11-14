"""Input validation helpers."""

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    """Trim whitespace and lowercase an email address."""
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


def is_strong_password(password: str) -> bool:
    return len(password) >= 8 and any(c.isdigit() for c in password)
