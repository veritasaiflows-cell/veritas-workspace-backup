#!/usr/bin/env python3
"""Build and validate the finance cache dependency manifest.

This manifest makes the owner-truth -> WF72 -> finance-state -> WF84 -> WF85
cache chain explicit. It is a proof/guard surface only; it does not mutate
canon, portfolio state, cash/sizing/risk rules, brokerage/account state, or
execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_intelligence_state import entry_stop_cache_freshness_guard
from wf72_entry_stop_reference_helper import build_entry_stop_reference_metadata
from finance_production_scope import production_tickers, source_summary as production_scope_summary

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.cache_dependency_manifest.v1"
DEFAULT_OUT = TMP / "cache-dependency-manifest.json"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
PORTFOLIO_CONFIG = TMP / "portfolio-config.json"
CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"
WF84_DB = TMP / "canonical-finance-data-plane.sqlite"
WF84_PACKET = TMP / "canonical-finance-data-plane.json"
WF84_PHASE = TMP / "canonical-finance-data-plane-phase6-10.json"
WF85_CARDS = TMP / "trade-grade-decision-cards.json"
WF85_FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"
WF85_FULL_ANSWER_ROLLUP = TMP / "trade-grade-full-answer-assembler.json"
WF85_FULL_ANSWER_DELTA = TMP / "trade-grade-full-answer-assembler-delta.json"
FULL_ANSWER_PARITY_ROLLUP = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
FULL_ANSWER_PARITY_DELTA = TMP / "full-answer-parity" / "full-answer-parity-delta.json"
FINANCE_CACHE_FRONTDOOR = TMP / "finance-cache-frontdoor.json"

AUTHORITY_BOUNDARY = {
    "manifest_role": "cache_dependency_guard_review_only",
    "owner_truth_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

SQL_CANON_FRONT_DOOR_OK_STATUSES = {
    "ok",
    "ok_legacy_cache_hash_warning",
    "ok_sql_canon_authoritative",
    "ok_sql_canon_authoritative_legacy_decoupled",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def file_meta(path: Path, *, role: str, builder: str | None = None, inputs: list[str] | None = None) -> dict[str, Any]:
    exists = path.exists()
    stat = path.stat() if exists else None
    payload = load_json_artifact(path) if exists and path.suffix.lower() == ".json" else None
    generated = payload.get("generated_at_utc") if isinstance(payload, dict) else None
    return {
        "path": rel(path),
        "role": role,
        "exists": exists,
        "sha256": sha256_file(path) if exists and path.is_file() else None,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stat else None,
        "size_bytes": stat.st_size if stat and path.is_file() else None,
        "generated_at_utc": generated,
        "builder": builder,
        "inputs": inputs or [],
    }


def connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def query_one(db_path: Path, sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
    conn = connect_ro(db_path)
    if conn is None:
        return {}
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else {}
    except sqlite3.Error as exc:
        return {"_error": str(exc)}
    finally:
        conn.close()


def load_wf85_card(ticker: str) -> dict[str, Any]:
    payload = load_json_artifact(WF85_CARDS)
    cards = payload.get("cards") if isinstance(payload, dict) else []
    for card in cards or []:
        if str(card.get("ticker") or "").upper() == ticker:
            return card
    return {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def requested_tickers(value: str | None) -> list[str]:
    if value:
        return sorted({item.strip().upper() for item in value.split(",") if item.strip()})
    try:
        return sorted({ticker.upper() for ticker in production_tickers()})
    except Exception:
        return []


def production_scope_metadata() -> dict[str, Any]:
    try:
        return production_scope_summary()
    except Exception as exc:
        return {
            "preferred_source": "finance_sql_canon_access.production_answer_tickers",
            "production_ticker_count": 0,
            "production_tickers": [],
            "empty_scope_is_valid_wait_state": False,
            "error": str(exc),
        }


def layer_status(source_hash: Any, owner_hash: str | None, validation_status: Any = None) -> dict[str, Any]:
    if not owner_hash:
        return {"status": "blocked", "reason": "owner_source_hash_missing"}
    if not source_hash:
        return {"status": "blocked", "reason": "source_hash_missing"}
    if str(source_hash) != owner_hash:
        return {"status": "stale", "reason": "source_hash_mismatch"}
    if validation_status not in (None, "", "ok", "available", "fresh"):
        return {"status": "blocked", "reason": f"validation_status={validation_status}"}
    return {"status": "ok", "reason": "source_hash_matches_owner_truth"}


def value_consistency(finance: dict[str, Any], wf84: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for field in ("entry_band_low", "entry_band_high", "stop_or_invalidation"):
        try:
            finance_value = float(finance.get(field))
            wf84_value = float(wf84.get(field))
            ok = abs(finance_value - wf84_value) <= 0.01
        except (TypeError, ValueError):
            finance_value = finance.get(field)
            wf84_value = wf84.get(field)
            ok = finance_value == wf84_value and finance_value not in (None, "")
        checks.append({"field": field, "ok": ok, "finance_state": finance_value, "wf84": wf84_value})
    return {
        "status": "ok" if all(check["ok"] for check in checks) else "blocked",
        "checks": checks,
    }


def sql_canon_front_door_guard_status(ticker: str, finance: dict[str, Any]) -> dict[str, Any]:
    """Classify legacy entry/stop cache residue under the SQL-canon front-door guard."""
    guard = entry_stop_cache_freshness_guard(ticker, finance)
    policy = guard.get("front_door_policy") if isinstance(guard, dict) else {}
    status = guard.get("status") if isinstance(guard, dict) else None
    ok = (
        status in SQL_CANON_FRONT_DOOR_OK_STATUSES
        and isinstance(policy, dict)
        and policy.get("prefer_wf85_full_answer") is True
        and policy.get("stale_entry_stop_cache_blocks_generated_answer") is False
    )
    return {
        "status": "ok" if ok else "blocked",
        "reason": "sql_canon_front_door_guard_allows_legacy_hash_residue" if ok else f"sql_canon_front_door_guard_status={status}",
        "guard_status": status,
        "front_door_policy": policy,
        "guard": guard,
    }


def sql_canon_guard_allows_legacy_value_residue(status: dict[str, Any]) -> bool:
    if status.get("status") != "ok":
        return False
    guard = as_dict(status.get("guard"))
    policy = as_dict(guard.get("front_door_policy"))
    consistency = as_dict(guard.get("sql_canon_reference_consistency"))
    wf84_vs_sql = as_dict(consistency.get("wf84_vs_sql_canon"))
    return (
        wf84_vs_sql.get("status") == "ok"
        and policy.get("prefer_wf85_full_answer") is True
        and policy.get("stale_entry_stop_cache_blocks_generated_answer") is False
        and policy.get("legacy_compatibility_blocks_front_door") is False
    )


def ticker_row(ticker: str, owner_hash: str | None) -> dict[str, Any]:
    wf72 = build_entry_stop_reference_metadata(ticker)
    wf72_hash = (wf72.get("source_lineage") or {}).get("source_sha256")
    finance = query_one(
        FINANCE_STATE_DB,
        "SELECT ticker, entry_band_low, entry_band_high, stop_or_invalidation, source_artifact_path, source_artifact_hash, source_timestamp, freshness_status, validation_status FROM entry_stop_reference WHERE ticker=?",
        (ticker,),
    )
    wf84 = query_one(
        WF84_DB,
        "SELECT ticker, entry_band_low, entry_band_high, stop_or_invalidation, source_artifact_path, source_artifact_hash, source_timestamp, freshness_status, validation_status FROM entry_stop_reference WHERE ticker=?",
        (ticker,),
    )
    card = load_wf85_card(ticker)
    answer_path = WF85_FULL_ANSWER_DIR / f"{ticker}.json"
    parity_path = TMP / "full-answer-parity" / f"{ticker}.json"
    statuses = {
        "wf72": layer_status(wf72_hash, owner_hash, wf72.get("status")),
        "finance_state": layer_status(finance.get("source_artifact_hash"), owner_hash, finance.get("validation_status")),
        "wf84": layer_status(wf84.get("source_artifact_hash"), owner_hash, wf84.get("validation_status")),
        "sql_canon_front_door_guard": sql_canon_front_door_guard_status(ticker, finance),
        "wf85_card": {"status": "ok" if card else "missing", "reason": "card_present" if card else "wf85_card_missing"},
        "wf85_full_answer": {"status": "ok" if answer_path.exists() else "missing", "reason": "full_answer_present" if answer_path.exists() else "wf85_full_answer_missing"},
        "full_answer_parity": {"status": "ok" if parity_path.exists() else "missing", "reason": "parity_present" if parity_path.exists() else "full_answer_parity_missing"},
    }
    values = value_consistency(finance, wf84)
    required = ["wf72", "finance_state", "wf84"]
    sql_guard_allows_legacy_values = sql_canon_guard_allows_legacy_value_residue(statuses["sql_canon_front_door_guard"])
    status = "ok" if all(statuses[name]["status"] == "ok" for name in required) and values["status"] == "ok" else "blocked"
    if statuses["sql_canon_front_door_guard"]["status"] == "ok" and (values["status"] == "ok" or sql_guard_allows_legacy_values):
        status = "ok"
    if any(statuses[name]["status"] == "stale" for name in required):
        status = "stale"
    if statuses["sql_canon_front_door_guard"]["status"] == "ok" and (values["status"] == "ok" or sql_guard_allows_legacy_values):
        status = "ok"
    elif values["status"] != "ok":
        status = "blocked_cross_layer_value_mismatch"
    return {
        "ticker": ticker,
        "status": status,
        "owner_source": {
            "path": rel(EXECUTION_BOARD),
            "sha256": owner_hash,
        },
        "layers": {
            "wf72": {
                "status": wf72.get("status"),
                "source_sha256": wf72_hash,
                "row_count": len(wf72.get("row_keys") or []),
                "issues": wf72.get("issues") or [],
            },
            "finance_state": finance,
            "wf84": wf84,
            "wf85_card": {
                "present": bool(card),
                "entry_band": card.get("entry_band") if card else None,
                "stop_or_invalidation": card.get("stop_or_invalidation") if card else None,
            },
            "wf85_full_answer": file_meta(answer_path, role="wf85_ticker_full_answer", builder="trade_grade_full_answer_assembler.py"),
            "full_answer_parity": file_meta(parity_path, role="wf85_ticker_full_answer_parity", builder="full_intelligence_answer_parity.py"),
        },
        "layer_status": statuses,
        "value_consistency": values,
    }


def build_manifest(tickers: list[str], production_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    production_scope = production_scope or production_scope_metadata()
    owner_hash = sha256_file(EXECUTION_BOARD)
    rows = [ticker_row(ticker, owner_hash) for ticker in tickers]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    status = "ok" if rows and status_counts.get("ok") == len(rows) else "blocked"
    if status_counts.get("stale"):
        status = "stale"
    empty_scope_valid_wait_state = (
        not rows
        and int(production_scope.get("production_ticker_count") or 0) == 0
        and production_scope.get("empty_scope_is_valid_wait_state") is True
    )
    if empty_scope_valid_wait_state:
        status = "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "ticker_count": len(rows),
            "status_counts": status_counts,
            "owner_execution_board_sha256": owner_hash,
            "manifest_scope": "entry_stop_reference_cache_chain",
            "production_scope": {
                "preferred_source": production_scope.get("preferred_source"),
                "production_scope_definition": production_scope.get("production_scope_definition"),
                "production_ticker_count": production_scope.get("production_ticker_count"),
                "empty_scope_valid_wait_state": empty_scope_valid_wait_state,
            },
            "empty_scope_valid_wait_state": empty_scope_valid_wait_state,
        },
        "cache_chain": [
            file_meta(EXECUTION_BOARD, role="owner_truth", inputs=[]),
            file_meta(PORTFOLIO_CONFIG, role="owner_truth_config", inputs=[]),
            file_meta(CANON_CACHE_DB, role="wf72_sql_reference_cache", builder="wf72_entry_stop_sql_activate.py", inputs=[rel(EXECUTION_BOARD)]),
            file_meta(FINANCE_STATE_DB, role="finance_state_query_cache", builder="finance_intelligence_state.py build", inputs=[rel(CANON_CACHE_DB)]),
            file_meta(WF84_DB, role="wf84_canonical_data_plane_sqlite", builder="canonical_finance_data_plane.py --write-db", inputs=[rel(FINANCE_STATE_DB)]),
            file_meta(WF84_PACKET, role="wf84_canonical_data_plane_json", builder="canonical_finance_data_plane.py --write", inputs=[rel(FINANCE_STATE_DB)]),
            file_meta(WF84_PHASE, role="wf84_consumer_phase_proof", builder="canonical_finance_data_plane_phase6_10.py", inputs=[rel(WF84_DB)]),
            file_meta(WF85_CARDS, role="wf85_decision_cards", builder="trade_grade_decision_cards.py", inputs=[rel(WF84_DB)]),
            file_meta(WF85_FULL_ANSWER_ROLLUP, role="wf85_full_answer_rollup", builder="trade_grade_full_answer_assembler.py", inputs=[rel(WF84_DB), rel(WF85_CARDS)]),
            file_meta(WF85_FULL_ANSWER_DELTA, role="wf85_changed_ticker_answer_delta", builder="trade_grade_full_answer_assembler.py --tickers", inputs=[rel(WF84_DB), rel(WF85_CARDS)]),
            file_meta(FULL_ANSWER_PARITY_ROLLUP, role="wf85_full_answer_parity_rollup", builder="full_intelligence_answer_parity.py", inputs=[rel(WF84_DB), rel(WF85_FULL_ANSWER_ROLLUP)]),
            file_meta(FULL_ANSWER_PARITY_DELTA, role="wf85_changed_ticker_parity_delta", builder="full_intelligence_answer_parity.py --tickers", inputs=[rel(WF84_DB), rel(WF85_FULL_ANSWER_DELTA)]),
        ],
        "downstream_chat_consumers": [
            file_meta(
                FINANCE_CACHE_FRONTDOOR,
                role="finance_cache_chat_frontdoor_consumer",
                builder="finance_cache_frontdoor.py",
                inputs=[
                    rel(WF84_DB),
                    rel(WF85_FULL_ANSWER_ROLLUP),
                    rel(FULL_ANSWER_PARITY_ROLLUP),
                    rel(DEFAULT_OUT),
                ],
            ),
        ],
        "tickers": rows,
        "stale_read_policy": {
            "empty_production_scope_is_valid_wait_state_when_sql_scope_says_so": True,
            "ticker_front_door_must_not_prefer_wf85_when_entry_stop_hash_mismatch": False,
            "legacy_entry_stop_hash_mismatch_is_monitor_only_when_sql_canon_guard_is_clean": True,
            "source_open_required_if_manifest_or_front_door_guard_blocks": True,
            "full_rebuild_still_required_for_major_closeout_or_population_proof": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", help="Comma-separated ticker subset. Defaults to production tickers.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    tickers = requested_tickers(args.tickers)
    manifest = build_manifest(tickers)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, manifest)
    print(json.dumps({"status": manifest["status"], "out": rel(out), "summary": manifest["summary"]}, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and manifest["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

