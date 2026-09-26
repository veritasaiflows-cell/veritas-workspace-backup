def lane_summary(values):
    """values: list of numbers. Returns {"n": ..., "median": ...}."""
    ordered = sorted(values)
    return {"n": len(ordered), "median": ordered[len(ordered) // 2]}
