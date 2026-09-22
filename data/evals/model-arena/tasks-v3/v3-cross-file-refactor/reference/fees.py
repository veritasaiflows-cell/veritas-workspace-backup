"""Marketplace fee calculation."""


def compute_fee(subtotal, rate_bps, minimum_fee=0.0):
    """Fee owed on an order subtotal. `rate_bps` is basis points, e.g. 250 = 2.5%."""
    return max(round(subtotal * rate_bps / 10000, 2), minimum_fee)
