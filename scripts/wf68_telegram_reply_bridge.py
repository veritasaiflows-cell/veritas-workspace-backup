#!/usr/bin/env python3
"""WF68 Telegram reply bridge.

Reads the Telegram direct-session transcript for Randall and writes a narrow
reply handoff artifact for the WebChat/main session. Optionally creates a
one-shot OpenClaw cron systemEvent to wake the main session.

This is a reply/handoff wrapper only. It does not create/submit/cancel paper
orders, touch Alpaca, mutate portfolio/canon state, infer approval, or make
live-account changes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_ROOT = Path(os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw")))
SESSIONS_DIR = OPENCLAW_ROOT / "agents" / "main" / "sessions"
SESSIONS_JSON = SESSIONS_DIR / "sessions.json"
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_STATE_JSON = OUT_DIR / "telegram-reply-bridge-state.json"
DEFAULT_OUTPUT_JSON = OUT_DIR / "telegram-reply-bridge-status.json"
DEFAULT_OUTPUT_MD = OUT_DIR / "telegram-reply-bridge-status.md"
DEFAULT_TARGET = "8650152206"
DEFAULT_TELEGRAM_SESSION_KEY = f"agent:main:telegram:direct:{DEFAULT_TARGET}"
DEFAULT_MAIN_SESSION_TARGET = "main"

AUTHORITY = {
    "posture": "telegram_reply_shadow_bridge",
    "telegram_reply_read_allowed": True,
    "main_session_system_event_allowed": True,
    "cli_cron_add_allowed_without_gateway_scope": False,
    "wf67_request_preparation_allowed": False,
    "paper_trade_execution_allowed": False,
    "paper_or_live_order_submission_allowed": False,
    "paper_or_live_order_cancellation_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "owner_approval_inferred": False,
}

BOUNDARY = (
    "Telegram reply bridge only. ACK confirms delivery. REVIEW asks main session "
    "to inspect the WF68 packet. PREPARE asks main session to consider creating a "
    "WF67 request artifact after fresh proof. APPROVE is not active in Telegram "
    "shadow mode. No paper/live order, brokerage/account action, money movement, "
    "portfolio/canon mutation, or owner approval inference is authorized."
)

COMMAND_RE = re.compile(r"^\s*(ACK|REVIEW|PREPARE|APPROVE)\b(?P<body>.*)$", re.IGNORECASE)
NON_TICKER_WORDS = {
    "ACK",
    "REVIEW",
    "PREPARE",
    "APPROVE",
    "DELIVERY",
    "TEST",
    "MESSAGE",
    "MSG",
    "ALERT",
    "PAPER",
    "READY",
    "SHADOW",
    "PILOT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_openclaw_command() -> str:
    found = shutil.which("openclaw") or shutil.which("openclaw.cmd") or shutil.which("openclaw.ps1")
    if found:
        return found
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "npm" / "openclaw.cmd"
        if candidate.exists():
            return str(candidate)
    return "openclaw"


def resolve_session_transcript(session_key: str) -> tuple[Path | None, dict[str, Any] | None]:
    sessions = load_json(SESSIONS_JSON, {})
    if not isinstance(sessions, dict):
        return None, None
    item = sessions.get(session_key)
    if not isinstance(item, dict):
        return None, None
    session_id = item.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        return None, item
    transcript = SESSIONS_DIR / f"{session_id}.jsonl"
    return transcript if transcript.exists() else None, item


def iter_user_messages(transcript: Path, target: str, lookback_minutes: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    messages: list[dict[str, Any]] = []
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        if message.get("role") != "user":
            continue
        if message.get("sourceChannel") != "telegram":
            continue
        if str(message.get("senderId") or "") != target:
            continue
        stamp = parse_utc(row.get("timestamp"))
        if stamp is not None and stamp < cutoff:
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        messages.append(
            {
                "row_id": row.get("id"),
                "timestamp_utc": stamp.isoformat().replace("+00:00", "Z") if stamp else None,
                "sender_id": str(message.get("senderId")),
                "sender_label": message.get("senderLabel"),
                "content": content.strip(),
                "idempotency_key": message.get("idempotencyKey"),
            }
        )
    return messages


def parse_command(message: dict[str, Any]) -> dict[str, Any] | None:
    content = str(message.get("content") or "").strip()
    match = COMMAND_RE.match(content)
    if not match:
        return None
    command = match.group(1).upper()
    body = match.group("body").strip()
    tokens = body.split()
    workflow = next((token.upper() for token in tokens if token.upper().startswith("WF")), "WF68")
    ticker = next(
        (
            token.upper()
            for token in tokens
            if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", token.upper())
            and not token.upper().startswith("WF")
            and token.upper() not in NON_TICKER_WORDS
        ),
        None,
    )
    numeric_refs = [token for token in tokens if re.fullmatch(r"\d+", token)]
    blocked = command == "APPROVE"
    return {
        "command": command,
        "body": body,
        "workflow": workflow,
        "ticker": ticker,
        "message_ref": numeric_refs[-1] if numeric_refs else None,
        "telegram_row_id": message.get("row_id"),
        "telegram_timestamp_utc": message.get("timestamp_utc"),
        "telegram_sender_id": message.get("sender_id"),
        "raw_content": content,
        "status": "BLOCKED_UNSUPPORTED_APPROVE" if blocked else "REPLY_READY",
        "blocked": blocked,
        "reason": "APPROVE is not active in Telegram shadow mode" if blocked else None,
    }


def build_main_message(command: dict[str, Any], output_json: Path) -> str:
    if command["blocked"]:
        headline = "WF68 TELEGRAM REPLY BLOCKED"
    else:
        headline = "WF68 TELEGRAM REPLY RECEIVED"
    ticker_text = f"\nTicker: {command['ticker']}" if command.get("ticker") else ""
    ref_text = f"\nTelegram/outbound message ref: {command['message_ref']}" if command.get("message_ref") else ""
    return (
        f"{headline} (SHADOW PILOT)\n"
        f"Command: {command['command']}\n"
        f"Workflow: {command['workflow']}"
        f"{ticker_text}"
        f"{ref_text}\n"
        f"Raw reply: {command['raw_content']}\n"
        f"Status: {command['status']}\n"
        f"Proof: {rel(output_json)}\n\n"
        f"{BOUNDARY}"
    )


def create_main_wake(message: str, timeout: int) -> dict[str, Any]:
    command = [
        resolve_openclaw_command(),
        "cron",
        "add",
        "--name",
        "WF68 Telegram Reply Bridge - one shot",
        "--description",
        "One-shot main-session wake for a Telegram WF68 shadow reply.",
        "--at",
        "+2s",
        "--session",
        DEFAULT_MAIN_SESSION_TARGET,
        "--system-event",
        message,
        "--delete-after-run",
        "--no-deliver",
        "--timeout",
        str(timeout * 1000),
        "--json",
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": "openclaw cron add --at +2s --session main --system-event <redacted> --delete-after-run --no-deliver --json",
        "resolved_command": command[0],
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def render_md(result: dict[str, Any]) -> str:
    lines = [
        "# WF68 Telegram Reply Bridge Status",
        "",
        f"- Generated UTC: `{result['generated_at_utc']}`",
        f"- Status: **{result['status']}**",
        f"- Telegram session key: `{result['telegram_session_key']}`",
        f"- Transcript: `{result.get('telegram_transcript') or ''}`",
        f"- Parsed command count: `{len(result.get('commands', []))}`",
        f"- Woke main: `{result.get('woke_main')}`",
        "",
        "## Boundary",
        "",
        BOUNDARY,
    ]
    if result.get("main_session_message"):
        lines.extend(["", "## Main Session Message", "", "```text", result["main_session_message"], "```"])
    if result.get("commands"):
        lines.extend(["", "## Commands", ""])
        for item in result["commands"]:
            lines.append(f"- `{item['status']}` `{item['command']}`: {item['raw_content']}")
    if result.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in result["blockers"])
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge Telegram WF68 replies into a main-session proof/wake artifact.")
    parser.add_argument("--telegram-session-key", default=DEFAULT_TELEGRAM_SESSION_KEY)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--lookback-minutes", type=int, default=180)
    parser.add_argument("--wake-main", action="store_true")
    parser.add_argument("--mark-processed", action="store_true", help="Mark the latest parsed reply processed after an external authorized wake succeeds.")
    parser.add_argument("--force", action="store_true", help="Process matching replies even if state says they were already bridged.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = utc_now()
    state_path = args.state if args.state.is_absolute() else ROOT / args.state
    output_json = args.output_json if args.output_json.is_absolute() else ROOT / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else ROOT / args.output_md
    state = load_json(state_path, {"processed_row_ids": {}})
    processed = state.get("processed_row_ids") if isinstance(state.get("processed_row_ids"), dict) else {}
    blockers: list[str] = []

    transcript, session_meta = resolve_session_transcript(args.telegram_session_key)
    if transcript is None:
        blockers.append("telegram_session_transcript_missing")
        messages: list[dict[str, Any]] = []
    else:
        messages = iter_user_messages(transcript, args.target, args.lookback_minutes)

    commands: list[dict[str, Any]] = []
    for message in messages:
        parsed = parse_command(message)
        if parsed is None:
            continue
        row_id = str(parsed.get("telegram_row_id") or "")
        if row_id in processed and not args.force:
            continue
        commands.append(parsed)

    latest = commands[-1] if commands else None
    main_message = build_main_message(latest, output_json) if latest else None
    wake_result = None
    woke_main = False
    if latest and args.wake_main:
        wake_result = create_main_wake(main_message or "", args.timeout_seconds)
        woke_main = bool(wake_result.get("ok"))
        if not woke_main:
            blockers.append("main_session_wake_failed")

    if latest and ((args.wake_main and woke_main) or args.mark_processed):
        row_id = str(latest.get("telegram_row_id") or "")
        if row_id:
            processed[row_id] = {
                "processed_at_utc": generated_at,
                "command": latest.get("command"),
                "woke_main": woke_main or args.mark_processed,
                "mark_source": "script_wake" if args.wake_main and woke_main else "external_authorized_wake",
            }
            state["processed_row_ids"] = processed
            write_json(state_path, state)

    if blockers:
        status = "BLOCKED"
    elif latest and args.wake_main and woke_main:
        status = "BRIDGED_MAIN_WAKE_CREATED"
    elif latest and args.mark_processed:
        status = "MARKED_PROCESSED_AFTER_EXTERNAL_WAKE"
    elif latest:
        status = "DRY_RUN_READY"
    else:
        status = "NO_REPLY"

    result = {
        "schema_version": "wf68.telegram_reply_bridge_status.v1",
        "workflow": "WF68",
        "generated_at_utc": generated_at,
        "status": status,
        "telegram_session_key": args.telegram_session_key,
        "telegram_transcript": rel(transcript) if transcript else None,
        "telegram_session_meta": {
            "sessionId": session_meta.get("sessionId") if isinstance(session_meta, dict) else None,
            "updatedAt": session_meta.get("updatedAt") if isinstance(session_meta, dict) else None,
        },
        "target": args.target,
        "lookback_minutes": args.lookback_minutes,
        "commands": commands,
        "latest_command": latest,
        "main_session_message": main_message,
        "wake_result": wake_result,
        "woke_main": woke_main,
        "blockers": blockers,
        "source_artifacts": {
            "sessions_json": str(SESSIONS_JSON),
            "state": rel(state_path),
        },
        "authority": AUTHORITY,
        "authority_clean": True,
        "boundary": BOUNDARY,
    }
    write_json(output_json, result)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_md(result), encoding="utf-8")
    print(json.dumps({
        "status": status,
        "command_count": len(commands),
        "latest_command": latest.get("command") if latest else None,
        "woke_main": woke_main,
        "blockers": blockers,
        "output_json": rel(output_json),
    }, indent=2, sort_keys=True))
    return 0 if status in {"BRIDGED_MAIN_WAKE_CREATED", "MARKED_PROCESSED_AFTER_EXTERNAL_WAKE", "DRY_RUN_READY", "NO_REPLY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
