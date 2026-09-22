"""Append-only cash ledger. Amounts are whole cents."""

VALID_KINDS = ("credit", "debit", "reversal")


def validate(entry):
    """Raise ValueError if the entry is malformed, otherwise return True."""
    kind = entry.get("kind")
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown entry kind: {kind!r}")
    if kind == "reversal":
        if not entry.get("ref"):
            raise ValueError("reversal entry requires a ref")
        return True
    amount = entry.get("amount")
    if not isinstance(amount, int):
        raise ValueError("amount must be an integer number of cents")
    if amount < 0:
        raise ValueError("amount must not be negative")
    return True


def balance(entries):
    """Net balance in cents for a list of entries, oldest first."""
    total = 0
    seen = {}
    already_reversed = set()
    for entry in entries:
        validate(entry)
        if entry["kind"] == "reversal":
            ref = entry["ref"]
            if ref not in seen:
                raise ValueError(f"unknown reversal ref: {ref!r}")
            if seen[ref]["kind"] == "reversal":
                raise ValueError(f"cannot reverse a reversal: {ref!r}")
            if ref in already_reversed:
                raise ValueError(f"entry already reversed: {ref!r}")
            already_reversed.add(ref)
            target = seen[ref]
            total -= target["amount"] if target["kind"] == "credit" else -target["amount"]
        else:
            total += entry["amount"] if entry["kind"] == "credit" else -entry["amount"]
        if entry.get("id"):
            seen[entry["id"]] = entry
    return total
