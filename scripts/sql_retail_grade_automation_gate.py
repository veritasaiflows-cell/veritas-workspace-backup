#!/usr/bin/env python3
"""Report-only SQL retail-grade automation gate.

This condenses the large SQL retail-readiness proof into a small automation
surface and cross-checks the live bounded cache DB. It does not write SQL,
change consumers, mutate canon/portfolio notes, infer approval, or grant
trade/account/paper/live authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json
from sql_consumer_authority_guard import active_sql_canon_approved_keys

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
READINESS_JSON = TMP / "sql-canon-retail-grade-readiness.json"
CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
DEFAULT_OUT = TMP / "sql-retail-grade-automation-gate.json"

EXPECTED_CACHE_ROWS = 265
EXPECTED_LOW_RISK_ROWS = 13
EXPECTED_ENTRY_STOP_ROWS = 252
STALE_PROOF_HOURS = 8

FALSE_AUTHORITY_FLAGS = (
    "activation_allowed_by_this_artifact",
    "canonical_note_mutation_allowed",
    "config_auth_channel_service_mutation_allowed",
    "consumer_behavior_change_allowed_by_this_artifact",
    "credential_config_mutation_allowed",
    "external_delivery_allowed",
    "live_trade_authority_allowed",
    "markdown_mutation_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "paper_trade_authority_allowed",
    "portfolio_mutation_allowed",
    "proposal_apply_allowed",
    "real_customer_data_allowed",
)

LOW_RISK_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
ENTRY_STOP_BOUNDARY = "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority"

AUTHORITY_BOUNDARY = (
    "sql_retail_grade_automation_gate_report_only_no_sql_writes_no_consumer_behavior_change_"
    "no_canon_or_portfolio_mutation_no_owner_approval_no_trade_account_paper_live_authority"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"{path.relative_to(ROOT).as_posix()} could not be read as JSON: {exc}"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def live_cache_snapshot(hard_failures: list[str]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "path": CANON_CACHE_DB.relative_to(ROOT).as_posix(),
        "exists": CANON_CACHE_DB.exists(),
        "quick_check": None,
        "row_count": None,
        "authority_boundaries": {},
        "field_counts": {},
        "scope_count": None,
        "approved_key_count_from_guard": None,
        "expected_cache_rows": EXPECTED_CACHE_ROWS,
        "expected_low_risk_rows": EXPECTED_LOW_RISK_ROWS,
        "expected_entry_stop_rows": EXPECTED_ENTRY_STOP_ROWS,
        "read_mode": "sqlite_uri_mode_ro",
    }
    if not CANON_CACHE_DB.exists():
        hard_failures.append("missing live cache DB tmp/veritas-canon-cache.sqlite")
        return snapshot

    try:
        with connect_ro(CANON_CACHE_DB) as conn:
            snapshot["quick_check"] = conn.execute("PRAGMA quick_check").fetchone()[0]
            rows = [dict(row) for row in conn.execute("SELECT * FROM canon_cache_fields")]
    except Exception as exc:
        hard_failures.append(f"live cache DB read failed: {exc}")
        return snapshot

    boundaries = Counter(str(row.get("authority_boundary")) for row in rows)
    fields = Counter(str(row.get("field_name")) for row in rows)
    snapshot["row_count"] = len(rows)
    snapshot["authority_boundaries"] = dict(sorted(boundaries.items()))
    snapshot["field_counts"] = dict(sorted(fields.items()))
    snapshot["scope_count"] = len({str(row.get("scope")) for row in rows})
    snapshot["approved_key_count_from_guard"] = len(active_sql_canon_approved_keys())

    if snapshot["quick_check"] != "ok":
        hard_failures.append(f"live cache DB quick_check={snapshot['quick_check']}")
    if len(rows) != EXPECTED_CACHE_ROWS:
        hard_failures.append(f"live cache row count {len(rows)} != expected {EXPECTED_CACHE_ROWS}")
    if boundaries.get(LOW_RISK_BOUNDARY, 0) != EXPECTED_LOW_RISK_ROWS:
        hard_failures.append("low-risk proof/freshness metadata row count mismatch")
    if boundaries.get(ENTRY_STOP_BOUNDARY, 0) != EXPECTED_ENTRY_STOP_ROWS:
        hard_failures.append("WF72 entry/stop reference metadata row count mismatch")
    if snapshot["approved_key_count_from_guard"] != EXPECTED_CACHE_ROWS:
        hard_failures.append("approved SQL-canon key count from guard does not match live cache row count")
    return snapshot


def summarize_readiness(data: dict[str, Any], warnings: list[str], blockers: list[str], hard_failures: list[str]) -> dict[str, Any]:
    rows = data.get("row_readiness") if isinstance(data.get("row_readiness"), list) else []
    generated_at = data.get("generated_at_utc")
    generated_dt = parse_utc(generated_at)
    age_hours = None
    if generated_dt is None:
        warnings.append("readiness proof has missing or invalid generated_at_utc")
    else:
        age_hours = round((datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600, 2)
        if age_hours > STALE_PROOF_HOURS:
            warnings.append(f"readiness proof age {age_hours}h exceeds {STALE_PROOF_HOURS}h freshness target")

    true_flags = [
        flag
        for flag in FALSE_AUTHORITY_FLAGS
        if data.get(flag) not in (False, None)
    ]
    if true_flags:
        hard_failures.append("readiness artifact has forbidden authority flags true/nonfalse: " + ", ".join(true_flags))

    activation_allowed = data.get("activation_allowed_by_this_artifact") is True
    if activation_allowed:
        hard_failures.append("readiness artifact unexpectedly allows activation")

    blocker_rows = [row for row in rows if row.get("sql_effective_allowed") is not True]
    effective_rows = [row for row in rows if row.get("sql_effective_allowed") is True]
    if blocker_rows:
        blockers.append(f"{len(blocker_rows)} rows are not SQL-effective for retail-grade use")

    issue_counter: Counter[str] = Counter()
    for row in rows:
        for issue in row.get("issues") or []:
            issue_counter[str(issue)] += 1

    guard_issue_count = len(data.get("guard_issues") or [])
    if guard_issue_count:
        blockers.append(f"{guard_issue_count} guard issue groups remain in retail readiness proof")

    return {
        "path": READINESS_JSON.relative_to(ROOT).as_posix(),
        "exists": READINESS_JSON.exists(),
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "source_status": data.get("status"),
        "activation_allowed_by_this_artifact": data.get("activation_allowed_by_this_artifact"),
        "authority_boundary": data.get("authority_boundary"),
        "row_count": len(rows),
        "sql_effective_allowed_rows": len(effective_rows),
        "blocked_or_fallback_required_rows": len(blocker_rows),
        "blocking_key_count": len(data.get("blocking_keys") or []),
        "guard_issue_group_count": guard_issue_count,
        "readiness_counts": dict(Counter(str(row.get("readiness")) for row in rows)),
        "freshness_counts": dict(Counter(str(row.get("freshness_status")) for row in rows)),
        "risk_family_counts": dict(Counter(str(row.get("risk_family")) for row in rows)),
        "top_row_issues": dict(issue_counter.most_common(12)),
        "authority_flags": {flag: data.get(flag) for flag in FALSE_AUTHORITY_FLAGS if flag in data},
        "retail_grade_phases": data.get("retail_grade_phases") or [],
    }


def build_report() -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    hard_failures: list[str] = []

    data, error = read_json(READINESS_JSON)
    if error:
        hard_failures.append(error)
        data = {}
    if not isinstance(data, dict):
        hard_failures.append("readiness artifact is not a JSON object")
        data = {}

    cache = live_cache_snapshot(hard_failures)
    readiness = summarize_readiness(data, warnings, blockers, hard_failures)

    status = "hard_failed" if hard_failures else "blocked" if blockers else "warning" if warnings else "ok"
    return {
        "schema_version": "sql_retail_grade_automation_gate.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "retail_grade_sql_first_allowed": False if status in {"hard_failed", "blocked", "warning"} else True,
        "consumer_behavior_change_allowed": False,
        "sql_writes_allowed": False,
        "canon_or_portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_account_paper_live_authority_allowed": False,
        "validation_semantics": {
            "validate_exit_nonzero_on": "hard failures only",
            "strict_blocked_exit_nonzero_on": "hard failures or blocked retail-grade status",
            "blocked_status_is_expected_while_sql_effective_allowed_rows_are_zero": True,
        },
        "counts": {
            "warnings": len(warnings),
            "blockers": len(blockers),
            "hard_failures": len(hard_failures),
        },
        "warnings": warnings,
        "blockers": blockers,
        "hard_failures": hard_failures,
        "live_cache": cache,
        "readiness": readiness,
        "next_safe_actions": [
            "Keep SQL retail-grade use blocked until fallback-required rows are modeled or remediated.",
            "Use the WF72 read-only entry/stop helper for display/reference metadata only.",
            "Build WF78 scaleout gate before increasing production ticker obligations.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report-only SQL retail-grade automation gate")
    parser.add_argument("--write", action="store_true", help=f"Write {DEFAULT_OUT.as_posix()}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validate", action="store_true", help="Return nonzero only for hard gate failures")
    parser.add_argument("--strict-blocked", action="store_true", help="Return nonzero for blocked status as well as hard failures")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(args.output, report, indent=2, ensure_ascii=True)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    print(
        "status={status} hard_failures={hard} blockers={blockers} warnings={warnings} "
        "cache_rows={cache_rows} sql_effective_allowed_rows={effective} output={output}".format(
            status=report["status"],
            hard=report["counts"]["hard_failures"],
            blockers=report["counts"]["blockers"],
            warnings=report["counts"]["warnings"],
            cache_rows=report["live_cache"].get("row_count"),
            effective=report["readiness"].get("sql_effective_allowed_rows"),
            output=args.output.as_posix() if args.write else "stdout",
        )
    )

    if args.validate and report["counts"]["hard_failures"]:
        return 1
    if args.validate and args.strict_blocked and report["status"] in {"hard_failed", "blocked"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
