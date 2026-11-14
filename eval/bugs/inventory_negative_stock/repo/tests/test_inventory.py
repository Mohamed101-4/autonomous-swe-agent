import pytest

from inventory.store import Inventory


def test_add_and_remove():
    inv = Inventory()
    inv.add("apple", 5)
    inv.remove("apple", 2)
    assert inv.level("apple") == 3


def test_cannot_go_negative():
    inv = Inventory()
    inv.add("apple", 1)
    with pytest.raises(ValueError, match="insufficient stock"):
        inv.remove("apple", 2)
    assert inv.level("apple") == 1
