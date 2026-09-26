import math


def lane_summary(values, min_n=5):
    """Return {"n": ..., "median": ..., "p90": ...}.

    None entries are ignored (not counted in "n"). "median" is the true
    median (average of the two middle values when n is even). "p90" uses
    the nearest-rank method: the ceil(0.9 * n)-th smallest value. When
    n < min_n, "median" and "p90" are None.
    """
    cleaned = [v for v in values if v is not None]
    n = len(cleaned)
    if n < min_n:
        return {"n": n, "median": None, "p90": None}
    ordered = sorted(cleaned)
    mid = n // 2
    if n % 2 == 1:
        median = ordered[mid]
    else:
        median = (ordered[mid - 1] + ordered[mid]) / 2
    p90 = ordered[math.ceil(0.9 * n) - 1]
    return {"n": n, "median": median, "p90": p90}
