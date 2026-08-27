#!/usr/bin/env python3
"""Ordered WF73 control-plane audit runner.

WF73's job is to keep startup, routing, queue lookup, helper-lane coordination,
and validator budgeting fast and honest. This runner removes remembered command
order from that audit path: it refreshes producer surfaces first, then consumers,
then the artifact index.

Report-only: no archive/delete, config/auth/runtime mutation, canon/portfolio
mutation, customer/external delivery, paper/live/account action, capital action,
or owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import access as finance_sql_canon_access
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf73-control-plane-audit.json"
SCHEMA = "veritas.wf73_control_plane_audit.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "audit_and_routing_validation_only": True,
    "executes_workflows": False,
    "spawns_helpers": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "sql_canon_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def openclaw_cmd() -> str:
    cmd = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(cmd) if cmd.exists() else "openclaw.cmd"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def run_step(name: str, command: list[str], timeout: int, severity: str = "critical") -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "severity": severity,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_head_preview": proc.stdout.strip()[:8000] if name == "memory_index_status" else "",
            "stdout_preview": proc.stdout.strip()[-3500:],
            "stderr_preview": proc.stderr.strip()[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "severity": severity,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-3500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }
    except OSError as exc:
        return {
            "name": name,
            "severity": severity,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "stdout_head_preview": "",
            "stdout_preview": "",
            "stderr_preview": "",
        }


def first_json(text: str) -> Any | None:
    stripped = text.strip()
    for opener in ("[", "{"):
        start = stripped.find(opener)
        if start < 0:
            continue
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(stripped[start:])
            return obj
        except json.JSONDecodeError:
            continue
    return None


def artifact(path: str) -> dict[str, Any]:
    payload = load_json_artifact(ROOT / path)
    return payload if isinstance(payload, dict) else {}


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive audit surface
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def summarize_memory_status(step: dict[str, Any]) -> dict[str, Any]:
    parsed = first_json(f"{step.get('stdout_head_preview') or ''}\n{step.get('stdout_preview') or ''}")
    rows = parsed if isinstance(parsed, list) else []
    row = as_dict(rows[0] if rows else {})
    status = as_dict(row.get("status"))
    custom = as_dict(status.get("custom"))
    index_identity = as_dict(custom.get("indexIdentity"))
    probe = as_dict(row.get("embeddingProbe"))
    return {
        "checked": True,
        "command_returncode": step.get("returncode"),
        "healthy": bool(probe.get("ok")) and index_identity.get("status") not in {"missing", "error"},
        "provider": status.get("provider"),
        "model": status.get("model"),
        "dirty": status.get("dirty"),
        "indexed_files": status.get("files"),
        "total_files": as_dict(row.get("scan")).get("totalFiles"),
        "vector_available": as_dict(status.get("vector")).get("storeAvailable"),
        "fts_available": as_dict(status.get("fts")).get("available"),
        "index_identity_status": index_identity.get("status"),
        "embedding_probe_ok": probe.get("ok"),
        "error_class": "embedding_provider_403_or_unavailable" if "403" in str(row.get("indexError") or probe.get("error") or "") else None,
        "next_safe_action": (
            "Repair provider/auth or switch approved memory provider, then run openclaw memory index --force. "
            "Do not edit index DB files by hand."
            if not bool(probe.get("ok"))
            else "Run openclaw memory index --force if dirty remains true."
        ),
    }


def cron_attention_summary() -> dict[str, Any]:
    cron = artifact("tmp/cron-freshness-spine.json")
    jobs = [as_dict(job) for job in as_list(cron.get("jobs")) if as_dict(job).get("enabled")]
    buckets = {
        "urgent_blocked_or_owner_decision": [],
        "main_review_queue": [],
        "monitor_only_or_stale": [],
        "quiet_success": [],
    }
    for job in jobs:
        cls = job.get("signal_class")
        item = {
            "name": job.get("name"),
            "status": job.get("status"),
            "signal_class": cls,
            "reason": job.get("reason"),
        }
        if cls in {"BLOCKED", "OWNER_DECISION"}:
            buckets["urgent_blocked_or_owner_decision"].append(item)
        elif cls == "MAIN_SESSION_REQUIRED":
            buckets["main_review_queue"].append(item)
        elif cls == "STALE_OR_NOISE":
            buckets["monitor_only_or_stale"].append(item)
        else:
            buckets["quiet_success"].append(item)
    return {
        "status": cron.get("status"),
        "summary": cron.get("summary"),
        "bucket_counts": {key: len(value) for key, value in buckets.items()},
        "buckets": buckets,
    }


def pm_stale_lane_digest() -> dict[str, Any]:
    pm = artifact("tmp/pm-control-packet.json")
    digest = as_dict(as_dict(pm.get("summary")).get("stale_lane_digest"))
    if digest:
        return digest
    lanes = as_list(as_dict(as_dict(pm.get("sections")).get("pm_program_state")).get("lanes"))
    stale = []
    for lane in lanes:
        lane = as_dict(lane)
        if lane.get("status") != "stale":
            continue
        action = as_dict(lane.get("next_action"))
        stale.append({
            "lane_id": lane.get("lane_id"),
            "title": lane.get("title"),
            "readiness_score": lane.get("readiness_score"),
            "next_action": action.get("description"),
            "action_id": action.get("action_id"),
            "helper_lane_allowed_from_main_session": action.get("helper_lane_allowed_from_main_session"),
        })
    return {"stale_lane_count": len(stale), "lanes": stale}


def artifact_summaries(memory_step: dict[str, Any]) -> dict[str, Any]:
    route_index = artifact("tmp/workflow-routing-index.json")
    fast_path = artifact("tmp/fast-path-qa.json")
    boot = artifact("tmp/boot-surface-size-guard.json")
    hygiene = artifact("tmp/workflow-hygiene-check.json")
    timing = artifact("tmp/validator-timing-ledger.json")
    closeout = artifact("tmp/control-closeout-bundle.json")
    return {
        "workflow_routing": {
            "route_count": as_dict(route_index.get("summary")).get("route_count"),
            "tier_counts": as_dict(route_index.get("summary")).get("tier_counts"),
            "freshness_counts": as_dict(route_index.get("summary")).get("freshness_counts"),
        },
        "fast_path": {
            "status": fast_path.get("status"),
            "summary": fast_path.get("summary"),
            "validation": fast_path.get("validation"),
        },
        "cron_attention": cron_attention_summary(),
        "pm_stale_lane_digest": pm_stale_lane_digest(),
        "boot_size": {
            "status": boot.get("status"),
            "counts": boot.get("counts"),
            "warnings": boot.get("warnings"),
        },
        "workflow_hygiene": {
            "status": hygiene.get("status"),
            "counts": hygiene.get("counts"),
            "findings": hygiene.get("findings"),
        },
        "validator_timing": {
            "status": timing.get("status"),
            "summary": timing.get("summary"),
            "validation": timing.get("validation"),
        },
        "control_closeout": {
            "status": closeout.get("status"),
            "summary": closeout.get("summary"),
            "validation": closeout.get("validation"),
        },
        "memory_index_health": summarize_memory_status(memory_step),
    }


def ordered_steps(include_memory: bool) -> list[tuple[str, list[str], int, str]]:
    steps: list[tuple[str, list[str], int, str]] = [
        ("workflow_router_wf73_summary", py_cmd("scripts\\workflow_router.py", "WF73", "--answer", "summary"), 120, "critical"),
        ("workflow_routing_index", py_cmd("scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"), 180, "critical"),
        ("concurrent_lane_manager", py_cmd("scripts\\concurrent_lane_manager.py", "--status", "--write", "--validate"), 120, "critical"),
        ("truth_surface_inventory", py_cmd("scripts\\truth_surface_inventory.py", "--write", "--validate"), 180, "critical"),
        ("cron_freshness_spine", py_cmd("scripts\\cron_freshness_spine.py", "--write", "--validate"), 180, "warning"),
        ("pm_control_packet", py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 240, "critical"),
        ("boot_surface_size_guard", py_cmd("scripts\\boot_surface_size_guard.py", "--write", "--validate"), 120, "warning"),
        ("workflow_hygiene_check", py_cmd("scripts\\workflow_hygiene_check.py", "--write", "--validate"), 120, "warning"),
        ("fast_path_qa", py_cmd("scripts\\fast_path_qa.py", "--write", "--validate"), 180, "critical"),
        ("validator_timing_ledger", py_cmd("scripts\\validator_timing_ledger.py", "--profile", "normal", "--write", "--validate"), 180, "critical"),
        ("control_closeout_bundle", py_cmd("scripts\\control_closeout_bundle.py", "--validation-budget", "shared", "--write", "--validate"), 900, "critical"),
        ("artifact_index_incremental", py_cmd("scripts\\artifact_index.py", "incremental"), 240, "critical"),
        ("artifact_index_validate", py_cmd("scripts\\artifact_index.py", "validate"), 240, "critical"),
    ]
    if include_memory:
        steps.append(("memory_index_status", [openclaw_cmd(), "memory", "status", "--index", "--agent", "main", "--json"], 90, "warning"))
    return steps


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for name, command, timeout, severity in ordered_steps(include_memory=not args.skip_memory_status):
        step = run_step(name, command, timeout, severity)
        if severity == "warning" and not step["ok"]:
            step["warning_class_failure"] = True
        steps.append(step)
        if severity == "critical" and not step["ok"] and not args.continue_on_failure:
            break
    memory_step = next((step for step in steps if step["name"] == "memory_index_status"), {"returncode": None, "stdout_preview": ""})
    critical_failed = [step["name"] for step in steps if step.get("severity") == "critical" and not step.get("ok")]
    warning_failed = [step["name"] for step in steps if step.get("severity") == "warning" and not step.get("ok")]
    summaries = artifact_summaries(memory_step)
    sql_health = sql_canon_health()
    if sql_health.get("status") != "ok":
        critical_failed.append("sql_canon_guard_blocked")
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            critical_failed.append(f"sql_canon_authority_{key}_not_false")
    warning_surfaces = []
    if as_dict(summaries["boot_size"].get("counts")).get("warnings", 0):
        warning_surfaces.append("boot_surface_size_guard")
    if as_dict(summaries["cron_attention"].get("bucket_counts")).get("main_review_queue", 0):
        warning_surfaces.append("cron_main_review_queue")
    if not as_dict(summaries["memory_index_health"]).get("healthy"):
        warning_surfaces.append("memory_index_health")
    if warning_failed:
        warning_surfaces.extend(warning_failed)
    status = "blocked" if critical_failed else "warning" if warning_surfaces else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Ordered WF73 control-plane audit over route/index/boot/cron/PM/QA/artifact/memory health.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "ordered_policy": {
            "producer_before_consumer": True,
            "parallel_writer_reader_validation_allowed": False,
            "why": "Route/index writers must finish before fast-path QA and artifact-index consumers read their outputs.",
            "critical_sequence": [
                "workflow_routing_index",
                "truth_surface_inventory",
                "cron_freshness_spine",
                "pm_control_packet",
                "fast_path_qa",
                "control_closeout_bundle",
                "artifact_index_incremental",
                "artifact_index_validate",
            ],
        },
        "summary": {
            "steps_run": len(steps),
            "critical_failed_steps": critical_failed,
            "warning_failed_steps": warning_failed,
            "warning_surfaces": sorted(set(warning_surfaces)),
            "route_count": summaries["workflow_routing"].get("route_count"),
            "fast_path_status": summaries["fast_path"].get("status"),
            "boot_status": summaries["boot_size"].get("status"),
            "cron_status": summaries["cron_attention"].get("status"),
            "pm_stale_lane_count": summaries["pm_stale_lane_digest"].get("stale_lane_count"),
            "memory_index_healthy": summaries["memory_index_health"].get("healthy"),
            "sql_canon_status": sql_health.get("status"),
            "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
            "next_safe_action": (
                "Repair the first critical failed step before using WF73 closeout."
                if critical_failed
                else "Use this runner for future WF73 audits; treat warning surfaces as routing work, not hidden blockers."
            ),
        },
        "artifact_summaries": summaries,
        "sql_canon_health": sql_health,
        "steps": steps,
        "validation": {
            "status": "ok" if not critical_failed else "blocked",
            "errors": critical_failed,
            "warnings": sorted(set(warning_surfaces)),
        },
        "stop_lines": [
            "This runner audits and refreshes control-plane proof only.",
            "No archive/delete, config/auth/runtime mutation, canon/portfolio mutation, customer delivery, paper/live/account action, capital deployment, money movement, or owner approval inference.",
            "Warning surfaces must be classified honestly; they do not become approval or execution authority.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ordered WF73 control-plane audit.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(OUT)}")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on critical audit failure.")
    parser.add_argument("--strict-warnings", action="store_true", help="With --validate, return non-zero for warning status too.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Run all steps even if a critical step fails.")
    parser.add_argument("--skip-memory-status", action="store_true", help="Skip OpenClaw memory index status probe.")
    parser.add_argument("--skip-post-write-index-refresh", action="store_true", help="Do not refresh artifact index after writing this audit artifact.")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
        print(f"wrote {rel(out)} status={report['status']} steps={report['summary']['steps_run']}")
        if not args.skip_post_write_index_refresh:
            inc = run_step(
                "post_write_artifact_index_incremental",
                py_cmd("scripts\\artifact_index.py", "incremental"),
                240,
                "critical",
            )
            val = run_step(
                "post_write_artifact_index_validate",
                py_cmd("scripts\\artifact_index.py", "validate"),
                240,
                "critical",
            )
            print(
                "post_write_index_refresh incremental={inc} validate={val}".format(
                    inc="ok" if inc.get("ok") else "failed",
                    val="ok" if val.get("ok") else "failed",
                )
            )
            if args.validate and (not inc.get("ok") or not val.get("ok")):
                return 1
    else:
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    if args.validate and args.strict_warnings and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
