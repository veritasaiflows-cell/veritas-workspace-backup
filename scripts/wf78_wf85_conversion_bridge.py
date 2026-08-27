#!/usr/bin/env python3
"""Convert WF78 opportunity signals into WF85 owner-review cards.

This is a review-only automation bridge. It turns WF78 promotion visibility,
Tier C opportunity scoring, WF85 timing gates, and trade-grade cards into an
owner-review queue. It does not create approval cards, WF67 requests, capital
authority, portfolio/canon mutations, or execution authority.
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
OUT = TMP / "wf78-wf85-conversion-bridge.json"
CARDS_OUT = TMP / "wf85-owner-review-cards.json"
SCHEMA = "veritas.wf78_wf85_conversion_bridge.v1"
CARDS_SCHEMA = "veritas.wf85_owner_review_cards.v1"

SOURCES = {
    "promotion_visibility": TMP / "wf78-promotion-visibility-top10.json",
    "tier_c_scoreboard": TMP / "wf78-tier-c-opportunity-scoreboard.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "trade_grade_cards": TMP / "trade-grade-decision-cards.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "owner_review_card_generation_allowed": True,
    "approval_card_generation_allowed": False,
    "wf67_request_generation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "registry_apply_allowed": False,
    "owner_lineage_apply_allowed": False,
    "sql_canon_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

ROW_FALSE_FIELDS = {
    "approval_card_generated": False,
    "wf67_request_generated": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False} | set(ROW_FALSE_FIELDS)

TIMING_PRIORITY = {
    "review_ready_wait_approval": 110.0,
    "review_ready_suppressed": 96.0,
    "repair_first": 72.0,
    "wait_no_chase": 58.0,
    "blocked_below_stop_or_invalidation": 48.0,
}

SOURCE_PRIORITY = {
    "owner_review_ready": 105.0,
    "c_to_b_evidence_complete": 88.0,
    "tier_c_attention": 78.0,
    "evidence_repair": 56.0,
    "repair_or_wait": 52.0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def ticker_of(row: dict[str, Any]) -> str:
    return clean_text(row.get("ticker")).upper()


def unique(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        text = clean_text(item)
        if text and text not in out:
            out.append(text)
    return out


def rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "cards", "candidates", "items"):
        raw = payload.get(key)
        if isinstance(raw, list):
            return [as_dict(row) for row in raw if isinstance(row, dict)]
    return []


def by_ticker(row_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in row_list:
        ticker = ticker_of(row)
        if ticker:
            out[ticker] = row
    return out


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FALSE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{index}]"))
    return paths


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_drift_paths": authority_true_paths(payload),
    }


def evidence_gaps(card: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    for family in as_list(card.get("evidence_family_status")):
        family = as_dict(family)
        family_id = clean_text(family.get("family_id"))
        status = clean_text(family.get("status"))
        resolution = clean_text(family.get("resolution_state"))
        missing = int(family.get("missing_count") or 0)
        stale = int(family.get("stale_count") or 0)
        if family_id and (missing > 0 or stale > 0 or status in {"missing", "stale", "blocked"} or resolution in {"missing", "stale", "blocked"}):
            gaps.append(family_id)
    gaps.extend(as_list(as_dict(card.get("source_freshness")).get("blockers")))
    gaps.extend(card.get("decision_state_reason") or [])
    return unique(gaps)


def candidate(candidates: dict[str, dict[str, Any]], ticker: str) -> dict[str, Any]:
    row = candidates.setdefault(
        ticker,
        {
            "ticker": ticker,
            "name": None,
            "auto_tier": None,
            "auto_state": None,
            "current_price": None,
            "entry_band": None,
            "stop_or_invalidation": None,
            "source_signals": [],
            "source_artifacts": [],
            "blockers": [],
            "evidence_gaps": [],
            "score_components": [],
            "timing_state": None,
            "decision_state": None,
            "macro_sector": None,
            "price_band_gate": None,
            "price_band_status": None,
        },
    )
    return row


def add_signal(row: dict[str, Any], signal: str, score: float, source_artifacts: list[Any] | None = None) -> None:
    if signal not in row["source_signals"]:
        row["source_signals"].append(signal)
    row["score_components"].append({"signal": signal, "score": round(float(score), 2)})
    row["source_artifacts"] = unique([*row["source_artifacts"], *(source_artifacts or [])])


def merge_common(row: dict[str, Any], source: dict[str, Any]) -> None:
    row["name"] = row["name"] or source.get("name")
    row["auto_tier"] = row["auto_tier"] or source.get("auto_tier") or source.get("router_tier")
    row["auto_state"] = row["auto_state"] or source.get("auto_state") or source.get("router_state")
    row["current_price"] = row["current_price"] or source.get("current_price") or source.get("latest_close")
    row["entry_band"] = row["entry_band"] or source.get("entry_band")
    row["stop_or_invalidation"] = row["stop_or_invalidation"] or source.get("stop_or_invalidation")
    row["blockers"] = unique([*row["blockers"], *as_list(source.get("blockers")), *as_list(source.get("actionability_blockers"))])
    row["source_artifacts"] = unique([*row["source_artifacts"], *as_list(source.get("source_artifacts"))])


def add_promotion_visibility(candidates: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
    for source in rows(payload):
        ticker = ticker_of(source)
        if not ticker:
            continue
        source_lane = clean_text(source.get("source_lane")) or clean_text(source.get("visibility_state"))
        if source_lane not in SOURCE_PRIORITY and source.get("rank", 999) > 40:
            continue
        row = candidate(candidates, ticker)
        merge_common(row, source)
        score = float(source.get("score") or 0.0)
        score = min(100.0, score / 10.0) if score > 100 else score
        score = max(score, SOURCE_PRIORITY.get(source_lane, 45.0))
        add_signal(row, f"wf78_promotion_visibility:{source_lane}", score, source.get("source_artifacts"))


def add_tier_c_scoreboard(candidates: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
    recommended = set(clean_text(item).upper() for item in as_list(as_dict(payload.get("summary")).get("recommended_next_batch")))
    for source in rows(payload):
        ticker = ticker_of(source)
        if not ticker:
            continue
        bucket = clean_text(source.get("bucket"))
        rank = int(source.get("rank") or 999)
        if ticker not in recommended and bucket not in {"promote_watch", "repair_first"} and rank > 25:
            continue
        row = candidate(candidates, ticker)
        merge_common(row, source)
        row["price_band_status"] = row["price_band_status"] or source.get("band_status")
        signal = "tier_c_next_batch" if ticker in recommended else f"tier_c_{bucket or 'attention'}"
        score = float(source.get("opportunity_score") or 0.0)
        if ticker in recommended:
            score += 10.0
        add_signal(row, signal, score, source.get("source_artifacts"))


def add_timing_gate(candidates: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
    for source in rows(payload):
        ticker = ticker_of(source)
        if not ticker:
            continue
        tier = clean_text(source.get("auto_tier"))
        timing_state = clean_text(source.get("final_timing_state"))
        if tier not in {"Tier A", "Tier B"} and timing_state not in TIMING_PRIORITY:
            continue
        row = candidate(candidates, ticker)
        merge_common(row, source)
        row["timing_state"] = row["timing_state"] or timing_state
        row["decision_state"] = row["decision_state"] or source.get("decision_state")
        row["macro_sector"] = row["macro_sector"] or source.get("macro_sector")
        row["price_band_gate"] = row["price_band_gate"] or source.get("price_band_gate")
        row["price_band_status"] = row["price_band_status"] or as_dict(source.get("entry_band")).get("band_status")
        row["blockers"] = unique([
            *row["blockers"],
            *as_list(source.get("final_timing_reasons")),
            *as_list(source.get("price_band_reasons")),
            *as_list(source.get("earnings_reasons")),
            *as_list(source.get("macro_sector_reasons")),
        ])
        source_paths = [
            as_dict(source.get("entry_band")).get("source_path"),
            as_dict(source.get("stop_or_invalidation")).get("source_path"),
            as_dict(source.get("earnings")).get("source_path"),
        ]
        add_signal(row, f"wf85_timing:{timing_state}", TIMING_PRIORITY.get(timing_state, 42.0), source_paths)


def merge_trade_grade_cards(candidates: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
    for ticker, card in by_ticker(rows(payload)).items():
        if ticker not in candidates:
            continue
        row = candidate(candidates, ticker)
        row["name"] = row["name"] or card.get("name")
        row["auto_tier"] = row["auto_tier"] or card.get("auto_tier")
        row["auto_state"] = row["auto_state"] or card.get("auto_state")
        row["decision_state"] = row["decision_state"] or card.get("decision_state")
        row["entry_band"] = row["entry_band"] or card.get("entry_band")
        row["stop_or_invalidation"] = row["stop_or_invalidation"] or card.get("stop_or_invalidation")
        price = as_dict(card.get("current_price"))
        row["current_price"] = row["current_price"] or price.get("latest_known_price")
        row["evidence_gaps"] = unique([*row["evidence_gaps"], *evidence_gaps(card)])
        row["blockers"] = unique([*row["blockers"], *as_list(as_dict(card.get("source_freshness")).get("blockers"))])
        row["source_artifacts"] = unique([
            *row["source_artifacts"],
            *[as_dict(item).get("path") for item in as_list(card.get("source_drillback"))],
        ])
        add_signal(row, f"trade_grade_card:{card.get('decision_state') or 'unknown'}", 30.0)


def card_state(row: dict[str, Any]) -> str:
    signals = set(row.get("source_signals") or [])
    timing_state = clean_text(row.get("timing_state"))
    if timing_state == "review_ready_wait_approval":
        return "approval_card_candidate_blocked_pending_owner_review"
    if timing_state == "review_ready_suppressed":
        return "owner_review_ready_not_approval_clean"
    if timing_state == "wait_no_chase":
        return "market_timing_wait_no_chase"
    if timing_state == "blocked_below_stop_or_invalidation":
        return "invalidation_or_below_stop_review"
    if any(signal.startswith("tier_c_next_batch") for signal in signals):
        return "tier_c_promotion_repair_candidate"
    if any("c_to_b_evidence_complete" in signal for signal in signals):
        return "tier_c_to_b_promotion_review_candidate"
    return "evidence_repair_required"


def next_automation_action(row: dict[str, Any]) -> str:
    state = row["owner_review_card_state"]
    blockers = set(row.get("blockers") or [])
    gaps = set(row.get("evidence_gaps") or [])
    if state == "owner_review_ready_not_approval_clean":
        return "source_open_earnings_and_material_claims_then_recheck_approval_card_gate"
    if state == "approval_card_candidate_blocked_pending_owner_review":
        return "prepare_exact_owner_approval_card_after_fresh_market_and_wf67_guard_proof"
    if state == "market_timing_wait_no_chase":
        return "keep_market_timing_watch_until_band_or_reclaim_signal_improves"
    if state == "invalidation_or_below_stop_review":
        return "review_invalidation_or_reclaim_before_any_deployment_discussion"
    if "technical_posture_missing" in blockers or "price_band_stop" in gaps:
        return "repair_price_band_stop_and_technical_posture"
    if any("official" in item or "earnings" in item for item in blockers | gaps):
        return "source_open_official_earnings_growth_guidance_and_management_commentary"
    if any("orders_backlog" in item or "backlog" in item for item in blockers | gaps):
        return "repair_orders_backlog_or_book_to_bill_evidence"
    return "run_bounded_evidence_repair_batch_then_rebuild_wf84_wf85"


def card_priority(row: dict[str, Any]) -> float:
    total = max((float(item.get("score") or 0.0) for item in row.get("score_components") or []), default=0.0)
    if row.get("auto_tier") == "Tier A":
        total += 12
    elif row.get("auto_tier") == "Tier B":
        total += 7
    if row.get("owner_review_card_state") == "owner_review_ready_not_approval_clean":
        total += 18
    elif row.get("owner_review_card_state") == "tier_c_promotion_repair_candidate":
        total += 8
    if row.get("price_band_status") in {"IN_BAND", "BELOW_BAND"}:
        total += 5
    total -= min(18, len(row.get("blockers") or []) * 1.5)
    return round(max(0.0, min(total, 120.0)), 2)


def finalize_card(row: dict[str, Any], rank: int) -> dict[str, Any]:
    row["owner_review_card_state"] = card_state(row)
    row["priority_score"] = card_priority(row)
    row["next_automation_action"] = next_automation_action(row)
    return {
        "rank": rank,
        "ticker": row["ticker"],
        "name": row.get("name"),
        "auto_tier": row.get("auto_tier"),
        "auto_state": row.get("auto_state"),
        "owner_review_card_state": row["owner_review_card_state"],
        "priority_score": row["priority_score"],
        "current_price": row.get("current_price"),
        "entry_band": row.get("entry_band"),
        "stop_or_invalidation": row.get("stop_or_invalidation"),
        "price_band_gate": row.get("price_band_gate"),
        "price_band_status": row.get("price_band_status"),
        "timing_state": row.get("timing_state"),
        "decision_state": row.get("decision_state"),
        "macro_sector": row.get("macro_sector"),
        "source_signals": row.get("source_signals"),
        "blockers": row.get("blockers"),
        "evidence_gaps": row.get("evidence_gaps"),
        "source_artifacts": row.get("source_artifacts"),
        "next_automation_action": row["next_automation_action"],
        "owner_action_required": row["owner_review_card_state"] in {
            "owner_review_ready_not_approval_clean",
            "approval_card_candidate_blocked_pending_owner_review",
        },
        "automation_action_allowed": True,
        "approval_card_generated": False,
        "wf67_request_generated": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "owner_approval_inferred": False,
        "not_approved_stamp": "NOT APPROVED - review card only; Randall exact approval required before any capital or execution step",
    }


def build_cards(payloads: dict[str, dict[str, Any]], max_cards: int) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    add_promotion_visibility(candidates, payloads["promotion_visibility"])
    add_tier_c_scoreboard(candidates, payloads["tier_c_scoreboard"])
    add_timing_gate(candidates, payloads["wf85_timing_gate"])
    merge_trade_grade_cards(candidates, payloads["trade_grade_cards"])
    staged = list(candidates.values())
    for row in staged:
        row["owner_review_card_state"] = card_state(row)
        row["priority_score"] = card_priority(row)
    staged.sort(key=lambda item: (-float(item.get("priority_score") or 0.0), str(item.get("ticker") or "")))
    return [finalize_card(row, index + 1) for index, row in enumerate(staged[:max_cards])]


def build_payload(paths: dict[str, Path], *, max_cards: int = 80) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads = {name: load(path) for name, path in paths.items()}
    cards = build_cards(payloads, max_cards=max_cards)
    state_counts = Counter(str(card.get("owner_review_card_state") or "unknown") for card in cards)
    tier_counts = Counter(str(card.get("auto_tier") or "unknown") for card in cards)
    next_actions = Counter(str(card.get("next_automation_action") or "unknown") for card in cards)
    source_records = [source_record(name, path, payloads[name]) for name, path in paths.items()]
    summary = {
        "owner_review_card_count": len(cards),
        "state_counts": dict(state_counts),
        "tier_counts": dict(tier_counts),
        "next_automation_action_counts": dict(next_actions),
        "top_tickers": [card["ticker"] for card in cards[:15]],
        "tier_c_next_batch_carded": [
            card["ticker"]
            for card in cards
            if "tier_c_next_batch" in set(card.get("source_signals") or [])
        ],
        "owner_action_required_count": sum(1 for card in cards if card.get("owner_action_required") is True),
        "capital_deployment_approved_count": 0,
        "trade_or_execution_approved_count": 0,
        "paper_or_live_execution_allowed_count": 0,
        "wf67_request_generated_count": 0,
        "approval_card_generated_count": 0,
        "next_safe_action": "Cron may refresh and surface owner-review cards; capital deployment and paper/live execution remain Randall-gated.",
    }
    cards_payload = {
        "schema": CARDS_SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF85",
        "status": "draft",
        "purpose": "Intermediate owner-review cards from WF78 opportunity signals and WF85 timing gates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "cards": cards,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "source_records": source_records,
        "stop_lines": [
            "Owner-review cards are not capital approval.",
            "No WF67 request, paper/live order, brokerage/account action, money movement, or owner approval is created.",
            "No canon, portfolio, cash, sizing, sleeve, risk-rule, SQL-canon, or registry mutation is allowed.",
        ],
    }
    cards_payload["validation"] = validate_cards(cards_payload)
    cards_payload["status"] = "ok" if cards_payload["validation"]["status"] in {"ok", "warning"} else "blocked"

    bridge = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF78/WF85",
        "status": "draft",
        "purpose": "Review-only WF78 to WF85 conversion bridge for automatic opportunity surfacing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            **summary,
            "source_count": len(source_records),
            "card_artifact": rel(CARDS_OUT),
        },
        "source_records": source_records,
        "card_artifact": rel(CARDS_OUT),
        "top_cards": cards[:20],
        "stop_lines": cards_payload["stop_lines"],
    }
    bridge["validation"] = validate_bridge(bridge, cards_payload)
    bridge["status"] = "ok" if bridge["validation"]["status"] in {"ok", "warning"} else "blocked"
    return bridge, cards_payload


def validate_cards(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append(f"authority_drift:{','.join(drift[:8])}")
    for record in as_list(payload.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("authority_drift_paths"):
            errors.append(f"source_authority_drift:{record.get('name')}")
    cards = as_list(payload.get("cards"))
    if not cards:
        errors.append("no_owner_review_cards_generated")
    for index, card in enumerate(cards):
        if not card.get("ticker"):
            errors.append(f"card_{index}_missing_ticker")
        if not card.get("source_signals"):
            errors.append(f"card_{index}_missing_source_signals")
        for key, expected in ROW_FALSE_FIELDS.items():
            if card.get(key) is not expected:
                errors.append(f"card_{card.get('ticker') or index}_{key}_not_false")
    summary = as_dict(payload.get("summary"))
    for key in ("capital_deployment_approved_count", "trade_or_execution_approved_count", "paper_or_live_execution_allowed_count"):
        if summary.get(key):
            errors.append(f"{key}_nonzero")
    if summary.get("owner_review_card_count", 0) > 0 and summary.get("owner_action_required_count", 0) == 0:
        warnings.append("no_owner_action_required_cards_currently_carded")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def validate_bridge(bridge: dict[str, Any], cards_payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if as_dict(cards_payload.get("validation")).get("status") == "error":
        errors.append("cards_payload_validation_error")
    drift = authority_true_paths(bridge)
    if drift:
        errors.append(f"authority_drift:{','.join(drift[:8])}")
    if as_dict(bridge.get("summary")).get("owner_review_card_count", 0) != len(as_list(cards_payload.get("cards"))):
        errors.append("bridge_card_count_mismatch")
    for record in as_list(bridge.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("validation_status") == "error":
            warnings.append(f"source_validation_error:{record.get('name')}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, path in SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--cards-out", type=Path, default=CARDS_OUT)
    parser.add_argument("--max-cards", type=int, default=80)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        key: (value if value.is_absolute() else ROOT / value)
        for key, value in vars(args).items()
        if key in SOURCES
    }
    bridge, cards_payload = build_payload(paths, max_cards=args.max_cards)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    cards_out = args.cards_out if args.cards_out.is_absolute() else ROOT / args.cards_out
    bridge["card_artifact"] = rel(cards_out)
    bridge["summary"]["card_artifact"] = rel(cards_out)
    if args.write:
        atomic_write_json(cards_out, cards_payload)
        atomic_write_json(out, bridge)
    response = bridge if args.pretty else {
        "status": bridge.get("status"),
        "validation": bridge.get("validation"),
        "summary": bridge.get("summary"),
        "out": rel(out) if args.write else None,
        "cards_out": rel(cards_out) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and (
        as_dict(bridge.get("validation")).get("status") == "error"
        or as_dict(cards_payload.get("validation")).get("status") == "error"
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
