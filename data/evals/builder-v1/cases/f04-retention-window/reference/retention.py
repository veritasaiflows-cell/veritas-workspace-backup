DAY_MS = 86_400_000


def is_expired(ended_at, now_ms, days=7):
    """True when a row that ended at ended_at (epoch ms) is past the retention window."""
    if ended_at is None:
        return False
    return now_ms >= ended_at + days * DAY_MS


def expiring_within(rows, now_ms, hours, days=7):
    horizon = now_ms + hours * 3_600_000
    live = [
        row for row in rows
        if row.get("ended_at") is not None
        and not is_expired(row["ended_at"], now_ms, days)
        and row["ended_at"] + days * DAY_MS <= horizon
    ]
    return [row["id"] for row in sorted(live, key=lambda row: row["ended_at"])]
