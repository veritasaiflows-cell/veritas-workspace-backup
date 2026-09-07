#!/usr/bin/env python3
"""Retired WF67 compatibility tombstone.

All invocations fail closed and are filesystem-neutral.
"""
from __future__ import annotations

import json


EXIT_BLOCKED = 2
BLOCKED_PAYLOAD = {
    "schema": "veritas.wf67.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "network_allowed": False,
    "filesystem_mutation_allowed": False,
}


def main(_argv: object = None) -> int:
    print(json.dumps(BLOCKED_PAYLOAD, sort_keys=True))
    return EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
