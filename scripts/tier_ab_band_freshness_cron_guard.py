#!/usr/bin/env python3
"""Guard Tier A/B decision-grade band freshness in scheduled finance chains.

This is cron proof only. It verifies that Tier A/B rows with decision-grade
band/stop coverage have current price/band-status context, that missing
decision-grade coverage is carried by the WF78 repair packet, and that cron
freshness contracts include the required proof artifacts.
"""
from __future__ import annotations

import argparse
import json
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
DEFAULT_OUT = TMP / "tier-ab-band-freshness-cron-guard.json"

CARDS = TMP / "trade-grade-decision-cards.json"
MISSING_BAND_REPAIR = TMP / "wf78-missing-band-context-repair.json"
REPAIR_CONVEYOR = TMP / "trade-grade-repair-conveyor.json"
WF77_PRICE_BRIDGE = TMP / "wf77-price-freshness-bridge.json"

SCHEMA = "veritas.tier_ab_band_freshness_cron_guard.v1"
TARGET_TIERS = {"Tier A", "Tier B"}
MISSING_BAND_STATUSES = {None, "", "UNKNOWN", "missing_required_refresh"}
CURRENT_PRICE_STATUSES = {
    "post_close_final_quote_available_for_non_executing_review",
    "current_price_technical_available_for_non_executing_review",
    "tier_c_monitor_grade_current_for_non_executing_review",
}

REQUIRED_CRON_ARTIFACTS = {
    "Finance - WF78 Daily Freshness and Promotion Proof": {
        "tmp/wf78-missing-band-context-repair.json",
        "tmp/tier-ab-band-freshness-cron-guard.json",
        "tmp/trade-grade-repair-conveyor.json",
        "tmp/trade-grade-os-freshness-cron-runner.json",
    },
    "Finance - Ticker Card Freshness Owner Runner": {
        "tmp/wf78-missing-band-context-repair.json",
        "tmp/tier-ab-band-freshness-cron-guard.json",
        "tmp/trade-grade-os-freshness-cron-runner.json",
    },
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_guard_only": True,
    "finance_domain_debt_visible": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def target_tier(card: dict[str, Any]) -> str:
    return str(card.get("auto_tier") or card.get("tier") or "")


def stop_present(card: dict[str, Any]) -> bool:
    return as_dict(card.get("stop_or_invalidation")).get("level") is not None


def decision_grade_band_missing(card: dict[str, Any]) -> bool:
    band = as_dict(card.get("entry_band"))
    return (
        band.get("low") is None
        or band.get("high") is None
        or not stop_present(card)
        or band.get("band_status") in MISSING_BAND_STATUSES
    )


def max_market_date(cards: list[dict[str, Any]]) -> str | None:
    dates = [
        str(as_dict(card.get("current_price")).get("market_date"))
        for card in cards
        if as_dict(card.get("current_price")).get("market_date")
    ]
    return max(dates) if dates else None


def bridge_rows_by_ticker(path: Path = WF77_PRICE_BRIDGE) -> dict[str, dict[str, Any]]:
    payload = load(path)
    return {
        ticker(row.get("ticker")): row
        for row in as_list(payload.get("rows"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def effective_current_price(card: dict[str, Any], bridge_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    price = as_dict(card.get("current_price"))
    if price.get("market_date") and price.get("latest_known_price") is not None:
        return {**price, "context_source": "decision_card"}

    bridge_row = as_dict(bridge_rows.get(ticker(card.get("ticker"))))
    bridge_price = as_dict(bridge_row.get("price_state"))
    if bridge_price.get("status") == "ok" and bridge_price.get("latest_close") is not None and bridge_price.get("data_date"):
        return {
            "latest_known_price": bridge_price.get("latest_close"),
            "market_date": bridge_price.get("data_date"),
            "quote_time_utc": None,
            "source": bridge_price.get("source"),
            "quote_freshness_status": "current_price_technical_available_for_non_executing_review",
            "context_source": "wf77_price_freshness_bridge",
            "source_family": bridge_price.get("source_family"),
            "source_label": bridge_price.get("source_label"),
        }
    return {**price, "context_source": "decision_card"}


def current_band_context_ok(card: dict[str, Any], expected_market_date: str | None, bridge_rows: dict[str, dict[str, Any]] | None = None) -> bool:
    price = effective_current_price(card, bridge_rows or {})
    if not expected_market_date:
        return False
    if price.get("latest_known_price") is None:
        return False
    if price.get("market_date") != expected_market_date:
        return False
    return str(price.get("quote_freshness_status") or "") in CURRENT_PRICE_STATUSES


def tier_band_rows(cards: list[dict[str, Any]], expected_market_date: str | None = None, bridge_rows: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    tier_cards = [card for card in cards if target_tier(card) in TARGET_TIERS]
    expected_date = expected_market_date or max_market_date(tier_cards)
    bridge = bridge_rows or {}
    rows: list[dict[str, Any]] = []
    for card in tier_cards:
        band = as_dict(card.get("entry_band"))
        stop = as_dict(card.get("stop_or_invalidation"))
        price = effective_current_price(card, bridge)
        missing = decision_grade_band_missing(card)
        context_current = False if missing else current_band_context_ok(card, expected_date, bridge)
        if missing:
            state = "missing_decision_grade_band"
        elif context_current:
            state = "complete_and_current"
        else:
            state = "stale_complete_band_context"
        rows.append({
            "ticker": ticker(card.get("ticker")),
            "auto_tier": target_tier(card),
            "state": state,
            "decision_grade_band_missing": missing,
            "current_band_context": context_current,
            "expected_market_date": expected_date,
            "market_date": price.get("market_date"),
            "quote_freshness_status": price.get("quote_freshness_status"),
            "current_price_context_source": price.get("context_source"),
            "current_price_source": price.get("source"),
            "latest_known_price_present": price.get("latest_known_price") is not None,
            "band_status": band.get("band_status"),
            "entry_band_low_present": band.get("low") is not None,
            "entry_band_high_present": band.get("high") is not None,
            "stop_or_invalidation_present": stop.get("level") is not None,
            "band_source_timestamp": band.get("source_timestamp"),
            "stop_source_timestamp": stop.get("source_timestamp"),
        })
    return sorted(rows, key=lambda row: (str(row.get("auto_tier")), str(row.get("ticker"))))


def expected_artifact_paths(job: dict[str, Any]) -> set[str]:
    return {str(as_dict(item).get("path") or "").replace("\\", "/") for item in as_list(job.get("expected_artifacts"))}


def cron_contract_checks() -> list[dict[str, Any]]:
    try:
        import cron_freshness_spine  # type: ignore
        contracts = getattr(cron_freshness_spine, "JOB_CONTRACTS", {})
    except Exception as exc:
        return [{
            "job": "cron_freshness_spine",
            "status": "blocked",
            "missing_artifacts": [],
            "error": f"import_failed:{exc}",
        }]

    checks: list[dict[str, Any]] = []
    for job_name, required in REQUIRED_CRON_ARTIFACTS.items():
        contract = as_dict(contracts.get(job_name))
        paths = expected_artifact_paths(contract)
        missing = sorted(required - paths)
        checks.append({
            "job": job_name,
            "status": "ok" if not missing and contract else "blocked",
            "missing_artifacts": missing,
            "observed_artifact_count": len(paths),
        })
    return checks


def build_payload() -> dict[str, Any]:
    cards_payload = load(CARDS)
    cards = [as_dict(card) for card in as_list(cards_payload.get("cards"))]
    bridge_rows = bridge_rows_by_ticker()
    rows = tier_band_rows(cards, bridge_rows=bridge_rows)
    missing_rows = [row for row in rows if row.get("state") == "missing_decision_grade_band"]
    stale_rows = [row for row in rows if row.get("state") == "stale_complete_band_context"]
    complete_rows = [row for row in rows if row.get("state") == "complete_and_current"]
    missing_tickers = sorted(str(row.get("ticker")) for row in missing_rows)

    repair = load(MISSING_BAND_REPAIR)
    repair_summary = as_dict(repair.get("summary"))
    repair_targets = sorted(ticker(item) for item in as_list(repair_summary.get("target_tickers")))
    uncovered_missing_tickers = sorted(set(missing_tickers) - set(repair_targets))

    conveyor = load(REPAIR_CONVEYOR)
    conveyor_summary = as_dict(conveyor.get("summary"))

    contract_checks = cron_contract_checks()
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        errors.append("tier_a_b_cards_missing")
    if stale_rows:
        errors.append("tier_a_b_complete_band_context_stale")
    if repair.get("status") != "ok":
        errors.append("missing_band_repair_status_not_ok")
    if uncovered_missing_tickers:
        errors.append("missing_band_repair_targets_do_not_match_cards")
    if int(conveyor_summary.get("tier_a_b_missing_decision_grade_band_count") or 0) != len(missing_rows):
        errors.append("repair_conveyor_tier_a_b_missing_band_count_mismatch")
    if any(item.get("status") != "ok" for item in contract_checks):
        errors.append("cron_expected_artifact_contract_missing_tier_a_b_band_guard")
    if missing_rows:
        warnings.append("tier_a_b_missing_decision_grade_band_finance_domain_debt")

    tier_counts = Counter(str(row.get("auto_tier")) for row in rows)
    state_counts = Counter(str(row.get("state")) for row in rows)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "warning" if warnings else "ok",
        "purpose": "Cron guard proving Tier A/B decision-grade band freshness stays explicit and finance-domain repair debt does not become implementation noise.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "target_tiers": sorted(TARGET_TIERS),
            "tier_a_b_total_count": len(rows),
            "tier_counts": dict(sorted(tier_counts.items())),
            "state_counts": dict(sorted(state_counts.items())),
            "expected_market_date": rows[0].get("expected_market_date") if rows else None,
            "complete_and_current_count": len(complete_rows),
            "stale_complete_band_context_count": len(stale_rows),
            "stale_complete_band_context_tickers": [str(row.get("ticker")) for row in stale_rows],
            "missing_decision_grade_band_count": len(missing_rows),
            "missing_decision_grade_band_tickers": missing_tickers,
            "missing_decision_grade_band_scope": "finance_domain_debt_not_implementation_blocker",
            "active_missing_band_repair_context_count": len(repair_targets),
            "active_missing_band_repair_context_tickers": repair_targets,
            "missing_band_repair_target_count": len(repair_targets),
            "missing_band_repair_targets_match_cards": not uncovered_missing_tickers,
            "missing_band_repair_uncovered_missing_tickers": uncovered_missing_tickers,
            "repair_conveyor_tier_a_b_missing_count": conveyor_summary.get("tier_a_b_missing_decision_grade_band_count"),
            "implementation_blocker_count": conveyor_summary.get("implementation_blocker_count"),
            "control_plane_blocker_count": conveyor_summary.get("control_plane_blocker_count"),
            "cron_contracts_ok": all(item.get("status") == "ok" for item in contract_checks),
        },
        "rows": rows,
        "cron_contract_checks": contract_checks,
        "source_artifacts": {
            "decision_cards": rel(CARDS),
            "missing_band_repair": rel(MISSING_BAND_REPAIR),
            "repair_conveyor": rel(REPAIR_CONVEYOR),
            "wf77_price_bridge": rel(WF77_PRICE_BRIDGE),
            "cron_freshness_spine_contracts": "scripts/cron_freshness_spine.py",
        },
        "validation": {
            "status": "error" if errors else "warning" if warnings else "ok",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "Missing Tier A/B decision-grade band coverage is finance-domain debt, not an implementation blocker by itself.",
            "This guard does not fabricate, apply, or mutate entry bands, stops, cards, canon, portfolio notes, cash, sizing, or risk rules.",
            "Capital deployment and paper/live execution remain owner-gated.",
        ],
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload, indent=2, ensure_ascii=True)
    print(json.dumps({
        "status": payload["status"],
        "out": rel(out),
        "summary": payload["summary"],
        "validation": payload["validation"],
    }, indent=2))
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
