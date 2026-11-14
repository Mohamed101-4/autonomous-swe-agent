from shop.pricing import apply_discount


def test_discount_percentages():
    assert apply_discount(50.0, 20) == 40.0
    assert apply_discount(80.0, 0) == 80.0
    assert apply_discount(80.0, 100) == 0.0
