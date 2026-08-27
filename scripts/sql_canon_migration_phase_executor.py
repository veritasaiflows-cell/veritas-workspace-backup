#!/usr/bin/env python3
"""Build an executable phase report for the SQL-canon migration.

This is a proof/classification tool. It does not edit consumers, write SQL,
archive files, retire fallbacks, change cron, or promote answer ownership.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_INVENTORY = ROOT / "tmp" / "sql-canon-consumer-inventory.json"
DEFAULT_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"
DEFAULT_BURNDOWN = ROOT / "tmp" / "finance-sql-consumer-migration-burndown.json"
DEFAULT_RETIREMENT = ROOT / "tmp" / "canonical-finance-data-plane-retirement-readiness.json"
DEFAULT_TRADE_GRADE_ASSEMBLER = ROOT / "tmp" / "trade-grade-full-answer-assembler.json"
DEFAULT_ANSWER_PATH_AB = ROOT / "tmp" / "sql-canon-answer-path-ab-harness.json"
DEFAULT_PYTHON_RETIREMENT = ROOT / "tmp" / "python-go-sql-helper-retirement-gate.json"
DEFAULT_CRON_CONTROL = ROOT / "tmp" / "cron-control-packet.json"
DEFAULT_DB_LIFECYCLE = ROOT / "tmp" / "db-lifecycle-manifest.json"
DEFAULT_OUT = ROOT / "tmp" / "sql-canon-migration-phase-executor.json"
DEFAULT_DECISION_OUT = ROOT / "tmp" / "sql-canon-migration-owner-decision-packet.json"

REQUIRED_PROOF_ARTIFACTS = [
    ROOT / "tmp" / "finance-sql-canon-access-validation.json",
    ROOT / "tmp" / "sql-canon-consumer-inventory.json",
    ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json",
    ROOT / "tmp" / "finance-sql-consumer-migration-burndown.json",
    ROOT / "tmp" / "canonical-finance-data-plane-retirement-readiness.json",
    ROOT / "tmp" / "trade-grade-full-answer-assembler.json",
    ROOT / "tmp" / "sql-canon-answer-path-ab-harness.json",
    ROOT / "tmp" / "python-go-sql-helper-retirement-gate.json",
    ROOT / "tmp" / "cron-control-packet.json",
]

AUTHORITY_BOUNDARY = {
    "classification_only": True,
    "consumer_files_modified": False,
    "sql_writes_performed": False,
    "archive_moves_performed": False,
    "hard_delete_allowed": False,
    "schema_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "source_feeder_retirement_allowed": False,
    "python_fallback_retirement_allowed": False,
    "answer_path_sql_first_promotion_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing_json:{rel(path)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid_json:{rel(path)}:{exc}")
        return {}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def registry_rows(db_path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not db_path.exists():
        errors.append(f"missing_db:{rel(db_path)}")
        return []
    with connect(db_path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            errors.append(f"db_integrity:{integrity}")
        table = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='consumer_migration_registry'
            """
        ).fetchone()
        if not table:
            errors.append("missing_table:consumer_migration_registry")
            return []
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM consumer_migration_registry
                ORDER BY priority, migration_lane, consumer_path
                """
            )
        ]


def lane_batches(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []
    for lane in backlog.get("recommended_parallel_lanes") or []:
        if not isinstance(lane, dict):
            continue
        paths = sorted(str(path).replace("\\", "/") for path in lane.get("paths", []) if path)
        batches.append(
            {
                "lane": lane.get("lane"),
                "consumer_count": len(paths),
                "paths": paths,
                "status": lane.get("status", "not_started"),
            }
        )
    return batches


def summarize_registry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "cutover_state_counts": dict(sorted(Counter(row.get("cutover_state") for row in rows).items())),
        "lane_state_counts": {
            f"{lane}:{state}": count
            for (lane, state), count in sorted(Counter((row.get("migration_lane"), row.get("cutover_state")) for row in rows).items())
        },
        "raw_sql_needs_review_count": sum(1 for row in rows if row.get("raw_sql_needs_review")),
        "parity_required_count": sum(1 for row in rows if row.get("parity_required")),
        "fallback_required_count": sum(1 for row in rows if row.get("fallback_required")),
    }


def shadow_promotion_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    shadow = [row for row in rows if row.get("cutover_state") == "sql_shadow_validated"]
    eligible = [
        row
        for row in shadow
        if row.get("migration_lane") == "test_parity_lane"
        and not row.get("raw_sql_needs_review")
        and not row.get("parity_required")
        and row.get("fallback_required")
    ]
    blocked = [row for row in shadow if row not in eligible]
    return {
        "shadow_validated_count": len(shadow),
        "eligible_registry_only_promotion_count": len(eligible),
        "blocked_count": len(blocked),
        "eligible_consumers": [row.get("consumer_path") for row in eligible],
        "blocked_consumers": [
            {
                "consumer_path": row.get("consumer_path"),
                "migration_lane": row.get("migration_lane"),
                "raw_sql_needs_review": bool(row.get("raw_sql_needs_review")),
                "parity_required": bool(row.get("parity_required")),
                "fallback_required": bool(row.get("fallback_required")),
            }
            for row in blocked
        ],
        "authority_note": (
            "Eligible promotion is registry maintenance only for test/parity consumers. "
            "It does not change answer behavior or retire fallbacks."
        ),
    }


def raw_sql_classification(inventory: dict[str, Any]) -> dict[str, Any]:
    consumers = inventory.get("consumers") or []
    raw_rows = [row for row in consumers if row.get("raw_sql_present", row.get("raw_sql_needs_review"))]
    review_rows = [row for row in raw_rows if row.get("raw_sql_needs_review")]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        ctype = row.get("consumer_type")
        imports = set(row.get("imports") or [])
        if ctype == "source_producer_or_loader":
            bucket = "source_producer_raw_sql_retained_or_partition"
        elif ctype == "test_or_parity_consumer":
            bucket = "test_fixture_raw_sql_review"
        elif ctype == "pm_cockpit_consumer":
            bucket = "pm_cockpit_raw_sql_review"
        elif ctype == "production_or_answer_path_consumer" and "finance_sql_canon_access" in imports:
            bucket = "p0_answer_path_typed_access_plus_raw_sql_review"
        elif ctype == "production_or_answer_path_consumer":
            bucket = "p0_answer_path_typed_replacement_candidate"
        else:
            bucket = "typed_replacement_review"
        buckets[bucket].append(row)

    actionable = []
    for bucket_name in [
        "p0_answer_path_typed_access_plus_raw_sql_review",
        "p0_answer_path_typed_replacement_candidate",
        "pm_cockpit_raw_sql_review",
        "typed_replacement_review",
    ]:
        actionable.extend(row for row in buckets.get(bucket_name, []) if row.get("raw_sql_needs_review"))

    return {
        "raw_sql_present_count": len(raw_rows),
        "raw_sql_review_count": len(review_rows),
        "bucket_counts": {name: len(rows) for name, rows in sorted(buckets.items())},
        "actionable_typed_replacement_review_count": len(actionable),
        "source_producer_raw_sql_count": len(buckets.get("source_producer_raw_sql_retained_or_partition", [])),
        "raw_sql_rows": [
            {
                "path": row.get("path"),
                "priority": row.get("priority"),
                "consumer_type": row.get("consumer_type"),
                "bucket": next((name for name, rows in buckets.items() if row in rows), "unknown"),
                "raw_sql_needs_review": bool(row.get("raw_sql_needs_review")),
                "raw_sql_classification": row.get("raw_sql_classification"),
                "imports": row.get("imports") or [],
                "migration_action": row.get("migration_action"),
            }
            for row in raw_rows
        ],
    }


def proof_artifacts(paths: list[Path]) -> list[dict[str, Any]]:
    return [{"path": rel(path), "exists": path.exists()} for path in paths]


def sample_paths(paths: list[str], limit: int = 12) -> list[str]:
    return sorted(paths)[:limit]


def inventory_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in inventory.get("consumers") or [] if isinstance(row, dict)]


def partition_source_producers(inventory: dict[str, Any], retirement: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in inventory_rows(inventory)
        if row.get("consumer_type") == "source_producer_or_loader"
    ]
    partitions: dict[str, list[dict[str, Any]]] = {
        "required_finance_feeders": [],
        "validators_and_proof_writers": [],
        "cron_dashboards_and_operator_surfaces": [],
        "lifecycle_archive_governance": [],
        "supporting_indexes_routes_and_tools": [],
    }

    finance_groups = {
        "answer_path",
        "canon_cache_sql",
        "finance_canon_sql",
        "portfolio_owner_notes",
        "ticker_cards",
        "universe_state",
        "wf77_state",
        "wf78_state",
        "wf75_product",
    }
    validator_markers = ("test_", "validator", "guard", "gate", "parity", "readiness", "audit", "proof")
    cron_markers = ("cron", "pm_", "dashboard", "cockpit", "operator", "today_card", "control_packet")
    lifecycle_markers = ("archive", "delete", "lifecycle", "retirement", "cleanup", "manifest")

    for row in rows:
        path = str(row.get("path", ""))
        path_lower = path.lower()
        groups = set(row.get("groups") or [])
        if path_lower.startswith("scripts/test_") or any(marker in path_lower for marker in validator_markers):
            bucket = "validators_and_proof_writers"
        elif any(marker in path_lower for marker in cron_markers):
            bucket = "cron_dashboards_and_operator_surfaces"
        elif any(marker in path_lower for marker in lifecycle_markers):
            bucket = "lifecycle_archive_governance"
        elif groups & finance_groups:
            bucket = "required_finance_feeders"
        else:
            bucket = "supporting_indexes_routes_and_tools"
        partitions[bucket].append(row)

    duplicate_ready = int((retirement.get("summary") or {}).get("duplicate_surface_retirement_ready_count") or 0)
    source_ready = int((retirement.get("summary") or {}).get("source_feeder_retirement_ready_count") or 0)
    return {
        "status": "ready_for_review",
        "source_producer_count": len(rows),
        "partition_counts": {name: len(items) for name, items in partitions.items()},
        "partitions": {
            name: {
                "count": len(items),
                "sample_paths": sample_paths([str(row.get("path")) for row in items if row.get("path")]),
            }
            for name, items in partitions.items()
        },
        "retirement_candidate_count": 0,
        "duplicate_surface_retirement_ready_count": duplicate_ready,
        "source_feeder_retirement_ready_count": source_ready,
        "retirement_recommendation": "retain_all_source_producers_pending_exact_retirement_gate",
        "why_no_retirement": [
            "canonical_finance_data_plane_retirement_readiness reports 0 source-feeder retirement-ready surfaces",
            "duplicate-surface retirement readiness is 0",
            "source producers still own proof/feed/write surfaces rather than duplicate answer authority",
        ],
    }


def answer_path_readiness(
    registry: dict[str, Any],
    trade_grade: dict[str, Any],
    answer_path_ab: dict[str, Any],
    retirement: dict[str, Any],
) -> dict[str, Any]:
    lane_counts = registry.get("lane_state_counts") or {}
    answer_guarded = int(lane_counts.get("answer_path_parity_lane:sql_primary_guarded", 0) or 0)
    trade_summary = trade_grade.get("summary") or {}
    ab_boundary = answer_path_ab.get("authority_boundary") or {}
    retirement_summary = retirement.get("summary") or {}
    blockers = []
    if registry.get("fallback_required_count"):
        blockers.append(f"fallback_required_count={registry.get('fallback_required_count')}")
    if registry.get("parity_required_count"):
        blockers.append(f"parity_required_count={registry.get('parity_required_count')}")
    if ab_boundary.get("rich_answer_claim_cutover_allowed") is False:
        blockers.append("answer_path_ab_harness_is_structural_only")
    if retirement_summary.get("source_feeder_retirement_ready_count", 0) == 0:
        blockers.append("source_feeders_retained")
    if retirement_summary.get("duplicate_surface_retirement_ready_count", 0) == 0:
        blockers.append("duplicate_surface_retirement_not_ready")

    return {
        "status": "review_ready_not_promotable",
        "answer_path_registry_sql_primary_guarded_count": answer_guarded,
        "full_answer_assembler_status": trade_grade.get("status"),
        "full_answer_built_count": trade_summary.get("full_answer_built_count"),
        "full_answer_validation_error_count": trade_summary.get("validation_error_count"),
        "full_answer_validation_warning_count": trade_summary.get("validation_warning_count"),
        "strategic_production_answer_count": trade_summary.get("strategic_production_answer_count"),
        "strategic_production_answer_definition": trade_summary.get("strategic_production_answer_definition"),
        "legacy_compatibility_answer_count": trade_summary.get("legacy_compatibility_answer_count"),
        "answer_path_ab_status": answer_path_ab.get("status"),
        "answer_path_ab_scope": answer_path_ab.get("scope"),
        "answer_path_ab_structural_only": bool(ab_boundary.get("structural_scope_only")),
        "sql_first_promotion_allowed_now": False,
        "required_before_promotion": [
            "rich-answer A/B parity contract beyond structural legacy-42 scope",
            "explicit fallback/source-open contract showing fallback can remain or a separate retirement gate approves removal",
            "source-feeder and duplicate-surface retirement readiness greater than 0 only through exact owner-approved gates",
            "separate SQL-first/front-door promotion approval packet",
        ],
        "blockers": blockers,
    }


def python_fallback_audit(registry: dict[str, Any], python_retirement: dict[str, Any]) -> dict[str, Any]:
    summary = python_retirement.get("summary") or {}
    return {
        "status": "retain_python_fallback",
        "fallback_required_registry_count": registry.get("fallback_required_count"),
        "python_retirement_gate_status": python_retirement.get("status"),
        "python_fallback_retained": summary.get("python_fallback_retained"),
        "retirement_ready": summary.get("retirement_ready"),
        "retire_python_now_count": summary.get("retire_python_now_count"),
        "retirement_blockers": summary.get("retirement_blockers"),
        "default_route_python_owner": summary.get("default_route_python_owner"),
        "python_file_delete_allowed": summary.get("python_file_delete_allowed"),
        "recommendation": "do_not_retire_python_fallback_or_delete_python_helpers",
    }


def duplicate_surface_cleanup_plan(retirement: dict[str, Any], db_lifecycle: dict[str, Any]) -> dict[str, Any]:
    summary = retirement.get("summary") or {}
    db_summary = db_lifecycle.get("summary") or {}
    return {
        "status": "planning_only_no_apply",
        "retirement_readiness_status": retirement.get("status"),
        "surface_count": summary.get("surface_count"),
        "archive_ready_count": summary.get("archive_ready_count"),
        "delete_ready_count": summary.get("delete_ready_count"),
        "apply_allowed_count": summary.get("apply_allowed_count"),
        "source_feeder_retirement_ready_count": summary.get("source_feeder_retirement_ready_count"),
        "duplicate_surface_retirement_ready_count": summary.get("duplicate_surface_retirement_ready_count"),
        "db_lifecycle_status": db_lifecycle.get("status"),
        "db_lifecycle_summary": {
            key: db_summary.get(key)
            for key in [
                "archive_candidate_count",
                "archive_ready_count",
                "unknown_count",
                "integrity_error_count",
                "archived_count",
            ]
            if key in db_summary
        },
        "schema_cleanup_allowed_now": False,
        "archive_delete_apply_allowed_now": False,
        "recommendation": "no_duplicate_surface_or_schema_cleanup_apply_until_exact_lifecycle_packet",
    }


def cron_impact_review(inventory: dict[str, Any], cron_control: dict[str, Any]) -> dict[str, Any]:
    rows = inventory_rows(inventory)
    cron_consumers = [
        row
        for row in rows
        if row.get("consumer_type") in {"cron_or_governance_consumer", "pm_cockpit_consumer"}
        or "cron_governance" in set(row.get("groups") or [])
        or "cron" in str(row.get("path", "")).lower()
    ]
    raw_review = [row for row in cron_consumers if row.get("raw_sql_needs_review")]
    summary = cron_control.get("summary") or {}
    boundary = cron_control.get("authority_boundary") or {}
    return {
        "status": "no_schedule_change_recommended",
        "cron_or_pm_consumer_count": len(cron_consumers),
        "cron_raw_sql_review_count": len(raw_review),
        "cron_control_status": cron_control.get("status"),
        "enabled_job_count": summary.get("enabled_job_count"),
        "blocked_count": summary.get("blocked_count"),
        "escalation_signal_count": summary.get("escalation_signal_count"),
        "stale_count": summary.get("stale_count"),
        "sql_canon_status": summary.get("sql_canon_status"),
        "sql_canon_production_answer_count": summary.get("sql_canon_production_answer_count"),
        "cron_schedule_mutation_allowed": bool(boundary.get("cron_schedule_mutation_allowed")),
        "recommendation": "do_not_mutate_cron_for_this_sql_migration_packet",
        "note": "Cron has unrelated blocked/attention signals, but no SQL migration schedule mutation is justified by this packet.",
    }


def owner_decision_packet(payload: dict[str, Any]) -> dict[str, Any]:
    phases = payload["phase_readiness"]
    source_partition = payload["source_producer_partition"]
    answer_path = payload["sql_first_front_door_readiness"]
    fallback = payload["python_fallback_retirement_audit"]
    duplicate = payload["duplicate_surface_schema_cleanup_plan"]
    cron = payload["cron_impact_review"]
    return {
        "schema": "veritas.sql_canon_migration_owner_decision_packet.v1",
        "generated_at_utc": payload["generated_at_utc"],
        "status": "owner_decision_required",
        "source_packet": rel(DEFAULT_OUT),
        "phase_readiness": phases,
        "recommendation": "continue proof_and_classification_only; do_not_promote_or_retire_yet",
        "decisions": [
            {
                "decision_id": "source_feeder_retirement",
                "recommended_decision": "hold",
                "eligible_count": source_partition["source_feeder_retirement_ready_count"],
                "approval_required_before_action": True,
                "reason": "0 source-feeder retirement-ready surfaces; source producers remain active proof/feed/write surfaces.",
            },
            {
                "decision_id": "python_fallback_retirement",
                "recommended_decision": "hold",
                "eligible_count": fallback.get("retire_python_now_count"),
                "approval_required_before_action": True,
                "reason": "Python fallback is retained and the retirement gate is not ready.",
            },
            {
                "decision_id": "sql_first_front_door_promotion",
                "recommended_decision": "hold",
                "eligible": False,
                "approval_required_before_action": True,
                "reason": "; ".join(answer_path.get("blockers") or []),
            },
            {
                "decision_id": "duplicate_surface_schema_cleanup",
                "recommended_decision": "hold",
                "eligible_count": duplicate.get("duplicate_surface_retirement_ready_count"),
                "approval_required_before_action": True,
                "reason": "No archive/delete/apply candidate is currently ready.",
            },
            {
                "decision_id": "cron_schedule_change",
                "recommended_decision": "no_change",
                "eligible": False,
                "approval_required_before_action": True,
                "reason": cron.get("recommendation"),
            },
        ],
        "approved_without_further_owner_decision": [
            "continue local proof-only classification packets",
            "refresh route/capsule/control packets",
            "run validators and readiness audits",
        ],
        "blocked_without_exact_owner_approval": [
            "source-feeder retirement",
            "Python fallback retirement or file deletion",
            "SQL-first/front-door promotion",
            "duplicate-surface archive/delete/schema cleanup apply",
            "cron schedule mutation",
            "portfolio/canon/cash/sizing/risk mutation",
            "capital deployment",
            "paper/live/account/brokerage action",
        ],
        "validation": payload["validation"],
        "authority_boundary": payload["authority_boundary"],
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    inventory = load_json(args.inventory, errors)
    backlog = load_json(args.backlog, errors)
    burndown = load_json(args.burndown, errors)
    retirement = load_json(args.retirement, errors)
    trade_grade = load_json(args.trade_grade_assembler, errors)
    answer_path_ab = load_json(args.answer_path_ab_harness, errors)
    python_retirement = load_json(args.python_retirement, errors)
    cron_control = load_json(args.cron_control, errors)
    db_lifecycle = load_json(args.db_lifecycle, errors)
    rows = registry_rows(args.db, errors)
    missing_proof = [rel(path) for path in REQUIRED_PROOF_ARTIFACTS if not path.exists()]
    if missing_proof:
        warnings.append("missing_recommended_proof:" + ",".join(missing_proof))

    registry = summarize_registry(rows)
    shadow = shadow_promotion_candidates(rows)
    raw_sql = raw_sql_classification(inventory)
    batches = lane_batches(backlog)
    batch_counts = {str(row.get("lane")): int(row.get("consumer_count", 0)) for row in batches}
    source_partition = partition_source_producers(inventory, retirement)
    answer_path = answer_path_readiness(registry, trade_grade, answer_path_ab, retirement)
    fallback = python_fallback_audit(registry, python_retirement)
    duplicate_cleanup = duplicate_surface_cleanup_plan(retirement, db_lifecycle)
    cron_review = cron_impact_review(inventory, cron_control)

    burndown_summary = burndown.get("summary") or {}
    if burndown_summary:
        expected_registry_total = burndown_summary.get("registry_total")
        if expected_registry_total is not None and int(expected_registry_total) != registry["row_count"]:
            warnings.append(f"registry_total_mismatch:burndown={expected_registry_total}:db={registry['row_count']}")

    phase_readiness = {
        "phase_1_classification_freeze": "ready" if not errors and batches else "blocked",
        "phase_2_typed_access_guard_expansion": "review_ready",
        "phase_3_shadow_registry_promotion": (
            "ready"
            if not errors
            and shadow["eligible_registry_only_promotion_count"] > 0
            and shadow["blocked_count"] == 0
            else "blocked"
        ),
        "phase_4_raw_sql_review": "ready" if raw_sql["raw_sql_review_count"] else "empty",
        "phase_5_source_producer_partition": "ready" if raw_sql["source_producer_raw_sql_count"] else "empty",
        "phase_6_p0_answer_path_closeout": "blocked_pending_exact_promotion_gate",
        "phase_7_burndown_closeout": "ready_as_review_only_packet",
        "phase_8_owner_decision_packet": "ready",
    }

    next_actions = []
    if phase_readiness["phase_3_shadow_registry_promotion"] == "ready":
        next_actions.append(
            {
                "phase": 3,
                "action": "Promote eligible test/parity consumers from sql_shadow_validated to sql_primary_guarded in the registry.",
                "consumer_count": shadow["eligible_registry_only_promotion_count"],
                "behavior_change": False,
                "sql_write_required": True,
                "backup_required": True,
                "fallback_retirement": False,
            }
        )
    if raw_sql["actionable_typed_replacement_review_count"]:
        next_actions.append(
            {
                "phase": 4,
                "action": "Inspect actionable raw-SQL review consumers before any typed replacement patch.",
                "consumer_count": raw_sql["actionable_typed_replacement_review_count"],
                "behavior_change": "possible",
                "sql_write_required": False,
                "hard_stop_before_answer_ownership_change": True,
            }
        )
    next_actions.append(
        {
            "phase": 5,
            "action": "Use source-producer partition packet to keep 346 source/proof/write surfaces retained; do not retire any source feeder yet.",
            "consumer_count": source_partition["source_producer_count"],
            "retirement_candidate_count": source_partition["retirement_candidate_count"],
            "behavior_change": False,
        }
    )
    next_actions.append(
        {
            "phase": 6,
            "action": "Hold SQL-first/front-door promotion until rich A/B parity, fallback/source-open contract, and exact owner approval exist.",
            "sql_first_promotion_allowed_now": answer_path["sql_first_promotion_allowed_now"],
            "behavior_change": False,
        }
    )

    status = "ok" if not errors else "blocked"
    payload = {
        "schema": "veritas.sql_canon_migration_phase_executor.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "inputs": {
            "db": rel(args.db),
            "inventory": rel(args.inventory),
            "backlog": rel(args.backlog),
            "burndown": rel(args.burndown),
            "retirement": rel(args.retirement),
            "trade_grade_assembler": rel(args.trade_grade_assembler),
            "answer_path_ab_harness": rel(args.answer_path_ab_harness),
            "python_retirement": rel(args.python_retirement),
            "cron_control": rel(args.cron_control),
            "db_lifecycle": rel(args.db_lifecycle),
        },
        "proof_artifacts": proof_artifacts(REQUIRED_PROOF_ARTIFACTS),
        "registry_summary": registry,
        "burndown_summary": burndown_summary,
        "batch_counts": batch_counts,
        "batches": batches,
        "shadow_promotion": shadow,
        "raw_sql_classification": raw_sql,
        "source_producer_partition": source_partition,
        "sql_first_front_door_readiness": answer_path,
        "python_fallback_retirement_audit": fallback,
        "duplicate_surface_schema_cleanup_plan": duplicate_cleanup,
        "cron_impact_review": cron_review,
        "phase_readiness": phase_readiness,
        "next_actions": next_actions,
        "validation": {
            "status": status,
            "critical_errors": errors,
            "warnings": warnings,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Do not retire source feeders from this report alone.",
            "Do not retire Python/source fallbacks from this report alone.",
            "Do not promote finance front doors or answer-path ownership to SQL-first from this report alone.",
            "Do not use this report for portfolio/canon/capital/paper/live/account authority.",
        ],
    }
    payload["owner_decision_packet"] = owner_decision_packet(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--burndown", type=Path, default=DEFAULT_BURNDOWN)
    parser.add_argument("--retirement", type=Path, default=DEFAULT_RETIREMENT)
    parser.add_argument("--trade-grade-assembler", type=Path, default=DEFAULT_TRADE_GRADE_ASSEMBLER)
    parser.add_argument("--answer-path-ab-harness", type=Path, default=DEFAULT_ANSWER_PATH_AB)
    parser.add_argument("--python-retirement", type=Path, default=DEFAULT_PYTHON_RETIREMENT)
    parser.add_argument("--cron-control", type=Path, default=DEFAULT_CRON_CONTROL)
    parser.add_argument("--db-lifecycle", type=Path, default=DEFAULT_DB_LIFECYCLE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    args.db = args.db if args.db.is_absolute() else ROOT / args.db
    args.inventory = args.inventory if args.inventory.is_absolute() else ROOT / args.inventory
    args.backlog = args.backlog if args.backlog.is_absolute() else ROOT / args.backlog
    args.burndown = args.burndown if args.burndown.is_absolute() else ROOT / args.burndown
    args.retirement = args.retirement if args.retirement.is_absolute() else ROOT / args.retirement
    args.trade_grade_assembler = (
        args.trade_grade_assembler if args.trade_grade_assembler.is_absolute() else ROOT / args.trade_grade_assembler
    )
    args.answer_path_ab_harness = (
        args.answer_path_ab_harness if args.answer_path_ab_harness.is_absolute() else ROOT / args.answer_path_ab_harness
    )
    args.python_retirement = args.python_retirement if args.python_retirement.is_absolute() else ROOT / args.python_retirement
    args.cron_control = args.cron_control if args.cron_control.is_absolute() else ROOT / args.cron_control
    args.db_lifecycle = args.db_lifecycle if args.db_lifecycle.is_absolute() else ROOT / args.db_lifecycle
    payload = build(args)
    if args.write:
        atomic_write_json(DEFAULT_OUT, payload)
        atomic_write_json(DEFAULT_DECISION_OUT, payload["owner_decision_packet"])
    print(
        json.dumps(
            {
                "status": payload["status"],
                "phase_readiness": payload["phase_readiness"],
                "shadow_promotion": {
                    "eligible": payload["shadow_promotion"]["eligible_registry_only_promotion_count"],
                    "blocked": payload["shadow_promotion"]["blocked_count"],
                },
                "raw_sql": {
                    "total_present": payload["raw_sql_classification"]["raw_sql_present_count"],
                    "review": payload["raw_sql_classification"]["raw_sql_review_count"],
                    "actionable": payload["raw_sql_classification"]["actionable_typed_replacement_review_count"],
                    "source_producer": payload["raw_sql_classification"]["source_producer_raw_sql_count"],
                },
                "source_producer_partition": {
                    "count": payload["source_producer_partition"]["source_producer_count"],
                    "retirement_candidates": payload["source_producer_partition"]["retirement_candidate_count"],
                    "partition_counts": payload["source_producer_partition"]["partition_counts"],
                },
                "sql_first_front_door": {
                    "status": payload["sql_first_front_door_readiness"]["status"],
                    "promotion_allowed_now": payload["sql_first_front_door_readiness"]["sql_first_promotion_allowed_now"],
                    "blocker_count": len(payload["sql_first_front_door_readiness"]["blockers"]),
                },
                "python_fallback": {
                    "status": payload["python_fallback_retirement_audit"]["status"],
                    "retirement_ready": payload["python_fallback_retirement_audit"]["retirement_ready"],
                    "retire_count": payload["python_fallback_retirement_audit"]["retire_python_now_count"],
                },
                "duplicate_cleanup": {
                    "status": payload["duplicate_surface_schema_cleanup_plan"]["status"],
                    "archive_ready": payload["duplicate_surface_schema_cleanup_plan"]["archive_ready_count"],
                    "delete_ready": payload["duplicate_surface_schema_cleanup_plan"]["delete_ready_count"],
                },
                "cron_impact": {
                    "status": payload["cron_impact_review"]["status"],
                    "cron_raw_sql_review_count": payload["cron_impact_review"]["cron_raw_sql_review_count"],
                    "schedule_mutation_allowed": payload["cron_impact_review"]["cron_schedule_mutation_allowed"],
                },
                "owner_decision_packet": rel(DEFAULT_DECISION_OUT) if args.write else None,
                "validation": payload["validation"],
                "written": [rel(DEFAULT_OUT), rel(DEFAULT_DECISION_OUT)] if args.write else [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
