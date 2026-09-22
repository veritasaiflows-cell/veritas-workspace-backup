"""Inventory reorder logic for a single SKU."""


def days_of_cover(on_hand: float, daily_demand: float) -> float:
    """How many days the current stock lasts at the given demand rate."""
    if daily_demand <= 0:
        return float("inf")
    return on_hand / daily_demand


def reorder_quantity(on_hand, daily_demand, lead_time_days, safety_days, pack_size):
    """Units to order, rounded to whole supplier packs."""
    target = daily_demand * (lead_time_days + safety_days)
    gap = target - on_hand
    if gap <= 0:
        return 0
    packs = int(gap / pack_size)
    return packs * pack_size


def needs_reorder(on_hand, daily_demand, lead_time_days, safety_days) -> bool:
    """True when stock will run out before a replenishment can arrive."""
    return days_of_cover(on_hand, daily_demand) < lead_time_days
