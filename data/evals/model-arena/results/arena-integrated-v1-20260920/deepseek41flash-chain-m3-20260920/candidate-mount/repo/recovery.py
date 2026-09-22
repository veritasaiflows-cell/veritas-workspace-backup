"""Recovery selection policy for replicated stores."""

ARCHIVE_PREFIX = "archive/"


def is_complete(store):
    """True when the store carries at least its own declared row count."""
    return len(store.get("rows", [])) >= store.get("declared_row_count", 0)


def latest_rows(rows):
    """Map each id to its newest row, breaking ties by later position."""
    chosen = {}
    for row in rows:
        current = chosen.get(row["id"])
        if current is None or row["ts"] >= current["ts"]:
            chosen[row["id"]] = row
    return chosen


def settle(stores):
    """Return the newest row per id from the first trusted store."""
    for name, store in stores.items():
        if name.startswith(ARCHIVE_PREFIX):
            continue
        if not is_complete(store):
            continue
        chosen = latest_rows(store.get("rows", []))
        records = sorted(
            (row for row in chosen.values() if not row.get("tombstone")),
            key=lambda row: row["id"],
        )
        tombstoned = sorted(
            rid for rid, row in chosen.items() if row.get("tombstone")
        )
        return {"records": records, "tombstoned": tombstoned, "source": name}
    return {"records": [], "tombstoned": [], "source": ""}
