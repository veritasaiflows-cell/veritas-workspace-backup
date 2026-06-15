#!/usr/bin/env python3
"""Prepare a planning-only retirement packet for ticker answer packets.

This packet is owner-review evidence only. It never archives, deletes, moves,
rewrites, or applies any lifecycle action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PACKET_DIR = TMP / "ticker-answer-packets"
ASSEMBLER_ROLLUP = TMP / "trade-grade-full-answer-assembler.json"
PARITY_ROLLUP = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
RETIREMENT_READINESS = TMP / "canonical-finance-data-plane-retirement-readiness.json"
DEFAULT_OUT = TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json"

SCHEMA = "veritas.ticker_answer_packet_retirement_plan.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "planning_only": True,
    "archive_allowed": False,
    "delete_allowed": False,
    "move_allowed": False,
    "apply_allowed": False,
    "source_feeder_retirement_allowed": False,
    "fallback_removal_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_json(path: Path, default: Any = None) -> Any:
    data = load_json_artifact(path)
    return default if data is None else data


def text_files() -> list[Path]:
    roots = [ROOT / "scripts", ROOT / "06. Playbooks", ROOT / "state", ROOT / "apps", ROOT / "TOOLS.md"]
    suffixes = {".py", ".md", ".json", ".ts", ".js", ".txt"}
    out: list[Path] = []
    for root in roots:
        if root.is_file():
            out.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes and "__pycache__" not in path.parts:
                out.append(path)
    return out


def active_references() -> list[str]:
    needles = {"tmp/ticker-answer-packets", "ticker-answer-packets", "ANSWER_PACKET_DIR", "ANSWER_PACKET_DIR"}
    refs: list[str] = []
    for path in text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            refs.append(rel(path))
    return sorted(set(refs))


def packet_status_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker in legacy_42_tier_tickers():
        path = PACKET_DIR / f"{ticker}.current.json"
        payload = as_dict(load_json(path, {}))
        rows.append({
            "ticker": ticker,
            "path": rel(path),
            "exists": path.exists(),
            "artifact_type": payload.get("artifact_type"),
            "generated_at_utc": payload.get("generated_at_utc"),
            "built_from_assembler": as_dict(payload.get("freshness")).get("built_from_trade_grade_full_answer_assembler") is True,
            "required_legacy_fields_present": all(
                field in payload
                for field in (
                    "thesis_summary",
                    "bull_case",
                    "bear_case",
                    "latest_earnings",
                    "key_financial_metrics",
                    "technical_posture",
                    "portfolio_fit",
                    "recommended_next_action",
                    "authority_boundary",
                )
            ),
        })
    return rows


def build_packet() -> dict[str, Any]:
    assembler = as_dict(load_json(ASSEMBLER_ROLLUP, {}))
    parity = as_dict(load_json(PARITY_ROLLUP, {}))
    parity_summary = as_dict(parity.get("summary"))
    retirement = as_dict(load_json(RETIREMENT_READINESS, {}))
    retirement_summary = as_dict(retirement.get("summary"))
    rows = packet_status_rows()
    refs = active_references()
    all_from_assembler = all(row["built_from_assembler"] for row in rows)
    all_present = all(row["exists"] and row["required_legacy_fields_present"] for row in rows)
    parity_ready = parity.get("status") == "ok" and parity_summary.get("production_answer_packet_retirement_planning_ready") is True
    assembler_ready = assembler.get("status") == "ok" and as_dict(assembler.get("summary")).get("legacy_packet_generation_source") == "trade_grade_full_answer_assembler"
    validation_errors: list[dict[str, Any]] = []
    if not all_present:
        validation_errors.append({"check": "all_legacy_packets_present_with_required_fields", "detail": [row for row in rows if not row["exists"] or not row["required_legacy_fields_present"]]})
    if not all_from_assembler:
        validation_errors.append({"check": "all_legacy_packets_generated_from_assembler", "detail": [row for row in rows if not row["built_from_assembler"]]})
    if not parity_ready:
        validation_errors.append({"check": "production_answer_packet_parity_ready", "detail": parity_summary})
    if not assembler_ready:
        validation_errors.append({"check": "assembler_rollup_ready", "detail": assembler.get("summary")})
    planning_ready = not validation_errors
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "planning_ready" if planning_ready else "blocked",
        "purpose": "Owner-review retirement plan for tmp/ticker-answer-packets after WF85 full-answer assembler migration.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "candidate_surface": {
            "path": "tmp/ticker-answer-packets",
            "owner_before_retirement": "legacy ticker answer packet response layer",
            "replacement_owner": "scripts/trade_grade_full_answer_assembler.py",
            "replacement_artifact": "tmp/trade-grade-full-answer/<TICKER>.json",
            "compatibility_mode": "ticker_answer_packet.py writes compatibility snapshots from the assembler",
        },
        "summary": {
            "legacy_packet_count": len(rows),
            "legacy_packets_present_with_required_fields": all_present,
            "legacy_packets_generated_from_assembler": all_from_assembler,
            "assembler_rollup_status": assembler.get("status"),
            "full_answer_parity_status": parity.get("status"),
            "production_answer_packet_retirement_planning_ready": parity_ready,
            "active_reference_count": len(refs),
            "archive_ready_now": False,
            "delete_ready_now": False,
            "apply_allowed_now": False,
            "planning_ready": planning_ready,
            "retirement_readiness_summary": retirement_summary,
        },
        "active_references": refs,
        "packet_rows": rows,
        "approval_sequence": [
            "Keep ticker_answer_packet.py as a compatibility wrapper while active readers still exist.",
            "Migrate each active reader to trade_grade_full_answer_assembler or finance_intelligence_state ticker front door.",
            "Rerun assembler, legacy packet wrapper, WF84, WF85, full-answer parity, and retirement readiness.",
            "Prove active_reference_count is zero or each remaining reader is compatibility-only.",
            "Prepare DB/file lifecycle packet with rollback path.",
            "Ask Randall for exact archive/delete/apply approval before any action.",
        ],
        "validation": {
            "status": "ok" if planning_ready else "blocked",
            "errors": validation_errors,
            "warnings": [
                "Planning-ready is not archive/delete/apply authority.",
                "Ticker-intelligence cards and WF78 feeders remain retained.",
            ],
        },
        "stop_lines": [
            "No archive/delete/apply/move action.",
            "No feeder/fallback retirement.",
            "No generated packet is canon, approval, or execution authority.",
            "Exact Randall approval is required before any lifecycle action.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    packet = build_packet()
    if args.write:
        atomic_write_json(args.out, packet)
    print(json.dumps({"status": packet["status"], "out": rel(args.out), "summary": packet["summary"], "validation": packet["validation"]}, indent=2))
    if args.validate and packet["status"] not in {"planning_ready"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
