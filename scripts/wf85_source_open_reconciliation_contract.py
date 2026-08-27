#!/usr/bin/env python3
"""Validate WF85 source-open state reconciliation across producer layers.

This is a review-only contract. It writes proof only and never grants capital,
paper/live execution, account, portfolio, or canon mutation authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SOURCE_GATE = ROOT / "tmp" / "trade-grade-source-freshness-gate.json"
DECISION_CARDS = ROOT / "tmp" / "trade-grade-decision-cards.json"
FULL_ANSWER_ROLLUP = ROOT / "tmp" / "trade-grade-full-answer-assembler.json"
FULL_ANSWER_DIR = ROOT / "tmp" / "trade-grade-full-answer"
CACHE_FRONTDOOR = ROOT / "tmp" / "finance-cache-frontdoor.json"
DEFAULT_OUT = ROOT / "tmp" / "wf85-source-open-reconciliation-contract.json"

BLOCKED_SOURCE_OPEN = "blocked_missing_source_open"
FRESH_STATUSES = {"fresh", "scoped_thin_monitor_not_required"}
PRODUCER_ORDER_GRACE_SECONDS = 120

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "owner_approval_inferred": False,
}

REPAIR_ORDER = [
    "python scripts\\trade_grade_decision_cards.py --write --validate",
    "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
    "python scripts\\finance_cache_frontdoor.py --write --validate",
    "python scripts\\wf85_source_open_reconciliation_contract.py --write --validate",
]


@dataclass(frozen=True)
class ContractPaths:
    source_gate: Path = SOURCE_GATE
    decision_cards: Path = DECISION_CARDS
    full_answer_rollup: Path = FULL_ANSWER_ROLLUP
    full_answer_dir: Path = FULL_ANSWER_DIR
    cache_frontdoor: Path = CACHE_FRONTDOOR


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rows_by_ticker(rows: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(rows):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def artifact_meta(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
    }


def source_verified(row: dict[str, Any]) -> bool:
    return row.get("source_open_status") == "verified"


def freshness_ok(row: dict[str, Any]) -> bool:
    return row.get("freshness_status") in FRESH_STATUSES


def decision_state(row: dict[str, Any]) -> str:
    return str(row.get("decision_state") or "")


def add_mismatch(
    mismatches: list[dict[str, Any]],
    *,
    ticker: str,
    kind: str,
    severity: str,
    detail: dict[str, Any],
) -> None:
    mismatches.append({
        "ticker": ticker,
        "kind": kind,
        "severity": severity,
        "detail": detail,
    })


def validate_producer_order(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    parsed = [(item, parse_ts(item.get("generated_at_utc"))) for item in artifacts]
    for item, stamp in parsed:
        if not item.get("exists"):
            errors.append({"kind": "missing_artifact", "artifact": item})
        elif stamp is None:
            errors.append({"kind": "missing_generated_at", "artifact": item})
    for (left, left_ts), (right, right_ts) in zip(parsed, parsed[1:]):
        if left_ts is None or right_ts is None:
            continue
        skew_seconds = (left_ts - right_ts).total_seconds()
        if skew_seconds > PRODUCER_ORDER_GRACE_SECONDS:
            errors.append({
                "kind": "downstream_older_than_upstream",
                "skew_seconds": round(skew_seconds, 3),
                "grace_seconds": PRODUCER_ORDER_GRACE_SECONDS,
                "upstream": left,
                "downstream": right,
            })
    return errors


def full_answer_machine_state(paths: ContractPaths, ticker: str) -> dict[str, Any]:
    payload = load_json(paths.full_answer_dir / f"{ticker}.json")
    return as_dict(payload.get("machine_state"))


def normalize_ticker_scope(tickers: set[str] | None) -> set[str] | None:
    if not tickers:
        return None
    return {str(ticker).upper() for ticker in tickers if str(ticker).strip()}


def filter_rows_by_scope(rows: dict[str, dict[str, Any]], ticker_scope: set[str] | None) -> dict[str, dict[str, Any]]:
    if ticker_scope is None:
        return rows
    return {ticker: row for ticker, row in rows.items() if ticker in ticker_scope}


def build_contract(paths: ContractPaths, ticker_scope: set[str] | None = None) -> dict[str, Any]:
    ticker_scope = normalize_ticker_scope(ticker_scope)
    source_gate = load_json(paths.source_gate)
    decision_cards = load_json(paths.decision_cards)
    full_rollup = load_json(paths.full_answer_rollup)
    cache = load_json(paths.cache_frontdoor)

    source_rows = filter_rows_by_scope(rows_by_ticker(source_gate.get("rows")), ticker_scope)
    card_rows = filter_rows_by_scope(rows_by_ticker(decision_cards.get("cards")), ticker_scope)
    full_result_rows = filter_rows_by_scope(rows_by_ticker(full_rollup.get("results")), ticker_scope)
    cache_rows = filter_rows_by_scope(rows_by_ticker(cache.get("rows")), ticker_scope)

    artifacts = [
        artifact_meta("trade_grade_source_freshness_gate", paths.source_gate, source_gate),
        artifact_meta("trade_grade_decision_cards", paths.decision_cards, decision_cards),
        artifact_meta("trade_grade_full_answer_assembler", paths.full_answer_rollup, full_rollup),
        artifact_meta("finance_cache_frontdoor", paths.cache_frontdoor, cache),
    ]
    producer_order_errors = validate_producer_order(artifacts)

    tickers = sorted((ticker_scope or set()) | set(source_rows) | set(card_rows) | set(full_result_rows) | set(cache_rows))
    mismatches: list[dict[str, Any]] = []
    unnecessary_blockers: list[str] = []
    wrong_blocker_reasons: list[str] = []

    for ticker in tickers:
        source = source_rows.get(ticker, {})
        card = card_rows.get(ticker, {})
        full_result = full_result_rows.get(ticker, {})
        full_machine = full_answer_machine_state(paths, ticker)
        cache_row = cache_rows.get(ticker, {})

        verified = source_verified(source)
        fresh = freshness_ok(source)

        if verified and decision_state(card) == BLOCKED_SOURCE_OPEN:
            kind = "fresh_verified_card_unnecessary_source_open_block" if fresh else "verified_card_wrong_source_open_blocker"
            severity = "error" if fresh else "warning"
            add_mismatch(
                mismatches,
                ticker=ticker,
                kind=kind,
                severity=severity,
                detail={
                    "source_open_status": source.get("source_open_status"),
                    "freshness_status": source.get("freshness_status"),
                    "card_decision_state": decision_state(card),
                    "card_reason": card.get("decision_state_reason"),
                },
            )
            (unnecessary_blockers if fresh else wrong_blocker_reasons).append(ticker)

        full_state = decision_state(full_result) or decision_state(full_machine)
        card_state = decision_state(card)
        if card_state and full_state and card_state != full_state:
            add_mismatch(
                mismatches,
                ticker=ticker,
                kind="decision_card_full_answer_state_mismatch",
                severity="error",
                detail={
                    "card_decision_state": card_state,
                    "full_answer_decision_state": full_state,
                    "full_answer_path": rel(paths.full_answer_dir / f"{ticker}.json"),
                },
            )

        if verified and full_state == BLOCKED_SOURCE_OPEN:
            kind = "fresh_verified_full_answer_unnecessary_source_open_block" if fresh else "verified_full_answer_wrong_source_open_blocker"
            severity = "error" if fresh else "warning"
            add_mismatch(
                mismatches,
                ticker=ticker,
                kind=kind,
                severity=severity,
                detail={
                    "source_open_status": source.get("source_open_status"),
                    "freshness_status": source.get("freshness_status"),
                    "full_answer_decision_state": full_state,
                },
            )
            (unnecessary_blockers if fresh else wrong_blocker_reasons).append(ticker)

        cache_state = decision_state(cache_row)
        if full_state and cache_state and full_state != cache_state:
            add_mismatch(
                mismatches,
                ticker=ticker,
                kind="full_answer_cache_state_mismatch",
                severity="error",
                detail={
                    "full_answer_decision_state": full_state,
                    "cache_decision_state": cache_state,
                    "cache_path": rel(paths.cache_frontdoor),
                },
            )

        if verified and cache_state == BLOCKED_SOURCE_OPEN:
            kind = "fresh_verified_cache_unnecessary_source_open_block" if fresh else "verified_cache_wrong_source_open_blocker"
            severity = "error" if fresh else "warning"
            add_mismatch(
                mismatches,
                ticker=ticker,
                kind=kind,
                severity=severity,
                detail={
                    "source_open_status": source.get("source_open_status"),
                    "freshness_status": source.get("freshness_status"),
                    "cache_decision_state": cache_state,
                    "material_claim_requires_source_open": cache_row.get("material_claim_requires_source_open"),
                },
            )
            (unnecessary_blockers if fresh else wrong_blocker_reasons).append(ticker)

        if verified and cache_row.get("material_claim_requires_source_open") is True:
            add_mismatch(
                mismatches,
                ticker=ticker,
                kind="verified_source_marked_material_source_open_required",
                severity="error",
                detail={
                    "source_open_status": source.get("source_open_status"),
                    "cache_material_claim_requires_source_open": cache_row.get("material_claim_requires_source_open"),
                    "cache_needs_refresh_reason": cache_row.get("needs_refresh_reason"),
                },
            )

    errors = [item for item in mismatches if item.get("severity") == "error"]
    warnings = [item for item in mismatches if item.get("severity") == "warning"]
    status = "blocked" if errors or producer_order_errors else "ok"

    return {
        "schema": "veritas.wf85_source_open_reconciliation_contract.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow_ids": ["WF84", "WF85"],
        "scope": {
            "mode": "ticker" if ticker_scope else "all",
            "tickers": sorted(ticker_scope) if ticker_scope else "all",
        },
        "purpose": "Detect stale or contradictory WF85 source-open state so verified fresh tickers are not left blocked by source-open residue.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "root_cause_contract": {
            "source_gate_is_upstream": rel(paths.source_gate),
            "decision_cards_must_follow_source_gate": rel(paths.decision_cards),
            "full_answers_must_follow_decision_cards": rel(paths.full_answer_rollup),
            "cache_frontdoor_must_follow_full_answers": rel(paths.cache_frontdoor),
            "do_not_weaken_source_open_policy": True,
            "repair_mode": "refresh stale downstream producers and block contradictions; do not infer approval or execution authority",
        },
        "producer_order": {
            "artifacts": artifacts,
            "errors": producer_order_errors,
        },
        "summary": {
            "ticker_count": len(tickers),
            "source_gate_ticker_count": len(source_rows),
            "decision_card_ticker_count": len(card_rows),
            "full_answer_ticker_count": len(full_result_rows),
            "cache_ticker_count": len(cache_rows),
            "verified_source_open_count": sum(1 for row in source_rows.values() if source_verified(row)),
            "fresh_verified_source_count": sum(1 for row in source_rows.values() if source_verified(row) and freshness_ok(row)),
            "unnecessary_source_open_blocker_count": len(set(unnecessary_blockers)),
            "wrong_source_open_blocker_reason_count": len(set(wrong_blocker_reasons)),
            "mismatch_error_count": len(errors),
            "mismatch_warning_count": len(warnings),
            "producer_order_error_count": len(producer_order_errors),
        },
        "mismatches": mismatches[:250],
        "repair_contract": {
            "name": "WF85 source-open reconciliation repair contract",
            "classification": "review_only_finance_support_contract",
            "repair_order": REPAIR_ORDER,
            "acceptance": [
                "producer_order_error_count == 0",
                "unnecessary_source_open_blocker_count == 0",
                "mismatch_error_count == 0",
                "source_open_status=verified never coexists with blocked_missing_source_open in decision cards, WF85 full answers, or finance cache",
            ],
            "stop_lines": [
                "No finance canon, portfolio, cash, sizing, risk-rule, paper/live, brokerage, account, or owner-approval mutation.",
                "Do not turn verified source-open into deployment authority; review_ready remains owner-gated and not approved.",
            ],
        },
        "validation": {
            "status": "ok" if status == "ok" else "blocked",
            "errors": errors[:100] + producer_order_errors[:100],
            "warnings": warnings[:100],
        },
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-gate", type=Path, default=SOURCE_GATE)
    parser.add_argument("--decision-cards", type=Path, default=DECISION_CARDS)
    parser.add_argument("--full-answer-rollup", type=Path, default=FULL_ANSWER_ROLLUP)
    parser.add_argument("--full-answer-dir", type=Path, default=FULL_ANSWER_DIR)
    parser.add_argument("--cache-frontdoor", type=Path, default=CACHE_FRONTDOOR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ticker", action="append", default=[], help="Limit reconciliation to one or more ticker symbols.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    paths = ContractPaths(
        source_gate=args.source_gate,
        decision_cards=args.decision_cards,
        full_answer_rollup=args.full_answer_rollup,
        full_answer_dir=args.full_answer_dir,
        cache_frontdoor=args.cache_frontdoor,
    )
    packet = build_contract(paths, set(args.ticker) if args.ticker else None)
    if args.write:
        atomic_write_json(args.out, packet)
    print(json.dumps({
        "status": packet["status"],
        "out": rel(args.out),
        "summary": packet["summary"],
        "repair_order": packet["repair_contract"]["repair_order"],
    }))
    if args.validate and packet["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
