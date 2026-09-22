"""Boundary helpers."""


def within(lo, hi, value):
    """True when value sits inside the [lo, hi] range (inclusive both ends)."""
    return bool(lo <= value <= hi)
