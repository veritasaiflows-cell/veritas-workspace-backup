#!/usr/bin/env python3
"""Build a compact finance cache front door for chat consumption.

SQL canon, WF84, and WF85 remain the production truth/proof layers. This
script only builds a small read facade so chat and lightweight CLIs can answer
from cache first, then source-open only when the claim is material.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from route_readiness import route_readiness_from_wf84_row


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

WF84_DB = TMP / "canonical-finance-data-plane.sqlite"
WF85_FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"
WF85_FULL_ANSWER_ROLLUP = TMP / "trade-grade-full-answer-assembler.json"
SOURCE_FRESHNESS_GATE = TMP / "trade-grade-source-freshness-gate.json"
OS_FRESHNESS_RUNNER = TMP / "trade-grade-os-freshness-cron-runner.json"
CACHE_DEPENDENCY_MANIFEST = TMP / "cache-dependency-manifest.json"
TIER_C_BAND_STATUS = TMP / "tier-c-band-status.json"
OUT = TMP / "finance-cache-frontdoor.json"

SCHEMA = "veritas.finance_cache_frontdoor.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "chat_cache_facade_only": True,
    "sql_first_truth_production_retained": True,
    "cache_first_chat_consumption": True,
    "source_open_required_for_material_claims": True,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cache_database_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = tuple(
    key for key in AUTHORITY_BOUNDARY
    if key.endswith("_allowed") or key.endswith("_inferred")
)

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def age_hours(value: Any) -> float | None:
    dt = parse_utc(value)
    if dt is None:
        return None
    return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600.0, 2)


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def wf84_rows() -> list[dict[str, Any]]:
    if not WF84_DB.exists():
        return []
    conn = connect_ro(WF84_DB)
    try:
        rows = conn.execute(
            """
            SELECT ticker, name, instrument_type, sector, auto_tier, auto_state,
                   route_priority, latest_known_price, band_status,
                   quote_freshness_status, entry_band_low, entry_band_high,
                   stop_or_invalidation, primary_state, queue_state,
                   actionability, owner_action_required,
                   capital_deployment_approved, trade_or_execution_approved,
                   paper_or_live_execution_allowed, owner_approval_inferred
            FROM v_current_decision_overview
            ORDER BY auto_tier, route_priority DESC, ticker
            """
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def source_rows_by_ticker() -> dict[str, dict[str, Any]]:
    payload = as_dict(load_json_artifact(SOURCE_FRESHNESS_GATE))
    return {
        str(row.get("ticker") or "").upper(): as_dict(row)
        for row in as_list(payload.get("rows"))
        if as_dict(row).get("ticker")
    }


def tier_c_monitor_bands_by_ticker() -> dict[str, dict[str, Any]]:
    payload = as_dict(load_json_artifact(TIER_C_BAND_STATUS))
    if payload.get("status") != "ok":
        return {}
    return {
        str(row.get("ticker") or "").upper(): as_dict(row)
        for row in as_list(payload.get("rows"))
        if as_dict(row).get("ticker")
    }


def missing_band_status(value: Any) -> bool:
    return str(value or "").strip().lower() in {"", "unknown", "missing_required_refresh"}


def usable_tier_c_monitor_band(wf84: dict[str, Any], monitor: dict[str, Any]) -> bool:
    if wf84.get("auto_tier") != "Tier C":
        return False
    if not missing_band_status(wf84.get("band_status")):
        return False
    status = str(monitor.get("band_status") or "").strip().upper()
    if status in {"", "UNKNOWN", "STALE", "MISSING_REQUIRED_REFRESH"}:
        return False
    return monitor.get("monitor_grade") is True and monitor.get("decision_grade") is False


def wf84_for_route_readiness(wf84: dict[str, Any], monitor: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if not usable_tier_c_monitor_band(wf84, monitor):
        return wf84, False
    routed = dict(wf84)
    routed["band_status"] = monitor.get("band_status")
    routed["quote_freshness_status"] = "tier_c_monitor_grade_reference"
    return routed, True


def answer_descriptor(ticker: str, max_age_hours: float) -> dict[str, Any]:
    path = WF85_FULL_ANSWER_DIR / f"{ticker}.json"
    if not path.exists():
        return {
            "status": "missing",
            "path": rel(path),
            "generated_at_utc": None,
            "age_hours": None,
            "confidence": None,
            "confidence_score": None,
            "decision_state": None,
            "missing_sections": [],
            "source_count": None,
        }
    payload = as_dict(load_json_artifact(path))
    validation = as_dict(payload.get("validation"))
    confidence = as_dict(payload.get("answer_confidence"))
    machine = as_dict(payload.get("machine_state"))
    answer_age = age_hours(payload.get("generated_at_utc"))
    status = "ok" if payload.get("status") == "ok" and validation.get("status") == "ok" else "warning"
    if answer_age is None:
        status = "missing_generated_at"
    elif answer_age > max_age_hours:
        status = "stale"
    return {
        "status": status,
        "path": rel(path),
        "generated_at_utc": payload.get("generated_at_utc"),
        "age_hours": answer_age,
        "confidence": confidence.get("overall_level"),
        "confidence_score": confidence.get("score"),
        "decision_state": machine.get("decision_state"),
        "primary_state": machine.get("primary_state"),
        "queue_state": machine.get("queue_state"),
        "recommended_next_action": as_dict(machine.get("owner_action")).get("owner_action"),
        "missing_sections": as_list(validation.get("missing_sections")),
        "source_count": payload.get("source_count"),
    }


def current_decision_state(answer: dict[str, Any], source: dict[str, Any], wf84: dict[str, Any], source_open: str) -> str | None:
    answer_state = answer.get("decision_state")
    source_state = source.get("decision_state")
    wf84_state = wf84.get("primary_state")
    if answer_state == "blocked_missing_source_open" and source_open == "verified":
        return source_state or wf84_state
    return answer_state or source_state or wf84_state


def cache_row(wf84: dict[str, Any], source: dict[str, Any], max_age_hours: float, monitor_band: dict[str, Any]) -> dict[str, Any]:
    ticker = str(wf84.get("ticker") or "").upper()
    answer = answer_descriptor(ticker, max_age_hours)
    source_open = source.get("source_open_status") or "unknown"
    freshness = source.get("freshness_status") or "unknown"
    decision_state = current_decision_state(answer, source, wf84, source_open)
    routed_wf84, monitor_band_applied = wf84_for_route_readiness(wf84, monitor_band)
    route_readiness = route_readiness_from_wf84_row(routed_wf84, decision_state)
    material_requires_source_open = source_open != "verified"
    reasons: list[str] = []
    if answer["status"] != "ok":
        reasons.append(f"answer_status={answer['status']}")
    if answer.get("missing_sections"):
        reasons.append("answer_missing_sections")
    if freshness not in {"fresh", "scoped_thin_monitor_not_required"}:
        reasons.append(f"freshness_status={freshness}")
    if not source:
        reasons.append("source_freshness_row_missing")
    safe_to_answer = not reasons
    if material_requires_source_open:
        # Review-only cached status can still be used, but recommendation/action
        # language must source-open first.
        reasons.append(f"material_claim_source_open_status={source_open}")
    needs_refresh_or_source_open = bool(reasons)
    return {
        "ticker": ticker,
        "name": wf84.get("name"),
        "instrument_type": wf84.get("instrument_type"),
        "sector": wf84.get("sector"),
        "auto_tier": wf84.get("auto_tier"),
        "auto_state": wf84.get("auto_state"),
        "route_priority": wf84.get("route_priority"),
        "latest_price": wf84.get("latest_known_price"),
        "band_status": route_readiness.get("band_status"),
        "wf84_band_status": wf84.get("band_status"),
        "band_status_source": "tier_c_monitor_grade_reference" if monitor_band_applied else "wf84_current_decision_overview",
        "quote_freshness_status": wf84.get("quote_freshness_status"),
        "route_quote_freshness_status": route_readiness.get("quote_freshness_status"),
        "entry_band_low": wf84.get("entry_band_low"),
        "entry_band_high": wf84.get("entry_band_high"),
        "stop_or_invalidation": wf84.get("stop_or_invalidation"),
        "tier_c_monitor_grade_band_applied": monitor_band_applied,
        "monitor_grade_reference_band_low": monitor_band.get("reference_band_low") if monitor_band_applied else None,
        "monitor_grade_reference_band_high": monitor_band.get("reference_band_high") if monitor_band_applied else None,
        "monitor_grade_reference_stop": monitor_band.get("coarse_reference_stop") if monitor_band_applied else None,
        "monitor_grade_band_context": monitor_band if monitor_band_applied else {},
        "primary_state": wf84.get("primary_state"),
        "queue_state": wf84.get("queue_state"),
        "decision_state": decision_state,
        "routing_tier": route_readiness["routing_tier"],
        "routing_state": route_readiness["routing_state"],
        "timing_state": route_readiness["timing_state"],
        "trade_readiness_state": route_readiness["trade_readiness_state"],
        "authority_state": route_readiness["authority_state"],
        "route_readiness": route_readiness,
        "actionability": wf84.get("actionability"),
        "recommended_next_action": answer.get("recommended_next_action") or route_readiness["next_route_action"],
        "source_open_status": source_open,
        "freshness_status": freshness,
        "material_claim_requires_source_open": material_requires_source_open,
        "source_open_required_before_material_claim": material_requires_source_open,
        "safe_to_answer_from_cache": safe_to_answer,
        "safe_for_material_claim_from_cache": safe_to_answer and not material_requires_source_open,
        "needs_refresh_or_source_open": needs_refresh_or_source_open,
        "needs_refresh_reason": reasons,
        "answer_missing_section_count": len(answer.get("missing_sections") or []),
        "canonical_answer_path": answer.get("path"),
        "review_only": True,
        "answer": answer,
        "authority": route_readiness["authority"],
    }


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path)) if path.exists() and path.suffix == ".json" else {}
    return {
        "path": rel(path),
        "present": path.exists(),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "age_hours": age_hours(payload.get("generated_at_utc")),
    }


def build_payload(max_age_hours: float = 12.0) -> dict[str, Any]:
    wf84 = wf84_rows()
    source_lookup = source_rows_by_ticker()
    tier_c_monitor_lookup = tier_c_monitor_bands_by_ticker()
    rows = [
        cache_row(
            row,
            source_lookup.get(str(row.get("ticker") or "").upper(), {}),
            max_age_hours,
            tier_c_monitor_lookup.get(str(row.get("ticker") or "").upper(), {}),
        )
        for row in wf84
    ]
    status_counts: dict[str, int] = {}
    source_open_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    timing_counts: dict[str, int] = {}
    trade_readiness_counts: dict[str, int] = {}
    authority_state_counts: dict[str, int] = {}
    for row in rows:
        status_counts["safe" if row["safe_to_answer_from_cache"] else "needs_refresh_or_source_open"] = status_counts.get("safe" if row["safe_to_answer_from_cache"] else "needs_refresh_or_source_open", 0) + 1
        source_open_counts[str(row.get("source_open_status"))] = source_open_counts.get(str(row.get("source_open_status")), 0) + 1
        decision_counts[str(row.get("decision_state"))] = decision_counts.get(str(row.get("decision_state")), 0) + 1
        timing_counts[str(row.get("timing_state"))] = timing_counts.get(str(row.get("timing_state")), 0) + 1
        trade_readiness_counts[str(row.get("trade_readiness_state"))] = trade_readiness_counts.get(str(row.get("trade_readiness_state")), 0) + 1
        authority_state_counts[str(row.get("authority_state"))] = authority_state_counts.get(str(row.get("authority_state")), 0) + 1
    errors: list[str] = []
    warnings: list[str] = []
    if not WF84_DB.exists():
        errors.append("wf84_sqlite_missing")
    if not rows:
        errors.append("frontdoor_ticker_rows_missing")
    if len(rows) != len(source_lookup):
        warnings.append(f"wf84_rows_{len(rows)}_source_rows_{len(source_lookup)}")
    authority_conflicts = [
        row.get("ticker")
        for row in rows
        if row.get("authority_state") != "review_only_no_capital_or_execution_authority"
    ]
    if authority_conflicts:
        errors.append(f"authority_conflict_rows={','.join(str(ticker) for ticker in authority_conflicts[:20])}")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "purpose": "Compact cache-first chat facade over SQL-first WF84/WF85 truth production.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "wf84_sqlite": source_status(WF84_DB),
            "wf85_full_answer_rollup": source_status(WF85_FULL_ANSWER_ROLLUP),
            "trade_grade_source_freshness_gate": source_status(SOURCE_FRESHNESS_GATE),
            "trade_grade_os_freshness_runner": source_status(OS_FRESHNESS_RUNNER),
            "cache_dependency_manifest": source_status(CACHE_DEPENDENCY_MANIFEST),
            "tier_c_monitor_band_status": source_status(TIER_C_BAND_STATUS),
        },
        "summary": {
            "ticker_count": len(rows),
            "safe_cached_review_answer_count": sum(1 for row in rows if row["safe_to_answer_from_cache"]),
            "safe_material_claim_from_cache_count": sum(1 for row in rows if row["safe_for_material_claim_from_cache"]),
            "material_claim_source_open_required_count": sum(1 for row in rows if row["material_claim_requires_source_open"]),
            "refresh_or_source_open_needed_count": sum(1 for row in rows if row["needs_refresh_reason"]),
            "status_counts": dict(sorted(status_counts.items())),
            "source_open_status_counts": dict(sorted(source_open_counts.items())),
            "decision_state_counts": dict(sorted(decision_counts.items())),
            "timing_state_counts": dict(sorted(timing_counts.items())),
            "trade_readiness_state_counts": dict(sorted(trade_readiness_counts.items())),
            "authority_state_counts": dict(sorted(authority_state_counts.items())),
            "tier_c_monitor_grade_band_overlay_count": sum(1 for row in rows if row.get("tier_c_monitor_grade_band_applied")),
            "max_answer_age_hours": max_age_hours,
            "chat_route": "SQL-first truth production, cache-first chat consumption, explicit route/timing/decision/trade/authority states.",
            "next_safe_action": "Use route_readiness for lightweight chat answers; source-open and market-window proof before material recommendation, readiness, approval, or action claims.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
        },
    }
    return payload


def load_or_build_payload(max_age_hours: float = 12.0, path: Path = OUT) -> dict[str, Any]:
    """Use the written front-door packet when available, otherwise build in memory."""
    payload = as_dict(load_json_artifact(path)) if path.exists() else {}
    if payload.get("schema") == SCHEMA and payload.get("status") == "ok":
        validation = as_dict(payload.get("validation"))
        boundary = as_dict(payload.get("authority_boundary"))
        packet_age = age_hours(payload.get("generated_at_utc"))
        fresh_enough = packet_age is not None and packet_age <= max_age_hours
        if validation.get("status") == "ok" and boundary.get("cache_first_chat_consumption") is True and fresh_enough:
            return payload
    return build_payload(max_age_hours=max_age_hours)


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors = list(as_dict(payload.get("validation")).get("errors") or [])
    boundary = as_dict(payload.get("authority_boundary"))
    for key in FALSE_AUTHORITY_KEYS:
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")
    if boundary.get("sql_first_truth_production_retained") is not True:
        errors.append("sql_first_truth_production_not_retained")
    if boundary.get("cache_first_chat_consumption") is not True:
        errors.append("cache_first_chat_consumption_not_true")
    if boundary.get("source_open_required_for_material_claims") is not True:
        errors.append("source_open_material_claim_guard_not_true")
    return sorted(set(errors))


def row_by_ticker(payload: dict[str, Any], ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    for row in as_list(payload.get("rows")):
        row_dict = as_dict(row)
        if str(row_dict.get("ticker") or "").upper() == ticker:
            return row_dict
    return {}


def render_row(row: dict[str, Any]) -> str:
    if not row:
        return "ticker | status\nticker_missing | missing\n"
    answer = as_dict(row.get("answer"))
    fields = [
        ("ticker", row.get("ticker")),
        ("auto_tier", row.get("auto_tier")),
        ("routing_state", row.get("routing_state")),
        ("timing_state", row.get("timing_state")),
        ("decision_state", row.get("decision_state")),
        ("trade_readiness", row.get("trade_readiness_state")),
        ("authority", row.get("authority_state")),
        ("price", row.get("latest_price")),
        ("band", f"{row.get('entry_band_low')}-{row.get('entry_band_high')}"),
        ("stop", row.get("stop_or_invalidation")),
        ("band_status_source", row.get("band_status_source")),
        ("monitor_grade_band", f"{row.get('monitor_grade_reference_band_low')}-{row.get('monitor_grade_reference_band_high')}"),
        ("monitor_grade_stop", row.get("monitor_grade_reference_stop")),
        ("source_open", row.get("source_open_status")),
        ("answer_age_hours", answer.get("age_hours")),
        ("cache_safe", row.get("safe_to_answer_from_cache")),
        ("material_source_open", row.get("material_claim_requires_source_open")),
    ]
    return "\n".join(f"{key}: {value}" for key, value in fields) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--max-answer-age-hours", type=float, default=12.0)

    ticker_parser = sub.add_parser("ticker", help="Render one cached ticker row.")
    ticker_parser.add_argument("ticker")
    ticker_parser.add_argument("--read-only", action="store_true")
    ticker_parser.add_argument("--json", action="store_true")
    ticker_parser.add_argument("--pretty", action="store_true")

    queue_parser = sub.add_parser("queue", help="Render cache rows needing refresh or source-open.")
    queue_parser.add_argument("--read-only", action="store_true")
    queue_parser.add_argument("--limit", type=int, default=20)
    queue_parser.add_argument("--json", action="store_true")

    stale_parser = sub.add_parser("stale", help="Render stale or missing cache rows.")
    stale_parser.add_argument("--read-only", action="store_true")
    stale_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(max_age_hours=args.max_answer_age_hours) if args.write else load_or_build_payload(max_age_hours=args.max_answer_age_hours, path=out)
    if args.write:
        atomic_write_json(out, payload)

    if args.command == "ticker":
        row = row_by_ticker(payload, args.ticker)
        if args.json:
            print(json.dumps(row, indent=2, sort_keys=True))
        else:
            print(render_row(row), end="")
        return 0 if row else 1
    if args.command == "queue":
        rows = [row for row in as_list(payload.get("rows")) if as_dict(row).get("needs_refresh_reason")][: args.limit]
        print(json.dumps(rows, indent=2 if args.json else None, sort_keys=True))
        return 0
    if args.command == "stale":
        rows = [
            row for row in as_list(payload.get("rows"))
            if as_dict(as_dict(row).get("answer")).get("status") in {"missing", "stale", "missing_generated_at", "warning"}
        ]
        print(json.dumps(rows, indent=2 if args.json else None, sort_keys=True))
        return 0

    errors = validate_payload(payload) if args.validate else []
    print(json.dumps({"status": payload["status"], "out": rel(out), "summary": payload["summary"], "validation_errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
