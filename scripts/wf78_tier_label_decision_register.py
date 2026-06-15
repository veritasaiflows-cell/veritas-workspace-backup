#!/usr/bin/env python3
"""Register owner-approved WF78 tier label decisions without applying labels.

This is the approval ledger for label-only decisions. It records exact owner
approval against final-promotion packets, but it does not mutate the universe,
canon, portfolio notes, SQL, ticker cards, or execution surfaces.
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
DEFAULT_OUT = TMP / "wf78-tier-label-decision-register.json"
TIER_A_PACKET = TMP / "wf78-tier-a-final-promotion-packet.json"
TIER_B_PACKET = TMP / "wf78-tier-b-final-promotion-packet.json"
SCHEMA = "veritas.wf78_tier_label_decision_register.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "approval_register_only": True,
    "tier_label_apply_allowed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "approval_register_only"}
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


def normalize_tickers(values: list[str]) -> list[str]:
    return sorted({str(value).upper().strip() for value in values if str(value).strip()})


def decision_id_for(tickers: list[str]) -> str:
    scope = "-".join(tickers).lower()
    return f"wf78-tier-b-research-bench-labels-{scope}-2026-06-05"


def build_tier_b_record(approval_reference: str, approval_text: str, packet_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    packet = load_dict(packet_path)
    summary = as_dict(packet.get("summary"))
    eligible = normalize_tickers([str(item) for item in as_list(summary.get("eligible_tickers"))])
    expected = eligible
    checks: list[dict[str, Any]] = []
    lowered = approval_text.lower()
    add_check(checks, "tier_b_packet_present", bool(packet), rel(packet_path))
    add_check(checks, "tier_b_packet_owner_decision_required", packet.get("status") == "owner_decision_required", packet.get("status"))
    add_check(checks, "tier_b_packet_validation_ok", as_dict(packet.get("validation")).get("status") == "ok", as_dict(packet.get("validation")).get("status"))
    add_check(checks, "tier_b_eligible_tickers_present", bool(expected), {"eligible": eligible})
    add_check(checks, "approval_text_mentions_tier_b_research_bench", "tier b research-bench labels only" in lowered or "tier b research bench labels only" in lowered, approval_text)
    add_check(checks, "approval_text_mentions_all_tickers", all(ticker.lower() in lowered for ticker in expected), approval_text)
    add_check(checks, "approval_text_not_trade_or_execution", not any(term in lowered for term in ("buy", "sell", "trade", "execute", "paper order", "live order")), approval_text)
    record = {
        "decision_id": decision_id_for(expected),
        "decision_type": "tier_b_research_bench_label_only",
        "approval_status": "approved_label_only",
        "approval_reference": approval_reference,
        "approval_text": approval_text,
        "approved_at_local": "2026-06-05 11:36 MST",
        "approved_tickers": expected,
        "source_packet": rel(packet_path),
        "label_semantics": {
            "tier": "B",
            "role": "research_bench",
            "deployment_ready": False,
            "trade_or_execution_approval": False,
            "canon_or_portfolio_mutation": False,
            "separate_apply_path_required_before_any_roster_surface_mutation": True,
        },
        "record_only": True,
        "applied_to_universe": False,
        "owner_approval_inferred": False,
    }
    return record, checks


def existing_records(path: Path) -> list[dict[str, Any]]:
    existing = load_dict(path)
    return [record for record in as_list(existing.get("records")) if isinstance(record, dict)]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    out = args.out if args.out.is_absolute() else ROOT / args.out
    records: list[dict[str, Any]] = existing_records(out)
    if args.approve_tier_b:
        packet_path = args.tier_b_packet if args.tier_b_packet.is_absolute() else ROOT / args.tier_b_packet
        record, tier_checks = build_tier_b_record(args.approval_reference, args.approval_text, packet_path)
        records = [existing for existing in records if existing.get("decision_id") != record.get("decision_id")]
        records.append(record)
        checks.extend(tier_checks)
    add_check(checks, "at_least_one_record", bool(records), len(records))
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    approved_tier_b = sorted({ticker for record in records if record.get("decision_type") == "tier_b_research_bench_label_only" for ticker in as_list(record.get("approved_tickers"))})
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier Label Decision Register",
        "purpose": "Record exact owner-approved tier-label decisions without applying labels or mutating any authority-bearing surface.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "tier_a_final_packet": rel(TIER_A_PACKET),
            "tier_b_final_packet": rel(args.tier_b_packet if args.tier_b_packet.is_absolute() else ROOT / args.tier_b_packet),
        },
        "summary": {
            "record_count": len(records),
            "approved_tier_b_research_bench_label_count": len(approved_tier_b),
            "approved_tier_b_research_bench_labels": approved_tier_b,
            "tier_label_apply_executed": False,
            "universe_mutation_executed": False,
            "next_safe_action": "Build a separate gated label-sync preview if formal roster surfaces need to consume these approvals; do not mutate universe/canon/portfolio from this register.",
        },
        "records": records,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This register records label approval only; it does not apply labels.",
            "No universe, canon, portfolio, ticker-card, SQL, customer, paper, live, brokerage, or account mutation.",
            "No capital deployment, paper/live order, or trade approval.",
            "No owner approval inference beyond the exact recorded label-only decision.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-tier-b", action="store_true")
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--approval-text", required=True)
    parser.add_argument("--tier-b-packet", type=Path, default=TIER_B_PACKET)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(args)
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
