"""Retired compatibility tombstone for the former portfolio mutation surface."""

from __future__ import annotations

import json


RETIRED_MARKER = "portfolio_mutation_surface_retired_tombstone_v1"
BLOCKED_RESULT = {
    "status": "blocked",
    "reason": "retired_surface",
    "marker": RETIRED_MARKER,
    "retired": True,
    "tombstone": True,
    "approval_artifact_read_allowed": False,
    "backup_creation_allowed": False,
    "owner_or_canon_write_allowed": False,
    "portfolio_mutation_allowed": False,
    "filesystem_mutation_allowed": False,
    "network_allowed": False,
}


def main() -> int:
    print(json.dumps(BLOCKED_RESULT, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
