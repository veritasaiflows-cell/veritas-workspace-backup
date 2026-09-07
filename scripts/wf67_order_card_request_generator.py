"""Retired compatibility tombstone for the former WF67 request surface."""

from __future__ import annotations

import json


EXIT_BLOCKED = 2
BLOCKED_PAYLOAD = {
    "status": "blocked",
    "reason": "retired_surface",
    "retired": True,
    "tombstone": True,
    "network_allowed": False,
    "filesystem_mutation_allowed": False,
    "paper_authority": False,
    "order_authority": False,
    "account_authority": False,
}


def main(_argv: object = None) -> int:
    print(json.dumps(BLOCKED_PAYLOAD, sort_keys=True))
    return EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
