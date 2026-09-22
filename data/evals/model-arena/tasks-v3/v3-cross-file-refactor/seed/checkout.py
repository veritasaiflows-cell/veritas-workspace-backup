"""Buyer-facing order totals."""
from fees import calc_fee


def order_total(subtotal, rate):
    """Grand total charged to the buyer, fee included."""
    return round(subtotal + calc_fee(subtotal, rate), 2)
