#!/usr/bin/env python3
"""Resolve WF78 freshness debt according to tier-specific evidence depth.

This runner answers a different question than the raw stale-card detector. The
raw detector reports decision-grade gaps. This resolver classifies those gaps
by the amount of evidence each tier actually requires:

* Tier A/B: decision or promotion repair remains strict.
* Tier C monitor: thin-monitor freshness can be resolved without creating
  owner entry/stop lineage or deployment-readiness rows.
* Structural holds remain blocked until promotion, better evidence, or owner
  decision changes the required depth.

It is review-only and does not mutate cards, registry, owner notes, canon,
portfolio, deployment surfaces, SQL canon/cache, imports, promotions, or any
execution/account surface.
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
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT = TMP / "wf78-tier-weighted-freshness-resolution.json"
SCHEMA = "veritas.wf78_tier_weighted_freshness_resolution.v1"

LEDGER = TMP / "wf78-ticker-freshness-ledger.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
REPAIR_EXECUTION = TMP / "wf78-source-open-repair-execution.json"
POSITION_PROPOSAL = TMP / "wf78-position-sizing-integration-proposal.json"
DEPLOYMENT_REVIEW = TMP / "wf78-deployment-readiness-review.json"
OWNER_LINEAGE_DISCOVERY = TMP / "wf78-owner-lineage-discovery.json"
REGISTRY_PREVIEW = TMP / "wf78-official-registry-apply-preview.json"
OWNER_LINEAGE_PROPOSAL = TMP / "wf78-owner-lineage-proposal.json"
BAND_CONTEXT_REPAIR = TMP / "wf78-missing-band-context-repair.json"
REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"
POST_CLOSE_FINAL_QUOTES = TMP / "post-close-final-quote-ledger.json"
TIER_C_BAND_STATUS = TMP / "tier-c-band-status.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "tier_weighted_freshness_resolution_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
    "registry_mutation_allowed": False,
    "owner_note_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "ticker_import_allowed": False,
    "promotion_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_AUTHORITY = {"review_only", "tier_weighted_freshness_resolution_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


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


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def rows_by_ticker(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_dict(path)
    return {ticker(row.get("ticker")): as_dict(row) for row in as_list(payload.get("rows")) if ticker(as_dict(row).get("ticker"))}


def card(symbol: str) -> dict[str, Any]:
    return load_dict(CARD_DIR / f"{symbol}.current.json")


def card_summary_by_ticker() -> dict[str, dict[str, Any]]:
    payload = load_dict(TMP / "ticker-card-refresh-gate-card-build-summary.json")
    return {ticker(row.get("ticker")): as_dict(row) for row in as_list(payload.get("cards")) if ticker(as_dict(row).get("ticker"))}


def refresh_gate_summary() -> dict[str, Any]:
    return as_dict(load_dict(REFRESH_GATE).get("summary"))


def is_current_card(symbol: str, ledger_row: dict[str, Any]) -> bool:
    generated = ledger_row.get("card_generated_at_utc") or card(symbol).get("generated_at_utc")
    return bool(generated)


def position_status(symbol: str, position_rows: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    row = position_rows.get(symbol, {})
    return row.get("proposal_status"), row


def deployment_status(symbol: str, deployment_rows: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    row = deployment_rows.get(symbol, {})
    return row.get("review_status"), row


def lineage_status(symbol: str, lineage_rows: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    row = lineage_rows.get(symbol, {})
    return row.get("discovery_status"), row


def registry_preview_status(symbol: str, registry_rows: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    row = registry_rows.get(symbol, {})
    return row.get("preview_action"), row


def current_technical_review_available(symbol: str) -> bool:
    ticker_card = card(symbol)
    technical = as_dict(ticker_card.get("technical_posture"))
    price_band = as_dict(ticker_card.get("price_band_stop"))
    return bool(
        technical.get("data_date")
        and (technical.get("latest_close") is not None or price_band.get("latest_known_price") is not None)
    )


def classify_tier_c(
    row: dict[str, Any],
    route: dict[str, Any],
    monitor_band_row: dict[str, Any],
) -> tuple[str, str, list[str]]:
    state = route.get("auto_state") or row.get("route_state")
    if state == "C-MONITOR":
        band_status = monitor_band_row.get("band_status")
        confidence = monitor_band_row.get("confidence")
        if band_status and band_status not in {"UNKNOWN", "STALE"}:
            rationale = (
                "Thin-monitor freshness is sufficient for ordinary Tier C; monitor-grade "
                f"band status is {band_status} at confidence {confidence}. Decision-grade "
                "families remain deferred until promotion."
            )
        else:
            rationale = (
                "Thin-monitor freshness is sufficient for ordinary Tier C; monitor-grade "
                "band status is unavailable/stale and decision-grade families are deferred until promotion."
            )
        return (
            "resolved_thin_monitor_current",
            rationale,
            ["price_band_stop", "deployment_readiness", "portfolio_fit_concentration", "recommendation_support", "owner_entry_stop_lineage"],
        )
    return (
        "blocked_structural_or_candidate_hold",
        "Tier C candidate/hold is not decision-grade; keep blocked until promotion policy or owner review changes required depth.",
        row.get("stale_families") or [],
    )


def classify_tier_ab(
    symbol: str,
    tier: str,
    ledger_row: dict[str, Any],
    repair_row: dict[str, Any],
    position_rows: dict[str, dict[str, Any]],
    deployment_rows: dict[str, dict[str, Any]],
    lineage_rows: dict[str, dict[str, Any]],
    registry_rows: dict[str, dict[str, Any]],
    owner_proposal_rows: dict[str, dict[str, Any]],
    band_repair_rows: dict[str, dict[str, Any]],
    post_close_quote_rows: dict[str, dict[str, Any]],
) -> tuple[str, str, list[str]]:
    repair = repair_row.get("repair_disposition") or ledger_row.get("repair_disposition")
    pos_status, _ = position_status(symbol, position_rows)
    dep_status, _ = deployment_status(symbol, deployment_rows)
    lin_status, _ = lineage_status(symbol, lineage_rows)
    reg_status, _ = registry_preview_status(symbol, registry_rows)
    owner_proposal = owner_proposal_rows.get(symbol, {})
    band_repair = band_repair_rows.get(symbol, {})
    post_close_quote = post_close_quote_rows.get(symbol, {})
    stale_families = {str(item) for item in ledger_row.get("stale_families") or []}

    if stale_families == {"fresh_price_quote"}:
        if post_close_quote.get("status") == "ok" and post_close_quote.get("close") is not None:
            return (
                "resolved_to_post_close_final_quote_review",
                f"{symbol} has a post-close final quote overlay available for closed-market recommendation review; execution freshness still requires a fresh market-window check.",
                [],
            )
        if current_technical_review_available(symbol):
            return (
                "resolved_to_current_technical_review",
                f"{symbol} has current technical/price context available for non-executing review; execution freshness still requires a fresh market-window check.",
                [],
            )
        return (
            "blocked_fresh_quote_required_before_final_use",
            f"{symbol} only has a fresh-price quote gate remaining; rerun during market/provider freshness window before final use.",
            ["fresh_price_quote"],
        )

    if pos_status == "ready_for_review_integration_proposal":
        return (
            "resolved_to_position_sizing_review",
            f"{tier} row has source-backed position-sizing integration proposal ready for review.",
            [],
        )
    if dep_status == "ready_for_non_executing_deployment_readiness_row":
        return (
            "resolved_to_deployment_readiness_review",
            f"{tier} row has non-executing deployment-readiness review row ready.",
            [],
        )
    if pos_status == "blocked_missing_band_context":
        if band_repair.get("repair_status") == "ready_for_position_sizing_repair_recheck":
            return (
                "resolved_to_band_context_repair_recheck",
                f"{symbol} has review-only current price and band-status repair proof ready for position-sizing recheck.",
                [],
            )
        return (
            "blocked_missing_band_context",
            f"{symbol} lacks band/price context required for {tier} repair.",
            ["entry_band", "current_price", "stop_or_invalidation"],
        )
    if owner_proposal.get("proposal_status") == "ready_for_owner_review":
        return (
            "resolved_to_owner_lineage_proposal_review",
            f"{symbol} has a review-only proposed entry/stop lineage packet ready for owner review; not applied or owner-approved.",
            [],
        )
    if lin_status == "needs_owner_decision":
        return (
            "blocked_owner_lineage_decision_required",
            f"{symbol} has official registry preview support but owner entry/stop lineage still requires owner/source decision.",
            ["owner_entry_stop_lineage"],
        )
    if repair == "needs_source_artifact":
        if reg_status == "would_add_registry_row":
            return (
                "blocked_owner_lineage_decision_required",
                f"{symbol} has registry preview support but owner entry/stop lineage remains blocked.",
                ["owner_entry_stop_lineage"],
            )
        return (
            "blocked_source_artifact_required",
            f"{symbol} still needs official/source artifact capture before promotion repair.",
            ["official_source_artifact", "owner_entry_stop_lineage"],
        )
    if repair == "needs_deployment_readiness_surface":
        return (
            "blocked_deployment_readiness_surface_required",
            f"{symbol} still needs deployment-readiness review packaging.",
            ["deployment_readiness_surface"],
        )
    if repair == "needs_position_sizing_surface":
        return (
            "blocked_position_sizing_surface_required",
            f"{symbol} still needs source-backed position-sizing repair.",
            ["position_sizing_surface"],
        )
    if ledger_row.get("overall_freshness_state") == "fresh":
        return ("fresh", f"{symbol} has no stale families in the freshness ledger.", [])
    return (
        "blocked_unresolved_tier_ab_debt",
        f"{symbol} remains unresolved for {tier}; inspect freshness ledger and repair execution.",
        ledger_row.get("stale_families") or [],
    )


def build() -> dict[str, Any]:
    ledger = load_dict(LEDGER)
    ledger_rows = {ticker(row.get("ticker")): as_dict(row) for row in as_list(ledger.get("rows")) if ticker(as_dict(row).get("ticker"))}
    routes = rows_by_ticker(AUTO_ROUTER)
    repair_rows = rows_by_ticker(REPAIR_EXECUTION)
    position_rows = rows_by_ticker(POSITION_PROPOSAL)
    deployment_rows = rows_by_ticker(DEPLOYMENT_REVIEW)
    lineage_rows = rows_by_ticker(OWNER_LINEAGE_DISCOVERY)
    registry_rows = rows_by_ticker(REGISTRY_PREVIEW)
    owner_proposal_rows = rows_by_ticker(OWNER_LINEAGE_PROPOSAL)
    band_repair_rows = rows_by_ticker(BAND_CONTEXT_REPAIR)
    post_close_quote_rows = rows_by_ticker(POST_CLOSE_FINAL_QUOTES)
    tier_c_band_rows = rows_by_ticker(TIER_C_BAND_STATUS)
    tier_c_band_payload = load_dict(TIER_C_BAND_STATUS)
    card_summary = card_summary_by_ticker()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for symbol in sorted(set(ledger_rows) | set(routes)):
        ledger_row = ledger_rows.get(symbol, {})
        route = routes.get(symbol, {})
        tier = str(route.get("auto_tier") or ledger_row.get("auto_tier") or "unknown")
        if tier == "Tier C":
            resolution, rationale, deferred = classify_tier_c(ledger_row, route, tier_c_band_rows.get(symbol, {}))
            required_depth = "thin_monitor"
        elif tier in {"Tier A", "Tier B"}:
            resolution, rationale, deferred = classify_tier_ab(
                symbol,
                tier,
                ledger_row,
                repair_rows.get(symbol, {}),
                position_rows,
                deployment_rows,
                lineage_rows,
                registry_rows,
                owner_proposal_rows,
                band_repair_rows,
                post_close_quote_rows,
            )
            required_depth = "decision_repair" if tier == "Tier A" else "promotion_repair"
        else:
            resolution = "blocked_unknown_tier"
            rationale = "Ticker is missing WF78 tier classification."
            deferred = ledger_row.get("stale_families") or []
            required_depth = "unknown"

        current_card = is_current_card(symbol, ledger_row)
        if not current_card:
            resolution = "blocked_missing_current_card"
            rationale = "Ticker card is missing or has no generated timestamp."
            deferred = ["ticker_card"]

        summary_row = card_summary.get(symbol, {})
        rows.append({
            "ticker": symbol,
            "auto_tier": tier,
            "route_state": route.get("auto_state") or ledger_row.get("route_state"),
            "required_depth": required_depth,
            "raw_ledger_state": ledger_row.get("overall_freshness_state"),
            "resolution_state": resolution,
            "resolution_rationale": rationale,
            "card_generated_at_utc": ledger_row.get("card_generated_at_utc") or card(symbol).get("generated_at_utc"),
            "card_missing_or_stale_count": summary_row.get("missing_or_stale_count"),
            "stale_families": ledger_row.get("stale_families") or [],
            "deferred_until_promotion_or_owner_decision": sorted(set(str(item) for item in deferred)),
            "repair_disposition": repair_rows.get(symbol, {}).get("repair_disposition") or ledger_row.get("repair_disposition"),
            "position_proposal_status": position_rows.get(symbol, {}).get("proposal_status"),
            "deployment_review_status": deployment_rows.get(symbol, {}).get("review_status"),
            "owner_lineage_discovery_status": lineage_rows.get(symbol, {}).get("discovery_status"),
            "registry_preview_status": registry_rows.get(symbol, {}).get("preview_action"),
            "owner_lineage_proposal_status": owner_proposal_rows.get(symbol, {}).get("proposal_status"),
            "band_context_repair_status": band_repair_rows.get(symbol, {}).get("repair_status"),
            "post_close_final_quote_status": post_close_quote_rows.get(symbol, {}).get("status"),
            "post_close_final_quote_market_date": post_close_quote_rows.get(symbol, {}).get("market_date"),
            "post_close_final_quote_close": post_close_quote_rows.get(symbol, {}).get("close"),
            "tier_c_monitor_band_status": tier_c_band_rows.get(symbol, {}).get("band_status"),
            "tier_c_monitor_reference_band_low": tier_c_band_rows.get(symbol, {}).get("reference_band_low"),
            "tier_c_monitor_reference_band_high": tier_c_band_rows.get(symbol, {}).get("reference_band_high"),
            "tier_c_monitor_reference_stop": tier_c_band_rows.get(symbol, {}).get("coarse_reference_stop"),
            "tier_c_monitor_confidence": tier_c_band_rows.get(symbol, {}).get("confidence"),
            "ticker_card_mutation_allowed": False,
            "registry_mutation_allowed": False,
            "owner_note_mutation_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })

    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if len(rows) != 200:
        errors.append(f"expected 200 resolution rows, got {len(rows)}")
    if any(row["resolution_state"] == "blocked_unknown_tier" for row in rows):
        errors.append("one or more rows have unknown tier")
    if any(
        row.get("ticker_card_mutation_allowed")
        or row.get("registry_mutation_allowed")
        or row.get("owner_note_mutation_allowed")
        or row.get("capital_deployment_approved")
        or row.get("trade_or_execution_approved")
        or row.get("paper_or_live_execution_allowed")
        or row.get("owner_approval_inferred")
        for row in rows
    ):
        errors.append("row authority boundary widened")

    state_counts = Counter(str(row.get("resolution_state")) for row in rows)
    tier_counts = Counter(str(row.get("auto_tier")) for row in rows)
    depth_counts = Counter(str(row.get("required_depth")) for row in rows)
    unresolved_states = {
        "blocked_missing_band_context",
        "blocked_owner_lineage_decision_required",
        "blocked_source_artifact_required",
        "blocked_deployment_readiness_surface_required",
        "blocked_position_sizing_surface_required",
        "blocked_unresolved_tier_ab_debt",
        "blocked_unknown_tier",
        "blocked_missing_current_card",
        "blocked_fresh_quote_required_before_final_use",
    }
    unresolved_rows = [row for row in rows if row["resolution_state"] in unresolved_states]
    resolved_rows = [row for row in rows if row["resolution_state"] not in unresolved_states]
    for row in rows:
        row["tier_weighted_resolved"] = row["resolution_state"] not in unresolved_states

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Tier-weighted WF78 freshness debt resolution for all 200 tickers.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [
            rel(LEDGER),
            rel(AUTO_ROUTER),
            rel(REPAIR_EXECUTION),
            rel(POSITION_PROPOSAL),
            rel(DEPLOYMENT_REVIEW),
            rel(OWNER_LINEAGE_DISCOVERY),
            rel(REGISTRY_PREVIEW),
            rel(OWNER_LINEAGE_PROPOSAL),
            rel(BAND_CONTEXT_REPAIR),
            rel(POST_CLOSE_FINAL_QUOTES),
            rel(TIER_C_BAND_STATUS),
            rel(REFRESH_GATE),
        ],
        "summary": {
            "ticker_count": len(rows),
            "tier_counts": dict(tier_counts.most_common()),
            "required_depth_counts": dict(depth_counts.most_common()),
            "resolution_state_counts": dict(state_counts.most_common()),
            "tier_weighted_resolved_count": len(resolved_rows),
            "tier_weighted_unresolved_count": len(unresolved_rows),
            "thin_monitor_resolved_count": state_counts.get("resolved_thin_monitor_current", 0),
            "tier_c_monitor_band_status": tier_c_band_payload.get("summary"),
            "decision_or_promotion_ready_count": state_counts.get("resolved_to_position_sizing_review", 0)
            + state_counts.get("resolved_to_deployment_readiness_review", 0)
            + state_counts.get("resolved_to_owner_lineage_proposal_review", 0)
            + state_counts.get("resolved_to_band_context_repair_recheck", 0)
            + state_counts.get("resolved_to_post_close_final_quote_review", 0)
            + state_counts.get("fresh", 0),
            "owner_decision_blocked_count": state_counts.get("blocked_owner_lineage_decision_required", 0),
            "missing_band_context_blocked_count": state_counts.get("blocked_missing_band_context", 0),
            "owner_lineage_proposal_ready_count": state_counts.get("resolved_to_owner_lineage_proposal_review", 0),
            "band_context_repair_ready_count": state_counts.get("resolved_to_band_context_repair_recheck", 0),
            "post_close_final_quote_review_count": state_counts.get("resolved_to_post_close_final_quote_review", 0),
            "fresh_quote_blocked_count": state_counts.get("blocked_fresh_quote_required_before_final_use", 0),
            "refresh_gate_status": load_dict(REFRESH_GATE).get("status"),
            "refresh_gate_warnings": as_dict(load_dict(REFRESH_GATE).get("validation")).get("warnings"),
            "next_safe_action": (
                "Use resolved Tier C rows as thin-monitor current; review owner-lineage proposals, missing-band repair packets, and post-close quote overlays. Execution freshness still requires a fresh market-window check."
                if state_counts.get("blocked_fresh_quote_required_before_final_use", 0) == 0
                else f"Use resolved Tier C rows as thin-monitor current; review owner-lineage proposals and missing-band repair packets; rerun quote freshness for {state_counts.get('blocked_fresh_quote_required_before_final_use', 0)} remaining Tier A quote gate(s) during a market/provider freshness window."
            ),
        },
        "rows": rows,
        "unresolved_rows": unresolved_rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Resolver changes classification only; no ticker-card, registry, owner-note, canon, portfolio, deployment, or SQL-canon mutation.",
            "Tier C thin-monitor resolution is not decision-grade readiness and does not create entry/stop/deployment authority.",
            "No capital deployment, import/promotion, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 tier-weighted freshness resolution.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"resolved={report['summary']['tier_weighted_resolved_count']} "
            f"unresolved={report['summary']['tier_weighted_unresolved_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
