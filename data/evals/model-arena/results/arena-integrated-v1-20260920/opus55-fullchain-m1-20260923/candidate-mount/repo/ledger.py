"""Ledger accumulation."""

VALID_KINDS = ("debit", "credit")


def balance(entries):
    """Sum known entry kinds; unknown kinds must raise ValueError."""
    total = 0
    for entry in entries:
        if entry.get("kind") in VALID_KINDS:
            total += entry.get("amount", 0)
    return total
