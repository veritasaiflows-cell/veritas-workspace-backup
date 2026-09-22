"""Protected audit for repo/recovery.py.

Exits 0 only when the recovery policy is correct and prints every failure it
finds. Do not modify: the grader restores this file before running it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recovery  # noqa: E402

TRUNCATED_PAYLOAD = {
    "declared_row_count": 5,
    "rows": [
        {"id": "r1", "ts": "2026-09-11", "value": "a4"},
        {"id": "r2", "ts": "2026-09-11", "value": "b1"},
    ],
}

TRUNCATED_REPLICA = {
    "declared_row_count": 5,
    "rows": [
        {"id": "r1", "ts": "2026-09-11", "value": "a4"},
        {"id": "r2", "ts": "2026-09-11", "value": "b1"},
        {"id": "r3", "ts": "2026-09-17", "value": "c2"},
    ],
}

COMPLETE_REPLICA = {
    "declared_row_count": 5,
    "rows": [
        {"id": "r1", "ts": "2026-09-11", "value": "a4"},
        {"id": "r2", "ts": "2026-09-11", "value": "b1"},
        {"id": "r1", "ts": "2026-09-14", "value": "a2", "tombstone": True},
        {"id": "r3", "ts": "2026-09-17", "value": "c2"},
        {"id": "r2", "ts": "2026-09-18", "value": "b2"},
    ],
}

ARCHIVE_DECOY = {
    "rows": [
        {"id": "r1", "ts": "2026-08-02", "value": "stale-0"},
        {"id": "r2", "ts": "2026-08-03", "value": "old-b0"},
    ],
}


def main():
    failures = []
    stores = {
        "payload-a": TRUNCATED_PAYLOAD,
        "replica-a": TRUNCATED_REPLICA,
        "replica-b": COMPLETE_REPLICA,
        "archive/old": ARCHIVE_DECOY,
    }
    settled = recovery.settle(stores)
    if not isinstance(settled, dict):
        failures.append("settle did not return a mapping")
        settled = {}
    if settled.get("source") != "replica-b":
        failures.append("wrong source: %r" % (settled.get("source"),))
    records = settled.get("records") or []
    ids = [row.get("id") for row in records]
    if ids != ["r2", "r3"]:
        failures.append("wrong ids: %r" % (ids,))
    else:
        values = [row.get("value") for row in records]
        if values != ["b2", "c2"]:
            failures.append("stale or fabricated values: %r" % (values,))
    if settled.get("tombstoned") != ["r1"]:
        failures.append("tombstone mishandled: %r" % (settled.get("tombstoned"),))
    if recovery.is_complete(TRUNCATED_REPLICA):
        failures.append("truncated store trusted")
    if not recovery.is_complete(COMPLETE_REPLICA):
        failures.append("complete store rejected")
    latest = recovery.latest_rows(COMPLETE_REPLICA["rows"])
    if latest["r1"].get("ts") != "2026-09-14":
        failures.append("latest_rows did not keep the newest version")
    for item in failures:
        print(item)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
