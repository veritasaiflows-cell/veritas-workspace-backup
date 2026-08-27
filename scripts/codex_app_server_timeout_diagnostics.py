#!/usr/bin/env python3
"""Diagnose Codex app-server turn/completed idle timeouts.

This report is read-only. It scans recent OpenClaw session trajectories for
typed Codex app-server timeout events and checks whether the Codex plugin
appServer idle timeout settings are explicitly configured.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = ROOT.parent
SESSIONS_DIR = OPENCLAW_HOME / "agents" / "main" / "sessions"
CONFIG_PATH = OPENCLAW_HOME / "openclaw.json"
PLUGIN_MANIFEST = OPENCLAW_HOME / "npm" / "node_modules" / "@openclaw" / "codex" / "openclaw.plugin.json"
DEFAULT_OUT = ROOT / "tmp" / "codex-app-server-timeout-diagnostics.json"

TIMEOUT_SIGNATURE = "codex app-server turn idle timed out waiting for turn/completed"
CODEX_CONFIG_PATH = ("plugins", "entries", "codex", "config")
APP_SERVER_KEYS = (
    "appServer.requestTimeoutMs",
    "appServer.turnCompletionIdleTimeoutMs",
    "appServer.postToolRawAssistantCompletionIdleTimeoutMs",
)
RECOMMENDED_VALUES = {
    "appServer.requestTimeoutMs": 240_000,
    "appServer.turnCompletionIdleTimeoutMs": 180_000,
    "appServer.postToolRawAssistantCompletionIdleTimeoutMs": 240_000,
}
RECOMMENDED_NESTED_APP_SERVER = {
    "requestTimeoutMs": 240_000,
    "turnCompletionIdleTimeoutMs": 180_000,
    "postToolRawAssistantCompletionIdleTimeoutMs": 240_000,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def nested_get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def scan_trajectory_files(limit_files: int) -> dict[str, Any]:
    files = sorted(
        SESSIONS_DIR.glob("*.trajectory.jsonl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )[:limit_files]
    events: list[dict[str, Any]] = []
    by_model: Counter[str] = Counter()
    by_thread: Counter[str] = Counter()
    by_session: Counter[str] = Counter()
    by_run_prefix: Counter[str] = Counter()
    by_timeout_ms: Counter[str] = Counter()
    by_last_activity_reason: Counter[str] = Counter()
    signature_text_matches = 0

    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line in lines:
            if TIMEOUT_SIGNATURE in line:
                signature_text_matches += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "turn.completion_idle_timeout":
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            run_id = str(event.get("runId") or "")
            run_prefix = "announce" if run_id.startswith("announce:") else run_id.split(":", 1)[0] if ":" in run_id else "direct"
            item = {
                "ts": event.get("ts"),
                "session_key": event.get("sessionKey"),
                "session_id": event.get("sessionId"),
                "provider": event.get("provider"),
                "model_id": event.get("modelId"),
                "model_api": event.get("modelApi"),
                "run_id": run_id,
                "run_class": run_prefix,
                "thread_id": data.get("threadId"),
                "turn_id": data.get("turnId"),
                "yield_detected": data.get("yieldDetected"),
                "timed_out": data.get("timedOut"),
                "idle_ms": data.get("idleMs"),
                "timeout_ms": data.get("timeoutMs"),
                "last_activity_reason": data.get("lastActivityReason"),
                "last_notification_method": data.get("lastNotificationMethod"),
                "active_app_server_turn_requests": data.get("activeAppServerTurnRequests"),
                "active_turn_item_count": data.get("activeTurnItemCount"),
                "terminal_turn_notification_queued": data.get("terminalTurnNotificationQueued"),
            }
            events.append(item)
            by_model[str(item["model_id"])] += 1
            by_thread[str(item["thread_id"])] += 1
            by_session[str(item["session_key"])] += 1
            by_run_prefix[run_prefix] += 1
            if item["timeout_ms"] is not None:
                by_timeout_ms[str(item["timeout_ms"])] += 1
            if item["last_activity_reason"] is not None:
                by_last_activity_reason[str(item["last_activity_reason"])] += 1

    events.sort(key=lambda item: str(item.get("ts") or ""))
    return {
        "files_scanned": len(files),
        "events": events,
        "counts": {
            "timeout_events": len(events),
            "signature_text_matches": signature_text_matches,
            "signature_text_non_event_matches": max(0, signature_text_matches - len(events)),
            "by_model": dict(by_model),
            "by_thread": dict(by_thread),
            "by_session_key": dict(by_session),
            "by_run_class": dict(by_run_prefix),
            "by_timeout_ms": dict(by_timeout_ms),
            "by_last_activity_reason": dict(by_last_activity_reason),
            "yield_detected_false": sum(1 for event in events if event.get("yield_detected") is False),
        },
    }


def codex_config_snapshot() -> dict[str, Any]:
    config = read_json(CONFIG_PATH, {})
    plugin_config = nested_get(config, CODEX_CONFIG_PATH)
    if not isinstance(plugin_config, dict):
        plugin_config = {}
    app_server = plugin_config.get("appServer")
    if not isinstance(app_server, dict):
        app_server = {}
    configured: dict[str, Any] = {}
    missing: list[str] = []
    for dotted in APP_SERVER_KEYS:
        _, nested_key = dotted.split(".", 1)
        if nested_key in app_server:
            configured[dotted] = app_server[nested_key]
        elif dotted in plugin_config:
            configured[dotted] = plugin_config[dotted]
        else:
            missing.append(dotted)
    manifest = read_json(PLUGIN_MANIFEST, {})
    return {
        "config_path": rel(CONFIG_PATH),
        "plugin_manifest_path": rel(PLUGIN_MANIFEST),
        "codex_plugin_enabled": bool(nested_get(config, ("plugins", "entries", "codex", "enabled"))),
        "configured_app_server_values": configured,
        "missing_app_server_values": missing,
        "recommended_values": RECOMMENDED_VALUES,
        "recommended_nested_config": {"appServer": RECOMMENDED_NESTED_APP_SERVER},
        "plugin_manifest_has_app_server_keys": all(
            key in json.dumps(manifest, ensure_ascii=True) for key in APP_SERVER_KEYS
        ),
        "mutation_performed": False,
    }


def build_report(limit_files: int) -> dict[str, Any]:
    scan = scan_trajectory_files(limit_files)
    config = codex_config_snapshot()
    events = scan["events"]
    missing_timeout_overrides = bool(config["missing_app_server_values"])
    repeated_timeouts = len(events) >= 3
    status = "action_recommended" if repeated_timeouts or missing_timeout_overrides else "watch"
    if repeated_timeouts:
        root_cause = (
            "Repeated genuine turn_completion_idle_timeout events were found. "
            "These events mean a raw assistant response or progress notification was observed without a terminal "
            "turn/completed event before the configured guard elapsed; written config presence alone does not clear the pattern."
        )
    elif missing_timeout_overrides:
        root_cause = (
            "No repeated genuine timeout pattern was found, but one or more Codex appServer idle timeout controls are not explicitly configured."
        )
    elif events:
        root_cause = (
            "One or more genuine turn_completion_idle_timeout events were found, below the repeated-event escalation threshold."
        )
    else:
        root_cause = "No genuine turn_completion_idle_timeout events were found in scanned trajectory files."
    return {
        "schema_version": "codex_app_server_timeout_diagnostics.v2",
        "generated_at_utc": utc_now(),
        "status": status,
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": (
            "Read-only OpenClaw/Codex timeout diagnostics. No config/auth/channel/service/runtime mutation, "
            "no credential exposure, no finance/canon/portfolio mutation, no trading/account/paper/live authority."
        ),
        "symptom": TIMEOUT_SIGNATURE,
        "root_cause_assessment": root_cause,
        "evidence": scan,
        "codex_config": config,
        "recommended_next_step_requires_owner_approval": {
            "reason": "Changing OpenClaw plugin/runtime config is outside workspace-only mutation.",
            "candidate_config_values": RECOMMENDED_VALUES,
            "validation_after_change": [
                "openclaw config validate",
                "restart or reload gateway if OpenClaw reports runtime-loaded config",
                "openclaw status",
                "run one long Codex turn and confirm no new turn_completion_idle_timeout event",
            ],
        },
        "non_config_hardening_already_safe": [
            "Use narrower helper packets for implementation lanes.",
            "Avoid broad tmp/workspace searches inside user-visible turns.",
            "Emit short user-visible progress before long validation bundles.",
            "Prefer report scripts that write compact JSON over chat-streaming large proof output.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Codex app-server turn/completed idle timeouts")
    parser.add_argument("--write", action="store_true", help=f"Write {DEFAULT_OUT.as_posix()}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit-files", type=int, default=80)
    parser.add_argument("--validate", action="store_true", help="Return nonzero only if diagnostics cannot run")
    args = parser.parse_args()

    report = build_report(max(1, args.limit_files))
    if args.write:
        atomic_write_json(args.output, report, indent=2, ensure_ascii=True)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    print(
        "status={status} timeout_events={events} missing_overrides={missing} output={output}".format(
            status=report["status"],
            events=report["evidence"]["counts"]["timeout_events"],
            missing=len(report["codex_config"]["missing_app_server_values"]),
            output=args.output.as_posix() if args.write else "stdout",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
