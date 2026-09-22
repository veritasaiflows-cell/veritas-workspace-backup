"""Boundary helpers."""


def within(lo, hi, value):
    """True when value sits inside the [lo, hi] range, inclusive at both ends."""
    return lo <= value <= hi
