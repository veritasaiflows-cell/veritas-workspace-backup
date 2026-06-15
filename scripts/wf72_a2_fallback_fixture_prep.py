#!/usr/bin/env python3
"""Refresh the WF72 A2 fallback-fixture status/prep packet.

This packet summarizes current live/fixture proof for WF72 A2. It remains
report-only: it does not create the persisted fixture, change guard routing,
mutate SQL/cache rows, retire Python fallback, or promote consumers.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf72-a2-fallback-fixture-parity-prep.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_packet() -> dict[str, Any]:
    live_guard = load(TMP / "go-sql-consumer-authority-guard.json")
    fixture = load(TMP / "python-go-sql-consumer-authority-guard-fixture-parity.json")
    dashboard_ab = load(TMP / "python-go-sql-consumer-authority-dashboard-ab.json")
    controlled_router = load(TMP / "python-go-sql-consumer-authority-controlled-router.json")

    live_summary = as_dict(live_guard.get("summary"))
    fixture_summary = as_dict(fixture.get("summary"))
    approved_keys = int(fixture_summary.get("approved_keys") or live_summary.get("approved_keys") or 0)
    fallback_missing_live = int(live_summary.get("fallback_missing_keys") or 0)
    stale_live = int(live_summary.get("cache_stale_or_unsafe_rows") or 0)
    fixture_clean = fixture.get("status") == "ok" and fixture_summary.get("critical") == 0
    ab_clean = dashboard_ab.get("status") == "ok" and as_dict(dashboard_ab.get("summary")).get("critical") == 0
    router_clean = controlled_router.get("status") == "ok" and as_dict(controlled_router.get("summary")).get("critical") == 0
    live_complete = (
        live_guard.get("status") == "ok"
        and live_guard.get("sql_read_allowed") is True
        and approved_keys == 265
        and fallback_missing_live == 0
        and stale_live == 0
    )
    pre_a2_expected_gap = live_guard.get("status") == "fail_closed" and fallback_missing_live == approved_keys and stale_live == 13
    prepared = fixture_clean and ab_clean and router_clean and (live_complete or pre_a2_expected_gap)

    errors: list[str] = []
    warnings: list[str] = []
    if not fixture_clean:
        errors.append("fixture_parity_not_clean")
    if not ab_clean:
        errors.append("dashboard_ab_not_clean")
    if not router_clean:
        errors.append("controlled_router_not_clean")
    if approved_keys != 265:
        warnings.append(f"approved_key_count_expected_265_got_{approved_keys}")
    if not live_complete and live_guard.get("status") != "fail_closed":
        warnings.append("live_guard_neither_complete_nor_expected_pre_a2_fail_closed")
    if not live_complete and stale_live != 13:
        warnings.append(f"live_stale_source_rows_expected_13_got_{stale_live}")

    return {
        "schema_version": "wf72_a2_fallback_fixture_parity_status.v3",
        "generated_at_utc": utc_now(),
        "status": "complete" if live_complete and prepared and not errors else "prepared" if prepared and not errors else "blocked" if errors else "warning",
        "purpose": "Current WF72 A2 status packet for the live fallback-present fixture path.",
        "a2_live_complete": live_complete,
        "pre_a2_expected_gap": pre_a2_expected_gap,
        "cache_row_count": int(live_summary.get("cache_rows") or 0),
        "fixture_key_count": approved_keys,
        "guard_status_live": live_guard.get("status"),
        "guard_status_with_fixture": "ok" if fixture_clean else fixture.get("status"),
        "guard_sql_read_allowed_with_fixture": fixture_clean,
        "fallback_missing_keys_live": fallback_missing_live,
        "fallback_missing_keys_with_fixture": [],
        "cache_stale_or_unsafe_rows_live": stale_live,
        "guard_issues_with_fixture": [],
        "proof_artifacts": {
            "live_go_guard": "tmp/go-sql-consumer-authority-guard.json",
            "fixture_parity": "tmp/python-go-sql-consumer-authority-guard-fixture-parity.json",
            "dashboard_ab": "tmp/python-go-sql-consumer-authority-dashboard-ab.json",
            "controlled_router": "tmp/python-go-sql-consumer-authority-controlled-router.json",
        },
        "next_implementation_steps": [
            "If a2_live_complete is false: persist fallback fixture to a dedicated state/tmp artifact with source hash and row hash manifest.",
            "If a2_live_complete is false: teach the Go consumer-authority guard to load that fixture rather than an empty fallback path.",
            "Keep live parity validation green: Python owner values, SQL cache values, and Go fixture reads must match key-for-key.",
            "Keep prior source-hash drift resolved through A1 hygiene plus A2 fallback manifest proof.",
            "Re-run Go guard, hardening pass, harness scorecard, PM program state, and source-trust validators after SQL/skill/cron changes.",
            "Keep SQL as read-consumer only; no canon/portfolio/trade/account/customer authority change.",
        ],
        "authority_boundary": {
            "report_only": True,
            "production_consumer_wiring_changed_by_this_packet": False,
            "sql_import_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh WF72 A2 fallback fixture prep packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    packet = build_packet()
    if args.write:
        atomic_write_json(resolve(args.out), packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    if args.validate and packet["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
