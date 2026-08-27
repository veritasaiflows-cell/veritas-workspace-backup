from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
FINANCE_CANON_DB = WORKSPACE / "state" / "finance" / "finance-canon.sqlite"
DATA_PLANE_DB = TMP / "canonical-finance-data-plane.sqlite"
OUT_JSON = TMP / "tier-a-trade-grade-coverage-gate.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"

AUTHORITY_BOUNDARY = {
    "artifact_role": "tier_a_trade_grade_coverage_gate_review_only",
    "review_only": True,
    "report_only": True,
    "sql_read_only": True,
    "sql_write_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_output_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_SECTIONS = {
    "thesis",
    "business_quality_moat",
    "bull_case",
    "bear_case",
    "earnings_guidance",
    "financial_metrics",
    "valuation",
    "technical_setup",
    "catalyst_news_macro",
    "risk_invalidation",
    "portfolio_fit",
    "entry_stop_sizing",
    "decision_state",
    "trade_grade",
    "owner_action",
    "authority_approval_status",
    "evidence_freshness_confidence",
}

PLACEHOLDER_THESIS = "Card-level thesis synthesis requires source-open review"
SLEEVE_ROUTER_ONLY_INSTRUMENT_TYPES = {
    "etf",
    "fund",
    "etf_or_macro_proxy",
    "sector_proxy",
    "sector_sleeve",
    "macro_proxy",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": repr(exc)}
    return data if isinstance(data, dict) else {"_load_error": "json_not_object"}


def query_rows(db_path: Path, sql: str) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql)]


def load_tier_rows() -> dict[str, list[dict[str, Any]]]:
    finance_rows = query_rows(
        FINANCE_CANON_DB,
        """
        select ticker, auto_tier, auto_state, route_priority, data_confidence_rating,
               fundamentals_confidence, tier_a_confidence_status
        from tier_routing_state
        where auto_tier = 'Tier A'
        order by ticker
        """,
    )
    plane_rows = query_rows(
        DATA_PLANE_DB,
        """
        select ticker, auto_tier, auto_state, route_priority, data_confidence_rating,
               fundamentals_confidence, tier_a_confidence_status
        from routing_state_current
        where auto_tier = 'Tier A'
        order by ticker
        """,
    )
    router = load_json(AUTO_ROUTER)
    router_rows = [
        row for row in router.get("rows", [])
        if isinstance(row, dict) and row.get("auto_tier") == "Tier A" and row.get("ticker")
    ]
    router_rows.sort(key=lambda row: str(row.get("ticker") or ""))
    return {
        "finance_canon_tier_a": finance_rows,
        "data_plane_tier_a": plane_rows,
        "router_tier_a": router_rows,
    }


def tier_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["ticker"]): row for row in rows}


def truthy_false_authority(boundary: dict[str, Any]) -> list[str]:
    allowed_true = {"review_only", "report_only", "source_open_required_before_material_finance_claims"}
    forbidden_true = []
    for key, value in boundary.items():
        if key in allowed_true:
            continue
        if value is True:
            forbidden_true.append(key)
    return forbidden_true


def card_depth_checks(card: dict[str, Any]) -> dict[str, Any]:
    instrument_type = str(card.get("instrument_type") or "").lower()
    durable_state = card.get("durable_sql_canon_state") or {}
    if not instrument_type:
        instrument_type = str(durable_state.get("instrument_type") or "").lower()

    thesis_ctx = card.get("thesis_bull_bear_entry_context") or {}
    thesis = str(thesis_ctx.get("thesis") or "")
    moat = card.get("competitive_moat") or {}
    sector = card.get("current_sector_performance") or {}
    etf_profile_present = card.get("etf_or_macro_proxy_profile") is not None
    price_band_stop = card.get("price_band_stop") or {}

    is_company = instrument_type in {"operating_company", "company", "equity", ""}
    thesis_synthesized = bool(thesis and PLACEHOLDER_THESIS not in thesis)
    moat_structured = moat.get("status") not in {None, "not_yet_structured_source_open_required"}
    sector_present = sector.get("status") not in {None, "missing"}
    fresh_quote_required = price_band_stop.get("fresh_quote_required") is True

    depth_blockers: list[str] = []
    if not thesis_synthesized:
        depth_blockers.append("thesis_not_synthesized")
    if is_company and not moat_structured:
        depth_blockers.append("competitive_moat_not_structured")
    if is_company and not sector_present:
        depth_blockers.append("current_sector_performance_missing")
    if not is_company and not etf_profile_present:
        depth_blockers.append("etf_or_macro_proxy_profile_missing")
    if fresh_quote_required:
        depth_blockers.append("fresh_quote_required")

    return {
        "instrument_type": instrument_type or None,
        "thesis_synthesized": thesis_synthesized,
        "competitive_moat_status": moat.get("status"),
        "competitive_moat_structured": moat_structured,
        "sector_status": sector.get("status"),
        "sector_present": sector_present,
        "etf_or_macro_proxy_profile_present": etf_profile_present,
        "fresh_quote_required": fresh_quote_required,
        "risk_register_count": len(card.get("risk_register") or []),
        "depth_blockers": depth_blockers,
    }


def parity_blocks_decision_grade(parity: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    validation = parity.get("validation") or {}
    critical_errors = [str(item) for item in validation.get("critical_errors") or []]
    if validation.get("status") == "ok" and not critical_errors:
        return False, [], []
    if critical_errors and all("section_value_hash_mismatch" in item for item in critical_errors):
        return False, [], critical_errors
    blockers: list[str] = []
    if validation.get("status") != "ok":
        blockers.append(f"parity_status:{validation.get('status')}")
    if critical_errors:
        blockers.append("parity_critical_errors")
    return True, blockers, []


def evaluate_ticker(ticker: str, tier_row: dict[str, Any], *, cohort: str) -> dict[str, Any]:
    card_path = TMP / "ticker-intelligence-cards" / f"{ticker}.current.json"
    full_answer_path = TMP / "trade-grade-full-answer" / f"{ticker}.json"
    parity_path = TMP / "full-answer-parity" / f"{ticker}.json"
    card = load_json(card_path) if card_path.exists() else {}
    full_answer = load_json(full_answer_path) if full_answer_path.exists() else {}
    parity = load_json(parity_path) if parity_path.exists() else {}

    sections = full_answer.get("sections") if isinstance(full_answer.get("sections"), dict) else {}
    missing_sections = sorted(REQUIRED_SECTIONS - set(sections))
    validation = full_answer.get("validation") or {}
    machine_state = full_answer.get("machine_state") or {}
    decision_gate = machine_state.get("decision_grade_gate") or {}
    trade_grade = machine_state.get("trade_grade") or {}
    parity_validation = parity.get("validation") or {}
    card_depth = card_depth_checks(card) if card else {"depth_blockers": ["card_missing"]}

    floor_blockers: list[str] = []
    if not card_path.exists():
        floor_blockers.append("ticker_card_missing")
    if not full_answer_path.exists():
        floor_blockers.append("full_answer_missing")
    if not parity_path.exists():
        floor_blockers.append("full_answer_parity_missing")
    if full_answer.get("status") != "ok":
        floor_blockers.append(f"full_answer_status:{full_answer.get('status')}")
    if len(sections) != len(REQUIRED_SECTIONS) or missing_sections:
        floor_blockers.append("required_sections_incomplete")
    if validation.get("missing_sections"):
        floor_blockers.append("full_answer_validation_missing_sections")
    parity_blocks, parity_blockers, parity_retirement_blockers = parity_blocks_decision_grade(parity)
    if parity_blocks:
        floor_blockers.extend(parity_blockers)
    if (full_answer.get("source_count") or 0) < 18:
        floor_blockers.append("source_count_below_18")
    if truthy_false_authority(full_answer.get("authority_boundary") or {}):
        floor_blockers.append("forbidden_authority_true")

    source_lineage_count = len(full_answer.get("source_lineage") or [])
    if source_lineage_count < 17:
        floor_blockers.append("source_lineage_below_17")

    status = "coverage_floor_ok" if not floor_blockers else "coverage_floor_blocked"
    if not floor_blockers and card_depth["depth_blockers"]:
        status = "coverage_floor_ok_depth_blocked"

    return {
        "ticker": ticker,
        "cohort": cohort,
        "auto_tier": tier_row.get("auto_tier"),
        "auto_state": tier_row.get("auto_state"),
        "route_priority": tier_row.get("route_priority"),
        "data_confidence_rating": tier_row.get("data_confidence_rating"),
        "fundamentals_confidence": tier_row.get("fundamentals_confidence"),
        "status": status,
        "coverage_floor_passed": not floor_blockers,
        "depth_ready": not card_depth["depth_blockers"],
        "decision_grade_claim_allowed": decision_gate.get("decision_grade_claim_allowed") is True,
        "decision_state": machine_state.get("decision_state"),
        "primary_state": machine_state.get("primary_state"),
        "queue_state": machine_state.get("queue_state"),
        "trade_grade": trade_grade.get("grade"),
        "source_count": full_answer.get("source_count"),
        "source_lineage_count": source_lineage_count,
        "section_count": len(sections),
        "missing_sections": missing_sections,
        "floor_blockers": floor_blockers,
        "parity_retirement_blockers": parity_retirement_blockers,
        "depth_blockers": card_depth["depth_blockers"],
        "depth_checks": card_depth,
        "paths": {
            "ticker_card": rel(card_path),
            "full_answer": rel(full_answer_path),
            "parity": rel(parity_path),
        },
    }


def load_retail_context() -> dict[str, Any]:
    control = load_json(TMP / "retail-automation-control-plane.json")
    readiness = load_json(TMP / "sql-canon-retail-grade-readiness.json")
    customer = load_json(TMP / "retail-customer-output-decision-packet.json")
    return {
        "retail_automation_control_plane": {
            "status": control.get("status"),
            "review_only": control.get("review_only"),
            "customer_output_decision": (control.get("customer_output_decision") or {}).get("decision"),
            "customer_output_allowed": (control.get("customer_output_decision") or {}).get("customer_output_allowed"),
            "sql_posture": (control.get("sql_support_health") or {}).get("posture"),
            "a2_sql_read_allowed": (control.get("sql_support_health") or {}).get("a2_sql_read_allowed"),
        },
        "sql_canon_retail_grade_readiness": {
            "status": readiness.get("status"),
            "guard_sql_read_allowed": (readiness.get("summary") or {}).get("guard_sql_read_allowed"),
            "sql_effective_allowed_rows": (readiness.get("summary") or {}).get("sql_effective_allowed_rows"),
            "blocker_rows": (readiness.get("summary") or {}).get("blocker_rows"),
        },
        "customer_output_decision_packet": {
            "status": customer.get("status"),
            "customer_output_allowed": customer.get("customer_output_allowed"),
            "blockers": customer.get("blockers"),
        },
    }


def instrument_type_for_row(row: dict[str, Any]) -> str:
    ticker = str(row.get("ticker") or "").upper()
    card = load_json(TMP / "ticker-intelligence-cards" / f"{ticker}.current.json")
    card_type = str((card or {}).get("instrument_type") or "").lower()
    if card_type:
        return card_type
    return str(row.get("instrument_type") or "").lower()


def split_router_only_rows(router_only_tickers: list[str], router_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for ticker in router_only_tickers:
        row = dict(router_map.get(ticker) or {})
        instrument_type = instrument_type_for_row({"ticker": ticker, **row})
        rows.append({
            "ticker": ticker,
            "instrument_type": instrument_type or None,
            "split_cohort": "fund_or_sector_sleeve" if instrument_type in SLEEVE_ROUTER_ONLY_INSTRUMENT_TYPES else "operating_company_followup",
        })
    sleeve = sorted(row["ticker"] for row in rows if row["split_cohort"] == "fund_or_sector_sleeve")
    operating = sorted(row["ticker"] for row in rows if row["split_cohort"] == "operating_company_followup")
    return {
        "validated": bool(router_only_tickers) and sorted(router_only_tickers) == sorted(sleeve + operating),
        "fund_or_sector_sleeve_tickers": sleeve,
        "operating_company_followup_tickers": operating,
        "rows": rows,
        "policy": (
            "Router-only ETF/fund/sector sleeve names are tracked as a separate Tier A sleeve/proxy subcohort; "
            "router-only operating companies require direct finance-canon/router reconciliation before decision-grade use."
        ),
    }


def build_report() -> dict[str, Any]:
    tier_rows = load_tier_rows()
    finance_map = tier_map(tier_rows["finance_canon_tier_a"])
    plane_map = tier_map(tier_rows["data_plane_tier_a"])
    router_map = tier_map(tier_rows["router_tier_a"])
    finance_tickers = sorted(finance_map)
    plane_tickers = sorted(plane_map)
    router_tickers = sorted(router_map)
    finance_a_ready = [ticker for ticker in finance_tickers if finance_map[ticker].get("auto_state") == "A-READY"]
    plane_a_ready = [ticker for ticker in plane_tickers if plane_map[ticker].get("auto_state") == "A-READY"]

    finance_rows = [evaluate_ticker(ticker, finance_map[ticker], cohort="finance_canon_tier_a") for ticker in finance_tickers]
    plane_rows = [evaluate_ticker(ticker, plane_map[ticker], cohort="data_plane_tier_a") for ticker in plane_tickers]
    router_rows = [evaluate_ticker(ticker, router_map[ticker], cohort="router_tier_a") for ticker in router_tickers]
    finance_a_ready_rows = [
        evaluate_ticker(ticker, finance_map[ticker], cohort="finance_canon_a_ready") for ticker in finance_a_ready
    ]
    plane_a_ready_rows = [
        evaluate_ticker(ticker, plane_map[ticker], cohort="data_plane_a_ready") for ticker in plane_a_ready
    ]

    all_rows = finance_rows + plane_rows
    all_evaluated_rows = finance_rows + plane_rows + router_rows
    unique_rows_by_ticker: dict[str, dict[str, Any]] = {}
    for row in [*finance_rows, *plane_rows, *router_rows]:
        unique_rows_by_ticker[str(row.get("ticker") or "")] = row
    status_counts = Counter(row["status"] for row in all_rows)
    router_status_counts = Counter(row["status"] for row in router_rows)
    depth_blockers = Counter(blocker for row in all_rows for blocker in row["depth_blockers"])
    floor_blockers = Counter(blocker for row in all_rows for blocker in row["floor_blockers"])
    router_depth_blockers = Counter(blocker for row in router_rows for blocker in row["depth_blockers"])
    router_floor_blockers = Counter(blocker for row in router_rows for blocker in row["floor_blockers"])
    strategic_depth_blockers = Counter(blocker for row in plane_a_ready_rows for blocker in row["depth_blockers"])

    router_only_from_finance = sorted(set(router_tickers) - set(finance_tickers))
    finance_only_from_router = sorted(set(finance_tickers) - set(router_tickers))
    router_only_from_data_plane = sorted(set(router_tickers) - set(plane_tickers))
    data_plane_only_from_router = sorted(set(plane_tickers) - set(router_tickers))
    legacy_finance_only = sorted(set(finance_tickers) - set(plane_tickers))
    legacy_data_plane_only = sorted(set(plane_tickers) - set(finance_tickers))
    router_finance_aligned = not router_only_from_finance and not finance_only_from_router
    router_data_plane_aligned = not router_only_from_data_plane and not data_plane_only_from_router
    split_cohort_alignment = split_router_only_rows(router_only_from_finance, router_map)
    split_cohort_alignment_validated = (
        not finance_only_from_router
        and not router_only_from_data_plane
        and not data_plane_only_from_router
        and split_cohort_alignment["validated"]
    )
    tier_definition_diff = {
        "finance_only": router_only_from_finance,
        "data_plane_only": router_only_from_data_plane,
        "router_only_tickers": router_only_from_finance,
        "router_only_from_finance": router_only_from_finance,
        "finance_only_from_router": finance_only_from_router,
        "router_only_from_data_plane": router_only_from_data_plane,
        "data_plane_only_from_router": data_plane_only_from_router,
        "legacy_finance_only_vs_data_plane": legacy_finance_only,
        "legacy_data_plane_only_vs_finance": legacy_data_plane_only,
        "finance_tier_a_count": len(finance_tickers),
        "data_plane_tier_a_count": len(plane_tickers),
        "router_tier_a_count": len(router_tickers),
        "finance_a_ready": finance_a_ready,
        "data_plane_a_ready": plane_a_ready,
        "router_finance_aligned": router_finance_aligned,
        "router_data_plane_aligned": router_data_plane_aligned,
    }

    coverage_floor_ok = all(row["coverage_floor_passed"] for row in all_evaluated_rows)
    depth_ready = all(row["depth_ready"] for row in all_evaluated_rows)
    strategic_depth_ready = all(row["depth_ready"] for row in plane_a_ready_rows)
    tier_definition_aligned = (router_finance_aligned and router_data_plane_aligned) or split_cohort_alignment_validated

    if not coverage_floor_ok:
        status = "blocked_coverage_floor"
    elif not tier_definition_aligned:
        status = "coverage_floor_ok_tier_definition_mismatch"
    elif not strategic_depth_ready:
        status = "coverage_floor_ok_strategic_depth_blocked"
    elif not depth_ready:
        status = "coverage_floor_ok_tier_a_depth_blocked"
    else:
        status = "ready_for_internal_retail_truth_routing_floor"
    decision_grade_allowed_count = (
        0 if not tier_definition_aligned
        else sum(1 for row in unique_rows_by_ticker.values() if row["decision_grade_claim_allowed"])
    )
    parity_retirement_blockers = Counter(
        "section_value_hash_mismatch"
        for row in all_evaluated_rows
        for _blocker in row.get("parity_retirement_blockers", [])
    )
    depth_blocker_details = [
        {
            "ticker": row["ticker"],
            "cohort": row["cohort"],
            "instrument_type": row.get("depth_checks", {}).get("instrument_type"),
            "depth_blockers": row["depth_blockers"],
        }
        for row in all_evaluated_rows
        if row["depth_blockers"]
    ]

    return {
        "schema": "veritas.tier_a_trade_grade_coverage_gate.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "coverage_floor_ok": coverage_floor_ok,
            "depth_ready_all_tier_a": depth_ready,
            "depth_ready_a_ready": strategic_depth_ready,
            "tier_definition_aligned": tier_definition_aligned,
            "router_finance_tier_definition_aligned": router_finance_aligned,
            "split_cohort_alignment_validated": split_cohort_alignment_validated,
            "router_data_plane_tier_definition_aligned": router_data_plane_aligned,
            "router_tier_a_count": len(router_tickers),
            "finance_tier_a_count": len(finance_tickers),
            "data_plane_tier_a_count": len(plane_tickers),
            "router_only_ticker_count": len(router_only_from_finance),
            "router_only_tickers": router_only_from_finance,
            "router_only_from_data_plane_count": len(router_only_from_data_plane),
            "router_only_from_data_plane_tickers": router_only_from_data_plane,
            "finance_only_from_router_count": len(finance_only_from_router),
            "finance_only_from_router_tickers": finance_only_from_router,
            "decision_grade_blocked_by_router_cohort_mismatch": not tier_definition_aligned,
            "finance_a_ready_count": len(finance_a_ready),
            "data_plane_a_ready_count": len(plane_a_ready),
            "status_counts": dict(sorted(status_counts.items())),
            "router_status_counts": dict(sorted(router_status_counts.items())),
            "floor_blocker_counts": dict(floor_blockers.most_common()),
            "router_floor_blocker_counts": dict(router_floor_blockers.most_common()),
            "parity_retirement_blocker_counts": dict(parity_retirement_blockers.most_common()),
            "depth_blocker_counts": dict(depth_blockers.most_common()),
            "router_depth_blocker_counts": dict(router_depth_blockers.most_common()),
            "strategic_a_ready_depth_blocker_counts": dict(strategic_depth_blockers.most_common()),
            "decision_grade_allowed_count": decision_grade_allowed_count,
        },
        "tier_definition_diff": tier_definition_diff,
        "split_cohort_alignment": split_cohort_alignment,
        "depth_blocker_details": depth_blocker_details,
        "governing_standard": {
            "coverage_floor": [
                "Tier A row in SQL canon/data plane",
                "ticker intelligence card present",
                "WF85 full answer present and status ok",
                "full-answer parity present and validation ok",
                "17 required full-answer sections present",
                "source_count >= 18",
                "source_lineage_count >= 17",
                "all authority/execution/customer-output flags false",
            ],
            "depth_gate": [
                "thesis must be synthesized, not just source-family pointers",
                "operating companies need structured competitive moat",
                "operating companies need current sector performance",
                "ETFs/proxies need ETF or macro proxy profile",
                "fresh quote requirement must be cleared before decision-grade or approval-ready claims",
            ],
            "retail_truth_boundary": [
                "Internal retail truth routing can use the gate as proof.",
                "Customer output remains blocked unless the retail customer-output decision packet clears.",
                "No buy/sell/hold/allocation/execution language is granted by this gate.",
            ],
        },
        "retail_context": load_retail_context(),
        "cohorts": {
            "finance_canon_tier_a": finance_rows,
            "data_plane_tier_a": plane_rows,
            "router_tier_a": router_rows,
            "finance_canon_a_ready": finance_a_ready_rows,
            "data_plane_a_ready": plane_a_ready_rows,
        },
        "next_safe_actions": [
            "Keep the coverage floor as a required SQL-canon/WF85 migration gate for Tier A and A-READY cohorts.",
            "Feed depth blockers into WF78/WF85 repair queues rather than treating 17/17 section parity as trade-grade readiness.",
            "Reconcile the finance-canon Tier A cohort against the data-plane Tier A cohort before calling the migration complete.",
            "Keep customer output blocked until retail customer-output approvals, source licensing, privacy, legal/compliance, disclaimer, personalization, external delivery, and security gates clear.",
        ],
        "stop_lines": [
            "This gate does not mutate SQL canon, portfolio notes, cards, full answers, or customer outputs.",
            "This gate does not approve capital deployment, paper/live execution, brokerage/account action, or money movement.",
            "Generated coverage status is review proof only; source-open review remains required before material finance claims.",
        ],
    }


def validate_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "detail": detail})

    add("finance_canon_db_exists", FINANCE_CANON_DB.exists(), rel(FINANCE_CANON_DB))
    add("data_plane_db_exists", DATA_PLANE_DB.exists(), rel(DATA_PLANE_DB))
    add("auto_router_exists", AUTO_ROUTER.exists(), rel(AUTO_ROUTER))
    add("authority_review_only", report.get("authority_boundary", {}).get("review_only") is True)
    add("authority_customer_output_false", report.get("authority_boundary", {}).get("customer_output_allowed") is False)
    add("authority_no_execution", report.get("authority_boundary", {}).get("paper_or_live_execution_allowed") is False)
    add("authority_no_capital", report.get("authority_boundary", {}).get("capital_deployment_approved") is False)
    add("authority_no_owner_approval_inferred", report.get("authority_boundary", {}).get("owner_approval_inferred") is False)
    add("finance_tier_a_present", report.get("summary", {}).get("finance_tier_a_count", 0) > 0)
    add("data_plane_tier_a_present", report.get("summary", {}).get("data_plane_tier_a_count", 0) > 0)
    add("router_tier_a_present", report.get("summary", {}).get("router_tier_a_count", 0) > 0)
    add(
        "coverage_floor_currently_ok",
        report.get("summary", {}).get("coverage_floor_ok") is True,
        report.get("summary", {}).get("floor_blocker_counts"),
        severity="warning",
    )
    add(
        "depth_blockers_reported_when_present",
        isinstance(report.get("summary", {}).get("depth_blocker_counts"), dict),
        report.get("summary", {}).get("depth_blocker_counts"),
    )
    add(
        "retail_customer_output_not_allowed",
        report.get("retail_context", {})
        .get("retail_automation_control_plane", {})
        .get("customer_output_allowed")
        is False,
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Build read-only Tier A trade-grade coverage gate")
    parser.add_argument("--write", action="store_true", help=f"write {OUT_JSON.relative_to(WORKSPACE).as_posix()}")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.validate:
        checks = validate_report(report)
        failed = [check for check in checks if not check["ok"] and check["severity"] == "critical"]
        report["validation"] = {
            "status": "ok" if not failed else "blocked",
            "critical_errors": failed,
            "warnings": [check for check in checks if not check["ok"] and check["severity"] == "warning"],
            "checks": checks,
        }
    if args.write:
        atomic_write_json(OUT_JSON, report)
    print(json.dumps({"status": report["status"], "summary": report["summary"], "validation": report.get("validation")}, indent=2))
    return 0 if report.get("validation", {}).get("status", "ok") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
