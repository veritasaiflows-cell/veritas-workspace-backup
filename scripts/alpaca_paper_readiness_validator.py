#!/usr/bin/env python3
"""Retired paper-validator compatibility tombstone.

All invocations fail closed and are filesystem-neutral.
"""
from __future__ import annotations

import json


EXIT_BLOCKED = 2


def main(_argv: object = None) -> int:
    print(
        json.dumps(
            {
                "schema": "veritas.retired_paper_validator.v1",
                "status": "blocked",
                "reason": "retired_surface",
                "retired": True,
                "tombstone": True,
                "ready_for_paper_submit_cancel": False,
                "network_allowed": False,
                "filesystem_mutation_allowed": False,
                "paper_execution_allowed": False,
                "order_action_allowed": False,
                "account_action_allowed": False,
                "owner_approval_inferred": False,
                "maintains_simulated_account_state": False,
            },
            sort_keys=True,
        )
    )
    return EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
