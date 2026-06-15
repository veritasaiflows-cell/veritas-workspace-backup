"""Read-only WF78 legacy-42 shadow Tier A/B state helpers.

The shadow DB is the preferred migration surface for legacy production-current
ticker membership. The durable universe registry remains fallback/audit. This
module does not mutate the router, universe, SQL canon, portfolio, or any legacy
database.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

DEFAULT_SHADOW_DB = TMP / "wf78-legacy-42-tier-state-shadow.sqlite"
DEFAULT_PLANNER_JSON = TMP / "wf78-legacy-42-tier-migration-planner.json"
DEFAULT_UNIVERSE = DATA / "finance" / "universe-v1.json"

PRODUCTION_SCOPE = "production_current_42"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def universe_production_entries(universe_path: Path = DEFAULT_UNIVERSE) -> list[dict[str, Any]]:
    universe = load_dict(universe_path)
    rows = [
        row
        for row in as_list(universe.get("entries"))
        if isinstance(row, dict)
        and row.get("active") is not False
        and (row.get("production_scope") is True or row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE)
        and row.get("ticker")
    ]
    rows.sort(key=lambda row: str(row.get("ticker") or ""))
    return rows


def shadow_rows(db_path: Path = DEFAULT_SHADOW_DB) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    conn.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM legacy_42_tier_shadow
                ORDER BY CASE recommended_tier WHEN 'Tier A' THEN 0 ELSE 1 END,
                         COALESCE(adjudication_rank, 9999),
                         ticker
                """
            )
        ]
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    return rows


def shadow_tickers(db_path: Path = DEFAULT_SHADOW_DB) -> list[str]:
    return [str(row.get("ticker") or "").upper() for row in shadow_rows(db_path) if row.get("ticker")]


def production_tickers(
    *,
    prefer_shadow: bool = True,
    db_path: Path = DEFAULT_SHADOW_DB,
    universe_path: Path = DEFAULT_UNIVERSE,
) -> list[str]:
    if prefer_shadow:
        tickers = shadow_tickers(db_path)
        if tickers:
            return sorted(set(tickers))
    return sorted({str(row.get("ticker") or "").upper() for row in universe_production_entries(universe_path)})


def production_entries(
    *,
    prefer_shadow: bool = True,
    db_path: Path = DEFAULT_SHADOW_DB,
    universe_path: Path = DEFAULT_UNIVERSE,
) -> list[dict[str, Any]]:
    universe_entries = {str(row.get("ticker") or "").upper(): row for row in universe_production_entries(universe_path)}
    if not prefer_shadow:
        return [universe_entries[ticker] for ticker in sorted(universe_entries)]
    rows = shadow_rows(db_path)
    if not rows:
        return [universe_entries[ticker] for ticker in sorted(universe_entries)]
    out: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        base = dict(universe_entries.get(ticker, {}))
        base.setdefault("ticker", ticker)
        if row.get("name") and not base.get("name"):
            base["name"] = row.get("name")
        if row.get("sector") and not base.get("sector"):
            base["sector"] = row.get("sector")
        base["legacy_42_tier_shadow"] = {
            "source": "tmp/wf78-legacy-42-tier-state-shadow.sqlite",
            "recommended_tier": row.get("recommended_tier"),
            "recommended_state": row.get("recommended_state"),
            "current_auto_tier": row.get("current_auto_tier"),
            "current_auto_state": row.get("current_auto_state"),
            "requires_router_alignment": bool(row.get("requires_router_alignment")),
            "formal_admission_allowed_now": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
        out.append(base)
    return out


def source_summary() -> dict[str, Any]:
    shadow = shadow_rows()
    fallback = universe_production_entries()
    planner = load_dict(DEFAULT_PLANNER_JSON)
    return {
        "preferred_source": "shadow_tier_state" if shadow else "universe_fallback",
        "shadow_db": str(DEFAULT_SHADOW_DB.relative_to(ROOT)).replace("\\", "/"),
        "shadow_rows": len(shadow),
        "universe_fallback_rows": len(fallback),
        "planner_status": planner.get("status"),
        "legacy_db_deprecation_ready": as_dict(planner.get("summary")).get("legacy_db_deprecation_ready"),
        "authority_boundary": {
            "read_only": True,
            "router_mutation_allowed": False,
            "universe_mutation_allowed": False,
            "legacy_database_archive_or_delete_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
