#!/usr/bin/env python3
"""Build a compact, review-only finance route for primary vector retrieval.

The WF84/WF85 packets remain the detailed proof surfaces. This artifact keeps
only deterministic routing, freshness, and drillback fields so routine vector
queries do not ingest repeated raw JSON bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WF84 = ROOT / "tmp" / "canonical-finance-data-plane.json"
DEFAULT_WF85 = ROOT / "tmp" / "trade-grade-decision-cards.json"
DEFAULT_OUT = ROOT / "tmp" / "finance-vector-retrieval-summary.json"
SCHEMA = "veritas.finance_vector_retrieval_summary.v1"
FORBIDDEN_NESTED_KEYS = {"raw_json", "source_drillback", "scenario_context", "authority_boundary"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "derived_routing_only": True,
    "source_open_required_before_material_finance_claims": True,
    "creates_canon": False,
    "approval_authority": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "customer_or_external_output_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def read_packet(path: Path) -> tuple[bytes, dict[str, Any]]:
    data = path.read_bytes()
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data, parsed


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_rows(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            result[ticker] = row
    return result


def scalar(value: Any) -> str | int | float | bool | None:
    return value if value is None or isinstance(value, (str, int, float, bool)) else None


def compact_text(value: Any, *, limit: int = 280) -> str | None:
    if not isinstance(value, str):
        return None
    compacted = " ".join(value.split())
    return compacted[:limit] if compacted else None


def picked(row: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: scalar(row.get(key)) for key in keys if scalar(row.get(key)) is not None}


def evidence_exceptions(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    exceptions: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        status = str(row.get("status") or "").lower()
        # This compact routing surface is for actionable evidence debt.  Covered,
        # resolved, and fresh rows are repeated for most tickers and belong in the
        # detailed WF84 source packet, not the protected primary vector summary.
        if (
            not ticker
            or status in {"ok", "covered", "available", "ready", "fresh"}
            or status.startswith("covered_")
            or status.startswith("resolved_")
        ):
            continue
        exceptions.setdefault(ticker, []).append(
            {
                "family_id": scalar(row.get("family_id")),
                "status": scalar(row.get("status")),
                "resolution_state": scalar(row.get("resolution_state")),
                "missing_count": scalar(row.get("missing_count")),
                "stale_count": scalar(row.get("stale_count")),
            }
        )
    for ticker in exceptions:
        exceptions[ticker].sort(key=lambda item: str(item.get("family_id") or ""))
    return exceptions


def source_packet_metadata(root: Path, path: Path, data: bytes, packet: dict[str, Any], *, workflow: str) -> dict[str, Any]:
    validation = as_dict(packet.get("validation"))
    return {
        "workflow_id": workflow,
        "path": rel(root, path),
        "sha256": sha256_bytes(data),
        "generated_at_utc": scalar(packet.get("generated_at_utc")),
        "status": scalar(packet.get("status")),
        "validation_status": scalar(validation.get("status")),
    }


def compact_source_artifacts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(
            {
                key: scalar(row.get(key))
                for key in (
                    "artifact_id",
                    "path",
                    "role",
                    "status",
                    "validation_status",
                    "sha256",
                    "source_rank",
                    "source_type",
                    "required_for_mvp",
                )
                if scalar(row.get(key)) is not None
            }
        )
    return sorted(result, key=lambda item: str(item.get("artifact_id") or ""))


def build_route(
    ticker: str,
    *,
    security: dict[str, Any],
    routing: dict[str, Any],
    queue: dict[str, Any],
    price: dict[str, Any],
    entry_stop: dict[str, Any],
    fundamental: dict[str, Any],
    earnings: dict[str, Any],
    analyst: dict[str, Any],
    card: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    card_band = as_dict(card.get("entry_band"))
    card_stop = as_dict(card.get("stop_or_invalidation"))
    card_freshness = as_dict(card.get("source_freshness"))
    promotion = as_dict(card.get("promotion_gate"))
    route = {
        "ticker": ticker,
        "security": picked(security, "name", "instrument_type", "sector", "industry"),
        "routing": picked(routing, "auto_tier", "auto_state", "route_priority", "route_reason", "tier_a_confidence_status"),
        "queue": picked(queue, "primary_state", "queue_state", "gate_verdict", "rank_score", "actionability", "owner_action_required", "wf67_request_generation_status"),
        "decision": {
            **picked(card, "decision_state"),
            "promotion_verdict": scalar(promotion.get("verdict")),
            "promotion_vetoes": [compact_text(item, limit=120) for item in promotion.get("vetoes", []) if compact_text(item, limit=120)] if isinstance(promotion.get("vetoes"), list) else [],
        },
        "freshness": {
            **picked(price, "market_date", "quote_freshness_status", "quote_time_utc", "fresh_quote_required", "band_status", "technical_status"),
            **{key: scalar(card_freshness.get(key)) for key in ("status", "scope") if scalar(card_freshness.get(key)) is not None},
        },
        "price_and_band": {
            **picked(price, "latest_known_price"),
            "technical_summary": compact_text(price.get("technical_summary"), limit=140),
            "entry_band_low": scalar(entry_stop.get("entry_band_low")) if scalar(entry_stop.get("entry_band_low")) is not None else scalar(card_band.get("low")),
            "entry_band_high": scalar(entry_stop.get("entry_band_high")) if scalar(entry_stop.get("entry_band_high")) is not None else scalar(card_band.get("high")),
            "stop_or_invalidation": scalar(entry_stop.get("stop_or_invalidation")) if scalar(entry_stop.get("stop_or_invalidation")) is not None else scalar(card_stop.get("level")),
            "entry_stop_freshness_status": scalar(entry_stop.get("freshness_status")),
            "entry_stop_validation_status": scalar(entry_stop.get("validation_status")) if scalar(entry_stop.get("validation_status")) is not None else scalar(card_band.get("validation_status")),
            "entry_stop_source_path": scalar(entry_stop.get("source_artifact_path")) if scalar(entry_stop.get("source_artifact_path")) is not None else scalar(card_band.get("source_path")),
            "entry_stop_source_hash": scalar(entry_stop.get("source_artifact_hash")),
            "entry_stop_source_timestamp": scalar(entry_stop.get("source_timestamp")) if scalar(entry_stop.get("source_timestamp")) is not None else scalar(card_band.get("source_timestamp")),
        },
        "fundamentals": picked(fundamental, "data_quality", "key_metrics_status", "latest_earnings_status", "valuation_status", "sec_reconciliation_status"),
        "earnings": picked(earnings, "catalyst_status", "latest_earnings_status", "next_earnings_date", "days_to_earnings", "earnings_date_confirmed", "post_earnings_review_confirmed"),
        "analyst": picked(analyst, "status", "consensus_rating", "rating_summary", "average_target", "median_target", "implied_upside_downside_pct", "confidence", "manual_review_required"),
        "evidence_exceptions": evidence,
    }
    decision_state = route["decision"].get("decision_state") or "unavailable"
    tier = route["routing"].get("auto_tier") or route["decision"].get("auto_tier") or "unclassified"
    price_value = route["price_and_band"].get("latest_known_price")
    band_status = route["freshness"].get("band_status") or "unknown"
    freshness = route["freshness"].get("status") or route["freshness"].get("quote_freshness_status") or "unknown"
    route["retrieval_text"] = (
        f"{ticker}: {tier}; {decision_state}; price={price_value}; band={band_status}; freshness={freshness}. "
        "Review-only. Source-open WF84/WF85 before material claims or action."
    )
    return route


def build_summary(*, root: Path, wf84_path: Path, wf85_path: Path, out_path: Path) -> dict[str, Any]:
    wf84_bytes, wf84 = read_packet(wf84_path)
    wf85_bytes, wf85 = read_packet(wf85_path)
    tables = as_dict(wf84.get("tables"))
    security = by_ticker(as_rows(tables.get("security_master")))
    routing = by_ticker(as_rows(tables.get("routing_state_current")))
    queue = by_ticker(as_rows(tables.get("decision_queue_state")))
    price = by_ticker(as_rows(tables.get("price_technical_current")))
    entry_stop = by_ticker(as_rows(tables.get("entry_stop_reference")))
    fundamental = by_ticker(as_rows(tables.get("fundamental_snapshot")))
    earnings = by_ticker(as_rows(tables.get("earnings_catalyst")))
    analyst = by_ticker(as_rows(tables.get("analyst_snapshot")))
    cards = by_ticker(as_rows(wf85.get("cards")))
    evidence = evidence_exceptions(as_rows(tables.get("evidence_family_status")))
    tickers = sorted(set(security) | set(routing) | set(queue) | set(cards))
    routes = [
        build_route(
            ticker,
            security=security.get(ticker, {}),
            routing=routing.get(ticker, {}),
            queue=queue.get(ticker, {}),
            price=price.get(ticker, {}),
            entry_stop=entry_stop.get(ticker, {}),
            fundamental=fundamental.get(ticker, {}),
            earnings=earnings.get(ticker, {}),
            analyst=analyst.get(ticker, {}),
            card=cards.get(ticker, {}),
            evidence=evidence.get(ticker, []),
        )
        for ticker in tickers
    ]
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ok",
        "generated_at_utc": utc_now(),
        "purpose": "Compact review-only finance retrieval routing for the primary vector-memory profile; not canon, approval, or execution authority.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_packets": [
            source_packet_metadata(root, wf84_path, wf84_bytes, wf84, workflow="WF84"),
            source_packet_metadata(root, wf85_path, wf85_bytes, wf85, workflow="WF85"),
        ],
        "raw_drillback_contract": {
            "required_before_material_finance_claims": True,
            "wf84": {
                "path": rel(root, wf84_path),
                "tables": ["security_master", "routing_state_current", "decision_queue_state", "price_technical_current", "entry_stop_reference", "fundamental_snapshot", "earnings_catalyst", "analyst_snapshot"],
                "key": "ticker",
                "read_only_command": "python scripts\\canonical_finance_data_plane.py ticker <TICKER> --pretty",
            },
            "wf85": {
                "path": rel(root, wf85_path),
                "collection": "cards",
                "key": "ticker",
            },
        },
        "source_artifacts": compact_source_artifacts(as_rows(tables.get("source_artifact"))),
        "route_count": len(routes),
        "ticker_routes": routes,
    }
    validation = validate_summary(payload, root=root)
    payload["validation"] = validation
    payload["status"] = "ok" if validation["status"] == "ok" else "error"
    if validation["status"] != "ok":
        raise ValueError(f"finance vector retrieval summary validation failed: {validation['errors']}")
    atomic_write_json(out_path, payload)
    return payload


def nested_forbidden_keys(value: Any, *, path: tuple[str, ...] = ()) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            next_path = (*path, str(key))
            if key in FORBIDDEN_NESTED_KEYS and next_path != ("authority_boundary",):
                found.append(".".join(next_path))
            found.extend(nested_forbidden_keys(child, path=next_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(nested_forbidden_keys(child, path=(*path, str(index))))
    return found


def validate_summary(payload: dict[str, Any], *, root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    routes = as_rows(payload.get("ticker_routes"))
    tickers = [str(route.get("ticker") or "") for route in routes]
    if not routes:
        errors.append("no_ticker_routes")
    if tickers != sorted(tickers) or len(set(tickers)) != len(tickers):
        errors.append("ticker_routes_not_sorted_unique")
    if int(payload.get("route_count") or 0) != len(routes):
        errors.append("route_count_mismatch")
    boundary = as_dict(payload.get("authority_boundary"))
    for key in (
        "creates_canon",
        "approval_authority",
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "portfolio_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "customer_or_external_output_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"authority_flag_not_false:{key}")
    forbidden = nested_forbidden_keys(payload)
    if forbidden:
        errors.append(f"forbidden_nested_keys:{','.join(forbidden[:8])}")
    packets = as_rows(payload.get("source_packets"))
    if len(packets) != 2:
        errors.append("source_packet_count_not_two")
    for packet in packets:
        relative = str(packet.get("path") or "")
        path = root / relative
        if not path.exists():
            errors.append(f"missing_source_packet:{relative}")
        elif sha256_bytes(path.read_bytes()) != packet.get("sha256"):
            errors.append(f"source_packet_hash_drift:{relative}")
    encoded_size = len(json.dumps(payload, sort_keys=True).encode("utf-8"))
    if encoded_size > 750_000:
        errors.append(f"summary_size_exceeds_budget:{encoded_size}")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "route_count": len(routes),
        "serialized_bytes": encoded_size,
        "size_budget_bytes": 750_000,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wf84", default=str(DEFAULT_WF84))
    parser.add_argument("--wf85", default=str(DEFAULT_WF85))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    wf84_path = Path(args.wf84)
    wf85_path = Path(args.wf85)
    out_path = Path(args.out)
    if not wf84_path.is_absolute():
        wf84_path = ROOT / wf84_path
    if not wf85_path.is_absolute():
        wf85_path = ROOT / wf85_path
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    try:
        if args.write:
            payload = build_summary(root=ROOT, wf84_path=wf84_path, wf85_path=wf85_path, out_path=out_path)
        else:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        if args.validate:
            payload["validation"] = validate_summary(payload, root=ROOT)
            payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
            if args.write:
                atomic_write_json(out_path, payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schema": SCHEMA, "status": "error", "error": str(exc)}
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({"status": payload.get("status"), "validation": payload.get("validation")}, sort_keys=True))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
