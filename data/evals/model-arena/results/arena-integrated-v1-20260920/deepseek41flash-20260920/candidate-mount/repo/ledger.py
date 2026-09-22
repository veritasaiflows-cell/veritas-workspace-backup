"""Ledger accumulation."""

VALID_KINDS = ("debit", "credit")


def balance(entries):
    """Sum known entry kinds; unknown kinds raise ValueError."""
    total = 0
    for entry in entries:
        kind = entry.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError("unknown entry kind: {0!r}".format(kind))
        total += entry.get("amount", 0)
    return total
