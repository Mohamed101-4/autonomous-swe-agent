from inventory.store import Inventory


def fulfil(inv: Inventory, order: dict[str, int]) -> bool:
    """Fulfil an order; return False (and change nothing) if any item is short."""
    try:
        for sku, qty in order.items():
            inv.remove(sku, qty)
    except ValueError:
        return False
    return True
