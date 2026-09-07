#!/usr/bin/env python3
"""Deny-only historical tombstone for the retired cache dependency manifest.

Every legacy CLI shape receives the same deterministic denial. This module
has no read, write, cache, SQL, network, subprocess, schedule, canon, tier,
portfolio, capital, account, order, paper, live, or execution authority.
"""
from __future__ import annotations

import json


EXIT_RETIRED = 2

DENIAL_PAYLOAD: dict[str, object] = {
    "schema": "veritas.cache_dependency_manifest.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "cache_dependency_manifest",
    "retired": True,
    "tombstone": True,
    "compatibility_mode": "deny_only",
    "current_truth_allowed": False,
    "legacy_manifest_read_allowed": False,
    "legacy_manifest_write_allowed": False,
    "cache_chain_build_allowed": False,
    "cache_or_sql_read_allowed": False,
    "filesystem_read_allowed": False,
    "filesystem_write_allowed": False,
    "subprocess_allowed": False,
    "network_allowed": False,
    "schedule_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "portfolio_state_or_mutation_allowed": False,
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
