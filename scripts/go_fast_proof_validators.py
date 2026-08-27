#!/usr/bin/env python3
"""Run the advisory compiled Go proof validators through a safe Python route.

The validator bundle executor allows guarded Python commands, not arbitrary
executables. This wrapper keeps that safety boundary while still using compiled
Go binaries for the actual read-only checks.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GO_BIN = ROOT / "scripts" / "go" / "bin"
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "go-fast-proof-validators.json"

FULL_PROOF_PACKETS: list[str] = []
IMPLEMENTATION_PROOF_PACKETS = [
    "tmp/finance-sql-canon-access-validation.json",
    "tmp/sql-canon-front-door-readiness-packet.json",
    "tmp/sql-canon-consumer-inventory.json",
    "tmp/sql-canon-consumer-registry-guard.json",
    "tmp/sql-canon-migration-completion-runner.json",
    "tmp/sql-canon-owner-decision-packet.json",
    "tmp/sql-canon-answer-path-ab-harness.json",
    "tmp/reference-levels-sql-native-source-family-proof.json",
]

# This validator consumes the warning-residue report, so its own warnings are
# necessarily produced after the residue classifier has run. Keep those
# post-residue warnings visible, but do not falsely require the earlier report
# to classify findings that did not yet exist.
POST_RESIDUE_VALIDATORS = frozenset({"go-implementation-closeout-ledger-lint"})


@dataclass(frozen=True)
class ValidatorCommand:
    name: str
    argv: list[str]
    out: Path | None


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def binary_path(name: str) -> Path:
    suffix = ".exe" if sys.platform.startswith("win") else ""
    return GO_BIN / f"{name}{suffix}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def proof_packets_for_profile(profile: str) -> list[str]:
    if profile in {"bundle", "implementation"}:
        return list(IMPLEMENTATION_PROOF_PACKETS)
    if profile == "full":
        return list(FULL_PROOF_PACKETS)
    raise ValueError(f"unsupported profile: {profile}")


def add_packet_args(argv: list[str], packets: list[str]) -> None:
    for packet in packets:
        argv.extend(["--packet", packet])


def build_commands(root: Path, write: bool, driver: str, max_age_hours: int, profile: str = "implementation") -> list[ValidatorCommand]:
    proof_packets = proof_packets_for_profile(profile)
    json_out = TMP / "go-json-proof-contract-lint.json" if write else None
    canon_out = TMP / "go-sql-canon-proof-bundle-lint.json" if write else None
    registry_out = TMP / "go-sql-consumer-registry-drift-lint.json" if write else None
    route_budget_out = TMP / "go-validator-route-budget-lint.json" if write else None
    field_family_out = TMP / "go-canon-json-field-family-parity.json" if write else None
    cron_out = TMP / "go-cron-contract-json-proof-lint.json" if write else None
    authority_event_out = TMP / "go-finance-canon-authority-event-lint.json" if write else None
    warning_residue_out = TMP / "go-json-proof-warning-residue-lint.json" if write else None
    source_freshness_out = TMP / "go-sql-source-artifact-freshness-lint.json" if write else None
    source_producer_out = TMP / "go-sql-source-lineage-producer-contract-lint.json" if write else None
    closeout_ledger_out = TMP / "go-implementation-closeout-ledger-lint.json" if write else None
    json_structural_out = TMP / "go-json-proof-structural-validator.json" if write else None
    workflow_freshness_out = TMP / "go-workflow-artifact-freshness-gate.json" if write else None
    band_freshness_out = TMP / "go-entry-stop-band-freshness-validator.json" if write else None
    answer_completeness_out = TMP / "go-finance-answer-completeness-validator.json" if write else None
    cross_db_out = TMP / "go-cross-db-referential-integrity-probe.json" if write else None
    pm_queue_out = TMP / "go-pm-queue-authority-lint.json" if write else None
    timing_benchmark_out = TMP / "go-validator-timing-benchmark.json" if write else None
    execution_board_out = TMP / "go-execution-board-structural-lint.json" if write else None
    paper_guard_out = TMP / "go-paper-trading-guard-preflight.json" if write else None
    json_argv = [
        str(binary_path("go-json-proof-contract-lint")),
        "--root",
        str(root),
        "--max-age-hours",
        str(max_age_hours),
    ]
    canon_argv = [
        str(binary_path("go-sql-canon-proof-bundle-lint")),
        "--root",
        str(root),
        "--driver",
        driver,
        "--max-age-hours",
        str(max_age_hours),
    ]
    registry_argv = [
        str(binary_path("go-sql-consumer-registry-drift-lint")),
        "--root",
        str(root),
        "--driver",
        driver,
    ]
    route_budget_argv = [
        str(binary_path("go-validator-route-budget-lint")),
        "--root",
        str(root),
        "--allow-timing-warnings",
    ]
    field_family_argv = [
        str(binary_path("go-canon-json-field-family-parity")),
        "--root",
        str(root),
        "--driver",
        driver,
    ]
    cron_argv = [
        str(binary_path("go-cron-contract-json-proof-lint")),
        "--root",
        str(root),
        "--max-age-hours",
        str(max_age_hours),
    ]
    authority_event_argv = [
        str(binary_path("go-finance-canon-authority-event-lint")),
        "--root",
        str(root),
        "--driver",
        driver,
    ]
    warning_reports = [
        "tmp/go-json-proof-contract-lint.json",
        "tmp/go-sql-canon-proof-bundle-lint.json",
        "tmp/go-validator-route-budget-lint.json",
        "tmp/go-cron-contract-json-proof-lint.json",
        "tmp/go-finance-canon-authority-event-lint.json",
        "tmp/go-sql-source-artifact-freshness-lint.json",
        "tmp/go-sql-source-lineage-producer-contract-lint.json",
    ]
    if profile == "full":
        warning_reports.extend(
            [
                "tmp/go-json-proof-structural-validator.json",
                "tmp/go-entry-stop-band-freshness-validator.json",
                "tmp/go-pm-queue-authority-lint.json",
                "tmp/go-finance-answer-completeness-validator.json",
                "tmp/go-cross-db-referential-integrity-probe.json",
                "tmp/go-workflow-artifact-freshness-gate.json",
                "tmp/go-validator-timing-benchmark.json",
                "tmp/go-execution-board-structural-lint.json",
                "tmp/go-paper-trading-guard-preflight.json",
            ]
        )
    warning_residue_argv = [
        str(binary_path("go-json-proof-warning-residue-lint")),
        "--root",
        str(root),
    ]
    for report_path in warning_reports:
        warning_residue_argv.extend(["--report", report_path])
    source_freshness_argv = [
        str(binary_path("go-sql-source-artifact-freshness-lint")),
        "--root",
        str(root),
        "--driver",
        driver,
        "--max-age-hours",
        "240",
    ]
    source_producer_argv = [
        str(binary_path("go-sql-source-lineage-producer-contract-lint")),
        "--root",
        str(root),
        "--freshness-report",
        "tmp/go-sql-source-artifact-freshness-lint.json",
    ]
    closeout_ledger_argv = [
        str(binary_path("go-implementation-closeout-ledger-lint")),
        "--root",
        str(root),
        "--warning-residue",
        "tmp/go-json-proof-warning-residue-lint.json",
        "--release-contract",
        "tmp/implementation-release-contract.json",
        "--allow-single-active-lane",
        "--skip-wrapper-proof",
    ]
    json_structural_argv = [
        str(binary_path("go-json-proof-structural-validator")),
        "--root",
        str(root),
        "--driver",
        driver,
        "--max-age-hours",
        str(max_age_hours),
    ]
    workflow_freshness_argv = [
        str(binary_path("go-workflow-artifact-freshness-gate")),
        "--root",
        str(root),
        "--driver",
        driver,
        "--max-age-hours",
        str(max_age_hours),
    ]
    band_freshness_argv = [
        str(binary_path("go-entry-stop-band-freshness-validator")),
        "--root",
        str(root),
        "--driver",
        driver,
        "--max-age-hours",
        str(max_age_hours),
    ]
    answer_completeness_argv = [
        str(binary_path("go-finance-answer-completeness-validator")),
        "--root",
        str(root),
        "--max-age-hours",
        str(max_age_hours),
    ]
    cross_db_argv = [
        str(binary_path("go-cross-db-referential-integrity-probe")),
        "--root",
        str(root),
        "--driver",
        driver,
    ]
    pm_queue_argv = [
        str(binary_path("go-pm-queue-authority-lint")),
        "--root",
        str(root),
    ]
    timing_benchmark_argv = [
        str(binary_path("go-validator-timing-benchmark")),
        "--root",
        str(root),
        "--timeout-ms",
        str(args_timeout_ms(max_age_hours)),
    ]
    execution_board_argv = [
        str(binary_path("go-execution-board-structural-lint")),
        "--root",
        str(root),
    ]
    paper_guard_argv = [
        str(binary_path("go-paper-trading-guard-preflight")),
        "--root",
        str(root),
    ]
    add_packet_args(json_argv, proof_packets)
    add_packet_args(canon_argv, proof_packets)
    if json_out:
        json_argv.extend(["--out", str(json_out)])
    if canon_out:
        canon_argv.extend(["--out", str(canon_out)])
    if registry_out:
        registry_argv.extend(["--out", str(registry_out)])
    if route_budget_out:
        route_budget_argv.extend(["--out", str(route_budget_out)])
    if field_family_out:
        field_family_argv.extend(["--out", str(field_family_out)])
    if cron_out:
        cron_argv.extend(["--out", str(cron_out)])
    if authority_event_out:
        authority_event_argv.extend(["--out", str(authority_event_out)])
    if warning_residue_out:
        warning_residue_argv.extend(["--out", str(warning_residue_out)])
    if source_freshness_out:
        source_freshness_argv.extend(["--out", str(source_freshness_out)])
    if source_producer_out:
        source_producer_argv.extend(["--out", str(source_producer_out)])
    if closeout_ledger_out:
        closeout_ledger_argv.extend(["--out", str(closeout_ledger_out)])
    if json_structural_out:
        json_structural_argv.extend(["--out", str(json_structural_out)])
    if workflow_freshness_out:
        workflow_freshness_argv.extend(["--out", str(workflow_freshness_out)])
    if band_freshness_out:
        band_freshness_argv.extend(["--out", str(band_freshness_out)])
    if answer_completeness_out:
        answer_completeness_argv.extend(["--out", str(answer_completeness_out)])
    if cross_db_out:
        cross_db_argv.extend(["--out", str(cross_db_out)])
    if pm_queue_out:
        pm_queue_argv.extend(["--out", str(pm_queue_out)])
    if timing_benchmark_out:
        timing_benchmark_argv.extend(["--out", str(timing_benchmark_out)])
    if execution_board_out:
        execution_board_argv.extend(["--out", str(execution_board_out)])
    if paper_guard_out:
        paper_guard_argv.extend(["--out", str(paper_guard_out)])
    commands = [
        ValidatorCommand("go-json-proof-contract-lint", json_argv, json_out),
        ValidatorCommand("go-sql-canon-proof-bundle-lint", canon_argv, canon_out),
        ValidatorCommand("go-sql-consumer-registry-drift-lint", registry_argv, registry_out),
    ]
    if profile != "bundle":
        commands.append(ValidatorCommand("go-validator-route-budget-lint", route_budget_argv, route_budget_out))
    commands.extend(
        [
            ValidatorCommand("go-canon-json-field-family-parity", field_family_argv, field_family_out),
            ValidatorCommand("go-cron-contract-json-proof-lint", cron_argv, cron_out),
            ValidatorCommand("go-finance-canon-authority-event-lint", authority_event_argv, authority_event_out),
            ValidatorCommand("go-sql-source-artifact-freshness-lint", source_freshness_argv, source_freshness_out),
            ValidatorCommand("go-sql-source-lineage-producer-contract-lint", source_producer_argv, source_producer_out),
        ]
    )
    if profile == "full":
        commands.extend(
            [
                ValidatorCommand("go-json-proof-structural-validator", json_structural_argv, json_structural_out),
                ValidatorCommand("go-entry-stop-band-freshness-validator", band_freshness_argv, band_freshness_out),
                ValidatorCommand("go-pm-queue-authority-lint", pm_queue_argv, pm_queue_out),
                ValidatorCommand("go-finance-answer-completeness-validator", answer_completeness_argv, answer_completeness_out),
                ValidatorCommand("go-cross-db-referential-integrity-probe", cross_db_argv, cross_db_out),
                ValidatorCommand("go-workflow-artifact-freshness-gate", workflow_freshness_argv, workflow_freshness_out),
                ValidatorCommand("go-validator-timing-benchmark", timing_benchmark_argv, timing_benchmark_out),
                ValidatorCommand("go-execution-board-structural-lint", execution_board_argv, execution_board_out),
                ValidatorCommand("go-paper-trading-guard-preflight", paper_guard_argv, paper_guard_out),
            ]
        )
    if profile != "bundle":
        commands.extend(
            [
                ValidatorCommand("go-json-proof-warning-residue-lint", warning_residue_argv, warning_residue_out),
                ValidatorCommand("go-implementation-closeout-ledger-lint", closeout_ledger_argv, closeout_ledger_out),
            ]
        )
    return commands


def args_timeout_ms(max_age_hours: int) -> int:
    _ = max_age_hours
    return 30000


def run_command(command: ValidatorCommand, timeout_seconds: int) -> dict[str, Any]:
    binary = Path(command.argv[0])
    if not binary.exists():
        return {
            "name": command.name,
            "ok": False,
            "returncode": 98,
            "error": f"missing_binary:{rel(binary)}",
            "command": command.argv,
            "out": rel(command.out) if command.out else None,
        }
    completed = subprocess.run(
        command.argv,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "name": command.name,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command.argv,
        "out": rel(command.out) if command.out else None,
        "stdout_tail": (completed.stdout or "")[-1000:],
        "stderr_tail": (completed.stderr or "")[-1000:],
    }


def read_inner_report(result: dict[str, Any]) -> dict[str, Any] | None:
    out = result.get("out")
    if not out:
        return None
    path = ROOT / str(out)
    if not path.exists():
        result["ok"] = False
        result["report_error"] = f"missing_report:{out}"
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive report parsing path
        result["ok"] = False
        result["report_error"] = f"invalid_report:{out}:{exc}"
        return None
    result["inner_status"] = report.get("status")
    summary = report.get("summary")
    if isinstance(summary, dict):
        result["inner_summary"] = {
            "checks": summary.get("checks"),
            "critical": summary.get("critical"),
            "warnings": summary.get("warnings"),
        }
    return report


def non_ok_findings(report: dict[str, Any], severity: str, limit: int = 12) -> list[dict[str, Any]]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        return []
    out: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if bool(finding.get("ok")):
            continue
        if str(finding.get("severity", "")).lower() != severity:
            continue
        out.append(
            {
                "path": finding.get("path"),
                "check": finding.get("check"),
                "detail": finding.get("detail"),
            }
        )
        if len(out) >= limit:
            break
    return out


def aggregate_payload(profile: str, proof_packets: list[str], results: list[dict[str, Any]]) -> dict[str, Any]:
    inner_reports: dict[str, dict[str, Any]] = {}
    for result in results:
        report = read_inner_report(result)
        if report is not None:
            inner_reports[str(result.get("name"))] = report

    failed = [result for result in results if not result.get("ok")]
    inner_status_counts: dict[str, int] = {}
    warning_details: list[dict[str, Any]] = []
    critical_details: list[dict[str, Any]] = []
    warning_count = 0
    residue_classifiable_warning_count = 0
    post_residue_warning_count = 0
    critical_count = 0

    for name, report in inner_reports.items():
        status = str(report.get("status") or "unknown")
        inner_status_counts[status] = inner_status_counts.get(status, 0) + 1
        summary = report.get("summary")
        if isinstance(summary, dict):
            warnings = int(summary.get("warnings") or 0)
            critical = int(summary.get("critical") or 0)
        else:
            warnings = 1 if status == "warning" else 0
            critical = 1 if status == "blocked" else 0
        warning_count += warnings
        if name in POST_RESIDUE_VALIDATORS:
            post_residue_warning_count += warnings
        else:
            residue_classifiable_warning_count += warnings
        critical_count += critical
        if warnings:
            warning_details.append(
                {
                    "validator": name,
                    "status": status,
                    "warning_count": warnings,
                    "examples": non_ok_findings(report, "warning"),
                }
            )
        if critical:
            critical_details.append(
                {
                    "validator": name,
                    "status": status,
                    "critical_count": critical,
                    "examples": non_ok_findings(report, "critical"),
                }
            )

    if failed:
        status = "error"
    elif critical_count:
        status = "blocked"
    elif warning_count or inner_status_counts.get("warning", 0):
        status = "warning"
    else:
        status = "ok"

    summary = {
        "validator_count": len(results),
        "failed_count": len(failed),
        "warning_count": warning_count,
        "residue_classifiable_warning_count": residue_classifiable_warning_count,
        "post_residue_warning_count": post_residue_warning_count,
        "critical_count": critical_count,
    }
    return {
        "schema_version": "go_fast_proof_validators_wrapper.v2",
        "generated_at_utc": utc_now(),
        "status": status,
        "profile": profile,
        "proof_packets": proof_packets if proof_packets else "go_default_full_packet_bundle",
        "summary": summary,
        "validator_count": len(results),
        "failed_count": len(failed),
        "warning_count": warning_count,
        "residue_classifiable_warning_count": residue_classifiable_warning_count,
        "post_residue_warning_count": post_residue_warning_count,
        "critical_count": critical_count,
        "inner_status_counts": dict(sorted(inner_status_counts.items())),
        "warning_details": warning_details,
        "critical_details": critical_details,
        "results": results,
        "authority_boundary": {
            "review_only": True,
            "compiled_go_validator_wrapper": True,
            "sql_write_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "cron_schedule_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "next_safe_action": "Use as advisory implementation-job proof until repeated clean runs justify stronger routing.",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--driver", choices=["cli", "inprocess"], default="inprocess")
    parser.add_argument("--max-age-hours", type=int, default=96)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--profile",
        choices=["bundle", "implementation", "full"],
        default="implementation",
        help=(
            "bundle excludes validators that consume the validator bundle or its closeout residue, avoiding a "
            "circular self-proof during bundle execution; implementation adds those post-bundle closeout checks; "
            "full runs the complete Go default packet bundle."
        ),
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Aggregate wrapper JSON report path used with --write.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    root = args.root if args.root.is_absolute() else ROOT / args.root
    proof_packets = proof_packets_for_profile(args.profile)
    commands = build_commands(root.resolve(), args.write, args.driver, args.max_age_hours, args.profile)
    if args.plan_only:
        print(json.dumps({"profile": args.profile, "proof_packets": proof_packets, "commands": [command.argv for command in commands]}, indent=2))
        return 0

    results = [run_command(command, args.timeout_seconds) for command in commands]
    payload = aggregate_payload(args.profile, proof_packets, results)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        write_json(out, payload)
    print(json.dumps(payload, indent=2))
    if args.validate and payload["status"] in {"error", "blocked"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
