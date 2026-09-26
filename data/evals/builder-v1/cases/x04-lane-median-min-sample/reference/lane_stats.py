import math


def lane_summary(values, min_n=5):
    """values: list of numbers (None ignored). Returns {"n", "median", "p90"}."""
    ordered = sorted(v for v in values if v is not None)
    n = len(ordered)
    if n == 0 or n < min_n:
        return {"n": n, "median": None, "p90": None}
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    p90 = ordered[math.ceil(0.9 * n) - 1]
    return {"n": n, "median": median, "p90": p90}
