#!/usr/bin/env python3
"""Build the SQL/finance-intelligence 500-ticker expansion readiness gate.

Report-only design proof. It checks the current WF78 scaleout baseline, keeps
the retired production answer path empty under SQL-first routing, proves
review-monitor/pilot separation, and emits the phased shard/freshness plan
before any 500-name import or consumer migration.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
OUT = TMP / "sql-500-ticker-expansion-design-gate.json"
COVERAGE = TMP / "finance-data-coverage-current.json"
PROVIDER_PROOF = TMP / "wf78-100-ticker-provider-runtime-proof.json"
REFRESH_100 = TMP / "finance-intelligence-state-refresh-100.json"
SOURCE_OPEN_CLEANUP = TMP / "wf78-review-monitor-source-open-cleanup-queue.json"

EXPECTED_DEPRECATED_PRODUCTION = 0
SUPPORTED_ACTIVE_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}
EXPECTED_LIVE_PILOT = 25
TARGET_500 = 500
TIER_TARGETS = {"A": 25, "B": 75, "C": 150, "D": 250}
ENRICHMENT_BATCH_1 = ["AAPL", "AVGO", "ASML", "COST", "CRM", "PANW", "TSM", "V", "UNH", "WMT"]
REQUIRED_ENRICHMENT_FAMILIES = [
    "official_fundamentals",
    "key_financial_metrics",
    "latest_earnings_performance",
    "price_band_stop",
    "technical_posture",
    "risk_register",
    "valuation_multiples",
    "revenue_growth_margins_fcf_debt",
    "analyst_consensus",
]

AUTHORITY = {
    "report_only": True,
    "broad_ticker_import_allowed": False,
    "production_answer_path_overwrite_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_trade_authority_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def scalar_or_none(conn: sqlite3.Connection, sql: str) -> Any:
    try:
        return scalar(conn, sql)
    except sqlite3.Error:
        return None


def tier_counts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT tier, universe_scope, COUNT(*) AS rows
            FROM universe
            GROUP BY tier, universe_scope
            ORDER BY tier, universe_scope
            """
        ).fetchall()
    except sqlite3.Error:
        return []
    return [{"tier": row[0], "universe_scope": row[1], "rows": row[2]} for row in rows]


def state_counts() -> dict[str, Any]:
    counts: dict[str, Any] = {"state_db": "tmp/finance-intelligence-state.sqlite", "exists": STATE_DB.exists()}
    if not STATE_DB.exists():
        return counts
    uri = STATE_DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        counts.update(
            {
                "integrity_check": scalar(conn, "PRAGMA integrity_check"),
                "universe_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM universe"),
                "all_ticker_sql_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM all_ticker_sql_rows"),
                "production_current_cards": scalar_or_none(conn, "SELECT COUNT(*) FROM current_ticker_cards"),
                "production_answer_path_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM universe WHERE production_answer_path_member = 1"),
                "review_monitor_thin_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM universe WHERE thin_monitor_row = 1 AND universe_scope = 'review_100_monitor'"),
                "fundamental_snapshot_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM fundamental_snapshot"),
                "analyst_snapshot_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM analyst_snapshot"),
                "ticker_family_status_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM ticker_family_status"),
                "card_registry_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM card_registry"),
                "missing_card_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM card_registry WHERE card_exists = 0"),
                "authority_forbidden_rows": scalar_or_none(conn, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json <> '[]'"),
                "pilot_fixtures": scalar_or_none(conn, "SELECT COUNT(*) FROM current_pilot_fixtures"),
                "live_pilot_candidates": scalar_or_none(conn, "SELECT COUNT(*) FROM current_live_pilot_candidates"),
                "pilot_production_overlap": scalar_or_none(conn, "SELECT COUNT(*) FROM current_live_pilot_candidates WHERE ticker IN (SELECT ticker FROM current_ticker_cards)"),
                "tier_counts": tier_counts(conn),
            }
        )
    return counts


def coverage_summary() -> dict[str, Any]:
    payload = load_json(COVERAGE)
    summary = payload.get("summary")
    return {
        "path": "tmp/finance-data-coverage-current.json",
        "exists": bool(payload),
        "status": payload.get("status"),
        "ticker_count_indexed": summary.get("ticker_count_indexed") if isinstance(summary, dict) else None,
        "source_artifacts_stale": summary.get("source_artifacts_stale") if isinstance(summary, dict) else None,
        "source_artifacts_present": summary.get("source_artifacts_present") if isinstance(summary, dict) else None,
    }


def provider_runtime_summary() -> dict[str, Any]:
    payload = load_json(PROVIDER_PROOF)
    summary = payload.get("summary")
    policy = payload.get("policy")
    return {
        "path": "tmp/wf78-100-ticker-provider-runtime-proof.json",
        "exists": bool(payload),
        "status": payload.get("status"),
        "candidate_count": summary.get("candidate_count") if isinstance(summary, dict) else None,
        "ok_count": summary.get("ok_count") if isinstance(summary, dict) else None,
        "error_count": summary.get("error_count") if isinstance(summary, dict) else None,
        "success_rate": summary.get("success_rate") if isinstance(summary, dict) else None,
        "total_runtime_seconds": summary.get("total_runtime_seconds") if isinstance(summary, dict) else None,
        "max_latency_seconds": summary.get("max_latency_seconds") if isinstance(summary, dict) else None,
        "runtime_budget_seconds": policy.get("runtime_budget_seconds") if isinstance(policy, dict) else None,
        "minimum_success_rate": policy.get("minimum_success_rate") if isinstance(policy, dict) else None,
        "circuit_breaker_opened": summary.get("circuit_breaker_opened") if isinstance(summary, dict) else None,
    }


def refresh_100_summary() -> dict[str, Any]:
    payload = load_json(REFRESH_100)
    scope = payload.get("refresh_scope")
    validation = payload.get("state_validation")
    state_summary = validation.get("summary") if isinstance(validation, dict) else {}
    return {
        "path": "tmp/finance-intelligence-state-refresh-100.json",
        "exists": bool(payload),
        "status": payload.get("status"),
        "active_tickers": scope.get("active_tickers") if isinstance(scope, dict) else None,
        "production_decision_grade_rows": scope.get("production_decision_grade_rows") if isinstance(scope, dict) else None,
        "review_monitor_thin_rows": scope.get("review_monitor_thin_rows") if isinstance(scope, dict) else None,
        "state_validation_status": validation.get("status") if isinstance(validation, dict) else None,
        "all_ticker_sql_rows": state_summary.get("all_ticker_sql_rows") if isinstance(state_summary, dict) else None,
    }


def source_open_cleanup_summary() -> dict[str, Any]:
    payload = load_json(SOURCE_OPEN_CLEANUP)
    summary = payload.get("summary")
    validation = payload.get("validation")
    return {
        "path": "tmp/wf78-review-monitor-source-open-cleanup-queue.json",
        "exists": bool(payload),
        "status": payload.get("status"),
        "validation_status": validation.get("status") if isinstance(validation, dict) else None,
        "review_monitor_cards": summary.get("review_monitor_cards") if isinstance(summary, dict) else None,
        "top_source_open_pass_count": summary.get("top_source_open_pass_count") if isinstance(summary, dict) else None,
        "promotion_ready_count": summary.get("promotion_ready_count") if isinstance(summary, dict) else None,
        "blocked_source_open_cleanup_count": summary.get("blocked_source_open_cleanup_count") if isinstance(summary, dict) else None,
        "authority_violation_count": summary.get("authority_violation_count") if isinstance(summary, dict) else None,
    }


def phased_approach() -> list[dict[str, Any]]:
    return [
        {
            "phase": "500-S0 baseline and authority freeze",
            "implementation_status": "implemented",
            "scope": "supported SQL-first active rows; retired production cards/path remain empty; review-monitor thin rows remain supported",
            "acceptance": ["all active rows routable", "retired production answer path remains empty", "no authority widening"],
        },
        {
            "phase": "500-S1 enrichment and source-open cleanup gate",
            "implementation_status": "enrichment_complete_cleanup_gate_active",
            "scope": "all 58 review-monitor cards exist; first bounded cleanup pass ranks top 15 source-open candidates",
            "acceptance": ["cleanup queue validates", "top pass stays bounded to 10-15", "promotion stays review-only until source-open blockers clear"],
        },
        {
            "phase": "500-S2 100-to-200 thin-row shard simulation",
            "implementation_status": "design_ready_no_import",
            "scope": "add candidate shards as proposed rows only; prove runtime/error budget before writes",
            "acceptance": ["A/B freshness unaffected", "C/D rows thin by default", "rollback and no-overwrite proof exists"],
        },
        {
            "phase": "500-S3 200/350 operating shard gate",
            "implementation_status": "design_ready_no_import",
            "scope": "separate A/B daily shards from C/D rotating shards",
            "acceptance": ["daily A/B continues if C/D degrades", "retry/backoff/circuit breaker policy explicit", "cron remains review-only"],
        },
        {
            "phase": "500-S4 500 operating mode",
            "implementation_status": "design_ready_no_import",
            "scope": "500 searchable/routable, about 100 priority-monitored, about 25 decision-grade",
            "acceptance": ["full cards generated selectively", "retail/customer use remains gated", "canon/portfolio stays owner-gated"],
        },
    ]


def shard_design() -> dict[str, Any]:
    return {
        "target_total": TARGET_500,
        "tier_targets": TIER_TARGETS,
        "shards": [
            {"name": "tier_a_decision_queue", "target": 25, "cadence": "daily plus intraday trigger", "data_depth": "full decision-grade card", "failure_mode": "block action claims, keep route visible"},
            {"name": "tier_b_priority_watch", "target": 75, "cadence": "daily technical, weekly fundamentals/analyst", "data_depth": "priority card with source-open gaps", "failure_mode": "do not promote to decision-grade"},
            {"name": "tier_c_sector_theme_monitor", "target": 150, "cadence": "weekly or event-triggered rotating shards", "data_depth": "thin row plus technical/price freshness", "failure_mode": "stays monitor-only"},
            {"name": "tier_d_broad_radar", "target": 250, "cadence": "monthly/quarterly rotation", "data_depth": "thin route row plus catalyst flags", "failure_mode": "drop/defer shard without affecting A/B"},
        ],
        "runtime_policy": {
            "preserve_a_b_before_c_d": True,
            "batch_size_default": 25,
            "max_parallel_provider_lanes": 4,
            "circuit_breaker": "open on provider/error-budget failure; never degrade SQL-first routing or resurrect retired production answer path",
            "source_open_required_before_material_claims": True,
        },
    }


def freshness_policy() -> list[dict[str, Any]]:
    return [
        {"tier": "A", "freshness": "price/technical daily plus intraday triggers; fundamentals weekly/event; official evidence on material claim"},
        {"tier": "B", "freshness": "price/technical daily; fundamentals/analyst weekly; risk register on promotion/event"},
        {"tier": "C", "freshness": "weekly or triggered; fundamentals/analyst required only before promotion"},
        {"tier": "D", "freshness": "monthly/quarterly broad radar; no decision-grade claims without promotion"},
    ]


def check(name: str, ok: bool, detail: Any, severity: str = "critical") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail, "severity": severity}


def active_count_supported(value: Any) -> bool:
    return isinstance(value, int) and value in SUPPORTED_ACTIVE_COUNTS


def review_monitor_count_supported(value: Any) -> bool:
    return isinstance(value, int) and value in SUPPORTED_REVIEW_MONITOR_COUNTS


def source_open_cleanup_queue_ready(value: dict[str, Any]) -> bool:
    return (
        value.get("status") in {"ok", "blocked"}
        and value.get("validation_status") in {"ok", "blocked"}
        and review_monitor_count_supported(value.get("review_monitor_cards"))
        and value.get("top_source_open_pass_count") == 15
        and value.get("authority_violation_count") == 0
    )


def build_report() -> dict[str, Any]:
    counts = state_counts()
    coverage = coverage_summary()
    provider = provider_runtime_summary()
    refresh = refresh_100_summary()
    source_open = source_open_cleanup_summary()
    checks = [
        check("state_db_exists", counts.get("exists") is True, counts.get("state_db")),
        check("state_db_integrity_ok", counts.get("integrity_check") == "ok", counts.get("integrity_check")),
        check("active_sql_rows_supported_scaleout_count", active_count_supported(counts.get("all_ticker_sql_rows")), {"actual": counts.get("all_ticker_sql_rows"), "supported": sorted(SUPPORTED_ACTIVE_COUNTS)}),
        check(
            "production_current_cards_empty_sql_first_wait_state",
            counts.get("production_current_cards") == EXPECTED_DEPRECATED_PRODUCTION,
            {
                "actual": counts.get("production_current_cards"),
                "expected": EXPECTED_DEPRECATED_PRODUCTION,
                "empty_production_scope_is_valid_wait_state": True,
                "source": "sql_first_300_cutover",
            },
        ),
        check(
            "production_answer_path_rows_empty_sql_first_wait_state",
            counts.get("production_answer_path_rows") == EXPECTED_DEPRECATED_PRODUCTION,
            {
                "actual": counts.get("production_answer_path_rows"),
                "expected": EXPECTED_DEPRECATED_PRODUCTION,
                "empty_production_scope_is_valid_wait_state": True,
                "source": "sql_first_300_cutover",
            },
        ),
        check("review_monitor_thin_rows_supported_scaleout_count", review_monitor_count_supported(counts.get("review_monitor_thin_rows")), {"actual": counts.get("review_monitor_thin_rows"), "supported": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS)}),
        check("fundamental_rows_for_supported_scaleout", active_count_supported(counts.get("fundamental_snapshot_rows")), {"actual": counts.get("fundamental_snapshot_rows"), "supported": sorted(SUPPORTED_ACTIVE_COUNTS)}),
        check("analyst_rows_for_supported_scaleout", active_count_supported(counts.get("analyst_snapshot_rows")), {"actual": counts.get("analyst_snapshot_rows"), "supported": sorted(SUPPORTED_ACTIVE_COUNTS)}),
        check("family_status_rows_for_supported_scaleout_x20", isinstance(counts.get("ticker_family_status_rows"), int) and counts.get("ticker_family_status_rows") == (counts.get("all_ticker_sql_rows") or 0) * 20, counts.get("ticker_family_status_rows")),
        check("live_pilot_isolated_25", counts.get("live_pilot_candidates") == EXPECTED_LIVE_PILOT, counts.get("live_pilot_candidates")),
        check("pilot_production_overlap_zero", counts.get("pilot_production_overlap") == 0, counts.get("pilot_production_overlap")),
        check("refresh_artifact_supported_scaleout_ok", refresh.get("status") == "ok" and active_count_supported(refresh.get("all_ticker_sql_rows")), refresh),
        check("coverage_registry_indexes_supported_scaleout", active_count_supported(coverage.get("ticker_count_indexed")), coverage, "warning"),
        check("provider_runtime_proof_review_monitor_ok", provider.get("status") == "ok" and review_monitor_count_supported(provider.get("ok_count")) and provider.get("success_rate") == 1.0, provider, "warning"),
        check(
            "source_open_cleanup_queue_top_15_ok",
            source_open_cleanup_queue_ready(source_open),
            source_open,
        ),
        check("shard_targets_sum_500", sum(TIER_TARGETS.values()) == TARGET_500, TIER_TARGETS),
        check("enrichment_batch_1_bounded_10", len(ENRICHMENT_BATCH_1) == 10, ENRICHMENT_BATCH_1),
    ]
    failed = [row for row in checks if not row["ok"] and row.get("severity") == "critical"]
    warnings = [row for row in checks if not row["ok"] and row.get("severity") == "warning"]
    return {
        "schema_version": "sql_500_ticker_expansion_design_gate.v2",
        "generated_at_utc": utc_now(),
        "status": "ready_for_source_open_cleanup" if not failed else "blocked",
        "authority_boundary": AUTHORITY,
        "current_state": counts,
        "coverage_summary": coverage,
        "provider_runtime_summary": provider,
        "refresh_100_summary": refresh,
        "source_open_cleanup_summary": source_open,
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed": len(failed), "warnings": len(warnings)},
        "phased_approach": phased_approach(),
        "staging_gates": phased_approach(),
        "shard_design": shard_design(),
        "freshness_policy": freshness_policy(),
        "enrichment_pilot": {
            "batch": "review_100_enrichment_batch_1",
            "tickers": ENRICHMENT_BATCH_1,
            "required_families": REQUIRED_ENRICHMENT_FAMILIES,
            "write_target": "tmp/ticker-intelligence-cards plus tmp/finance-intelligence-state.sqlite derived review rows only",
            "promotion_rule": "no decision-grade promotion until source-open evidence and validation pass",
        },
        "source_open_cleanup_gate": {
            "artifact": "tmp/wf78-review-monitor-source-open-cleanup-queue.json",
            "top_pass_count": source_open.get("top_source_open_pass_count"),
            "promotion_ready_count": source_open.get("promotion_ready_count"),
            "blocked_source_open_cleanup_count": source_open.get("blocked_source_open_cleanup_count"),
            "promotion_rule": "review-monitor ticker promotion remains blocked until source-open cleanup gate reports promotion_ready for that ticker",
        },
        "implementation_status": {
            "readiness_shard_gate_implemented": True,
            "actual_500_import_performed": False,
            "cron_schedule_changed": False,
            "canon_or_portfolio_mutation_performed": False,
            "enrichment_batches_completed": True,
            "ready_for_source_open_cleanup": not failed,
        },
        "next_safe_action": "Work the top 15 source-open cleanup queue; do not broaden to 500 import or promote review-monitor tickers until source-open blockers clear and this gate remains clean.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    report = build_report()
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "validation": report["validation"]["status"], "output": args.output.as_posix() if args.write else None}, indent=2))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
