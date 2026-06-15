#!/usr/bin/env python3
"""Build a preview-only WF78 tier-label sync artifact.

The tier-label decision register records owner-approved labels, but it is not
itself a roster surface. This script prepares the formal sync preview that a
future gated apply path can review. It never writes labels into the universe,
canon, portfolio notes, SQL, ticker cards, or execution surfaces.
"""
from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REGISTER = TMP / "wf78-tier-label-decision-register.json"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
DEFAULT_OUT = TMP / "wf78-tier-label-sync-preview.json"
SCHEMA = "veritas.wf78_tier_label_sync_preview.v1"

TIER_A_CAP = 25
TIER_B_CAP = 50
COMBINED_CAP = 75

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "preview_only": True,
    "audit_only": True,
    "not_current_tier_authority": True,
    "auto_router_is_current_tier_authority": True,
    "tier_label_apply_executed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "report_only",
    "preview_only",
    "audit_only",
    "not_current_tier_authority",
    "auto_router_is_current_tier_authority",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def approved_tier_b_labels(register: dict[str, Any]) -> list[str]:
    labels = {
        str(ticker).upper().strip()
        for record in as_list(register.get("records"))
        if isinstance(record, dict) and record.get("decision_type") == "tier_b_research_bench_label_only"
        for ticker in as_list(record.get("approved_tickers"))
        if str(ticker).strip()
    }
    return sorted(labels)


def universe_by_ticker(universe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(universe.get("entries"))
        if isinstance(row, dict) and row.get("ticker")
    }


def preview_row(ticker: str, row: dict[str, Any]) -> dict[str, Any]:
    current_tier = row.get("tier")
    current_role = row.get("monitoring_role")
    current_coverage = as_dict(row.get("coverage_reason"))
    already_legacy_b = current_tier == "B"
    proposed_action = "no_legacy_tier_change_needed" if already_legacy_b else "would_add_formal_tier_b_research_bench_label"
    return {
        "ticker": ticker,
        "name": row.get("name"),
        "sector": row.get("sector"),
        "instrument_type": row.get("instrument_type"),
        "active": row.get("active"),
        "current_universe_tier": current_tier,
        "current_monitoring_role": current_role,
        "current_workflow_state": legacy_state(current_coverage, "workflow_state"),
        "approved_label": "Tier B",
        "approved_role": "research_bench",
        "deployment_ready": False,
        "trade_or_execution_approval": False,
        "proposed_sync_action": proposed_action,
        "would_mutate_universe": False,
        "requires_separate_apply_path": True,
    }


def build_report() -> dict[str, Any]:
    register = load_dict(REGISTER)
    universe = load_dict(UNIVERSE)
    by_ticker = universe_by_ticker(universe)
    labels = approved_tier_b_labels(register)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for ticker in labels:
        row = by_ticker.get(ticker)
        if row:
            rows.append(preview_row(ticker, row))
        else:
            missing.append(ticker)

    would_add = [row["ticker"] for row in rows if row.get("proposed_sync_action") == "would_add_formal_tier_b_research_bench_label"]
    already_legacy_b = [row["ticker"] for row in rows if row.get("proposed_sync_action") == "no_legacy_tier_change_needed"]
    current_legacy_a = sorted(ticker for ticker, row in by_ticker.items() if row.get("tier") == "A")
    current_legacy_b = sorted(ticker for ticker, row in by_ticker.items() if row.get("tier") == "B")

    checks: list[dict[str, Any]] = []
    add_check(checks, "register_present", bool(register), rel(REGISTER))
    add_check(checks, "register_validation_ok", as_dict(register.get("validation")).get("status") == "ok", as_dict(register.get("validation")).get("status"))
    add_check(checks, "universe_present", bool(universe), rel(UNIVERSE))
    add_check(checks, "universe_entries_present", bool(by_ticker), len(by_ticker))
    add_check(checks, "approved_tier_b_labels_present", bool(labels), labels)
    add_check(checks, "approved_labels_resolve_in_universe", not missing, missing)
    add_check(checks, "approved_tier_b_within_cap", len(labels) <= TIER_B_CAP, {"approved": len(labels), "cap": TIER_B_CAP})
    add_check(checks, "legacy_tier_a_within_cap", len(current_legacy_a) <= TIER_A_CAP, {"legacy_a": len(current_legacy_a), "cap": TIER_A_CAP})
    add_check(checks, "formal_a_plus_approved_b_within_combined_cap", (0 + len(labels)) <= COMBINED_CAP, {"approved_tier_a": 0, "approved_tier_b": len(labels), "cap": COMBINED_CAP})
    add_check(checks, "no_universe_mutation", AUTHORITY_BOUNDARY["universe_mutation_allowed"] is False, AUTHORITY_BOUNDARY["universe_mutation_allowed"])
    add_check(checks, "no_tier_label_apply_executed", AUTHORITY_BOUNDARY["tier_label_apply_executed"] is False, AUTHORITY_BOUNDARY["tier_label_apply_executed"])
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "preview_ready" if not errors else "blocked",
        "workflow": "WF78 - Tier Label Sync Preview",
        "purpose": "Preview how owner-approved WF78 label-only decisions would map to a formal roster surface without applying or mutating anything.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "semantic_contract": {
            "current_tier_authority": "tmp/wf78-auto-tier-routing.json",
            "this_artifact_role": "audit_only_formal_label_sync_preview",
            "not_current_tier_authority": True,
            "auto_router_wins_on_conflict": True,
            "lower_model_instruction": "Do not answer current Tier A/B/C membership from this artifact. Use wf78-auto-tier-routing or wf78-clean-tier-roster.",
        },
        "source_artifacts": {
            "tier_label_decision_register": rel(REGISTER),
            "universe_registry": rel(UNIVERSE),
        },
        "summary": {
            "approved_tier_b_research_bench_label_count": len(labels),
            "approved_tier_b_research_bench_labels": labels,
            "already_legacy_b_count": len(already_legacy_b),
            "already_legacy_b_tickers": already_legacy_b,
            "would_add_formal_tier_b_label_count": len(would_add),
            "would_add_formal_tier_b_label_tickers": would_add,
            "missing_from_universe": missing,
            "current_legacy_tier_a_count": len(current_legacy_a),
            "current_legacy_tier_b_count": len(current_legacy_b),
            "formal_approved_tier_a_count": 0,
            "formal_approved_tier_b_count": len(labels),
            "tier_label_apply_executed": False,
            "universe_mutation_executed": False,
            "recommended_next_action": "Use this preview as the input to a separate owner-gated label-sync apply path only if a formal roster surface is needed.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This preview does not apply Tier A or Tier B labels.",
            "This preview does not modify universe-v1, portfolio notes, canon notes, SQL, ticker cards, or production answer paths.",
            "Tier B means research bench only, not deployment readiness.",
            "No buy/sell/paper/live order, account action, or capital deployment authority is created.",
            "Clean validation is not owner approval to apply labels.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(out),
                "summary": report.get("summary"),
                "validation": {
                    "status": as_dict(report.get("validation")).get("status"),
                    "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
                },
            },
            indent=2,
        )
    )
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
