"""Boundary helpers."""


def within(lo, hi, value):
    """True when value sits inside the inclusive [lo, hi] range."""
    return lo <= value <= hi
