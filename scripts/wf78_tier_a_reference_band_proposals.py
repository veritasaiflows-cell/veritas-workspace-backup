#!/usr/bin/env python3
"""Build a review-only Tier A reference-band proposal surface.

Tier A names whose canonical reference band is stale or low-confidence surface
as ``STALE_REFERENCE_BAND`` in their ticker card: the card refuses to make a
hard-stop claim off a stale legacy band even when technical freshness exists.
Nothing today presents an explicit *proposed refreshed reference band* for those
names, so the stale band stays unresolved.

This surface reuses the fresh Keltner/MA technical band already computed by
``wf78_missing_band_context_repair.py`` (its ``technical_band_context.band``
block) and the ticker card's ``price_band_stop`` to emit, per Tier A name, a
review-only comparison of the current stale reference band vs. a proposed fresh
one. It does not recompute market data, add anything to ``portfolio-config.json``,
mutate cards/canon/SQL, or apply any band. Owner review and the bounded
``entry_band`` gate remain the only paths to change a canonical reference band.

Reads:
  tmp/wf78-clean-tier-roster.json            -- current Tier A membership (true_tier_a)
  tmp/wf78-missing-band-context-repair.json  -- fresh technical band per ticker (reused)
  tmp/ticker-intelligence-cards/*.current.json -- current reference band / staleness

Writes:
  tmp/wf78-tier-a-reference-band-proposals.json

Usage:
  python scripts/wf78_tier_a_reference_band_proposals.py --write --validate
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ROSTER = TMP / "wf78-clean-tier-roster.json"
REPAIR = TMP / "wf78-missing-band-context-repair.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT = TMP / "wf78-tier-a-reference-band-proposals.json"
SCHEMA = "veritas.wf78_tier_a_reference_band_proposals.v1"

LOW_CONFIDENCE_REFERENCE_MAX = 2

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "tier_a_reference_band_proposal_only": True,
    "automated_non_capital_routing_allowed": True,
    "proposal_applied": False,
    "auto_added_to_config": False,
    "config_auth_runtime_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "owner_note_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
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
TRUE_AUTHORITY_KEYS = {
    "review_only",
    "tier_a_reference_band_proposal_only",
    "automated_non_capital_routing_allowed",
}
FALSE_AUTHORITY_KEYS = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY_KEYS}

ROW_FALSE_KEYS = (
    "proposal_applied",
    "auto_added_to_config",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "owner_approval_inferred",
)

ALLOWED_PROPOSAL_STATUS = {
    "proposal_ready",
    "proposal_pending_fresh_band",
    "no_proposal_needed",
    "card_missing",
}

STOP_LINES = [
    "Review-only reference-band proposal surface; no config add, no card/canon/SQL/portfolio mutation, no band apply.",
    "Proposed bands reuse already-computed review-only technical context; a refreshed reference band still requires owner review and the bounded entry_band gate.",
    "No capital deployment, trade/order execution, paper/live brokerage action, account action, money movement, or inferred owner approval.",
]


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


def norm_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def tier_a_members(roster: dict[str, Any]) -> list[str]:
    members = [norm_ticker(t) for t in as_list(roster.get("true_tier_a")) if norm_ticker(t)]
    return sorted(dict.fromkeys(members))


def fresh_bands_by_ticker(repair: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(repair.get("rows")):
        row = as_dict(row)
        ticker = norm_ticker(row.get("ticker"))
        if not ticker:
            continue
        context = as_dict(row.get("technical_band_context"))
        out[ticker] = {
            "context_status": context.get("status"),
            "engine_version": context.get("engine_version"),
            "band": as_dict(context.get("band")),
        }
    return out


def current_reference_band(card: dict[str, Any]) -> dict[str, Any]:
    band = as_dict(card.get("price_band_stop"))
    sql_ref = as_dict(band.get("sql_canon_reference"))
    return {
        "entry_band_low": as_float(band.get("entry_band_low")),
        "entry_band_high": as_float(band.get("entry_band_high")),
        "stop_or_invalidation": as_float(band.get("stop_or_invalidation")),
        "band_status": band.get("band_status"),
        "band_source": band.get("band_source"),
        "reference_confidence": sql_ref.get("reference_confidence"),
        "reference_band_status": sql_ref.get("reference_band_status"),
        "reference_band_refresh_required": bool(band.get("reference_band_refresh_required")),
        "latest_known_price": as_float(band.get("latest_known_price")),
        "present": bool(band),
    }


def proposal_needed(current: dict[str, Any]) -> bool:
    if not current.get("present"):
        return False
    if current.get("band_status") == "STALE_REFERENCE_BAND":
        return True
    if current.get("reference_band_refresh_required"):
        return True
    confidence = current.get("reference_confidence")
    if isinstance(confidence, (int, float)) and confidence <= LOW_CONFIDENCE_REFERENCE_MAX:
        return True
    if (
        current.get("entry_band_low") is None
        and current.get("entry_band_high") is None
        and current.get("stop_or_invalidation") is None
    ):
        return True
    return False


def proposed_band_from_context(fresh: dict[str, Any]) -> dict[str, Any] | None:
    band = as_dict(fresh.get("band"))
    low = as_float(band.get("entry_band_low"))
    high = as_float(band.get("entry_band_high"))
    stop = as_float(band.get("stop_or_invalidation"))
    if fresh.get("context_status") != "ok" or low is None or high is None or stop is None:
        return None
    return {
        "entry_band_low": low,
        "entry_band_high": high,
        "stop_or_invalidation": stop,
        "band_status": band.get("band_status"),
        "entry_band_method": band.get("entry_band_method"),
        "entry_band_type": band.get("entry_band_type"),
        "trend_stack": band.get("trend_stack"),
        "band_confidence": band.get("band_confidence"),
        "stop_basis": band.get("stop_basis"),
        "engine_version": fresh.get("engine_version"),
        "band_source": "review_only_technical_band_context",
    }


def interpretation(current: dict[str, Any], proposed: dict[str, Any] | None) -> str:
    cur = (
        f"Current reference band {current.get('entry_band_low')}-{current.get('entry_band_high')} "
        f"(stop {current.get('stop_or_invalidation')}, confidence {current.get('reference_confidence')}) "
        f"is {current.get('band_status')}"
    )
    if proposed is None:
        return (
            f"{cur}. No fresh technical band is available yet; keep review-only and do not treat the "
            f"stale band as a hard stop."
        )
    price = current.get("latest_known_price")
    price_note = f" Latest known price {price}." if price is not None else ""
    return (
        f"{cur}. Proposed fresh band {proposed['entry_band_low']}-{proposed['entry_band_high']} "
        f"(stop {proposed['stop_or_invalidation']}, {proposed.get('entry_band_method')}, "
        f"trend {proposed.get('trend_stack')}, confidence {proposed.get('band_confidence')}, "
        f"status {proposed.get('band_status')}).{price_note} Review-only comparison; the fresh band is "
        f"technical context, not a validated canonical reference band."
    )


def build_row(ticker: str, card: dict[str, Any], fresh: dict[str, Any] | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticker": ticker,
        "tier": "Tier A",
        "proposal_applied": False,
        "auto_added_to_config": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }
    if not card:
        row.update({
            "proposal_status": "card_missing",
            "proposal_needed": None,
            "current_reference_band": None,
            "proposed_reference_band": None,
            "interpretation": f"No ticker card found for {ticker}; cannot assess reference-band staleness.",
            "review_only_next_step": f"Regenerate the {ticker} ticker card, then re-run this surface. No apply.",
        })
        return row

    current = current_reference_band(card)
    needed = proposal_needed(current)
    proposed = proposed_band_from_context(fresh) if (needed and fresh) else None

    if not needed:
        status = "no_proposal_needed"
        next_step = f"{ticker} reference band is not stale/low-confidence; no reference-band proposal required."
    elif proposed is not None:
        status = "proposal_ready"
        next_step = (
            f"Owner review only: compare the proposed fresh band for {ticker} against the current stale band. "
            f"If the owner chooses to refresh the canonical reference band, that goes through the separate bounded "
            f"entry_band maintenance gate. This artifact does not add to config or change canon."
        )
    else:
        status = "proposal_pending_fresh_band"
        next_step = (
            f"{ticker} needs a refreshed reference band but no fresh technical band is available; run "
            f"wf78_missing_band_context_repair.py --target {ticker} first, then re-run this surface. No apply, no fabrication."
        )

    row.update({
        "proposal_status": status,
        "proposal_needed": needed,
        "current_reference_band": current,
        "proposed_reference_band": proposed,
        "proposed_source": rel(REPAIR) + ":technical_band_context.band",
        "interpretation": interpretation(current, proposed) if needed else (
            f"Current reference band status {current.get('band_status')}; no refresh proposal needed."
        ),
        "review_only_next_step": next_step,
    })
    return row


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if artifact.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    authority = as_dict(artifact.get("authority_boundary"))
    for key in sorted(TRUE_AUTHORITY_KEYS):
        if authority.get(key) is not True:
            errors.append(f"authority_not_true:{key}")
    for key in sorted(FALSE_AUTHORITY_KEYS):
        if authority.get(key) is not False:
            errors.append(f"authority_not_false:{key}")
    rows = [as_dict(r) for r in as_list(artifact.get("proposals"))]
    for row in rows:
        ticker = norm_ticker(row.get("ticker"))
        label = ticker or "unknown"
        if not ticker:
            errors.append("row_missing_ticker")
        for key in ROW_FALSE_KEYS:
            if row.get(key) is not False:
                errors.append(f"row_authority_not_false:{label}:{key}")
        status = row.get("proposal_status")
        if status not in ALLOWED_PROPOSAL_STATUS:
            errors.append(f"row_bad_status:{label}:{status}")
        if status == "proposal_ready":
            proposed = as_dict(row.get("proposed_reference_band"))
            if any(proposed.get(k) is None for k in ("entry_band_low", "entry_band_high", "stop_or_invalidation")):
                errors.append(f"row_proposal_ready_incomplete_band:{label}")
        if status == "proposal_pending_fresh_band" and row.get("proposed_reference_band") is not None:
            errors.append(f"row_pending_has_band:{label}")
    if not rows:
        warnings.append("no_tier_a_rows")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build() -> dict[str, Any]:
    roster = load_dict(ROSTER)
    repair = load_dict(REPAIR)
    fresh_map = fresh_bands_by_ticker(repair)
    members = tier_a_members(roster)

    rows: list[dict[str, Any]] = []
    for ticker in members:
        card = load_dict(CARD_DIR / f"{ticker}.current.json")
        rows.append(build_row(ticker, card, fresh_map.get(ticker)))

    status_counts = Counter(str(r.get("proposal_status")) for r in rows)
    ready = sorted(r["ticker"] for r in rows if r.get("proposal_status") == "proposal_ready")
    pending = sorted(r["ticker"] for r in rows if r.get("proposal_status") == "proposal_pending_fresh_band")

    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Review-only Tier A reference-band proposal surface reusing computed technical band context.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "tier_a_roster_path": rel(ROSTER),
            "fresh_band_source_path": rel(REPAIR),
            "ticker_card_glob": rel(CARD_DIR / "*.current.json"),
            "tier_a_roster_loaded": bool(roster),
            "fresh_band_source_loaded": bool(repair),
        },
        "summary": {
            "tier_a_count": len(members),
            "proposal_status_counts": dict(status_counts),
            "proposal_ready_count": len(ready),
            "proposal_ready_tickers": ready,
            "proposal_pending_fresh_band_count": len(pending),
            "proposal_pending_fresh_band_tickers": pending,
            "no_proposal_needed_count": status_counts.get("no_proposal_needed", 0),
            "card_missing_count": status_counts.get("card_missing", 0),
            "next_safe_action": (
                "Owner reviews proposal_ready rows; route any accepted refresh through the bounded entry_band gate. "
                "This surface never adds to config or applies a band."
            ),
        },
        "proposals": rows,
        "stop_lines": STOP_LINES,
    }
    artifact["validation"] = validate_artifact(artifact)
    artifact["status"] = artifact["validation"]["status"]
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the proposal artifact to disk.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if the artifact does not validate.")
    parser.add_argument("--out", default=str(OUT), help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = build()
    out_path = Path(args.out)
    if args.write:
        atomic_write_json(out_path, artifact)
    validation = artifact["validation"]
    summary = artifact["summary"]
    print(
        f"{validation['status']}: tier_a={summary['tier_a_count']} "
        f"ready={summary['proposal_ready_count']} "
        f"pending={summary['proposal_pending_fresh_band_count']} "
        f"no_proposal={summary['no_proposal_needed_count']} "
        f"card_missing={summary['card_missing_count']} "
        f"out={rel(out_path) if args.write else '<not-written>'}"
    )
    if args.validate and validation["status"] != "ok":
        for error in validation["errors"]:
            print(f"  error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
