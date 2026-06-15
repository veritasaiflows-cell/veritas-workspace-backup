#!/usr/bin/env python3
"""Build the WF84 read-only canonical finance data plane.

This creates an internal, review-only canonical packet and optional derived
SQLite lookup companion. It normalizes current WF78/finance feeder surfaces but
does not become canon, approval, portfolio, capital, paper/live, account, or
customer authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from wf84_sqlite_mutex import wf84_sqlite_mutex

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.canonical_finance_data_plane.v1"
SQLITE_SCHEMA = "veritas.canonical_finance_data_plane.sqlite.v1"
WORKFLOW_ID = "WF84"
EXPECTED_ACTIVE_TICKERS = 200
DEFAULT_REQUIRED_SOURCE_MAX_AGE_HOURS = 48
NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS = "current_price_technical_available_for_non_executing_review"

TIER_WEIGHTED_NONBLOCKING_RESOLUTION_STATES = {
    "resolved_thin_monitor_current",
    "resolved_to_deployment_readiness_review",
    "resolved_to_owner_lineage_proposal_review",
    "resolved_to_position_sizing_review",
    "resolved_to_post_close_final_quote_review",
    "resolved_to_current_technical_review",
}

DEFAULT_CONTRACT = TMP / "canonical-finance-data-plane-contract.json"
DEFAULT_PACKET = TMP / "canonical-finance-data-plane.json"
DEFAULT_VALIDATION = TMP / "canonical-finance-data-plane-validation.json"
DEFAULT_DB = TMP / "canonical-finance-data-plane.sqlite"

AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"
TIER_WEIGHTED_FRESHNESS = TMP / "wf78-tier-weighted-freshness-resolution.json"
DECISION_SYNC_SPINE = TMP / "finance-decision-sync-spine.json"
TICKER_CARD_GATE = TMP / "finance-ticker-card-refresh-gate.json"
CAPITAL_REVIEW_QUEUE = TMP / "wf78-capital-review-queue.json"
POST_CLOSE_FINAL_QUOTES = TMP / "post-close-final-quote-ledger.json"
TIER_C_BAND_STATUS = TMP / "tier-c-band-status.json"
WF78_MISSING_BAND_CONTEXT_REPAIR = TMP / "wf78-missing-band-context-repair.json"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
TICKER_CARD_DIR = TMP / "ticker-intelligence-cards"
TRADE_GRADE_FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"

ACCEPTED_SOURCE_SCHEMAS = {
    "data/finance/universe-v1.json": {"1"},
    "tmp/wf78-auto-tier-routing.json": {"veritas.wf78_auto_tier_router.v1"},
    "tmp/wf78-tier-weighted-freshness-resolution.json": {"veritas.wf78_tier_weighted_freshness_resolution.v1"},
    "tmp/finance-decision-sync-spine.json": {"veritas.finance_decision_sync_spine.v1"},
    "tmp/finance-ticker-card-refresh-gate.json": {"1"},
    "tmp/wf78-capital-review-queue.json": {"veritas.wf78_capital_review_queue.v1"},
    "tmp/post-close-final-quote-ledger.json": {"veritas.post_close_final_quote_ledger.v1"},
    "tmp/tier-c-band-status.json": {"veritas.tier_c_band_status.v1"},
    "tmp/wf78-missing-band-context-repair.json": {"veritas.wf78_missing_band_context_repair.v1"},
}

SOURCE_MAX_AGE_HOURS = {
}
DURABLE_REGISTRY_SOURCE_PATHS = {
    "data/finance/universe-v1.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "read_only_canonical_data_plane": True,
    "internal_personal_finance_infrastructure": True,
    "automated_non_capital_routing_allowed": True,
    "source_open_required_before_finance_claims": True,
    "derived_sqlite_lookup_only": True,
    "customer_or_external_delivery_allowed": False,
    "real_customer_data_allowed": False,
    "account_or_brokerage_data_required": False,
    "pii_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_FLAGS = {
    "customer_or_external_delivery_allowed",
    "real_customer_data_allowed",
    "account_or_brokerage_data_required",
    "pii_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cash_sizing_sleeve_risk_rule_mutation_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "portfolio_mutation_allowed",
    "canonical_mutation_allowed",
    "canonical_note_mutation_allowed",
    "live_trade_allowed",
    "paper_order_execution_allowed",
}

TABLE_ORDER = [
    "schema_run",
    "source_artifact",
    "security_master",
    "universe_membership",
    "routing_state_current",
    "evidence_family_status",
    "full_answer_section_context",
    "price_technical_current",
    "entry_stop_reference",
    "fundamental_snapshot",
    "analyst_snapshot",
    "earnings_catalyst",
    "official_evidence",
    "decision_queue_state",
    "validation_result",
]

PRIMARY_KEYS = {
    "schema_run": ("run_id",),
    "source_artifact": ("artifact_id",),
    "security_master": ("ticker",),
    "universe_membership": ("ticker",),
    "routing_state_current": ("ticker",),
    "evidence_family_status": ("ticker", "family_id"),
    "full_answer_section_context": ("ticker", "section_id"),
    "price_technical_current": ("ticker",),
    "entry_stop_reference": ("ticker",),
    "fundamental_snapshot": ("ticker",),
    "analyst_snapshot": ("ticker", "provider"),
    "earnings_catalyst": ("ticker",),
    "official_evidence": ("evidence_id",),
    "decision_queue_state": ("ticker",),
    "validation_result": ("run_id", "check_name"),
}

VALID_AUTO_TIERS = {"Tier A", "Tier B", "Tier C"}
VALID_AUTO_STATES = {
    "A-CHALLENGED",
    "A-READY",
    "A-WATCH",
    "B-CANDIDATE",
    "B-CHALLENGED",
    "B-VALIDATED",
    "C-CANDIDATE",
    "C-CANDIDATE-HOLD",
    "C-CANDIDATE-REPAIR",
    "C-MONITOR",
    "C-THEME-WATCH",
}
FORBIDDEN_ACTIONABILITY_TERMS = ("approved", "execute", "execution", "trade", "live", "paper_order")

FULL_ANSWER_SECTION_SOURCES = [
    ("identity", None, "universe_metadata"),
    ("thesis", "thesis", "thesis_bull_bear_entry_context"),
    ("bull_case", "bull_case", "thesis_bull_bear_entry_context"),
    ("bear_case", "bear_case", "thesis_bull_bear_entry_context"),
    ("latest_earnings", "earnings_guidance", "latest_earnings_performance"),
    ("key_financial_metrics", "financial_metrics", "key_financial_metrics"),
    ("valuation", "valuation", "valuation"),
    ("competitive_moat", "business_quality_moat", "competitive_moat"),
    ("recent_developments_catalysts", "catalyst_news_macro", "recent_developments"),
    ("analyst_consensus", None, "analyst_consensus_ratings_targets"),
    ("technical_posture", "technical_setup", "technical_posture"),
    ("sector_macro_context", "catalyst_news_macro", "current_sector_performance"),
    ("risks_counterarguments", "risk_invalidation", "risk_register"),
    ("entry_band_stop", "entry_stop_sizing", "price_band_stop"),
    ("portfolio_fit", "portfolio_fit", "portfolio_fit_concentration"),
    ("recommendation_posture", "decision_state", "recommendation_support"),
    ("authority_boundary", "authority_approval_status", "authority_boundary"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hours_between(later: datetime, earlier_text: Any) -> float | None:
    earlier = parse_utc(earlier_text)
    if earlier is None:
        return None
    return (later - earlier).total_seconds() / 3600


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def tier_weighted_blocker_counts(row: dict[str, Any]) -> tuple[int, int]:
    """Return unresolved blocker counts after WF78 tier-weighted repair has run."""
    resolution_state = row.get("resolution_state")
    if row.get("tier_weighted_resolved") and resolution_state in TIER_WEIGHTED_NONBLOCKING_RESOLUTION_STATES:
        return 0, 0
    return inum(row.get("card_missing_or_stale_count")) or 0, len(as_list(row.get("stale_families")))


def tier_weighted_resolution_is_nonblocking(row: dict[str, Any]) -> bool:
    return bool(
        row.get("tier_weighted_resolved")
        and row.get("resolution_state") in TIER_WEIGHTED_NONBLOCKING_RESOLUTION_STATES
    )


def family_row_after_tier_weighted_resolution(row: dict[str, Any], tier_weighted_row: dict[str, Any]) -> dict[str, Any]:
    """Clear stale family markers when WF78 already resolved the active freshness debt.

    The finance-state family snapshot can lag the post-close/Tier-weighted
    resolver. Without this overlay, WF85 sees stale family rows even after the
    current quote/band/stop proof has been refreshed.
    """
    out = {
        "ticker": str(row.get("ticker") or "").upper(),
        "family_id": row.get("family_id"),
        "status": row.get("status"),
        "missing_count": inum(row.get("missing_count")) or 0,
        "stale_count": inum(row.get("stale_count")) or 0,
        "source_required": bool(row.get("source_required")),
        "required_depth": "finance_state",
        "resolution_state": row.get("status"),
        "tier_weighted_resolved": False,
        "source_paths_json": row.get("source_paths_json") or "[]",
    }
    if (
        tier_weighted_resolution_is_nonblocking(tier_weighted_row)
        and out["missing_count"] == 0
        and out["stale_count"] > 0
        and str(out["status"]).startswith("covered")
    ):
        paths = as_list(parse_json_text(out["source_paths_json"], []))
        paths.append(rel(TIER_WEIGHTED_FRESHNESS))
        out.update({
            "status": "covered_by_tier_weighted_freshness_resolution",
            "stale_count": 0,
            "resolution_state": tier_weighted_row.get("resolution_state"),
            "tier_weighted_resolved": True,
            "source_paths_json": json_text(sorted(set(str(path) for path in paths if path))),
        })
    return out


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def inum(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_int(value: Any) -> int:
    return 1 if value is True or value == 1 else 0


def classify_band_status(price: Any, low: Any, high: Any, stop: Any) -> str | None:
    price_f = fnum(price)
    if price_f is None:
        return None
    stop_f = fnum(stop)
    low_f = fnum(low)
    high_f = fnum(high)
    if stop_f is not None and price_f < stop_f:
        return "BELOW_STOP"
    if low_f is not None and price_f < low_f:
        return "BELOW_BAND"
    if high_f is not None and price_f > high_f:
        return "ABOVE_BAND"
    if low_f is not None and high_f is not None:
        return "IN_BAND"
    return None


def load_json(path: Path, default: Any = None) -> Any:
    data = load_json_artifact(path)
    return default if data is None else data


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def source_artifact_id(path: Path) -> str:
    name = path.stem.replace("-", "_").replace(".", "_")
    return f"src_{name}"


def source_meta(path: Path, *, role: str, source_type: str, required: bool, rank: int) -> dict[str, Any]:
    payload = load_json(path, {}) if source_type == "json" else {}
    sqlite_exists = source_type == "sqlite" and path.exists()
    validation = as_dict(payload.get("validation")) if isinstance(payload, dict) else {}
    return {
        "artifact_id": source_artifact_id(path),
        "path": rel(path),
        "role": role,
        "source_type": source_type,
        "required_for_mvp": required,
        "exists_on_disk": path.exists(),
        "generated_at_utc": payload.get("generated_at_utc") if isinstance(payload, dict) else None,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if path.exists() else None,
        "sha256": sha256_file(path),
        "schema": payload.get("schema") or payload.get("schema_version") if isinstance(payload, dict) else None,
        "status": ("ok" if sqlite_exists else "missing") if source_type == "sqlite" else payload.get("status") if isinstance(payload, dict) else None,
        "validation_status": ("ok" if sqlite_exists else "missing") if source_type == "sqlite" else validation.get("status"),
        "source_rank": rank,
        "raw_summary_json": json_text({
            "summary": payload.get("summary") if isinstance(payload, dict) else None,
            "size_bytes": path.stat().st_size if path.exists() else None,
            "sqlite_source_status": "exists_validated_by_wf84_builder" if sqlite_exists else None,
        }),
    }


def feeder_sources() -> list[dict[str, Any]]:
    return [
        source_meta(UNIVERSE, role="universe/security base feed", source_type="json", required=True, rank=10),
        source_meta(AUTO_ROUTER, role="primary non-capital tier/routing feed", source_type="json", required=True, rank=20),
        source_meta(FINANCE_STATE_DB, role="current-state SQL feeder", source_type="sqlite", required=True, rank=30),
        source_meta(TIER_WEIGHTED_FRESHNESS, role="tier-weighted evidence/freshness feed", source_type="json", required=True, rank=40),
        source_meta(DECISION_SYNC_SPINE, role="decision-readiness spine feed", source_type="json", required=False, rank=50),
        source_meta(TICKER_CARD_GATE, role="ticker-card repair/staleness feed", source_type="json", required=True, rank=60),
        source_meta(CAPITAL_REVIEW_QUEUE, role="non-executing owner-review queue feed", source_type="json", required=False, rank=70),
        source_meta(POST_CLOSE_FINAL_QUOTES, role="review-only closed-market quote overlay", source_type="json", required=False, rank=80),
        source_meta(TIER_C_BAND_STATUS, role="Tier C monitor-grade price/technical fallback", source_type="json", required=False, rank=90),
        source_meta(WF78_MISSING_BAND_CONTEXT_REPAIR, role="Tier A/B review-only missing band-context repair feed", source_type="json", required=False, rank=95),
    ]


def finance_rows(table: str) -> list[dict[str, Any]]:
    if not FINANCE_STATE_DB.exists():
        return []
    with connect_ro(FINANCE_STATE_DB) as conn:
        return [dict(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY 1')]


def index_by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def recursive_forbidden_true(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_FLAGS and child is True:
                found.append(child_path)
            found.extend(recursive_forbidden_true(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(recursive_forbidden_true(child, f"{path}[{index}]"))
    return found


def duplicate_keys(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[str]:
    seen: set[tuple[Any, ...]] = set()
    duplicates: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row.get(name) for name in keys)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return [json_text(dict(zip(keys, key, strict=True))) for key in sorted(duplicates)]


def feeder_authority_violations() -> list[str]:
    violations: list[str] = []
    for path in (UNIVERSE, AUTO_ROUTER, TIER_WEIGHTED_FRESHNESS, DECISION_SYNC_SPINE, TICKER_CARD_GATE, CAPITAL_REVIEW_QUEUE, WF78_MISSING_BAND_CONTEXT_REPAIR):
        if not path.exists():
            continue
        payload = load_json(path, {})
        for item in recursive_forbidden_true(payload, rel(path)):
            violations.append(item)
    for table in (
        "universe",
        "ticker_tier",
        "latest_price_technical",
        "entry_stop_reference",
        "fundamental_snapshot",
        "analyst_snapshot",
        "earnings_calendar",
        "official_evidence_index",
        "promotion_signals",
    ):
        for index, row in enumerate(finance_rows(table)):
            for item in recursive_forbidden_true(row, f"{rel(FINANCE_STATE_DB)}.{table}[{index}]"):
                violations.append(item)
    return violations


def full_answer_path(ticker: str) -> Path:
    return TRADE_GRADE_FULL_ANSWER_DIR / f"{ticker}.json"


def ticker_card_path(ticker: str) -> Path:
    return TICKER_CARD_DIR / f"{ticker}.current.json"


def section_status(value: Any) -> str:
    if isinstance(value, dict):
        status = value.get("status") or value.get("parse_status")
        if status:
            return str(status)
        return "available" if value else "missing"
    if isinstance(value, list):
        return "available" if value else "missing"
    return "available" if value not in (None, "") else "missing"


def section_presence_score(value: Any) -> float:
    if isinstance(value, dict):
        if not value:
            return 0.0
        status = str(value.get("status") or value.get("parse_status") or "").lower()
        if status in {"missing", "unavailable", "source_open_required"}:
            substantive = [
                child for key, child in value.items()
                if key not in {"status", "parse_status"} and child not in (None, "", [], {})
            ]
            if not substantive:
                return 0.0
        present = sum(1 for child in value.values() if child not in (None, "", [], {}))
        return round(present / max(len(value), 1), 3)
    if isinstance(value, list):
        return 1.0 if value else 0.0
    return 1.0 if value not in (None, "") else 0.0


def source_paths_from_full_answer_and_card(full_answer: dict[str, Any], card: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for row in as_list(full_answer.get("source_lineage")):
        path = as_dict(row).get("path")
        if path:
            paths.append(str(path).replace("\\", "/"))
    for row in as_list(card.get("source_artifacts")):
        path = as_dict(row).get("path")
        if path:
            paths.append(str(path).replace("\\", "/"))
    return sorted(set(paths))


def assembler_section_raw(full_answer: dict[str, Any], assembler_section_id: str | None) -> Any:
    if not assembler_section_id:
        return {}
    section = as_dict(as_dict(full_answer.get("sections")).get(assembler_section_id))
    return section.get("raw") if section else {}


def parse_json_text(value: Any, default: Any = None) -> Any:
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def technical_posture_from_price_row(price_row: dict[str, Any]) -> dict[str, Any]:
    """Return source-backed technical posture or an explicit repair state."""
    raw = as_dict(parse_json_text(price_row.get("raw_json"), {}))
    technical = dict(as_dict(raw.get("technical_posture")))
    status = price_row.get("technical_status")
    summary = price_row.get("technical_summary")
    if section_presence_score(technical) == 0.0 and not (status or summary):
        return {}
    if status:
        technical["status"] = status
    if summary:
        technical["summary"] = summary
    technical["source_path"] = price_row.get("source_path") or price_row.get("price_source") or rel(FINANCE_STATE_DB)
    technical["repair_required"] = status in {"missing_required_refresh", "stale_required_refresh"}
    technical["source_open_required_before_material_claims"] = True
    return technical


def review_price_context_from_price_row(price_row: dict[str, Any]) -> dict[str, Any]:
    """Derive non-executing review price freshness from the current card row."""
    raw = as_dict(parse_json_text(price_row.get("raw_json"), {}))
    price_band_stop = as_dict(raw.get("price_band_stop"))
    technical = as_dict(raw.get("technical_posture"))
    latest_price = fnum(price_row.get("latest_known_price"))
    post_close = as_dict(price_band_stop.get("post_close_final_quote"))
    if latest_price is None:
        latest_price = fnum(price_band_stop.get("latest_known_price") or technical.get("latest_close"))
    if post_close.get("market_date") and latest_price is not None:
        return {
            "latest_price": latest_price,
            "quote_time_utc": post_close.get("retrieved_at_utc"),
            "market_date": post_close.get("market_date"),
            "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review",
            "price_source": price_row.get("price_source") or price_band_stop.get("price_source"),
        }
    if technical.get("data_date") and latest_price is not None:
        return {
            "latest_price": latest_price,
            "quote_time_utc": None,
            "market_date": technical.get("data_date"),
            "quote_freshness_status": NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS,
            "price_source": price_row.get("price_source") or price_band_stop.get("price_source"),
        }
    return {
        "latest_price": latest_price,
        "quote_time_utc": None,
        "market_date": None,
        "quote_freshness_status": None,
        "price_source": price_row.get("price_source") or price_band_stop.get("price_source"),
    }


def price_row_with_tier_c_monitor_context(price_row: dict[str, Any], monitor_row: dict[str, Any]) -> dict[str, Any]:
    """Fill missing price/technical fields from Tier C monitor-grade context."""
    if monitor_row.get("technical_input_status") != "ok" or fnum(monitor_row.get("latest_price")) is None:
        return price_row
    out = dict(price_row)
    raw = as_dict(parse_json_text(out.get("raw_json"), {}))
    technical = as_dict(raw.get("technical_posture"))
    monitor_technical = {
        "status": "monitor_grade_current",
        "monitor_grade_only": True,
        "decision_grade": False,
        "latest_close": fnum(monitor_row.get("latest_price")),
        "data_date": monitor_row.get("data_date"),
        "band_status": monitor_row.get("band_status"),
        "trend_stack": monitor_row.get("trend_stack"),
        "confidence": monitor_row.get("confidence"),
        "reference_source": monitor_row.get("reference_source"),
        "source_path": rel(TIER_C_BAND_STATUS),
        "source_open_required_before_material_claims": True,
    }
    out["latest_known_price"] = out.get("latest_known_price") if fnum(out.get("latest_known_price")) is not None else monitor_technical["latest_close"]
    out["price_source"] = out.get("price_source") or rel(TIER_C_BAND_STATUS)
    out["band_status"] = out.get("band_status") or monitor_row.get("band_status")
    out["technical_status"] = out.get("technical_status") or "monitor_grade_current"
    out["technical_summary"] = out.get("technical_summary") or (
        f"Tier C monitor-grade {monitor_row.get('trend_stack')} / {monitor_row.get('band_status')}"
    )
    if section_presence_score(technical) == 0.0:
        raw["technical_posture"] = monitor_technical
    raw["tier_c_monitor_context"] = monitor_row
    out["raw_json"] = json_text(raw)
    return out


def full_answer_section_rows(ticker: str, context: dict[str, Any], full_answer: dict[str, Any], card: dict[str, Any], price_row: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    full_answer_exists = bool(full_answer)
    card_exists = bool(card)
    price_row = price_row or {}
    answer_path = rel(full_answer_path(ticker))
    card_path = rel(ticker_card_path(ticker))
    shared_sources = source_paths_from_full_answer_and_card(full_answer, card)
    generated_at = full_answer.get("generated_at_utc") or card.get("generated_at_utc")
    rows_out: list[dict[str, Any]] = []
    for section_id, assembler_section_id, card_key in FULL_ANSWER_SECTION_SOURCES:
        if section_id == "identity":
            value = {
                "ticker": ticker,
                "name": context.get("name"),
                "instrument_type": context.get("instrument_type"),
                "sector": context.get("sector"),
                "auto_tier": context.get("auto_tier"),
                "auto_state": context.get("auto_state"),
            }
            source_kind = "wf84_core"
            source_paths = [rel(AUTO_ROUTER), rel(FINANCE_STATE_DB)]
        elif assembler_section_id:
            value = assembler_section_raw(full_answer, assembler_section_id)
            source_kind = "wf85_full_answer_assembler" if full_answer_exists else "missing"
            source_paths = [answer_path, *shared_sources] if full_answer_exists else []
        elif card_key and card_key in card:
            value = card.get(card_key)
            source_kind = "ticker_intelligence_card"
            source_paths = [card_path, *shared_sources]
        else:
            value = {}
            source_kind = "missing"
            source_paths = [path for path in [answer_path if full_answer_exists else None, card_path if card_exists else None] if path]
        if section_presence_score(value) == 0.0 and card_key and card_key in card and source_kind in {"wf85_full_answer_assembler", "missing"}:
            value = card.get(card_key)
            source_kind = "ticker_intelligence_card"
            source_paths = [card_path, *shared_sources]
        if section_id == "technical_posture" and section_presence_score(value) == 0.0:
            technical_repair_state = technical_posture_from_price_row(price_row)
            if technical_repair_state:
                value = technical_repair_state
                source_kind = "price_technical_current_repair_state"
                source_paths = [
                    path
                    for path in [
                        rel(FINANCE_STATE_DB),
                        str(price_row.get("source_path") or "").replace("\\", "/"),
                        card_path if card_exists else None,
                    ]
                    if path
                ]
        rows_out.append({
            "ticker": ticker,
            "section_id": section_id,
            "section_status": section_status(value),
            "source_kind": source_kind,
            "freshness_status": "source_open_required" if source_kind == "missing" else "mapped",
            "source_paths_json": json_text(sorted(set(source_paths))),
            "source_open_required": True,
            "field_presence_score": section_presence_score(value),
            "value_hash": hashlib.sha256(json_text(value).encode("utf-8")).hexdigest(),
            "generated_at_utc": generated_at,
            "raw_json": json_text(value),
        })
    return rows_out


def check_source_schemas(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for row in source_rows:
        accepted = ACCEPTED_SOURCE_SCHEMAS.get(row["path"])
        if not accepted:
            continue
        observed = str(row.get("schema"))
        if observed not in accepted:
            mismatches.append({
                "path": row["path"],
                "observed": observed,
                "accepted": sorted(accepted),
            })
    return mismatches


def stale_required_sources(source_rows: list[dict[str, Any]], generated_at_utc: str) -> list[dict[str, Any]]:
    generated_at = parse_utc(generated_at_utc) or datetime.now(timezone.utc)
    stale: list[dict[str, Any]] = []
    for row in source_rows:
        if not row.get("required_for_mvp") or not row.get("exists_on_disk"):
            continue
        if row["path"] in DURABLE_REGISTRY_SOURCE_PATHS:
            continue
        timestamp = row.get("generated_at_utc") or row.get("mtime_utc")
        age_hours = hours_between(generated_at, timestamp)
        max_age = SOURCE_MAX_AGE_HOURS.get(row["path"], DEFAULT_REQUIRED_SOURCE_MAX_AGE_HOURS)
        if age_hours is None or age_hours > max_age:
            stale.append({
                "path": row["path"],
                "timestamp": timestamp,
                "age_hours": round(age_hours, 2) if age_hours is not None else None,
                "max_age_hours": max_age,
            })
    return stale


def durable_registry_findings(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    by_path = {str(row.get("path")): row for row in source_rows}
    universe_source = by_path.get(rel(UNIVERSE))
    universe = as_dict(load_json(UNIVERSE, {}))
    summary = as_dict(universe.get("summary"))
    authority = as_dict(universe.get("authority_boundary"))
    entries = as_list(universe.get("entries"))

    if not universe_source or not universe_source.get("exists_on_disk"):
        findings.append({"path": rel(UNIVERSE), "reason": "missing_durable_universe_registry"})
        return findings
    if universe.get("artifact_type") != "wf78_finance_universe_registry":
        findings.append({"path": rel(UNIVERSE), "reason": "unexpected_artifact_type", "observed": universe.get("artifact_type")})
    if summary.get("active_ticker_count") != EXPECTED_ACTIVE_TICKERS:
        findings.append({
            "path": rel(UNIVERSE),
            "reason": "active_ticker_count_mismatch",
            "expected": EXPECTED_ACTIVE_TICKERS,
            "observed": summary.get("active_ticker_count"),
        })
    if len(entries) != EXPECTED_ACTIVE_TICKERS:
        findings.append({
            "path": rel(UNIVERSE),
            "reason": "entry_count_mismatch",
            "expected": EXPECTED_ACTIVE_TICKERS,
            "observed": len(entries),
        })
    if authority.get("owner_approval_inferred") is not False:
        findings.append({"path": rel(UNIVERSE), "reason": "owner_approval_boundary_not_false"})
    if not universe_source.get("sha256"):
        findings.append({"path": rel(UNIVERSE), "reason": "missing_semantic_digest"})
    return findings


def build_packet() -> dict[str, Any]:
    generated = utc_now()
    run_id = f"wf84-{generated.replace(':', '').replace('-', '').replace('Z', 'Z')}"
    auto_router = as_dict(load_json(AUTO_ROUTER, {}))
    router_rows = [row for row in as_list(auto_router.get("rows")) if isinstance(row, dict)]
    router_by_ticker = index_by_ticker(router_rows)
    summary = as_dict(auto_router.get("summary"))

    universe_rows = finance_rows("universe")
    family_rows = finance_rows("ticker_family_status")
    price_rows = index_by_ticker(finance_rows("latest_price_technical"))
    entry_rows = index_by_ticker(finance_rows("entry_stop_reference"))
    fundamental_rows = index_by_ticker(finance_rows("fundamental_snapshot"))
    analyst_rows = finance_rows("analyst_snapshot")
    earnings_rows = index_by_ticker(finance_rows("earnings_calendar"))
    evidence_rows = finance_rows("official_evidence_index")
    promotion_rows = index_by_ticker(finance_rows("promotion_signals"))

    tier_weighted = as_dict(load_json(TIER_WEIGHTED_FRESHNESS, {}))
    tier_weighted_by_ticker = index_by_ticker([row for row in as_list(tier_weighted.get("rows")) if isinstance(row, dict)])
    spine = as_dict(load_json(DECISION_SYNC_SPINE, {}))
    spine_by_ticker = index_by_ticker([row for row in as_list(spine.get("rows")) if isinstance(row, dict)])
    capital_queue = as_dict(load_json(CAPITAL_REVIEW_QUEUE, {}))
    capital_by_ticker = index_by_ticker([row for row in as_list(capital_queue.get("rows")) if isinstance(row, dict)])
    post_close_quotes = as_dict(load_json(POST_CLOSE_FINAL_QUOTES, {}))
    post_close_by_ticker = index_by_ticker([row for row in as_list(post_close_quotes.get("rows")) if isinstance(row, dict)])
    tier_c_band = as_dict(load_json(TIER_C_BAND_STATUS, {}))
    tier_c_band_by_ticker = index_by_ticker([row for row in as_list(tier_c_band.get("rows")) if isinstance(row, dict)])
    missing_band_repair = as_dict(load_json(WF78_MISSING_BAND_CONTEXT_REPAIR, {}))
    missing_band_repair_by_ticker = index_by_ticker([row for row in as_list(missing_band_repair.get("rows")) if isinstance(row, dict)])
    sources = feeder_sources()
    src_auto = source_artifact_id(AUTO_ROUTER)
    src_finance = source_artifact_id(FINANCE_STATE_DB)
    src_freshness = source_artifact_id(TIER_WEIGHTED_FRESHNESS)
    src_spine = source_artifact_id(DECISION_SYNC_SPINE)
    src_capital = source_artifact_id(CAPITAL_REVIEW_QUEUE)
    src_post_close = source_artifact_id(POST_CLOSE_FINAL_QUOTES)
    src_tier_c_band = source_artifact_id(TIER_C_BAND_STATUS)
    src_missing_band_repair = source_artifact_id(WF78_MISSING_BAND_CONTEXT_REPAIR)

    security_master: list[dict[str, Any]] = []
    universe_membership: list[dict[str, Any]] = []
    routing_state_current: list[dict[str, Any]] = []
    evidence_family_status: list[dict[str, Any]] = []
    full_answer_section_context: list[dict[str, Any]] = []
    price_technical_current: list[dict[str, Any]] = []
    entry_stop_reference: list[dict[str, Any]] = []
    fundamental_snapshot: list[dict[str, Any]] = []
    analyst_snapshot: list[dict[str, Any]] = []
    earnings_catalyst: list[dict[str, Any]] = []
    official_evidence: list[dict[str, Any]] = []
    decision_queue_state: list[dict[str, Any]] = []

    for row in router_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        urow = next((item for item in universe_rows if str(item.get("ticker") or "").upper() == ticker), {})
        p = price_rows.get(ticker, {})
        e = entry_rows.get(ticker, {})
        f = fundamental_rows.get(ticker, {})
        earn = earnings_rows.get(ticker, {})
        prom = promotion_rows.get(ticker, {})
        tw = tier_weighted_by_ticker.get(ticker, {})
        tier_c_monitor = tier_c_band_by_ticker.get(ticker, {})
        band_repair = missing_band_repair_by_ticker.get(ticker, {})
        band_repair_band = as_dict(band_repair.get("band"))
        band_repair_ready = band_repair.get("repair_status") in {
            "ready_for_decision_grade_band_context",
            "ready_for_position_sizing_repair_recheck",
        }
        ds = spine_by_ticker.get(ticker, {})
        cq = capital_by_ticker.get(ticker, {})
        post_close = post_close_by_ticker.get(ticker, {})
        p_effective = price_row_with_tier_c_monitor_context(p, tier_c_monitor)
        full_answer = as_dict(load_json(full_answer_path(ticker), {}))
        card = as_dict(load_json(ticker_card_path(ticker), {}))
        full_answer_context = {
            "ticker": ticker,
            "name": row.get("name") or urow.get("name"),
            "instrument_type": row.get("instrument_type") or urow.get("instrument_type"),
            "sector": row.get("sector") or urow.get("sector"),
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
        }
        full_answer_section_context.extend(full_answer_section_rows(ticker, full_answer_context, full_answer, card, p_effective))

        security_master.append({
            "ticker": ticker,
            "name": row.get("name") or urow.get("name"),
            "instrument_type": row.get("instrument_type") or urow.get("instrument_type"),
            "sector": row.get("sector") or urow.get("sector"),
            "industry": urow.get("industry"),
            "yfinance_symbol": ticker,
            "sec_cik": None,
            "company_ir_url": None,
            "active": True,
        })
        universe_membership.append({
            "ticker": ticker,
            "universe_scope": urow.get("universe_scope") or "active_internal_universe",
            "legacy_universe_tier": row.get("legacy_universe_tier"),
            "legacy_monitoring_role": row.get("legacy_monitoring_role"),
            "production_answer_path_member": bool(urow.get("production_answer_path_member")),
            "thin_monitor_row": bool(urow.get("thin_monitor_row")),
            "decision_grade_eligible": bool(urow.get("decision_grade_eligible")),
            "promotion_required_before_action": bool(urow.get("promotion_required_before_action")),
            "source_open_required": bool(urow.get("source_open_required", True)),
            "owner_note_path": urow.get("owner_note_path"),
            "raw_json": json_text(urow or row),
        })
        routing_state_current.append({
            "ticker": ticker,
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "route_priority": inum(row.get("route_priority")),
            "route_reason": row.get("route_reason"),
            "data_confidence_rating": row.get("data_confidence_rating"),
            "fundamentals_confidence": row.get("fundamentals_confidence"),
            "tier_a_confidence_status": row.get("tier_a_confidence_status"),
            "tier_a_confidence_promotion_effect": row.get("tier_a_confidence_promotion_effect"),
            "critical_data_conflict_count": inum(row.get("critical_data_conflict_count")) or 0,
            "requires_separate_capital_or_execution_approval": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "would_mutate_universe": False,
            "source_artifact_id": src_auto,
        })
        price_context = review_price_context_from_price_row(p_effective)
        latest_price = fnum(price_context.get("latest_price"))
        price_source_artifact = src_tier_c_band if price_context.get("price_source") == rel(TIER_C_BAND_STATUS) else src_finance if latest_price is not None else src_spine
        if latest_price is None:
            latest_price = fnum(ds.get("current_price"))
            price_source_artifact = src_spine
        if latest_price is None:
            latest_price = fnum(cq.get("current_price"))
            price_source_artifact = src_capital if latest_price is not None else src_finance
        if latest_price is None and band_repair_ready:
            latest_price = fnum(band_repair.get("current_price"))
            price_source_artifact = src_missing_band_repair if latest_price is not None else price_source_artifact
            if latest_price is not None:
                quote_time_utc = missing_band_repair.get("generated_at_utc")
                market_date = band_repair.get("price_data_date") or band_repair_band.get("source_timestamp")
                quote_freshness_status = NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS
        post_close_available = post_close.get("status") == "ok" and fnum(post_close.get("close")) is not None
        quote_time_utc = price_context.get("quote_time_utc") or (as_dict(cq.get("quote")).get("timestamp_utc") if isinstance(cq.get("quote"), dict) else None)
        market_date = price_context.get("market_date") or (as_dict(cq.get("quote")).get("market_date") if isinstance(cq.get("quote"), dict) else None)
        quote_freshness_status = price_context.get("quote_freshness_status") or cq.get("quote_freshness_status") or "unknown"
        if band_repair_ready and latest_price is not None and not market_date:
            quote_time_utc = missing_band_repair.get("generated_at_utc")
            market_date = band_repair.get("price_data_date") or band_repair_band.get("source_timestamp")
            quote_freshness_status = NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS
        if post_close_available:
            latest_price = fnum(post_close.get("close"))
            price_source_artifact = src_post_close
            quote_time_utc = post_close.get("retrieved_at_utc")
            market_date = post_close.get("market_date")
            quote_freshness_status = "post_close_final_quote_available_for_non_executing_review"
        # Entry/stop reference rows are owner/WF72-backed; decision-spine values
        # are fallback context only and must not override the reference table.
        entry_band_low = fnum(e.get("entry_band_low") if e.get("entry_band_low") is not None else ds.get("entry_band_low"))
        entry_band_high = fnum(e.get("entry_band_high") if e.get("entry_band_high") is not None else ds.get("entry_band_high"))
        stop_or_invalidation = fnum(e.get("stop_or_invalidation") if e.get("stop_or_invalidation") is not None else ds.get("stop_or_invalidation"))
        if band_repair_ready:
            entry_band_low = entry_band_low if entry_band_low is not None else fnum(band_repair_band.get("entry_band_low"))
            entry_band_high = entry_band_high if entry_band_high is not None else fnum(band_repair_band.get("entry_band_high"))
            stop_or_invalidation = stop_or_invalidation if stop_or_invalidation is not None else fnum(band_repair_band.get("stop_or_invalidation"))
        source_band_status = ds.get("band_status") or cq.get("current_band_status") or p.get("band_status")
        if not source_band_status and band_repair_ready:
            source_band_status = band_repair.get("fresh_band_status") or band_repair_band.get("band_status")
        computed_band_status = classify_band_status(latest_price, entry_band_low, entry_band_high, stop_or_invalidation)
        price_technical_current.append({
            "ticker": ticker,
            "latest_known_price": latest_price,
            "price_source": rel(POST_CLOSE_FINAL_QUOTES) if post_close_available else rel(WF78_MISSING_BAND_CONTEXT_REPAIR) if price_source_artifact == src_missing_band_repair else price_context.get("price_source") or p_effective.get("price_source") or cq.get("quote_freshness_status"),
            "quote_time_utc": quote_time_utc,
            "market_date": market_date,
            "band_status": computed_band_status or source_band_status,
            "technical_status": p_effective.get("technical_status"),
            "technical_summary": p_effective.get("technical_summary"),
            "fresh_quote_required": bool(p.get("fresh_quote_required") or cq.get("requires_fresh_quote_band_stop_before_deployment_review")),
            "quote_freshness_status": quote_freshness_status,
            "source_artifact_id": price_source_artifact,
            "raw_json": json_text({
                "finance_state": p_effective,
                "decision_spine": ds,
                "capital_queue": cq,
                "post_close_final_quote": post_close if post_close_available else None,
                "missing_band_context_repair": band_repair if band_repair_ready else None,
                "price_context": price_context,
                "source_band_status": source_band_status,
                "computed_band_status": computed_band_status,
            }),
        })
        entry_stop_reference.append({
            "ticker": ticker,
            "entry_band_low": entry_band_low,
            "entry_band_high": entry_band_high,
            "stop_or_invalidation": stop_or_invalidation,
            "band_source": e.get("band_source") or band_repair_band.get("band_source") or "unknown",
            "stop_source": e.get("stop_source") or band_repair_band.get("stop_source"),
            "freshness_status": "fresh_review_context" if band_repair_ready else e.get("freshness_status") or "unknown",
            "validation_status": "ok" if band_repair_ready else e.get("validation_status") or "unknown",
            "owner_note_path": e.get("owner_note_path"),
            "source_artifact_path": e.get("source_artifact_path") or (rel(WF78_MISSING_BAND_CONTEXT_REPAIR) if band_repair_ready else None),
            "source_artifact_hash": e.get("source_artifact_hash") or (sha256_file(WF78_MISSING_BAND_CONTEXT_REPAIR) if band_repair_ready else None),
            "source_timestamp": e.get("source_timestamp") or (band_repair_band.get("source_timestamp") if band_repair_ready else None),
            "authority_boundary": "review_only_reference_no_capital_or_execution_approval",
            "raw_json": json_text({"finance_state": e, "decision_spine": ds, "missing_band_context_repair": band_repair if band_repair_ready else None}),
        })
        fundamental_snapshot.append({
            "ticker": ticker,
            "period_end": None,
            "period_age_days": None,
            "data_quality": f.get("data_quality") or f.get("valuation_status") or "unknown",
            "valuation_status": f.get("valuation_status"),
            "key_metrics_status": f.get("key_metrics_status"),
            "latest_earnings_status": f.get("latest_earnings_status"),
            "sec_reconciliation_status": None,
            "sec_conflicts_json": "[]",
            "company_ir_reconciliation_status": None,
            "capital_allocation_quality": None,
            "source_path": f.get("source_path") or rel(FINANCE_STATE_DB),
            "raw_json": f.get("raw_json") or json_text(f),
        })
        earnings_catalyst.append({
            "ticker": ticker,
            "latest_earnings_status": earn.get("latest_earnings_status"),
            "latest_period_end": None,
            "next_earnings_date": earn.get("next_earnings_date"),
            "days_to_earnings": None,
            "earnings_date_confirmed": False,
            "post_earnings_review_confirmed": False,
            "catalyst_status": earn.get("catalyst_status"),
            "source_path": earn.get("source_path") or rel(FINANCE_STATE_DB),
            "raw_json": earn.get("raw_json") or json_text(earn),
        })
        decision_queue_state.append({
            "ticker": ticker,
            "primary_state": ds.get("primary_state") or cq.get("queue_state") or prom.get("recommendation_posture_key") or "monitor",
            "states_json": json_text(ds.get("states") or []),
            "recommendation_posture_key": prom.get("recommendation_posture_key"),
            "actionability": prom.get("actionability") or "review_only",
            "queue_state": ds.get("primary_state") or cq.get("queue_state") or "monitor",
            "rank_score": fnum(cq.get("rank_score")),
            "gate_verdict": ds.get("promotion_gate_verdict"),
            "gate_vetoes_json": json_text(ds.get("promotion_gate_vetoes") or []),
            "owner_card_path": ds.get("owner_card_path") or cq.get("owner_card_path"),
            "wf67_request_path": ds.get("wf67_request_path"),
            "wf67_request_generation_status": ds.get("wf67_request_generation_status"),
            "blockers_json": json_text(ds.get("blockers") or cq.get("blockers") or []),
            "warnings_json": json_text(ds.get("warnings") or cq.get("cautions") or []),
            "owner_action_required": bool(ds.get("owner_action_required") or cq.get("owner_action_required")),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
        tier_missing_count, tier_stale_count = tier_weighted_blocker_counts(tw)
        evidence_family_status.append({
            "ticker": ticker,
            "family_id": "tier_weighted_freshness",
            "status": tw.get("resolution_state") or "unknown",
            "missing_count": tier_missing_count,
            "stale_count": tier_stale_count,
            "source_required": True,
            "required_depth": tw.get("required_depth") or "unknown",
            "resolution_state": tw.get("resolution_state"),
            "tier_weighted_resolved": bool(tw.get("tier_weighted_resolved")),
            "source_paths_json": json_text([rel(TIER_WEIGHTED_FRESHNESS)]),
        })

    for row in family_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker in router_by_ticker:
            evidence_family_status.append(
                family_row_after_tier_weighted_resolution(row, tier_weighted_by_ticker.get(ticker, {}))
            )
    for row in analyst_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker in router_by_ticker:
            analyst_snapshot.append({
                "ticker": ticker,
                "provider": "finance_state",
                "status": row.get("status"),
                "accessed_at_utc": None,
                "consensus_rating": None,
                "rating_summary": row.get("rating_summary"),
                "average_target": None,
                "median_target": None,
                "implied_upside_downside_pct": None,
                "confidence": None,
                "manual_review_required": row.get("status") not in {"ok", "fresh", "available"},
                "source_url": row.get("source_path"),
                "raw_json": row.get("raw_json") or json_text(row),
            })
    for row in evidence_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker in router_by_ticker:
            official_evidence.append({
                "evidence_id": row.get("id") or f"{ticker}:{row.get('evidence_family')}",
                "ticker": ticker,
                "evidence_family": row.get("evidence_family"),
                "status": row.get("status"),
                "source_url": None,
                "source_section": None,
                "period": None,
                "manual_capture_required": row.get("status") not in {"ok", "available", "registered"},
                "inferred": False,
                "source_open_required": bool(row.get("source_open_required")),
                "source_path": row.get("source_path"),
                "raw_json": row.get("raw_json") or json_text(row),
            })

    tables = {
        "schema_run": [{
            "run_id": run_id,
            "schema_version": SCHEMA,
            "generated_at_utc": generated,
            "local_market_date": datetime.now().date().isoformat(),
            "status": "pending_validation",
            "builder_version": "canonical_finance_data_plane.py:v1",
            "authority_boundary_json": json_text(AUTHORITY_BOUNDARY),
            "validation_status": "pending_validation",
        }],
        "source_artifact": sources,
        "security_master": sorted(security_master, key=lambda r: r["ticker"]),
        "universe_membership": sorted(universe_membership, key=lambda r: r["ticker"]),
        "routing_state_current": sorted(routing_state_current, key=lambda r: r["ticker"]),
        "evidence_family_status": sorted(evidence_family_status, key=lambda r: (r["ticker"], str(r["family_id"]))),
        "full_answer_section_context": sorted(full_answer_section_context, key=lambda r: (r["ticker"], r["section_id"])),
        "price_technical_current": sorted(price_technical_current, key=lambda r: r["ticker"]),
        "entry_stop_reference": sorted(entry_stop_reference, key=lambda r: r["ticker"]),
        "fundamental_snapshot": sorted(fundamental_snapshot, key=lambda r: r["ticker"]),
        "analyst_snapshot": sorted(analyst_snapshot, key=lambda r: (r["ticker"], r["provider"])),
        "earnings_catalyst": sorted(earnings_catalyst, key=lambda r: r["ticker"]),
        "official_evidence": sorted(official_evidence, key=lambda r: str(r["evidence_id"])),
        "decision_queue_state": sorted(decision_queue_state, key=lambda r: r["ticker"]),
        "validation_result": [],
    }
    context = {
        "generated_at_utc": generated,
        "router_tickers": sorted(router_by_ticker),
        "finance_universe_tickers": sorted(str(row.get("ticker") or "").upper() for row in universe_rows if row.get("ticker")),
        "tier_weighted_tickers": sorted(tier_weighted_by_ticker),
        "decision_spine_tickers": sorted(spine_by_ticker),
    }
    validation = validate_tables(tables, summary, context)
    for check in validation["checks"]:
        check["run_id"] = run_id
    tables["schema_run"][0]["status"] = validation["status"]
    tables["schema_run"][0]["validation_status"] = validation["status"]
    tables["validation_result"] = validation["checks"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated,
        "workflow_id": WORKFLOW_ID,
        "status": validation["status"],
        "purpose": "Internal review-only canonical finance data plane for Randall's personal trade-grade OS.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_contract": {
            "wf78_feeds_this_surface": True,
            "json_packet_is_primary_rebuild_proof": True,
            "sqlite_companion_is_derived_lookup_only": True,
            "material_finance_claims_require_source_open_context": True,
        },
        "summary": validation["summary"],
        "tables": tables,
        "decision_grade_views": {
            "review_queue_view": "v_current_decision_overview",
            "owner_action_view": "v_owner_action_queue",
            "truth_boundary_view": "v_authority_boundary_false",
        },
        "validation": validation,
        "stop_lines": [
            "No customer/account/PII/suitability/brokerage schema or external delivery.",
            "No canon/portfolio/cash/sizing/risk-rule mutation.",
            "No capital deployment, paper/live order, brokerage/account action, money movement, or owner approval inference.",
            "SQLite companion is rebuildable lookup proof only and never approval authority.",
        ],
    }


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any, *, severity: str = "critical") -> None:
    checks.append({
        "run_id": "current",
        "check_name": name,
        "status": "ok" if ok else "blocked",
        "severity": "info" if ok else severity,
        "detail_json": json_text(detail),
        "source_artifact_id": None,
    })


def validate_tables(tables: dict[str, list[dict[str, Any]]], router_summary: dict[str, Any], context: dict[str, list[str]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    counts = {name: len(tables.get(name, [])) for name in TABLE_ORDER}
    tier_counts: dict[str, int] = {}
    for row in tables["routing_state_current"]:
        tier_counts[str(row.get("auto_tier"))] = tier_counts.get(str(row.get("auto_tier")), 0) + 1

    def record(name: str, ok: bool, detail: Any, severity: str = "critical") -> None:
        add_check(checks, name, ok, detail, severity=severity)
        if not ok and severity == "critical":
            errors.append(name)
        elif not ok:
            warnings.append(name)

    source_missing = [row["path"] for row in tables["source_artifact"] if row["required_for_mvp"] and not row["exists_on_disk"]]
    record("required_sources_exist", not source_missing, {"missing": source_missing})
    schema_mismatches = check_source_schemas(tables["source_artifact"])
    record("accepted_source_schemas", not schema_mismatches, {"mismatches": schema_mismatches})
    stale_sources = stale_required_sources(tables["source_artifact"], str(context.get("generated_at_utc") or ""))
    record("required_source_freshness_thresholds", not stale_sources, {"stale": stale_sources}, severity="warning")
    durable_registry_gaps = durable_registry_findings(tables["source_artifact"])
    record("durable_registry_semantic_validity", not durable_registry_gaps, {"gaps": durable_registry_gaps}, severity="warning")
    record("active_router_rows_200", counts["routing_state_current"] == EXPECTED_ACTIVE_TICKERS, counts["routing_state_current"])
    record("security_master_rows_match_router", counts["security_master"] == counts["routing_state_current"], counts)
    record("universe_membership_rows_match_router", counts["universe_membership"] == counts["routing_state_current"], counts)
    expected_full_answer_rows = counts["routing_state_current"] * len(FULL_ANSWER_SECTION_SOURCES)
    record("full_answer_section_context_complete", counts["full_answer_section_context"] == expected_full_answer_rows, {"expected": expected_full_answer_rows, "actual": counts["full_answer_section_context"]})
    source_open_section_gaps = [
        {"ticker": row["ticker"], "section_id": row["section_id"], "source_kind": row.get("source_kind")}
        for row in tables["full_answer_section_context"]
        if not row.get("source_open_required")
    ]
    record("full_answer_sections_keep_source_open_required", not source_open_section_gaps, {"gaps": source_open_section_gaps[:50]})
    duplicate_findings = {
        table: duplicate_keys(tables.get(table, []), keys)
        for table, keys in PRIMARY_KEYS.items()
        if table != "validation_result"
    }
    duplicate_findings = {table: values for table, values in duplicate_findings.items() if values}
    record("generated_table_primary_keys_unique", not duplicate_findings, duplicate_findings)
    router_tickers = set(context.get("router_tickers") or [])
    finance_tickers = set(context.get("finance_universe_tickers") or [])
    freshness_tickers = set(context.get("tier_weighted_tickers") or [])
    spine_tickers = set(context.get("decision_spine_tickers") or [])
    record(
        "router_ticker_set_matches_finance_state_universe",
        router_tickers == finance_tickers,
        {"router_only": sorted(router_tickers - finance_tickers), "finance_only": sorted(finance_tickers - router_tickers)},
    )
    record(
        "tier_weighted_ticker_set_matches_router",
        router_tickers == freshness_tickers,
        {"router_only": sorted(router_tickers - freshness_tickers), "freshness_only": sorted(freshness_tickers - router_tickers)},
    )
    record(
        "decision_spine_extra_rows_recorded_as_optional",
        router_tickers.issubset(spine_tickers) or not spine_tickers,
        {"spine_extra": sorted(spine_tickers - router_tickers), "router_missing_from_spine": sorted(router_tickers - spine_tickers)},
        severity="warning",
    )
    record("tier_a_cap", tier_counts.get("Tier A", 0) <= 25, tier_counts)
    record("tier_b_cap", tier_counts.get("Tier B", 0) <= 50, tier_counts)
    record("tier_a_b_combined_cap", tier_counts.get("Tier A", 0) + tier_counts.get("Tier B", 0) <= 75, tier_counts)
    bad_tiers = sorted({str(row.get("auto_tier")) for row in tables["routing_state_current"] if row.get("auto_tier") not in VALID_AUTO_TIERS})
    bad_states = sorted({str(row.get("auto_state")) for row in tables["routing_state_current"] if row.get("auto_state") not in VALID_AUTO_STATES})
    record("routing_enum_domain_known", not bad_tiers and not bad_states, {"bad_tiers": bad_tiers, "bad_states": bad_states})
    record("router_summary_approval_counts_zero", router_summary.get("capital_deployment_approved_count", 0) == 0 and router_summary.get("trade_or_execution_approved_count", 0) == 0, router_summary)
    conflicted_ready = [
        row["ticker"] for row in tables["routing_state_current"]
        if row.get("auto_state") == "A-READY" and (row.get("critical_data_conflict_count") or 0) > 0
    ]
    record("no_a_ready_critical_conflicts", not conflicted_ready, {"tickers": conflicted_ready})
    missing_decision = sorted(set(row["ticker"] for row in tables["routing_state_current"]) - set(row["ticker"] for row in tables["decision_queue_state"]))
    record("decision_queue_rows_cover_router", not missing_decision, {"missing": missing_decision})
    actionability_risk = [
        {"ticker": row["ticker"], "actionability": row.get("actionability")}
        for row in tables["decision_queue_state"]
        if any(term in str(row.get("actionability") or "").lower() for term in FORBIDDEN_ACTIONABILITY_TERMS)
    ]
    record("decision_actionability_domain_review_only", not actionability_risk, {"risk": actionability_risk[:50]})
    source_ids = {row["artifact_id"] for row in tables["source_artifact"]}
    missing_source_refs = [
        {"table": table, "ticker": row.get("ticker"), "source_artifact_id": row.get("source_artifact_id")}
        for table in ("routing_state_current", "price_technical_current")
        for row in tables[table]
        if row.get("source_artifact_id") not in source_ids
    ]
    record("source_artifact_references_resolve", not missing_source_refs, {"missing_refs": missing_source_refs[:50]})
    forbidden = recursive_forbidden_true({"authority_boundary": AUTHORITY_BOUNDARY, "tables": tables})
    record("forbidden_authority_true_count_zero", not forbidden, {"forbidden": forbidden[:50], "count": len(forbidden)})
    feeder_forbidden = feeder_authority_violations()
    record("feeder_forbidden_authority_true_count_zero", not feeder_forbidden, {"forbidden": feeder_forbidden[:50], "count": len(feeder_forbidden)})
    paper_join_risk = [
        row["ticker"] for row in tables["decision_queue_state"]
        if row.get("paper_or_live_execution_allowed") is True
    ]
    record("paper_rows_read_only_boundary", not paper_join_risk, {"tickers": paper_join_risk})
    material_without_source = [
        row["ticker"] for row in tables["universe_membership"]
        if not row.get("source_open_required")
    ]
    record("source_open_required_or_explicit_context", not material_without_source, {"source_open_false": material_without_source[:50]}, severity="warning")

    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "canonical_table_count": len(TABLE_ORDER),
            "source_artifact_count": counts["source_artifact"],
            "routing_state_current_count": counts["routing_state_current"],
            "security_master_count": counts["security_master"],
            "decision_queue_state_count": counts["decision_queue_state"],
            "evidence_family_status_count": counts["evidence_family_status"],
            "full_answer_section_context_count": counts["full_answer_section_context"],
            "tier_counts": tier_counts,
            "forbidden_authority_true_count": len(forbidden),
            "owner_action_required_count": sum(1 for row in tables["decision_queue_state"] if row.get("owner_action_required")),
            "decision_spine_extra_count": len(spine_tickers - router_tickers),
        },
        "checks": checks,
    }


SQL_COLUMNS = {
    "schema_run": ["run_id TEXT PRIMARY KEY", "schema_version TEXT NOT NULL", "generated_at_utc TEXT NOT NULL", "local_market_date TEXT", "status TEXT NOT NULL", "builder_version TEXT", "authority_boundary_json TEXT NOT NULL", "validation_status TEXT NOT NULL"],
    "source_artifact": ["artifact_id TEXT PRIMARY KEY", "path TEXT NOT NULL", "role TEXT NOT NULL", "source_type TEXT NOT NULL", "required_for_mvp INTEGER NOT NULL", "exists_on_disk INTEGER NOT NULL", "generated_at_utc TEXT", "mtime_utc TEXT", "sha256 TEXT", "schema TEXT", "status TEXT", "validation_status TEXT", "source_rank INTEGER", "raw_summary_json TEXT"],
    "security_master": ["ticker TEXT PRIMARY KEY", "name TEXT", "instrument_type TEXT", "sector TEXT", "industry TEXT", "yfinance_symbol TEXT", "sec_cik TEXT", "company_ir_url TEXT", "active INTEGER NOT NULL"],
    "universe_membership": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "universe_scope TEXT NOT NULL", "legacy_universe_tier TEXT", "legacy_monitoring_role TEXT", "production_answer_path_member INTEGER NOT NULL", "thin_monitor_row INTEGER NOT NULL", "decision_grade_eligible INTEGER NOT NULL", "promotion_required_before_action INTEGER NOT NULL", "source_open_required INTEGER NOT NULL", "owner_note_path TEXT", "raw_json TEXT"],
    "routing_state_current": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "auto_tier TEXT NOT NULL", "auto_state TEXT NOT NULL", "route_priority INTEGER", "route_reason TEXT", "data_confidence_rating TEXT", "fundamentals_confidence TEXT", "tier_a_confidence_status TEXT", "tier_a_confidence_promotion_effect TEXT", "critical_data_conflict_count INTEGER NOT NULL", "requires_separate_capital_or_execution_approval INTEGER NOT NULL", "capital_deployment_approved INTEGER NOT NULL", "trade_or_execution_approved INTEGER NOT NULL", "would_mutate_universe INTEGER NOT NULL", "source_artifact_id TEXT NOT NULL"],
    "evidence_family_status": ["ticker TEXT NOT NULL REFERENCES security_master(ticker) ON DELETE CASCADE", "family_id TEXT NOT NULL", "status TEXT NOT NULL", "missing_count INTEGER NOT NULL", "stale_count INTEGER NOT NULL", "source_required INTEGER NOT NULL", "required_depth TEXT NOT NULL", "resolution_state TEXT", "tier_weighted_resolved INTEGER NOT NULL", "source_paths_json TEXT", "PRIMARY KEY (ticker, family_id)"],
    "full_answer_section_context": ["ticker TEXT NOT NULL REFERENCES security_master(ticker) ON DELETE CASCADE", "section_id TEXT NOT NULL", "section_status TEXT NOT NULL", "source_kind TEXT NOT NULL", "freshness_status TEXT NOT NULL", "source_paths_json TEXT", "source_open_required INTEGER NOT NULL", "field_presence_score REAL NOT NULL", "value_hash TEXT NOT NULL", "generated_at_utc TEXT", "raw_json TEXT", "PRIMARY KEY (ticker, section_id)"],
    "price_technical_current": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "latest_known_price REAL", "price_source TEXT", "quote_time_utc TEXT", "market_date TEXT", "band_status TEXT", "technical_status TEXT", "technical_summary TEXT", "fresh_quote_required INTEGER NOT NULL", "quote_freshness_status TEXT NOT NULL", "source_artifact_id TEXT NOT NULL", "raw_json TEXT"],
    "entry_stop_reference": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "entry_band_low REAL", "entry_band_high REAL", "stop_or_invalidation REAL", "band_source TEXT NOT NULL", "stop_source TEXT", "freshness_status TEXT NOT NULL", "validation_status TEXT NOT NULL", "owner_note_path TEXT", "source_artifact_path TEXT", "source_artifact_hash TEXT", "source_timestamp TEXT", "authority_boundary TEXT NOT NULL", "raw_json TEXT"],
    "fundamental_snapshot": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "period_end TEXT", "period_age_days INTEGER", "data_quality TEXT NOT NULL", "valuation_status TEXT", "key_metrics_status TEXT", "latest_earnings_status TEXT", "sec_reconciliation_status TEXT", "sec_conflicts_json TEXT", "company_ir_reconciliation_status TEXT", "capital_allocation_quality TEXT", "source_path TEXT NOT NULL", "raw_json TEXT"],
    "analyst_snapshot": ["ticker TEXT NOT NULL REFERENCES security_master(ticker) ON DELETE CASCADE", "provider TEXT NOT NULL", "status TEXT", "accessed_at_utc TEXT", "consensus_rating TEXT", "rating_summary TEXT", "average_target REAL", "median_target REAL", "implied_upside_downside_pct REAL", "confidence TEXT", "manual_review_required INTEGER NOT NULL", "source_url TEXT", "raw_json TEXT", "PRIMARY KEY (ticker, provider)"],
    "earnings_catalyst": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "latest_earnings_status TEXT", "latest_period_end TEXT", "next_earnings_date TEXT", "days_to_earnings INTEGER", "earnings_date_confirmed INTEGER NOT NULL", "post_earnings_review_confirmed INTEGER NOT NULL", "catalyst_status TEXT", "source_path TEXT NOT NULL", "raw_json TEXT"],
    "official_evidence": ["evidence_id TEXT PRIMARY KEY", "ticker TEXT NOT NULL REFERENCES security_master(ticker) ON DELETE CASCADE", "evidence_family TEXT", "status TEXT", "source_url TEXT", "source_section TEXT", "period TEXT", "manual_capture_required INTEGER NOT NULL", "inferred INTEGER NOT NULL", "source_open_required INTEGER NOT NULL", "source_path TEXT", "raw_json TEXT"],
    "decision_queue_state": ["ticker TEXT PRIMARY KEY REFERENCES security_master(ticker) ON DELETE CASCADE", "primary_state TEXT NOT NULL", "states_json TEXT", "recommendation_posture_key TEXT", "actionability TEXT NOT NULL", "queue_state TEXT NOT NULL", "rank_score REAL", "gate_verdict TEXT", "gate_vetoes_json TEXT", "owner_card_path TEXT", "wf67_request_path TEXT", "wf67_request_generation_status TEXT", "blockers_json TEXT", "warnings_json TEXT", "owner_action_required INTEGER NOT NULL", "capital_deployment_approved INTEGER NOT NULL", "trade_or_execution_approved INTEGER NOT NULL", "paper_or_live_execution_allowed INTEGER NOT NULL", "owner_approval_inferred INTEGER NOT NULL"],
    "validation_result": ["run_id TEXT NOT NULL", "check_name TEXT NOT NULL", "status TEXT NOT NULL", "severity TEXT NOT NULL", "detail_json TEXT", "source_artifact_id TEXT", "PRIMARY KEY (run_id, check_name)"],
}


def remove_existing_sqlite(db_path: Path, *, attempts: int = 12, delay_seconds: float = 0.25) -> None:
    paths = [db_path, db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm")]
    last_error: PermissionError | None = None
    for attempt in range(attempts):
        try:
            for path in paths:
                if path.exists():
                    path.unlink()
            return
        except PermissionError as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(delay_seconds)
    if last_error is not None:
        raise last_error


def create_sqlite(packet: dict[str, Any], db_path: Path) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with wf84_sqlite_mutex(db_path, role="canonical_finance_data_plane_writer"):
        return _create_sqlite_unlocked(packet, db_path)


def _create_sqlite_unlocked(packet: dict[str, Any], db_path: Path) -> dict[str, Any]:
    remove_existing_sqlite(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    tables = as_dict(packet.get("tables"))
    for table in TABLE_ORDER:
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    for table in TABLE_ORDER:
        conn.execute(f'CREATE TABLE "{table}" ({", ".join(SQL_COLUMNS[table])}) STRICT')
        rows = as_list(tables.get(table))
        columns = [part.split()[0] for part in SQL_COLUMNS[table] if not part.startswith("PRIMARY KEY")]
        if rows:
            placeholders = ",".join("?" for _ in columns)
            conn.executemany(
                f'INSERT INTO "{table}" ({",".join(columns)}) VALUES ({placeholders})',
                [tuple(to_sql_value(row.get(col)) for col in columns) for row in rows],
            )
    conn.executescript(
        """
        CREATE VIEW v_current_decision_overview AS
            SELECT s.ticker, s.name, s.instrument_type, s.sector,
                   r.auto_tier, r.auto_state, r.route_priority, r.route_reason,
                   p.latest_known_price, p.band_status, p.quote_freshness_status,
                   e.entry_band_low, e.entry_band_high, e.stop_or_invalidation,
                   d.primary_state, d.queue_state, d.actionability, d.owner_action_required,
                   d.capital_deployment_approved, d.trade_or_execution_approved,
                   d.paper_or_live_execution_allowed, d.owner_approval_inferred
            FROM security_master s
            JOIN routing_state_current r ON r.ticker = s.ticker
            LEFT JOIN price_technical_current p ON p.ticker = s.ticker
            LEFT JOIN entry_stop_reference e ON e.ticker = s.ticker
            LEFT JOIN decision_queue_state d ON d.ticker = s.ticker
            WHERE s.active = 1;

        CREATE VIEW v_owner_action_queue AS
            SELECT *
            FROM v_current_decision_overview
            WHERE owner_action_required = 1
               OR actionability IN ('approval_ready_if_fresh', 'promotion_review', 'owner_review_candidate')
            ORDER BY CASE auto_tier WHEN 'Tier A' THEN 1 WHEN 'Tier B' THEN 2 WHEN 'Tier C' THEN 3 ELSE 4 END,
                     route_priority IS NULL, route_priority, ticker;

        CREATE VIEW v_source_lineage_drillback AS
            SELECT s.artifact_id, s.path, s.role, s.status, s.validation_status, s.sha256,
                   COUNT(DISTINCT r.ticker) AS routing_rows
            FROM source_artifact s
            LEFT JOIN routing_state_current r ON r.source_artifact_id = s.artifact_id
            GROUP BY s.artifact_id, s.path, s.role, s.status, s.validation_status, s.sha256;

        CREATE VIEW v_full_ticker_answer_context AS
            SELECT s.ticker, s.name, s.instrument_type, s.sector,
                   r.auto_tier, r.auto_state, r.route_priority,
                   f.section_id, f.section_status, f.source_kind, f.freshness_status,
                   f.source_paths_json, f.source_open_required, f.field_presence_score,
                   f.value_hash, f.generated_at_utc, f.raw_json
            FROM full_answer_section_context f
            JOIN security_master s ON s.ticker = f.ticker
            JOIN routing_state_current r ON r.ticker = f.ticker
            WHERE s.active = 1;

        CREATE VIEW v_full_answer_source_drillback AS
            SELECT ticker, section_id, source_kind, section_status,
                   source_paths_json, source_open_required, generated_at_utc
            FROM full_answer_section_context;

        CREATE VIEW v_ticker_source_drillback AS
            SELECT r.ticker, 'routing_state_current' AS source_use,
                   s.artifact_id, s.path, s.role, s.status, s.validation_status, s.sha256
            FROM routing_state_current r
            JOIN source_artifact s ON s.artifact_id = r.source_artifact_id
            UNION ALL
            SELECT p.ticker, 'price_technical_current' AS source_use,
                   s.artifact_id, s.path, s.role, s.status, s.validation_status, s.sha256
            FROM price_technical_current p
            JOIN source_artifact s ON s.artifact_id = p.source_artifact_id
            UNION ALL
            SELECT e.ticker, 'entry_stop_reference' AS source_use,
                   'entry_stop_reference_source_path' AS artifact_id,
                   e.source_artifact_path AS path, 'entry_stop_reference_source' AS role,
                   e.freshness_status AS status, e.validation_status, e.source_artifact_hash AS sha256
            FROM entry_stop_reference e
            WHERE e.source_artifact_path IS NOT NULL AND e.source_artifact_path <> '';

        CREATE VIEW v_decision_grade_os_layer AS
            SELECT o.ticker, o.name, o.auto_tier, o.auto_state, o.route_priority, o.primary_state,
                   o.queue_state, o.actionability, o.owner_action_required,
                   o.latest_known_price, o.band_status, o.entry_band_low,
                   o.entry_band_high, o.stop_or_invalidation,
                   CASE
                       WHEN o.capital_deployment_approved != 0
                         OR o.trade_or_execution_approved != 0
                         OR o.paper_or_live_execution_allowed != 0
                         OR o.owner_approval_inferred != 0
                       THEN 'blocked_authority_violation'
                       WHEN o.owner_action_required = 1 THEN 'owner_review_queue'
                       WHEN o.quote_freshness_status NOT IN ('fresh', 'ok') THEN 'review_only_freshness_blocked'
                       ELSE 'review_only_monitor'
                   END AS os_decision_state,
                   'review_only_no_capital_or_execution_authority' AS authority_boundary
            FROM v_current_decision_overview o;

        CREATE VIEW v_wf84_priority_queue AS
            SELECT o.*,
                   CASE o.auto_tier WHEN 'Tier A' THEN 300 WHEN 'Tier B' THEN 200 WHEN 'Tier C' THEN 100 ELSE 0 END
                   + CASE WHEN o.owner_action_required = 1 THEN 75 ELSE 0 END
                   + CASE WHEN o.os_decision_state = 'review_only_freshness_blocked' THEN 25 ELSE 0 END
                   + CASE WHEN o.primary_state IN ('owner_review_candidate', 'invalidation_review') THEN 20 ELSE 0 END
                   AS review_priority_score,
                   'review_only_ranking_not_capital_or_execution_approval' AS priority_boundary
            FROM v_decision_grade_os_layer o
            ORDER BY review_priority_score DESC, route_priority IS NULL, route_priority, ticker;

        CREATE VIEW v_pm_decision_queue_overlay AS
            SELECT ticker, name, auto_tier, auto_state, primary_state, queue_state,
                   actionability, owner_action_required, review_priority_score,
                   latest_known_price, band_status, entry_band_low, entry_band_high,
                   stop_or_invalidation, authority_boundary, priority_boundary
            FROM v_wf84_priority_queue;

        CREATE VIEW v_authority_boundary_false AS
            SELECT
                (SELECT COUNT(*) FROM routing_state_current WHERE capital_deployment_approved != 0 OR trade_or_execution_approved != 0) AS routing_forbidden_count,
                (SELECT COUNT(*) FROM decision_queue_state WHERE capital_deployment_approved != 0 OR trade_or_execution_approved != 0 OR paper_or_live_execution_allowed != 0 OR owner_approval_inferred != 0) AS decision_forbidden_count;
        """
    )
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk_rows = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    counts = {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in TABLE_ORDER}
    view_counts = {
        "v_current_decision_overview": conn.execute("SELECT COUNT(*) FROM v_current_decision_overview").fetchone()[0],
        "v_owner_action_queue": conn.execute("SELECT COUNT(*) FROM v_owner_action_queue").fetchone()[0],
        "v_decision_grade_os_layer": conn.execute("SELECT COUNT(*) FROM v_decision_grade_os_layer").fetchone()[0],
        "v_source_lineage_drillback": conn.execute("SELECT COUNT(*) FROM v_source_lineage_drillback").fetchone()[0],
        "v_ticker_source_drillback": conn.execute("SELECT COUNT(*) FROM v_ticker_source_drillback").fetchone()[0],
        "v_full_ticker_answer_context": conn.execute("SELECT COUNT(*) FROM v_full_ticker_answer_context").fetchone()[0],
        "v_full_answer_source_drillback": conn.execute("SELECT COUNT(*) FROM v_full_answer_source_drillback").fetchone()[0],
        "v_wf84_priority_queue": conn.execute("SELECT COUNT(*) FROM v_wf84_priority_queue").fetchone()[0],
        "v_pm_decision_queue_overlay": conn.execute("SELECT COUNT(*) FROM v_pm_decision_queue_overlay").fetchone()[0],
    }
    authority = dict(conn.execute("SELECT * FROM v_authority_boundary_false").fetchone())
    conn.commit()
    conn.close()
    return {
        "status": "ok" if integrity == "ok" and not fk_rows and not any(authority.values()) else "blocked",
        "db_path": rel(db_path),
        "schema": SQLITE_SCHEMA,
        "integrity_check": integrity,
        "foreign_key_errors": fk_rows,
        "table_counts": counts,
        "view_counts": view_counts,
        "authority_view": authority,
    }


def to_sql_value(value: Any) -> Any:
    if isinstance(value, bool):
        return bool_int(value)
    if isinstance(value, (dict, list)):
        return json_text(value)
    return value


def ticker_packet(ticker: str, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    ticker = ticker.upper()
    if not db_path.exists():
        return {"status": "missing", "ticker": ticker, "db_path": rel(db_path)}
    with connect_ro(db_path) as conn:
        current = conn.execute("SELECT * FROM v_current_decision_overview WHERE ticker=?", (ticker,)).fetchone()
        if not current:
            return {"status": "missing", "ticker": ticker, "db_path": rel(db_path)}
        family = [dict(row) for row in conn.execute("SELECT * FROM evidence_family_status WHERE ticker=? ORDER BY family_id", (ticker,))]
        full_answer = [dict(row) for row in conn.execute("SELECT * FROM v_full_ticker_answer_context WHERE ticker=? ORDER BY section_id", (ticker,))]
        sources = [dict(row) for row in conn.execute("SELECT artifact_id,path,role,status,validation_status,sha256 FROM source_artifact ORDER BY source_rank")]
    return {
        "schema": "veritas.canonical_finance_data_plane.ticker_packet.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "ticker": ticker,
        "db_path": rel(db_path),
        "current": dict(current),
        "evidence_family_status": family,
        "full_answer_section_context": full_answer,
        "source_artifacts": sources,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "answer_contract": {
            "internal_review_only": True,
            "source_open_required_before_material_finance_claims": True,
            "does_not_authorize_capital_or_execution": True,
            "finance_intelligence_state_fallback_required_if_missing": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["build", "ticker"], default="build")
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--validation-out", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if args.command == "ticker":
        if not args.ticker:
            parser.error("ticker command requires ticker")
        result = ticker_packet(args.ticker, args.db)
        print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
        return 0 if result.get("status") == "ok" else 1

    packet = build_packet()
    sqlite_result = None
    if args.write:
        atomic_write_json(args.out, packet)
        atomic_write_json(args.validation_out, packet["validation"])
    if args.write_db:
        if packet.get("status") == "blocked":
            sqlite_result = {"status": "blocked", "reason": "packet validation blocked"}
        else:
            sqlite_result = create_sqlite(packet, args.db)
    result = {
        "status": packet.get("status"),
        "packet": rel(args.out),
        "validation": rel(args.validation_out),
        "db": rel(args.db) if args.write_db else None,
        "summary": packet.get("summary"),
        "sqlite": sqlite_result,
    }
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and (packet.get("status") == "blocked" or (sqlite_result and sqlite_result.get("status") != "ok")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
