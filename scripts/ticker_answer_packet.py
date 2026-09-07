#!/usr/bin/env python3
"""Deny-only historical tombstone for the retired ticker-answer packet surface.

All legacy CLI shapes receive the same deterministic denial. This module has
no read, build, write, network, subprocess, schedule, SQL, canon, tier,
portfolio, capital, account, order, execution, paper, or live authority.
"""
from __future__ import annotations

import json
import sys
from typing import Final


SCHEMA: Final = "veritas.ticker_answer_packet.retired_compatibility.v1"
EXIT_RETIRED: Final = 2

DENIAL_PAYLOAD: Final[dict[str, object]] = {
    "schema": SCHEMA,
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "ticker_answer_packet",
    "retired": True,
    "tombstone": True,
    "compatibility_mode": "deny_only",
    "legacy_read_allowed": False,
    "legacy_write_allowed": False,
    "build_allowed": False,
    "build_summary_allowed": False,
    "filesystem_mutation_allowed": False,
    "subprocess_allowed": False,
    "network_allowed": False,
    "schedule_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "portfolio_state_allowed": False,
    "capital_deployment_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "trade_order_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "exit_code": EXIT_RETIRED,
}


def main(_argv: list[str] | None = None) -> int:
    """Deny every legacy invocation without parsing it or touching the workspace."""
    print(json.dumps(DENIAL_PAYLOAD, sort_keys=True, separators=(",", ":")))
    return EXIT_RETIRED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
