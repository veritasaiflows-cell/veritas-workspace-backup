#!/usr/bin/env python3
"""Inventory cron reduction contracts and phase status.

This is a planning/proof surface. It reads live cron state and writes the
replacement map used by the cron reduction migration. It does not mutate cron.
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

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "cron-reduction-inventory.json"
CONTRACTS_OUT = TMP / "cron-runner-contracts.json"
PHASE1_OUT = TMP / "cron-phase1-shadow-parity.json"
PHASE2_OUT = TMP / "cron-phase2-shadow-parity.json"
PHASE3_OUT = TMP / "cron-phase3-cadence-plan.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "job_add_disable_delete_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def openclaw_cmd() -> str:
    found = shutil.which("openclaw.cmd") or shutil.which("openclaw") or shutil.which("openclaw.ps1")
    if found:
        return found
    known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(known) if known.exists() else "openclaw.cmd"


def cron_list() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    command = [openclaw_cmd(), "cron", "list", "--all", "--json", "--timeout", "30000"]
    proc = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=45,
    )
    result = {
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }
    if proc.returncode != 0:
        return [], result
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result["ok"] = False
        result["stderr_tail"] = "cron_json_parse_failed"
        return [], result
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    return [job for job in jobs if isinstance(job, dict)], result if isinstance(jobs, list) else {**result, "ok": False}


def payload(job: dict[str, Any]) -> dict[str, Any]:
    value = job.get("payload")
    return value if isinstance(value, dict) else {}


def job_summary(job: dict[str, Any]) -> dict[str, Any]:
    p = payload(job)
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "enabled": bool(job.get("enabled")),
        "schedule": job.get("cron") or job.get("schedule") or job.get("cadence"),
        "model": p.get("model"),
        "thinking": p.get("thinking"),
        "timeout_seconds": p.get("timeoutSeconds"),
        "payload_kind": p.get("type") or job.get("type") or ("agentTurn" if p.get("message") else "unknown"),
    }


def find_jobs(jobs: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    by_name = {str(job.get("name") or ""): job for job in jobs}
    return [by_name[name] for name in names if name in by_name]


CONTRACTS: list[dict[str, Any]] = [
    {
        "id": "phase1_control_fail_closed_dispatcher",
        "phase": 1,
        "runner": "scripts/cron_control_digest_runner.py",
        "runner_command": "python scripts\\cron_control_digest_runner.py --window control --out tmp\\cron-control-digest-runner-control.json --write --write-md --validate",
        "replacement_job_name": "Cron Reduction - Control Fail-Closed Dispatcher",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 120,
        "hard_timeout_seconds": 300,
        "source_jobs": [
            "Cron - Main Session Auto-Green Watchdog",
            "Operating Leverage - Escalation Trigger Check",
        ],
        "required_outputs": [
            "tmp/cron-control-packet.json",
            "tmp/pm-control-packet.json",
            "tmp/cron-control-digest-runner-control.json",
        ],
        "disable_gate": "Control runner either passes cleanly or fails closed with a main-session blocker packet.",
    },
    {
        "id": "phase1_morning_control_digest",
        "phase": 1,
        "runner": "scripts/cron_control_digest_runner.py",
        "runner_command": "python scripts\\cron_control_digest_runner.py --window morning --out tmp\\cron-control-digest-runner-morning.json --write --write-md --validate",
        "replacement_job_name": "Cron Reduction - Morning Control Digest",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 240,
        "hard_timeout_seconds": 600,
        "source_jobs": [
            "Finance - Morning Control Digest Proof Refresh",
            "Finance - Layered Morning Advancement Audit",
        ],
        "required_outputs": [
            "tmp/morning-control-digest.json",
            "tmp/cron-control-digest-runner-morning.json",
        ],
        "disable_gate": "Morning digest proof must exist, preserve blocker routing, and avoid duplicate delivery before source jobs are disabled.",
    },
    {
        "id": "phase1_postclose_control_digest",
        "phase": 1,
        "runner": "scripts/cron_control_digest_runner.py",
        "runner_command": "python scripts\\cron_control_digest_runner.py --window post-close --out tmp\\cron-control-digest-runner-post-close.json --write --write-md --validate",
        "replacement_job_name": "Cron Reduction - Post-Close Control Digest",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 240,
        "hard_timeout_seconds": 600,
        "source_jobs": [
            "Finance - Post-Close Control Digest Consolidated Handoff",
            "Finance - Layered Post-Close Advancement Audit",
        ],
        "required_outputs": [
            "tmp/post-close-control-digest.json",
            "tmp/cron-control-digest-runner-post-close.json",
        ],
        "disable_gate": "Post-close digest proof must exist, preserve blocker routing, and avoid duplicate delivery before source jobs are disabled.",
    },
    {
        "id": "phase1_delivery_daily",
        "phase": 1,
        "runner": "scripts/finance_delivery_series_consolidated_runner.py",
        "runner_command": "python scripts\\finance_delivery_series_consolidated_runner.py --mode daily --out tmp\\finance-delivery-series-consolidated-runner-daily.json --write --write-md --validate",
        "replacement_job_name": "Finance Delivery Series - Daily Builder and Handoff",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 300,
        "hard_timeout_seconds": 900,
        "source_jobs": [
            "Finance Delivery Series - Daily Market Read Builder",
            "Finance Delivery Series - Daily Market Read Handoff",
        ],
        "required_outputs": [
            "tmp/finance-delivery-series.json",
            "tmp/finance-delivery-series/daily-market-read.html",
            "tmp/finance-delivery-series-consolidated-runner-daily.json",
        ],
        "disable_gate": "Daily builder and handoff parity must be proven by the same replacement cadence.",
    },
    {
        "id": "phase1_delivery_weekly",
        "phase": 1,
        "runner": "scripts/finance_delivery_series_consolidated_runner.py",
        "runner_command": "python scripts\\finance_delivery_series_consolidated_runner.py --mode weekly --out tmp\\finance-delivery-series-consolidated-runner-weekly.json --write --write-md --validate",
        "replacement_job_name": "Finance Delivery Series - Weekly Builder and Handoff",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 300,
        "hard_timeout_seconds": 900,
        "source_jobs": [
            "Finance Delivery Series - Weekly Market Read Builder",
            "Finance Delivery Series - Weekly Performance Builder",
            "Finance Delivery Series - Weekly Handoff",
        ],
        "required_outputs": [
            "tmp/finance-delivery-series.json",
            "tmp/finance-delivery-series/weekly-market-read.html",
            "tmp/finance-delivery-series/weekly-investments-performance.html",
            "tmp/finance-delivery-series-consolidated-runner-weekly.json",
        ],
        "disable_gate": "Weekly builder and main-session handoff parity must be proven by the same replacement cadence.",
    },
    {
        "id": "phase1_delivery_monthly",
        "phase": 1,
        "runner": "scripts/finance_delivery_series_consolidated_runner.py",
        "runner_command": "python scripts\\finance_delivery_series_consolidated_runner.py --mode monthly --out tmp\\finance-delivery-series-consolidated-runner-monthly.json --write --write-md --validate",
        "replacement_job_name": "Finance Delivery Series - Monthly Builder and Handoff",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 600,
        "hard_timeout_seconds": 1500,
        "source_jobs": [
            "Finance Delivery Series - Monthly Direction and Deep Dive Builder",
            "Finance Delivery Series - Monthly Handoff",
        ],
        "required_outputs": [
            "tmp/finance-delivery-series.json",
            "tmp/finance-delivery-series/monthly-investment-direction.html",
            "tmp/finance-delivery-series/monthly-market-deep-dive.html",
            "tmp/finance-delivery-series-consolidated-runner-monthly.json",
        ],
        "disable_gate": "Monthly builder and main-session handoff parity must be proven by the same replacement cadence.",
    },
    {
        "id": "phase1_runtime_future_session",
        "phase": 1,
        "runner": "scripts/runtime_ops_consolidated_digest.py",
        "runner_command": "python scripts\\runtime_ops_consolidated_digest.py --component future-session --profile normal --out tmp\\runtime-ops-consolidated-digest-future-session.json --write --write-md --validate",
        "replacement_job_name": "Runtime - Future Session Packet Refresh",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 120,
        "hard_timeout_seconds": 300,
        "source_jobs": [
            "Runtime - Future Session Packet Refresh",
        ],
        "required_outputs": [
            "tmp/future-session-enhancement-packet.json",
            "tmp/runtime-ops-consolidated-digest-future-session.json",
        ],
        "disable_gate": "Future-session twice-daily cadence must be preserved before disabling the source job.",
    },
    {
        "id": "phase1_runtime_otel",
        "phase": 1,
        "runner": "scripts/runtime_ops_consolidated_digest.py",
        "runner_command": "python scripts\\runtime_ops_consolidated_digest.py --component otel --profile normal --out tmp\\runtime-ops-consolidated-digest-otel.json --write --write-md --validate",
        "replacement_job_name": "Runtime - OTEL Local Digest",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 120,
        "hard_timeout_seconds": 300,
        "source_jobs": [
            "Ops - OTEL Local Digest",
        ],
        "required_outputs": [
            "tmp/otel-ops-control.json",
            "tmp/runtime-ops-consolidated-digest-otel.json",
        ],
        "disable_gate": "OTEL digest cadence must be preserved before disabling the source job.",
    },
    {
        "id": "phase1_runtime_wf74_send",
        "phase": 1,
        "runner": "scripts/runtime_ops_consolidated_digest.py",
        "runner_command": "python scripts\\runtime_ops_consolidated_digest.py --component wf74 --send --profile normal --out tmp\\runtime-ops-consolidated-digest-wf74-send.json --write --write-md --validate",
        "replacement_job_name": "Runtime - WF74 Learning Loop Telegram Digest",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 180,
        "hard_timeout_seconds": 900,
        "source_jobs": [
            "WF74 - Learning Loop Telegram Digest",
        ],
        "required_outputs": [
            "tmp/wf74-learning-loop-telegram-cron-runner.json",
            "tmp/runtime-ops-consolidated-digest-wf74-send.json",
        ],
        "disable_gate": "Telegram send parity must be explicitly proven before disabling the WF74 Telegram digest.",
    },
    {
        "id": "phase3_runtime_weekly_improvement_proof",
        "phase": 3,
        "runner": "scripts/runtime_ops_consolidated_digest.py",
        "runner_command": "python scripts\\runtime_ops_consolidated_digest.py --component weekly-improvement-proof --profile normal --out tmp\\runtime-ops-consolidated-digest-weekly-improvement-proof.json --write --write-md --validate",
        "replacement_job_name": "Runtime - Weekly OS Improvement Proof Refresh",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 180,
        "hard_timeout_seconds": 600,
        "source_jobs": [
            "Runtime - Weekly OS Improvement Radar Proof Refresh",
        ],
        "required_outputs": [
            "tmp/artifact-staleness-explainer.json",
            "tmp/cron-contract-validator.json",
            "tmp/pm-control-packet.json",
            "tmp/cron-control-packet.json",
            "tmp/runtime-ops-consolidated-digest-weekly-improvement-proof.json",
        ],
        "disable_gate": "Weekly proof refresh can be folded only if the main-session review reminder remains separately preserved.",
    },
    {
        "id": "phase2_morning_market_paper",
        "phase": 2,
        "runner": "scripts/morning_market_paper_consolidated_runner.py",
        "runner_command": "python scripts\\morning_market_paper_consolidated_runner.py --send --write --write-md --validate",
        "replacement_job_name": "Finance - Morning Market Paper Consolidator",
        "recommended_model": "ollama-cloud/glm-5.3:cloud for reasoning refresh, GLM 5.3 Flash only for deterministic bounded verification",
        "target_seconds": 120,
        "hard_timeout_seconds": 240,
        "source_jobs": [
            "Finance - Silent Tier A Intraday Market Readiness Probe",
            "Finance - Silent Tier A Confirmation Market Readiness Probe",
            "Finance - WF85 Paper Deployment Telegram Radar",
            "Finance - Morning Paper Deployment Recommendation Cards",
            "Finance - WF87 Market-Hours Fresh Gate Probe",
            "Finance - WF87 Autonomy Command Center Refresh",
        ],
        "required_outputs": [
            "tmp/morning-market-paper-consolidated-runner.json",
            "tmp/wf85-paper-deployment-telegram-cron-runner.json",
            "tmp/wf87-market-hours-gate-probe.json",
            "tmp/wf87-autonomy-command-center.json",
        ],
        "disable_gate": "One clean market-day shadow run with same artifacts and no duplicate Telegram sends.",
    },
    {
        "id": "phase2_midday_market_paper",
        "phase": 2,
        "runner": "scripts/midday_market_paper_consolidated_runner.py",
        "runner_command": "python scripts\\midday_market_paper_consolidated_runner.py --send --write --write-md --validate",
        "replacement_job_name": "Finance - Midday Market Paper Consolidator",
        "recommended_model": "ollama-cloud/glm-5.3:cloud for reasoning refresh, GLM 5.3 Flash only for deterministic bounded verification",
        "target_seconds": 120,
        "hard_timeout_seconds": 240,
        "source_jobs": [
            "Finance - WF85 Post-Refresh Paper Deployment Telegram Radar",
            "Finance - Midday Paper Deployment Recommendation Cards",
            "Finance - Silent Tier A Late-Session Market Readiness Probe",
            "Finance - WF87 Market-Hours Fresh Gate Probe",
            "Finance - WF87 Autonomy Command Center Refresh",
        ],
        "required_outputs": [
            "tmp/midday-market-paper-consolidated-runner.json",
            "tmp/wf85-paper-deployment-telegram-cron-runner.json",
            "tmp/wf87-market-hours-gate-probe.json",
            "tmp/wf87-autonomy-command-center.json",
        ],
        "disable_gate": "One clean market-day shadow run with same artifacts and no duplicate Telegram sends.",
    },
    {
        "id": "phase2_postclose_paper_reconciliation",
        "phase": 2,
        "runner": "scripts/postclose_paper_reconciliation_runner.py",
        "runner_command": "python scripts\\postclose_paper_reconciliation_runner.py --write --write-md --validate",
        "replacement_job_name": "Finance - Post-Close Paper State Reconciliation",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 300,
        "hard_timeout_seconds": 1500,
        "source_jobs": [
            "Finance - WF63/WF67 Paper Position Read-Only Refresh",
            "Finance - WF86 Daily Shadow and Paper Reconciliation",
        ],
        "required_outputs": [
            "tmp/postclose-paper-reconciliation-runner.json",
            "tmp/wf67-paper-position-refresh-cron-runner.json",
            "tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.json",
        ],
        "disable_gate": "Paper-state and shadow artifacts remain fresh; GET-only/account boundaries remain false.",
    },
    {
        "id": "phase2_wf68_alert_digest",
        "phase": 2,
        "runner": "scripts/wf68_alert_digest_consolidated_runner.py",
        "runner_command": "python scripts\\wf68_alert_digest_consolidated_runner.py --write --write-md --validate",
        "replacement_job_name": "Finance - WF68 Alert Producer and Digest",
        "recommended_model": "command_job_preferred_or_ollama-cloud/glm-5.3:cloud",
        "target_seconds": 180,
        "hard_timeout_seconds": 600,
        "source_jobs": [
            "Finance - WF68 Intraday Alert Producer",
            "Finance - WF68 Grouped Alert Digest Handoff",
        ],
        "required_outputs": [
            "tmp/wf68-alert-digest-consolidated-runner.json",
            "tmp/intraday-alerts/current-alerts.json",
            "tmp/intraday-alerts/main-session-handoff-validation.json",
        ],
        "disable_gate": "Producer and grouped digest parity clean; no duplicate Telegram alerts.",
    },
]


def build_contract_payload(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    contracts: list[dict[str, Any]] = []
    by_name = {str(job.get("name") or ""): job for job in jobs}
    for contract in CONTRACTS:
        matched = find_jobs(jobs, contract["source_jobs"])
        missing = [name for name in contract["source_jobs"] if name not in by_name]
        enabled_matches = [job for job in matched if job.get("enabled")]
        runner_path = ROOT / contract["runner"]
        required_outputs = [ROOT / path for path in contract["required_outputs"]]
        if runner_path.exists() and not missing:
            status = "ready_to_shadow"
        elif matched and missing:
            status = "partial_source_match"
        elif not matched:
            status = "source_jobs_absent"
        else:
            status = "pending"
        contract_payload = {
            **contract,
            "runner_exists": runner_path.exists(),
            "source_job_count": len(matched),
            "enabled_source_job_count": len(enabled_matches),
            "source_jobs_found": [job_summary(job) for job in matched],
            "source_jobs_missing": missing,
            "required_output_status": [
                {"path": rel(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0}
                for path in required_outputs
            ],
            "status": status,
        }
        contracts.append(contract_payload)
    return {
        "schema": "veritas.cron_runner_contracts.v1",
        "generated_at_utc": utc_now(),
        "status": "ok"
        if all(item["status"] in {"ready_to_shadow", "pending", "source_jobs_absent"} for item in contracts)
        else "blocked",
        "contracts": contracts,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def load_artifact(path_text: str) -> dict[str, Any]:
    payload = load_json_artifact(ROOT / path_text)
    return payload if isinstance(payload, dict) else {}


def status_from(payload: dict[str, Any]) -> str:
    value = payload.get("status")
    if isinstance(value, str) and value:
        return value.lower()
    validation = payload.get("validation")
    if isinstance(validation, dict):
        value = validation.get("status")
        if isinstance(value, str) and value:
            return value.lower()
    return "missing"


def runner_component(
    *,
    name: str,
    path: str,
    fallback_path: str | None = None,
    fail_closed_blocker_ok: bool = False,
) -> dict[str, Any]:
    primary = ROOT / path
    used_path = path
    payload = load_artifact(path)
    fallback_used = False
    if not payload and fallback_path:
        payload = load_artifact(fallback_path)
        used_path = fallback_path
        fallback_used = bool(payload)
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    status = status_from(payload)
    blocker_packet = payload.get("main_session_blocker_packet")
    blocker_packet_exists = bool(blocker_packet and (ROOT / str(blocker_packet)).exists())
    blocker_dispatched = (
        fail_closed_blocker_ok
        and status == "blocked"
        and payload.get("operator_action") == "MAIN_SESSION_BLOCKER_PACKET"
        and blocker_packet_exists
    )
    primary_exists = primary.exists()
    clean = status in {"ok", "warning"}
    safe_to_disable = bool(primary_exists and (clean or blocker_dispatched))
    return {
        "name": name,
        "path": path,
        "path_used": used_path,
        "fallback_used": fallback_used,
        "exists": bool(payload),
        "cadence_specific_output_exists": primary_exists,
        "status": status,
        "validation_status": validation.get("status"),
        "errors": validation.get("errors") or [],
        "warnings": validation.get("warnings") or [],
        "elapsed_seconds": payload.get("elapsed_seconds"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "operator_action": payload.get("operator_action"),
        "blocker_packet": blocker_packet,
        "blocker_packet_exists": blocker_packet_exists,
        "fail_closed_blocker_accepted": blocker_dispatched,
        "safe_to_disable_source_jobs": safe_to_disable,
    }


def build_phase1_payload(enabled_count: int) -> dict[str, Any]:
    components = [
        runner_component(
            name="control_fail_closed_dispatcher",
            path="tmp/cron-control-digest-runner-control.json",
            fallback_path="tmp/cron-control-digest-runner.json",
            fail_closed_blocker_ok=True,
        ),
        runner_component(name="morning_control_digest", path="tmp/cron-control-digest-runner-morning.json", fail_closed_blocker_ok=True),
        runner_component(name="postclose_control_digest", path="tmp/cron-control-digest-runner-post-close.json", fail_closed_blocker_ok=True),
        runner_component(name="finance_delivery_daily", path="tmp/finance-delivery-series-consolidated-runner-daily.json"),
        runner_component(name="finance_delivery_weekly", path="tmp/finance-delivery-series-consolidated-runner-weekly.json"),
        runner_component(name="finance_delivery_monthly", path="tmp/finance-delivery-series-consolidated-runner-monthly.json"),
        runner_component(name="runtime_future_session", path="tmp/runtime-ops-consolidated-digest-future-session.json"),
        runner_component(name="runtime_otel", path="tmp/runtime-ops-consolidated-digest-otel.json"),
        runner_component(name="runtime_wf74_send", path="tmp/runtime-ops-consolidated-digest-wf74-send.json"),
    ]
    errors: list[str] = []
    for item in components:
        if not item["safe_to_disable_source_jobs"]:
            reason = "missing_cadence_specific_output" if not item["cadence_specific_output_exists"] else str(item["status"])
            errors.append(f"{item['name']}:{reason}")
    return {
        "schema": "veritas.cron_reduction_phase_parity.v1",
        "phase": "phase_1_control_delivery_runtime",
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "live_cron_mutation_allowed": not errors,
        "replacement_safe_to_apply": not errors,
        "enabled_count_after_attempt": enabled_count,
        "components": components,
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
            "warnings": [
                "No live cron jobs were added, disabled, edited, or removed.",
                "Cadence-specific output is required before disabling source jobs; legacy fallback output is proof context only.",
            ],
        },
        "next_safe_action": "Run cadence-specific Phase 1 shadow commands, then disable source jobs only after every component has cadence-specific proof and rollback IDs.",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_phase2_payload(enabled_count: int) -> dict[str, Any]:
    components = [
        runner_component(name="morning_market_paper", path="tmp/morning-market-paper-consolidated-runner.json"),
        runner_component(name="midday_market_paper", path="tmp/midday-market-paper-consolidated-runner.json"),
        runner_component(name="postclose_paper_reconciliation", path="tmp/postclose-paper-reconciliation-runner.json"),
        runner_component(name="wf68_alert_digest", path="tmp/wf68-alert-digest-consolidated-runner.json"),
    ]
    errors: list[str] = []
    for item in components:
        if item["status"] not in {"ok", "warning"}:
            errors.append(f"{item['name']}:{item['status']}")
    return {
        "schema": "veritas.cron_reduction_phase_parity.v1",
        "phase": "phase_2_market_paper_alerts",
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "live_cron_mutation_allowed": not errors,
        "replacement_safe_to_apply": not errors,
        "enabled_count_after_attempt": enabled_count,
        "components": components,
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
            "warnings": [
                "No live cron jobs were added, disabled, edited, or removed.",
                "Market/paper jobs still require a valid market-window shadow run before live disable.",
            ],
        },
        "next_safe_action": "Rerun morning and midday market/paper wrappers during a valid market session before disabling WF85/WF87/WF67/WF68 jobs.",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_phase3_payload(phase1: dict[str, Any], phase2: dict[str, Any], enabled_count: int) -> dict[str, Any]:
    blockers = []
    if phase1.get("status") != "ok":
        blockers.append("phase_1_control_delivery_runtime not clean")
    if phase2.get("status") != "ok":
        blockers.append("phase_2_market_paper_alerts not clean")
    return {
        "schema": "veritas.cron_reduction_phase_parity.v1",
        "phase": "phase_3_cadence_cleanup",
        "generated_at_utc": utc_now(),
        "status": "pending" if blockers else "ok",
        "live_cron_mutation_allowed": not blockers,
        "replacement_safe_to_apply": not blockers,
        "enabled_count_after_attempt": enabled_count,
        "blockers": blockers,
        "validation": {
            "status": "blocked" if blockers else "ok",
            "errors": blockers,
            "warnings": ["Phase 3 is intentionally held until Phase 1 and Phase 2 parity are clean."],
        },
        "next_safe_action": "Prepare live cron create/disable commands with rollback IDs only after earlier phases are clean.",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_payload() -> dict[str, Any]:
    jobs, cron_result = cron_list()
    enabled = [job for job in jobs if job.get("enabled")]
    disabled = [job for job in jobs if not job.get("enabled")]
    contracts = build_contract_payload(jobs)
    validation_errors: list[str] = []
    if not cron_result.get("ok"):
        validation_errors.append("cron_list_failed")
    if len(enabled) == 0:
        validation_errors.append("enabled_jobs_zero_unexpected")
    partial_missing_sources = [
        f"{contract['id']}:{','.join(contract['source_jobs_missing'])}"
        for contract in contracts["contracts"]
        if contract.get("status") == "partial_source_match"
    ]
    if partial_missing_sources:
        validation_errors.extend(f"partial_source_jobs:{item}" for item in partial_missing_sources)
    phase1 = build_phase1_payload(len(enabled))
    phase2 = build_phase2_payload(len(enabled))
    phase3 = build_phase3_payload(phase1, phase2, len(enabled))
    payload = {
        "schema": "veritas.cron_reduction_inventory.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_errors else "ok",
        "summary": {
            "total_jobs": len(jobs),
            "enabled_jobs": len(enabled),
            "disabled_jobs": len(disabled),
            "phase1_target_enabled_jobs": "38-42",
            "phase2_target_enabled_jobs": "29-32",
            "final_target_enabled_jobs": "25-27",
            "current_replacement_contracts": len(contracts["contracts"]),
            "source_jobs_absent_contracts": sum(
                1 for contract in contracts["contracts"] if contract.get("status") == "source_jobs_absent"
            ),
            "partial_source_match_contracts": sum(
                1 for contract in contracts["contracts"] if contract.get("status") == "partial_source_match"
            ),
        },
        "enabled_jobs": [job_summary(job) for job in enabled],
        "contracts_path": rel(CONTRACTS_OUT),
        "phase_proof_paths": {
            "phase1": rel(PHASE1_OUT),
            "phase2": rel(PHASE2_OUT),
            "phase3": rel(PHASE3_OUT),
        },
        "contracts": contracts["contracts"],
        "cron_list_result": cron_result,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "blocked" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [
                "This inventory is review-only. Use guarded cron add/edit/disable commands after shadow proof before live schedule changes."
            ],
        },
    }
    return payload, contracts, phase1, phase2, phase3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--contracts-out", type=Path, default=CONTRACTS_OUT)
    args = parser.parse_args()

    payload, contracts, phase1, phase2, phase3 = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    contracts_out = args.contracts_out if args.contracts_out.is_absolute() else ROOT / args.contracts_out
    if args.write:
        atomic_write_json(out, payload, indent=2)
        atomic_write_json(contracts_out, contracts, indent=2)
        atomic_write_json(PHASE1_OUT, phase1, indent=2)
        atomic_write_json(PHASE2_OUT, phase2, indent=2)
        atomic_write_json(PHASE3_OUT, phase3, indent=2)
    print(
        f"status={payload['status']} enabled={payload['summary']['enabled_jobs']} "
        f"contracts={payload['summary']['current_replacement_contracts']} out={rel(out)}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
