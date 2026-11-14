from contacts.importer import parse_csv


def load_directory(text: str) -> dict[str, str]:
    """Map contact name -> email."""
    return {row["name"]: row["email"] for row in parse_csv(text)}
