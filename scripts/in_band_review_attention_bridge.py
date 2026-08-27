#!/usr/bin/env python3
"""Publish a fresh, review-only attention queue for Tier A/B in-band setups.

This bridge consumes existing WF78 routing, band-hygiene, decision-sync, and
intraday quote artifacts.  It deliberately does not calculate a competing
technical signal, create a capital recommendation, or widen execution
authority.  Its purpose is visibility: a fresh in-band Tier A/B setup with
policy or evidence debt must reach a main-session review queue instead of
silently disappearing behind a watch lane.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "in-band-review-attention-bridge.json"
SYNC = TMP / "finance-decision-sync-spine.json"
HYGIENE = TMP / "band-hygiene-freshness-controller.json"
ROUTER = TMP / "wf78-auto-tier-routing.json"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"

SCHEMA = "veritas.in_band_review_attention_bridge.v1"
FRESH_QUOTE_AGE_SECONDS = 15 * 60
MAX_TIER_ROUTER_AGE_SECONDS = 24 * 60 * 60
REVIEW_TIERS = {"Tier A", "Tier B"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "operator_attention_artifact_only": True,
    "external_delivery_allowed": False,
    "capital_recommendation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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


def rows_for(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "snapshots", "proposals"):
        rows = as_list(payload.get(key))
        if rows:
            return [as_dict(row) for row in rows]
    return []


def index_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows_for(payload):
        symbol = ticker(row.get("ticker") or row.get("symbol"))
        if symbol:
            result[symbol] = row
    return result


def fresh_quote(snapshot: dict[str, Any]) -> bool:
    try:
        age = int(snapshot.get("age_seconds"))
    except (TypeError, ValueError):
        return False
    return (
        snapshot.get("freshness_status") == "fresh"
        and snapshot.get("calendar_freshness_status") == "fresh_intraday"
        and fnum(snapshot.get("price")) is not None
        and age <= FRESH_QUOTE_AGE_SECONDS
    )


def band_fields(sync_row: dict[str, Any], hygiene_row: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    hygiene_band = as_dict(hygiene_row.get("band"))
    low = fnum(sync_row.get("entry_band_low"))
    high = fnum(sync_row.get("entry_band_high"))
    stop = fnum(sync_row.get("stop_or_invalidation"))
    if low is None:
        low = fnum(hygiene_band.get("current_band_low"))
    if high is None:
        high = fnum(hygiene_band.get("current_band_high"))
    if stop is None:
        stop = fnum(hygiene_band.get("current_stop"))
    return low, high, stop


def price_is_in_band(price: float | None, low: float | None, high: float | None, stop: float | None) -> bool:
    if price is None or low is None or high is None:
        return False
    if stop is not None and price < stop:
        return False
    return low <= price <= high


def source_errors(
    quote_proof: dict[str, Any],
    hygiene: dict[str, Any],
    sync: dict[str, Any],
    router: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for name, payload in (
        ("quote_proof", quote_proof),
        ("band_hygiene", hygiene),
        ("decision_sync", sync),
        ("tier_router", router),
    ):
        if payload.get("status") != "ok":
            errors.append(f"{name}_status_not_ok:{payload.get('status')}")
    quote_time = parse_utc(quote_proof.get("generated_at_utc"))
    if quote_time is None:
        errors.append("quote_proof_generated_at_missing")
        return errors
    for name, payload in (("band_hygiene", hygiene), ("decision_sync", sync)):
        generated = parse_utc(payload.get("generated_at_utc"))
        if generated is None:
            errors.append(f"{name}_generated_at_missing")
        elif generated < quote_time:
            errors.append(f"{name}_older_than_quote_proof")
    router_time = parse_utc(router.get("generated_at_utc"))
    if router_time is None:
        errors.append("tier_router_generated_at_missing")
    elif (quote_time - router_time).total_seconds() > MAX_TIER_ROUTER_AGE_SECONDS:
        errors.append("tier_router_not_current_for_quote_proof")
    return sorted(set(errors))


def attention_rows(
    quote_proof: dict[str, Any],
    hygiene: dict[str, Any],
    sync: dict[str, Any],
    router: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    quotes = index_rows(quote_proof)
    hygiene_rows = index_rows(hygiene)
    sync_rows = index_rows(sync)
    router_rows = index_rows(router)
    review: list[dict[str, Any]] = []
    repair: list[dict[str, Any]] = []

    for symbol in sorted(set(sync_rows) | set(hygiene_rows)):
        route = router_rows.get(symbol, {})
        tier = str(route.get("auto_tier") or "")
        if tier not in REVIEW_TIERS:
            continue
        quote = quotes.get(symbol, {})
        if not fresh_quote(quote):
            continue
        sync_row = sync_rows.get(symbol, {})
        hygiene_row = hygiene_rows.get(symbol, {})
        price = fnum(quote.get("price"))
        low, high, stop = band_fields(sync_row, hygiene_row)
        if not price_is_in_band(price, low, high, stop):
            continue
        entry_policy = as_dict(sync_row.get("entry_policy_review")) or as_dict(hygiene_row.get("entry_policy_review"))
        conflicts = [str(item) for item in as_list(entry_policy.get("surface_conflicts"))]
        blockers = [str(item) for item in as_list(sync_row.get("blockers"))]
        warnings = [str(item) for item in as_list(sync_row.get("warnings"))]
        base = {
            "ticker": symbol,
            "auto_tier": tier,
            "route_state": route.get("auto_state"),
            "current_price": price,
            "quote_source_timestamp_utc": quote.get("source_timestamp_utc"),
            "quote_age_seconds": quote.get("age_seconds"),
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "derived_band_status": "IN_BAND",
            "decision_state": sync_row.get("primary_state"),
            "promotion_gate_verdict": sync_row.get("promotion_gate_verdict"),
            "blockers": blockers,
            "warnings": warnings,
            "entry_policy_review": entry_policy,
            "source_artifacts": [rel(QUOTE_PROOF), rel(HYGIENE), rel(SYNC), rel(ROUTER)],
            "capital_recommendation": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }
        if entry_policy.get("candidate") is True:
            review.append({
                **base,
                "attention_type": "entry_policy_review",
                "recommended_action": "main_review_required",
                "reason": "fresh_in_band_setup_with_policy_or_evidence_debt",
            })
        elif conflicts:
            repair.append({
                **base,
                "attention_type": "technical_surface_conflict",
                "recommended_action": "technical_surface_reconciliation_required",
                "reason": "fresh_in_band_quote_conflicts_with_existing_technical_surface",
                "surface_conflicts": conflicts,
            })
        elif str(sync_row.get("primary_state") or "") in {
            "evidence_repair",
            "monitor_only",
            "in_band_not_clean",
            "promotion_vetoed",
            "blocked_missing_freshness",
        }:
            repair.append({
                **base,
                "attention_type": "in_band_evidence_repair",
                "recommended_action": "evidence_repair_required",
                "reason": "fresh_in_band_setup_remains_non_decision_grade",
            })

    tier_rank = {"Tier A": 0, "Tier B": 1}
    sorter = lambda row: (tier_rank.get(str(row.get("auto_tier")), 9), str(row.get("ticker")))
    return sorted(review, key=sorter), sorted(repair, key=sorter)


def fingerprint(rows: list[dict[str, Any]]) -> str:
    stable = [
        {
            "ticker": row.get("ticker"),
            "attention_type": row.get("attention_type"),
            "recommended_action": row.get("recommended_action"),
            "blockers": sorted(str(item) for item in as_list(row.get("blockers"))),
            "surface_conflicts": sorted(str(item) for item in as_list(row.get("surface_conflicts"))),
        }
        for row in rows
    ]
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors = [str(item) for item in as_list(payload.get("errors"))]
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    for section in ("review_attention", "repair_attention"):
        for row in as_list(payload.get(section)):
            item = as_dict(row)
            if str(item.get("auto_tier")) not in REVIEW_TIERS:
                errors.append(f"{item.get('ticker')}:non_review_tier_visible")
            if item.get("derived_band_status") != "IN_BAND":
                errors.append(f"{item.get('ticker')}:non_in_band_row_visible")
            for key in (
                "capital_deployment_approved",
                "trade_or_execution_approved",
                "paper_or_live_execution_allowed",
                "owner_approval_inferred",
            ):
                if item.get(key) is not False:
                    errors.append(f"{item.get('ticker')}:{key}_not_false")
    for row in as_list(payload.get("review_attention")):
        if as_dict(as_dict(row).get("entry_policy_review")).get("candidate") is not True:
            errors.append(f"{as_dict(row).get('ticker')}:review_attention_without_entry_policy_candidate")
    for row in as_list(payload.get("repair_attention")):
        item = as_dict(row)
        if item.get("attention_type") == "technical_surface_conflict" and not as_list(item.get("surface_conflicts")):
            errors.append(f"{item.get('ticker')}:technical_conflict_without_source_conflict")
    return {"status": "blocked" if errors else "ok", "errors": sorted(set(errors)), "warnings": []}


def build_payload(
    *,
    quote_proof: dict[str, Any],
    hygiene: dict[str, Any],
    sync: dict[str, Any],
    router: dict[str, Any],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    errors = source_errors(quote_proof, hygiene, sync, router)
    review, repair = ([], []) if errors else attention_rows(quote_proof, hygiene, sync, router)
    all_rows = review + repair
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or utc_now(),
        "status": "draft",
        "purpose": "Expose fresh Tier A/B in-band attention for review without creating capital or execution authority.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "quote_snapshot_proof": rel(QUOTE_PROOF),
            "band_hygiene": rel(HYGIENE),
            "finance_decision_sync": rel(SYNC),
            "wf78_auto_tier_router": rel(ROUTER),
        },
        "source_generated_at_utc": {
            "quote_snapshot_proof": quote_proof.get("generated_at_utc"),
            "band_hygiene": hygiene.get("generated_at_utc"),
            "finance_decision_sync": sync.get("generated_at_utc"),
            "wf78_auto_tier_router": router.get("generated_at_utc"),
        },
        "operator_alert": {
            "action": "REVIEW_ATTENTION" if all_rows else "NO_REPLY",
            "delivery": "operator_artifact_only",
            "external_delivery_allowed": False,
            "capital_recommendation_allowed": False,
        },
        "summary": {
            "review_attention_count": len(review),
            "review_attention_tickers": [row["ticker"] for row in review],
            "repair_attention_count": len(repair),
            "repair_attention_tickers": [row["ticker"] for row in repair],
            "attention_fingerprint": fingerprint(all_rows),
            "next_safe_action": (
                "Main-session review of fresh in-band attention rows; resolve evidence or technical conflicts before capital-review language."
                if all_rows else "No fresh Tier A/B in-band review attention is currently present."
            ),
        },
        "review_attention": review,
        "repair_attention": repair,
        "errors": errors,
        "stop_lines": [
            "This artifact is review-only and cannot create a capital recommendation, approval card, order, or execution authority.",
            "Technical conflicts remain repair work; a fresh in-band quote does not override an existing technical or evidence gate.",
            "External notification delivery is not authorized by this bridge.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quote-proof", type=Path, default=QUOTE_PROOF)
    parser.add_argument("--band-hygiene", type=Path, default=HYGIENE)
    parser.add_argument("--decision-sync", type=Path, default=SYNC)
    parser.add_argument("--tier-router", type=Path, default=ROUTER)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        quote_proof=load(args.quote_proof),
        hygiene=load(args.band_hygiene),
        sync=load(args.decision_sync),
        router=load(args.tier_router),
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "in_band_review_attention_bridge: "
        f"status={payload['status']} review={payload['summary']['review_attention_count']} "
        f"repair={payload['summary']['repair_attention_count']} action={payload['operator_alert']['action']}"
    )
    return 1 if args.validate and payload["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
