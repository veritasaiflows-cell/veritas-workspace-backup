"""Marketplace fee calculation."""


def calc_fee(subtotal, rate):
    """Fee owed on an order subtotal. `rate` is a decimal fraction, e.g. 0.025."""
    return round(subtotal * rate, 2)
