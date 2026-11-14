from datetime import date

from calendar_utils.booking import nights_booked
from calendar_utils.ranges import date_range


def test_nights():
    assert nights_booked(date(2024, 1, 1), date(2024, 1, 4)) == 3


def test_range_includes_end():
    days = date_range(date(2024, 1, 30), date(2024, 2, 1))
    assert days == [date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 1)]
