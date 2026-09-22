"""Recovery selection policy for replicated stores."""

ARCHIVE_PREFIX = "archive/"


def is_complete(store):
    """True when the store carries at least its own declared row count."""
    declared = store.get("declared_row_count")
    if not isinstance(declared, int) or isinstance(declared, bool):
        return False
    return len(store.get("rows", [])) >= declared


def latest_rows(rows):
    """Map each id to its newest row; equal timestamps keep the later row."""
    chosen = {}
    for row in rows:
        current = chosen.get(row["id"])
        if current is None or row["ts"] >= current["ts"]:
            chosen[row["id"]] = row
    return chosen


def settle(stores):
    """Return the rows of the first non-archive store that satisfies its count."""
    for name, store in stores.items():
        if name.startswith(ARCHIVE_PREFIX) or not is_complete(store):
            continue
        latest = latest_rows(store.get("rows", []))
        records = []
        tombstoned = []
        for rid in sorted(latest):
            row = latest[rid]
            if row.get("tombstone"):
                tombstoned.append(rid)
                continue
            records.append({"id": row["id"], "ts": row["ts"], "value": row["value"]})
        return {"records": records, "tombstoned": tombstoned, "source": name}
    return {"records": [], "tombstoned": [], "source": ""}
