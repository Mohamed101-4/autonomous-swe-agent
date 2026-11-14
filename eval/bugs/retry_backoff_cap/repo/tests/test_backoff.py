from netutil.client import retry_schedule


def test_first_delays_double():
    assert retry_schedule(3) == [1.0, 2.0, 4.0]


def test_delay_is_capped():
    assert retry_schedule(10, max_delay=30)[-1] == 30
