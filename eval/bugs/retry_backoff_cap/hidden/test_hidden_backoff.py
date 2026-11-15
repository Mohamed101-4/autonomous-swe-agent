from netutil.backoff import backoff_delay


def test_cap_and_base():
    assert backoff_delay(3, base=0.5, max_delay=10) == 4.0
    assert backoff_delay(20, base=0.5, max_delay=10) == 10
    assert backoff_delay(0, base=2, max_delay=1) == 1
