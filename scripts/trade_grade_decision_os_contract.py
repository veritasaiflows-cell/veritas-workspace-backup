#!/usr/bin/env python3
"""Define the WF85 trade-grade decision and approval-card OS contract.

This contract sits above the WF84 data plane. It specifies the review-only
decision-card, approval-card, and parallel-work architecture before any card
engine is implemented.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "trade-grade-decision-os-contract.json"

SCHEMA = "veritas.trade_grade_decision_os_contract.v1"
WORKFLOW_ID = "WF85"
MAX_PAPER_GUARD_CONTEXT_AGE_DAYS = 2
EXPECTED_APPROVAL_DRAFT_COUNT_BEFORE_FRESHNESS_REPAIR = 0

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "decision_support_only": True,
    "approval_card_draft_allowed": True,
    "wf67_paper_request_draft_allowed": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "customer_account_pii_or_suitability_data_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_KEYS = {
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cash_sizing_or_risk_rule_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "customer_account_pii_or_suitability_data_allowed",
    "owner_approval_inferred",
}

INPUTS = [
    {
        "key": "wf84_canonical_finance_data_plane",
        "path": "tmp/canonical-finance-data-plane.json",
        "role": "normalized read-only ticker, routing, decision, price, band, evidence, and authority state",
        "required": True,
    },
    {
        "key": "wf84_phase6_10_proof",
        "path": "tmp/canonical-finance-data-plane-phase6-10.json",
        "role": "consumer parity, source drillback, priority queue, and retirement-gate proof",
        "required": True,
    },
    {
        "key": "wf84_sqlite_companion",
        "path": "tmp/canonical-finance-data-plane.sqlite",
        "role": "derived read-only query layer for decision-card construction",
        "required": True,
    },
    {
        "key": "wf78_capital_review_queue",
        "path": "tmp/wf78-capital-review-queue.json",
        "role": "non-executing owner-review candidate queue",
        "required": True,
    },
    {
        "key": "finance_decision_sync_spine",
        "path": "tmp/finance-decision-sync-spine.json",
        "role": "cross-artifact decision-state synchronization feed",
        "required": True,
    },
    {
        "key": "wf67_paper_guard_context",
        "path": "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
        "role": "paper-only guard context for future request-card boundaries",
        "required": False,
    },
]

BLOCKING_PRIMARY_STATES = {
    "blocked_missing_freshness",
    "blocked_missing_source_open",
    "blocked_missing_band_or_stop",
    "blocked_wf67_guard_context",
    "below_stop_or_invalidation",
    "evidence_repair",
}

INVALIDATION_PRIMARY_STATES = {
    "below_stop_or_invalidation",
    "invalidation_review",
}

OK_SOURCE_STATUSES = {"ok"}

TABLE_PARITY_CHECKS = [
    "schema_run",
    "source_artifact",
    "security_master",
    "routing_state_current",
    "price_technical_current",
    "entry_stop_reference",
    "decision_queue_state",
    "evidence_family_status",
    "official_evidence",
    "validation_result",
]

PARALLEL_LANES = [
    {
        "lane_id": "wf85_contract_and_schema",
        "purpose": "Define decision-card schema, authority flags, status vocabulary, and validation gates.",
        "writes": ["tmp/trade-grade-decision-os-contract.json"],
        "can_parallelize": False,
        "stop_line": "No card generation until schema and authority contract validate.",
    },
    {
        "lane_id": "wf85_decision_card_builder",
        "purpose": "Build review-only decision cards from WF84/WF78/WF67 inputs after source/freshness and state-precedence checks pass.",
        "writes": ["tmp/trade-grade-decision-cards.json"],
        "depends_on": ["wf85_contract_and_schema", "wf85_source_and_freshness_gate"],
        "can_parallelize": False,
        "stop_line": "Cards may recommend review and draft approval terms only; blocked or below-stop primary states must override optimistic auto_state.",
    },
    {
        "lane_id": "wf85_phase1_authority_validator",
        "purpose": "Scan generated decision cards for true authority flags and forbidden action vocabulary from Phase 1 onward.",
        "writes": ["tmp/trade-grade-decision-card-authority-validation.json"],
        "depends_on": ["wf85_decision_card_builder"],
        "can_parallelize": False,
        "stop_line": "Generated cards with true capital/execution/account/canon/customer authority flags are invalid artifacts.",
    },
    {
        "lane_id": "wf85_approval_card_gate",
        "purpose": "Separate review-ready, blocked, stale, and approval-card-draft states.",
        "writes": ["tmp/trade-grade-approval-card-gate.json"],
        "depends_on": ["wf85_decision_card_builder", "wf85_phase1_authority_validator"],
        "can_parallelize": True,
        "stop_line": "Approval-card draft is allowed only after review_ready gates pass; it is not Randall approval and cannot trigger paper/live action.",
    },
    {
        "lane_id": "wf85_risk_and_sizing_overlay",
        "purpose": "Draft sizing, staggering, invalidation, concentration, and no-chase context.",
        "writes": ["tmp/trade-grade-risk-sizing-overlay.json"],
        "depends_on": ["wf85_decision_card_builder"],
        "can_parallelize": True,
        "stop_line": "No cash, sizing, risk-rule, canon, or portfolio mutation.",
    },
    {
        "lane_id": "wf85_source_and_freshness_gate",
        "purpose": "Require source-open, source-age, and material-claim freshness before card readiness.",
        "writes": ["tmp/trade-grade-source-freshness-gate.json"],
        "depends_on": ["wf85_contract_and_schema"],
        "can_parallelize": False,
        "stop_line": "No material finance claim from SQLite alone.",
    },
    {
        "lane_id": "wf85_pm_cockpit_decision_view",
        "purpose": "Expose decision-card state through local PM cockpit read-only views after cards exist.",
        "writes": ["apps/pm-control-cockpit/*", "state/pm-cockpit-source-registry.json"],
        "depends_on": ["wf85_decision_card_builder", "wf85_approval_card_gate"],
        "can_parallelize": True,
        "stop_line": "Local read-only visibility only; no external delivery or action endpoint.",
    },
    {
        "lane_id": "wf85_challenger_qa",
        "purpose": "Independent critique of decision vocabulary, authority boundaries, and false-ready risks.",
        "writes": ["tmp/trade-grade-decision-os-challenger-review.json"],
        "can_parallelize": True,
        "stop_line": "Challenger output is advisory until main-session Veritas verifies it.",
    },
]

PHASES = [
    {
        "phase": 0,
        "name": "Contract and Route Registration",
        "acceptance": [
            "WF85 contract validates",
            "workflow router and PM lane see WF85",
            "authority flags remain hard false for capital/execution/account/customer/canon mutation",
        ],
    },
    {
        "phase": 1,
        "name": "Decision Card Schema and Builder",
        "acceptance": [
            "cards include thesis, price/band/stop, freshness, source drillback, base/bull/bear, invalidation, and owner action",
            "missing or stale evidence blocks readiness instead of filling guesses",
            "blocked or below-stop primary_state wins over optimistic auto_state",
            "initial approval_card_draft count is expected to be zero until WF84 freshness blockers clear",
            "all card authority flags remain false",
            "card authority/vocabulary validator runs against generated cards in this phase",
        ],
    },
    {
        "phase": 2,
        "name": "Approval Draft Gate",
        "acceptance": [
            "review-ready, blocked, stale, no-chase, invalidation-review, and approval-draft states are distinct",
            "paper request drafts require fresh WF67 guard context",
            "approval-draft is reachable only from fully gated review_ready",
            "approval-draft carries an inline NOT APPROVED stamp and never implies Randall approval",
        ],
    },
    {
        "phase": 3,
        "name": "Risk, Sizing, and Staggering Overlay",
        "acceptance": [
            "sizing/staggering is recommendation-only",
            "concentration and no-chase checks are visible",
            "no portfolio/cash/risk-rule mutation or execution entitlement changes",
        ],
    },
    {
        "phase": 4,
        "name": "PM Cockpit Decision View",
        "acceptance": [
            "local cockpit shows card queue and blockers",
            "queries are allowlisted and read-only",
            "no external delivery or action endpoint is added",
        ],
    },
    {
        "phase": 5,
        "name": "Parallel QA and Promotion Criteria",
        "acceptance": [
            "Opus/challenger review finds no authority drift",
            "validator proves no forbidden action vocabulary or true authority flags",
            "WF85 can feed WF67 request-card prep only after Randall exact approval remains separately required",
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_days(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    reference = now or datetime.now(timezone.utc)
    return round((reference - parsed).total_seconds() / 86400, 2)


def sqlite_probe(path: Path) -> dict[str, Any]:
    probe: dict[str, Any] = {
        "exists": path.exists(),
        "status": None,
        "validation_status": None,
        "generated_at_utc": None,
        "sqlite_integrity_status": None,
        "table_counts": {},
    }
    if not path.exists():
        return probe
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        probe["sqlite_integrity_status"] = integrity
        schema_row = conn.execute(
            "SELECT generated_at_utc, status, validation_status FROM schema_run ORDER BY generated_at_utc DESC LIMIT 1"
        ).fetchone()
        if schema_row:
            probe["generated_at_utc"] = schema_row["generated_at_utc"]
            probe["status"] = schema_row["status"]
            probe["validation_status"] = schema_row["validation_status"]
        counts: dict[str, int] = {}
        for table in TABLE_PARITY_CHECKS:
            try:
                counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            except sqlite3.Error:
                counts[table] = -1
        probe["table_counts"] = counts
        conn.close()
    except sqlite3.Error as exc:
        probe["sqlite_integrity_status"] = f"error:{exc}"
    return probe


def artifact_probe(spec: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / spec["path"]
    payload = load_json(path) if path.suffix.lower() == ".json" else {}
    sqlite_details = sqlite_probe(path) if path.suffix.lower() == ".sqlite" else {}
    probe = dict(spec)
    probe.update({
        "exists": path.exists(),
        "status": sqlite_details.get("status") if sqlite_details else (payload.get("status") if payload else None),
        "validation_status": sqlite_details.get("validation_status") if sqlite_details else (payload.get("validation", {}).get("status") if isinstance(payload.get("validation"), dict) else None),
        "generated_at_utc": sqlite_details.get("generated_at_utc") if sqlite_details else (payload.get("generated_at_utc") if payload else None),
    })
    if sqlite_details:
        probe.update({
            "sqlite_integrity_status": sqlite_details.get("sqlite_integrity_status"),
            "table_counts": sqlite_details.get("table_counts", {}),
        })
    if spec["key"] == "wf67_paper_guard_context":
        probe["max_age_days"] = MAX_PAPER_GUARD_CONTEXT_AGE_DAYS
        probe["age_days"] = age_days(probe.get("generated_at_utc"))
    return probe


def wf84_sqlite_json_parity(wf84_payload: dict[str, Any], sqlite_input: dict[str, Any]) -> dict[str, Any]:
    json_tables = wf84_payload.get("tables") if isinstance(wf84_payload.get("tables"), dict) else {}
    json_counts = {
        table: len(rows)
        for table, rows in json_tables.items()
        if isinstance(rows, list) and table in TABLE_PARITY_CHECKS
    }
    sqlite_counts = sqlite_input.get("table_counts") if isinstance(sqlite_input.get("table_counts"), dict) else {}
    mismatches = {
        table: {"json": json_counts.get(table), "sqlite": sqlite_counts.get(table)}
        for table in TABLE_PARITY_CHECKS
        if json_counts.get(table) != sqlite_counts.get(table)
    }
    return {
        "status": "ok" if (
            sqlite_input.get("exists")
            and sqlite_input.get("sqlite_integrity_status") == "ok"
            and wf84_payload.get("generated_at_utc") == sqlite_input.get("generated_at_utc")
            and not mismatches
        ) else "blocked",
        "json_generated_at_utc": wf84_payload.get("generated_at_utc"),
        "sqlite_generated_at_utc": sqlite_input.get("generated_at_utc"),
        "sqlite_integrity_status": sqlite_input.get("sqlite_integrity_status"),
        "json_counts": json_counts,
        "sqlite_counts": sqlite_counts,
        "mismatches": mismatches,
    }


def source_status_warnings(wf84_payload: dict[str, Any], phase_payload: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    source_rows = wf84_payload.get("tables", {}).get("source_artifact", [])
    if isinstance(source_rows, list):
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            if row.get("required_for_mvp") and row.get("status") not in OK_SOURCE_STATUSES:
                warnings.append({
                    "artifact_id": row.get("artifact_id"),
                    "path": row.get("path"),
                    "status": row.get("status"),
                    "validation_status": row.get("validation_status"),
                    "source": "wf84.source_artifact",
                })
    for source in phase_payload.get("source_artifacts", []) if isinstance(phase_payload.get("source_artifacts"), list) else []:
        if not isinstance(source, dict):
            continue
        for artifact in source.get("artifacts", []) if isinstance(source.get("artifacts"), list) else []:
            if not isinstance(artifact, dict):
                continue
            status = artifact.get("status")
            if status not in OK_SOURCE_STATUSES:
                warnings.append({
                    "artifact_id": artifact.get("artifact_id"),
                    "path": artifact.get("path"),
                    "status": status,
                    "validation_status": artifact.get("validation_status"),
                    "source": "wf84.phase6_10.source_artifacts",
                })
    return warnings


def state_precedence_probe(limit: int = 25) -> dict[str, Any]:
    db_path = ROOT / "tmp/canonical-finance-data-plane.sqlite"
    rows: list[dict[str, Any]] = []
    counts = {
        "a_ready_but_blocked": 0,
        "below_stop_or_invalidation": 0,
        "approval_card_draft_expected": EXPECTED_APPROVAL_DRAFT_COUNT_BEFORE_FRESHNESS_REPAIR,
    }
    if not db_path.exists():
        return {"status": "blocked", "reason": "wf84_sqlite_missing", "counts": counts, "sample": rows}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        for row in conn.execute(f"SELECT * FROM v_wf84_priority_queue LIMIT {int(limit)}"):
            data = dict(row)
            sample = {
                "ticker": data.get("ticker"),
                "auto_state": data.get("auto_state"),
                "primary_state": data.get("primary_state"),
                "band_status": data.get("band_status"),
            }
            rows.append(sample)
            if data.get("auto_state") == "A-READY" and data.get("primary_state") in BLOCKING_PRIMARY_STATES:
                counts["a_ready_but_blocked"] += 1
            if data.get("primary_state") in INVALIDATION_PRIMARY_STATES or data.get("band_status") == "BELOW_STOP":
                counts["below_stop_or_invalidation"] += 1
        conn.close()
    except sqlite3.Error as exc:
        return {"status": "blocked", "reason": f"sqlite_error:{exc}", "counts": counts, "sample": rows}
    return {
        "status": "ok",
        "policy": "primary_state precedence wins over auto_state; blocked and below-stop states cannot become approval_card_draft",
        "counts": counts,
        "sample": rows,
    }


def build_contract() -> dict[str, Any]:
    inputs = [artifact_probe(item) for item in INPUTS]
    wf84_payload = load_json(ROOT / "tmp/canonical-finance-data-plane.json")
    phase_payload = load_json(ROOT / "tmp/canonical-finance-data-plane-phase6-10.json")
    errors: list[str] = []
    warnings: list[str] = []
    missing_required = [item["key"] for item in inputs if item["required"] and not item["exists"]]
    if missing_required:
        errors.append(f"missing_required_inputs:{','.join(missing_required)}")
    true_authority = [key for key in REQUIRED_FALSE_KEYS if AUTHORITY_BOUNDARY.get(key) is not False]
    if true_authority:
        errors.append(f"authority_not_false:{','.join(true_authority)}")
    wf84_phase = next((item for item in inputs if item["key"] == "wf84_phase6_10_proof"), {})
    if wf84_phase.get("status") != "ok":
        warnings.append("wf84_phase6_10_not_ok_or_missing")
    sqlite_input = next((item for item in inputs if item["key"] == "wf84_sqlite_companion"), {})
    sqlite_parity = wf84_sqlite_json_parity(wf84_payload, sqlite_input)
    if sqlite_parity["status"] != "ok":
        errors.append("wf84_sqlite_json_parity_failed")
    feeder_warnings = source_status_warnings(wf84_payload, phase_payload)
    if feeder_warnings:
        warnings.append("wf84_feeder_status_not_plain_ok")
    paper_guard = next((item for item in inputs if item["key"] == "wf67_paper_guard_context"), {})
    paper_guard_age = paper_guard.get("age_days")
    if isinstance(paper_guard_age, (int, float)) and paper_guard_age > MAX_PAPER_GUARD_CONTEXT_AGE_DAYS:
        warnings.append("wf67_paper_guard_context_stale_for_request_drafts")
    state_probe = state_precedence_probe()
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": WORKFLOW_ID,
        "display_name": "Trade-Grade Decision and Approval Card OS",
        "status": "ok" if not errors else "blocked",
        "purpose": "Review-only decision and approval-card layer above WF84's canonical finance data plane.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": inputs,
        "decision_card_required_fields": [
            "ticker",
            "decision_state",
            "thesis_snapshot",
            "current_price",
            "entry_band",
            "stop_or_invalidation",
            "source_freshness",
            "source_drillback",
            "base_case",
            "bull_case",
            "bear_case",
            "key_risks",
            "counterargument",
            "sizing_staggering_recommendation",
            "owner_action_required",
            "authority_boundary",
        ],
        "state_precedence_policy": {
            "highest_priority": [
                "below_stop_or_invalidation",
                "blocked_missing_freshness",
                "blocked_missing_source_open",
                "blocked_missing_band_or_stop",
                "blocked_wf67_guard_context",
                "evidence_repair",
            ],
            "rule": "decision_queue_state.primary_state overrides routing_state_current.auto_state for readiness and approval-card draft decisions",
            "approval_card_draft_prerequisites": [
                "decision_state == review_ready",
                "source_freshness == fresh",
                "source_open_status == verified",
                "band_status == IN_BAND",
                "stop_or_invalidation present",
                "primary_state not in blocked or invalidation states",
                "wf67 guard context fresh if a paper-request draft is included",
                "inline_not_approved_stamp present",
            ],
            "initial_expected_approval_card_drafts": EXPECTED_APPROVAL_DRAFT_COUNT_BEFORE_FRESHNESS_REPAIR,
        },
        "allowed_decision_states": [
            "review_ready",
            "approval_card_draft",
            "blocked_missing_freshness",
            "blocked_missing_source_open",
            "blocked_missing_band_or_stop",
            "blocked_wf67_guard_context",
            "below_stop_or_invalidation",
            "evidence_repair",
            "no_chase",
            "invalidation_review",
            "monitor_only",
        ],
        "phase1_prerequisite_gates": {
            "wf84_sqlite_json_parity": sqlite_parity,
            "wf84_feeder_status_warnings": feeder_warnings,
            "paper_guard_context": {
                "required_for_card_generation": False,
                "required_for_wf67_request_drafts": True,
                "max_age_days": MAX_PAPER_GUARD_CONTEXT_AGE_DAYS,
                "current_age_days": paper_guard_age,
                "stale_for_request_drafts": isinstance(paper_guard_age, (int, float)) and paper_guard_age > MAX_PAPER_GUARD_CONTEXT_AGE_DAYS,
            },
            "state_precedence_probe": state_probe,
            "authority_validator_required_from_phase": 1,
            "expected_fail_closed_posture": "Most cards should remain blocked_missing_freshness until WF84 feeder freshness repair clears; approval_card_draft count above zero before that is suspect.",
        },
        "parallel_lanes": PARALLEL_LANES,
        "phases": PHASES,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "No capital deployment approval, paper/live execution, brokerage/account action, or money movement.",
            "No generated decision card, score, SQL row, or approval-card draft implies Randall approval.",
            "No canon/portfolio/cash/sizing/risk-rule mutation.",
            "No customer/account/PII/suitability/retail-public schema or external delivery.",
            "No material finance claim from WF84 SQLite alone; source-open proof remains required.",
        ],
        "next_safe_action": "Implement Phase 1 only after SQLite/JSON parity passes; build source/freshness/state-precedence gates first, then generate fail-closed decision cards and run authority validation before any approval-card gate.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF85 trade-grade decision OS contract.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = build_contract()
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, contract)
        print(f"wrote {rel(out)} status={contract['status']}")
    else:
        print(json.dumps(contract, indent=2))
    if args.validate and contract["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
