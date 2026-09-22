"""Append-only cash ledger. Amounts are whole cents."""

VALID_KINDS = ("credit", "debit")


def validate(entry):
    """Raise ValueError if the entry is malformed, otherwise return True."""
    kind = entry.get("kind")
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown entry kind: {kind!r}")
    amount = entry.get("amount")
    if not isinstance(amount, int):
        raise ValueError("amount must be an integer number of cents")
    if amount < 0:
        raise ValueError("amount must not be negative")
    return True


def balance(entries):
    """Net balance in cents for a list of entries, oldest first."""
    total = 0
    for entry in entries:
        validate(entry)
        total += entry["amount"] if entry["kind"] == "credit" else -entry["amount"]
    return total
