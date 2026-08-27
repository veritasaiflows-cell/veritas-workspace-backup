#!/usr/bin/env python3
"""Emit read-only parallel repair packets for Tier A trade-grade depth gaps.

This is an orchestration/proof surface, not a source-open research writer.
It converts the Tier A coverage gate into exact parallel repair lanes for:

Phase A: cohort alignment
Phase B: thesis synthesis
Phase C: quote/freshness refresh
Phase D: competitive moat structuring
Phase E: sector/proxy context
Phase F: response-contract, skill, and retail-routing integration

No SQL, portfolio, card, full-answer, customer, or execution surface is
mutated by this script.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

GATE_PATH = TMP / "tier-a-trade-grade-coverage-gate.json"
AGGREGATE_OUT = TMP / "tier-a-depth-repair-phase-execution-packet.json"
PHASE_A_OUT = TMP / "tier-a-depth-phase-a-cohort-alignment.json"
PHASE_B_OUT = TMP / "tier-a-depth-phase-b-thesis-synthesis.json"
PHASE_C_OUT = TMP / "tier-a-depth-phase-c-freshness-refresh.json"
PHASE_D_OUT = TMP / "tier-a-depth-phase-d-moat-structuring.json"
PHASE_E_OUT = TMP / "tier-a-depth-phase-e-sector-context.json"
PHASE_F_OUT = TMP / "tier-a-depth-phase-f-response-skills-retail-routing.json"
PHASE_A_RECONCILIATION_PATH = TMP / "tier-a-cohort-alignment-reconciliation.json"
SKILL_PATHS = {
    "veritas-response-contract": ROOT / "skills" / "veritas-response-contract" / "SKILL.md",
    "veritas-wf78-tier-promotion-spine": ROOT / "skills" / "veritas-wf78-tier-promotion-spine" / "SKILL.md",
    "veritas-intelligence-effort-router": ROOT / "skills" / "veritas-intelligence-effort-router" / "SKILL.md",
}

SCHEMA = "veritas.tier_a_depth_repair_phase_executor.v1"

AUTHORITY_BOUNDARY = {
    "artifact_role": "tier_a_depth_repair_parallel_phase_packet",
    "review_only": True,
    "proof_packet_only": True,
    "sql_write_allowed": False,
    "ticker_card_mutation_allowed": False,
    "full_answer_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_output_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def skill_gate_evidence() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name, path in SKILL_PATHS.items():
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        rows[name] = {
            "path": rel(path),
            "exists": path.exists(),
            "mentions_tier_a_gate": "tier_a_trade_grade_coverage_gate.py" in text,
            "mentions_depth": "depth" in text.lower(),
        }
    return rows


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique_tickers(rows: list[dict[str, Any]], blocker: str | None = None) -> list[str]:
    tickers: set[str] = set()
    for row in rows:
        if blocker and blocker not in as_list(row.get("depth_blockers")):
            continue
        ticker = row.get("ticker")
        if isinstance(ticker, str) and ticker:
            tickers.add(ticker)
    return sorted(tickers)


def rows_with_blocker(rows: list[dict[str, Any]], blocker: str) -> list[dict[str, Any]]:
    return [row for row in rows if blocker in as_list(row.get("depth_blockers"))]


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def lane_batch(
    *,
    phase: str,
    blocker: str,
    tickers: list[str],
    max_batch_size: int,
    workstream_prefix: str,
    deliverable: str,
    stop_lines: list[str],
) -> list[dict[str, Any]]:
    batches = []
    for index, batch in enumerate(chunked(tickers, max_batch_size), start=1):
        batches.append(
            {
                "lane": f"{phase}{index}",
                "workstream": f"{workstream_prefix}-{index:02d}",
                "blocker": blocker,
                "tickers": batch,
                "ticker_count": len(batch),
                "deliverable": deliverable,
                "acceptance": [
                    "source paths and timestamps captured",
                    "claims are source-backed and no model-only inference is promoted",
                    "authority flags remain false",
                    "rerun tier_a_trade_grade_coverage_gate after integration",
                ],
                "stop_lines": stop_lines,
            }
        )
    return batches


def gate_rows(gate: dict[str, Any]) -> list[dict[str, Any]]:
    cohorts = as_dict(gate.get("cohorts"))
    rows = []
    for row in as_list(cohorts.get("data_plane_tier_a")):
        if isinstance(row, dict):
            rows.append(dict(row))
    return rows


def finance_rows(gate: dict[str, Any]) -> list[dict[str, Any]]:
    cohorts = as_dict(gate.get("cohorts"))
    rows = []
    for row in as_list(cohorts.get("finance_canon_tier_a")):
        if isinstance(row, dict):
            rows.append(dict(row))
    return rows


def build_phase_a(now: str, gate: dict[str, Any]) -> dict[str, Any]:
    diff = as_dict(gate.get("tier_definition_diff"))
    finance_only = as_list(diff.get("finance_only"))
    data_plane_only = as_list(diff.get("data_plane_only"))
    mismatch = bool(finance_only or data_plane_only)
    reconciliation = read_json(PHASE_A_RECONCILIATION_PATH)
    reconciliation_valid = as_dict(reconciliation.get("validation")).get("status") == "ok"
    reconciled = mismatch and reconciliation_valid
    if reconciled:
        status = "cohort_alignment_reconciled_with_durable_sync_followup"
    else:
        status = "cohort_alignment_required" if mismatch else "cohort_alignment_ok"
    return {
        "schema": f"{SCHEMA}.phase_a",
        "generated_at_utc": now,
        "phase": "A",
        "name": "cohort_alignment",
        "status": status,
        "parallelizable": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "problem": "Finance canon and data-plane Tier A cohorts differ; depth metrics should be based on an aligned cohort before migration is called complete.",
        "cohort_counts": {
            "finance_tier_a_count": diff.get("finance_tier_a_count"),
            "data_plane_tier_a_count": diff.get("data_plane_tier_a_count"),
            "finance_a_ready": diff.get("finance_a_ready"),
            "data_plane_a_ready": diff.get("data_plane_a_ready"),
        },
        "mismatches": {
            "finance_only": finance_only,
            "data_plane_only": data_plane_only,
        },
        "reconciliation_packet": {
            "path": rel(PHASE_A_RECONCILIATION_PATH),
            "exists": PHASE_A_RECONCILIATION_PATH.exists(),
            "status": reconciliation.get("status"),
            "summary": reconciliation.get("summary"),
        },
        "lane_batches": [] if reconciled or not mismatch else [
            {
                "lane": "A1",
                "workstream": "tier-a-cohort-reconciliation",
                "tickers": sorted(set(finance_only + data_plane_only)),
                "deliverable": "reconciliation note explaining whether each mismatch is ETF/proxy scope, legacy SQL-canon residue, or data-plane omission",
                "acceptance": [
                    "no SQL writes from this packet",
                    "exact proposed owner or producer of alignment identified",
                    "gate rerun shows finance/data-plane definition mismatch resolved or explicitly waived",
                ],
                "stop_lines": [
                    "Do not mutate state/finance/finance-canon.sqlite.",
                    "Do not change universe membership without the existing gated apply path.",
                ],
            }
        ],
        "recommended_followup_commands": [
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
            "python scripts\\tier_a_trade_grade_coverage_gate.py --write --validate",
        ],
    }


def build_phase_b(now: str, gate: dict[str, Any]) -> dict[str, Any]:
    rows = gate_rows(gate)
    blocked_rows = rows_with_blocker(rows, "thesis_not_synthesized")
    tickers = unique_tickers(rows, "thesis_not_synthesized")
    return {
        "schema": f"{SCHEMA}.phase_b",
        "generated_at_utc": now,
        "phase": "B",
        "name": "source_open_thesis_synthesis",
        "status": "parallel_source_open_repair_ready" if tickers else "complete_no_thesis_blockers",
        "parallelizable": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "blocker": "thesis_not_synthesized",
        "row_count": len(blocked_rows),
        "unique_ticker_count": len(tickers),
        "tickers": tickers,
        "lane_batches": lane_batch(
            phase="B",
            blocker="thesis_not_synthesized",
            tickers=tickers,
            max_batch_size=5,
            workstream_prefix="tier-a-thesis-source-open",
            deliverable="source-open thesis/bull/bear synthesis packet per ticker",
            stop_lines=[
                "No material thesis claim without source path and timestamp.",
                "No buy/sell/hold/allocation/execution language.",
                "Do not write ticker cards or full answers from helper lanes; produce review packets only.",
            ],
        ),
        "source_requirements": [
            "official earnings/SEC/IR source",
            "current fundamentals and valuation source",
            "risk/invalidation source",
            "technical/entry context source",
            "clear bull, bear, and invalidation summary",
        ],
    }


def build_phase_c(now: str, gate: dict[str, Any]) -> dict[str, Any]:
    rows = gate_rows(gate)
    blocked_rows = rows_with_blocker(rows, "fresh_quote_required")
    tickers = unique_tickers(rows, "fresh_quote_required")
    lane_batches = []
    if tickers:
        lane_batches = [
            {
                "lane": "C1",
                "workstream": "tier-a-market-window-freshness-refresh",
                "tickers": tickers,
                "ticker_count": len(tickers),
                "deliverable": "fresh quote/band/stop refresh proof for Tier A, preferably during an open market or post-close final quote window",
                "acceptance": [
                    "quote timestamp and market date captured",
                    "band status recomputed",
                    "trade-grade full answers rebuilt after refresh",
                    "no execution approval inferred",
                ],
                "stop_lines": [
                    "Do not submit paper/live orders.",
                    "Do not call stale quotes fresh for decision-grade claims.",
                    "Do not mutate entry bands unless the existing bounded entry-band gate independently permits it.",
                ],
            }
        ]
    return {
        "schema": f"{SCHEMA}.phase_c",
        "generated_at_utc": now,
        "phase": "C",
        "name": "quote_and_band_freshness",
        "status": "market_window_refresh_required" if tickers else "complete_no_fresh_quote_blockers",
        "parallelizable": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "blocker": "fresh_quote_required",
        "row_count": len(blocked_rows),
        "unique_ticker_count": len(tickers),
        "tickers": tickers,
        "lane_batches": lane_batches,
        "recommended_followup_commands": [
            "python scripts\\trade_grade_os_freshness_cron_runner.py --component all --full-answer-mode changed --write --validate",
            "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
            "python scripts\\tier_a_trade_grade_coverage_gate.py --write --validate",
        ],
    }


def build_phase_d(now: str, gate: dict[str, Any]) -> dict[str, Any]:
    rows = gate_rows(gate)
    blocked_rows = rows_with_blocker(rows, "competitive_moat_not_structured")
    tickers = unique_tickers(rows, "competitive_moat_not_structured")
    return {
        "schema": f"{SCHEMA}.phase_d",
        "generated_at_utc": now,
        "phase": "D",
        "name": "competitive_moat_structuring",
        "status": "parallel_source_open_repair_ready" if tickers else "complete_no_moat_blockers",
        "parallelizable": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "blocker": "competitive_moat_not_structured",
        "row_count": len(blocked_rows),
        "unique_ticker_count": len(tickers),
        "tickers": tickers,
        "lane_batches": lane_batch(
            phase="D",
            blocker="competitive_moat_not_structured",
            tickers=tickers,
            max_batch_size=5,
            workstream_prefix="tier-a-moat-source-open",
            deliverable="structured moat packet per company with source-backed evidence and counterpoints",
            stop_lines=[
                "No moat claim without source path and timestamp.",
                "Do not infer durable moat from market cap or price action alone.",
                "Do not write canon/card/full-answer surfaces directly from helper lanes.",
            ],
        ),
        "source_requirements": [
            "official annual/quarterly filing or IR source",
            "segment/revenue concentration evidence",
            "competitive positioning evidence",
            "risk/counter-moat evidence",
        ],
    }


def build_phase_e(now: str, gate: dict[str, Any]) -> dict[str, Any]:
    rows = gate_rows(gate)
    sector_rows = rows_with_blocker(rows, "current_sector_performance_missing")
    etf_rows = rows_with_blocker(rows, "etf_or_macro_proxy_profile_missing")
    sector_tickers = unique_tickers(rows, "current_sector_performance_missing")
    etf_tickers = unique_tickers(rows, "etf_or_macro_proxy_profile_missing")
    return {
        "schema": f"{SCHEMA}.phase_e",
        "generated_at_utc": now,
        "phase": "E",
        "name": "sector_and_proxy_context",
        "status": "parallel_context_repair_ready" if sector_tickers or etf_tickers else "complete_no_sector_or_proxy_blockers",
        "parallelizable": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "blockers": {
            "current_sector_performance_missing": {
                "row_count": len(sector_rows),
                "unique_ticker_count": len(sector_tickers),
                "tickers": sector_tickers,
            },
            "etf_or_macro_proxy_profile_missing": {
                "row_count": len(etf_rows),
                "unique_ticker_count": len(etf_tickers),
                "tickers": etf_tickers,
            },
        },
        "lane_batches": [
            *lane_batch(
                phase="E",
                blocker="current_sector_performance_missing",
                tickers=sector_tickers,
                max_batch_size=6,
                workstream_prefix="tier-a-sector-context",
                deliverable="current sector-relative context packet",
                stop_lines=[
                    "No performance claim without date range and source.",
                    "No customer-facing investment advice.",
                    "Do not write card/full-answer surfaces directly.",
                ],
            ),
            *lane_batch(
                phase="E",
                blocker="etf_or_macro_proxy_profile_missing",
                tickers=etf_tickers,
                max_batch_size=6,
                workstream_prefix="tier-a-etf-proxy-context",
                deliverable="ETF/proxy macro profile packet",
                stop_lines=[
                    "No ETF allocation recommendation.",
                    "No customer-facing suitability language.",
                    "Do not write card/full-answer surfaces directly.",
                ],
            ),
        ],
    }


def build_phase_f(now: str, gate: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(gate.get("summary"))
    retail = as_dict(gate.get("retail_context"))
    skills = skill_gate_evidence()
    skills_applied = all(row.get("exists") and row.get("mentions_tier_a_gate") and row.get("mentions_depth") for row in skills.values())
    return {
        "schema": f"{SCHEMA}.phase_f",
        "generated_at_utc": now,
        "phase": "F",
        "name": "response_contract_skills_and_retail_truth_routing",
        "status": "complete_skills_applied_retail_boundary_preserved" if skills_applied else "skill_workshop_update_recommended",
        "parallelizable": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "problem": "The response layer must distinguish coverage floor, depth readiness, trade-grade readiness, approval, and customer-output readiness.",
        "response_contract_requirements": [
            "Say structural coverage floor separately from depth readiness.",
            "Never use 17/17 sections as shorthand for decision-grade readiness.",
            "Report blocker-instance counts and unique ticker counts distinctly.",
            "State customer-output and capital/execution boundaries whenever retail routing or trade-grade language appears.",
        ],
        "skills_to_update_or_reference": [
            {
                "skill": "veritas-response-contract",
                "change": "Add Tier A coverage floor vs depth readiness wording and blocker-count interpretation.",
            },
            {
                "skill": "veritas-wf78-tier-promotion-spine",
                "change": "Add Tier A depth gate after SQL-canon/WF85 parity and before A-READY/customer-output language.",
            },
            {
                "skill": "veritas-intelligence-effort-router",
                "change": "Reference tier_a_trade_grade_coverage_gate before material Tier A readiness claims.",
            },
        ],
        "skill_gate_evidence": skills,
        "retail_truth_routing_state": {
            "retail_automation_control_plane": as_dict(retail.get("retail_automation_control_plane")),
            "sql_canon_retail_grade_readiness": as_dict(retail.get("sql_canon_retail_grade_readiness")),
            "customer_output_decision_packet": as_dict(retail.get("customer_output_decision_packet")),
        },
        "current_gate_summary": summary,
        "acceptance": [
            "Skill Workshop proposal applied or live skill evidence references the Tier A depth gate.",
            "Retail routing stays internal/review-only while customer-output gate is blocked.",
            "Final answers cite this gate when discussing Tier A coverage.",
        ],
    }


def build_packets() -> dict[str, dict[str, Any]]:
    gate = read_json(GATE_PATH)
    now = utc_now()
    phases = {
        "A": build_phase_a(now, gate),
        "B": build_phase_b(now, gate),
        "C": build_phase_c(now, gate),
        "D": build_phase_d(now, gate),
        "E": build_phase_e(now, gate),
        "F": build_phase_f(now, gate),
    }
    ready_parallel_lanes = sum(len(as_list(phase.get("lane_batches"))) for phase in phases.values())
    all_repairs_complete = ready_parallel_lanes == 0
    aggregate_status = (
        "depth_repairs_complete_customer_and_decision_still_blocked"
        if all_repairs_complete
        else "parallel_depth_repair_ready_customer_and_decision_blocked"
    )
    recommended_parallel_sequence = [
        "Run Phase A once to reconcile the Tier A cohort denominator.",
        "Run Phases B, D, and E in parallel source-open helper lanes.",
        "Run Phase C in the next valid market/post-close quote window.",
        "Run Phase F through Skill Workshop and response-contract governance.",
        "Rerun tier_a_trade_grade_coverage_gate and WF85 assembler after repair packets integrate.",
    ]
    if all_repairs_complete:
        recommended_parallel_sequence = [
            "All Phase A-F repair lanes are complete against the current Tier A depth gate.",
            "WF85 decision-grade and approval-ready claims still remain blocked until the downstream decision gates clear.",
            "Rerun the freshness and coverage chain on the next market/post-close cycle if Tier A inputs change.",
        ]
    aggregate = {
        "schema": SCHEMA,
        "generated_at_utc": now,
        "status": aggregate_status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_gate": rel(GATE_PATH),
        "input_gate_status": gate.get("status"),
        "phase_order": ["A", "B", "C", "D", "E", "F"],
        "phases": {
            phase_id: {
                "name": phase.get("name"),
                "status": phase.get("status"),
                "parallelizable": phase.get("parallelizable"),
                "lane_count": len(as_list(phase.get("lane_batches"))),
            }
            for phase_id, phase in phases.items()
        },
        "summary": {
            "coverage_floor_ok": as_dict(gate.get("summary")).get("coverage_floor_ok"),
            "depth_ready_all_tier_a": as_dict(gate.get("summary")).get("depth_ready_all_tier_a"),
            "depth_ready_a_ready": as_dict(gate.get("summary")).get("depth_ready_a_ready"),
            "decision_grade_allowed_count": as_dict(gate.get("summary")).get("decision_grade_allowed_count"),
            "ready_parallel_lane_count": ready_parallel_lanes,
            "customer_output_allowed": False,
            "capital_or_execution_allowed": False,
        },
        "recommended_parallel_sequence": recommended_parallel_sequence,
        "phase_outputs": {
            "A": rel(PHASE_A_OUT),
            "B": rel(PHASE_B_OUT),
            "C": rel(PHASE_C_OUT),
            "D": rel(PHASE_D_OUT),
            "E": rel(PHASE_E_OUT),
            "F": rel(PHASE_F_OUT),
        },
        "stop_lines": [
            "No card/full-answer/canon/portfolio/customer/execution mutation is performed here.",
            "This packet authorizes parallel review lanes only.",
            "Decision-grade and customer-output language remain blocked until downstream gates clear.",
        ],
    }
    return {"aggregate": aggregate, **phases}


def validate_packets(packets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    aggregate = packets["aggregate"]
    add("gate_input_exists", GATE_PATH.exists(), rel(GATE_PATH))
    add("six_phases_present", set(packets) == {"aggregate", "A", "B", "C", "D", "E", "F"})
    add("authority_no_customer_output", aggregate["authority_boundary"]["customer_or_external_output_allowed"] is False)
    add("authority_no_execution", aggregate["authority_boundary"]["paper_or_live_execution_allowed"] is False)
    add("authority_no_capital", aggregate["authority_boundary"]["capital_deployment_approved"] is False)
    add(
        "phase_b_ready_or_complete",
        packets["B"].get("unique_ticker_count", 0) > 0 or packets["B"].get("status") == "complete_no_thesis_blockers",
        packets["B"].get("status"),
    )
    add(
        "phase_c_ready_or_complete",
        packets["C"].get("unique_ticker_count", 0) > 0 or packets["C"].get("status") == "complete_no_fresh_quote_blockers",
        packets["C"].get("status"),
    )
    add(
        "phase_d_ready_or_complete",
        packets["D"].get("unique_ticker_count", 0) > 0 or packets["D"].get("status") == "complete_no_moat_blockers",
        packets["D"].get("status"),
    )
    add(
        "phase_e_ready_or_complete",
        bool(as_dict(packets["E"].get("blockers")).get("current_sector_performance_missing", {}).get("unique_ticker_count"))
        or bool(as_dict(packets["E"].get("blockers")).get("etf_or_macro_proxy_profile_missing", {}).get("unique_ticker_count"))
        or packets["E"].get("status") == "complete_no_sector_or_proxy_blockers",
        packets["E"].get("status"),
    )
    add(
        "phase_f_names_response_contract",
        any(item.get("skill") == "veritas-response-contract" for item in as_list(packets["F"].get("skills_to_update_or_reference"))),
    )
    add(
        "aggregate_has_parallel_lanes_or_repairs_complete",
        aggregate["summary"]["ready_parallel_lane_count"] > 0
        or aggregate.get("status") == "depth_repairs_complete_customer_and_decision_still_blocked",
        aggregate.get("status"),
    )
    return checks


def write_packets(packets: dict[str, dict[str, Any]]) -> None:
    atomic_write_json(AGGREGATE_OUT, packets["aggregate"])
    atomic_write_json(PHASE_A_OUT, packets["A"])
    atomic_write_json(PHASE_B_OUT, packets["B"])
    atomic_write_json(PHASE_C_OUT, packets["C"])
    atomic_write_json(PHASE_D_OUT, packets["D"])
    atomic_write_json(PHASE_E_OUT, packets["E"])
    atomic_write_json(PHASE_F_OUT, packets["F"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Tier A depth repair parallel phase packets")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packets = build_packets()
    if args.validate:
        checks = validate_packets(packets)
        failed = [check for check in checks if not check["ok"]]
        packets["aggregate"]["validation"] = {
            "status": "ok" if not failed else "blocked",
            "errors": failed,
            "checks": checks,
        }
    if args.write:
        write_packets(packets)
    print(
        json.dumps(
            {
                "status": packets["aggregate"]["status"],
                "summary": packets["aggregate"]["summary"],
                "phase_statuses": packets["aggregate"]["phases"],
                "validation": packets["aggregate"].get("validation"),
            },
            indent=2,
        )
    )
    return 0 if packets["aggregate"].get("validation", {}).get("status", "ok") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
