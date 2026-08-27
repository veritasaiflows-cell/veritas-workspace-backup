#!/usr/bin/env python3
"""Define proof-joined production-grade answer eligibility.

This is a review-only policy gate. It reads the finance SQL canon and writes a
proof packet showing which tickers are production-grade after current router,
coverage, confidence, and authority proof agree. The legacy production 42 and
label-only Tier A/A-READY sets are reported only as compatibility surfaces.

It performs no SQL writes, no universe mutation, no portfolio/canon mutation,
and grants no capital, paper/live, account, customer, or approval authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json
from finance_sql_canon_access import _current_proof_state, _validated_production_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_OUT = ROOT / "tmp" / "finance-production-grade-policy-gate.json"
SCHEMA = "veritas.finance_production_grade_policy_gate.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "policy_gate_only": True,
    "automated_non_capital_routing_allowed": True,
    "sql_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "answer_consumer_cutover_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "policy_gate_only", "automated_non_capital_routing_allowed"}
REQUIRED_FALSE_FLAGS = set(AUTHORITY_BOUNDARY) - REQUIRED_TRUE_FLAGS


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_int(value: Any) -> int:
    return int(value or 0)


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def build_report(db_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if not db_path.exists():
        add_check(checks, "db_exists", False, rel(db_path))
        return finish_report(db_path, checks, {}, [], [], [], {})

    with connect_readonly(db_path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        counts = {
            "securities": as_int(conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0]),
            "universe_membership": as_int(conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0]),
            "tier_routing_state": as_int(conn.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0]),
            "reference_levels": as_int(conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0]),
            "retired_legacy_42_answer_path": as_int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM answer_path_scope
                    WHERE answer_scope LIKE 'legacy_%'
                      AND production_card_generation_allowed=1
                    """
                ).fetchone()[0]
            ),
            "production_scope_member": as_int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM current_sql_canon_routing
                    WHERE production_scope_member=1
                    """
                ).fetchone()[0]
            ),
            "tier_a_ready": as_int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM tier_routing_state
                    WHERE auto_tier='Tier A'
                      AND auto_state='A-READY'
                    """
                ).fetchone()[0]
            ),
        }
        tier_a_ready_rows = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    r.ticker,
                    r.name,
                    r.instrument_type,
                    r.sector,
                    r.industry,
                    r.universe_scope,
                    r.legacy_tier,
                    r.production_scope_member,
                    r.production_scope_source,
                    r.sql_tier,
                    r.sql_tier_state,
                    r.tier_decision_scope,
                    r.auto_tier,
                    r.auto_state,
                    r.route_priority,
                    r.has_production_card,
                    r.provider_status,
                    r.answer_scope,
                    r.production_card_generation_allowed AS legacy_answer_path_allowed,
                    r.reference_price_low,
                    r.reference_price_high,
                    r.reference_invalidation_level,
                    r.reference_band_status,
                    f.resolution_state,
                    f.required_depth,
                    f.card_missing_or_stale_count,
                    f.source_confidence_class,
                    t.capital_deployment_approved,
                    t.trade_or_execution_approved,
                    t.requires_separate_capital_or_execution_approval
                FROM current_sql_canon_routing AS r
                JOIN tier_routing_state AS t USING (ticker)
                LEFT JOIN evidence_freshness AS f USING (ticker)
                WHERE r.auto_tier='Tier A'
                  AND r.auto_state='A-READY'
                ORDER BY r.route_priority DESC, r.ticker
                """
            )
        )
        production_review_rows = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    r.ticker,
                    r.name,
                    r.instrument_type,
                    r.sector,
                    r.industry,
                    r.universe_scope,
                    r.legacy_tier,
                    r.production_scope_member,
                    r.production_scope_source,
                    r.sql_tier,
                    r.sql_tier_state,
                    r.tier_decision_scope,
                    r.auto_tier,
                    r.auto_state,
                    r.route_priority,
                    r.has_production_card,
                    r.provider_status,
                    r.answer_scope,
                    r.production_card_generation_allowed AS legacy_answer_path_allowed,
                    f.resolution_state,
                    f.required_depth,
                    f.card_missing_or_stale_count,
                    f.source_confidence_class,
                    t.capital_deployment_approved,
                    t.trade_or_execution_approved,
                    t.requires_separate_capital_or_execution_approval
                FROM current_sql_canon_routing AS r
                JOIN tier_routing_state AS t USING (ticker)
                LEFT JOIN evidence_freshness AS f USING (ticker)
                WHERE r.auto_tier IN ('Tier A', 'Tier B')
                ORDER BY CASE r.auto_tier WHEN 'Tier A' THEN 1 WHEN 'Tier B' THEN 2 ELSE 3 END,
                         r.route_priority DESC,
                         r.ticker
                """
            )
        )
        proof = _current_proof_state()
        production_grade_rows = [row for row in tier_a_ready_rows if _validated_production_row(row, proof)]
        tier_a_nonready_rows = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    r.ticker,
                    r.name,
                    r.universe_scope,
                    r.legacy_tier,
                    r.production_scope_member,
                    r.production_scope_source,
                    r.sql_tier,
                    r.sql_tier_state,
                    r.tier_decision_scope,
                    r.auto_tier,
                    r.auto_state,
                    r.route_priority,
                    r.has_production_card,
                    r.answer_scope,
                    r.production_card_generation_allowed AS legacy_answer_path_allowed,
                    f.card_missing_or_stale_count,
                    f.source_confidence_class
                FROM current_sql_canon_routing AS r
                LEFT JOIN evidence_freshness AS f USING (ticker)
                WHERE r.auto_tier='Tier A'
                  AND COALESCE(r.auto_state, '') <> 'A-READY'
                ORDER BY r.route_priority DESC, r.ticker
                """
            )
        )
        legacy_only_rows = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    r.ticker,
                    r.name,
                    r.universe_scope,
                    r.legacy_tier,
                    r.production_scope_member,
                    r.production_scope_source,
                    r.sql_tier,
                    r.sql_tier_state,
                    r.tier_decision_scope,
                    r.auto_tier,
                    r.auto_state,
                    r.production_card_generation_allowed AS legacy_answer_path_allowed
                FROM current_sql_canon_routing AS r
                WHERE r.answer_scope LIKE 'legacy_%'
                  AND r.production_card_generation_allowed=1
                  AND NOT (r.auto_tier='Tier A' AND r.auto_state='A-READY')
                ORDER BY r.ticker
                """
            )
        )
        false_authority_count = as_int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM tier_routing_state
                WHERE capital_deployment_approved != 0
                   OR trade_or_execution_approved != 0
                   OR requires_separate_capital_or_execution_approval != 1
                """
            ).fetchone()[0]
        )
        row_authority_violations = [
            row["ticker"]
            for row in production_grade_rows
            if as_int(row.get("capital_deployment_approved")) != 0
            or as_int(row.get("trade_or_execution_approved")) != 0
            or as_int(row.get("requires_separate_capital_or_execution_approval")) != 1
        ]
        missing_reference_rows = [
            row["ticker"]
            for row in production_grade_rows
            if row.get("reference_price_low") is None
            or row.get("reference_price_high") is None
            or row.get("reference_invalidation_level") is None
        ]
        stale_or_incomplete_rows = [
            row["ticker"]
            for row in production_grade_rows
            if as_int(row.get("card_missing_or_stale_count")) > 0
        ]

    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    add_check(checks, "integrity_ok", integrity == "ok", integrity)
    add_check(checks, "foreign_keys_ok", not fk_issues, len(fk_issues))
    add_check(checks, "core_dynamic_rows_present", counts.get("securities") in {100, 200, 300, 400, 500} and counts.get("universe_membership") == counts.get("securities"), counts)
    add_check(
        checks,
        "production_grade_candidates_fail_closed_to_current_proof",
        len(production_grade_rows) <= len(tier_a_ready_rows),
        {"validated": [row["ticker"] for row in production_grade_rows], "label_only": [row["ticker"] for row in tier_a_ready_rows]},
    )
    add_check(checks, "production_grade_reference_levels_complete", not missing_reference_rows, missing_reference_rows)
    add_check(checks, "all_rows_preserve_no_execution_authority", false_authority_count == 0 and not row_authority_violations, {"false_authority_count": false_authority_count, "candidate_violations": row_authority_violations})
    add_check(
        checks,
        "production_grade_freshness_needs_source_open_before_material_claim",
        not stale_or_incomplete_rows,
        stale_or_incomplete_rows,
        "warning",
    )

    summary = {
        **counts,
        "production_grade_definition": "validated proof-joined Tier A/A-READY with current router, coverage, confidence, and authority gates",
        "production_grade_candidate_count": len(production_grade_rows),
        "production_grade_tickers": [row["ticker"] for row in production_grade_rows],
        "dynamic_production_review_candidate_count": len(production_review_rows),
        "dynamic_production_review_tickers": [row["ticker"] for row in production_review_rows],
        "dynamic_production_review_definition": "SQL-first current Tier A/B router surface; review-only candidate scope before strict production-grade answer eligibility.",
        "legacy_tier_a_ready_compatibility_count": len(tier_a_ready_rows),
        "legacy_tier_a_ready_compatibility_tickers": [row["ticker"] for row in tier_a_ready_rows],
        "coverage_gate_decision_grade_allowed_count": as_int((proof.get("coverage_gate", {}).get("summary") or {}).get("decision_grade_allowed_count")),
        "auto_router_a_ready_count": len([row for row in (proof.get("router_rows") or {}).values() if row.get("auto_tier") == "Tier A" and row.get("auto_state") == "A-READY"]),
        "tier_a_nonready_count": len(tier_a_nonready_rows),
        "legacy_42_compatibility_only_count": counts["retired_legacy_42_answer_path"],
        "production_scope_member_count": counts["production_scope_member"],
        "production_scope_definition": "proof_joined_routing_tier_ab_fresh_confident_card_coverage_authority",
        "legacy_42_rows_not_production_grade_count": len(legacy_only_rows),
        "legacy_42_rows_not_production_grade": [row["ticker"] for row in legacy_only_rows],
        "answer_consumer_cutover_allowed": False,
        "typed_access_default_cutover": "production_answer_tickers_returns_validated_proof_joined_set",
        "next_safe_action": "Use dynamic Tier A/B production-review scope for attention/routing, while keeping strict production-grade answer eligibility fail-closed until current coverage, router, confidence, freshness, and authority proof all clear.",
    }
    policy = {
        "strategic_production_boundary": "Validated Tier A readiness from SQL plus current router, coverage, confidence, and authority proof",
        "production_review_boundary": "Dynamic SQL-first Tier A/B router surface for review/attention only; not answer authority, capital approval, or execution approval.",
        "legacy_42_role": "hard_retired_from_active_sql_answer_authority",
        "tier_a_ready_means": "label-only compatibility until proof-joined gates clear; not capital deployment or execution approval",
        "material_claim_rule": "source-open/freshness proof still required before material finance claims",
        "promotion_rule": "review-monitor tickers can become production-grade only after WF78 routing/evidence repair moves them to fresh Tier A/A-READY and coverage/confidence gates allow decision-grade claims",
        "execution_rule": "capital/trade/paper/live action remains owner-gated even for A-READY rows",
    }
    return finish_report(db_path, checks, summary, production_grade_rows, tier_a_nonready_rows, legacy_only_rows, policy, production_review_rows)


def finish_report(
    db_path: Path,
    checks: list[dict[str, Any]],
    summary: dict[str, Any],
    production_grade_rows: list[dict[str, Any]],
    tier_a_nonready_rows: list[dict[str, Any]],
    legacy_only_rows: list[dict[str, Any]],
    policy: dict[str, Any],
    production_review_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    production_review_rows = production_review_rows or []
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "db_path": rel(db_path),
        "purpose": "Replace legacy 42 and label-only Tier A/A-READY as strategic production boundaries with a proof-joined production-grade policy gate.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "policy": policy,
        "production_grade_rows": production_grade_rows,
        "dynamic_production_review_rows": production_review_rows,
        "tier_a_nonready_rows": tier_a_nonready_rows,
        "legacy_42_compatibility_only_rows": legacy_only_rows,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "No SQL data/schema mutation.",
            "No universe/canon/portfolio mutation.",
            "No answer consumer cutover from this packet alone.",
            "No capital deployment, trade approval, paper/live execution, brokerage/account action, customer delivery, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    db_path = args.db if args.db.is_absolute() else ROOT / args.db
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    report = build_report(db_path)
    if args.write:
        atomic_write_json(out_path, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "out": rel(out_path),
                "summary": report.get("summary"),
                "validation": {
                    "status": report["validation"]["status"],
                    "errors": len(report["validation"]["errors"]),
                    "warnings": len(report["validation"]["warnings"]),
                },
            },
            indent=2,
        )
    )
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
