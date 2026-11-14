from datetime import date

from calendar_utils.ranges import date_range


def nights_booked(check_in: date, check_out: date) -> int:
    return max((check_out - check_in).days, 0)


def days_on_site(check_in: date, check_out: date) -> list[date]:
    return date_range(check_in, check_out)
