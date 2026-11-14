from netutil.backoff import backoff_delay


def retry_schedule(retries: int, base: float = 1.0, max_delay: float = 30.0) -> list[float]:
    return [backoff_delay(i, base, max_delay) for i in range(retries)]
