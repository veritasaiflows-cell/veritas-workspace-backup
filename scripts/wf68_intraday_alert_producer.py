#!/usr/bin/env python3
"""WF68 runtime producer wrapper.

Runs the read-only intraday alert artifact chain and writes a compact runtime
status artifact for the paired main-session systemEvent handoff. This wrapper
is intentionally local/artifact-only: no channel delivery, no cron wake, no
brokerage/account action, no paper/live order, no portfolio/canon/Call Log
mutation, and no owner-approval inference.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
STATUS_JSON = OUT_DIR / "runtime-handoff-status.json"
STATUS_MD = OUT_DIR / "runtime-handoff-status.md"

AUTHORITY = {
    "posture": "review_only_runtime_artifact_producer",
    "live_trade_or_account_action_allowed": False,
    "paper_trade_allowed": False,
    "paper_or_live_order_submission_allowed": False,
    "paper_or_live_order_cancellation_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "call_log_mutation_allowed": False,
    "state_history_append_allowed_by_this_wrapper": False,
    "cron_channel_config_mutation_allowed_by_this_wrapper": False,
    "owner_approval_inferred": False,
    "probability_claims_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_json_error": str(exc)}


def run_step(name: str, args: list[str]) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=420,
    )
    return {
        "name": name,
        "command": " ".join([sys.executable, *args]),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def artifact_record(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status") if isinstance(data, dict) else None,
        "schema_version": data.get("schema_version") if isinstance(data, dict) else None,
        "generated_at_utc": data.get("generated_at_utc") if isinstance(data, dict) else None,
        "summary": data.get("summary") if isinstance(data, dict) else None,
    }


def authority_clean(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, bool) and child is True:
                lowered = str(key).lower()
                if any(token in lowered for token in [
                    "trade", "order", "cancel", "account", "broker", "money", "portfolio",
                    "canonical", "call_log", "state_history", "approval", "mutation", "config",
                    "channel", "runtime", "probability",
                ]):
                    return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, status: dict[str, Any]) -> None:
    lines = [
        "# WF68 Runtime Handoff Status",
        "",
        f"- Generated UTC: {status['generated_at_utc']}",
        f"- Status: **{status['status']}**",
        f"- Handoff status: `{status.get('handoff_status')}`",
        f"- Action needed: **{str(status.get('action_needed')).lower()}**",
        f"- Failure reason: {status.get('failure_reason') or 'none'}",
        "- Boundary: review-only producer; no order/account/brokerage/money/canon/portfolio/Call Log/state-history/channel/config/runtime mutation or owner-approval inference.",
        "",
        "## Steps",
    ]
    for step in status.get("steps", []):
        lines.append(f"- `{step['name']}` returncode `{step['returncode']}` ok `{str(step['ok']).lower()}`")
    lines.extend(["", "## Artifacts"])
    for artifact in status.get("artifacts", []):
        lines.append(f"- `{artifact['path']}` exists `{str(artifact['exists']).lower()}` status `{artifact.get('status')}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_no_alert_advisor_validation() -> None:
    """Clear stale advisor validation errors when no alert packet is produced."""
    validation = {
        "schema_version": "wf68.advisor_alert_packet_validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "summary": {"alerts_checked": 0, "critical": 0, "warning": 0},
        "errors": [],
        "warnings": [],
        "note": "No ALERT_READY handoff was produced; advisor packet validation is intentionally neutral for this runtime pass.",
        "authority": AUTHORITY,
    }
    write_json(OUT_DIR / "advisor-alert-packet-validation.json", validation)
    (OUT_DIR / "advisor-alert-packet-validation.md").write_text(
        "# WF68 Advisor Alert Packet Validation\n\n"
        "- Status: **ok**\n"
        "- Alerts checked: 0\n"
        "- Boundary: no ALERT_READY handoff was produced; this clears stale advisor-validation errors for the current runtime pass.\n",
        encoding="utf-8",
    )


def write_blocked_router(reason: str, steps: list[dict[str, Any]]) -> None:
    """Overwrite stale router artifacts when the producer cannot finish cleanly."""
    router = {
        "schema_version": "wf68.delivery_router_status.v1",
        "workflow": "WF68",
        "generated_at_utc": utc_now(),
        "status": "BLOCKED_VALIDATION_ERROR",
        "immediate_policy": "failed runtime producer runs must not preserve stale execution-ready router artifacts",
        "action_needed": True,
        "immediate_count": 0,
        "grouped_count": 0,
        "blocked_in_band_count": 0,
        "immediate_execution_recommendations": [],
        "blocked_in_band_candidates": [],
        "grouped_digest_items": [],
        "execution_recommendation_paths": [],
        "user_facing_message": f"WF68 producer blocked: {reason}. Inspect tmp/intraday-alerts/runtime-handoff-status.json before any review or WF67 preparation.",
        "failure_reason": reason,
        "failed_steps": [
            {
                "name": step.get("name"),
                "returncode": step.get("returncode"),
                "ok": step.get("ok"),
            }
            for step in steps
            if not step.get("ok")
        ],
        "authority": AUTHORITY,
        "authority_clean": True,
        "boundary": "Blocked router artifact only. It prevents stale execution-ready state from surviving a failed producer run.",
    }
    write_json(OUT_DIR / "delivery-router-status.json", router)
    (OUT_DIR / "delivery-router-status.md").write_text(
        "# WF68 Delivery Router Status\n\n"
        "- Status: **BLOCKED_VALIDATION_ERROR**\n"
        f"- Failure reason: `{reason}`\n"
        "- Boundary: stale execution-ready state has been blocked; inspect runtime proof before action.\n",
        encoding="utf-8",
    )


def main() -> int:
    steps: list[dict[str, Any]] = []
    failure_reason: str | None = None

    sequence = [
        ("quote_snapshot_proof", ["scripts\\intraday_quote_snapshot_proof.py"]),
        ("trigger_engine", ["scripts\\intraday_alert_trigger_engine.py"]),
        (
            "main_session_handoff",
            [
                "scripts\\intraday_alert_main_handoff.py",
                "--input", "tmp\\intraday-alerts\\current-alerts.json",
                "--output-json", "tmp\\intraday-alerts\\main-session-handoff.json",
                "--output-md", "tmp\\intraday-alerts\\main-session-handoff.md",
                "--validation-output", "tmp\\intraday-alerts\\main-session-handoff-validation.json",
            ],
        ),
    ]

    for name, args in sequence:
        step = run_step(name, args)
        steps.append(step)
        if not step["ok"]:
            failure_reason = f"step_failed:{name}"
            break

    handoff = load_json(OUT_DIR / "main-session-handoff.json")
    handoff_status = handoff.get("status") if isinstance(handoff, dict) else None

    if failure_reason is None and handoff_status != "ALERT_READY":
        write_no_alert_advisor_validation()
        quiet_router = {
            "schema_version": "wf68.delivery_router_status.v1",
            "workflow": "WF68",
            "generated_at_utc": utc_now(),
            "status": "NO_REPLY",
            "immediate_policy": "only in-band execution recommendation packets interrupt; all other alerts are grouped",
            "action_needed": False,
            "immediate_count": 0,
            "grouped_count": 0,
            "blocked_in_band_count": 0,
            "immediate_execution_recommendations": [],
            "blocked_in_band_candidates": [],
            "grouped_digest_items": [],
            "execution_recommendation_paths": [],
            "user_facing_message": "NO_REPLY",
            "authority": AUTHORITY,
            "authority_clean": True,
            "boundary": "Quiet router artifact written by runtime producer because no validated alert packets were present.",
        }
        write_json(OUT_DIR / "delivery-router-status.json", quiet_router)
        (OUT_DIR / "delivery-router-status.md").write_text(
            "# WF68 Delivery Router Status\n\n- Status: **NO_REPLY**\n- Immediate count: 0\n- Grouped count: 0\n- Boundary: no validated alert packets were present; stay quiet.\n",
            encoding="utf-8",
        )

    if failure_reason is None and handoff_status == "ALERT_READY":
        advisor = run_step(
            "advisor_enricher",
            [
                "scripts\\intraday_alert_advisor_enricher.py",
                "--handoff", "tmp\\intraday-alerts\\main-session-handoff.json",
                "--output-json", "tmp\\intraday-alerts\\advisor-alert-packet.json",
                "--output-md", "tmp\\intraday-alerts\\advisor-alert-packet.md",
                "--validation-output", "tmp\\intraday-alerts\\advisor-alert-packet-validation.json",
            ],
        )
        steps.append(advisor)
        if not advisor["ok"]:
            failure_reason = "step_failed:advisor_enricher"
        else:
            outcome = run_step(
                "outcome_link",
                [
                    "scripts\\intraday_alert_outcome_link.py",
                    "--write",
                    "--advisor-packet", "tmp\\intraday-alerts\\advisor-alert-packet.json",
                    "--output-json", "tmp\\intraday-alerts\\advisor-alert-outcome-link.json",
                    "--output-md", "tmp\\intraday-alerts\\advisor-alert-outcome-link.md",
                    "--validation-output", "tmp\\intraday-alerts\\advisor-alert-outcome-link-validation.json",
                ],
            )
            steps.append(outcome)
            if not outcome["ok"]:
                failure_reason = "step_failed:outcome_link"
            else:
                router = run_step(
                    "delivery_router",
                    [
                        "scripts\\intraday_alert_delivery_router.py",
                        "--advisor-packet", "tmp\\intraday-alerts\\advisor-alert-packet.json",
                        "--output-json", "tmp\\intraday-alerts\\delivery-router-status.json",
                        "--output-md", "tmp\\intraday-alerts\\delivery-router-status.md",
                    ],
                )
                steps.append(router)
                if not router["ok"]:
                    failure_reason = "step_failed:delivery_router"

    artifacts = [
        OUT_DIR / "quote-snapshot-proof.json",
        OUT_DIR / "quote-snapshot-proof-validation.json",
        OUT_DIR / "current-alerts.json",
        OUT_DIR / "trigger-engine-validation.json",
        OUT_DIR / "main-session-handoff.json",
        OUT_DIR / "main-session-handoff-validation.json",
        OUT_DIR / "delivery-router-status.json",
    ]
    if handoff_status == "ALERT_READY":
        artifacts.extend([
            OUT_DIR / "advisor-alert-packet.json",
            OUT_DIR / "advisor-alert-packet-validation.json",
            OUT_DIR / "advisor-alert-outcome-link.json",
            OUT_DIR / "advisor-alert-outcome-link-validation.json",
        ])
    artifact_records = [artifact_record(path) for path in artifacts]

    validation_bad = []
    for artifact in artifact_records:
        if artifact["path"].endswith("validation.json"):
            status = artifact.get("status")
            summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
            critical = summary.get("critical") or summary.get("critical_count") or 0
            if status not in ("ok", None) or critical:
                validation_bad.append(artifact["path"])

    authority_ok = authority_clean(handoff) if isinstance(handoff, dict) else False
    if not authority_ok and failure_reason is None:
        failure_reason = "authority_flag_unexpectedly_true_or_handoff_missing"

    router_status_artifact = load_json(OUT_DIR / "delivery-router-status.json")
    delivery_router_status = router_status_artifact.get("status") if isinstance(router_status_artifact, dict) else None
    effective_handoff_status = delivery_router_status or handoff_status

    if failure_reason or validation_bad:
        write_blocked_router(failure_reason or f"validation_bad:{','.join(validation_bad)}", steps)
        router_status_artifact = load_json(OUT_DIR / "delivery-router-status.json")
        delivery_router_status = router_status_artifact.get("status") if isinstance(router_status_artifact, dict) else None
        effective_handoff_status = delivery_router_status or handoff_status

    status_value = "ok" if failure_reason is None and not validation_bad else "warning" if effective_handoff_status == "NO_REPLY" and not validation_bad else "error"
    action_needed = bool(
        failure_reason
        or validation_bad
        or effective_handoff_status in {
            "EXECUTION_PACKET_READY",
            "OWNER_REVIEW_PACKET_READY",
            "BLOCKED_VALIDATION_ERROR",
        }
    )

    result = {
        "schema_version": "wf68.runtime_handoff_status.v1",
        "workflow": "WF68",
        "generated_at_utc": utc_now(),
        "status": status_value,
        "handoff_status": effective_handoff_status,
        "raw_alert_handoff_status": handoff_status,
        "delivery_router_status": delivery_router_status,
        "action_needed": action_needed,
        "failure_reason": failure_reason,
        "validation_bad": validation_bad,
        "steps": steps,
        "artifacts": artifact_records,
        "authority": AUTHORITY,
        "authority_clean": authority_ok,
        "main_session_instruction": "Main handoff should interrupt for EXECUTION_PACKET_READY, OWNER_REVIEW_PACKET_READY, validation/blocker states, or failed/stale artifacts. OWNER_REVIEW_PACKET_READY is not execution-ready and carries no approval word. GROUPED_DIGEST_READY means non-immediate alerts are available on request/cadence but should not interrupt. NO_REPLY stays quiet.",
    }
    write_json(STATUS_JSON, result)
    write_md(STATUS_MD, result)
    print(json.dumps({
        "status": result["status"],
        "handoff_status": result["handoff_status"],
        "action_needed": result["action_needed"],
        "failure_reason": result["failure_reason"],
        "status_artifact": rel(STATUS_JSON),
    }, indent=2, sort_keys=True))
    return 0 if result["status"] in {"ok", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
