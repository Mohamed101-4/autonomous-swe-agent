from datetime import date

from calendar_utils.ranges import date_range


def test_single_day_and_reversed():
    assert date_range(date(2024, 5, 5), date(2024, 5, 5)) == [date(2024, 5, 5)]
    assert date_range(date(2024, 5, 6), date(2024, 5, 5)) == []
