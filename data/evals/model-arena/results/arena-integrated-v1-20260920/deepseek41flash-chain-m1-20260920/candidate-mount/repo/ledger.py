"""Ledger accumulation."""

VALID_KINDS = ("debit", "credit")


def balance(entries):
    """Sum known entry kinds; unknown kinds must raise ValueError."""
    total = 0
    for entry in entries:
        kind = entry.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(f"unknown entry kind: {kind!r}")
        total += entry.get("amount", 0)
    return total
