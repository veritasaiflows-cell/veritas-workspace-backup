#!/usr/bin/env python3
"""Deny-only historical tombstone for the retired post-apply validator.

Every legacy CLI shape receives the same deterministic denial. This module
has no read, write, network, subprocess, schedule, SQL, canon, tier,
portfolio, proposal/apply, capital, account, order, paper, live, or execution
authority.
"""
from __future__ import annotations

import json


EXIT_RETIRED = 2

DENIAL_PAYLOAD: dict[str, object] = {
    "schema": "veritas.post_apply_validation_chain.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "post_apply_validation_chain",
    "retired": True,
    "tombstone": True,
    "compatibility_mode": "deny_only",
    "legacy_execute_allowed": False,
    "legacy_write_allowed": False,
    "validation_chain_execution_allowed": False,
    "subprocess_allowed": False,
    "filesystem_read_allowed": False,
    "filesystem_write_allowed": False,
    "network_allowed": False,
    "proposal_apply_allowed": False,
    "portfolio_state_or_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "schedule_mutation_allowed": False,
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
    raise SystemExit(main())
