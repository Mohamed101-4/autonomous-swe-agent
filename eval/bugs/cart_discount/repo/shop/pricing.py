def apply_discount(total: float, percent: float) -> float:
    """Return total after a percentage discount (e.g. percent=10 means 10% off)."""
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total - percent, 2)


def add_tax(total: float, rate: float) -> float:
    return round(total * (1 + rate), 2)
