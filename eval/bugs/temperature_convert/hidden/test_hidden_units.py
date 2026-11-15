import pytest

from weather.units import c_to_f, f_to_c


def test_f_to_c_values():
    assert f_to_c(32) == 0
    assert f_to_c(-40) == -40
    assert f_to_c(98.6) == pytest.approx(37.0)


def test_round_trip():
    assert f_to_c(c_to_f(21.5)) == pytest.approx(21.5)
