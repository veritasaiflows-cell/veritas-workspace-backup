#!/usr/bin/env python3
"""Build targeted WF85 production-blocker repair proof.

This report closes the targeted WF84/WF85 production blocker repair pass. It
records what was repaired, what became true no-chase/invalidation state, and
what remains blocked by an upstream promotion veto. It is report-only: no
archive/delete/apply, no source feeder retirement, and no finance authority.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf85-production-blocker-repair.json"

WF85_CARDS = TMP / "trade-grade-decision-cards.json"
SOURCE_GATE = TMP / "trade-grade-source-freshness-gate.json"
ADJUDICATION = TMP / "wf85-retirement-gate-adjudication.json"
PARITY_ROLLUP = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
RETIREMENT_READINESS = TMP / "canonical-finance-data-plane-retirement-readiness.json"
POST_CLOSE_LEDGER = TMP / "post-close-final-quote-ledger.json"
SUPPLEMENTAL_PRICE = TMP / "wf77-supplemental-price-evidence.json"
PRICE_BRIDGE = TMP / "wf77-price-freshness-bridge.json"

SCHEMA = "veritas.wf85_production_blocker_repair.v1"

BASELINE_COUNTS = {
    "blocked_missing_band_or_stop": 2,
    "blocked_missing_freshness": 7,
    "blocked_missing_source_open": 1,
    "evidence_repair": 2,
    "below_stop_or_invalidation": 11,
    "no_chase": 7,
    "review_ready": 1,
}

TARGETS = {
    "missing_band_or_stop": ["SLV", "TLT"],
    "freshness_blockers": ["LIN", "PAVE", "VAW", "VXUS", "XLE", "XLF", "XLI"],
    "source_open_blockers": ["SMCI"],
    "promotion_veto_adjudication": ["ETN", "NVDA"],
    "baseline_invalidation_review": ["AMZN", "CME", "ECL", "KTOS", "LMT", "LNG", "META", "NFLX", "TMUS", "VMC", "XLC"],
    "baseline_no_chase_review": ["GS", "ITA", "JPM", "AMD", "CAT", "GE", "LLY"],
}

TERMINAL_BLOCKER_STATES = {
    "blocked_missing_band_or_stop",
    "blocked_missing_freshness",
    "blocked_missing_source_open",
}

NO_CHASE_BANDS = {"ABOVE_BAND", "ABOVE_BAND_WAIT", "BELOW_BAND", "BELOW_BAND_WAIT"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "report_only": True,
    "archive_allowed": False,
    "delete_allowed": False,
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


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def cards_by_ticker(cards_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(card.get("ticker") or "").upper(): card
        for card in as_list(cards_payload.get("cards"))
        if isinstance(card, dict) and card.get("ticker")
    }


def source_rows_by_ticker(source_gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(source_gate.get("rows"))
        if isinstance(row, dict) and row.get("ticker")
    }


def quote_ok_counts(path: Path) -> dict[str, Any]:
    payload = load_dict(path)
    summary = as_dict(payload.get("summary"))
    return {
        "path": rel(path),
        "status": payload.get("status"),
        "target_count": summary.get("target_count") or summary.get("record_count"),
        "ok_count": summary.get("ok_count"),
        "latest_market_date": summary.get("latest_market_date") or summary.get("latest_market_data_date"),
        "problem_tickers": summary.get("error_tickers") or summary.get("problem_tickers") or [],
    }


def compact_card_row(ticker: str, card: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    entry_band = as_dict(card.get("entry_band"))
    current_price = as_dict(card.get("current_price"))
    freshness = as_dict(card.get("source_freshness"))
    return {
        "ticker": ticker,
        "decision_state": card.get("decision_state"),
        "primary_state": card.get("primary_state"),
        "auto_state": card.get("auto_state"),
        "latest_known_price": current_price.get("latest_known_price"),
        "market_date": current_price.get("market_date"),
        "quote_freshness_status": freshness.get("quote_freshness_status"),
        "freshness_status": freshness.get("status"),
        "source_open_status": source_row.get("source_open_status"),
        "band_status": entry_band.get("band_status"),
        "entry_band_low": entry_band.get("low"),
        "entry_band_high": entry_band.get("high"),
        "stop_or_invalidation": as_dict(card.get("stop_or_invalidation")).get("level"),
        "decision_state_reason": card.get("decision_state_reason"),
    }


def target_rows(tickers: list[str], cards: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [compact_card_row(ticker, cards.get(ticker, {}), sources.get(ticker, {})) for ticker in tickers]


def all_not_terminal(rows: list[dict[str, Any]]) -> bool:
    return all(row.get("decision_state") not in TERMINAL_BLOCKER_STATES for row in rows)


def all_fresh_and_verified(rows: list[dict[str, Any]]) -> bool:
    return all(row.get("freshness_status") == "fresh" and row.get("source_open_status") == "verified" for row in rows)


def invalidation_rows_are_true(rows: list[dict[str, Any]]) -> bool:
    return all(
        row.get("decision_state") == "below_stop_or_invalidation"
        and row.get("band_status") == "BELOW_STOP"
        and row.get("latest_known_price") is not None
        and row.get("stop_or_invalidation") is not None
        for row in rows
    )


def no_chase_rows_are_true(rows: list[dict[str, Any]]) -> bool:
    return all(
        row.get("decision_state") == "no_chase"
        and row.get("band_status") in NO_CHASE_BANDS
        and row.get("latest_known_price") is not None
        for row in rows
    )


def phase_result(phase: int, name: str, status: str, detail: Any) -> dict[str, Any]:
    return {"phase": phase, "name": name, "status": status, "detail": detail}


def build_artifact() -> dict[str, Any]:
    cards_payload = load_dict(WF85_CARDS)
    source_gate = load_dict(SOURCE_GATE)
    adjudication = load_dict(ADJUDICATION)
    parity = load_dict(PARITY_ROLLUP)
    readiness = load_dict(RETIREMENT_READINESS)
    cards = cards_by_ticker(cards_payload)
    sources = source_rows_by_ticker(source_gate)
    state_counts = Counter(card.get("decision_state") for card in cards.values())

    missing_band_rows = target_rows(TARGETS["missing_band_or_stop"], cards, sources)
    freshness_rows = target_rows(TARGETS["freshness_blockers"], cards, sources)
    source_open_rows = target_rows(TARGETS["source_open_blockers"], cards, sources)
    veto_rows = target_rows(TARGETS["promotion_veto_adjudication"], cards, sources)
    invalidation_rows = [
        compact_card_row(ticker, card, sources.get(ticker, {}))
        for ticker, card in sorted(cards.items())
        if card.get("decision_state") == "below_stop_or_invalidation"
    ]
    no_chase_rows = [
        compact_card_row(ticker, card, sources.get(ticker, {}))
        for ticker, card in sorted(cards.items())
        if card.get("decision_state") == "no_chase"
    ]

    blockers_cleared = all(
        int(state_counts.get(state) or 0) == 0
        for state in TERMINAL_BLOCKER_STATES
    )
    target_freshness_clean = all_fresh_and_verified(freshness_rows)
    target_source_open_clean = all_fresh_and_verified(source_open_rows)
    target_missing_band_clean = all_not_terminal(missing_band_rows) and all(
        row.get("latest_known_price") is not None
        and row.get("entry_band_low") is not None
        and row.get("entry_band_high") is not None
        and row.get("stop_or_invalidation") is not None
        for row in missing_band_rows
    )
    promotion_veto_preserved = all(
        row.get("decision_state") == "evidence_repair"
        and row.get("primary_state") == "promotion_vetoed"
        and row.get("freshness_status") == "fresh"
        and row.get("source_open_status") == "verified"
        for row in veto_rows
    )
    true_invalidation = invalidation_rows_are_true(invalidation_rows)
    true_no_chase = no_chase_rows_are_true(no_chase_rows)

    errors: list[str] = []
    warnings: list[str] = []
    if not blockers_cleared:
        errors.append("terminal_production_blockers_remain")
    if not target_missing_band_clean:
        errors.append("missing_band_or_stop_targets_not_repaired")
    if not target_freshness_clean:
        errors.append("freshness_targets_not_clean")
    if not target_source_open_clean:
        errors.append("source_open_targets_not_clean")
    if not promotion_veto_preserved:
        errors.append("promotion_veto_adjudication_not_preserved")
    if not true_invalidation:
        errors.append("below_stop_or_invalidation_rows_not_all_true_state")
    if not true_no_chase:
        errors.append("no_chase_rows_not_all_true_state")
    if cards_payload.get("status") != "ok":
        errors.append("wf85_cards_status_not_ok")
    if parity.get("status") != "ok":
        errors.append("full_answer_parity_status_not_ok")
    if readiness.get("status") != "ok":
        errors.append("retirement_readiness_status_not_ok")
    if int(cards_payload.get("summary", {}).get("approval_card_draft_count") or 0) != 0:
        errors.append("approval_card_draft_count_not_zero")
    if adjudication.get("status") != "ok":
        warnings.append("retirement_gate_adjudication_not_ok")

    phase_results = [
        phase_result(0, "freeze_baseline", "complete", {"baseline_counts": BASELINE_COUNTS}),
        phase_result(1, "repair_slv_tlt_price_band_stop", "complete" if target_missing_band_clean else "blocked", {"rows": missing_band_rows}),
        phase_result(2, "refresh_freshness_blockers", "complete" if target_freshness_clean else "blocked", {"rows": freshness_rows}),
        phase_result(3, "source_open_smci", "complete" if target_source_open_clean else "blocked", {"rows": source_open_rows}),
        phase_result(4, "adjudicate_etn_nvda_promotion_vetoes", "complete" if promotion_veto_preserved else "blocked", {"rows": veto_rows, "decision": "retain evidence_repair until upstream promotion veto clears"}),
        phase_result(5, "confirm_true_no_chase_and_invalidation", "complete" if true_invalidation and true_no_chase else "blocked", {"below_stop_rows": invalidation_rows, "no_chase_rows": no_chase_rows}),
        phase_result(6, "rebuild_parity_and_readiness_proof", "complete" if parity.get("status") == "ok" and readiness.get("status") == "ok" else "blocked", {"parity_summary": parity.get("summary"), "retirement_readiness_summary": readiness.get("summary")}),
        phase_result(7, "prepare_planning_only_retirement_packet", "complete" if as_dict(readiness.get("summary")).get("approval_plan_prepared") is True else "blocked", {"archive_delete_apply_allowed": False, "source_feeder_retirement_allowed": False}),
    ]

    status = "ok" if not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_ids": ["WF84", "WF85"],
        "status": status,
        "purpose": "Targeted production blocker repair proof for WF85 before duplicate-surface retirement planning.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf85_cards": rel(WF85_CARDS),
            "source_gate": rel(SOURCE_GATE),
            "full_answer_parity_rollup": rel(PARITY_ROLLUP),
            "retirement_gate_adjudication": rel(ADJUDICATION),
            "retirement_readiness": rel(RETIREMENT_READINESS),
            "post_close_quote_ledger": rel(POST_CLOSE_LEDGER),
            "supplemental_price_evidence": rel(SUPPLEMENTAL_PRICE),
            "price_freshness_bridge": rel(PRICE_BRIDGE),
        },
        "evidence_inputs": {
            "post_close_quote_ledger": quote_ok_counts(POST_CLOSE_LEDGER),
            "supplemental_price_evidence": quote_ok_counts(SUPPLEMENTAL_PRICE),
            "price_freshness_bridge": {
                "path": rel(PRICE_BRIDGE),
                "status": load_dict(PRICE_BRIDGE).get("status"),
                "summary": load_dict(PRICE_BRIDGE).get("summary"),
            },
        },
        "baseline_counts": BASELINE_COUNTS,
        "current_counts": dict(state_counts),
        "deltas": {
            key: int(state_counts.get(key) or 0) - int(BASELINE_COUNTS.get(key) or 0)
            for key in sorted(set(BASELINE_COUNTS) | set(state_counts))
        },
        "target_groups": TARGETS,
        "phase_results": phase_results,
        "remaining_true_state": {
            "below_stop_or_invalidation_count": len(invalidation_rows),
            "below_stop_or_invalidation_tickers": [row["ticker"] for row in invalidation_rows],
            "no_chase_count": len(no_chase_rows),
            "no_chase_tickers": [row["ticker"] for row in no_chase_rows],
            "evidence_repair_count": len(veto_rows),
            "evidence_repair_tickers": [row["ticker"] for row in veto_rows],
        },
        "promotion_boundary": {
            "review_ready_tickers": [ticker for ticker, card in sorted(cards.items()) if card.get("decision_state") == "review_ready"],
            "approval_card_draft_count": cards_payload.get("summary", {}).get("approval_card_draft_count"),
            "approval_card_drafts_allowed_now": False,
            "reason": "Post-close/review quote freshness is not execution-fresh quote context; ETN/NVDA retain promotion vetoes.",
        },
        "retirement_boundary": {
            "ready_to_start_duplicate_surface_retirement_planning": as_dict(parity.get("summary")).get("ready_to_start_duplicate_surface_retirement_planning") is True,
            "archive_allowed": False,
            "delete_allowed": False,
            "apply_allowed": False,
            "source_feeder_retirement_allowed": False,
            "fallback_removal_allowed": False,
            "owner_exact_approval_required_before_any_archive_packet": True,
        },
        "validation": {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "checks": {
                "terminal_blockers_cleared": blockers_cleared,
                "target_missing_band_clean": target_missing_band_clean,
                "target_freshness_clean": target_freshness_clean,
                "target_source_open_clean": target_source_open_clean,
                "promotion_veto_preserved": promotion_veto_preserved,
                "true_invalidation_rows": true_invalidation,
                "true_no_chase_rows": true_no_chase,
            },
        },
        "stop_lines": [
            "No archive/delete/apply authority.",
            "No source feeder or fallback retirement.",
            "No canon/portfolio/cash/sizing/risk-rule mutation.",
            "No capital deployment, paper/live order, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 targeted production blocker repair proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    artifact = build_artifact()
    if args.write:
        atomic_write_json(out, artifact)
        print(
            "wrote "
            f"{rel(out)} status={artifact['status']} "
            f"terminal_blockers={artifact['validation']['checks']['terminal_blockers_cleared']} "
            f"below_stop={artifact['remaining_true_state']['below_stop_or_invalidation_count']} "
            f"no_chase={artifact['remaining_true_state']['no_chase_count']} "
            f"evidence_repair={artifact['remaining_true_state']['evidence_repair_count']}"
        )
    else:
        print(json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and artifact["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
