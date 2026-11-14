from shop.pricing import add_tax, apply_discount


class Cart:
    def __init__(self) -> None:
        self.items: list[tuple[str, float, int]] = []
        self.coupon_percent = 0.0

    def add(self, name: str, price: float, qty: int = 1) -> None:
        self.items.append((name, price, qty))

    def subtotal(self) -> float:
        return round(sum(price * qty for _, price, qty in self.items), 2)

    def total(self, tax_rate: float = 0.0) -> float:
        discounted = apply_discount(self.subtotal(), self.coupon_percent)
        return add_tax(discounted, tax_rate)
