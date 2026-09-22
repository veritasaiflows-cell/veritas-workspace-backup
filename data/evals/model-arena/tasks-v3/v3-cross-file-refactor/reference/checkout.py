"""Buyer-facing order totals."""
from fees import compute_fee


def order_total(subtotal, rate_bps, minimum_fee=0.0):
    """Grand total charged to the buyer, fee included."""
    return round(subtotal + compute_fee(subtotal, rate_bps, minimum_fee), 2)
