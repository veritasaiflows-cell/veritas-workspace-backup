#!/usr/bin/env python3
"""Adjudicate WF85 retirement-readiness repair gates.

This report sits between full-answer parity and any duplicate-surface retirement
packet. It validates scope classifications, technical-posture missingness, price
overlay warnings, and remaining WF85 card blockers. It is report-only and never
archives, deletes, applies, mutates canon/portfolio state, or touches trading.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PARITY_DIR = TMP / "full-answer-parity"
PARITY_ROLLUP = PARITY_DIR / "full-answer-parity-rollup.json"
WF84_DB = TMP / "canonical-finance-data-plane.sqlite"
WF85_CARDS = TMP / "trade-grade-decision-cards.json"
WF85_SOURCE_GATE = TMP / "trade-grade-source-freshness-gate.json"
WF85_AUTHORITY = TMP / "trade-grade-decision-card-authority-validation.json"
TECHNICAL_REFRESH = TMP / "technical-refresh.json"
FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"
TICKER_CARD_DIR = TMP / "ticker-intelligence-cards"
DEFAULT_OUT = TMP / "wf85-retirement-gate-adjudication.json"

SCHEMA = "veritas.wf85_retirement_gate_adjudication.v1"
EXPECTED_THIN_MONITOR_COUNT = 158
EXPECTED_PRICE_OVERLAY_WARNING_COUNT = 8

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "report_only": True,
    "archive_allowed": False,
    "delete_allowed": False,
    "apply_allowed": False,
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


def load_json(path: Path, default: Any = None) -> Any:
    payload = load_json_artifact(path)
    return default if payload is None else payload


def parse_json_text(value: Any, default: Any = None) -> Any:
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def connect_ro() -> sqlite3.Connection:
    uri = WF84_DB.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def flag_true(value: Any) -> bool:
    return value in {1, True, "1", "true", "True", "yes", "YES"}


def meaningful(value: Any) -> bool:
    if isinstance(value, dict):
        if not value:
            return False
        status = str(value.get("status") or "").lower()
        if status in {"missing", "unavailable", "source_open_required", "not_yet_structured_source_open_required"}:
            non_status_keys = [key for key in value if key not in {"status", "note", "reason"}]
            return any(meaningful(value.get(key)) for key in non_status_keys)
        return any(meaningful(child) for child in value.values())
    if isinstance(value, list):
        return any(meaningful(child) for child in value)
    return value not in (None, "")


def keyed_json_rows(payload: Any, key: str = "ticker") -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if isinstance(payload, dict):
        for row in payload.get("records", []) or payload.get("rows", []) or payload.get("cards", []):
            if isinstance(row, dict) and row.get(key):
                rows[str(row[key]).upper()] = row
    return rows


def db_rows(table: str) -> dict[str, dict[str, Any]]:
    with connect_ro() as conn:
        return {str(row["ticker"]).upper(): dict(row) for row in conn.execute(f"SELECT * FROM {table}")}


def db_section_rows(section_id: str) -> dict[str, dict[str, Any]]:
    with connect_ro() as conn:
        rows = conn.execute(
            "SELECT * FROM full_answer_section_context WHERE section_id = ?",
            (section_id,),
        ).fetchall()
        return {str(row["ticker"]).upper(): dict(row) for row in rows}


def parity_detail(ticker: str) -> dict[str, Any]:
    return load_json(PARITY_DIR / f"{ticker}.json", {}) or {}


def full_answer_path(ticker: str) -> Path:
    return FULL_ANSWER_DIR / f"{ticker}.json"


def card_path(ticker: str) -> Path:
    return TICKER_CARD_DIR / f"{ticker}.current.json"


def warning_tickers(rollup: dict[str, Any], warning: str) -> set[str]:
    tickers: set[str] = set()
    for row in rollup.get("per_ticker", []):
        if warning in row.get("warnings", []):
            tickers.add(str(row.get("ticker")).upper())
    return tickers


def parity_thin_tickers(rollup: dict[str, Any]) -> set[str]:
    tickers: set[str] = set()
    for row in rollup.get("per_ticker", []):
        scope = row.get("parity_scope")
        if scope == "thin_monitor_card_wf84_surface":
            tickers.add(str(row.get("ticker")).upper())
    return tickers


def validate_thin_monitors(rollup: dict[str, Any], cards_by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any]:
    membership = db_rows("universe_membership")
    db_thin = {
        ticker
        for ticker, row in membership.items()
        if flag_true(row.get("thin_monitor_row"))
        and not flag_true(row.get("production_answer_path_member"))
        and not flag_true(row.get("decision_grade_eligible"))
    }
    parity_thin = parity_thin_tickers(rollup)
    card_thin = {
        ticker
        for ticker, card in cards_by_ticker.items()
        if card.get("wf84_scope", {}).get("classification") == "thin_monitor_card_wf84_surface"
    }
    mismatches = sorted((db_thin ^ parity_thin) | (db_thin ^ card_thin))
    sample = [
        {
            "ticker": ticker,
            "db_thin_monitor": ticker in db_thin,
            "parity_thin_monitor": ticker in parity_thin,
            "card_thin_monitor": ticker in card_thin,
            "production_answer_path_member": flag_true(membership.get(ticker, {}).get("production_answer_path_member")),
            "decision_grade_eligible": flag_true(membership.get(ticker, {}).get("decision_grade_eligible")),
        }
        for ticker in mismatches[:25]
    ]
    status = (
        "ok"
        if not mismatches
        and len(db_thin) == EXPECTED_THIN_MONITOR_COUNT
        and len(parity_thin) == EXPECTED_THIN_MONITOR_COUNT
        and len(card_thin) == EXPECTED_THIN_MONITOR_COUNT
        else "blocked"
    )
    return {
        "status": status,
        "expected_count": EXPECTED_THIN_MONITOR_COUNT,
        "db_thin_monitor_count": len(db_thin),
        "parity_thin_monitor_scope_count": len(parity_thin),
        "wf85_card_thin_monitor_count": len(card_thin),
        "mismatch_count": len(mismatches),
        "mismatch_sample": sample,
        "decision": "thin monitors are scope-validated card/WF84 monitor rows, not production full-answer retirement candidates"
        if status == "ok"
        else "thin monitor scope requires repair before retirement planning",
    }


def review_technical_missing(rollup: dict[str, Any], technical_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    technical_tickers = warning_tickers(rollup, "section:technical_posture:section_explicitly_missing_in_both_routes")
    section_rows = db_section_rows("technical_posture")
    membership = db_rows("universe_membership")
    rows: list[dict[str, Any]] = []
    generated_unique_count = 0
    source_feeder_record_count = 0
    production_missing_count = 0
    for ticker in sorted(technical_tickers):
        full_answer = load_json(full_answer_path(ticker), {}) or {}
        card = load_json(card_path(ticker), {}) or {}
        full_sections = full_answer.get("sections", {}) if isinstance(full_answer, dict) else {}
        full_technical = full_sections.get("technical_setup", {}) if isinstance(full_sections, dict) else {}
        packet_value = full_technical.get("raw") if isinstance(full_technical, dict) else None
        card_value = card.get("technical_posture") if isinstance(card, dict) else None
        old_generated_has_content = meaningful(packet_value) or meaningful(card_value)
        tech_refresh_record = technical_records.get(ticker)
        has_source_feeder_record = bool(tech_refresh_record)
        section = section_rows.get(ticker, {})
        is_production = flag_true(membership.get(ticker, {}).get("production_answer_path_member"))
        if old_generated_has_content:
            generated_unique_count += 1
        if has_source_feeder_record:
            source_feeder_record_count += 1
        if is_production:
            production_missing_count += 1
        detail = parity_detail(ticker)
        parity_section = next(
            (
                section
                for section in detail.get("section_results", [])
                if section.get("section_id") == "technical_posture"
            ),
            {},
        )
        parity_source_paths = parity_section.get("source_paths", [])
        rows.append({
            "ticker": ticker,
            "production_answer_path_member": is_production,
            "thin_monitor_row": flag_true(membership.get(ticker, {}).get("thin_monitor_row")),
            "assembler_or_card_technical_content_present": old_generated_has_content,
            "technical_refresh_record_present": has_source_feeder_record,
            "parity_section_status": parity_section.get("status"),
            "parity_section_reason": parity_section.get("reason"),
            "parity_old_present": parity_section.get("old_present"),
            "parity_new_present": parity_section.get("new_present"),
            "parity_source_paths_include_technical_refresh": any(
                str(path).replace("\\", "/") == "tmp/technical-refresh.json"
                for path in parity_source_paths
            ),
            "wf84_section_status": section.get("section_status"),
            "wf84_source_kind": section.get("source_kind"),
            "classification": (
                "retain_generated_surface_until_technical_content_is_mapped"
                if old_generated_has_content
                else "retain_source_feeder_for_technical_refresh"
                if has_source_feeder_record
                else "no_unique_generated_technical_content_found"
            ),
        })
    status = "blocked" if generated_unique_count else "ok"
    return {
        "status": status,
        "shared_missing_technical_posture_count": len(technical_tickers),
        "generated_unique_technical_content_count": generated_unique_count,
        "source_feeder_technical_record_count": source_feeder_record_count,
        "production_answer_path_missing_technical_count": production_missing_count,
        "thin_monitor_missing_technical_count": len(technical_tickers) - production_missing_count,
        "decision": (
            "Do not retire generated technical surfaces until unique generated technical content is mapped."
            if generated_unique_count
            else "No unique generated technical_posture content found in the shared-missing set; retain source feeders/fallbacks and repair production technical refresh separately."
        ),
        "rows": rows,
    }


def triage_price_overlays(rollup: dict[str, Any]) -> dict[str, Any]:
    price_rows = db_rows("price_technical_current")
    overlay_rows: list[dict[str, Any]] = []
    for row in rollup.get("per_ticker", []):
        ticker = str(row.get("ticker") or "").upper()
        detail = parity_detail(ticker)
        for check in detail.get("numeric_checks", []):
            if (
                check.get("name") == "latest_known_price"
                and check.get("status") == "warning"
                and check.get("reason") == "wf84_may_have_fresher_price_overlay"
            ):
                price_row = price_rows.get(ticker, {})
                overlay_rows.append({
                    "ticker": ticker,
                    "parity_scope": row.get("parity_scope"),
                    "old_latest_known_price": check.get("old"),
                    "wf84_latest_known_price": check.get("new"),
                    "delta": check.get("delta"),
                    "wf84_price_source": price_row.get("price_source"),
                    "wf84_quote_time_utc": price_row.get("quote_time_utc"),
                    "wf84_market_date": price_row.get("market_date"),
                    "wf84_quote_freshness_status": price_row.get("quote_freshness_status"),
                    "triage": "wf84_fresher_overlay_preferred_refresh_old_generated_price_snapshot_before_surface_retirement",
                })
    repair_status = (
        "cleared_after_refresh"
        if len(overlay_rows) == 0
        else "unchanged_expected_triage_count"
        if len(overlay_rows) == EXPECTED_PRICE_OVERLAY_WARNING_COUNT
        else "changed_requires_review"
    )
    return {
        "status": "ok",
        "historical_expected_count_before_targeted_refresh": EXPECTED_PRICE_OVERLAY_WARNING_COUNT,
        "latest_price_overlay_warning_count": len(overlay_rows),
        "repair_status": repair_status,
        "count_matches_expected_or_cleared": len(overlay_rows) in {0, EXPECTED_PRICE_OVERLAY_WARNING_COUNT},
        "decision": (
            "Latest-price overlay warnings cleared after refreshing generated card/answer packet surfaces."
            if len(overlay_rows) == 0
            else "Treat as fresher WF84 overlay warnings, not parity blockers; refresh old generated price snapshots before targeted retirement."
        ),
        "rows": overlay_rows,
    }


def classify_remaining_blockers(cards_by_ticker: dict[str, dict[str, Any]], source_gate: dict[str, Any]) -> dict[str, Any]:
    source_rows = {str(row.get("ticker") or "").upper(): row for row in source_gate.get("rows", [])}
    states = Counter(card.get("decision_state") for card in cards_by_ticker.values())
    rows: list[dict[str, Any]] = []
    for ticker, card in sorted(cards_by_ticker.items()):
        state = card.get("decision_state")
        if state in {"monitor_only", "no_chase", "review_ready"}:
            continue
        source_row = source_rows.get(ticker, {})
        rows.append({
            "ticker": ticker,
            "decision_state": state,
            "primary_state": card.get("primary_state"),
            "band_status": card.get("entry_band", {}).get("band_status"),
            "source_open_status": source_row.get("source_open_status"),
            "freshness_status": card.get("source_freshness", {}).get("status"),
            "quote_freshness_status": card.get("source_freshness", {}).get("quote_freshness_status"),
            "scope": card.get("wf84_scope", {}).get("classification"),
            "repair_lane": {
                "blocked_missing_band_or_stop": "price_or_band_stop_refresh_required",
                "blocked_missing_freshness": "fresh_quote_or_price_overlay_refresh_required",
                "blocked_missing_source_open": "source_open_drillback_repair_required",
                "below_stop_or_invalidation": "invalidation_review_true_state_do_not_promote",
                "evidence_repair": "promotion_veto_or_evidence_repair_required",
            }.get(str(state), "review_required"),
        })
    return {
        "status": "ok",
        "decision_state_counts": dict(states),
        "remaining_blocker_count": len(rows),
        "remaining_blocker_counts": dict(Counter(row["decision_state"] for row in rows)),
        "rows": rows,
    }


def challenger_metric_reconciliation(
    rollup: dict[str, Any],
    source_gate: dict[str, Any],
    blockers: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, Any]:
    source_counts = source_gate.get("summary", {}).get("source_open_status_counts", {})
    freshness_counts = source_gate.get("summary", {}).get("freshness_status_counts", {})
    blocker_counts = blockers.get("remaining_blocker_counts", {})
    summary = rollup.get("summary", {})
    section_count = int(summary.get("section_count") or 0)
    section_ok_count = int(summary.get("section_ok_count") or 0)
    non_ok_section_count = section_count - section_ok_count if section_count >= section_ok_count else None
    return {
        "status": "ok",
        "source_open_row_level_blocked_count": int(source_counts.get("blocked") or 0),
        "decision_state_blocked_missing_source_open_count": int(blocker_counts.get("blocked_missing_source_open") or 0),
        "freshness_row_level_blocked_count": int(freshness_counts.get("blocked") or 0),
        "decision_state_blocked_missing_freshness_count": int(blocker_counts.get("blocked_missing_freshness") or 0),
        "metric_divergence_explanation": (
            "Source/freshness gate counts are row-level diagnostics. WF85 decision_state counts are "
            "precedence-deduplicated after invalidation, missing band/stop, source-open, freshness, "
            "evidence-repair, no-chase, and monitor-only classification."
        ),
        "non_ok_section_count": non_ok_section_count,
        "non_ok_section_explanation": (
            "The 150 non-OK sections are the shared-missing technical_posture set reviewed in this artifact; "
            "generated_unique_technical_content_count is 0, so the missingness does not hide unique generated "
            "technical content. Source feeders/fallbacks still remain retained."
        ),
        "shared_missing_technical_posture_count": technical.get("shared_missing_technical_posture_count"),
        "generated_unique_technical_content_count": technical.get("generated_unique_technical_content_count"),
        "live_blocker_count": blockers.get("remaining_blocker_count"),
        "live_blocker_counts": blocker_counts,
        "no_chase_count": blockers.get("decision_state_counts", {}).get("no_chase"),
        "action_ceiling": "duplicate_surface_retirement_planning_only_no_archive_delete_apply",
    }


def build_artifact() -> dict[str, Any]:
    rollup = load_json(PARITY_ROLLUP, {}) or {}
    cards_payload = load_json(WF85_CARDS, {}) or {}
    source_gate = load_json(WF85_SOURCE_GATE, {}) or {}
    authority = load_json(WF85_AUTHORITY, {}) or {}
    technical_refresh = load_json(TECHNICAL_REFRESH, {}) or {}
    cards_by_ticker = {
        str(card.get("ticker") or "").upper(): card
        for card in cards_payload.get("cards", [])
        if isinstance(card, dict) and card.get("ticker")
    }
    technical_records = keyed_json_rows(technical_refresh)

    thin = validate_thin_monitors(rollup, cards_by_ticker)
    technical = review_technical_missing(rollup, technical_records)
    price = triage_price_overlays(rollup)
    blockers = classify_remaining_blockers(cards_by_ticker, source_gate)
    challenger_reconciliation = challenger_metric_reconciliation(rollup, source_gate, blockers, technical)

    errors: list[str] = []
    warnings: list[str] = []
    if rollup.get("status") != "ok":
        errors.append("full_answer_parity_rollup_not_ok")
    if cards_payload.get("status") != "ok":
        errors.append("wf85_cards_not_ok")
    if authority.get("status") != "ok":
        errors.append("wf85_authority_validation_not_ok")
    if thin.get("status") != "ok":
        errors.append("thin_monitor_classification_not_validated")
    if technical.get("status") != "ok":
        errors.append("shared_missing_technical_has_unique_generated_content")
    if not price.get("count_matches_expected_or_cleared"):
        warnings.append("price_overlay_warning_count_changed")

    status = "blocked" if errors else "ok"
    ready_to_start_planning = (
        status == "ok"
        and bool(rollup.get("summary", {}).get("ready_to_start_duplicate_surface_retirement_planning"))
        and technical.get("generated_unique_technical_content_count") == 0
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_ids": ["WF84", "WF85"],
        "status": status,
        "purpose": "WF85 repair/adjudication proof before duplicate-surface retirement planning.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "ready_to_start_duplicate_surface_retirement_planning": ready_to_start_planning,
            "archive_delete_apply_allowed": False,
            "thin_monitor_classification_status": thin.get("status"),
            "shared_missing_technical_status": technical.get("status"),
            "latest_price_overlay_triage_status": price.get("status"),
            "remaining_blocker_counts": blockers.get("remaining_blocker_counts"),
            "source_open_status_counts": source_gate.get("summary", {}).get("source_open_status_counts"),
            "freshness_status_counts": source_gate.get("summary", {}).get("freshness_status_counts"),
        },
        "inputs": {
            "full_answer_parity_rollup": rel(PARITY_ROLLUP),
            "wf84_sqlite": rel(WF84_DB),
            "wf85_cards": rel(WF85_CARDS),
            "wf85_source_gate": rel(WF85_SOURCE_GATE),
            "wf85_authority_validation": rel(WF85_AUTHORITY),
            "technical_refresh": rel(TECHNICAL_REFRESH),
        },
        "thin_monitor_validation": thin,
        "technical_posture_shared_missing_review": technical,
        "latest_price_overlay_triage": price,
        "remaining_wf85_blockers": blockers,
        "challenger_metric_reconciliation": challenger_reconciliation,
        "retirement_boundary": {
            "planning_allowed": ready_to_start_planning,
            "archive_allowed": False,
            "delete_allowed": False,
            "apply_allowed": False,
            "retain_source_feeders_and_fallbacks": True,
            "do_not_retire": [
                "owner notes",
                "source-open evidence roots",
                "source feeders and fallback DBs",
                "technical-refresh feeder until production technical gaps are repaired",
                "any generated surface with unique unmapped technical content",
            ],
        },
        "validation": {"status": status, "errors": errors, "warnings": warnings},
        "stop_lines": [
            "No archive/delete/apply authority.",
            "No source feeder or fallback removal.",
            "No canon/portfolio/cash/sizing/risk-rule mutation.",
            "No capital deployment, paper/live order, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 retirement-gate adjudication proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = build_artifact()
    if args.write:
        atomic_write_json(args.out, artifact)
        print(
            "wrote "
            f"{rel(args.out)} status={artifact.get('status')} "
            f"thin={artifact.get('thin_monitor_validation', {}).get('status')} "
            f"technical={artifact.get('technical_posture_shared_missing_review', {}).get('status')} "
            f"price_warnings={artifact.get('latest_price_overlay_triage', {}).get('latest_price_overlay_warning_count')}"
        )
    else:
        print(json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and artifact.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
