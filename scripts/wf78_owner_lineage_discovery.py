#!/usr/bin/env python3
"""Discover existing owner entry/stop lineage for WF78 promotion-scope rows."""
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
QUEUE = TMP / "wf78-promotion-owner-lineage-queue.json"
POSITION_PROPOSAL = TMP / "wf78-position-sizing-integration-proposal.json"
OWNER_PROPOSALS = TMP / "wf78-tier-a-owner-readiness-proposals.json"
SOURCE_CAPTURE = TMP / "wf78-source-artifact-capture-review.json"
REGISTRY_PREVIEW = TMP / "wf78-official-registry-apply-preview.json"
OUT = TMP / "wf78-owner-lineage-discovery.json"
SCHEMA = "veritas.wf78_owner_lineage_discovery.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "owner_lineage_discovery_only": True,
    "owner_note_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
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


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def rows_by_ticker(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_dict(path)
    return {ticker(row.get("ticker")): as_dict(row) for row in as_list(payload.get("rows")) if ticker(as_dict(row).get("ticker"))}


def card_lineage(symbol: str) -> dict[str, Any]:
    card = load_dict(CARD_DIR / f"{symbol}.current.json")
    metadata = as_dict(card.get("entry_stop_reference_metadata"))
    lineage = as_dict(metadata.get("source_lineage"))
    owner_source_path = first_text(lineage.get("owner_source_path"), metadata.get("owner_source_path"))
    source_timestamp = first_text(lineage.get("source_timestamp"), metadata.get("source_timestamp"))
    source_sha256 = first_text(lineage.get("source_sha256"), metadata.get("source_sha256"))
    available = bool(owner_source_path and source_timestamp and source_sha256 and metadata.get("status") != "fallback_required")
    return {
        "available": available,
        "status": metadata.get("status"),
        "owner_source_path": owner_source_path,
        "source_timestamp": source_timestamp,
        "source_sha256": source_sha256,
        "source": rel(CARD_DIR / f"{symbol}.current.json"),
    }


def generic_lineage(row: dict[str, Any], key: str = "source_lineage") -> dict[str, Any]:
    lineage = as_dict(row.get(key))
    owner_source_path = first_text(lineage.get("owner_source_path"))
    source_timestamp = first_text(lineage.get("source_timestamp"))
    source_sha256 = first_text(lineage.get("source_sha256"))
    return {
        "available": bool(lineage.get("available")) or bool(owner_source_path and source_timestamp and source_sha256),
        "owner_source_path": owner_source_path,
        "source_timestamp": source_timestamp,
        "source_sha256": source_sha256,
    }


def source_capture_lineage(row: dict[str, Any]) -> dict[str, Any]:
    lineage = as_dict(row.get("source_lineage_availability"))
    return {
        "available": bool(lineage.get("available")),
        "owner_source_path": first_text(lineage.get("owner_source_path")),
        "source_timestamp": first_text(lineage.get("source_timestamp")),
        "source_sha256": first_text(lineage.get("source_sha256")),
    }


def registry_preview_map() -> dict[str, dict[str, Any]]:
    return rows_by_ticker(REGISTRY_PREVIEW)


def lineage_row(queue_row: dict[str, Any], sources: dict[str, dict[str, dict[str, Any]]], registry_preview: dict[str, dict[str, Any]]) -> dict[str, Any]:
    symbol = ticker(queue_row.get("ticker"))
    candidates = [
        ("ticker_card_entry_stop_reference_metadata", card_lineage(symbol)),
        ("position_sizing_integration_proposal", generic_lineage(sources["position"].get(symbol, {}))),
        ("tier_a_owner_readiness_proposals", generic_lineage(sources["owner"].get(symbol, {}))),
        ("source_artifact_capture_review", source_capture_lineage(sources["capture"].get(symbol, {}))),
    ]
    found = [dict(source=name, **lineage) for name, lineage in candidates if lineage.get("available")]
    preview = registry_preview.get(symbol, {})
    if found:
        status = "lineage_found"
        next_step = f"Use existing {symbol} owner entry/stop lineage for review-only repair integration."
    elif preview.get("preview_action") == "would_add_registry_row":
        status = "needs_owner_decision"
        next_step = f"{symbol} has official registry preview evidence, but owner entry/stop lineage still requires an owner/source decision."
    else:
        status = "lineage_missing"
        next_step = f"Find source-backed owner entry/stop lineage for {symbol}; keep repair blocked until it exists."
    return {
        "ticker": symbol,
        "auto_tier": queue_row.get("auto_tier"),
        "route_state": queue_row.get("route_state"),
        "queue_lineage_status": queue_row.get("lineage_status"),
        "discovery_status": status,
        "lineage_candidates_checked": [name for name, _ in candidates],
        "lineage_evidence": found,
        "official_registry_preview_status": preview.get("preview_action"),
        "recommended_next_step": next_step,
        "owner_note_mutation_allowed": False,
        "ticker_card_mutation_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def build() -> dict[str, Any]:
    queue = load_dict(QUEUE)
    sources = {
        "position": rows_by_ticker(POSITION_PROPOSAL),
        "owner": rows_by_ticker(OWNER_PROPOSALS),
        "capture": rows_by_ticker(SOURCE_CAPTURE),
    }
    registry_preview = registry_preview_map()
    target_rows = [as_dict(row) for row in as_list(queue.get("rows")) if as_dict(row).get("lineage_status") == "owner_lineage_required"]
    rows = [lineage_row(row, sources, registry_preview) for row in target_rows]
    status_counts = Counter(str(row.get("discovery_status")) for row in rows)
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        if key not in {"review_only", "owner_lineage_discovery_only"} and value is not False:
            errors.append(f"authority flag not false: {key}")
    for row in rows:
        if row.get("owner_note_mutation_allowed") or row.get("ticker_card_mutation_allowed"):
            errors.append(f"{row.get('ticker')} row implies mutation")
        if row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred"):
            errors.append(f"{row.get('ticker')} authority boundary widened")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only discovery of existing owner entry/stop lineage for promotion-scope WF78 rows.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(QUEUE), rel(POSITION_PROPOSAL), rel(OWNER_PROPOSALS), rel(SOURCE_CAPTURE), rel(REGISTRY_PREVIEW)],
        "summary": {
            "target_row_count": len(target_rows),
            "discovery_status_counts": dict(status_counts),
            "lineage_found_count": status_counts.get("lineage_found", 0),
            "lineage_missing_or_owner_decision_count": len(rows) - status_counts.get("lineage_found", 0),
            "next_safe_action": "Only rows with lineage_found can move toward review-only repair integration; owner-decision rows remain blocked.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Discovery only; no owner-note, card, deployment, canon, portfolio, or SQL-canon mutation.",
            "No fabricated bands/stops and no capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover WF78 owner entry/stop lineage.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} rows={report['summary']['target_row_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
