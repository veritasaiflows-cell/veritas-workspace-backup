#!/usr/bin/env python3
"""Build the WF85 review-only opportunity visibility queue.

This consumes the WF78 opportunity visibility queue and WF85 timing/cards to
produce an operator-facing view of candidates that are ready for review,
waiting for a market refresh, or blocked by substantive evidence/timing debt.
It is not an approval or execution surface.
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
OUT = TMP / "wf85-opportunity-visibility-queue.json"
SCHEMA = "veritas.wf85_opportunity_visibility_queue.v1"

SOURCES = {
    "wf78_visibility_queue": TMP / "wf78-opportunity-visibility-queue.json",
    "trade_grade_cards": TMP / "trade-grade-decision-cards.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "finance_decision_factory": TMP / "finance-decision-factory.json",
    "market_loop": TMP / "finance-market-deployment-operating-loop.json",
    # These two intraday inputs are optional for compatibility with the
    # ordinary pre-/post-market queue, but become authoritative *review-only*
    # context whenever an eligible overlay row exists.
    "in_band_review_attention": TMP / "in-band-review-attention-bridge.json",
    "intraday_review_overlay": TMP / "wf85-intraday-review-overlay.json",
}

OPTIONAL_SOURCES = {"in_band_review_attention", "intraday_review_overlay"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "wf85_visibility_only": True,
    "owner_review_card_preparation_reference_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}


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


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FALSE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "required": name not in OPTIONAL_SOURCES,
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_drift_paths": authority_true_paths(payload),
    }


def by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row = as_dict(row)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def attention_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index fresh attention rows, retaining repair semantics if duplicated."""
    rows: dict[str, dict[str, Any]] = {}
    for section in ("review_attention", "repair_attention"):
        for raw in as_list(payload.get(section)):
            row = as_dict(raw)
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                rows[ticker] = row
    return rows


def active_overlay_by_ticker(payload: dict[str, Any], now: datetime) -> dict[str, dict[str, Any]]:
    """Return only overlay rows whose review-only quote has not expired.

    An overlay is deliberately a short-lived market-hours surface.  Retaining
    an old row in the general queue would recreate the cadence defect as a
    misleading recommendation, so expiration downgrades it to attention-only
    repair rather than preserving it as current review context.
    """
    if payload.get("status") not in {"ok", "warning"}:
        return {}
    validation = as_dict(payload.get("validation"))
    if validation.get("status") not in {"ok", "warning"}:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for raw in as_list(payload.get("rows")):
        row = as_dict(raw)
        ticker = str(row.get("ticker") or "").upper().strip()
        quote = as_dict(row.get("current_price"))
        freshness = as_dict(row.get("source_freshness"))
        expires_at = parse_utc(freshness.get("expires_at_utc"))
        if (
            not ticker
            or expires_at is None
            or expires_at <= now
            or quote.get("quote_freshness_status") != "intraday_review_only_fresh"
            or quote.get("review_only_quote") is not True
            or quote.get("approval_draft_eligible") is not False
            or freshness.get("fresh_for_review") is not True
            or freshness.get("fresh_for_approval") is not False
        ):
            continue
        rows[ticker] = row
    return rows


def intraday_priority(overlay: dict[str, Any], attention: dict[str, Any]) -> int:
    if not overlay:
        return 100
    priority = 10 if overlay.get("auto_tier") == "Tier A" else 20
    if attention.get("attention_type") == "technical_surface_conflict":
        priority -= 5
    return priority


def market_state(market_loop: dict[str, Any]) -> dict[str, Any]:
    session = as_dict(market_loop.get("market_session"))
    return {
        "final_market_deployment_state": market_loop.get("final_market_deployment_state"),
        "operator_action": market_loop.get("operator_action"),
        "fresh_price_allowed": session.get("deployment_fresh_price_allowed") is True,
        "window": session.get("window"),
    }


def classify(
    row: dict[str, Any],
    card: dict[str, Any],
    timing: dict[str, Any],
    market: dict[str, Any],
    overlay: dict[str, Any],
    attention: dict[str, Any],
) -> tuple[str, list[str]]:
    blockers = set(str(item) for item in as_list(row.get("blockers")) if str(item).strip())
    if overlay:
        # An overlay is current market-hours review context only.  It must
        # remain visible even when the normal card/timing state carries the
        # very repair debt this queue is meant to escalate.
        blockers.update(str(item) for item in as_list(attention.get("blockers")) if str(item).strip())
        if card.get("decision_state"):
            blockers.add(f"trade_grade_card_state={card.get('decision_state')}")
        if timing.get("final_timing_state"):
            blockers.add(f"wf85_timing_state={timing.get('final_timing_state')}")
        if market.get("fresh_price_allowed") is not True:
            blockers.add("market_refresh_pending")
        return "intraday_review_required", sorted(blockers)
    if attention:
        # Never silently drop a fresh attention row just because its derived
        # intraday overlay failed.  This is a repair signal, not a fallback
        # recommendation.
        blockers.update(str(item) for item in as_list(attention.get("blockers")) if str(item).strip())
        blockers.add("intraday_review_overlay_missing_or_rejected")
        return "intraday_review_sync_degraded", sorted(blockers)
    if card.get("decision_state") == "blocked_missing_freshness":
        blockers.add("trade_grade_card_blocked_missing_freshness")
    timing_state = timing.get("final_timing_state")
    if timing_state and timing_state != "review_ready_wait_approval":
        blockers.add(f"wf85_timing_state={timing_state}")
    if market.get("fresh_price_allowed") is not True:
        blockers.add("market_refresh_pending")
    if row.get("visibility_state") == "owner_review_ready" and not blockers:
        return "owner_review_ready", []
    if "market_refresh_pending" in blockers:
        return "market_refresh_pending", sorted(blockers)
    if row.get("visibility_state") == "gate_deferred":
        return "gate_deferred", sorted(blockers)
    if blockers:
        return "repair_or_wait", sorted(blockers)
    return "monitor_only", []


def build_payload(paths: dict[str, Path], now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payloads = {name: load(path) for name, path in paths.items()}
    wf78_rows = by_ticker(as_list(payloads["wf78_visibility_queue"].get("rows")))
    cards = by_ticker(as_list(payloads["trade_grade_cards"].get("cards")))
    timing_rows = by_ticker(as_list(payloads["wf85_timing_gate"].get("rows")))
    factory_rows = by_ticker(as_list(payloads["finance_decision_factory"].get("decision_ledger")))
    attention_rows = attention_by_ticker(payloads["in_band_review_attention"])
    overlay_rows = active_overlay_by_ticker(payloads["intraday_review_overlay"], now)
    market = market_state(payloads["market_loop"])

    rows: list[dict[str, Any]] = []
    all_tickers = sorted(set(wf78_rows) | set(attention_rows) | set(overlay_rows))
    for ticker in all_tickers:
        wf78_row = wf78_rows.get(ticker, {"ticker": ticker})
        card = cards.get(ticker, {})
        timing = timing_rows.get(ticker, {})
        factory = factory_rows.get(ticker, {})
        attention = attention_rows.get(ticker, {})
        overlay = overlay_rows.get(ticker, {})
        state, blockers = classify(wf78_row, card, timing, market, overlay, attention)
        overlay_price = as_dict(overlay.get("current_price"))
        rows.append({
            "ticker": ticker,
            "name": wf78_row.get("name") or card.get("name") or timing.get("name") or overlay.get("name"),
            "wf85_visibility_state": state,
            "blockers": blockers,
            "wf78_visibility_state": wf78_row.get("visibility_state"),
            "market_state": market,
            "auto_tier": overlay.get("auto_tier") or attention.get("auto_tier") or wf78_row.get("auto_tier") or card.get("auto_tier") or timing.get("auto_tier"),
            "auto_state": attention.get("route_state") or wf78_row.get("auto_state") or card.get("auto_state") or timing.get("auto_state"),
            "decision_state": attention.get("decision_state") or card.get("decision_state"),
            "decision_state_reason": card.get("decision_state_reason"),
            "final_timing_state": timing.get("final_timing_state"),
            "review_state": overlay.get("review_state") or attention.get("review_state"),
            "gate_verdict": factory.get("gate_verdict") or wf78_row.get("gate_verdict"),
            "current_price": overlay_price.get("latest_known_price") if overlay else (wf78_row.get("current_price") or timing.get("current_price")),
            "intraday_review_quote": overlay_price if overlay else None,
            "intraday_review_source_freshness": overlay.get("source_freshness") if overlay else None,
            "entry_band": overlay.get("entry_band") or wf78_row.get("entry_band") or timing.get("entry_band"),
            "stop_or_invalidation": overlay.get("stop_or_invalidation") or wf78_row.get("stop_or_invalidation") or timing.get("stop_or_invalidation"),
            "attention_type": attention.get("attention_type"),
            "recommended_review_action": overlay.get("recommended_action") or attention.get("recommended_action"),
            "intraday_overlay_applied": bool(overlay),
            "review_priority": intraday_priority(overlay, attention),
            "owner_card_path": wf78_row.get("owner_card_path") or factory.get("owner_card_path"),
            "wf67_request_path": wf78_row.get("wf67_request_path") or factory.get("wf67_request_path"),
            "owner_action_required": state == "owner_review_ready",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })

    rows.sort(key=lambda row: (int(row.get("review_priority") or 100), str(row.get("ticker") or "")))
    counts = Counter(row["wf85_visibility_state"] for row in rows)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF85",
        "status": "draft",
        "purpose": "WF85 review-ready visibility queue, consuming WF78 candidate visibility and trade-grade timing/card gates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(rows),
            "visibility_state_counts": dict(counts),
            "owner_review_ready_count": counts.get("owner_review_ready", 0),
            "market_refresh_pending_count": counts.get("market_refresh_pending", 0),
            "gate_deferred_count": counts.get("gate_deferred", 0),
            "repair_or_wait_count": counts.get("repair_or_wait", 0),
            "intraday_review_required_count": counts.get("intraday_review_required", 0),
            "intraday_review_sync_degraded_count": counts.get("intraday_review_sync_degraded", 0),
            "ranked_intraday_review_tickers": [
                row["ticker"] for row in rows if row["wf85_visibility_state"] == "intraday_review_required"
            ],
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "paper_or_live_execution_allowed_count": 0,
            "next_safe_action": (
                "Route intraday_review_required rows to main review/evidence repair; owner-review and capital gates remain separate."
                if counts.get("intraday_review_required", 0)
                else "Present owner-review visibility only if rows are owner_review_ready; otherwise refresh/repair the listed blockers."
            ),
        },
        "rows": rows,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "source_records": [source_record(name, path, payloads[name]) for name, path in paths.items()],
        "stop_lines": [
            "WF85 visibility is not capital approval.",
            "No paper/live/order/account/brokerage action is allowed from this queue.",
            "No canon/portfolio/cash/sizing mutation is allowed.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "ok" if payload["validation"]["status"] in {"ok", "warning"} else "blocked"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append(f"authority_drift:{','.join(drift[:5])}")
    for record in as_list(payload.get("source_records")):
        if record.get("required") is True and record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("authority_drift_paths"):
            errors.append(f"source_authority_drift:{record.get('name')}")
        if record.get("validation_status") == "error":
            warnings.append(f"source_validation_error:{record.get('name')}")
    summary = as_dict(payload.get("summary"))
    if summary.get("capital_deployment_approved_count") or summary.get("trade_or_execution_approved_count"):
        errors.append("authority_approval_count_nonzero")
    for row in as_list(payload.get("rows")):
        row = as_dict(row)
        if row.get("wf85_visibility_state") == "intraday_review_required":
            quote = as_dict(row.get("intraday_review_quote"))
            if quote.get("quote_freshness_status") != "intraday_review_only_fresh":
                errors.append(f"intraday_row_quote_not_review_only:{row.get('ticker')}")
            if quote.get("approval_draft_eligible") is not False:
                errors.append(f"intraday_row_approval_eligible:{row.get('ticker')}")
            if row.get("owner_action_required") is not False:
                errors.append(f"intraday_row_owner_action_inferred:{row.get('ticker')}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, path in SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in SOURCES}
    payload = build_payload(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "validation": payload.get("validation"),
            "summary": payload.get("summary"),
            "out": rel(out) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
