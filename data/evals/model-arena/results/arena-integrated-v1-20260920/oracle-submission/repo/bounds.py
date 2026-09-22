"""Boundary helpers."""


def within(lo, hi, value):
    """True when value sits inside the [lo, hi] range."""
    return lo <= value <= hi
