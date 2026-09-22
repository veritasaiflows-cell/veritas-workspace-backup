"""Renders invoice rows for the accounting export."""
from fees import compute_fee as _fee


def render_line(description, subtotal, rate_bps, minimum_fee=0.0):
    """One pipe-delimited row: description|subtotal|fee|total."""
    fee = _fee(subtotal, rate_bps, minimum_fee)
    return f"{description}|{subtotal:.2f}|{fee:.2f}|{subtotal + fee:.2f}"
