#!/usr/bin/env python3
"""Restore selected quiet-only agentTurn cron jobs to command-backed payloads."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CONTRACT_DIR = ROOT / "state" / "cron-contracts"
DEFAULT_OUT = TMP / "cron-predispatch-payload-restore.json"
DEFAULT_APPLY_OUT = TMP / "cron-predispatch-payload-restore-live-apply.json"
DEFAULT_MD = TMP / "cron-predispatch-payload-restore-summary.md"
SCHEMA = "veritas.cron_predispatch_payload_restore.v1"
QUIET_ONLY_PREFIX = "QUIET CRON OUTPUT RULE (hard):"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "payload_restore_only": True,
    "schedule_mutation_allowed": False,
    "delivery_mutation_allowed": False,
    "enable_disable_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


@dataclass(frozen=True)
class RestoreSpec:
    name: str
    owner_workflow: str
    contract_path: str
    description: str
    argv: tuple[str, ...]
    timeout_seconds: int
    expected_artifacts: tuple[str, ...]
    include_failure_alert_compare: bool = False


SPECS: tuple[RestoreSpec, ...] = (
    RestoreSpec(
        name="Runtime - Future Session Packet Refresh",
        owner_workflow="future session carryover packet refresh",
        contract_path="state/cron-contracts/runtime-future-session-packet-refresh.json",
        description=(
            "Command-backed future-session packet refresh with changed-input skip. Review-only; no schedule, "
            "delivery, runtime config, finance/canon/portfolio, execution, account, or approval authority."
        ),
        argv=("python", "scripts\\future_session_enhancement_packet.py", "--write", "--write-md", "--skip-if-unchanged", "--validate"),
        timeout_seconds=300,
        expected_artifacts=("tmp/future-session-enhancement-packet.json", "tmp/future-session-enhancement-packet.md"),
        include_failure_alert_compare=True,
    ),
    RestoreSpec(
        name="Finance - Daily Canon Drift Freshness Gate",
        owner_workflow="WF64/WF56 canon drift proof",
        contract_path="state/cron-contracts/finance-daily-canon-drift-freshness-gate.json",
        description=(
            "Command-backed daily canon drift/freshness proof with changed-input skip. Review-only; no canon/"
            "portfolio mutation, capital deployment, paper/live/account action, or owner approval inference."
        ),
        argv=("python", "scripts\\canon_drift_freshness_gate.py", "--skip-if-unchanged", "--write"),
        timeout_seconds=600,
        expected_artifacts=("tmp/canon-drift-freshness-gate.json",),
    ),
    RestoreSpec(
        name="Cron Reduction - Control Fail-Closed Dispatcher",
        owner_workflow="CRON phase1 control reduction",
        contract_path="state/cron-contracts/cron-reduction-control-fail-closed-dispatcher.json",
        description=(
            "Command-backed Phase 1 cron/control fail-closed dispatcher with changed-input skip. Review-only; "
            "no repair execution, schedule mutation, finance/canon/portfolio, paper/live/account, or approval authority."
        ),
        argv=("python", "scripts\\cron_control_digest_runner.py", "--window", "control", "--write", "--write-md", "--validate"),
        timeout_seconds=420,
        expected_artifacts=(
            "tmp/cron-control-digest-runner-control.json",
            "tmp/cron-contract-validator.json",
            "tmp/cron-control-packet.json",
            "tmp/escalation-trigger.json",
        ),
    ),
    RestoreSpec(
        name="Cron Reduction - Morning Control Digest",
        owner_workflow="CRON phase1 morning control reduction",
        contract_path="state/cron-contracts/cron-reduction-morning-control-digest.json",
        description=(
            "Command-backed morning cron/control digest. Review-only; no repair execution, schedule mutation, "
            "finance/canon/portfolio, paper/live/account, or approval authority."
        ),
        argv=("python", "scripts\\cron_control_digest_runner.py", "--window", "morning", "--write", "--write-md", "--validate"),
        timeout_seconds=420,
        expected_artifacts=(
            "tmp/cron-control-digest-runner-morning.json",
            "tmp/cron-contract-validator.json",
            "tmp/cron-control-packet.json",
            "tmp/morning-control-digest.json",
        ),
    ),
    RestoreSpec(
        name="Cron Reduction - Post-Close Control Digest",
        owner_workflow="CRON phase1 post-close control reduction",
        contract_path="state/cron-contracts/cron-reduction-post-close-control-digest.json",
        description=(
            "Command-backed post-close cron/control digest. Review-only; no repair execution, schedule mutation, "
            "finance/canon/portfolio, paper/live/account, or approval authority."
        ),
        argv=("python", "scripts\\cron_control_digest_runner.py", "--window", "post-close", "--write", "--write-md", "--validate"),
        timeout_seconds=420,
        expected_artifacts=(
            "tmp/cron-control-digest-runner-post-close.json",
            "tmp/cron-contract-validator.json",
            "tmp/cron-control-packet.json",
            "tmp/post-close-control-digest.json",
        ),
    ),
    RestoreSpec(
        name="Memory Dream Review Packet",
        owner_workflow="OpenClaw Dreaming review packet",
        contract_path="state/cron-contracts/memory-dream-review-packet.json",
        description=(
            "Command-backed OpenClaw Dreaming review packet. Review-only; no memory promotion, config mutation, "
            "delivery, canon/portfolio, execution, account, or approval authority."
        ),
        argv=("python", "scripts\\dream_review_packet.py", "--write", "--validate"),
        timeout_seconds=120,
        expected_artifacts=("tmp/dream-review-packet.json",),
    ),
    RestoreSpec(
        name="Finance - Silent Tier A Intraday Market Readiness Probe",
        owner_workflow="WF78/WF85/WF87 market readiness",
        contract_path="state/cron-contracts/finance-silent-tier-a-intraday-market-readiness-probe.json",
        description=(
            "Command-backed silent Tier A intraday readiness probe. Review-only; no send, approval, execution, "
            "canon/portfolio, account, or capital authority."
        ),
        argv=(
            "python",
            "scripts\\finance_market_deployment_operating_loop.py",
            "--window",
            "intraday",
            "--refresh-readiness",
            "--refresh-intraday",
            "--write",
            "--write-md",
            "--validate",
        ),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/finance-market-deployment-operating-loop.json",
            "tmp/finance-market-deployment-operating-loop.md",
            "tmp/tier-a-intraday-opportunity-probe.json",
            "tmp/market-execution-readiness-cron-hardening.json",
        ),
    ),
    RestoreSpec(
        name="Finance - Silent Tier A Confirmation Market Readiness Probe",
        owner_workflow="WF78/WF85/WF87 market readiness",
        contract_path="state/cron-contracts/finance-silent-tier-a-confirmation-market-readiness-probe.json",
        description=(
            "Command-backed silent Tier A confirmation readiness probe. Review-only; no send, approval, execution, "
            "canon/portfolio, account, or capital authority."
        ),
        argv=(
            "python",
            "scripts\\finance_market_deployment_operating_loop.py",
            "--window",
            "intraday",
            "--refresh-readiness",
            "--refresh-intraday",
            "--write",
            "--write-md",
            "--validate",
        ),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/finance-market-deployment-operating-loop.json",
            "tmp/finance-market-deployment-operating-loop.md",
            "tmp/tier-a-intraday-opportunity-probe.json",
            "tmp/market-execution-readiness-cron-hardening.json",
        ),
    ),
    RestoreSpec(
        name="Finance - Silent Tier A Late-Session Market Readiness Probe",
        owner_workflow="WF78/WF85/WF87 market readiness",
        contract_path="state/cron-contracts/finance-silent-tier-a-late-session-market-readiness-probe.json",
        description=(
            "Command-backed silent Tier A late-session readiness probe. Review-only; no send, approval, execution, "
            "canon/portfolio, account, or capital authority."
        ),
        argv=(
            "python",
            "scripts\\finance_market_deployment_operating_loop.py",
            "--window",
            "late_session",
            "--refresh-readiness",
            "--refresh-intraday",
            "--write",
            "--write-md",
            "--validate",
        ),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/finance-market-deployment-operating-loop.json",
            "tmp/finance-market-deployment-operating-loop.md",
            "tmp/tier-a-intraday-opportunity-probe.json",
            "tmp/market-execution-readiness-cron-hardening.json",
        ),
    ),
    RestoreSpec(
        name="Ops - OTEL Local Digest",
        owner_workflow="WF74 observability and model-quality operations",
        contract_path="state/cron-contracts/ops-otel-local-digest.json",
        description=(
            "Command-backed WF74 local-only OTEL/model-quality collection digest. Review-only metadata only; no raw "
            "prompt/response/tool capture, external export, runtime config mutation, finance/canon/portfolio, execution, "
            "account, or approval authority."
        ),
        argv=(
            "python",
            "scripts\\wf74_model_quality_collection_cron_runner.py",
            "--write",
            "--write-md",
            "--validate",
            "--cron-nonblocking-domain-exit",
        ),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/wf74-model-quality-collection-cron-runner.json",
            "tmp/model-quality-scorecard.json",
            "tmp/cron-control-packet.json",
            "tmp/otel-ops-control.json",
            "tmp/otel-ops-window-summary.json",
            "tmp/otel-tool-workflow-metadata.json",
            "tmp/model-learning-metadata-ledger.json",
            "tmp/otel-learning-loop.json",
            "tmp/coding-runtime-kpi-probe.json",
        ),
    ),
    RestoreSpec(
        name="Finance - WF78 Open-Ready Owner Review Proof",
        owner_workflow="WF78/WF85 open-ready owner review proof",
        contract_path="state/cron-contracts/finance-wf78-open-ready-owner-review-proof.json",
        description=(
            "Command-backed WF78 open-ready owner-review proof. Review-only; no deployment mutation, approval, "
            "execution, canon/portfolio, cash/sizing/risk, account, or capital authority."
        ),
        argv=("python", "scripts\\wf78_open_ready_owner_review_cron_runner.py", "--write", "--validate"),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/wf78-open-ready-owner-review-cron-runner.json",
            "tmp/wf78-position-sizing-surface-review.json",
            "tmp/wf78-deployment-readiness-review.json",
            "tmp/wf78-source-artifact-capture-review.json",
            "tmp/wf78-position-sizing-integration-proposal.json",
            "tmp/wf78-tier-a-owner-readiness-proposals.json",
            "tmp/cron-control-packet.json",
        ),
    ),
    RestoreSpec(
        name="Finance - WF78 Opportunity Refresh Controller",
        owner_workflow="WF78/WF84/WF85 opportunity visibility",
        contract_path="state/cron-contracts/finance-wf78-opportunity-refresh-controller.json",
        description=(
            "Command-backed WF78 opportunity refresh controller. Review-only visibility and routing proof; no registry "
            "apply, canon/portfolio mutation, approval, execution, account, or capital authority."
        ),
        argv=("python", "scripts\\wf78_opportunity_refresh_controller.py", "--mode", "audit", "--write", "--validate"),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/wf78-opportunity-refresh-controller.json",
            "tmp/wf78-opportunity-visibility-queue.json",
            "tmp/wf78-promotion-visibility-top10.json",
            "tmp/wf78-tier-b-research-packets.json",
            "tmp/wf78-tier-b-research-packet-requests.json",
            "tmp/wf78-tier-b-research-packets.sqlite",
            "tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json",
            "tmp/wf78-tier-c-to-b-auto-promotion-pipeline.closeout.json",
            "tmp/wf85-opportunity-visibility-queue.json",
            "tmp/finance-decision-factory.json",
            "tmp/finance-market-deployment-operating-loop.json",
        ),
        include_failure_alert_compare=True,
    ),
    RestoreSpec(
        name="Finance - WF78 to WF85 Owner Review Conversion Bridge",
        owner_workflow="WF78/WF85 owner-review card conversion",
        contract_path="state/cron-contracts/finance-wf78-wf85-conversion-bridge.json",
        description=(
            "Command-backed WF78 to WF85 owner-review conversion bridge. Review-only card surfacing; no approval, "
            "execution, canon/portfolio, cash/sizing/risk, account, or capital authority."
        ),
        argv=("python", "scripts\\wf78_wf85_conversion_bridge.py", "--write", "--validate"),
        timeout_seconds=900,
        expected_artifacts=("tmp/wf78-wf85-conversion-bridge.json", "tmp/wf85-owner-review-cards.json"),
        include_failure_alert_compare=True,
    ),
    RestoreSpec(
        name="Finance - WF87 Market-Hours Fresh Gate Probe",
        owner_workflow="WF87 market-hours gate proof",
        contract_path="state/cron-contracts/finance-wf87-market-hours-fresh-gate-probe.json",
        description=(
            "Command-backed WF87 market-hours fresh-gate probe. Review-only; no kill switch, approval, execution, "
            "paper/live/account, canon/portfolio, or capital authority."
        ),
        argv=("python", "scripts\\wf87_market_hours_gate_probe.py", "--write", "--validate"),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/wf87-market-hours-gate-probe.json",
            "tmp/wf87-position-sizing-runtime-check.json",
            "tmp/wf87-portfolio-circuit-breakers.json",
            "tmp/wf87-approval-freshness-ttl.json",
            "tmp/wf87-intraday-monitor.json",
            "tmp/wf87-shadow-outcome-scorecard.json",
            "tmp/wf87-v2-readiness-rollup.json",
            "tmp/autonomous-routing-deployment-cards.json",
            "tmp/autonomous-card-authority-audit.json",
        ),
    ),
    RestoreSpec(
        name="Finance - WF87 Autonomy Command Center Refresh",
        owner_workflow="WF87 autonomy command center",
        contract_path="state/cron-contracts/finance-wf87-autonomy-command-center-refresh.json",
        description=(
            "Command-backed WF87 autonomy command-center refresh. Review-only routing-card proof; no approval, "
            "execution, paper/live/account, canon/portfolio, or capital authority."
        ),
        argv=(
            "python",
            "scripts\\wf87_autonomy_command_center.py",
            "--refresh-routing-cards",
            "--write",
            "--write-md",
            "--validate",
        ),
        timeout_seconds=900,
        expected_artifacts=(
            "tmp/wf87-autonomy-command-center.json",
            "tmp/wf87-v2-readiness-rollup.json",
            "tmp/paper-autotrader/assisted-order-cards.json",
            "tmp/wf87-market-hours-gate-probe.json",
            "tmp/wf87-shadow-outcome-scorecard.json",
            "tmp/wf87-assisted-paper-cadence.json",
            "tmp/wf85-deployment-timing-gate.json",
            "tmp/morning-paper-deployment-recommendation-cards.json",
            "tmp/autonomous-routing-deployment-cards.json",
            "tmp/autonomous-card-authority-audit.json",
        ),
    ),
    RestoreSpec(
        name="Finance - WF78 Daily Freshness and Promotion Proof",
        owner_workflow="WF78",
        contract_path="state/cron-contracts/finance-wf78-daily-freshness-and-promotion-proof.json",
        description=(
            "Command-backed WF78 daily_core_v2 pre-open proof. Runs fail-on-budget daily routing and repair proof. "
            "Review-only; no registry apply, canon/portfolio mutation, capital deployment, paper/live/account action, "
            "or approval inference."
        ),
        argv=(
            "python",
            "scripts\\wf78_intelligence_routing_v2.py",
            "--layer",
            "daily_core_v2",
            "--fail-on-budget-exceeded",
            "--write",
            "--validate",
        ),
        timeout_seconds=1500,
        expected_artifacts=(
            "tmp/wf78-intelligence-routing-v2.json",
            "tmp/wf78-daily-movement-ledger.json",
            "tmp/wf78-repair-priority-queue.json",
            "tmp/cron-control-packet.json",
            "tmp/veritas-artifact-index.sqlite",
        ),
        include_failure_alert_compare=True,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def openclaw_cmd() -> str:
    found = shutil.which("openclaw.cmd") or shutil.which("openclaw") or shutil.which("openclaw.ps1")
    if found:
        return found
    known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(known) if known.exists() else "openclaw.cmd"


def run_command(command: list[str], timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
    }


def cron_list() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    command = [openclaw_cmd(), "cron", "list", "--all", "--json", "--timeout", "30000"]
    result = run_command(command, timeout=60)
    if not result["ok"]:
        return [], result
    try:
        payload = json.loads(result["stdout_tail"] if len(result["stdout_tail"]) == len(result["stdout_tail"]) else result["stdout_tail"])
    except json.JSONDecodeError:
        # stdout_tail can be truncated for huge outputs; rerun and parse full stdout via subprocess directly.
        completed = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        result.update({"returncode": completed.returncode, "ok": completed.returncode == 0, "stderr_tail": (completed.stderr or "")[-4000:]})
        if completed.returncode != 0:
            return [], result
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result["ok"] = False
            result["error"] = "cron_list_json_parse_failed"
            return [], result
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        result["ok"] = False
        result["error"] = "cron_list_missing_jobs"
        return [], result
    return [job for job in jobs if isinstance(job, dict)], result


def find_job(jobs: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    matches = [job for job in jobs if job.get("name") == name]
    return matches[0] if len(matches) == 1 else None


def is_quiet_only_agent_turn(job: dict[str, Any]) -> bool:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    message = payload.get("message")
    return payload.get("kind") == "agentTurn" and isinstance(message, str) and message.startswith(QUIET_ONLY_PREFIX) and len(message) < 500


def desired_payload(spec: RestoreSpec) -> dict[str, Any]:
    return {
        "kind": "command",
        "argv": list(spec.argv),
        "cwd": str(ROOT),
        "timeoutSeconds": spec.timeout_seconds,
    }


def field_diff(job: dict[str, Any], spec: RestoreSpec) -> list[dict[str, Any]]:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    desired = desired_payload(spec)
    fields = [
        ("description", job.get("description"), spec.description),
        ("payload.kind", payload.get("kind"), desired["kind"]),
        ("payload.argv", payload.get("argv"), desired["argv"]),
        ("payload.cwd", payload.get("cwd"), desired["cwd"]),
        ("payload.timeoutSeconds", payload.get("timeoutSeconds"), desired["timeoutSeconds"]),
    ]
    return [{"field": key, "before": before, "after": after} for key, before, after in fields if before != after]


def compare_fields_for(spec: RestoreSpec, live_job: dict[str, Any] | None = None) -> list[str]:
    fields = [
        "enabled",
        "description",
        "schedule",
        "sessionTarget",
        "wakeMode",
        "delivery.mode",
        "delivery.bestEffort",
        "payload.kind",
        "payload.argv",
        "payload.cwd",
        "payload.timeoutSeconds",
    ]
    if live_job and "deleteAfterRun" in live_job:
        fields.insert(2, "deleteAfterRun")
    if spec.include_failure_alert_compare:
        fields.insert(8, "failureAlert")
    return fields


def authority_for(spec: RestoreSpec) -> dict[str, Any]:
    payload = dict(AUTHORITY_BOUNDARY)
    payload.update(
        {
            "cron_contract_only": True,
            "owner_workflow": spec.owner_workflow,
            "command_payload": True,
            "agent_turn_model_spawn_required": False,
        }
    )
    if spec.name.startswith("Ops - OTEL"):
        payload.update(
            {
                "metadata_only": True,
                "raw_prompt_capture_allowed": False,
                "raw_response_capture_allowed": False,
                "tool_payload_capture_allowed": False,
                "external_export_allowed": False,
                "model_ranking_claim": False,
            }
        )
    return payload


def build_contract(spec: RestoreSpec, live_job: dict[str, Any] | None) -> dict[str, Any]:
    existing = load_json(ROOT / spec.contract_path)
    contract = dict(existing)
    contract.update(
        {
            "schema": "veritas.cron_contract.v1",
            "job_id": live_job.get("id") if live_job else existing.get("job_id"),
            "name": spec.name,
            "required": True,
            "owner_workflow": spec.owner_workflow,
            "contract_reason": existing.get(
                "contract_reason",
                "Command-backed cron payload contract so quiet-only agentTurn drift is caught by validation.",
            ),
            "enabled": live_job.get("enabled", True) if live_job else existing.get("enabled", True),
            "deleteAfterRun": live_job.get("deleteAfterRun", False) if live_job else existing.get("deleteAfterRun", False),
            "schedule": live_job.get("schedule", existing.get("schedule", {})) if live_job else existing.get("schedule", {}),
            "sessionTarget": live_job.get("sessionTarget", existing.get("sessionTarget", "isolated")) if live_job else existing.get("sessionTarget", "isolated"),
            "wakeMode": live_job.get("wakeMode", existing.get("wakeMode", "now")) if live_job else existing.get("wakeMode", "now"),
            "delivery": live_job.get("delivery", existing.get("delivery", {"mode": "none"})) if live_job else existing.get("delivery", {"mode": "none"}),
            "payload": desired_payload(spec),
            "compare_fields": compare_fields_for(spec, live_job),
            "expected_artifacts": list(spec.expected_artifacts),
            "authority_boundary": authority_for(spec),
            "description": spec.description,
            "updated_at_utc": utc_now(),
            "contract_update_reason": "Restore quiet-only agentTurn cron to command-backed pre-dispatch proof path; preserve schedule/session/delivery.",
        }
    )
    if spec.include_failure_alert_compare and live_job and "failureAlert" in live_job:
        contract["failureAlert"] = live_job["failureAlert"]
    return contract


def edit_command(job_id: str, spec: RestoreSpec) -> list[str]:
    return [
        openclaw_cmd(),
        "cron",
        "edit",
        job_id,
        "--command-argv",
        json.dumps(list(spec.argv)),
        "--command-cwd",
        str(ROOT),
        "--timeout-seconds",
        str(spec.timeout_seconds),
        "--description",
        spec.description,
        "--timeout",
        "30000",
    ]


def build_restore_payload(*, apply: bool, write_contracts: bool) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    jobs, list_meta = cron_list()
    contracts_to_write: list[tuple[Path, dict[str, Any]]] = []
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    if not list_meta.get("ok"):
        errors.append("live_cron_list_failed")

    for spec in SPECS:
        job = find_job(jobs, spec.name)
        if job is None:
            errors.append(f"missing_live_job:{spec.name}")
            rows.append({"name": spec.name, "status": "missing_live_job"})
            continue
        diffs = field_diff(job, spec)
        quiet_only = is_quiet_only_agent_turn(job)
        existing_payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        row: dict[str, Any] = {
            "name": spec.name,
            "job_id": job.get("id"),
            "enabled": job.get("enabled"),
            "schedule": job.get("schedule"),
            "sessionTarget": job.get("sessionTarget"),
            "delivery": job.get("delivery"),
            "before_payload": existing_payload,
            "after_payload": desired_payload(spec),
            "quiet_only_agent_turn": quiet_only,
            "diffs": diffs,
            "status": "already_restored" if not diffs else "needs_restore",
            "apply_command": edit_command(str(job.get("id")), spec),
            "apply_result": None,
            "contract_path": spec.contract_path,
            "expected_artifacts": list(spec.expected_artifacts),
        }
        if existing_payload.get("kind") == "command" and not diffs:
            row["status"] = "already_restored"
        if apply and diffs:
            result = run_command(edit_command(str(job.get("id")), spec), timeout=90)
            row["apply_result"] = result
            row["status"] = "applied" if result.get("ok") else "apply_failed"
            if not result.get("ok"):
                errors.append(f"apply_failed:{spec.name}")
        contract = build_contract(spec, job)
        contracts_to_write.append((ROOT / spec.contract_path, contract))
        if write_contracts:
            atomic_write_json(ROOT / spec.contract_path, contract)
        rows.append(row)

    after_jobs: list[dict[str, Any]] = []
    after_list_meta: dict[str, Any] = {}
    if apply and not errors:
        after_jobs, after_list_meta = cron_list()
        for row in rows:
            spec = next((item for item in SPECS if item.name == row.get("name")), None)
            if spec is None or row.get("status") == "missing_live_job":
                continue
            after_job = find_job(after_jobs, spec.name)
            if after_job is None:
                errors.append(f"post_apply_missing_live_job:{spec.name}")
                continue
            row["post_apply_payload"] = after_job.get("payload")
            remaining = field_diff(after_job, spec)
            row["post_apply_remaining_diffs"] = remaining
            if remaining:
                errors.append(f"post_apply_drift:{spec.name}")
    elif apply:
        after_list_meta = {"skipped": "preexisting_errors"}

    if not any(row.get("diffs") for row in rows if row.get("status") != "missing_live_job"):
        warnings.append("no_live_payload_diffs")

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else ("applied" if apply else "planned"),
        "apply": apply,
        "write_contracts": write_contracts,
        "summary": {
            "target_count": len(SPECS),
            "needs_restore_count": sum(1 for row in rows if row.get("diffs")),
            "quiet_only_agent_turn_count": sum(1 for row in rows if row.get("quiet_only_agent_turn")),
            "applied_count": sum(1 for row in rows if row.get("status") == "applied"),
            "already_restored_count": sum(1 for row in rows if row.get("status") == "already_restored"),
            "main_session_wake_reduction": "agentTurn model wake replaced by command payload for restored rows",
        },
        "live_list_meta": {key: value for key, value in list_meta.items() if key != "stdout_tail"},
        "post_apply_live_list_meta": {key: value for key, value in after_list_meta.items() if key != "stdout_tail"},
        "jobs": rows,
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return payload, contracts_to_write


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Cron Pre-Dispatch Payload Restore",
        "",
        f"- Status: `{payload['status']}`",
        f"- Apply: `{payload['apply']}`",
        f"- Targets: `{payload['summary']['target_count']}`",
        f"- Quiet-only agentTurn targets: `{payload['summary']['quiet_only_agent_turn_count']}`",
        f"- Needs restore: `{payload['summary']['needs_restore_count']}`",
        f"- Applied: `{payload['summary']['applied_count']}`",
        "",
        "| Job | Status | Before | After |",
        "|---|---|---|---|",
    ]
    for row in payload["jobs"]:
        before = (row.get("before_payload") or {}).get("kind")
        after = (row.get("after_payload") or {}).get("kind")
        lines.append(f"| {row.get('name')} | {row.get('status')} | {before} | {after} |")
    lines.extend(
        [
            "",
            "Boundary: payload/contract restore only. No schedule, delivery, enable/disable, finance canon/portfolio, capital, paper/live/account, or owner-approval authority.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply live cron payload edits through openclaw cron edit.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown summary.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--apply-output", type=Path, default=DEFAULT_APPLY_OUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--no-contract-write", action="store_true", help="Do not write local cron contract updates.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, _contracts = build_restore_payload(apply=args.apply, write_contracts=not args.no_contract_write and args.write)
    output = args.apply_output if args.apply else args.output
    output = output if output.is_absolute() else ROOT / output
    if args.write:
        atomic_write_json(output, payload)
    if args.write_md:
        md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
        atomic_write_text(md_output, render_md(payload))
    if not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True))
    if args.validate and payload["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
