"""Renders invoice rows for the accounting export."""
from fees import calc_fee as _fee


def render_line(description, subtotal, rate):
    """One pipe-delimited row: description|subtotal|fee|total."""
    fee = _fee(subtotal, rate)
    return f"{description}|{subtotal:.2f}|{fee:.2f}|{subtotal + fee:.2f}"
