"""Recovery selection policy for replicated stores."""

ARCHIVE_PREFIX = "archive/"


def is_complete(store):
    """True when the store carries at least its own declared row count."""
    return len(store.get("rows", [])) >= store.get("declared_row_count", 0)


def latest_rows(rows):
    """Map each id to its newest row."""
    chosen = {}
    for row in rows:
        current = chosen.get(row["id"])
        if current is None or row["ts"] >= current["ts"]:
            chosen[row["id"]] = row
    return chosen


def settle(stores):
    """Return the newest row per id across every complete store."""
    rows = []
    source = "primary"
    for name, store in stores.items():
        if name.startswith(ARCHIVE_PREFIX):
            continue
        if not is_complete(store):
            continue
        source = name
        rows.extend(store.get("rows", []))
    chosen = latest_rows(rows)
    return {"records": sorted(chosen.values(), key=lambda row: row["id"]),
            "tombstoned": [],
            "source": source}
