"""Retired compatibility tombstone for the layered refresh timing probe.

All invocations fail closed and are filesystem- and network-neutral.
"""

from __future__ import annotations

import json


EXIT_BLOCKED = 2
BLOCKED_PAYLOAD = {
    "schema": "veritas.layered_finance_refresh_timing_probe.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "layered_finance_refresh_timing_probe",
    "retired": True,
    "tombstone": True,
    "timing_probe_allowed": False,
    "finance_chain_execution_allowed": False,
    "subprocess_execution_allowed": False,
    "network_allowed": False,
    "filesystem_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "sql_or_canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "capital_account_order_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def main(_argv: object = None) -> int:
    print(json.dumps(BLOCKED_PAYLOAD, sort_keys=True))
    return EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
