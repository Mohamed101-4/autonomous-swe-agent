def parse_csv(text: str) -> list[dict[str, str]]:
    """Parse CSV text with a header row into a list of dicts."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    header = lines[0].split(",")
    return [dict(zip(header, line.split(","))) for line in lines[1:]]
