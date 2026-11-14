from weather.report import format_reading
from weather.units import c_to_f


def test_c_to_f():
    assert c_to_f(100) == 212


def test_boiling_point_report():
    assert format_reading("Lab", 212) == "Lab: 100C"
