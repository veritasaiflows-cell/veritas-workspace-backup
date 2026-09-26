DAY_MS = 86_400_000
HOUR_MS = 3_600_000


def is_expired(ended_at, now_ms, days=7):
    """True when a row that ended at ended_at is past the retention window."""
    if ended_at is None:
        return False
    return now_ms - ended_at >= days * DAY_MS


def expiring_within(rows, now_ms, hours, days=7):
    """Ids of rows not yet expired that will expire at or before now_ms + hours.

    Rows are dicts with "id" and "ended_at" (epoch ms, or None for a
    still-running row). Skips rows whose ended_at is None. Ordered by
    expiry time, earliest first.
    """
    cutoff = now_ms + hours * HOUR_MS
    candidates = []
    for row in rows:
        ended_at = row.get("ended_at")
        if ended_at is None:
            continue
        if is_expired(ended_at, now_ms, days):
            continue
        expiry = ended_at + days * DAY_MS
        if expiry <= cutoff:
            candidates.append((expiry, row.get("id")))
    candidates.sort(key=lambda item: item[0])
    return [row_id for _, row_id in candidates]
