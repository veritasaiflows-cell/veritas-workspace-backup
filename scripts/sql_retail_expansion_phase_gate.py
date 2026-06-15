#!/usr/bin/env python3
"""Coordinate WF72/WF78 SQL retail expansion Phases 1-4.

Report-only gate. It freezes the current SQL baseline, proves the WF72
entry/stop helper is no-drift across the current 42 production cards, summarizes
SQL retail blockers, and checks the existing isolated 25-name pilot without
adding tickers or changing production consumers.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ticker_intelligence_card import (
    ANALYST_CONSENSUS_PATH,
    DEFAULT_OUT_DIR,
    DEPLOYMENT_SURFACE_PATH,
    FUNDAMENTALS_PATH,
    OFFICIAL_EARNINGS_BRIDGE_PATH,
    PORTFOLIO_CONFIG_PATH,
    POSITION_SIZING_READINESS_PATH,
    SECTOR_EXPANSION_BOARD_PATH,
    TECHNICAL_REFRESH_PATH,
    UNIVERSE_PATH,
    build_card,
    index_fundamentals,
    index_universe,
    load_json,
    tickers_from_coverage,
    validate_card,
)
from wf72_entry_stop_reference_helper import NO_DRIFT_FIELDS
from wf78_legacy_42_tier_state import production_tickers as effective_production_tickers

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_DB = TMP / "finance-intelligence-state.sqlite"

PHASES_OUT = TMP / "sql-retail-expansion-phases-1-4-gate.json"
NO_DRIFT_OUT = TMP / "finance-sql-canon-production42-no-drift-review.json"
BLOCKERS_OUT = TMP / "sql-retail-blocker-classification.json"
READINESS = TMP / "sql-canon-retail-grade-readiness.json"
VALIDATION_BUNDLE = TMP / "sql-retail-grade-validation-bundle.json"
DESIGN_GATE = TMP / "sql-500-ticker-expansion-design-gate.json"

AUTHORITY_BOUNDARY = {
    "report_only": True,
    "ticker_import_allowed": False,
    "broad_100_200_350_500_import_allowed": False,
    "production_answer_path_overwrite_allowed": False,
    "sql_canon_expansion_allowed": False,
    "sql_first_consumer_migration_allowed": False,
    "database_path_migration_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_trade_authority_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "config_auth_channel_service_runtime_mutation_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def card_inputs() -> dict[str, Any]:
    fundamentals = load_json(FUNDAMENTALS_PATH, {})
    universe = load_json(UNIVERSE_PATH, {})
    return {
        "fundamentals": fundamentals,
        "fundamental_index": index_fundamentals(fundamentals),
        "deployment_surface": load_json(DEPLOYMENT_SURFACE_PATH, {}),
        "tuesday_readiness": load_json(POSITION_SIZING_READINESS_PATH, {}),
        "analyst_consensus": load_json(ANALYST_CONSENSUS_PATH, {}),
        "universe": universe,
        "universe_index": index_universe(universe),
        "official_earnings_bridge": load_json(OFFICIAL_EARNINGS_BRIDGE_PATH, {}),
        "sector_expansion_board": load_json(SECTOR_EXPANSION_BOARD_PATH, {}),
        "technical_refresh": load_json(TECHNICAL_REFRESH_PATH, {}),
        "portfolio_config": load_json(PORTFOLIO_CONFIG_PATH, {}),
    }


def production_tickers_from_universe(inputs: dict[str, Any]) -> list[str]:
    migrated = effective_production_tickers()
    if migrated:
        return migrated
    universe = inputs.get("universe", {}) if isinstance(inputs.get("universe"), dict) else {}
    entries = universe.get("entries", []) if isinstance(universe.get("entries"), list) else []
    tickers: list[str] = []
    for row in entries:
        if not isinstance(row, dict) or row.get("active") is not True:
            continue
        if row.get("universe_scope", "production_current_42") != "production_current_42":
            continue
        ticker = str(row.get("ticker", "")).upper().strip()
        if ticker:
            tickers.append(ticker)
    return sorted(set(tickers))


def build_42_no_drift_review(write: bool = False) -> dict[str, Any]:
    inputs = card_inputs()
    tickers = production_tickers_from_universe(inputs) or tickers_from_coverage()
    results: list[dict[str, Any]] = []
    missing_existing: list[str] = []
    validation_errors: list[dict[str, Any]] = []
    drift: list[dict[str, Any]] = []
    metadata_issues: list[dict[str, Any]] = []

    for ticker in tickers:
        existing_path = DEFAULT_OUT_DIR / f"{ticker}.current.json"
        existing = read_json(existing_path, {})
        if not existing:
            missing_existing.append(ticker)
            continue
        generated = build_card(ticker, inputs)
        additive = dict(existing)
        additive["entry_stop_reference_metadata"] = generated.get("entry_stop_reference_metadata")
        additive["generated_at_utc"] = generated.get("generated_at_utc")
        errors = validate_card(additive)
        if errors:
            validation_errors.append({"ticker": ticker, "errors": errors})

        diffs = [
            {"field": field, "before": existing.get(field), "after": generated.get(field)}
            for field in NO_DRIFT_FIELDS
            if existing.get(field) != additive.get(field)
        ]
        if diffs:
            drift.append({"ticker": ticker, "diffs": diffs})

        metadata = additive.get("entry_stop_reference_metadata") or {}
        row_keys = metadata.get("row_keys") or []
        if metadata.get("status") != "available" or len(row_keys) != 6:
            metadata_issues.append({
                "ticker": ticker,
                "metadata_status": metadata.get("status"),
                "row_count": len(row_keys),
                "issues": metadata.get("issues") or [],
            })

        results.append({
            "ticker": ticker,
            "existing_card": rel(existing_path),
            "no_drift": not diffs,
            "proof_mode": "additive_metadata_overlay_only_no_card_regeneration",
            "metadata_status": metadata.get("status"),
            "metadata_row_count": len(row_keys),
            "compared_fields": list(NO_DRIFT_FIELDS),
        })

    status = "no_drift" if tickers and not missing_existing and not validation_errors and not drift and not metadata_issues else "blocked"
    packet = {
        "schema_version": "wf72_entry_stop_helper_42_no_drift_review.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "scope": "current_42_production_cards_additive_metadata_overlay_no_card_writes",
        "ticker_count": len(tickers),
        "compared_fields": list(NO_DRIFT_FIELDS),
        "regeneration_note": (
            "This gate intentionally does not rebuild production cards. It proves that adding "
            "typed SQL entry/stop reference metadata to existing cards leaves semantic fields "
            "unchanged; full card regeneration is a separate freshness/update workflow."
        ),
        "summary": {
            "missing_existing_cards": len(missing_existing),
            "validation_error_tickers": len(validation_errors),
            "drift_tickers": len(drift),
            "metadata_issue_tickers": len(metadata_issues),
        },
        "missing_existing_cards": missing_existing,
        "validation_errors": validation_errors,
        "drift": drift,
        "metadata_issues": metadata_issues,
        "results": results,
        "stop_lines": [
            "No ticker-card files were written by this gate.",
            "SQL metadata remains display/reference/fallback-required only.",
            "No SQL-first consumer migration or SQL-canon expansion is authorized.",
        ],
    }
    if write:
        write_json(NO_DRIFT_OUT, packet)
    return packet


def classify_retail_blockers(write: bool = False) -> dict[str, Any]:
    readiness = read_json(READINESS, {}) or {}
    rows = readiness.get("row_readiness") or []
    readiness_counts = Counter(row.get("readiness", "unknown") for row in rows)
    issue_counts = Counter(issue for row in rows for issue in row.get("issues", []))
    family_counts = Counter(row.get("risk_family") or "unclassified" for row in rows)
    ticker_counts = Counter(str(row.get("scope") or "").upper() for row in rows if row.get("scope"))
    direct_sql_allowed = [row.get("key") for row in rows if row.get("sql_effective_allowed") is True]
    display_reference = [row.get("key") for row in rows if row.get("readiness") == "display_only_reference_metadata"]
    fallback_rows = [
        row.get("key")
        for row in rows
        if str(row.get("readiness") or "").startswith("fallback_required")
        or row.get("readiness") == "blocked_higher_risk_family"
    ]

    summary = readiness.get("summary", {}) or {}
    status = "classified_blocked" if readiness.get("status") == "blocked_for_sql_first_retail_grade" else "classified_ready"
    packet = {
        "schema_version": "sql_retail_blocker_classification.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_readiness_artifact": rel(READINESS),
        "summary": {
            "readiness_status": readiness.get("status"),
            "cache_rows": summary.get("cache_rows"),
            "sql_effective_allowed_rows": len(direct_sql_allowed),
            "display_reference_rows": len(display_reference),
            "fallback_or_blocked_rows": len(fallback_rows),
            "readiness_counts": dict(sorted(readiness_counts.items())),
            "risk_family_counts": dict(sorted(family_counts.items())),
            "top_issue_counts": dict(issue_counts.most_common(25)),
            "top_scope_counts": dict(ticker_counts.most_common(20)),
        },
        "blocker_model": [
            {
                "class": "display_reference_metadata",
                "row_count": len(display_reference),
                "handling": "Allowed only as labeled reference context with existing card/Markdown fallback; not SQL-first retail truth.",
            },
            {
                "class": "stale_or_missing_fallback_or_guard_blocked",
                "row_count": len(fallback_rows),
                "handling": "Keep blocked for SQL-first use until fallback/no-drift/source freshness gates are explicitly green.",
            },
            {
                "class": "direct_sql_effective",
                "row_count": len(direct_sql_allowed),
                "handling": "Currently zero by design; do not force this open during Phases 1-4.",
            },
        ],
        "next_remediation_order": [
            "Keep all 252 entry/stop rows display/reference/fallback-required until a customer-safe renderer exists.",
            "Resolve stale/hash mismatches in the 13 low-risk proof/freshness/lifecycle rows before SQL-first use.",
            "Run no-drift across all 42 before any consumer migration.",
            "Do not add leadership/ticker enrichment rows until artifact-only research and renderer leak/claim gates exist.",
        ],
        "stop_lines": [
            "This classification does not activate rows, write SQL, or clear the retail block.",
            "Retail/customer SQL-first use remains blocked unless the readiness artifact says otherwise.",
        ],
    }
    if write:
        write_json(BLOCKERS_OUT, packet)
    return packet


def state_counts() -> dict[str, Any]:
    counts: dict[str, Any] = {"state_db": rel(STATE_DB), "exists": STATE_DB.exists()}
    if not STATE_DB.exists():
        return counts
    uri = STATE_DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        counts.update({
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "production_current_cards": conn.execute("SELECT COUNT(*) FROM current_ticker_cards").fetchone()[0],
            "live_pilot_candidates": conn.execute("SELECT COUNT(*) FROM current_live_pilot_candidates").fetchone()[0],
            "live_pilot_provider_ok": conn.execute("SELECT COUNT(*) FROM live_pilot_provider_status WHERE provider_status='ok'").fetchone()[0],
            "pilot_production_overlap": conn.execute(
                "SELECT COUNT(*) FROM current_live_pilot_candidates WHERE ticker IN (SELECT ticker FROM current_ticker_cards)"
            ).fetchone()[0],
            "live_pilot_bad_authority": conn.execute(
                """
                SELECT COUNT(*)
                FROM live_pilot_candidate_registry
                WHERE production_answer_path_member != 0
                   OR decision_grade_eligible != 0
                   OR source_open_required != 1
                   OR thin_row_only != 1
                   OR on_demand_card_required_before_claim != 1
                """
            ).fetchone()[0],
        })
    return counts


def phase3_blockers_ok(blockers: dict[str, Any]) -> bool:
    summary = blockers.get("summary", {}) or {}
    return (
        blockers.get("status") == "classified_blocked"
        and summary.get("readiness_status") == "blocked_for_sql_first_retail_grade"
        and summary.get("cache_rows") == 265
        and summary.get("sql_effective_allowed_rows") == 0
        and summary.get("fallback_or_blocked_rows") == 265
    )


def build_phase_gate(no_drift: dict[str, Any], blockers: dict[str, Any], write: bool = False) -> dict[str, Any]:
    bundle = read_json(VALIDATION_BUNDLE, {}) or {}
    design = read_json(DESIGN_GATE, {}) or {}
    counts = state_counts()
    checks = [
        {"name": "phase1_validation_bundle_ok", "ok": bundle.get("status") in {"ok", "warning"}, "detail": bundle.get("status")},
        {"name": "phase1_500_design_gate_ok", "ok": design.get("validation", {}).get("status") == "ok", "detail": design.get("status")},
        {"name": "phase2_42_card_no_drift", "ok": no_drift.get("status") == "no_drift", "detail": no_drift.get("summary")},
        {"name": "phase3_blockers_classified", "ok": phase3_blockers_ok(blockers), "detail": blockers.get("summary")},
        {"name": "phase4_state_db_integrity_ok", "ok": counts.get("integrity_check") == "ok", "detail": counts.get("integrity_check")},
        {"name": "phase4_production_locked_42", "ok": counts.get("production_current_cards") == 42, "detail": counts.get("production_current_cards")},
        {"name": "phase4_live_pilot_isolated_25", "ok": counts.get("live_pilot_candidates") == 25, "detail": counts.get("live_pilot_candidates")},
        {"name": "phase4_live_pilot_provider_ok_25", "ok": counts.get("live_pilot_provider_ok") == 25, "detail": counts.get("live_pilot_provider_ok")},
        {"name": "phase4_pilot_overlap_zero", "ok": counts.get("pilot_production_overlap") == 0, "detail": counts.get("pilot_production_overlap")},
        {"name": "phase4_live_pilot_authority_clean", "ok": counts.get("live_pilot_bad_authority") == 0, "detail": counts.get("live_pilot_bad_authority")},
    ]
    failed = [check for check in checks if not check["ok"]]
    packet = {
        "schema_version": "sql_retail_expansion_phases_1_4_gate.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_phase5_design_no_import" if not failed else "blocked",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "phase_results": [
            {
                "phase": "Phase 1 baseline freeze",
                "status": "ok" if checks[0]["ok"] and checks[1]["ok"] else "blocked",
                "proof": [rel(VALIDATION_BUNDLE), rel(DESIGN_GATE)],
            },
            {
                "phase": "Phase 2 current 42 no-drift",
                "status": no_drift.get("status"),
                "proof": rel(NO_DRIFT_OUT),
            },
            {
                "phase": "Phase 3 retail blocker classification",
                "status": blockers.get("status"),
                "proof": rel(BLOCKERS_OUT),
            },
            {
                "phase": "Phase 4 existing pilot hardening",
                "status": "ok" if all(check["ok"] for check in checks[4:]) else "blocked",
                "proof": [rel(STATE_DB), "tmp/finance-intelligence-state-live-pilot.json"],
            },
        ],
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed": len(failed)},
        "current_state": counts,
        "phase5_preparation": {
            "prepared": not failed,
            "next_gate": "Design 100-name thin-monitor proposal without import.",
            "required_before_any_import": [
                "Phase 5 import candidate list as review-only proposal",
                "provider/runtime budget and sharding/circuit-breaker plan",
                "A/B freshness non-regression proof",
                "source-open/customer-safe renderer and claim/leak validation if retail output is involved",
                "explicit owner approval before adding any new tickers",
            ],
        },
        "stop_lines": [
            "Do not add additional tickers from this packet.",
            "Do not migrate consumers to SQL-first.",
            "Do not move DB paths or promote tmp databases.",
            "Do not expand SQL-canon/cache rows.",
        ],
    }
    if write:
        write_json(PHASES_OUT, packet)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write proof packets under tmp/.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero when gate validation is blocked.")
    args = parser.parse_args()

    no_drift = build_42_no_drift_review(write=args.write)
    blockers = classify_retail_blockers(write=args.write)
    phase_gate = build_phase_gate(no_drift, blockers, write=args.write)
    print(json.dumps({
        "status": phase_gate["status"],
        "validation": phase_gate["validation"]["status"],
        "phase2": no_drift["status"],
        "phase3": blockers["status"],
        "output": rel(PHASES_OUT) if args.write else None,
        "no_drift_output": rel(NO_DRIFT_OUT) if args.write else None,
        "blockers_output": rel(BLOCKERS_OUT) if args.write else None,
    }, indent=2))
    return 1 if args.validate and phase_gate["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
