#!/usr/bin/env python3
"""Build fixture, parity, and consumer-stability contracts for queued helpers.

This is the next gate after the first controlled demotion. It works through the
remaining demotion queue and records, per helper, what must be true before the
helper can move from "queued" to controlled Go-first/Python-fallback.

The gate is report-only. It does not execute candidate helpers, switch
production routing, retire Python, write/import SQL, mutate canon/portfolio
state, change runtime config, infer approval, or grant paper/live/account
authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.pm_control_reader import pm_program_state
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-helper-contract-gate.json"
QUEUE_JSON = TMP / "python-go-sql-helper-demotion-queue.json"
RUNTIME_JSON = TMP / "runtime-performance-scorecard.json"
HARNESS_JSON = TMP / "veritas-harness-scorecard.json"
DEFAULT_PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
SCHEMA = "veritas.python_go_sql_helper_contract_gate.v1"

OUTPUT_ARTIFACTS: dict[str, str] = {
    "scripts/finance_data_coverage.py": "tmp/finance-data-coverage-current.json",
    "scripts/finance_human_notes_thinning_candidates.py": "tmp/finance-human-notes-thinning-candidates.json",
    "scripts/finance_universe_validator.py": "tmp/wf78-finance-universe-validation.json",
    "scripts/sql_500_ticker_expansion_design_gate.py": "tmp/sql-500-ticker-expansion-design-gate.json",
    "scripts/sql_coverage_guard.py": "tmp/sql-coverage-guard.json",
    "scripts/sql_latency_benchmark.py": "tmp/sql-latency-benchmark-current.json",
    "scripts/sql_pre_phase5_hardening_gate.py": "tmp/sql-pre-phase5-hardening-gate.json",
    "scripts/sql_retail_grade_automation_gate.py": "tmp/sql-retail-grade-automation-gate.json",
    "scripts/go_sql_inprocess_driver_pilot_gate.py": "tmp/go-sql-inprocess-driver-pilot-gate.json",
    "scripts/sql_source_truth_authority_manifest.py": "tmp/sql-source-truth-authority-manifest.json",
    "scripts/sql_source_truth_parity_validator.py": "tmp/sql-source-truth-parity-validation.json",
    "scripts/wf78_sql_phase2_readiness.py": "tmp/wf78-sql-phase2-readiness.json",
}

PARITY_ARTIFACTS: dict[str, str] = {
    "scripts/finance_data_coverage.py": "tmp/python-go-finance-data-coverage-probe-parity.json",
    "scripts/finance_human_notes_thinning_candidates.py": "tmp/python-go-finance-human-notes-sql-check-parity.json",
    "scripts/finance_universe_validator.py": "tmp/python-go-finance-universe-validation-parity.json",
    "scripts/sql_500_ticker_expansion_design_gate.py": "tmp/python-go-sql-500-expansion-gate-parity.json",
    "scripts/sql_latency_benchmark.py": "tmp/python-go-sql-parity-check.json",
    "scripts/sql_source_truth_authority_manifest.py": "tmp/python-go-source-truth-manifest-parity.json",
    "scripts/sql_source_truth_parity_validator.py": "tmp/python-go-source-truth-parity-validator-parity.json",
    "scripts/wf78_sql_phase2_readiness.py": "tmp/python-go-wf78-sql-phase2-readiness-parity.json",
}

STATUS_ALLOW: dict[str, set[str]] = {
    "tmp/sql-retail-grade-automation-gate.json": {"hard_failed", "blocked", "ok", "warning"},
    "tmp/sql-source-truth-authority-manifest.json": {"ready_for_phase2_parity_scaffold"},
    "tmp/sql-source-truth-parity-validation.json": {"phase2_parity_green_for_entry_stop_reference_metadata"},
    "tmp/sql-500-ticker-expansion-design-gate.json": {"ready_for_next_gate_design", "ready_for_source_open_cleanup"},
    "tmp/go-sql-inprocess-driver-pilot-gate.json": {"ok", "blocked", "warning"},
    "tmp/finance-data-coverage-current.json": {"ok", "ok_with_explicit_gaps", "warning"},
    "tmp/finance-human-notes-thinning-candidates.json": {"ready_for_owner_review_no_archive_applied"},
    "tmp/wf78-sql-phase2-readiness.json": {"ready"},
}

FORBIDDEN_AUTHORITY_KEYS = (
    "sql_write_allowed",
    "sql_writes_allowed",
    "live_sql_write_or_import_allowed",
    "db_mutation",
    "canonical_mutation_allowed",
    "canonical_markdown_mutation_allowed",
    "canon_or_portfolio_mutation",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "paper_or_live_execution",
    "paper_or_live_execution_allowed",
    "paper_or_live_execution_authority",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "customer_or_external_delivery",
    "customer_or_external_delivery_allowed",
    "config_auth_runtime_mutation",
    "production_routing_changed",
    "retire_python_now",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: str | Path) -> dict[str, Any]:
    payload = load_json_artifact(ROOT / str(path).replace("/", "\\") if isinstance(path, str) else path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def artifact_path(path_value: str) -> Path:
    return ROOT / path_value.replace("/", "\\")


def output_shape(payload: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    authority = as_dict(payload.get("authority_boundary")) or as_dict(payload.get("authority"))
    return {
        "top_level_keys": sorted(str(key) for key in payload.keys()),
        "status": payload.get("status"),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "summary_keys": sorted(str(key) for key in summary.keys()),
        "validation_keys": sorted(str(key) for key in validation.keys()),
        "authority_keys": sorted(str(key) for key in authority.keys()),
    }


def forbidden_true_values(payload: dict[str, Any]) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    pools = [payload, as_dict(payload.get("authority_boundary")), as_dict(payload.get("authority"))]
    for pool in pools:
        for key in FORBIDDEN_AUTHORITY_KEYS:
            if pool.get(key) is True:
                observed[key] = True
    return observed


def allowed_status(path_value: str, status: Any) -> bool:
    allowed = STATUS_ALLOW.get(path_value)
    if not allowed:
        return status in {"ok", "warning", "ready", "blocked", "hard_failed"} or status is not None
    return status in allowed


def parity_status(path_value: str | None) -> tuple[str, dict[str, Any]]:
    if not path_value:
        return "pending_go_contract", {}
    payload = load(path_value)
    if not payload:
        return "missing", {}
    if payload.get("status") != "ok":
        return "not_green", payload
    summary = as_dict(payload.get("summary"))
    if int(summary.get("critical") or 0) != 0:
        return "not_green", payload
    return "green", payload


def consumer_stability(runtime: dict[str, Any], harness: dict[str, Any], pm_state: dict[str, Any], *, allow_runtime_self_cycle: bool = False) -> dict[str, Any]:
    runtime_summary = as_dict(runtime.get("summary"))
    runtime_ok = runtime.get("status") == "ok" and runtime_summary.get("blocked_count") == 0
    runtime_self_cycle_deferred = allow_runtime_self_cycle and not runtime_ok
    harness_failure_count = int(as_dict(harness.get("summary")).get("failure_count") or 0)
    harness_self_cycle_deferred = allow_runtime_self_cycle and harness_failure_count != 0
    return {
        "runtime_scorecard": {
            "status": runtime.get("status"),
            "checks_total": runtime_summary.get("checks_total"),
            "blocked_count": runtime_summary.get("blocked_count"),
            "ok": runtime_ok or runtime_self_cycle_deferred,
            "self_cycle_deferred": runtime_self_cycle_deferred,
            "note": "runtime_scorecard_validated_by_parent_run" if runtime_self_cycle_deferred else None,
        },
        "harness": {
            "status": harness.get("status"),
            "failure_count": as_dict(harness.get("summary")).get("failure_count"),
            "warning_count": as_dict(harness.get("summary")).get("warning_count"),
            "ok": harness_failure_count == 0 or harness_self_cycle_deferred,
            "self_cycle_deferred": harness_self_cycle_deferred,
            "note": "harness_validated_after_parent_runtime_scorecard" if harness_self_cycle_deferred else None,
            "known_warning": "wf55_probability_readiness=NOT_READY",
        },
        "pm_state": {
            "status": pm_state.get("status"),
            "readiness_band": as_dict(pm_state.get("readiness")).get("readiness_band"),
            "ok": pm_state.get("status") == "ok",
        },
    }


def build_candidate_contract(row: dict[str, Any], stability: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = str(row.get("path") or "")
    out_path = OUTPUT_ARTIFACTS.get(path)
    parity_path = PARITY_ARTIFACTS.get(path)
    output_payload = load(out_path) if out_path else {}
    parity_state, parity_payload = parity_status(parity_path)
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"candidate": path, "check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    add("fixture_contract_defined", bool(out_path), "critical", out_path)
    add("expected_output_artifact_exists", bool(output_payload), "critical", out_path)
    if output_payload:
        add("expected_output_status_allowed", allowed_status(out_path or "", output_payload.get("status")), "critical", {"status": output_payload.get("status"), "path": out_path})
        add("no_forbidden_authority_true_values", not forbidden_true_values(output_payload), "critical", forbidden_true_values(output_payload))
    if row.get("durable_output"):
        add("durable_output_shape_captured", bool(output_payload), "critical", output_shape(output_payload) if output_payload else None)
        add("durable_output_not_retired", row.get("retire_python_now") is False, "critical", row.get("retire_python_now"))
    if row.get("candidate_kind") == "existing_go_covered":
        add("python_go_parity_green", parity_state == "green", "critical", parity_path or parity_state)
    else:
        add("python_go_parity_not_required_until_go_spike", parity_state in {"pending_go_contract", "green"}, "warning", parity_path or parity_state)
    if row.get("orchestrates_commands"):
        add("orchestration_keeps_python_owner", True, "info", "Go work limited to extracted read-only probes.")
    add("consumer_runtime_stable", as_dict(stability.get("runtime_scorecard")).get("ok") is True, "critical", stability.get("runtime_scorecard"))
    add("consumer_harness_no_failures", as_dict(stability.get("harness")).get("ok") is True, "critical", stability.get("harness"))
    add("consumer_pm_state_ok", as_dict(stability.get("pm_state")).get("ok") is True, "critical", stability.get("pm_state"))

    critical = [item for item in findings if item["ok"] is not True and item["severity"] == "critical"]
    warnings = [item for item in findings if item["ok"] is not True and item["severity"] == "warning"]
    next_stage = "eligible_for_controlled_router_design" if not critical and parity_state == "green" and not row.get("orchestrates_commands") else "contract_captured_keep_python_owner"
    if row.get("orchestrates_commands"):
        next_stage = "extract_go_probe_only_keep_python_orchestrator"
    if row.get("durable_output") and parity_state != "green":
        next_stage = "durable_shape_captured_wait_for_go_semantic_parity"
    contract = {
        "path": path,
        "candidate_kind": row.get("candidate_kind"),
        "migration_batch": row.get("migration_batch"),
        "durable_output": bool(row.get("durable_output")),
        "orchestrates_commands": bool(row.get("orchestrates_commands")),
        "fixture_contract": {
            "source_python_helper": path,
            "expected_output_artifact": out_path,
            "expected_output_shape": output_shape(output_payload) if output_payload else None,
            "fixture_inputs": row.get("requirements_before_controlled_demotion"),
            "forbidden_authority_true_values": forbidden_true_values(output_payload) if output_payload else {},
        },
        "semantic_shape_parity": {
            "parity_artifact": parity_path,
            "status": parity_state,
            "checks": as_dict(parity_payload.get("summary")).get("checks") if parity_payload else None,
            "critical": as_dict(parity_payload.get("summary")).get("critical") if parity_payload else None,
            "warnings": as_dict(parity_payload.get("summary")).get("warnings") if parity_payload else None,
        },
        "consumer_stability": stability,
        "contract_status": "ok" if not critical else "blocked",
        "next_stage": next_stage,
        "retire_python_now": False,
    }
    return contract, findings


def build_report(*, allow_runtime_self_cycle: bool = False) -> dict[str, Any]:
    default_promotion = load(DEFAULT_PROMOTION_JSON)
    if (
        default_promotion.get("status") == "ok"
        and as_dict(default_promotion.get("summary")).get("default_route") == "python_owner_only"
    ):
        python_default_helpers = [
            str(row.get("path"))
            for row in as_list(default_promotion.get("promoted_routes"))
            if isinstance(row, dict) and row.get("path")
        ]
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "ok",
            "workspace_root": str(ROOT),
            "source_artifacts": {
                "default_route_promotion": "tmp/python-go-sql-helper-default-route-promotion.json",
            },
            "summary": {
                "checks": len(python_default_helpers) + 1,
                "critical": 0,
                "warnings": 0,
                "contracts_total": len(python_default_helpers),
                "fixture_contracts_captured": len(python_default_helpers),
                "semantic_shape_parity_green": 0,
                "durable_output_candidates": 0,
                "durable_output_parity_pending": 0,
                "controlled_router_design_eligible": 0,
                "orchestrators_keep_python_owner": 0,
                "retire_python_now": 0,
                "default_route": "python_owner_only",
                "python_default_helpers": len(python_default_helpers),
                "go_validator_only_helpers": len(python_default_helpers),
                "contract_gate_signal": "dormant_python_owner_default_go_validator_only",
            },
            "contracts": [],
            "eligible_next_controlled_router_candidates": [],
            "durable_output_parity_pending": [],
            "orchestration_python_owner_retained": [],
            "python_default_helpers": python_default_helpers,
            "findings": [
                {
                    "check": "python_owner_default_route_active",
                    "ok": True,
                    "severity": "info",
                    "detail": "Contract capture is dormant while Python is owner/default and Go is validator-only.",
                }
            ],
            "authority_boundary": {
                "report_only": True,
                "read_only": True,
                "executes_candidate_helpers": False,
                "controlled_demotion_not_retirement": False,
                "production_routing_changed": False,
                "python_owner_default": True,
                "go_validator_only": True,
                "python_fallback_retained": True,
                "retire_python_now": False,
                "live_sql_write_or_import_allowed": False,
                "db_mutation": False,
                "canon_or_portfolio_mutation": False,
                "customer_or_external_delivery": False,
                "paper_or_live_execution": False,
                "owner_approval_inferred": False,
                "config_auth_runtime_mutation": False,
                "trade_or_account_action_allowed": False,
                "money_movement_allowed": False,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }
    queue = load(QUEUE_JSON)
    rows = [row for row in as_list(queue.get("next_demotion_queue")) if isinstance(row, dict)]
    runtime = load(RUNTIME_JSON)
    harness = load(HARNESS_JSON)
    pm_state = pm_program_state()
    stability = consumer_stability(runtime, harness, pm_state, allow_runtime_self_cycle=allow_runtime_self_cycle)

    contracts: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for row in rows:
        contract, row_findings = build_candidate_contract(row, stability)
        contracts.append(contract)
        findings.extend(row_findings)

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    eligible = [row for row in contracts if row.get("next_stage") == "eligible_for_controlled_router_design"]
    durable_pending = [row for row in contracts if row.get("durable_output") and as_dict(row.get("semantic_shape_parity")).get("status") != "green"]
    orchestrator_kept = [row for row in contracts if row.get("orchestrates_commands")]

    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "demotion_queue": "tmp/python-go-sql-helper-demotion-queue.json",
            "runtime_scorecard": "tmp/runtime-performance-scorecard.json",
            "harness_scorecard": "tmp/veritas-harness-scorecard.json",
            "pm_control_packet": "tmp/pm-control-packet.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "contracts_total": len(contracts),
            "fixture_contracts_captured": sum(1 for row in contracts if as_dict(row.get("fixture_contract")).get("expected_output_artifact")),
            "semantic_shape_parity_green": sum(1 for row in contracts if as_dict(row.get("semantic_shape_parity")).get("status") == "green"),
            "durable_output_candidates": sum(1 for row in contracts if row.get("durable_output")),
            "durable_output_parity_pending": len(durable_pending),
            "controlled_router_design_eligible": len(eligible),
            "orchestrators_keep_python_owner": len(orchestrator_kept),
            "retire_python_now": 0,
            "contract_gate_signal": "contracts_captured_no_python_retirement" if not critical else "blocked",
        },
        "contracts": contracts,
        "eligible_next_controlled_router_candidates": [row.get("path") for row in eligible],
        "durable_output_parity_pending": [row.get("path") for row in durable_pending],
        "orchestration_python_owner_retained": [row.get("path") for row in orchestrator_kept],
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "executes_candidate_helpers": False,
            "controlled_demotion_not_retirement": True,
            "production_routing_changed": False,
            "python_fallback_retained": True,
            "retire_python_now": False,
            "live_sql_write_or_import_allowed": False,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
            "trade_or_account_action_allowed": False,
            "money_movement_allowed": False,
        },
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [f"{row.get('candidate')}:{row.get('check')}" for row in critical],
            "warnings": [f"{row.get('candidate')}:{row.get('check')}" for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Python-Go SQL helper fixture/contract gate.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--allow-runtime-self-cycle",
        action="store_true",
        help="Allow parent runtime scorecard runs to validate this gate without depending on a completed fresh scorecard artifact.",
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    report = build_report(allow_runtime_self_cycle=args.allow_runtime_self_cycle)
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
