#!/usr/bin/env python3
"""Build a report-only SQL source-of-truth authority manifest.

This manifest is a promotion-readiness control. It records what SQL surfaces
currently own, what they do not own, and the gated phase path required before
any SQL surface can become source of truth for a field family.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-source-truth-authority-manifest.json"
SCHEMA_VERSION = "sql_source_truth_authority_manifest.v1"

DB_SURFACES: dict[str, dict[str, Any]] = {
    "artifact_index": {
        "path": TMP / "veritas-artifact-index.sqlite",
        "authority_class": "derived_proof_index_staging_only",
        "may_route": True,
        "may_source_open": False,
        "may_apply": False,
        "current_owner": "scripts/artifact_index.py",
        "description": "Fast artifact/proof cockpit and lineage index. It routes to source artifacts; it is not canon.",
    },
    "canon_cache": {
        "path": TMP / "veritas-canon-cache.sqlite",
        "authority_class": "bounded_metadata_mirror_cache_only",
        "may_route": True,
        "may_source_open": False,
        "may_apply": False,
        "current_owner": "WF72 SQL-canon/cache guarded metadata boundary",
        "description": "Bounded metadata mirror/cache with fallback/source-open requirements. It is not broad SQL truth.",
    },
    "finance_intelligence_state": {
        "path": TMP / "finance-intelligence-state.sqlite",
        "authority_class": "current_state_query_and_pilot_staging_only",
        "may_route": True,
        "may_source_open": False,
        "may_apply": False,
        "current_owner": "scripts/finance_intelligence_state.py and WF78 pilot state",
        "description": "Ticker-card and entry/stop query surface; production path remains 42-card/file-backed.",
    },
    "paper_position_state": {
        "path": TMP / "wf67-paper-position-state.sqlite",
        "authority_class": "paper_position_visibility_only",
        "may_route": True,
        "may_source_open": False,
        "may_apply": False,
        "current_owner": "WF67 paper-position read-only visibility",
        "description": "Read-only paper position visibility. It grants no submit, cancel, sell, live, or account authority.",
    },
}

CANONICAL_OWNER_NOTES = [
    "03. Portfolio/Execution Board.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "04. Research/Coverage and Watchlist.md",
    "02. Markets/Macro Regime Dashboard.md",
    "07. Risk/Risk Rules.md",
    "06. Playbooks/Active Workflows.md",
]

FALSE_FLAGS = {
    "source_of_truth_promotion_allowed_by_this_artifact": False,
    "sql_first_consumer_migration_allowed": False,
    "sql_canon_expansion_allowed": False,
    "ticker_import_allowed": False,
    "production_answer_path_change_allowed": False,
    "canonical_markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "destructive_cleanup_allowed": False,
    "config_auth_channel_runtime_mutation_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_only_connect(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def sqlite_scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    if row is None:
        return None
    return row[0]


def inspect_db(surface: dict[str, Any]) -> dict[str, Any]:
    path = Path(surface["path"])
    payload: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "authority_class": surface["authority_class"],
        "current_owner": surface["current_owner"],
        "may_route": surface["may_route"],
        "may_source_open": surface["may_source_open"],
        "may_apply": surface["may_apply"],
        "description": surface["description"],
    }
    if not path.exists():
        payload["status"] = "missing"
        return payload

    payload["sha256"] = sha256(path)
    payload["bytes"] = path.stat().st_size
    try:
        with read_only_connect(path) as conn:
            payload["integrity_check"] = sqlite_scalar(conn, "PRAGMA integrity_check")
            payload["foreign_key_check_rows"] = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            tables = [
                {"name": row["name"], "type": row["type"]}
                for row in conn.execute(
                    "SELECT name, type FROM sqlite_master "
                    "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
                )
            ]
            payload["objects"] = tables
            counts: dict[str, int | None] = {}
            for item in tables:
                if item["type"] != "table":
                    continue
                try:
                    counts[item["name"]] = int(sqlite_scalar(conn, f"SELECT COUNT(*) FROM [{item['name']}]"))
                except sqlite3.Error:
                    counts[item["name"]] = None
            payload["table_counts"] = counts
            payload["status"] = "ok" if payload["integrity_check"] == "ok" else "integrity_warning"
    except sqlite3.Error as exc:
        payload["status"] = "error"
        payload["error"] = str(exc)
    return payload


def note_state(note_rel: str) -> dict[str, Any]:
    path = ROOT / note_rel
    return {
        "path": note_rel,
        "exists": path.exists(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size if path.exists() else None,
        "authority_class": "canonical_markdown_owner_surface",
        "source_of_truth_today": True,
    }


def field_family_plan() -> list[dict[str, Any]]:
    return [
        {
            "family": "proof_freshness_lifecycle_metadata",
            "current_status": "bounded_sql_cache_allowed_with_fallback",
            "promotion_candidate": "low_risk_after_parity_and_source_open_gate",
            "blocked_authority": ["recommendation", "deployment", "execution", "customer delivery"],
        },
        {
            "family": "entry_stop_reference_metadata",
            "current_status": "bounded_sql_cache_allowed_as_display_reference_only",
            "promotion_candidate": "first_phase_parity_mirror_candidate",
            "blocked_authority": ["action state", "sizing", "sleeve", "cash", "order terms", "execution"],
        },
        {
            "family": "artifact_routing_and_lineage",
            "current_status": "derived_index_route_allowed",
            "promotion_candidate": "routing_truth_candidate_after index_rebuild_and_source_open_proof",
            "blocked_authority": ["content claims without source-open", "canon mutation"],
        },
        {
            "family": "ticker_action_state",
            "current_status": "markdown_owner_only",
            "promotion_candidate": "blocked_until_bidirectional_drift_and_owner_decision_gate",
            "blocked_authority": ["deployable-now promotion", "recommendation", "paper/live order authority"],
        },
        {
            "family": "sizing_sleeve_cash_risk_rules",
            "current_status": "markdown_owner_only",
            "promotion_candidate": "blocked_higher_consequence",
            "blocked_authority": ["portfolio mutation", "cash/risk-rule change", "execution entitlement"],
        },
        {
            "family": "retail_customer_output",
            "current_status": "fixture_validation_only",
            "promotion_candidate": "blocked_until_privacy_source_legal_export_gates",
            "blocked_authority": ["real customer data", "external delivery", "regulated personalized advice"],
        },
        {
            "family": "paper_live_account_execution",
            "current_status": "not_sql_truth_candidate",
            "promotion_candidate": "blocked",
            "blocked_authority": ["paper submit/cancel/sell without exact approval", "live account action", "money movement"],
        },
    ]


def promotion_phases() -> list[dict[str, Any]]:
    return [
        {
            "phase": 0,
            "name": "freeze_current_truth_boundary",
            "status": "active",
            "acceptance": "SQL remains proof/query/staging; Markdown owner notes remain canonical.",
        },
        {
            "phase": 1,
            "name": "authority_manifest",
            "status": "implemented_by_this_script",
            "acceptance": "All SQL surfaces have authority class, false flags, owners, and stop lines.",
        },
        {
            "phase": 2,
            "name": "markdown_to_sql_parity_mirror",
            "status": "next_active_phase",
            "acceptance": "Exact owner-note extraction compares cleanly to SQL mirror for one approved field family.",
        },
        {
            "phase": 3,
            "name": "bidirectional_drift_validator",
            "status": "pending",
            "acceptance": "Markdown->SQL and SQL->Markdown drift are both fail-closed and source-hashed.",
        },
        {
            "phase": 4,
            "name": "consumer_ab_sql_first_read_with_markdown_fallback",
            "status": "pending",
            "acceptance": "A/B outputs are identical for production 42 and fail back to Markdown on any SQL gap.",
        },
        {
            "phase": 5,
            "name": "field_family_promotion_decision_packet",
            "status": "pending_owner_decision",
            "acceptance": "Randall approves exact field family, scope, rollback, validator, and consumer behavior.",
        },
        {
            "phase": 6,
            "name": "source_of_truth_promotion_readiness",
            "status": "blocked_until_prior_phases_green",
            "acceptance": "Promotion packet proves no drift, no authority widening, rollback, and downstream validators.",
        },
    ]


def build_manifest() -> dict[str, Any]:
    dbs = {name: inspect_db(surface) for name, surface in DB_SURFACES.items()}
    canonical_notes = [note_state(path) for path in CANONICAL_OWNER_NOTES]
    errors = [
        f"{name}:missing"
        for name, state in dbs.items()
        if not state.get("exists")
    ] + [
        f"{name}:integrity:{state.get('integrity_check')}"
        for name, state in dbs.items()
        if state.get("exists") and state.get("integrity_check") not in (None, "ok")
    ] + [
        f"{note['path']}:missing"
        for note in canonical_notes
        if not note.get("exists")
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "blocked_for_sql_source_truth_promotion" if errors else "ready_for_phase2_parity_scaffold",
        "authority_boundary": (
            "report_only_no_sql_writes_no_source_of_truth_promotion_no_consumer_migration_"
            "no_canon_or_portfolio_mutation_no_customer_or_execution_authority"
        ),
        **FALSE_FLAGS,
        "summary": {
            "database_surfaces": len(dbs),
            "canonical_owner_notes": len(canonical_notes),
            "errors": errors,
            "source_of_truth_today": "canonical_markdown_owner_notes",
            "sql_today": "derived_proof_query_staging_and_bounded_metadata_mirror_only",
            "next_safe_phase": "phase2_markdown_to_sql_parity_mirror",
        },
        "database_surfaces": dbs,
        "canonical_owner_notes": canonical_notes,
        "field_family_plan": field_family_plan(),
        "promotion_phases": promotion_phases(),
        "stop_lines": [
            "Do not promote SQL to source of truth from row counts or green proof packets alone.",
            "Do not add tickers, expand SQL-canon/cache, or change production answer paths from this manifest.",
            "Do not migrate consumers to SQL-first until field-family parity, drift, fallback, and A/B proofs are green.",
            "Do not treat SQL route/proof/index artifacts as owner approval, canon mutation authority, or trade/account authority.",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build_manifest()
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        missing_false = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if missing_false:
            raise SystemExit(f"authority false flag drift: {missing_false}")
        if payload["summary"]["errors"]:
            raise SystemExit(f"manifest errors: {payload['summary']['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
