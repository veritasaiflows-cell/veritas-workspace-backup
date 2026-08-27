#!/usr/bin/env python3
"""Build a fail-closed, intraday **review-only** WF85 price overlay.

The normal WF85 cards deliberately consume a post-close quote ledger.  This
overlay lets the existing market-hours controller surface a fresh Tier A/B
in-band setup for review without changing card quote semantics, creating an
approval card, or granting execution authority.

``intraday_review_only_fresh`` is intentionally distinct from
``intraday_fresh``.  The latter can be execution-fresh in other WF85
consumers; this overlay is never eligible to clear an approval or order gate.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
QUOTE_VALIDATION = TMP / "intraday-alerts" / "quote-snapshot-proof-validation.json"
ATTENTION = TMP / "in-band-review-attention-bridge.json"
OUT = TMP / "wf85-intraday-review-overlay.json"

SCHEMA = "veritas.wf85_intraday_review_overlay.v1"
REVIEW_ONLY_QUOTE_STATUS = "intraday_review_only_fresh"
MAX_QUOTE_AGE_SECONDS = 15 * 60
REVIEW_TIERS = {"Tier A", "Tier B"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "fresh_price_review_context_only": True,
    "creates_owner_cards": False,
    "creates_approval_cards": False,
    "approval_card_generation_allowed": False,
    "capital_recommendation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}
FALSE_AUTHORITY_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def validation_status(payload: dict[str, Any]) -> str | None:
    validation = as_dict(payload.get("validation"))
    value = validation.get("status")
    return str(value).lower() if value is not None else None


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FALSE_AUTHORITY_KEYS and item is True:
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
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_drift_paths": authority_true_paths(payload),
    }


def quote_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for raw in as_list(payload.get("snapshots")):
        row = as_dict(raw)
        ticker = str(row.get("symbol") or row.get("ticker") or "").upper().strip()
        if ticker:
            rows[ticker] = row
    return rows


def attention_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    # A repair row carries more restrictive semantics than a plain review row,
    # so let it win when a ticker appears in both lists.
    for section in ("review_attention", "repair_attention"):
        for raw in as_list(payload.get(section)):
            row = as_dict(raw)
            ticker = str(row.get("ticker") or "").upper().strip()
            if ticker:
                rows[ticker] = row
    return rows


def quote_is_fresh_for_review(snapshot: dict[str, Any], now: datetime) -> tuple[bool, list[str], datetime | None]:
    reasons: list[str] = []
    source_time = parse_utc(snapshot.get("source_timestamp_utc"))
    if snapshot.get("freshness_status") != "fresh":
        reasons.append("quote_freshness_not_fresh")
    if snapshot.get("calendar_freshness_status") != "fresh_intraday":
        reasons.append("quote_not_market_hours_fresh")
    age = snapshot.get("age_seconds")
    try:
        age_value = int(age)
    except (TypeError, ValueError):
        age_value = None
    if age_value is None or age_value < 0 or age_value > MAX_QUOTE_AGE_SECONDS:
        reasons.append("quote_age_outside_review_window")
    if source_time is None:
        reasons.append("quote_source_timestamp_missing_or_invalid")
    elif source_time > now:
        reasons.append("quote_source_timestamp_in_future")
    elif (now - source_time).total_seconds() > MAX_QUOTE_AGE_SECONDS:
        reasons.append("quote_source_timestamp_stale")
    if fnum(snapshot.get("price")) is None:
        reasons.append("quote_price_missing_or_invalid")
    return not reasons, reasons, source_time


def build_row(ticker: str, attention: dict[str, Any], snapshot: dict[str, Any], now: datetime) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    tier = str(attention.get("auto_tier") or "")
    if tier not in REVIEW_TIERS:
        reasons.append("attention_row_not_tier_a_or_b")
    if attention.get("derived_band_status") != "IN_BAND":
        reasons.append("attention_row_not_in_band")
    for key in FALSE_AUTHORITY_KEYS:
        if attention.get(key) is True:
            reasons.append(f"attention_authority_drift:{key}")
    fresh, quote_reasons, source_time = quote_is_fresh_for_review(snapshot, now)
    reasons.extend(quote_reasons)
    quote_time = str(snapshot.get("source_timestamp_utc") or "")
    attention_quote_time = str(attention.get("quote_source_timestamp_utc") or "")
    if not attention_quote_time or attention_quote_time != quote_time:
        reasons.append("attention_quote_timestamp_mismatch")
    price = fnum(snapshot.get("price"))
    low = fnum(attention.get("entry_band_low"))
    high = fnum(attention.get("entry_band_high"))
    stop = fnum(attention.get("stop_or_invalidation"))
    if low is None or high is None or stop is None or price is None:
        reasons.append("numeric_band_stop_or_price_missing")
    elif price < stop:
        reasons.append("quote_below_stop")
    elif price < low or price > high:
        reasons.append("quote_outside_attention_band")
    if reasons or not fresh or source_time is None or price is None or low is None or high is None or stop is None:
        return None, sorted(set(reasons))

    attention_type = str(attention.get("attention_type") or "in_band_evidence_repair")
    recommended_action = str(attention.get("recommended_action") or "main_review_required")
    review_state = (
        "technical_reconciliation_required"
        if attention_type == "technical_surface_conflict"
        else "main_review_required"
    )
    return {
        "ticker": ticker,
        "auto_tier": tier,
        "route_state": attention.get("route_state"),
        "attention_type": attention_type,
        "review_state": review_state,
        "recommended_action": recommended_action,
        "reason": attention.get("reason"),
        "blockers": list(attention.get("blockers") or []),
        "warnings": list(attention.get("warnings") or []),
        "current_price": {
            "latest_known_price": price,
            "market_date": snapshot.get("source_market_date") or source_time.date().isoformat(),
            "quote_time_utc": quote_time,
            "quote_age_seconds": snapshot.get("age_seconds"),
            "source": rel(QUOTE_PROOF),
            "quote_freshness_status": REVIEW_ONLY_QUOTE_STATUS,
            "display_status": "intraday_review_only",
            "review_only_quote": True,
            "approval_draft_eligible": False,
        },
        "entry_band": {
            "low": low,
            "high": high,
            "band_status": "IN_BAND",
            "source": rel(ATTENTION),
        },
        "stop_or_invalidation": {"level": stop, "source": rel(ATTENTION)},
        "source_freshness": {
            "quote_freshness_status": REVIEW_ONLY_QUOTE_STATUS,
            "fresh_for_review": True,
            "fresh_for_approval": False,
            "expires_at_utc": utc_text(source_time + timedelta(seconds=MAX_QUOTE_AGE_SECONDS)),
        },
        "source_lineage": {
            "quote_snapshot_proof": rel(QUOTE_PROOF),
            "quote_snapshot_validation": rel(QUOTE_VALIDATION),
            "in_band_review_attention": rel(ATTENTION),
            "attention_quote_timestamp_utc": attention_quote_time,
        },
        "creates_approval_card": False,
        "capital_recommendation_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }, []


def build_payload(paths: dict[str, Path], now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    payloads = {name: load(path) for name, path in paths.items()}
    records = [source_record(name, path, payloads[name]) for name, path in paths.items()]
    errors: list[str] = []
    for record in records:
        if not record["exists"]:
            errors.append(f"missing_source:{record['name']}")
        if record["status"] != "ok":
            errors.append(f"source_status_not_ok:{record['name']}:{record['status']}")
        if record["validation_status"] not in {None, "ok"}:
            errors.append(f"source_validation_not_ok:{record['name']}:{record['validation_status']}")
        if record["authority_drift_paths"]:
            errors.append(f"source_authority_drift:{record['name']}")

    attention_rows = attention_index(payloads["in_band_review_attention"])
    quotes = quote_index(payloads["quote_snapshot_proof"])
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if not errors:
        for ticker, attention in sorted(attention_rows.items()):
            row, reasons = build_row(ticker, attention, quotes.get(ticker, {}), now)
            if row is None:
                rejected.append({"ticker": ticker, "reasons": reasons})
            else:
                rows.append(row)

    rows.sort(key=lambda row: (0 if row.get("auto_tier") == "Tier A" else 1, str(row.get("ticker"))))
    summary = {
        "attention_row_count": len(attention_rows),
        "overlay_row_count": len(rows),
        "overlay_tickers": [row["ticker"] for row in rows],
        "rejected_attention_count": len(rejected),
        "rejected_attention_tickers": [row["ticker"] for row in rejected],
        "review_only_quote_status": REVIEW_ONLY_QUOTE_STATUS,
        "approval_card_draft_eligible_count": 0,
        "capital_deployment_approved_count": 0,
        "trade_or_execution_approved_count": 0,
        "paper_or_live_execution_allowed_count": 0,
        "attention_fingerprint": as_dict(payloads["in_band_review_attention"].get("summary")).get("attention_fingerprint"),
        "next_safe_action": (
            "Route listed rows to review/evidence repair; do not create approval cards or submit orders."
            if rows else
            "No fresh Tier A/B in-band review-only overlay rows are available; inspect rejected rows or source blockers."
        ),
    }
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_text(now),
        "status": "blocked" if errors else "warning" if rejected else "ok",
        "purpose": "Fresh intraday Tier A/B in-band review context for WF85; never an approval or execution price surface.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "source_records": records,
        "summary": summary,
        "rows": rows,
        "rejected_attention": rejected,
        "errors": sorted(set(errors)),
        "stop_lines": [
            "intraday_review_only_fresh is not execution-fresh and cannot clear an approval-card, paper, or order gate.",
            "This overlay never mutates WF84/SQL canon, portfolio/cash/sizing/risk state, or existing WF85 card quote fields.",
            "Existing technical, source-open, earnings, promotion, concentration, and WF67 blockers remain authoritative.",
        ],
    }
    output["validation"] = validate_payload(output)
    if output["validation"]["status"] == "error":
        output["status"] = "blocked"
    return output


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    # Source failures are not merely display metadata.  A blocked overlay must
    # fail --validate so the controller cannot continue as if its derived rows
    # were safe to consume.
    errors.extend(f"payload_error:{item}" for item in as_list(payload.get("errors")) if str(item).strip())
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_invalid:{key}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append(f"authority_drift:{','.join(drift[:8])}")
    rows = as_list(payload.get("rows"))
    tickers = [str(as_dict(row).get("ticker") or "") for row in rows]
    if len(tickers) != len(set(tickers)):
        errors.append("duplicate_overlay_ticker")
    for row in rows:
        row = as_dict(row)
        quote = as_dict(row.get("current_price"))
        source_freshness = as_dict(row.get("source_freshness"))
        if quote.get("quote_freshness_status") != REVIEW_ONLY_QUOTE_STATUS:
            errors.append(f"row_quote_status_not_review_only:{row.get('ticker')}")
        if quote.get("approval_draft_eligible") is not False or quote.get("review_only_quote") is not True:
            errors.append(f"row_quote_authority_invalid:{row.get('ticker')}")
        if source_freshness.get("fresh_for_approval") is not False:
            errors.append(f"row_fresh_for_approval:{row.get('ticker')}")
        if row.get("entry_band", {}).get("band_status") != "IN_BAND":
            errors.append(f"row_not_in_band:{row.get('ticker')}")
        for key in (
            "creates_approval_card",
            "capital_recommendation_allowed",
            "capital_deployment_approved",
            "trade_or_execution_approved",
            "paper_or_live_execution_allowed",
            "owner_approval_inferred",
        ):
            if row.get(key) is not False:
                errors.append(f"row_authority_invalid:{row.get('ticker')}:{key}")
    if as_list(payload.get("rejected_attention")):
        warnings.append("some_attention_rows_rejected_fail_closed")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = parse_utc(value)
    if parsed is None:
        raise ValueError("invalid --now-utc")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quote-proof", type=Path, default=QUOTE_PROOF)
    parser.add_argument("--quote-validation", type=Path, default=QUOTE_VALIDATION)
    parser.add_argument("--attention", type=Path, default=ATTENTION)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--now-utc")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        now = parse_now(args.now_utc)
    except ValueError as exc:
        print(str(exc))
        return 2
    paths = {
        "quote_snapshot_proof": args.quote_proof if args.quote_proof.is_absolute() else ROOT / args.quote_proof,
        "quote_snapshot_validation": args.quote_validation if args.quote_validation.is_absolute() else ROOT / args.quote_validation,
        "in_band_review_attention": args.attention if args.attention.is_absolute() else ROOT / args.attention,
    }
    payload = build_payload(paths, now)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "wf85_intraday_review_overlay: "
            f"status={payload['status']} rows={payload['summary']['overlay_row_count']} "
            f"rejected={payload['summary']['rejected_attention_count']}"
        )
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
