from shop.cart import Cart


def test_subtotal():
    cart = Cart()
    cart.add("pen", 2.5, 4)
    assert cart.subtotal() == 10.0


def test_no_coupon():
    cart = Cart()
    cart.add("book", 40.0)
    assert cart.total() == 40.0


def test_ten_percent_coupon():
    cart = Cart()
    cart.add("book", 200.0)
    cart.coupon_percent = 10
    assert cart.total() == 180.0
