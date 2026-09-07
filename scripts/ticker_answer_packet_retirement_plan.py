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
from finance_sql_canon_access import FinanceSqlCanonAccess, strategic_answer_route_context

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PACKET_DIR = TMP / "ticker-answer-packets"
ARCHIVE_DIR = ROOT / "09. Archive" / "WF85 Legacy Ticker Answer Packets" / "preview"
PARITY_ROLLUP = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
RETIREMENT_READINESS = TMP / "canonical-finance-data-plane-retirement-readiness.json"
DEFAULT_OUT = TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json"
TOMBSTONE_SOURCE = ROOT / "scripts" / "ticker_answer_packet.py"

SCHEMA = "veritas.ticker_answer_packet_retirement_plan.v1"
TOMBSTONE_SCHEMA = "veritas.ticker_answer_packet.retired_compatibility.v1"
TOMBSTONE_MARKERS = (
    TOMBSTONE_SCHEMA,
    '"compatibility_mode": "deny_only"',
    '"legacy_read_allowed": False',
    '"legacy_write_allowed": False',
    '"filesystem_mutation_allowed": False',
)

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

REFERENCE_CLASSIFICATIONS = {
    "scripts/alerts_os_pivot_validator.py": (
        "retired_surface_absence_validator",
        False,
        "pivot validation lists the retired directory only to prove that it remains absent",
    ),
    "scripts/canonical_finance_data_plane_retirement_readiness.py": (
        "retirement_governance_owner",
        False,
        "readiness planner intentionally tracks ticker-answer-packets as a candidate surface",
    ),
    "scripts/concurrent_lane_manager.py": (
        "archive_proof_path_resolver",
        False,
        "lane proof validator resolves approved archived WF85 packet paths; it is not an active packet consumer",
    ),
    "scripts/ticker_answer_packet.py": (
        "deny_only_compatibility_tombstone",
        False,
        "retired historical surface denies every legacy read and write invocation",
    ),
    "scripts/ticker_answer_packet_retirement_plan.py": (
        "current_retirement_planner",
        False,
        "this planner must reference the candidate surface it is evaluating",
    ),
    "scripts/legacy_42_lifecycle_gate_packet.py": (
        "legacy_lifecycle_governance_packet",
        False,
        "lifecycle gate references the candidate surface as governance proof, not as an active packet consumer",
    ),
    "scripts/retire_portfolio_paper_runtime_state.py": (
        "historical_archive_governance",
        False,
        "retirement tooling lists the historical directory as an archive candidate, not as an active reader",
    ),
    "scripts/sql_canon_parallel_phase_executor.py": (
        "parallel_phase_governance_packet",
        False,
        "parallel phase executor references the candidate surface to build review packets only",
    ),
    "scripts/test_wf88_route_contraction_packet.py": (
        "deny_only_tombstone_regression_test",
        False,
        "the test hashes retired output locations to prove every legacy CLI shape performs zero writes",
    ),
    "scripts/trade_grade_full_answer_assembler.py": (
        "retired_historical_emitter_residue",
        False,
        "standalone legacy emitter residue is historical evidence, not an active replacement owner",
    ),
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


def archived_legacy_packet_tickers() -> list[str]:
    """Return the archived legacy answer-packet tickers without importing retired WF78 code."""
    tickers = []
    for path in sorted(ARCHIVE_DIR.glob("*.current.json")):
        ticker = path.name.removesuffix(".current.json").upper()
        if ticker:
            tickers.append(ticker)
    return tickers


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
            if (
                path.is_file()
                and path.suffix.lower() in suffixes
                and "__pycache__" not in path.parts
                and "graphify-out" not in path.parts
            ):
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


def reference_inventory(refs: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ref in refs:
        classification, blocking, rationale = REFERENCE_CLASSIFICATIONS.get(
            ref,
            ("unclassified_active_reader", True, "unclassified reference must be migrated or classified before retirement"),
        )
        rows.append(
            {
                "path": ref,
                "classification": classification,
                "blocking": blocking,
                "rationale": rationale,
            }
        )
    return rows


def packet_status_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker in archived_legacy_packet_tickers():
        path = PACKET_DIR / f"{ticker}.current.json"
        archived_path = ARCHIVE_DIR / path.name
        active_exists = path.exists()
        archived_exists = archived_path.exists()
        payload_path = path if active_exists else archived_path
        payload = as_dict(load_json(payload_path, {}))
        rows.append({
            "ticker": ticker,
            "path": rel(path),
            "archive_path": rel(archived_path),
            "exists": active_exists,
            "archived": archived_exists,
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


def tombstone_status() -> dict[str, Any]:
    """Confirm the retired wrapper is the exact deny-only, zero-write tombstone."""
    try:
        source = TOMBSTONE_SOURCE.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "status": "blocked",
            "path": rel(TOMBSTONE_SOURCE),
            "schema": TOMBSTONE_SCHEMA,
            "missing_markers": list(TOMBSTONE_MARKERS),
            "error": str(exc),
        }
    missing = [marker for marker in TOMBSTONE_MARKERS if marker not in source]
    return {
        "status": "confirmed" if not missing else "blocked",
        "path": rel(TOMBSTONE_SOURCE),
        "schema": TOMBSTONE_SCHEMA,
        "missing_markers": missing,
        "deny_only": not missing,
        "legacy_reads_allowed": False,
        "legacy_writes_allowed": False,
    }


def build_packet() -> dict[str, Any]:
    sql_canon = FinanceSqlCanonAccess()
    sql_canon_validation = sql_canon.validate()
    sql_canon_registry: dict[str, Any] = {}
    if sql_canon_validation.get("status") == "ok":
        sql_canon_registry = sql_canon.migration_registry_summary()
    route = strategic_answer_route_context(consumer="ticker_answer_packet_retirement_plan")
    parity = as_dict(load_json(PARITY_ROLLUP, {}))
    parity_summary = as_dict(parity.get("summary"))
    parity_sql_scope = as_dict(parity.get("sql_canon_scope"))
    retirement = as_dict(load_json(RETIREMENT_READINESS, {}))
    retirement_summary = as_dict(retirement.get("summary"))
    rows = packet_status_rows()
    refs = active_references()
    reference_rows = reference_inventory(refs)
    blocking_refs = [row for row in reference_rows if row["blocking"]]
    wrapper_tombstone = tombstone_status()
    all_from_assembler = all(row["built_from_assembler"] for row in rows)
    all_archived = all(row["archived"] and not row["exists"] for row in rows)
    all_present = all((row["exists"] or row["archived"]) and row["required_legacy_fields_present"] for row in rows)
    parity_ready = route.get("status") == "ok"
    validation_errors: list[dict[str, Any]] = []
    if not all_present:
        validation_errors.append({"check": "all_legacy_packets_present_with_required_fields", "detail": [row for row in rows if not row["exists"] or not row["required_legacy_fields_present"]]})
    if not all_from_assembler:
        validation_errors.append({"check": "all_legacy_packets_generated_from_assembler", "detail": [row for row in rows if not row["built_from_assembler"]]})
    if not parity_ready:
        validation_errors.append({"check": "sql_first_route_ready_for_legacy_packet_retirement", "detail": route.get("validation")})
    if wrapper_tombstone.get("status") != "confirmed":
        validation_errors.append({"check": "ticker_answer_packet_deny_only_tombstone", "detail": wrapper_tombstone})
    if sql_canon_validation.get("status") != "ok":
        validation_errors.append({"check": "sql_canon_access_ready", "detail": sql_canon_validation.get("errors")})
    p0_status = as_dict(route.get("p0_registry_lane_status"))
    if p0_status.get("ok") is not True:
        validation_errors.append({"check": "sql_canon_p0_registry_lane", "detail": p0_status})
    if blocking_refs:
        validation_errors.append({"check": "no_unclassified_active_packet_references", "detail": blocking_refs})
    validation_errors.append({
        "check": "retired_answer_packet_family_has_no_active_writer_or_current_replacement",
        "detail": {
            "wrapper_tombstone_status": wrapper_tombstone.get("status"),
            "operational_replacement_claimed": False,
            "historical_snapshot_structure_is_current_evidence": False,
        },
    })
    planning_ready = False
    archive_ready_now = False
    archive_completed = all_archived and all_present
    status = "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Owner-review retirement plan for tmp/ticker-answer-packets after WF85 full-answer assembler migration.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "candidate_surface": {
            "path": "tmp/ticker-answer-packets",
            "owner_before_retirement": "legacy ticker answer packet response layer",
            "replacement_owner": None,
            "replacement_artifact": None,
            "compatibility_mode": "deny_only_tombstone_no_reads_or_writes",
            "operational_replacement_claimed": False,
            "wrapper_tombstone": wrapper_tombstone,
        },
        "sql_canon_migration_context": {
            "access_validation_status": sql_canon_validation.get("status"),
            "registry_summary": sql_canon_registry,
            "parity_sql_scope_status": parity_sql_scope.get("status"),
            "parity_sql_scope_validation": parity_sql_scope.get("validation"),
            "answer_route_policy": route.get("answer_route_policy"),
            "legacy_42_retired_from_blocking": route.get("legacy_42_retired_from_blocking"),
            "legacy_42_count_advisory_only": route.get("legacy_42_count_advisory_only"),
            "sql_canon_production_answer_count": parity_summary.get("sql_canon_production_answer_count"),
            "sql_canon_production_scope_diff": parity_summary.get("sql_canon_production_scope_diff"),
            "retirement_planning_uses_sql_canon_scope": True,
            "global_full_answer_parity_status_advisory": parity.get("status"),
        },
        "summary": {
            "legacy_packet_count": len(rows),
            "legacy_packets_archived_count": sum(1 for row in rows if row["archived"] and not row["exists"]),
            "legacy_packets_present_with_required_fields": all_present,
            "legacy_packets_generated_from_assembler": all_from_assembler,
            "historical_assembler_lineage_only": True,
            "full_answer_parity_status": parity.get("status"),
            "production_answer_packet_retirement_planning_ready": False,
            "current_operational_replacement_ready": False,
            "global_full_answer_parity_blocks_legacy_packet_retirement": False,
            "sql_canon_access_status": sql_canon_validation.get("status"),
            "sql_canon_scope_status": parity_sql_scope.get("status"),
            "sql_canon_p0_registry_count": as_dict(sql_canon_registry.get("priority_counts")).get("P0"),
            "sql_canon_p0_registry_lane_status": p0_status,
            "total_reference_count": len(refs),
            "compatibility_or_governance_reference_count": len(refs) - len(blocking_refs),
            "active_reference_count": len(blocking_refs),
            "archive_ready_now": archive_ready_now,
            "archive_completed": archive_completed,
            "delete_ready_now": False,
            "apply_allowed_now": False,
            "planning_ready": planning_ready,
            "retirement_readiness_summary": retirement_summary,
        },
        "active_references": [row["path"] for row in blocking_refs],
        "reference_inventory": reference_rows,
        "exact_archive_candidates": [
            row["path"]
            for row in rows
            if row["exists"] and row["built_from_assembler"] and row["required_legacy_fields_present"]
        ],
        "proposed_archive_destination": "09. Archive/WF85 Legacy Ticker Answer Packets/preview",
        "packet_rows": rows,
        "approval_sequence": [
            "Keep ticker_answer_packet.py as a deny-only historical tombstone.",
            "Keep archived legacy packet artifacts as non-current historical evidence; do not regenerate them.",
            "Review remaining references and classify them as governance-only residue or migrate them to a current owner.",
            "Use current finance-intelligence front doors without claiming replacement equivalence for this retired packet family.",
            "Prepare a separate scoped lifecycle packet before any archive, delete, move, or cleanup action.",
            "Ask Randall for exact archive/delete/apply approval before any lifecycle action.",
        ],
        "validation": {
            "status": "blocked",
            "errors": validation_errors,
            "warnings": [
                "Archived packet structure and stale generated artifacts are historical evidence only.",
                "The standalone legacy emitter and other classified governance references remain residue.",
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
    if args.validate and packet["status"] not in {"planning_ready", "archived"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
