DAY_MS = 86_400_000


def is_expired(ended_at, now_ms, days=7):
    """True when a row that ended at ended_at is past the retention window."""
    ended_ms = ended_at * 1000  # ended_at is seconds
    return now_ms - ended_ms > days * DAY_MS
