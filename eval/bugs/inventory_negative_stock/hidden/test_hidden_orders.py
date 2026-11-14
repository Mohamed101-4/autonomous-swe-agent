from inventory.orders import fulfil
from inventory.store import Inventory


def test_short_order_rejected():
    inv = Inventory()
    inv.add("a", 2)
    assert fulfil(inv, {"a": 3}) is False
    assert inv.level("a") == 2


def test_unknown_sku_rejected():
    inv = Inventory()
    assert fulfil(inv, {"ghost": 1}) is False
    assert inv.level("ghost") == 0
