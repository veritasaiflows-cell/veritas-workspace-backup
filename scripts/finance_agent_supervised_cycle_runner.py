#!/usr/bin/env python3
"""Dry-run or execute one supervised finance-agent packet.

Default mode is packet validation only. `--execute-one` launches exactly one
packet through `openclaw agent --agent ... --json` and records the result for
main-Veritas verification. It does not bind agents to cron/channels, deliver
externally, mutate finance state, or infer approval.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import wf89_dispatch_record
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-agent-supervised-cycle-runner.json"
PACKETS = TMP / "finance-agent-packets.json"
OPENCLAW_MJS = Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "openclaw" / "openclaw.mjs"

SCHEMA = "veritas.finance_agent_supervised_cycle_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "supervised_single_packet_runner": True,
    "launches_at_most_one_agent_when_execute_one": True,
    "direct_cron_agent_binding_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "sql_or_ticker_card_mutation_allowed": False,
    "approval_card_generation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def openclaw_prefix() -> list[str]:
    node = shutil.which("node.exe") or shutil.which("node")
    if node and OPENCLAW_MJS.exists():
        return [node, str(OPENCLAW_MJS)]
    openclaw = shutil.which("openclaw.cmd") or shutil.which("openclaw.exe") or shutil.which("openclaw")
    return [openclaw or "openclaw"]


def select_packet(packets: dict[str, Any], packet_id: str | None, processed_fingerprints: set[str]) -> dict[str, Any]:
    rows = [as_dict(packet) for packet in as_list(packets.get("packets"))]
    if packet_id:
        for packet in rows:
            if packet.get("packet_id") == packet_id:
                return packet
        return {}
    for packet in rows:
        fingerprint = str(packet.get("packet_fingerprint") or "")
        if fingerprint and fingerprint in processed_fingerprints:
            continue
        return packet
    return rows[0] if rows else {}


def launch_args(packet: dict[str, Any]) -> list[str]:
    return [
        "--thinking",
        str(packet.get("thinking") or "low"),
        "--timeout",
        str(packet.get("timeout_seconds") or 900),
        "--json",
    ]


def command_for(packet: dict[str, Any]) -> list[str]:
    return wf89_dispatch_record.agent_command(
        openclaw_prefix(),
        str(packet.get("agent_id")),
        str(packet.get("session_key")),
        message_text=str(packet.get("message") or ""),
        extra_args=launch_args(packet),
    )


def preview_command(command: list[str]) -> list[str]:
    preview = list(command)
    if len(preview) >= 2 and preview[1].endswith("openclaw.mjs"):
        preview = ["openclaw", *preview[2:]]
    if "--message" in preview:
        idx = preview.index("--message")
        if idx + 1 < len(preview):
            preview[idx + 1] = "<packet message omitted>"
    return preview


def parse_agent_stdout(stdout: str) -> dict[str, Any]:
    try:
        parsed = json.loads(stdout)
        return parsed if isinstance(parsed, dict) else {"parsed_json_type": type(parsed).__name__, "value_preview": str(parsed)[:500]}
    except json.JSONDecodeError:
        return {}


def parse_agent_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    meta = as_dict(as_dict(parsed.get("result")).get("meta"))
    candidates = [
        meta.get("finalAssistantVisibleText"),
        meta.get("finalAssistantRawText"),
    ]
    for payload in as_list(as_dict(parsed.get("result")).get("payloads")):
        candidates.append(as_dict(payload).get("text"))
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        try:
            result = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            return result
    return {}


def run_packet(packet: dict[str, Any]) -> dict[str, Any]:
    command = command_for(packet)
    started = utc_now()
    try:
        # WF89: the launcher writes the dispatch record before starting the run.
        _dispatch, proc = wf89_dispatch_record.launch(
            str(packet.get("agent_id")),
            str(packet.get("session_key")),
            f"finance packet: {packet.get('packet_id') or 'unknown'}",
            message_text=str(packet.get("message") or ""),
            extra_args=launch_args(packet),
            binary=openclaw_prefix(),
            launched_by="finance_agent_supervised_cycle_runner",
            cwd=ROOT, text=True, capture_output=True,
            timeout=int(packet.get("timeout_seconds") or 900) + 60,
        )
        parsed = parse_agent_stdout(proc.stdout)
        agent_payload = parse_agent_payload(parsed)
        return {
            "executed": True,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "command_preview": preview_command(command),
            "stdout_preview": proc.stdout.strip()[-5000:],
            "stderr_preview": proc.stderr.strip()[-2500:],
            "parsed_json": parsed,
            "agent_payload": agent_payload,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "executed": True,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": int(packet.get("timeout_seconds") or 900) + 60,
            "command_preview": preview_command(command),
            "stdout_preview": stdout[-5000:],
            "stderr_preview": stderr[-2500:],
        }
    except FileNotFoundError as exc:
        return {
            "executed": True,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "command_preview": preview_command(command),
            "stdout_preview": "",
            "stderr_preview": f"openclaw executable not found: {exc}",
        }
    except (OSError, ValueError) as exc:
        # The dispatch record could not be written, so the agent was not started.
        return {
            "executed": False,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "command_preview": preview_command(command),
            "stdout_preview": "",
            "stderr_preview": f"wf89 dispatch record not written; agent not launched: {exc}",
        }


def build_report(execute_one: bool, packet_id: str | None) -> dict[str, Any]:
    packets = load(PACKETS)
    previous = load(OUT)
    previous_processed = {
        str(item)
        for item in as_list(as_dict(previous.get("summary")).get("processed_packet_fingerprints"))
        if str(item)
    }
    packet = select_packet(packets, packet_id, previous_processed if execute_one else set())
    command = command_for(packet) if packet else []
    execution = run_packet(packet) if execute_one and packet else {
        "executed": False,
        "ok": True,
        "command_preview": preview_command(command) if command else [],
        "reason": "dry_run_default" if packet else "no_packet_available",
    }
    processed_fingerprints = sorted(previous_processed)
    selected_fingerprint = str(packet.get("packet_fingerprint") or "") if packet else ""
    if execution.get("executed") is True and execution.get("ok") is True and selected_fingerprint:
        processed_fingerprints = sorted({*processed_fingerprints, selected_fingerprint})
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": "execute_one" if execute_one else "dry_run",
        "purpose": "Run at most one supervised finance-agent packet for main-Veritas verification.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "packets": {
                "path": rel(PACKETS),
                "exists": PACKETS.exists(),
                "loaded": bool(packets),
                "schema": packets.get("schema"),
                "status": packets.get("status"),
                "generated_at_utc": packets.get("generated_at_utc"),
            }
        },
        "summary": {
            "selected_packet_id": packet.get("packet_id") if packet else None,
            "selected_packet_fingerprint": selected_fingerprint or None,
            "selected_agent_id": packet.get("agent_id") if packet else None,
            "selected_ticker": packet.get("target_ticker") if packet else None,
            "packet_count": len(as_list(packets.get("packets"))),
            "processed_packet_count": len(processed_fingerprints),
            "processed_packet_fingerprints": processed_fingerprints,
            "execute_one_requested": execute_one,
            "executed": execution.get("executed") is True,
            "execution_ok": execution.get("ok") is True,
            "agent_output_ticker": as_dict(execution.get("agent_payload")).get("target_ticker"),
            "agent_ticker_echo_valid": as_dict(execution.get("agent_payload")).get("ticker_echo_valid"),
            "agent_readiness_impact": as_dict(execution.get("agent_payload")).get("readiness_impact"),
            "agent_forbidden_boundary_hit_count": len(as_list(as_dict(execution.get("agent_payload")).get("forbidden_boundary_hits"))),
            "requires_main_veritas_verification": True,
            "next_safe_action": (
                "Main Veritas must parse/check the agent output, reject any boundary/readiness violation, and close proof."
                if execution.get("executed")
                else "All current packets have already been processed; regenerate source artifacts or queue for new work."
                if execute_one and as_list(packets.get("packets")) and not packet
                else "Run with --execute-one from a main-session supervised pickup only after packets validate clean."
            ),
        },
        "selected_packet": {
            key: value
            for key, value in packet.items()
            if key not in {"message"}
        } if packet else {},
        "execution": execution,
        "stop_lines": [
            "Default dry run writes proof only.",
            "--execute-one launches exactly one packet and does not use --deliver.",
            "No direct cron binding, channel delivery, runtime/config change, portfolio/canon/SQL/ticker mutation, approval-card generation, capital deployment, paper/live/account action, or owner approval inference.",
        ],
    }
    report["validation"] = validate_report(report)
    report["status"] = "ok" if report["validation"]["status"] == "ok" else "blocked"
    return report


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if report.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    packet = as_dict(report.get("selected_packet"))
    if report.get("mode") == "execute_one" and not packet:
        if as_dict(report.get("summary")).get("packet_count"):
            warnings.append("execute_one_no_unprocessed_packet_available")
        else:
            errors.append("execute_one_requested_without_packet")
    if packet:
        if packet.get("agent_id") not in {"finance-source-scout", "finance-redteam"}:
            errors.append(f"forbidden_agent:{packet.get('agent_id')}")
        if packet.get("requires_main_veritas_verification") is not True:
            errors.append("packet_missing_main_veritas_verification")
        if as_dict(packet.get("authority_boundary")) != {
            "review_only": True,
            "packet_generation_only": True,
            "launches_agents": False,
            "direct_cron_agent_binding_allowed": False,
            "cron_schedule_mutation_allowed": False,
            "runtime_config_mutation_allowed": False,
            "portfolio_or_canon_mutation_allowed": False,
            "sql_or_ticker_card_mutation_allowed": False,
            "approval_card_generation_allowed": False,
            "capital_deployment_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_allowed": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "external_delivery_allowed": False,
            "owner_approval_inferred": False,
        }:
            errors.append("selected_packet_authority_boundary_changed")
    execution = as_dict(report.get("execution"))
    command = [str(part) for part in as_list(execution.get("command_preview"))]
    if "--deliver" in command:
        errors.append("deliver_flag_forbidden")
    if report.get("mode") == "execute_one" and execution.get("ok") is not True:
        errors.append("agent_execution_failed")
    if report.get("mode") == "execute_one" and execution.get("ok") is True:
        payload = as_dict(execution.get("agent_payload"))
        target = str(as_dict(report.get("summary")).get("selected_ticker") or "")
        if not payload:
            errors.append("agent_payload_not_parseable_json")
        if str(payload.get("target_ticker") or "").upper() != target:
            errors.append(f"agent_ticker_echo_mismatch:{target}:{payload.get('target_ticker')}")
        if payload.get("ticker_echo_valid") is not True:
            errors.append(f"agent_ticker_echo_invalid:{target}")
        if payload.get("readiness_impact") not in {"no_change", "demote", "source_context_only"}:
            errors.append(f"agent_readiness_impact_invalid:{target}:{payload.get('readiness_impact')}")
        if as_list(payload.get("forbidden_boundary_hits")):
            errors.append(f"agent_forbidden_boundary_hits:{target}")
    if report.get("mode") == "dry_run":
        warnings.append("dry_run_no_agent_executed")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one supervised finance-agent packet or dry-run proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--execute-one", action="store_true")
    parser.add_argument("--packet-id")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report(args.execute_one, args.packet_id)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} mode={report['mode']} "
            f"agent={report['summary']['selected_agent_id']} ticker={report['summary']['selected_ticker']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
