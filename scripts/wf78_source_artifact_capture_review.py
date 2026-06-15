#!/usr/bin/env python3
"""Build a review-only WF78 source-artifact capture review artifact.

This generator consumes WF78 source-open work packets, current ticker cards,
and the optional official source registry. It only reports capture readiness
and blockers; it does not copy source values into cards or mutate any owner,
canon, portfolio, deployment, SQL, brokerage, or execution surface.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PACKETS = TMP / "wf78-source-open-work-packets.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
OUT = TMP / "wf78-source-artifact-capture-review.json"
SCHEMA = "veritas.wf78_source_artifact_capture_review.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "hard_false_authority_boundary": True,
    "source_artifact_capture_review_only": True,
    "ticker_card_mutation_allowed": False,
    "source_values_copied_into_cards": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
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

FALSE_AUTHORITY_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items() if value is False
}

STOP_LINES = [
    "Review-only source-artifact capture queue; do not mutate ticker cards, canon, portfolio, deployment surfaces, SQL canon/cache, or owner notes.",
    "Do not fabricate source evidence or copy values into cards from this artifact.",
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


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def registry_tickers(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        norm_ticker(symbol): as_dict(row)
        for symbol, row in as_dict(registry.get("tickers")).items()
        if norm_ticker(symbol)
    }


def selected_packet_rows(packets: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_ticker: dict[str, dict[str, Any]] = {}
    for packet in as_list(packets.get("packets")):
        packet = as_dict(packet)
        packet_selected = (
            packet.get("lane") == "source_artifact_capture"
            or packet.get("disposition") == "needs_source_artifact"
        )
        for row in as_list(packet.get("rows")):
            row = as_dict(row)
            selected = packet_selected or row.get("repair_disposition") == "needs_source_artifact"
            ticker = norm_ticker(row.get("ticker"))
            if selected and ticker:
                merged = dict(row)
                merged["_packet_id"] = packet.get("packet_id")
                merged["_packet_lane"] = packet.get("lane")
                rows_by_ticker[ticker] = merged
    return sorted(rows_by_ticker.values(), key=lambda row: (str(row.get("auto_tier") or ""), norm_ticker(row.get("ticker"))))


def entry_stop_status(packet_row: dict[str, Any], card: dict[str, Any]) -> str:
    packet_context = as_dict(packet_row.get("current_band_context"))
    card_reference = as_dict(card.get("entry_stop_reference_metadata"))
    return str(
        first_text(packet_context.get("entry_stop_reference_status"), card_reference.get("status"))
        or "missing"
    )


def source_lineage(packet_row: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    packet_context = as_dict(packet_row.get("current_band_context"))
    reference = as_dict(card.get("entry_stop_reference_metadata"))
    lineage = as_dict(reference.get("source_lineage"))
    owner_source_path = first_text(packet_context.get("owner_source_path"), lineage.get("owner_source_path"))
    source_timestamp = first_text(packet_context.get("owner_source_timestamp"), lineage.get("source_timestamp"))
    source_sha256 = first_text(packet_context.get("owner_source_sha256"), lineage.get("source_sha256"))
    available = bool(packet_row.get("source_lineage_available")) or bool(
        owner_source_path and source_timestamp and source_sha256
    )
    return {
        "available": available,
        "owner_source_path": owner_source_path,
        "source_timestamp": source_timestamp,
        "source_sha256": source_sha256,
    }


def ir_url(card: dict[str, Any], registry_row: dict[str, Any]) -> str | None:
    universe = as_dict(card.get("universe_metadata"))
    source_symbols = as_dict(universe.get("source_symbols"))
    reconciliation = as_dict(card.get("fundamental_reconciliation"))
    return first_text(
        source_symbols.get("company_ir"),
        reconciliation.get("company_ir_source_url"),
        registry_row.get("official_earnings_source_url"),
    )


def official_capture_status(card: dict[str, Any]) -> str:
    capture = as_dict(card.get("official_capture_developments_orders_backlog"))
    statuses: list[str] = []
    for value in capture.values():
        if isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str) and status:
                statuses.append(status)
    earnings = as_dict(card.get("latest_earnings_performance"))
    for key in ("official_adjusted_eps", "official_growth_bridge", "official_guidance", "management_explanation"):
        status = as_dict(earnings.get(key)).get("status")
        if isinstance(status, str) and status:
            statuses.append(status)
    if not statuses:
        return "not_assessed"
    if any(status == "available" for status in statuses):
        return "official_capture_pointer_present_in_card"
    if all(status == "missing_manual_required" for status in statuses):
        return "missing_manual_required"
    return "partial_or_mixed_manual_review_required"


def row_for(packet_row: dict[str, Any], registry_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ticker = norm_ticker(packet_row.get("ticker"))
    path = card_path(ticker)
    card = load_dict(path)
    registry_row = registry_rows.get(ticker, {})
    registry_available = bool(registry_row)
    lineage = source_lineage(packet_row, card)
    entry_status = entry_stop_status(packet_row, card)
    capture_status = official_capture_status(card)

    if lineage["available"]:
        next_step = "Verify existing owner entry/stop source lineage before any separate integration pass; no card mutation from this review."
        blocker = None
    elif registry_available:
        next_step = "Open the official registry URL and capture owner/source evidence in a separate gated integration pass."
        blocker = "entry_stop_owner_source_lineage_missing"
    else:
        next_step = "Find an official IR/earnings source and owner entry/stop source artifact; keep ticker blocked until evidence exists."
        blocker = "official_registry_and_entry_stop_lineage_missing"

    return {
        "ticker": ticker,
        "tier": packet_row.get("auto_tier"),
        "route_state": packet_row.get("route_state"),
        "packet_id": packet_row.get("_packet_id"),
        "packet_lane": packet_row.get("_packet_lane"),
        "repair_disposition": packet_row.get("repair_disposition"),
        "card_path": rel(path),
        "card_available": bool(card),
        "ir_url": ir_url(card, registry_row),
        "entry_stop_reference_status": entry_status,
        "source_lineage_availability": lineage,
        "official_registry_availability": {
            "available": registry_available,
            "registry_path": rel(REGISTRY),
            "official_earnings_source_url": registry_row.get("official_earnings_source_url"),
            "source_label": registry_row.get("source_label"),
            "period_label": registry_row.get("period_label"),
            "source_section": registry_row.get("source_section"),
        },
        "capture_status": capture_status,
        "recommended_non_mutating_next_step": next_step,
        "residual_blocker": blocker,
        "authority_boundary": {
            "review_only": True,
            "card_mutation_allowed": False,
            "source_value_copy_allowed": False,
            "capital_deployment_allowed": False,
            "trade_or_execution_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if artifact.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    authority = as_dict(artifact.get("authority_boundary"))
    for key in FALSE_AUTHORITY_KEYS:
        if authority.get(key) is not False:
            errors.append(f"authority_not_false:{key}")
    if authority.get("review_only") is not True:
        errors.append("review_only_not_true")
    rows = [as_dict(row) for row in as_list(artifact.get("rows"))]
    if not rows:
        return {"status": "ok_no_work", "errors": [], "warnings": ["no_source_artifact_rows"]}
    for row in rows:
        ticker = norm_ticker(row.get("ticker"))
        if not ticker:
            errors.append("row_missing_ticker")
        if row.get("packet_lane") != "source_artifact_capture" and row.get("repair_disposition") != "needs_source_artifact":
            errors.append(f"unexpected_row_scope:{ticker or 'unknown'}")
        row_authority = as_dict(row.get("authority_boundary"))
        for key in ("card_mutation_allowed", "source_value_copy_allowed", "capital_deployment_allowed", "trade_or_execution_allowed", "paper_or_live_execution_allowed", "owner_approval_inferred"):
            if row_authority.get(key) is not False:
                errors.append(f"row_authority_not_false:{ticker}:{key}")
        if not row.get("card_available"):
            warnings.append(f"card_missing:{ticker}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build() -> dict[str, Any]:
    packets = load_dict(PACKETS)
    registry = load_dict(REGISTRY)
    registry_rows = registry_tickers(registry)
    packet_rows = selected_packet_rows(packets)
    rows = [row_for(row, registry_rows) for row in packet_rows]

    tier_counts = Counter(str(row.get("tier") or "unknown") for row in rows)
    capture_counts = Counter(str(row.get("capture_status") or "unknown") for row in rows)
    entry_stop_counts = Counter(str(row.get("entry_stop_reference_status") or "unknown") for row in rows)
    registry_available_count = sum(1 for row in rows if as_dict(row.get("official_registry_availability")).get("available"))
    lineage_available_count = sum(1 for row in rows if as_dict(row.get("source_lineage_availability")).get("available"))

    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Review-only WF78 source-artifact capture queue for rows needing source artifact evidence.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "work_packets_path": rel(PACKETS),
            "ticker_card_glob": rel(CARD_DIR / "*.current.json"),
            "official_registry_path": rel(REGISTRY),
            "official_registry_loaded": bool(registry),
        },
        "summary": {
            "target_packet_row_count": len(packet_rows),
            "review_row_count": len(rows),
            "ticker_count": len({row.get("ticker") for row in rows}),
            "tier_counts": dict(tier_counts),
            "entry_stop_reference_status_counts": dict(entry_stop_counts),
            "source_lineage_available_count": lineage_available_count,
            "source_lineage_missing_count": len(rows) - lineage_available_count,
            "official_registry_available_count": registry_available_count,
            "official_registry_missing_count": len(rows) - registry_available_count,
            "capture_status_counts": dict(capture_counts),
            "blocked_count": sum(1 for row in rows if row.get("residual_blocker")),
        },
        "rows": rows,
        "stop_lines": STOP_LINES,
    }
    artifact["validation"] = validate_artifact(artifact)
    artifact["status"] = artifact["validation"]["status"]
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the review artifact to disk.")
    parser.add_argument("--validate", action="store_true", help="Fail if the generated artifact does not validate.")
    parser.add_argument("--out", default=str(OUT), help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = build()
    if args.write:
        atomic_write_json(Path(args.out), artifact)
    if args.validate and not str(artifact["validation"]["status"]).startswith("ok"):
        for error in artifact["validation"]["errors"]:
            print(error)
        return 1
    print(
        f"{artifact['validation']['status']}: rows={artifact['summary']['review_row_count']} "
        f"blocked={artifact['summary']['blocked_count']} out={args.out if args.write else '<not-written>'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
