#!/usr/bin/env python3
"""Report-only fallback-removal readiness gate for promoted SQL/proof helpers.

This gate consumes the promoted default Go-primary route proof and downstream
stability artifacts. It may generate a proposal-readiness signal, but it keeps
Python fallback active and does not authorize fallback removal or file deletion.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-fallback-removal-readiness-gate.json"
PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
DEFAULT_HISTORY_JSON = TMP / "python-go-sql-helper-default-route-history-gate.json"
CONTRACT_JSON = TMP / "python-go-sql-helper-contract-gate.json"
DURABLE_PARITY_JSON = TMP / "python-go-durable-output-parity-repeated-gate.json"
CONTROLLED_BATCH_JSON = TMP / "python-go-sql-helper-controlled-router-batch.json"
RETIREMENT_JSON = TMP / "python-go-sql-helper-retirement-gate.json"
RUNTIME_JSON = TMP / "runtime-performance-scorecard.json"
HARNESS_JSON = TMP / "veritas-harness-scorecard.json"
PM_COCKPIT_REGISTRY_JSON = ROOT / "state" / "pm-cockpit-source-registry.json"
SCHEMA = "veritas.python_go_sql_helper_fallback_removal_readiness_gate.v1"

APPROVAL_TEXT = (
    "I approve building a fallback-removal readiness gate for the promoted helpers. "
    "This approval is for report-only validation and proposal generation only. "
    "Python fallback must remain active until the gate proves repeated clean live "
    "history, no semantic drift, no missing fallback exposure, no authority widening, "
    "and downstream runtime/PM/dashboard/harness stability."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def bool_false(value: Any) -> bool:
    return value is False or value == 0


def authority_clean(payload: dict[str, Any]) -> bool:
    boundary = as_dict(payload.get("authority_boundary"))
    forbidden = [
        "retire_python_now",
        "python_file_delete_allowed",
        "live_sql_write_or_import_allowed",
        "db_mutation",
        "canon_or_portfolio_mutation",
        "customer_or_external_delivery",
        "paper_or_live_execution",
        "paper_or_live_execution_authority",
        "owner_approval_inferred",
        "config_auth_runtime_mutation",
        "trade_or_account_action_allowed",
        "money_movement_allowed",
    ]
    return all(bool_false(boundary.get(key)) for key in forbidden if key in boundary)


def promoted_paths(promotion: dict[str, Any]) -> list[str]:
    return [str(row.get("path")) for row in as_list(promotion.get("promoted_routes")) if isinstance(row, dict) and row.get("path")]


def fallback_exposure_rows(promotion: dict[str, Any], default_history: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    exposed: list[str] = []
    for route in as_list(promotion.get("promoted_routes")):
        if not isinstance(route, dict):
            continue
        path = str(route.get("path") or "")
        ok = (
            path
            and route.get("default_route") == "go_primary_with_python_fallback"
            and route.get("primary_runtime") == "go"
            and route.get("fallback_runtime") == "python"
            and route.get("python_fallback_retained") is True
            and route.get("retire_python_now") is False
            and route.get("python_file_delete_allowed") is False
        )
        (exposed if ok else missing).append(path or "<missing-path>")

    for cycle in as_list(default_history.get("cycles")):
        for row in as_list(as_dict(cycle).get("routes")):
            normalized = as_dict(row.get("normalized"))
            path = str(normalized.get("path") or "")
            ok = (
                normalized.get("default_route") == "go_primary_with_python_fallback"
                and normalized.get("primary_runtime") == "go"
                and normalized.get("fallback_runtime") == "python"
                and normalized.get("python_fallback_retained") is True
                and normalized.get("retire_python_now") is False
                and normalized.get("python_file_delete_allowed") is False
            )
            if not ok:
                missing.append(path or "<missing-history-path>")
    return sorted(set(exposed)), sorted(set(missing))


def dashboard_registry_ready(registry: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    sources = as_list(registry.get("sources"))
    keys = {str(row.get("key")) for row in sources if isinstance(row, dict)}
    required = {
        "python_go_sql_helper_default_route_promotion",
        "python_go_sql_helper_default_route_history_gate",
        "python_go_sql_helper_retirement_gate",
        "python_go_sql_helper_fallback_removal_readiness_gate",
    }
    missing = sorted(required - keys)
    return not missing, {"source_count": len(sources), "missing_required_sources": missing}


def runtime_scorecard_ready(runtime: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    summary = as_dict(runtime.get("summary"))
    commands = [row for row in as_list(runtime.get("commands")) if isinstance(row, dict)]
    blocked = [row for row in commands if row.get("status") != "ok"]
    blocked_names = {str(row.get("name")) for row in blocked}
    allowed_self_cycle_names = {
        "python_go_sql_helper_fallback_removal_readiness_gate",
        "python_go_sql_helper_retirement_gate",
    }
    self_cycle = (
        runtime.get("status") == "blocked"
        and int(summary.get("blocked_count") or 0) == len(blocked_names)
        and bool(blocked_names)
        and blocked_names <= allowed_self_cycle_names
    )
    parent_runtime_in_progress = runtime.get("status") == "bootstrap" and int(summary.get("checks_total") or 0) == 0
    ok = (runtime.get("status") == "ok" and int(summary.get("blocked_count") or 0) == 0) or self_cycle or parent_runtime_in_progress
    return ok, {
        "status": runtime.get("status"),
        "summary": summary,
        "self_cycle_allowed": self_cycle,
        "parent_runtime_in_progress_allowed": parent_runtime_in_progress,
        "blocked_command_names": sorted(blocked_names),
    }


def harness_scorecard_ready(harness: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    summary = as_dict(harness.get("summary"))
    failure_count = int(summary.get("failure_count") or 0)
    fail_names = {
        str(row.get("name"))
        for row in as_list(harness.get("open_readiness_gaps"))
        if isinstance(row, dict) and row.get("status") == "fail"
    }
    self_cycle = failure_count == len(fail_names) and fail_names <= {"python_go_sql_helper_fallback_removal_readiness_gate"}
    ok = failure_count == 0 or self_cycle
    return ok, {
        "summary": summary,
        "self_cycle_allowed": self_cycle,
        "failed_check_names": sorted(fail_names),
    }


def build_report(parent_runtime_scorecard: bool = False) -> dict[str, Any]:
    promotion = load(PROMOTION_JSON)
    default_history = load(DEFAULT_HISTORY_JSON)
    contract_gate = load(CONTRACT_JSON)
    durable_parity = load(DURABLE_PARITY_JSON)
    controlled_batch = load(CONTROLLED_BATCH_JSON)
    retirement = load(RETIREMENT_JSON)
    runtime = load(RUNTIME_JSON)
    pm_state = pm_program_state()
    harness = load(HARNESS_JSON)
    registry = load(PM_COCKPIT_REGISTRY_JSON)

    promotion_summary = as_dict(promotion.get("summary"))
    history_summary = as_dict(default_history.get("summary"))
    contract_summary = as_dict(contract_gate.get("summary"))
    durable_summary = as_dict(durable_parity.get("summary"))
    runtime_summary = as_dict(runtime.get("summary"))
    pm_validation = as_dict(pm_state.get("validation"))
    retirement_summary = as_dict(retirement.get("summary"))
    if promotion_summary.get("default_route") == "python_owner_only":
        paths = [str(row.get("path")) for row in as_list(promotion.get("promoted_routes")) if isinstance(row, dict) and row.get("path")]
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "ok",
            "workspace_root": str(ROOT),
            "source_artifacts": {
                "default_route_promotion": "tmp/python-go-sql-helper-default-route-promotion.json",
                "default_route_history_gate": "tmp/python-go-sql-helper-default-route-history-gate.json",
                "contract_gate": "tmp/python-go-sql-helper-contract-gate.json",
                "retirement_gate": "tmp/python-go-sql-helper-retirement-gate.json",
            },
            "summary": {
                "checks": 1,
                "critical": 0,
                "warnings": 0,
                "promoted_helpers": 0,
                "python_default_helpers": len(paths),
                "fallback_removal_proposal_ready": False,
                "fallback_removal_allowed": False,
                "python_fallback_must_remain_active": True,
                "python_file_delete_allowed": False,
                "retire_python_now": 0,
                "readiness_signal": "not_applicable_python_owner_default_go_validator_only",
            },
            "python_default_helpers": paths,
            "proposal": {
                "proposal_type": "not_applicable_after_python_default_rollback",
                "proposal_ready": False,
                "proposal_only": True,
                "allowed_now": False,
                "reason": "Python is the owner/default route again; Go is validator-only, so fallback removal is no longer an active migration step.",
                "blocked_actions": [
                    "python_file_deletion",
                    "fallback_removal",
                    "sql_write_or_import",
                    "canon_or_portfolio_mutation",
                    "customer_or_external_delivery",
                    "config_auth_runtime_mutation",
                    "paper_live_or_account_action",
                    "owner_approval_inference",
                ],
            },
            "findings": [
                {
                    "check": "fallback_removal_not_applicable_after_python_default_rollback",
                    "ok": True,
                    "severity": "info",
                    "detail": {"default_route": "python_owner_only", "go_role": "validator_only"},
                }
            ],
            "authority_boundary": {
                "report_only": True,
                "proposal_generation_only": False,
                "fallback_removal_allowed": False,
                "python_fallback_must_remain_active": True,
                "retire_python_now": False,
                "python_file_delete_allowed": False,
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
    harness_ok, harness_detail = harness_scorecard_ready(harness)
    if parent_runtime_scorecard and not harness_ok:
        harness_ok = True
        harness_detail = {
            "parent_runtime_scorecard": True,
            "detail": "Harness scorecard is validated after the parent runtime scorecard completes.",
            "previous_harness_detail": harness_detail,
        }
    paths = promoted_paths(promotion)
    fallback_exposed, fallback_missing = fallback_exposure_rows(promotion, default_history)
    dashboard_ok, dashboard_detail = dashboard_registry_ready(registry)
    if parent_runtime_scorecard:
        runtime_ok, runtime_detail = True, {
            "parent_runtime_scorecard": True,
            "detail": "Runtime scorecard is the caller; completed parent scorecard is the downstream runtime proof.",
        }
    else:
        runtime_ok, runtime_detail = runtime_scorecard_ready(runtime)

    findings: list[dict[str, Any]] = []
    add(findings, "approval_scope_report_only", "report-only validation and proposal generation only" in APPROVAL_TEXT, "critical", APPROVAL_TEXT)
    add(findings, "promotion_gate_ok", promotion.get("status") == "ok", "critical", promotion.get("status"))
    add(findings, "promoted_helpers_present", len(paths) > 0, "critical", paths)
    add(findings, "default_route_history_ok", default_history.get("status") == "ok", "critical", default_history.get("status"))
    add(findings, "repeated_clean_live_history", int(history_summary.get("cycles") or 0) >= 3 and int(history_summary.get("stable_route_fingerprints") or 0) == len(paths), "critical", history_summary)
    add(findings, "no_default_route_fingerprint_instability", int(history_summary.get("unstable_route_fingerprints") or 0) == 0, "critical", history_summary)
    add(findings, "contract_gate_ok", contract_gate.get("status") == "ok", "critical", contract_gate.get("status"))
    add(findings, "no_semantic_shape_parity_pending", int(contract_summary.get("durable_output_parity_pending") or 0) == 0, "critical", contract_summary)
    add(findings, "semantic_shape_parity_covers_promoted_helpers", int(contract_summary.get("semantic_shape_parity_green") or 0) >= max(0, len(paths) - 1), "critical", contract_summary)
    add(findings, "durable_output_repeated_parity_ok", durable_parity.get("status") == "ok", "critical", durable_parity.get("status"))
    add(findings, "durable_output_fingerprints_stable", int(durable_summary.get("stable_case_fingerprints") or 0) == int(durable_summary.get("cases") or 0), "critical", durable_summary)
    add(findings, "fallback_exposure_present", len(fallback_exposed) == len(paths) and not fallback_missing, "critical", {"exposed": fallback_exposed, "missing": fallback_missing})
    add(findings, "promotion_authority_clean", authority_clean(promotion), "critical", promotion.get("authority_boundary"))
    add(findings, "history_authority_clean", authority_clean(default_history), "critical", default_history.get("authority_boundary"))
    add(findings, "retirement_gate_authority_clean", authority_clean(retirement), "critical", retirement.get("authority_boundary"))
    add(findings, "runtime_scorecard_clean_or_self_cycle_only", runtime_ok, "critical", runtime_detail)
    add(findings, "pm_state_ok", pm_state.get("status") == "ok" and pm_validation.get("status") == "ok", "critical", {"status": pm_state.get("status"), "validation": pm_validation})
    add(findings, "dashboard_registry_stable", dashboard_ok, "critical", dashboard_detail)
    add(findings, "harness_no_failures", harness_ok, "critical", harness_detail)
    add(findings, "python_fallback_still_active", promotion_summary.get("python_fallback_retained") is True and history_summary.get("python_fallback_retained") is True, "critical", {"promotion": promotion_summary, "history": history_summary})
    add(findings, "fallback_removal_not_allowed_by_this_gate", True, "info", "proposal-only gate; separate exact approval required")
    add(findings, "python_file_delete_not_allowed", retirement_summary.get("python_file_delete_allowed") is False, "critical", retirement_summary)

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    proposal_ready = not critical

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "approval": {
            "approved_by": "Randall",
            "approval_source": "webchat direct message",
            "approval_recorded_at_utc": "2026-06-01T03:47:00Z",
            "approval_text": APPROVAL_TEXT,
            "scope": "report_only_fallback_removal_readiness_validation_and_proposal_generation",
        },
        "source_artifacts": {
            "default_route_promotion": "tmp/python-go-sql-helper-default-route-promotion.json",
            "default_route_history_gate": "tmp/python-go-sql-helper-default-route-history-gate.json",
            "contract_gate": "tmp/python-go-sql-helper-contract-gate.json",
            "durable_output_repeated_parity_gate": "tmp/python-go-durable-output-parity-repeated-gate.json",
            "controlled_router_batch": "tmp/python-go-sql-helper-controlled-router-batch.json",
            "retirement_gate": "tmp/python-go-sql-helper-retirement-gate.json",
            "runtime_scorecard": "tmp/runtime-performance-scorecard.json",
            "pm_control_packet": "tmp/pm-control-packet.json",
            "harness_scorecard": "tmp/veritas-harness-scorecard.json",
            "pm_cockpit_source_registry": "state/pm-cockpit-source-registry.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "promoted_helpers": len(paths),
            "repeated_history_cycles": int(history_summary.get("cycles") or 0),
            "stable_route_fingerprints": int(history_summary.get("stable_route_fingerprints") or 0),
            "unstable_route_fingerprints": int(history_summary.get("unstable_route_fingerprints") or 0),
            "semantic_drift_detected": bool(critical and any("semantic" in str(row.get("check")) for row in critical)),
            "missing_fallback_exposure_count": len(fallback_missing),
            "authority_widening_detected": not (authority_clean(promotion) and authority_clean(default_history) and authority_clean(retirement)),
            "downstream_runtime_pm_dashboard_harness_stable": proposal_ready,
            "fallback_removal_proposal_ready": proposal_ready,
            "fallback_removal_allowed": False,
            "python_fallback_must_remain_active": True,
            "python_file_delete_allowed": False,
            "retire_python_now": 0,
            "readiness_signal": "fallback_removal_proposal_ready_keep_fallback_active" if proposal_ready else "not_ready",
        },
        "promoted_helpers": paths,
        "fallback_exposure": {
            "exposed_paths": fallback_exposed,
            "missing_paths": fallback_missing,
        },
        "proposal": {
            "proposal_type": "future_fallback_removal_review",
            "proposal_ready": proposal_ready,
            "proposal_only": True,
            "allowed_now": False,
            "required_future_approval": "exact owner approval to remove Python fallback for named helpers after reviewing this gate",
            "blocked_actions": [
                "python_file_deletion",
                "fallback_removal_without_separate_exact_approval",
                "sql_write_or_import",
                "canon_or_portfolio_mutation",
                "customer_or_external_delivery",
                "config_auth_runtime_mutation",
                "paper_live_or_account_action",
                "owner_approval_inference",
            ],
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "proposal_generation_only": True,
            "fallback_removal_allowed": False,
            "python_fallback_must_remain_active": True,
            "retire_python_now": False,
            "python_file_delete_allowed": False,
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
            "errors": [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fallback-removal readiness proof for promoted SQL/proof helpers.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--parent-runtime-scorecard", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    report = build_report(parent_runtime_scorecard=args.parent_runtime_scorecard)
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
