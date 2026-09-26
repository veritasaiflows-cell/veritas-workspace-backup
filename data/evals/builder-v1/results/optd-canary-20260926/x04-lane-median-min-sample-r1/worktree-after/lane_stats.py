import math


def lane_summary(values, min_n=5):
    """values: list of numbers (None entries ignored). Returns {"n": ..., "median": ..., "p90": ...}."""
    cleaned = [v for v in values if v is not None]
    n = len(cleaned)
    if n < min_n:
        return {"n": n, "median": None, "p90": None}
    ordered = sorted(cleaned)
    if n % 2 == 1:
        median = ordered[n // 2]
    else:
        median = (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    p90 = ordered[math.ceil(0.9 * n) - 1]
    return {"n": n, "median": median, "p90": p90}
