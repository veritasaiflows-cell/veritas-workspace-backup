#!/usr/bin/env python3
"""QA the intended fast path for startup/status/continue work.

Lane B proof for WF72/WF73. It checks route SQLite parity, PM control SQLite,
artifact index health, cron freshness, fallback artifacts, and closeout ordering
discipline. It is report-only and grants no SQL-first/canon/approval authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "fast-path-qa.json"

SCHEMA = "veritas.fast_path_qa.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "qa_only": True,
    "sql_read_only": True,
    "sql_canon_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

ORDERED_CLOSEOUT_CHAIN = [
    "python scripts\\workflow_routing_index.py --write --write-db --validate",
    "python scripts\\artifact_intelligence_action_scorer.py --write --validate",
    "python scripts\\wf78_event_triggered_rerouting.py --write --write-db --validate",
    "python scripts\\truth_surface_inventory.py --write --validate",
    "python scripts\\pm_sidecar_retirement_guard.py --write --validate",
    "python scripts\\cron_control_packet.py --write --validate",
    "python scripts\\changed_file_validator_router.py --write --validate",
    "python scripts\\fast_path_qa.py --write --validate",
    "python scripts\\artifact_index.py incremental",
    "python scripts\\artifact_index.py validate",
    "python scripts\\pm_control_packet.py --write --write-db --validate",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "status": "ok" if ok else "fail",
        "severity": severity,
        "detail": detail,
    }


def sqlite_count(path: Path, table: str) -> tuple[bool, int | None, str | None]:
    if not path.exists():
        return False, None, "missing"
    try:
        with sqlite3.connect(path) as con:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if integrity != "ok":
            return False, count, f"integrity={integrity}"
        return True, int(count), None
    except sqlite3.Error as exc:
        return False, None, str(exc)


def command_probe(name: str, args: list[str], target_seconds: float) -> dict[str, Any]:
    start = time.perf_counter()
    completed = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
    elapsed = round(time.perf_counter() - start, 3)
    return {
        "name": name,
        "command": " ".join(args),
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "target_seconds": target_seconds,
        "status": "ok" if completed.returncode == 0 and elapsed <= target_seconds else "slow" if completed.returncode == 0 else "failed",
        "stderr_preview": completed.stderr.strip()[:500],
    }


def build_report(run_probes: bool = True) -> dict[str, Any]:
    workflow_index = as_dict(load_json_artifact(TMP / "workflow-routing-index.json"))
    workflow_validation = as_dict(load_json_artifact(TMP / "workflow-routing-index-validation.json"))
    pm_control = as_dict(load_json_artifact(TMP / "pm-control-packet.json"))
    cron = as_dict(load_json_artifact(TMP / "cron-freshness-spine.json"))
    cron_control = as_dict(load_json_artifact(TMP / "cron-control-packet.json"))
    otel_ops = as_dict(load_json_artifact(TMP / "otel-ops-control.json"))
    scorer = as_dict(load_json_artifact(TMP / "artifact-intelligence-action-scorer.json"))
    rerouting = as_dict(load_json_artifact(TMP / "wf78-event-triggered-rerouting.json"))
    sidecar_guard = as_dict(load_json_artifact(TMP / "pm-sidecar-retirement-guard.json"))
    validator_router = as_dict(load_json_artifact(TMP / "changed-file-validator-router.json"))

    checks: list[dict[str, Any]] = []
    route_ok, route_count, route_err = sqlite_count(TMP / "workflow-routing-index.sqlite", "workflow_routes")
    pm_ok, pm_row_count, pm_err = sqlite_count(TMP / "pm-control-packet.sqlite", "pm_control_summary")
    artifact_ok, artifact_rows, artifact_err = sqlite_count(TMP / "veritas-artifact-index.sqlite", "artifact_file_state")

    route_summary = workflow_index.get("summary", {})
    checks.append(check("workflow_routing_json_ok", route_summary.get("route_count", 0) >= 33, route_summary))
    checks.append(check("workflow_routing_validation_ok", workflow_validation.get("status") == "ok", workflow_validation.get("summary")))
    checks.append(check("workflow_routing_sqlite_ok", route_ok and route_count == workflow_index.get("summary", {}).get("route_count"), {"count": route_count, "error": route_err}))
    checks.append(check("pm_control_packet_ok", pm_control.get("status") == "ok", pm_control.get("summary")))
    checks.append(check("pm_control_sqlite_ok", pm_ok and (pm_row_count or 0) >= 1, {"count": pm_row_count, "error": pm_err}))
    checks.append(check("artifact_index_sqlite_ok", artifact_ok and (artifact_rows or 0) >= 1, {"count": artifact_rows, "error": artifact_err}))
    checks.append(check("cron_freshness_validation_ok", as_dict(cron.get("validation")).get("status") == "ok", cron.get("validation")))
    checks.append(check("cron_freshness_no_blocked_jobs", cron.get("summary", {}).get("blocked_count") == 0, cron.get("summary"), severity="warning"))
    checks.append(check("cron_control_packet_ok", cron_control.get("status") == "ok", cron_control.get("summary")))
    checks.append(check("otel_ops_control_ok", otel_ops.get("status") == "ok", otel_ops.get("summary"), severity="warning"))
    checks.append(check("artifact_scorer_ok", scorer.get("status") == "ok", scorer.get("summary")))
    checks.append(check("wf78_rerouting_ok", rerouting.get("status") == "ok", rerouting.get("summary")))
    checks.append(check("pm_sidecar_retirement_guard_ok", sidecar_guard.get("status") == "ok", sidecar_guard.get("summary")))
    checks.append(check("changed_file_validator_router_ok", validator_router.get("status") == "ok", validator_router.get("summary"), severity="warning"))
    checks.append(check(
        "validation_order_encoded",
        ORDERED_CLOSEOUT_CHAIN.index("python scripts\\artifact_intelligence_action_scorer.py --write --validate")
        < ORDERED_CLOSEOUT_CHAIN.index("python scripts\\artifact_index.py incremental")
        < ORDERED_CLOSEOUT_CHAIN.index("python scripts\\artifact_index.py validate"),
        ORDERED_CLOSEOUT_CHAIN,
    ))

    probes: list[dict[str, Any]] = []
    if run_probes:
        probes.extend([
            command_probe("sql_route_wf73", ["python", "scripts\\workflow_routing_index.py", "--sql-route", "WF73"], 2.0),
            command_probe("sql_next_actions", ["python", "scripts\\workflow_routing_index.py", "--sql-next-actions"], 5.0),
        ])
    slow_or_failed = [row for row in probes if row["status"] != "ok"]
    criticals = [row for row in checks if not row["ok"] and row["severity"] == "critical"]
    warnings = [row for row in checks if not row["ok"] and row["severity"] != "critical"]

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not criticals else "blocked",
        "purpose": "Verify the default fast path before broad scans or source-open drilldown.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "checks": len(checks),
            "critical_failures": len(criticals),
            "warnings": len(warnings),
            "probe_count": len(probes),
            "slow_or_failed_probe_count": len(slow_or_failed),
            "next_safe_action": "Use route SQL/PM/artifact/cron fast path first; source-open exact owners only for material claims.",
        },
        "ordered_closeout_chain": ORDERED_CLOSEOUT_CHAIN,
        "checks": checks,
        "probes": probes,
        "validation": {
            "status": "ok" if not criticals else "blocked",
            "errors": [row["name"] for row in criticals],
            "warnings": [row["name"] for row in warnings] + [f"slow_or_failed_probe:{row['name']}:{row['status']}" for row in slow_or_failed],
        },
        "stop_lines": [
            "Fast-path QA is read-only/report-only; no SQL promotion, canon/portfolio mutation, customer output, config/runtime mutation, paper/live/account action, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="QA the WF72/WF73 fast path.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on critical validation errors.")
    parser.add_argument("--no-probes", action="store_true", help="Skip timing probes.")
    args = parser.parse_args()

    report = build_report(run_probes=not args.no_probes)
    if args.write:
        atomic_write_json(OUT, report)
        print(f"wrote {rel(OUT)} status={report['status']} checks={report['summary']['checks']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
