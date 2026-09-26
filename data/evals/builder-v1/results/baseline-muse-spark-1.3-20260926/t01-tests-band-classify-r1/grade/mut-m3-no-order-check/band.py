def classify(price, low, high):
    """Return "below" if price < low, "above" if price > high, else "inside".

    low and high are inclusive bounds (a price equal to low or high is "inside").
    Raises ValueError if low > high or if any argument is None.
    """
    if price is None or low is None or high is None:
        raise ValueError("missing value")
    if price < low:
        return "below"
    if price > high:
        return "above"
    return "inside"
