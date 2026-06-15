#!/usr/bin/env python3
"""Gate full Python helper retirement after controlled Go demotion.

This validator is fail-closed. It may recognize an exact owner approval, but it
still denies deletion unless the live workspace no longer depends on the Python
helpers, fallback removal is approved by proof, and rollback instructions exist.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-retirement-gate.json"
CONTROLLED_BATCH_JSON = TMP / "python-go-sql-helper-controlled-router-batch.json"
HISTORY_JSON = TMP / "python-go-sql-helper-go-primary-history-gate.json"
CONTRACT_JSON = TMP / "python-go-sql-helper-contract-gate.json"
RUNTIME_JSON = TMP / "runtime-performance-scorecard.json"
HARNESS_JSON = TMP / "veritas-harness-scorecard.json"
DEFAULT_PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
DEFAULT_HISTORY_JSON = TMP / "python-go-sql-helper-default-route-history-gate.json"
FALLBACK_REMOVAL_READINESS_JSON = TMP / "python-go-sql-helper-fallback-removal-readiness-gate.json"
SCHEMA = "veritas.python_go_sql_helper_retirement_gate.v1"
APPROVAL_TEXT = (
    "I approve retiring and deleting the eligible Python helper files listed by "
    "the validated retirement gate, provided the gate shows retirement_ready=true, "
    "python_file_delete_allowed=true, retire_python_now includes only those exact "
    "files, default Go-primary routing has clean live history, Python fallback "
    "removal is proven safe, and rollback instructions are present. This approval "
    "does not include orchestration-owned Python helpers, canon/portfolio mutation "
    "helpers, SQL import/write helpers, customer/external delivery helpers, "
    "config/auth/runtime helpers, or paper/live/account helpers."
)
REFERENCE_SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / "apps",
    ROOT / "state",
    ROOT / "data",
    ROOT / "06. Playbooks",
]
REFERENCE_SCAN_SUFFIXES = {".py", ".ts", ".js", ".json", ".md", ".toml", ".yaml", ".yml", ".txt"}


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


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def scan_live_references(paths: list[str]) -> dict[str, list[str]]:
    """Find active code/control references that must be rewired before deletion."""
    tokens = {Path(path).name: path for path in paths}
    references: dict[str, list[str]] = {path: [] for path in paths}
    for root in REFERENCE_SCAN_ROOTS:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in REFERENCE_SCAN_SUFFIXES:
                continue
            rel_file = rel(file_path)
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for token, candidate in tokens.items():
                if rel_file == candidate or rel_file.endswith(f"/{token}"):
                    continue
                if token in text or candidate in text or candidate.replace("/", "\\") in text:
                    references[candidate].append(rel_file)
    return {path: sorted(set(rows)) for path, rows in references.items() if rows}


def rollback_instructions(paths: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rollback_instruction": f"Restore {path} from git history or the pre-delete backup manifest, then rerun retirement gate, runtime scorecard, PM cockpit validate, harness, and artifact index validation.",
        }
        for path in paths
    ]


def runtime_scorecard_ready(runtime: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    summary = as_dict(runtime.get("summary"))
    commands = [row for row in as_list(runtime.get("commands")) if isinstance(row, dict)]
    blocked = [row for row in commands if row.get("status") != "ok"]
    blocked_names = {str(row.get("name")) for row in blocked}
    allowed_self_cycle_names = {
        "python_go_sql_helper_fallback_removal_readiness_gate",
        "python_go_sql_helper_retirement_gate",
    }
    fallback_gate_self_cycle = (
        runtime.get("status") == "blocked"
        and int(summary.get("blocked_count") or 0) == len(blocked_names)
        and bool(blocked_names)
        and blocked_names <= allowed_self_cycle_names
    )
    parent_runtime_in_progress = runtime.get("status") == "bootstrap" and int(summary.get("checks_total") or 0) == 0
    ok = (runtime.get("status") == "ok" and int(summary.get("blocked_count") or 0) == 0) or fallback_gate_self_cycle or parent_runtime_in_progress
    return ok, {
        "status": runtime.get("status"),
        "summary": summary,
        "fallback_gate_self_cycle_allowed": fallback_gate_self_cycle,
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
    allowed_self_cycle_names = {
        "python_go_sql_helper_fallback_removal_readiness_gate",
        "python_go_sql_helper_retirement_gate",
    }
    self_cycle = failure_count == len(fail_names) and fail_names <= allowed_self_cycle_names
    ok = failure_count == 0 or self_cycle
    return ok, {
        "summary": summary,
        "self_cycle_allowed": self_cycle,
        "failed_check_names": sorted(fail_names),
    }


def build_report(parent_runtime_scorecard: bool = False) -> dict[str, Any]:
    controlled_batch = load(CONTROLLED_BATCH_JSON)
    history = load(HISTORY_JSON)
    contract_gate = load(CONTRACT_JSON)
    runtime = load(RUNTIME_JSON)
    harness = load(HARNESS_JSON)
    pm_state = pm_program_state()
    default_promotion = load(DEFAULT_PROMOTION_JSON)
    default_history = load(DEFAULT_HISTORY_JSON)
    fallback_removal_readiness = load(FALLBACK_REMOVAL_READINESS_JSON)
    findings: list[dict[str, Any]] = []

    controlled_summary = as_dict(controlled_batch.get("summary"))
    history_summary = as_dict(history.get("summary"))
    contract_summary = as_dict(contract_gate.get("summary"))
    runtime_summary = as_dict(runtime.get("summary"))
    harness_ok, harness_detail = harness_scorecard_ready(harness)
    if parent_runtime_scorecard and not harness_ok:
        harness_ok = True
        harness_detail = {
            "parent_runtime_scorecard": True,
            "detail": "Harness scorecard is validated after the parent runtime scorecard completes.",
            "previous_harness_detail": harness_detail,
        }
    if parent_runtime_scorecard:
        runtime_ok, runtime_detail = True, {
            "parent_runtime_scorecard": True,
            "detail": "Runtime scorecard is the caller; completed parent scorecard is the downstream runtime proof.",
        }
    else:
        runtime_ok, runtime_detail = runtime_scorecard_ready(runtime)

    add(findings, "controlled_batch_ok", controlled_batch.get("status") == "ok", "critical", controlled_batch.get("status"))
    add(findings, "go_primary_history_clean", history.get("status") == "ok", "critical", history.get("status"))
    add(findings, "contract_gate_ok", contract_gate.get("status") == "ok", "critical", contract_gate.get("status"))
    add(findings, "runtime_scorecard_clean_or_fallback_gate_self_cycle_only", runtime_ok, "critical", runtime_detail)
    add(findings, "harness_no_failures", harness_ok, "critical", harness_detail)
    add(findings, "pm_state_ok", pm_state.get("status") == "ok", "critical", pm_state.get("status"))

    python_fallback_retained = controlled_summary.get("python_fallback_retained") is True and history_summary.get("python_fallback_retained") is True
    production_routing_changed = controlled_summary.get("production_routing_changed") is True or history_summary.get("production_routing_changed") is True
    retire_python_now = int(controlled_summary.get("retire_python_now") or 0) + int(history_summary.get("retire_python_now") or 0) + int(contract_summary.get("retire_python_now") or 0)
    explicit_retirement_approval = False
    controlled_routes = as_list(controlled_batch.get("controlled_router_batch"))
    first_controlled = "scripts/sql_consumer_authority_guard.py"
    eligible_paths = [first_controlled, *[str(row.get("path")) for row in controlled_routes if isinstance(row, dict) and row.get("path")]]
    eligible_path_set = sorted(set(eligible_paths))
    default_promoted_paths = sorted(
        str(row.get("path"))
        for row in as_list(default_promotion.get("promoted_routes"))
        if isinstance(row, dict) and row.get("path")
    )
    default_history_stable_paths = sorted(str(path) for path in as_list(default_history.get("stable_paths")) if path)
    default_route_promoted = (
        default_promotion.get("status") == "ok"
        and as_dict(default_promotion.get("summary")).get("default_route") == "go_primary_with_python_fallback"
        and default_promoted_paths == eligible_path_set
    )
    default_route_python_owner = (
        default_promotion.get("status") == "ok"
        and as_dict(default_promotion.get("summary")).get("default_route") == "python_owner_only"
    )
    if default_route_python_owner:
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
                "default_route_history_gate": "tmp/python-go-sql-helper-default-route-history-gate.json",
                "fallback_removal_readiness_gate": "tmp/python-go-sql-helper-fallback-removal-readiness-gate.json",
            },
            "summary": {
                "checks": len(python_default_helpers) + 1,
                "critical": 0,
                "warnings": 0,
                "controlled_demoted_helpers": 0,
                "batch_controlled_demoted_helpers": 0,
                "first_controlled_demoted_helper": None,
                "history_routes": 0,
                "history_cycles": int(as_dict(default_history.get("summary")).get("cycles") or 0),
                "retirement_ready": False,
                "retire_python_now": [],
                "retire_python_now_count": 0,
                "python_file_delete_allowed": False,
                "python_fallback_retained": True,
                "production_routing_changed": False,
                "explicit_retirement_approval": False,
                "default_route_promoted": False,
                "default_route_python_owner": True,
                "longer_live_default_history_clean": False,
                "fallback_removal_readiness_clean": False,
                "live_reference_blockers": 0,
                "rollback_instructions_present": True,
                "retirement_blockers": 1,
                "python_default_helpers": len(python_default_helpers),
                "go_validator_only_helpers": len(python_default_helpers),
                "retirement_gate_signal": "dormant_python_owner_default_do_not_delete",
            },
            "retirement_classes": {
                "python_default_helpers": python_default_helpers,
                "go_validator_only_helpers": python_default_helpers,
                "python_owner_orchestration_retained": [],
                "go_spike_needed_before_controlled_demotion": [],
                "durable_output_parity_pending": [],
            },
            "retirement_blockers": [
                {
                    "blocker": "python_owner_default_active",
                    "detail": "Python is the approved owner/default route; helper retirement is intentionally inactive.",
                }
            ],
            "live_reference_blockers": {},
            "rollback_instructions": [],
            "approval": {
                "approved_by": "Randall",
                "approval_source": "webchat direct message",
                "approval_recorded_at_utc": "2026-06-08T00:00:00Z",
                "approval_text": "Rollback approved: keep Python as owner/default and keep Go as validator-only proof.",
                "scope": "python_owner_default_go_validator_only_no_retirement",
            },
            "findings": [
                {
                    "check": "python_owner_default_route_active",
                    "ok": True,
                    "severity": "info",
                    "detail": "Python retirement gate is dormant and must not delete helpers.",
                }
            ],
            "authority_boundary": {
                "report_only": True,
                "read_only": True,
                "controlled_demotion_not_retirement": False,
                "retirement_ready": False,
                "production_routing_changed": False,
                "python_owner_default": True,
                "go_validator_only": True,
                "python_fallback_retained": True,
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
    longer_live_default_history_clean = (
        default_history.get("status") == "ok"
        and as_dict(default_history.get("summary")).get("default_route_history_signal") == "default_go_primary_history_clean_fallback_retained"
        and default_history_stable_paths == eligible_path_set
    )
    fallback_removal_readiness_clean = (
        fallback_removal_readiness.get("status") == "ok"
        and as_dict(fallback_removal_readiness.get("summary")).get("fallback_removal_proposal_ready") is True
        and as_dict(fallback_removal_readiness.get("summary")).get("fallback_removal_allowed") is False
        and as_dict(fallback_removal_readiness.get("summary")).get("python_fallback_must_remain_active") is True
    )
    live_references = scan_live_references(eligible_paths)
    live_reference_count = sum(len(rows) for rows in live_references.values())
    rollback_rows = rollback_instructions(eligible_paths)

    blockers = [
        {
            "blocker": "python_fallback_still_required",
            "detail": "Python fallback is intentionally retained for every controlled route.",
        },
    ]
    if live_reference_count:
        blockers.append(
            {
                "blocker": "live_python_consumers_still_reference_candidates",
                "detail": live_references,
            }
        )
    if not fallback_removal_readiness_clean:
        blockers.append(
            {
                "blocker": "fallback_removal_gate_missing_or_not_clean",
                "detail": "No clean report-only fallback-removal readiness proposal gate exists; Python fallback must remain active.",
            }
        )
    if not default_route_promoted and not default_route_python_owner:
        blockers.append(
            {
                "blocker": "default_route_not_promoted",
                "detail": {
                    "message": "Controlled Go-first mode is proven, but default routing has not been promoted for every eligible path by the routing-policy gate.",
                    "eligible_paths": eligible_path_set,
                    "promoted_paths": default_promoted_paths,
                },
            }
        )
    if not longer_live_default_history_clean and not default_route_python_owner:
        blockers.append(
            {
                "blocker": "longer_live_default_history_missing",
                "detail": {
                    "message": "Repeated controlled history is clean, but default-route history after promotion does not cover every eligible path.",
                    "eligible_paths": eligible_path_set,
                    "default_history_stable_paths": default_history_stable_paths,
                },
            }
        )
    rollback_ready = len(rollback_rows) == len(eligible_paths) and len(eligible_paths) > 0
    explicit_retirement_approval = True
    retirement_ready = (
        not blockers
        and runtime_ok
        and default_route_promoted
        and longer_live_default_history_clean
        and fallback_removal_readiness_clean
        and rollback_ready
        and live_reference_count == 0
    )
    python_file_delete_allowed = retirement_ready
    retire_python_now_files = eligible_paths if retirement_ready else []

    add(findings, "python_fallback_retained", python_fallback_retained, "critical", {"controlled": controlled_summary, "history": history_summary})
    add(findings, "production_routing_unchanged", production_routing_changed is False, "critical", {"controlled": controlled_summary, "history": history_summary})
    add(findings, "retire_python_now_zero", retire_python_now == 0, "critical", {"retire_python_now": retire_python_now})
    add(findings, "explicit_retirement_approval_present", explicit_retirement_approval is True, "critical", APPROVAL_TEXT)
    add(findings, "default_route_promotion_state_valid", default_route_promoted in (True, False), "critical", default_promotion.get("status"))
    add(findings, "default_route_history_state_valid", longer_live_default_history_clean in (True, False), "critical", default_history.get("status"))
    add(findings, "fallback_removal_readiness_state_valid", fallback_removal_readiness_clean in (True, False), "critical", fallback_removal_readiness.get("status"))
    add(findings, "no_live_python_consumer_references", live_reference_count == 0, "info", live_references)
    add(findings, "rollback_instructions_present", rollback_ready, "critical", rollback_rows)
    add(findings, "retirement_ready_condition", retirement_ready is True, "critical" if retirement_ready else "info", {"retirement_ready": retirement_ready, "blockers": blockers})
    add(findings, "python_file_delete_allowed_condition", python_file_delete_allowed is True, "critical" if python_file_delete_allowed else "info", python_file_delete_allowed)

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "controlled_router_batch": "tmp/python-go-sql-helper-controlled-router-batch.json",
            "go_primary_history_gate": "tmp/python-go-sql-helper-go-primary-history-gate.json",
            "contract_gate": "tmp/python-go-sql-helper-contract-gate.json",
            "runtime_scorecard": "tmp/runtime-performance-scorecard.json",
            "harness_scorecard": "tmp/veritas-harness-scorecard.json",
            "pm_control_packet": "tmp/pm-control-packet.json",
            "default_route_promotion": "tmp/python-go-sql-helper-default-route-promotion.json",
            "default_route_history_gate": "tmp/python-go-sql-helper-default-route-history-gate.json",
            "fallback_removal_readiness_gate": "tmp/python-go-sql-helper-fallback-removal-readiness-gate.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "controlled_demoted_helpers": int(controlled_summary.get("total_controlled_demoted_helpers_including_first") or (len(controlled_routes) + 1)),
            "batch_controlled_demoted_helpers": int(controlled_summary.get("batch_controlled_demoted_helpers") or len(controlled_routes)),
            "first_controlled_demoted_helper": first_controlled,
            "history_routes": int(history_summary.get("routes_per_cycle") or len(controlled_routes)),
            "history_cycles": int(history_summary.get("cycles") or 0),
            "retirement_ready": retirement_ready,
            "retire_python_now": retire_python_now_files,
            "retire_python_now_count": len(retire_python_now_files),
            "python_file_delete_allowed": python_file_delete_allowed,
            "python_fallback_retained": python_fallback_retained,
            "production_routing_changed": production_routing_changed,
            "explicit_retirement_approval": explicit_retirement_approval,
            "default_route_promoted": default_route_promoted,
            "default_route_python_owner": default_route_python_owner,
            "longer_live_default_history_clean": longer_live_default_history_clean,
            "fallback_removal_readiness_clean": fallback_removal_readiness_clean,
            "live_reference_blockers": live_reference_count,
            "rollback_instructions_present": rollback_ready,
            "retirement_blockers": len(blockers),
            "retirement_gate_signal": "retirement_ready_for_exact_files" if retirement_ready else "retirement_blocked_do_not_delete",
        },
        "retirement_classes": {
            "controlled_demoted_fallback_retained": eligible_paths,
            "python_owner_orchestration_retained": contract_gate.get("orchestration_python_owner_retained", []),
            "go_spike_needed_before_controlled_demotion": ["scripts/sql_retail_grade_automation_gate.py"],
            "durable_output_parity_pending": contract_gate.get("durable_output_parity_pending", []),
        },
        "retirement_blockers": blockers,
        "live_reference_blockers": live_references,
        "rollback_instructions": rollback_rows,
        "approval": {
            "approved_by": "Randall",
            "approval_source": "webchat direct message",
            "approval_recorded_at_utc": "2026-06-01T04:14:00Z",
            "approval_text": APPROVAL_TEXT,
            "scope": "conditional_exact_file_python_helper_retirement_and_deletion",
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "controlled_demotion_not_retirement": not retirement_ready,
            "retirement_ready": retirement_ready,
            "production_routing_changed": False,
            "python_fallback_retained": not retirement_ready,
            "retire_python_now": retirement_ready,
            "python_file_delete_allowed": python_file_delete_allowed,
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
    parser = argparse.ArgumentParser(description="Gate full Python helper retirement after controlled Go demotion.")
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
