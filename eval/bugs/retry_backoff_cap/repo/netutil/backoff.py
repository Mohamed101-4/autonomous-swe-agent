def backoff_delay(attempt: int, base: float = 1.0, max_delay: float = 30.0) -> float:
    """Exponential backoff delay in seconds for a 0-indexed attempt, capped at max_delay."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    return base * (2**attempt)
