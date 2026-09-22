"""Shipping cost bands. Independent of fees."""

BANDS = ((1.0, 4.95), (5.0, 7.95), (20.0, 12.95))


def shipping_cost(weight_kg):
    """Flat band price for a parcel weight."""
    for limit, price in BANDS:
        if weight_kg <= limit:
            return price
    return 19.95
