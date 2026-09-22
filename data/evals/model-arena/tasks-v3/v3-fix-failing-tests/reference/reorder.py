"""Answer key. Never shipped to a model; used only to self-test the task."""
import math


def days_of_cover(on_hand: float, daily_demand: float) -> float:
    if daily_demand <= 0:
        return float("inf")
    return on_hand / daily_demand


def reorder_quantity(on_hand, daily_demand, lead_time_days, safety_days, pack_size):
    target = daily_demand * (lead_time_days + safety_days)
    gap = target - on_hand
    if gap <= 0:
        return 0
    packs = math.ceil(gap / pack_size)
    return packs * pack_size


def needs_reorder(on_hand, daily_demand, lead_time_days, safety_days) -> bool:
    return days_of_cover(on_hand, daily_demand) <= lead_time_days + safety_days
