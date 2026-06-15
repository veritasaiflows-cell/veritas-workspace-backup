#!/usr/bin/env python3
"""Shared routing metadata for bounded Go SQL validator binary pilots.

This registry is intentionally narrow. It describes the helpers Randall
approved for compiled-binary Go-validator routing and keeps Python owner/default,
deletion, SQL write/import, canon/portfolio, external/customer, and
paper/live/account authority outside this route.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GO_ROOT = ROOT / "scripts" / "go"
GO_BIN_DIR = TMP / "go-binaries"

SELECTED_INPROCESS_BINARY_HELPERS: list[dict[str, Any]] = [
    {
        "key": "go_sql_inventory_helper",
        "command": ".\\cmd\\go-sql-inventory-helper",
        "binary": "go-sql-inventory-helper.exe",
        "cli_out": TMP / "go-sql-inventory-helper.json",
        "comparison_cli_out": TMP / "go-sql-inventory-helper-cli-comparison.json",
        "inprocess_out": TMP / "go-sql-inventory-helper-inprocess.json",
        "args": ["--root", "..\\.."],
        "sqlite_flag": "--sqlite3",
        "summary_fields": ["databases", "present", "missing", "warning_dbs", "blocked_dbs", "tables", "views", "total_rows", "missing_tables", "row_count_errors"],
        "row_fields": ["summary", "databases"],
    },
    {
        "key": "go_sql_latency_probe",
        "command": ".\\cmd\\go-sql-latency-probe",
        "binary": "go-sql-latency-probe.exe",
        "cli_out": TMP / "go-sql-latency-probe.json",
        "comparison_cli_out": TMP / "go-sql-latency-probe-cli-comparison.json",
        "inprocess_out": TMP / "go-sql-latency-probe-inprocess.json",
        "args": ["--root", "..\\..", "--iterations", "5"],
        "sqlite_flag": "--sqlite",
        "summary_fields": ["benchmarks", "successful", "failed_or_missing"],
        "row_fields": ["summary", "results"],
    },
    {
        "key": "go_finance_human_notes_sql_check",
        "command": ".\\cmd\\go-finance-human-notes-sql-check",
        "binary": "go-finance-human-notes-sql-check.exe",
        "cli_out": TMP / "go-finance-human-notes-sql-check.json",
        "comparison_cli_out": TMP / "go-finance-human-notes-sql-check-cli-comparison.json",
        "inprocess_out": TMP / "go-finance-human-notes-sql-check-inprocess.json",
        "args": ["--root", "..\\.."],
        "sqlite_flag": "--sqlite3",
        "summary_fields": [],
        "row_fields": ["sql_canon_check"],
    },
    {
        "key": "go_finance_data_coverage_probe",
        "command": ".\\cmd\\go-finance-data-coverage-probe",
        "binary": "go-finance-data-coverage-probe.exe",
        "cli_out": TMP / "go-finance-data-coverage-probe.json",
        "comparison_cli_out": TMP / "go-finance-data-coverage-probe-cli-comparison.json",
        "inprocess_out": TMP / "go-finance-data-coverage-probe-inprocess.json",
        "args": ["--root", "..\\.."],
        "requires_sqlite_driver": False,
        "summary_fields": ["source_artifact_count", "ticker_count_indexed", "data_family_count", "universe_ticker_count"],
        "row_fields": ["summary", "source_artifacts", "authority_boundary", "validation"],
    },
    {
        "key": "go_source_truth_parity_validator",
        "command": ".\\cmd\\go-source-truth-parity-validator",
        "binary": "go-source-truth-parity-validator.exe",
        "cli_out": TMP / "go-source-truth-parity-validation.json",
        "comparison_cli_out": TMP / "go-source-truth-parity-validation-cli-comparison.json",
        "inprocess_out": TMP / "go-source-truth-parity-validation-inprocess.json",
        "args": ["--root", "..\\.."],
        "sqlite_flag": "--sqlite3",
        "summary_fields": ["markdown_rows", "ready_rows", "mismatch_rows"],
        "row_fields": ["summary", "checks", "authority_boundary"],
    },
]

PROBE_ONLY_INPROCESS_HELPERS: list[dict[str, Any]] = [
    {
        "key": "go_sql_source_truth_manifest",
        "command": ".\\cmd\\go-sql-source-truth-manifest",
        "cli_out": TMP / "go-sql-source-truth-authority-manifest-cli-comparison.json",
        "inprocess_out": TMP / "go-sql-source-truth-authority-manifest-inprocess.json",
        "args": ["--root", "..\\.."],
        "summary_fields": ["database_surfaces", "canonical_owner_notes", "errors"],
        "row_fields": ["summary", "database_surfaces", "canonical_owner_notes", "authority_boundary"],
    },
    {
        "key": "go_sql_500_expansion_gate",
        "command": ".\\cmd\\go-sql-500-expansion-design-gate",
        "cli_out": TMP / "go-sql-500-ticker-expansion-design-gate-cli-comparison.json",
        "inprocess_out": TMP / "go-sql-500-ticker-expansion-design-gate-inprocess.json",
        "args": ["--root", "..\\.."],
        "summary_fields": [],
        "row_fields": ["status", "current_state", "validation", "authority_boundary"],
    },
    {
        "key": "go_sql_consumer_authority_guard",
        "command": ".\\cmd\\go-sql-consumer-authority-guard",
        "cli_out": TMP / "go-sql-consumer-authority-guard-cli-comparison.json",
        "inprocess_out": TMP / "go-sql-consumer-authority-guard-inprocess.json",
        "args": ["--root", "..\\.."],
        "summary_fields": ["checks", "failed", "fallback_missing_keys", "extra_keys", "cache_stale_or_unsafe_rows"],
        "row_fields": ["summary", "authority_boundary", "sql_read_allowed"],
    },
    {
        "key": "sql_schema_drift_lint",
        "command": ".\\cmd\\sql-schema-drift-lint",
        "cli_out": TMP / "sql-schema-drift-lint-cli-comparison.json",
        "inprocess_out": TMP / "sql-schema-drift-lint-inprocess.json",
        "args": ["--root", "..\\.."],
        "summary_fields": ["checks", "failed", "warning"],
        "row_fields": ["summary", "checks", "authority_boundary"],
    },
    {
        "key": "sql_proof_probe",
        "command": ".\\cmd\\sql-proof-probe",
        "cli_out": TMP / "sql-proof-probe-cli-comparison.json",
        "inprocess_out": TMP / "sql-proof-probe-inprocess.json",
        "args": ["--root", "..\\.."],
        "summary_fields": ["checks", "failed", "warning"],
        "row_fields": ["summary", "checks", "authority_boundary"],
    },
]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def binary_path(helper: dict[str, Any]) -> Path:
    return GO_BIN_DIR / str(helper["binary"])


def root_args(helper: dict[str, Any]) -> list[str]:
    return [str(ROOT) if str(arg) == "..\\.." else str(arg) for arg in helper["args"]]


def go_run_command(helper: dict[str, Any], out: Path, driver: str = "cli") -> list[str]:
    command = ["go", "run", str(helper["command"]), *[str(arg) for arg in helper["args"]]]
    command.extend(["--driver", driver])
    command.extend(["--out", "..\\..\\" + rel(out).replace("/", "\\")])
    return command


def build_command(helper: dict[str, Any]) -> list[str]:
    return ["go", "build", "-o", str(binary_path(helper)), str(helper["command"])]


def binary_default_command(helper: dict[str, Any], out: Path | None = None) -> list[str]:
    output = out or helper["cli_out"]
    return [str(binary_path(helper)), *root_args(helper), "--driver", "inprocess", "--out", str(output)]


def rollback_instruction(helper: dict[str, Any]) -> str:
    return (
        f"Rollback: restore {helper['key']} command routing to go run {helper['command']} "
        "with the previous arguments and rerun pilot gate, runtime scorecard, "
        "harness, PM cockpit validation, and artifact index validation."
    )


def _check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def validate_registry() -> dict[str, Any]:
    """Validate bounded helper routing metadata.

    This is a read-only contract check. It does not execute helpers, touch
    SQLite databases, write SQL, mutate canon/portfolio state, change customer
    delivery, infer owner approval, or touch paper/live/account surfaces.
    """
    checks: list[dict[str, Any]] = []
    all_helpers = SELECTED_INPROCESS_BINARY_HELPERS + PROBE_ONLY_INPROCESS_HELPERS
    keys = [str(helper.get("key", "")) for helper in all_helpers]

    _check(checks, "helper_keys_unique", len(keys) == len(set(keys)), "all helper keys must be unique")
    _check(checks, "selected_helpers_present", len(SELECTED_INPROCESS_BINARY_HELPERS) == 5, "five approved selected helpers")

    for helper in SELECTED_INPROCESS_BINARY_HELPERS:
        key = str(helper["key"])
        default_command = binary_default_command(helper)
        requires_sqlite_driver = helper.get("requires_sqlite_driver", True) is not False
        _check(checks, f"{key}_has_binary", bool(helper.get("binary")), "selected helpers must have compiled binary metadata")
        _check(
            checks,
            f"{key}_has_sqlite_flag_or_exemption",
            (helper.get("sqlite_flag") in {"--sqlite", "--sqlite3"}) if requires_sqlite_driver else "sqlite_flag" not in helper,
            "selected helpers must expose a sqlite binary override flag unless they do not use SQLite",
        )
        _check(checks, f"{key}_default_driver_inprocess", "--driver" in default_command and "inprocess" in default_command, "compiled-binary default route must pass --driver inprocess")
        _check(checks, f"{key}_default_out_not_cli_comparison", not str(helper["cli_out"]).endswith("-cli-comparison.json"), "default artifact must not be the CLI comparison artifact")
        _check(checks, f"{key}_comparison_out_is_cli_comparison", str(helper["comparison_cli_out"]).endswith("-cli-comparison.json"), "comparison artifact must be clearly CLI-scoped")
        _check(checks, f"{key}_rollback_instruction_present", "rollback" in rollback_instruction(helper).lower(), "selected helper must have rollback instruction")

    for helper in PROBE_ONLY_INPROCESS_HELPERS:
        key = str(helper["key"])
        _check(checks, f"{key}_probe_only_has_no_binary_default", "binary" not in helper, "probe-only helpers must not become compiled-binary defaults through this registry")
        _check(checks, f"{key}_cli_comparison_explicit_artifact", str(helper["cli_out"]).endswith("-cli-comparison.json"), "probe-only CLI output must remain comparison-scoped")

    ok = all(check["ok"] for check in checks)
    return {
        "schema_version": "go_sql_helper_route_registry_validation.v1",
        "status": "ok" if ok else "blocked",
        "selected_helper_keys": [helper["key"] for helper in SELECTED_INPROCESS_BINARY_HELPERS],
        "probe_only_helper_keys": [helper["key"] for helper in PROBE_ONLY_INPROCESS_HELPERS],
        "checks": checks,
        "authority_boundary": (
            "Read-only route metadata validation only. No SQL writes/imports, "
            "canon/portfolio mutation, customer/external delivery, Python fallback "
            "removal, Python deletion, paper/live/account action, config/auth/runtime "
            "change outside bounded helper routing, or owner approval inference."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true", help="validate bounded helper routing metadata")
    args = parser.parse_args(argv)
    if not args.validate:
        parser.print_help()
        return 0
    report = validate_registry()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
