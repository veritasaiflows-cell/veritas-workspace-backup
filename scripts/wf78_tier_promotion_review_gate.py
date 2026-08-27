#!/usr/bin/env python3
"""Build WF78 tier-promotion and 101-200 owner-decision packets.

This gate separates broad Tier C/D discovery from Tier B/A research and
capital-deployment readiness. It prepares an exact 101-200 Tier C
review-monitor owner decision packet and a repair queue for evidence families
that must be completed before any Tier B or Tier A promotion.

It never imports/applies tickers, promotes production answer paths, mutates
canon/portfolio state, infers approval, or authorizes paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

REPUTATION_GATE = TMP / "wf78-500-ticker-reputation-gate.json"
TICKER_CARD_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"
IMPORT_GATE = TMP / "wf78-101-200-tier-c-import-gate.json"
MACRO_THESIS_OVERLAY_GATE = TMP / "wf78-macro-thesis-overlay-gate.json"
TIER_CAPACITY_POLICY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"

DEFAULT_OUT = TMP / "wf78-tier-promotion-review-gate.json"
DEFAULT_DB = TMP / "wf78-tier-promotion-review-gate.sqlite"
DEFAULT_OWNER_PACKET = TMP / "wf78-101-200-tier-c-owner-decision-packet.json"

SCHEMA = "veritas.wf78_tier_promotion_review_gate.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "owner_decision_packet_allowed": True,
    "repair_queue_allowed": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "production_answer_path_change_allowed": False,
    "tier_b_promotion_allowed": False,
    "tier_a_promotion_allowed": False,
    "capital_deployment_allowed": False,
    "paper_execution_allowed": False,
    "live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_first_promotion_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "owner_decision_packet_allowed", "repair_queue_allowed"}
REQUIRED_FALSE_FLAGS = {
    "ticker_import_allowed",
    "apply_allowed",
    "production_answer_path_change_allowed",
    "tier_b_promotion_allowed",
    "tier_a_promotion_allowed",
    "capital_deployment_allowed",
    "paper_execution_allowed",
    "live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "canon_or_portfolio_mutation_allowed",
    "sql_first_promotion_allowed",
    "customer_or_external_delivery_allowed",
    "owner_approval_inferred",
}

TIER_B_REQUIRED = {
    "fundamentals",
    "analyst_layer",
    "valuation_layer",
    "technical_layer",
    "official_source_evidence",
    "ticker_card",
    "macro_or_thesis_fit",
    "portfolio_fit",
    "risk_register",
}

TIER_A_REQUIRED = {
    "entry_stop_band_context",
    "source_open_answer_contract",
    "production_answer_path_qa",
    "fresh_price_band_stop",
    "sizing_staggering_logic",
    "owner_approval",
}

TIER_A_CAP = 25
TIER_B_CAP = 50
TIER_A_B_COMBINED_CAP = 75


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


def int_or(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def reputation_gate_future_pending(gate: dict[str, Any]) -> bool:
    summary = as_dict(gate.get("summary"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    return (
        gate.get("status") == "blocked"
        and validation.get("status") == "error"
        and int_or(summary.get("row_count")) < int_or(summary.get("target_count"), 500)
        and int_or(summary.get("future_validation_required_count")) > 0
        and int_or(summary.get("tier_a_production_eligible_count")) == 0
        and int_or(summary.get("tier_b_research_eligible_count")) == 0
        and authority.get("ticker_import_allowed") is False
        and authority.get("apply_allowed") is False
        and authority.get("production_answer_path_change_allowed") is False
        and authority.get("sql_first_promotion_allowed") is False
        and authority.get("sql_canon_expansion_allowed") is False
        and authority.get("canon_or_portfolio_mutation_allowed") is False
        and authority.get("customer_or_external_delivery_allowed") is False
        and authority.get("paper_or_live_execution_allowed") is False
        and authority.get("brokerage_or_account_action_allowed") is False
        and authority.get("money_movement_allowed") is False
        and authority.get("owner_approval_inferred") is False
    )


def normalize_reason(reason: Any) -> str:
    if isinstance(reason, dict):
        return str(reason.get("family") or reason.get("status") or "unknown").strip()
    text = str(reason or "unknown").strip()
    if text.startswith("stale:"):
        text = text.split(":", 1)[1]
    return text or "unknown"


def selected_101_200_rows(reputation_gate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in as_list(reputation_gate.get("candidate_rows"))
        if isinstance(row, dict) and row.get("batch_index") == 2
    ]
    rows.sort(key=lambda row: int(row.get("candidate_rank_for_500") or 9999))
    return rows


def owner_rows_from_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(packet.get("tickers")):
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "reputation_score": row.get("reputation_score"),
                "candidate_rank_for_500": row.get("rank"),
                "current_tier": "tier_c_imported_review_monitor",
                "tier_c_import_review_eligible": True,
                "missing_evidence_families": row.get("not_decision_grade_because_missing") or [],
            }
        )
    rows.sort(key=lambda row: int(row.get("candidate_rank_for_500") or 9999))
    return rows


def owner_decision_packet(rows: list[dict[str, Any]], reputation_gate: dict[str, Any]) -> dict[str, Any]:
    sector_counts = dict(sorted(Counter(str(row.get("sector") or "Unknown") for row in rows).items()))
    eligible_rows = [row for row in rows if row.get("tier_c_import_review_eligible") is True]
    tickers = [
        {
            "rank": row.get("candidate_rank_for_500"),
            "ticker": row.get("ticker"),
            "name": row.get("name"),
            "sector": row.get("sector"),
            "industry": row.get("industry"),
            "reputation_score": row.get("reputation_score"),
            "source_open_status": row.get("source_open_status"),
            "provider_status": row.get("provider_status"),
            "freshness_status": row.get("freshness_status"),
            "allowed_tier_after_approval": "Tier C review-monitor only",
            "not_decision_grade_because_missing": sorted(set(as_list(row.get("missing_evidence_families"))).intersection(TIER_B_REQUIRED | TIER_A_REQUIRED)),
        }
        for row in rows
    ]
    return {
        "schema": "veritas.wf78_101_200_tier_c_owner_decision_packet.v1",
        "generated_at_utc": utc_now(),
        "status": "decision_required",
        "decision_type": "owner_approval_required_before_tier_c_review_monitor_import",
        "source": rel(REPUTATION_GATE),
        "exact_owner_question": (
            "Approve importing exactly these 100 tickers as Tier C review-monitor rows only, "
            "with no production answer-path expansion, no Tier B/A promotion, no capital deployment, "
            "no SQL-first route, and no canon/portfolio/customer/paper/live/account authority?"
        ),
        "recommended_answer": "approve_only_if_you_want_101_200_as_review_monitor_breadth",
        "scope": {
            "target_batch": "101-200",
            "ticker_count": len(rows),
            "tier_c_import_review_eligible_count": len(eligible_rows),
            "post_approval_allowed_state": "Tier C review-monitor only",
            "production_answer_path_change": False,
            "decision_grade_claim": False,
            "capital_deployment_claim": False,
        },
        "sector_counts": sector_counts,
        "tickers": tickers,
        "pre_apply_requirements": [
            "Randall exact approval for this packet and exact scope.",
            "Backup current universe/state before any scoped apply gate.",
            "No-regression proof that current 42 production answer-path tickers remain unchanged.",
            "Rerun wf78_phase_runner.py --phase all-safe --write --validate.",
            "Rerun wf78_500_ticker_reputation_gate.py --write --write-db --validate.",
            "Rerun hardening, PM state, PM queue, and cockpit validation after any approved apply.",
        ],
        "blocked_until_approval": {
            "import_apply_blocked": True,
            "approval_artifact_required": True,
            "approval_inferred_from_clean_gate": False,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "upstream_summary": as_dict(reputation_gate.get("summary")),
        "stop_lines": [
            "No import/apply unless Randall explicitly approves this exact packet.",
            "No production answer-path promotion.",
            "No Tier B or Tier A promotion from Tier C existence.",
            "No capital deployment or paper/live/account action.",
            "No canon/portfolio mutation.",
            "No SQL-first route.",
            "No customer/external output.",
            "No owner approval inference.",
        ],
    }


def current_card_repair_jobs(refresh_gate: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for index, item in enumerate(as_list(refresh_gate.get("repair_queue")), start=1):
        if not isinstance(item, dict):
            continue
        reasons = sorted({normalize_reason(reason) for reason in as_list(item.get("stale_reasons"))})
        ticker = str(item.get("ticker") or "").upper()
        if not ticker:
            continue
        jobs.append(
            {
                "job_id": f"repair-current-{ticker.lower()}",
                "rank": index,
                "ticker": ticker,
                "source_card": item.get("card_path"),
                "current_scope": "current_100_existing_card_repair",
                "repair_reasons": reasons,
                "missing_evidence_families": reasons,
                "required_before_tier_b": sorted(TIER_B_REQUIRED),
                "required_before_tier_a": sorted(TIER_A_REQUIRED),
                "next_action": "repair stale evidence families, then rerun finance_ticker_card_refresh_gate before promotion review",
                "promotion_allowed_now": False,
                "capital_deployment_allowed_now": False,
            }
        )
    return jobs


def c_to_b_research_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in rows:
        missing = set(as_list(row.get("missing_evidence_families"))).union(TIER_B_REQUIRED | TIER_A_REQUIRED)
        queue.append(
            {
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "reputation_score": row.get("reputation_score"),
                "current_tier": row.get("current_tier"),
                "candidate_rank_for_500": row.get("candidate_rank_for_500"),
                "promotion_target": "Tier B research candidate only after evidence build",
                "missing_for_tier_b": sorted(missing.intersection(TIER_B_REQUIRED)),
                "missing_for_tier_a": sorted(missing.intersection(TIER_A_REQUIRED)),
                "macro_thesis_research_required": True,
                "capital_deployment_allowed_now": False,
                "next_action": "eligible as a lead only; build thesis/macro/fundamental/valuation/technical packet before promotion",
            }
        )
    queue.sort(key=lambda item: (-int(item.get("reputation_score") or 0), int(item.get("candidate_rank_for_500") or 9999)))
    return queue


def grouped_repair_summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    by_reason: dict[str, list[str]] = defaultdict(list)
    for job in jobs:
        for reason in as_list(job.get("repair_reasons")):
            by_reason[str(reason)].append(str(job.get("ticker")))
    return {
        "job_count": len(jobs),
        "reason_counts": dict(sorted((reason, len(tickers)) for reason, tickers in by_reason.items())),
        "top_reason_examples": [
            {"reason": reason, "ticker_count": len(tickers), "sample_tickers": tickers[:10]}
            for reason, tickers in sorted(by_reason.items(), key=lambda item: (-len(item[1]), item[0]))[:15]
        ],
    }


def build_report() -> tuple[dict[str, Any], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    reputation_gate = load_dict(REPUTATION_GATE)
    refresh_gate = load_dict(TICKER_CARD_REFRESH_GATE)
    import_gate = load_dict(IMPORT_GATE)
    macro_overlay = load_dict(MACRO_THESIS_OVERLAY_GATE)
    capacity_gate = load_dict(TIER_CAPACITY_POLICY_GATE)
    future_pending = reputation_gate_future_pending(reputation_gate)
    import_status = str(import_gate.get("status") or "")
    import_applied = import_status in {"ok_imported_tier_c_only", "ok_already_imported_tier_c_only"}
    if import_applied:
        owner_packet = load_dict(DEFAULT_OWNER_PACKET)
        owner_packet = {**owner_packet, "status": "approved_applied_tier_c_only", "post_apply_proof": rel(IMPORT_GATE)}
        rows = owner_rows_from_packet(owner_packet)
    else:
        rows = selected_101_200_rows(reputation_gate)
        owner_packet = owner_decision_packet(rows, reputation_gate)
    repair_jobs = current_card_repair_jobs(refresh_gate)
    research_queue = c_to_b_research_queue(rows)
    authority = AUTHORITY_BOUNDARY

    add_check(checks, "reputation_gate_exists", REPUTATION_GATE.exists(), rel(REPUTATION_GATE))
    add_check(checks, "reputation_gate_status_ok_or_future_pending", reputation_gate.get("status") == "ok" or future_pending, reputation_gate.get("status"))
    add_check(checks, "ticker_card_refresh_gate_exists", TICKER_CARD_REFRESH_GATE.exists(), rel(TICKER_CARD_REFRESH_GATE))
    add_check(checks, "ticker_card_refresh_gate_validation_ok", as_dict(refresh_gate.get("validation")).get("status") == "ok", as_dict(refresh_gate.get("validation")))
    add_check(checks, "import_gate_status_acceptable_if_present", (not IMPORT_GATE.exists()) or import_applied, {"path": rel(IMPORT_GATE), "status": import_status})
    add_check(checks, "macro_thesis_overlay_gate_ok_if_present", (not MACRO_THESIS_OVERLAY_GATE.exists()) or as_dict(macro_overlay.get("validation")).get("status") == "ok", {"path": rel(MACRO_THESIS_OVERLAY_GATE), "status": macro_overlay.get("status")})
    add_check(checks, "tier_capacity_policy_gate_ok_if_present_or_future_pending", (not TIER_CAPACITY_POLICY_GATE.exists()) or as_dict(capacity_gate.get("validation")).get("status") == "ok" or future_pending, {"path": rel(TIER_CAPACITY_POLICY_GATE), "status": capacity_gate.get("status")})
    add_check(checks, "tier_a_capacity_policy_25", int(as_dict(capacity_gate.get("policy")).get("tier_a_max") or TIER_A_CAP) == 25, as_dict(capacity_gate.get("policy")))
    add_check(checks, "tier_b_capacity_policy_50", int(as_dict(capacity_gate.get("policy")).get("tier_b_max") or TIER_B_CAP) == 50, as_dict(capacity_gate.get("policy")))
    add_check(checks, "combined_capacity_policy_75", int(as_dict(capacity_gate.get("policy")).get("tier_a_b_combined_max") or TIER_A_B_COMBINED_CAP) == 75, as_dict(capacity_gate.get("policy")))
    add_check(checks, "owner_packet_has_100_tickers", len(rows) == 100, len(rows))
    add_check(checks, "owner_packet_all_tier_c_eligible_or_already_imported", import_applied or len([row for row in rows if row.get("tier_c_import_review_eligible") is True]) == 100, {"import_applied": import_applied, "rows": len(rows)})
    add_check(checks, "tier_b_research_eligible_zero", as_dict(reputation_gate.get("summary")).get("tier_b_research_eligible_count") == 0, as_dict(reputation_gate.get("summary")))
    add_check(checks, "tier_a_production_eligible_zero", as_dict(reputation_gate.get("summary")).get("tier_a_production_eligible_count") == 0, as_dict(reputation_gate.get("summary")))
    add_check(checks, "current_card_repair_jobs_present", len(repair_jobs) > 0, len(repair_jobs), "warning")
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", authority.get(flag) is True, authority.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", authority.get(flag) is False, authority.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    status = "ok" if not errors else "blocked"
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Tiered 500 Ticker Scaleout Promotion Review",
        "purpose": "Separate Tier C/D discovery from Tier B/A research and capital-deployment readiness.",
        "authority_boundary": authority,
        "summary": {
            "status": status,
            "owner_decision_packet_status": owner_packet["status"],
            "tier_c_101_200_import_status": import_status or "not_applied",
            "owner_decision_ticker_count": len(rows),
            "tier_c_import_review_eligible_count": len([row for row in rows if row.get("tier_c_import_review_eligible") is True]),
            "tier_b_research_eligible_now_count": 0,
            "tier_a_deployment_eligible_now_count": 0,
            "current_card_repair_job_count": len(repair_jobs),
            "c_to_b_research_lead_count": len(research_queue),
            "macro_thesis_shortlist_count": len(as_list(macro_overlay.get("tier_b_research_shortlist"))),
            "tier_capacity_policy_status": capacity_gate.get("status") or "not_yet_run",
            "tier_a_capacity_max": int(as_dict(capacity_gate.get("policy")).get("tier_a_max") or TIER_A_CAP),
            "tier_b_capacity_max": int(as_dict(capacity_gate.get("policy")).get("tier_b_max") or TIER_B_CAP),
            "tier_a_b_combined_capacity_max": int(as_dict(capacity_gate.get("policy")).get("tier_a_b_combined_max") or TIER_A_B_COMBINED_CAP),
            "tier_a_remaining_capacity": as_dict(capacity_gate.get("summary")).get("tier_a_remaining_capacity"),
            "tier_b_remaining_capacity": as_dict(capacity_gate.get("summary")).get("tier_b_remaining_capacity"),
            "import_apply_blocked": True,
            "next_safe_action": "Use the macro/thesis overlay shortlist and evidence-repair jobs before any Tier B/Tier A promotion.",
        },
        "tier_capacity_policy": as_dict(capacity_gate.get("policy")) or {
            "tier_a_max": TIER_A_CAP,
            "tier_b_max": TIER_B_CAP,
            "tier_a_b_combined_max": TIER_A_B_COMBINED_CAP,
            "note": "Run wf78_tier_capacity_policy_gate.py --write --write-db --validate for current capacity proof.",
        },
        "truth_model": {
            "tier_d": "raw candidate/watchlist: identity/theme discovery only",
            "tier_c": "review-monitor: breadth/routing lead only; not investable",
            "tier_b": "research candidate: full finance picture build required",
            "tier_a": "deployment review: full fresh evidence, portfolio fit, sizing logic, owner approval card",
        },
        "owner_decision_packet_path": rel(DEFAULT_OWNER_PACKET),
        "owner_decision_packet": owner_packet,
        "tier_c_to_b_research_queue": research_queue,
        "current_card_repair_jobs": repair_jobs,
        "repair_summary": grouped_repair_summary(repair_jobs),
        "repeatable_sequence": [
            "Run finance_ticker_card_refresh_gate.py --write --validate.",
            "Run wf78_phase_runner.py --phase all-safe --write --validate.",
            "Run wf78_500_ticker_reputation_gate.py --write --write-db --validate.",
            "Run wf78_tier_promotion_review_gate.py --write --write-db --validate.",
            "Run wf78_tier_capacity_policy_gate.py --write --write-db --validate.",
            "Owner may approve only exact Tier C review-monitor import packets.",
            "Run wf78_macro_thesis_overlay_gate.py --write --write-db --validate after every approved batch.",
            "Evidence repair jobs must close before any Tier B/Tier A promotion packet.",
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": owner_packet["stop_lines"],
    }
    return report, owner_packet


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS owner_decision_tickers;
        DROP TABLE IF EXISTS research_queue;
        DROP TABLE IF EXISTS repair_jobs;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_checks;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE owner_decision_tickers (
            ticker TEXT PRIMARY KEY,
            rank INTEGER,
            name TEXT,
            sector TEXT,
            industry TEXT,
            reputation_score INTEGER,
            allowed_tier_after_approval TEXT NOT NULL,
            not_decision_grade_because_missing_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE research_queue (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            reputation_score INTEGER,
            promotion_target TEXT NOT NULL,
            missing_for_tier_b_json TEXT NOT NULL,
            missing_for_tier_a_json TEXT NOT NULL,
            capital_deployment_allowed_now INTEGER NOT NULL CHECK (capital_deployment_allowed_now IN (0,1))
        ) STRICT;

        CREATE TABLE repair_jobs (
            job_id TEXT PRIMARY KEY,
            rank INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            source_card TEXT,
            repair_reasons_json TEXT NOT NULL,
            promotion_allowed_now INTEGER NOT NULL CHECK (promotion_allowed_now IN (0,1)),
            capital_deployment_allowed_now INTEGER NOT NULL CHECK (capital_deployment_allowed_now IN (0,1))
        ) STRICT;

        CREATE TABLE authority_boundary (
            flag TEXT PRIMARY KEY,
            value INTEGER NOT NULL CHECK (value IN (0,1)),
            required_value INTEGER NOT NULL CHECK (required_value IN (0,1)),
            ok INTEGER NOT NULL CHECK (ok IN (0,1))
        ) STRICT;

        CREATE TABLE validation_checks (
            name TEXT PRIMARY KEY,
            ok INTEGER NOT NULL CHECK (ok IN (0,1)),
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;
        """
    )


def write_db(report: dict[str, Any], db_path: Path) -> None:
    with connect_write(db_path) as conn:
        init_schema(conn)
        for row in as_list(as_dict(report.get("owner_decision_packet")).get("tickers")):
            conn.execute(
                "INSERT INTO owner_decision_tickers VALUES (?,?,?,?,?,?,?,?)",
                (
                    row.get("ticker"),
                    row.get("rank"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("industry"),
                    row.get("reputation_score"),
                    row.get("allowed_tier_after_approval"),
                    json_text(row.get("not_decision_grade_because_missing")),
                ),
            )
        for row in as_list(report.get("tier_c_to_b_research_queue")):
            conn.execute(
                "INSERT INTO research_queue VALUES (?,?,?,?,?,?,?,?)",
                (
                    row.get("ticker"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("reputation_score"),
                    row.get("promotion_target"),
                    json_text(row.get("missing_for_tier_b")),
                    json_text(row.get("missing_for_tier_a")),
                    1 if row.get("capital_deployment_allowed_now") else 0,
                ),
            )
        for row in as_list(report.get("current_card_repair_jobs")):
            conn.execute(
                "INSERT INTO repair_jobs VALUES (?,?,?,?,?,?,?)",
                (
                    row.get("job_id"),
                    row.get("rank"),
                    row.get("ticker"),
                    row.get("source_card"),
                    json_text(row.get("repair_reasons")),
                    1 if row.get("promotion_allowed_now") else 0,
                    1 if row.get("capital_deployment_allowed_now") else 0,
                ),
            )
        for flag, value in AUTHORITY_BOUNDARY.items():
            required = True if flag in REQUIRED_TRUE_FLAGS else False if flag in REQUIRED_FALSE_FLAGS else bool(value)
            conn.execute("INSERT INTO authority_boundary VALUES (?,?,?,?)", (flag, 1 if value else 0, 1 if required else 0, 1 if bool(value) == required else 0))
        for check in as_list(as_dict(report.get("validation")).get("checks")):
            conn.execute("INSERT INTO validation_checks VALUES (?,?,?,?)", (check.get("name"), 1 if check.get("ok") else 0, check.get("severity"), json_text(check.get("detail"))))
        for key in ("schema", "generated_at_utc", "status", "summary", "truth_model"):
            conn.execute("INSERT INTO meta VALUES (?,?)", (key, json_text(report.get(key))))
        conn.commit()


def validate_outputs(report: dict[str, Any], out: Path, owner_packet_out: Path, db: Path, write: bool, write_db_flag: bool) -> list[str]:
    errors: list[str] = []
    if as_dict(report.get("validation")).get("status") != "ok":
        errors.append("report validation is not ok")
    if write:
        loaded = load_json_artifact(out)
        owner = load_json_artifact(owner_packet_out)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("main JSON missing or schema mismatch")
        if not isinstance(owner, dict) or owner.get("status") not in {"decision_required", "approved_applied_tier_c_only"}:
            errors.append("owner decision packet missing or status not recognized")
    if write_db_flag:
        if not db.exists():
            errors.append("SQLite output missing")
        else:
            with sqlite3.connect(str(db)) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    errors.append("SQLite integrity_check failed")
                if conn.execute("SELECT count(*) FROM authority_boundary WHERE ok=0").fetchone()[0]:
                    errors.append("unsafe authority rows present")
                if conn.execute("SELECT count(*) FROM owner_decision_tickers").fetchone()[0] != 100:
                    errors.append("owner_decision_tickers row count mismatch")
                if conn.execute("SELECT count(*) FROM research_queue WHERE capital_deployment_allowed_now != 0").fetchone()[0]:
                    errors.append("capital deployment allowed in research_queue")
    return errors


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 tier promotion review and owner decision packets.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--owner-packet-out", type=Path, default=DEFAULT_OWNER_PACKET)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = resolve(args.out)
    db = resolve(args.db)
    owner_packet_out = resolve(args.owner_packet_out)
    report, owner_packet = build_report()
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
        atomic_write_json(owner_packet_out, owner_packet, ensure_ascii=False)
    if args.write_db:
        write_db(report, db)
    output_errors = validate_outputs(report, out, owner_packet_out, db, args.write, args.write_db)
    status = report["status"] if not output_errors else "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "validation_status": as_dict(report.get("validation")).get("status"),
                "output_errors": output_errors,
                "out": rel(out) if args.write else None,
                "owner_packet_out": rel(owner_packet_out) if args.write else None,
                "db": rel(db) if args.write_db else None,
                "summary": report.get("summary"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and status != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
