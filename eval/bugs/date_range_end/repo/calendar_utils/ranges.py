from datetime import date, timedelta


def date_range(start: date, end: date) -> list[date]:
    """All dates from start to end, inclusive."""
    if end < start:
        return []
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days)]
