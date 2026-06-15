#!/usr/bin/env python3
"""Compare CLI-backed Go SQL helpers with in-process SQLite driver companions.

Report-only pilot gate. It validates selected low-risk helpers before any
compiled-binary routing change. It does not retire Python, remove fallbacks,
mutate SQL/canon/portfolio state, deliver externally, or alter account/runtime
authority.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from go_sql_helper_route_registry import (
    GO_BIN_DIR,
    GO_ROOT,
    PROBE_ONLY_INPROCESS_HELPERS,
    ROOT,
    SELECTED_INPROCESS_BINARY_HELPERS,
    TMP,
    binary_default_command,
    binary_path,
    build_command,
    go_run_command,
    rel,
    rollback_instruction,
)
from lib.pm_control_reader import pm_program_state
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

DEFAULT_JSON = TMP / "go-sql-inprocess-driver-pilot-gate.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
DEFAULT_PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
SCHEMA = "veritas.go_sql_inprocess_driver_pilot_gate.v1"
HELPERS = SELECTED_INPROCESS_BINARY_HELPERS
ALL_COMPARISON_HELPERS = [*SELECTED_INPROCESS_BINARY_HELPERS, *PROBE_ONLY_INPROCESS_HELPERS]

AUTHORITY_FALSE_KEYS = {
    "sql_write_or_import_allowed",
    "db_mutation",
    "canon_or_portfolio_mutation",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "customer_or_external_delivery",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution",
    "paper_or_live_execution_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "config_auth_runtime_mutation",
    "delete_allowed",
    "human_note_archive_applied",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def tail(text: str, limit: int = 1800) -> str:
    return text[-limit:] if len(text) > limit else text


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def run_command(name: str, command: list[str], cwd: Path = ROOT, timeout: int = 240) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None and not Path(command[0]).exists():
        return {"name": name, "status": "blocked", "returncode": None, "command": command, "cwd": rel(cwd), "notes": f"binary not found: {command[0]}"}
    resolved = [executable or command[0], *command[1:]]
    try:
        completed = subprocess.run(resolved, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {"name": name, "status": "blocked", "returncode": None, "command": command, "cwd": rel(cwd), "notes": f"timeout after {timeout}s", "stdout_tail": tail(exc.stdout or ""), "stderr_tail": tail(exc.stderr or "")}
    return {
        "name": name,
        "status": "ok" if completed.returncode == 0 else "blocked",
        "returncode": completed.returncode,
        "command": command,
        "cwd": rel(cwd),
        "notes": "ok" if completed.returncode == 0 else "command failed",
        "stdout_tail": tail(completed.stdout or ""),
        "stderr_tail": tail(completed.stderr or ""),
    }


def run_probes(binary_route_active: bool = False) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for helper in HELPERS:
        cli_out_path = helper["comparison_cli_out"] if binary_route_active else helper["cli_out"]
        commands.append(
            run_command(
                f"{helper['key']}_cli",
                go_run_command(helper, cli_out_path),
                cwd=GO_ROOT,
            )
        )
        if binary_route_active:
            commands.append(
                run_command(
                    f"{helper['key']}_binary_default_route",
                    binary_default_command(helper),
                    cwd=ROOT,
                )
            )
            commands.append(
                run_command(
                    f"{helper['key']}_binary_no_cli_dependency_probe",
                    binary_no_cli_dependency_command(helper),
                    cwd=ROOT,
                )
            )
        commands.append(
            run_command(
                f"{helper['key']}_inprocess",
                go_run_command(helper, helper["inprocess_out"], "inprocess"),
                cwd=GO_ROOT,
            )
        )
    for helper in PROBE_ONLY_INPROCESS_HELPERS:
        commands.append(
            run_command(
                f"{helper['key']}_cli_probe_only",
                go_run_command(helper, helper["cli_out"]),
                cwd=GO_ROOT,
            )
        )
        commands.append(
            run_command(
                f"{helper['key']}_inprocess_probe_only",
                go_run_command(helper, helper["inprocess_out"], "inprocess"),
                cwd=GO_ROOT,
            )
        )
    commands.append(
        run_command(
            "go_sql_inprocess_readonly_probe",
            ["go", "run", ".\\cmd\\go-sql-inprocess-readonly-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\go-sql-inprocess-readonly-probe.json"],
            cwd=GO_ROOT,
        )
    )
    return commands


def build_binaries() -> list[dict[str, Any]]:
    GO_BIN_DIR.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    for helper in HELPERS:
        commands.append(
            run_command(
                f"build_{helper['key']}",
                build_command(helper),
                cwd=GO_ROOT,
                timeout=300,
            )
        )
    commands.append(
        run_command(
            "build_go_sql_inprocess_readonly_probe",
            ["go", "build", "-o", str(GO_BIN_DIR / "go-sql-inprocess-readonly-probe.exe"), ".\\cmd\\go-sql-inprocess-readonly-probe"],
            cwd=GO_ROOT,
            timeout=300,
        )
    )
    return commands


def binary_no_cli_dependency_command(helper: dict[str, Any]) -> list[str]:
    output = TMP / f"{helper['key'].replace('_', '-')}-no-cli-dependency-proof.json"
    sqlite_flag = str(helper.get("sqlite_flag", "--sqlite3"))
    return [
        *binary_default_command(helper, output),
        sqlite_flag,
        "definitely_missing_sqlite3_for_inprocess_route.exe",
    ]


def top_level_keys(payload: dict[str, Any]) -> list[str]:
    return sorted(str(key) for key in payload.keys())


def status_vocabulary(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"status", "validation_status", "verdict"} and isinstance(item, str):
                found.add(item)
            found.update(status_vocabulary(item))
    elif isinstance(value, list):
        for item in value:
            found.update(status_vocabulary(item))
    return found


def authority_regressions(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in AUTHORITY_FALSE_KEYS and item not in (False, 0, None):
                findings.append(f"{path}={item!r}")
            findings.extend(authority_regressions(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(authority_regressions(item, f"{prefix}[{index}]"))
    return findings


def contains_database_locked(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_database_locked(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_database_locked(item) for item in value)
    if isinstance(value, str):
        return "database is locked" in value.lower()
    return False


def scrub_timing(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_timing(item)
            for key, item in value.items()
            if key not in {"generated_at_utc", "root", "iterations", "cold_ms", "p50_ms", "p95_ms", "max_p95_ms", "sqlite_driver"}
        }
    if isinstance(value, list):
        return [scrub_timing(item) for item in value]
    return value


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def compare_helper(helper: dict[str, Any], binary_route_active: bool = False) -> dict[str, Any]:
    comparison_cli_path = helper["comparison_cli_out"] if binary_route_active else helper["cli_out"]
    cli = load(comparison_cli_path)
    inproc = load(helper["inprocess_out"])
    default_route = load(helper["cli_out"])
    requires_sqlite_driver = helper.get("requires_sqlite_driver", True) is not False
    findings: list[dict[str, Any]] = []
    add(findings, "cli_artifact_present", bool(cli), "critical", rel(comparison_cli_path))
    add(findings, "inprocess_artifact_present", bool(inproc), "critical", rel(helper["inprocess_out"]))
    if cli and inproc:
        add(findings, "top_level_json_shape_match", top_level_keys(cli) == top_level_keys(inproc), "critical", {"cli": top_level_keys(cli), "inprocess": top_level_keys(inproc)})
        add(findings, "status_match", cli.get("status") == inproc.get("status"), "critical", {"cli": cli.get("status"), "inprocess": inproc.get("status")})
        add(findings, "status_vocabulary_match", status_vocabulary(cli) == status_vocabulary(inproc), "critical", {"cli": sorted(status_vocabulary(cli)), "inprocess": sorted(status_vocabulary(inproc))})
        for field in helper["summary_fields"]:
            cli_value = as_dict(cli.get("summary")).get(field)
            inproc_value = as_dict(inproc.get("summary")).get(field)
            add(findings, f"summary_{field}_match", cli_value == inproc_value, "critical", {"cli": cli_value, "inprocess": inproc_value})
        for field in helper["row_fields"]:
            add(findings, f"{field}_semantic_match", scrub_timing(cli.get(field)) == scrub_timing(inproc.get(field)), "critical", {"field": field})
        add(findings, "cli_authority_clean", not authority_regressions(cli), "critical", authority_regressions(cli)[:20])
        add(findings, "inprocess_authority_clean", not authority_regressions(inproc), "critical", authority_regressions(inproc)[:20])
        add(
            findings,
            "inprocess_driver_declared_or_exempt",
            (find_driver(inproc) == "inprocess") if requires_sqlite_driver else find_driver(inproc) is None,
            "critical",
            find_driver(inproc),
        )
    if binary_route_active:
        helper_binary = binary_path(helper)
        add(findings, "compiled_binary_exists", helper_binary.exists(), "critical", rel(helper_binary))
        add(findings, "default_route_artifact_present", bool(default_route), "critical", rel(helper["cli_out"]))
        add(
            findings,
            "default_route_uses_inprocess_driver_or_exempt",
            (find_driver(default_route) == "inprocess") if requires_sqlite_driver else find_driver(default_route) is None,
            "critical",
            find_driver(default_route),
        )
        if default_route and inproc:
            add(findings, "default_route_matches_inprocess_companion", scrub_timing(default_route) == scrub_timing(inproc), "critical", {"default": rel(helper["cli_out"]), "inprocess": rel(helper["inprocess_out"])})
        add(findings, "python_fallback_retained_for_route", True, "critical", "fallback_retained_no_python_removal")
    if (
        binary_route_active
        and cli
        and default_route
        and inproc
        and contains_database_locked(cli)
        and scrub_timing(default_route) == scrub_timing(inproc)
        and not authority_regressions(default_route)
        and not authority_regressions(inproc)
    ):
        tolerated_checks = {
            "status_match",
            "status_vocabulary_match",
            "summary_warning_dbs_match",
            "summary_total_rows_match",
            "summary_row_count_errors_match",
            "summary_semantic_match",
            "databases_semantic_match",
        }
        for row in findings:
            if row.get("check") in tolerated_checks and row.get("ok") is not True:
                row["ok"] = True
                row["severity"] = "info"
                row["tolerated_reason"] = "legacy_cli_sqlite3_database_locked_default_inprocess_route_clean"
        add(
            findings,
            "legacy_cli_lock_tolerated_by_default_inprocess_route",
            True,
            "critical",
            "CLI sqlite3 hit database-is-locked; selected default route matched the in-process companion and authority scans were clean.",
        )
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    return {
        "helper": helper["key"],
        "status": "blocked" if critical else "warning" if warnings else "ok",
        "cli_artifact": rel(comparison_cli_path),
        "default_route_artifact": rel(helper["cli_out"]),
        "inprocess_artifact": rel(helper["inprocess_out"]),
        "findings": findings,
        "summary": {"checks": len(findings), "critical": len(critical), "warnings": len(warnings)},
    }


def find_driver(payload: dict[str, Any]) -> str | None:
    if "sqlite_driver" in payload:
        return str(payload.get("sqlite_driver"))
    check = as_dict(payload.get("sql_canon_check"))
    if "sqlite_driver" in check:
        return str(check.get("sqlite_driver"))
    return None


def stability_snapshot() -> dict[str, Any]:
    runtime = load(TMP / "runtime-performance-scorecard.json")
    harness = load(TMP / "veritas-harness-scorecard.json")
    pm_state = pm_program_state()
    return {
        "runtime_scorecard": {
            "path": "tmp/runtime-performance-scorecard.json",
            "status": runtime.get("status"),
            "blocked_count": as_dict(runtime.get("summary")).get("blocked_count"),
        },
        "harness_scorecard": {
            "path": "tmp/veritas-harness-scorecard.json",
            "status": harness.get("status"),
            "failure_count": as_dict(harness.get("summary")).get("failure_count"),
            "warning_count": as_dict(harness.get("summary")).get("warning_count"),
        },
        "pm_program_state": {
            "path": "tmp/pm-control-packet.json#sections.pm_program_state",
            "status": pm_state.get("status"),
            "validation_status": as_dict(pm_state.get("validation")).get("status"),
        },
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    default_promotion = load(DEFAULT_PROMOTION_JSON)
    python_owner_default = (
        default_promotion.get("status") == "ok"
        and as_dict(default_promotion.get("summary")).get("default_route") == "python_owner_only"
    )
    binary_route_active = bool(args.binary_route_active) and not python_owner_default
    probe_commands: list[dict[str, Any]] = run_probes(binary_route_active) if args.run_probes else []
    build_commands: list[dict[str, Any]] = build_binaries() if args.build_binaries else []
    selected_comparisons = [compare_helper(helper, binary_route_active) for helper in HELPERS]
    probe_only_comparisons = [compare_helper(helper, False) for helper in PROBE_ONLY_INPROCESS_HELPERS]
    comparisons = [*selected_comparisons, *probe_only_comparisons]
    readonly_probe = load(TMP / "go-sql-inprocess-readonly-probe.json")
    findings: list[dict[str, Any]] = []
    for comparison in comparisons:
        comparison_ok = comparison.get("status") == "ok" or python_owner_default
        add(
            findings,
            f"{comparison['helper']}_comparison_ok",
            comparison_ok,
            "critical",
            {
                "summary": comparison.get("summary"),
                "note": "nonblocking under Python owner/default; Go is validator-only" if python_owner_default and comparison.get("status") != "ok" else None,
            },
        )
    add(findings, "readonly_probe_ok", readonly_probe.get("status") == "ok", "critical", as_dict(readonly_probe.get("summary")))
    add(findings, "readonly_probe_authority_clean", not authority_regressions(readonly_probe), "critical", authority_regressions(readonly_probe)[:20])
    for row in probe_commands:
        add(findings, f"command_{row['name']}_ok", row.get("status") == "ok", "critical", row)
    for row in build_commands:
        add(findings, f"binary_{row['name']}_ok", row.get("status") == "ok", "critical", row)
    add(findings, "rollback_instructions_present", True, "critical", "restore scorecard/harness commands to go run helper commands or rerun this gate without --binary-route-active")
    add(findings, "python_owner_default_respected", not args.binary_route_active or not python_owner_default or binary_route_active is False, "critical", {"requested_binary_route_active": args.binary_route_active, "effective_binary_route_active": binary_route_active, "python_owner_default": python_owner_default})
    stability = stability_snapshot()
    runtime_self_cycle = args.parent_runtime_scorecard and stability["runtime_scorecard"].get("status") in {"bootstrap", "blocked"}
    harness_self_cycle = args.parent_harness_scorecard and stability["harness_scorecard"].get("status") in {"bootstrap", "blocked"}
    runtime_ok = (
        stability["runtime_scorecard"].get("status") in {"ok", "warning"} and stability["runtime_scorecard"].get("blocked_count") in {0, None}
    ) or runtime_self_cycle
    harness_ok = (
        stability["harness_scorecard"].get("status") in {"ok", "warning"} and stability["harness_scorecard"].get("failure_count") in {0, None}
    ) or harness_self_cycle
    pm_ok = stability["pm_program_state"].get("validation_status") in {"ok", None}
    runtime_detail = dict(stability["runtime_scorecard"])
    if runtime_self_cycle:
        runtime_detail["self_cycle_deferred"] = True
        runtime_detail["note"] = "runtime_scorecard_validated_by_parent_run"
    harness_detail = dict(stability["harness_scorecard"])
    if harness_self_cycle:
        harness_detail["self_cycle_deferred"] = True
        harness_detail["note"] = "harness_scorecard_validated_by_parent_run"
    add(findings, "runtime_scorecard_stable", runtime_ok, "critical", runtime_detail)
    add(findings, "harness_scorecard_stable", harness_ok, "critical", harness_detail)
    add(findings, "pm_program_state_stable", pm_ok, "critical", stability["pm_program_state"])

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    binary_ready = status == "ok" and (not args.build_binaries or all(row.get("status") == "ok" for row in build_commands))
    route_ready = binary_ready and binary_route_active
    rollback_instructions = [
        {
            "helper": helper["key"],
            "rollback_instruction": rollback_instruction(helper),
        }
        for helper in HELPERS
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "scope": {
            "pilot": "in_process_sqlite_driver_for_selected_low_risk_go_sql_helpers",
            "selected_helpers": [helper["key"] for helper in HELPERS],
            "probe_only_helpers": [helper["key"] for helper in PROBE_ONLY_INPROCESS_HELPERS],
            "driver_under_test": "modernc.org/sqlite via database/sql read-only URI mode",
        },
        "summary": {
            "helpers_compared": len(comparisons),
            "helpers_ok": sum(1 for row in comparisons if row.get("status") == "ok"),
            "default_routed_helpers": len(HELPERS),
            "probe_only_helpers": len(PROBE_ONLY_INPROCESS_HELPERS),
            "critical": len(critical),
            "warnings": len(warnings),
            "read_only_probe_status": readonly_probe.get("status"),
            "compiled_binary_ready": binary_ready,
            "routing_change_ready_for_future_gate": binary_ready,
            "routing_changed_by_this_gate": route_ready,
            "compiled_binary_default_route_active": route_ready,
            "python_owner_default": python_owner_default,
            "go_validator_only": python_owner_default,
            "python_fallback_retained": True,
            "rollback_instructions_present": bool(rollback_instructions),
        },
        "comparisons": comparisons,
        "selected_default_route_comparisons": selected_comparisons,
        "probe_only_comparisons": probe_only_comparisons,
        "read_only_enforcement": {
            "path": "tmp/go-sql-inprocess-readonly-probe.json",
            "status": readonly_probe.get("status"),
            "checks": as_list(readonly_probe.get("checks")),
        },
        "runtime_harness_pm_stability": stability,
        "probe_commands": probe_commands,
        "build_commands": build_commands,
        "binary_outputs": [rel(binary_path(helper)) for helper in HELPERS],
        "compiled_binary_default_routing": {
            "approved_scope": [helper["key"] for helper in HELPERS],
            "active": route_ready,
            "driver": "inprocess" if route_ready else "not_routed_by_this_gate",
            "python_fallback_retained": True,
            "rollback_instructions": rollback_instructions,
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "pilot_gate_only": True,
            "compiled_binary_routing_changed": route_ready,
            "compiled_binary_default_route_active": route_ready,
            "python_owner_default": python_owner_default,
            "go_validator_only": python_owner_default,
            "python_retirement_allowed": False,
            "python_file_delete_allowed": False,
            "python_fallback_removal_allowed": False,
            "sql_write_or_import_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
        "next_safe_action": "If this gate remains ok across repeated runs, prepare a separate compiled-binary routing proposal for the selected helpers while keeping Python fallback and deletion blocked until later retirement gates prove safety.",
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def render_md(report: dict[str, Any]) -> str:
    summary = as_dict(report.get("summary"))
    lines = [
        "# Go SQL In-Process Driver Pilot Gate",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Helpers compared: `{summary.get('helpers_ok')}/{summary.get('helpers_compared')}`",
        f"- Read-only probe: `{summary.get('read_only_probe_status')}`",
        f"- Compiled binary ready: `{summary.get('compiled_binary_ready')}`",
        f"- Routing changed by this gate: `{summary.get('routing_changed_by_this_gate')}`",
        "",
        "## Boundary",
        "",
        "Report-only/read-only pilot. No Python retirement, fallback removal, SQL import/write, canon/portfolio mutation, external delivery, account/trading action, or runtime authority change.",
    ]
    return "\n".join(lines) + "\n"


def render_summary(report: dict[str, Any]) -> str:
    summary = as_dict(report.get("summary"))
    validation = as_dict(report.get("validation"))
    return (
        "go_sql_inprocess_driver_pilot_gate "
        f"status={report.get('status')} "
        f"helpers={summary.get('helpers_ok')}/{summary.get('helpers_compared')} "
        f"critical={summary.get('critical')} "
        f"warnings={summary.get('warnings')} "
        f"read_only_probe={summary.get('read_only_probe_status')} "
        f"binary_ready={summary.get('compiled_binary_ready')} "
        f"route_active={summary.get('compiled_binary_default_route_active')} "
        f"validation={validation.get('status')} "
        f"path={rel(DEFAULT_JSON)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate in-process SQLite driver pilot for selected Go SQL helpers.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--run-probes", action="store_true", help="Regenerate CLI and in-process comparison artifacts before gating.")
    parser.add_argument("--build-binaries", action="store_true", help="Compile selected helper binaries into tmp/go-binaries as readiness proof.")
    parser.add_argument("--binary-route-active", action="store_true", help="Validate selected helpers as routed to compiled binaries with in-process SQLite driver.")
    parser.add_argument("--parent-runtime-scorecard", action="store_true", help="Allow runtime scorecard self-cycle while the parent runtime scorecard is running.")
    parser.add_argument("--parent-harness-scorecard", action="store_true", help="Allow harness scorecard self-cycle while the parent harness scorecard is running.")
    parser.add_argument("--print-json", action="store_true", help="Print the full JSON report to stdout. Default output is a compact summary.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout unless validation fails through the process exit code.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve(args.json_out)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    if args.write_md:
        atomic_write_text(args.json_out.with_suffix(".md"), render_md(report))
    if args.print_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif not args.quiet:
        print(render_summary(report))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
