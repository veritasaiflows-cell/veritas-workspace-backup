import math


def lane_summary(values, min_n=5):
    """values: list of numbers (None entries ignored). Returns {"n": ..., "median": ..., "p90": ...}."""
    filtered = [v for v in values if v is not None]
    n = len(filtered)
    if n < min_n or n == 0:
        return {"n": n, "median": None, "p90": None}
    ordered = sorted(filtered)
    mid = n // 2
    if n % 2 == 1:
        median = ordered[mid]
    else:
        median = (ordered[mid - 1] + ordered[mid]) / 2
    p90 = ordered[math.ceil(0.9 * n) - 1]
    return {"n": n, "median": median, "p90": p90}
