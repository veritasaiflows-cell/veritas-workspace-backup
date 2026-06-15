#!/usr/bin/env python3
"""Telegram notifier for the WF85 paper-deployment radar.

The notifier sends the digest preview to Randall when the local digest says
there is material deployment/near-deployment/watch/repair state to review. It is
delivery only. Telegram replies may route to REVIEW/PREPARE workflows elsewhere,
but APPROVE is not active and this script never submits paper orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_DIGEST = TMP / "wf85-paper-deployment-notification-digest.json"
DEFAULT_STATE = TMP / "wf85-paper-deployment-telegram-state.json"
DEFAULT_OUTPUT = TMP / "wf85-paper-deployment-telegram-notifier.json"
DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"
MARKET_TZ = ZoneInfo("America/New_York")

AUTHORITY = {
    "posture": "telegram_delivery_review_only_wf85_paper_deployment_radar",
    "telegram_delivery_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_or_live_order_submission_allowed": False,
    "paper_or_live_order_cancellation_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "owner_approval_inferred": False,
}

BOUNDARY = (
    "Delivery note: this alert is review/prep only. It does not approve or "
    "submit any paper/live order. Paper orders still require exact Randall "
    "approval plus fresh WF67 guard and kill-switch proof."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_minutes(value: Any) -> float | None:
    parsed = parse_utc(value)
    if not parsed:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60), 2)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path, default: Any) -> Any:
    payload = load_json_artifact(path)
    return payload if payload is not None else default


def authority_clean(value: Any) -> bool:
    dangerous = (
        "capital",
        "trade",
        "execution",
        "order",
        "submit",
        "cancel",
        "sell",
        "account",
        "brokerage",
        "money",
        "portfolio",
        "canonical",
        "approval",
        "mutation",
    )
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, bool) and child is True:
                if any(token in lowered for token in dangerous) and lowered != "telegram_delivery_allowed":
                    return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


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


def send_telegram(channel: str, target: str, message: str, timeout: int) -> dict[str, Any]:
    openclaw_command = resolve_openclaw_command()
    command = [openclaw_command, "message", "send", "--channel", channel, "--target", target, "--message", message]
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
        "command": "openclaw message send --channel <channel> --target <target> --message <redacted>",
        "resolved_command": openclaw_command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "ok": completed.returncode == 0,
    }


def market_hours_gate() -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone(MARKET_TZ)
    minutes = now.hour * 60 + now.minute
    open_minutes = 9 * 60 + 30
    close_minutes = 16 * 60
    weekday = now.weekday() < 5
    in_regular_session = weekday and open_minutes <= minutes < close_minutes
    return {
        "timezone": "America/New_York",
        "checked_at_local": now.replace(microsecond=0).isoformat(),
        "weekday": weekday,
        "regular_session": "09:30-16:00 America/New_York",
        "in_regular_session": in_regular_session,
        "reason": "regular_market_hours" if in_regular_session else "outside_regular_market_hours",
    }


def build_message(digest: dict[str, Any]) -> tuple[str | None, str]:
    validation = as_dict(digest.get("validation"))
    summary = as_dict(digest.get("summary"))
    if digest.get("status") == "blocked" or validation.get("status") == "blocked":
        errors = ", ".join(str(item) for item in as_list(validation.get("errors"))[:6]) or "unknown"
        text = (
            "WF85 PAPER DEPLOYMENT RADAR BLOCKED\n"
            f"Errors: {errors}\n"
            f"Proof: {rel(DEFAULT_DIGEST)}\n\n"
            f"{BOUNDARY}"
        )
        return text, "blocker"

    if digest.get("operator_action") == "NO_REPLY":
        return None, "no_reply"

    preview = digest.get("message_preview")
    if not isinstance(preview, str) or not preview.strip():
        return None, "no_message_preview"

    guard_ready = summary.get("wf67_guard_ready_for_submit_cancel") is True
    guard_status = "clean" if summary.get("wf67_guard_status") == "ok" else str(summary.get("wf67_guard_status") or "unknown")
    guard_line = "WF67 guard: clean for review" if guard_ready and guard_status == "clean" else f"WF67 guard: {guard_status}; not execution-ready"
    header = f"Generated UTC: {digest.get('generated_at_utc')}\n{guard_line}\n"
    return f"{header}\n{preview}\n\n{BOUNDARY}", "radar"


def flatten_section(section: str) -> str:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    return " | ".join(lines)


def split_long_text(value: str, limit: int) -> list[str]:
    if len(value) <= limit:
        return [value]
    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        split_at = remaining.rfind(" | ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip(" |"))
        remaining = remaining[split_at:].strip(" |")
    if remaining:
        chunks.append(remaining)
    return chunks


def telegram_cli_safe_messages(message: str, max_chars: int = 2800) -> list[str]:
    """Return newline-free chunks to avoid CLI/provider first-line truncation."""
    sections = [flatten_section(section) for section in message.strip().split("\n\n")]
    sections = [section for section in sections if section]
    raw_chunks: list[str] = []
    current = ""
    for section in sections:
        candidates = split_long_text(section, max_chars)
        for candidate in candidates:
            if not current:
                current = candidate
            elif len(current) + len(" || ") + len(candidate) <= max_chars:
                current = f"{current} || {candidate}"
            else:
                raw_chunks.append(current)
                current = candidate
    if current:
        raw_chunks.append(current)
    total = len(raw_chunks)
    return [f"WF85 Paper Deployment Radar alert part {index}/{total}: {chunk}" for index, chunk in enumerate(raw_chunks, start=1)]


def message_key(digest: dict[str, Any], kind: str) -> str | None:
    generated = parse_utc(digest.get("generated_at_utc"))
    if generated is None:
        return None
    summary = as_dict(digest.get("summary"))
    raw = json.dumps(
        {
            "kind": kind,
            "day": generated.date().isoformat(),
            "deployment_ready": summary.get("deployment_ready_tickers"),
            "near_deployment": summary.get("near_deployment_tickers"),
            "wf67_guard_status": summary.get("wf67_guard_status"),
            "wf85_drafts": summary.get("wf85_approval_card_draft_count"),
            "status": digest.get("status"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send WF85 paper-deployment Telegram radar notification.")
    parser.add_argument("--digest", type=Path, default=DEFAULT_DIGEST)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--max-age-minutes", type=int, default=240)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--market-hours-only", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    digest_path = args.digest if args.digest.is_absolute() else ROOT / args.digest
    state_path = args.state if args.state.is_absolute() else ROOT / args.state
    output = args.output if args.output.is_absolute() else ROOT / args.output

    digest = load_json(digest_path, {})
    state = load_json(state_path, {"sent_keys": {}})
    blockers: list[str] = []
    if not isinstance(digest, dict) or not digest:
        blockers.append("digest_missing_or_invalid")
        digest = {}
    if not authority_clean(AUTHORITY):
        blockers.append("notifier_authority_drift")
    if not authority_clean(as_dict(digest.get("authority_boundary"))):
        blockers.append("digest_authority_drift")

    age = age_minutes(digest.get("generated_at_utc"))
    if age is None:
        blockers.append("digest_generated_at_missing")
    elif age > args.max_age_minutes:
        blockers.append(f"digest_stale:{age}min_gt_{args.max_age_minutes}min")

    market_gate = market_hours_gate()
    if args.market_hours_only and not market_gate["in_regular_session"]:
        message, kind = None, "outside_market_hours"
    else:
        message, kind = build_message(digest) if not blockers else (None, "artifact_blocker")
    key = message_key(digest, kind) if message else None
    sent_keys = state.get("sent_keys") if isinstance(state.get("sent_keys"), dict) else {}
    duplicate = bool(key and key in sent_keys and not args.force)
    if duplicate:
        blockers.append("dedupe_key_already_sent")

    sent_count = 0
    send_result: dict[str, Any] | None = None
    delivery_messages = telegram_cli_safe_messages(message) if message else []
    mode = "send" if args.send else "dry_run"
    status = "NO_REPLY"

    non_dedupe_blockers = [item for item in blockers if item != "dedupe_key_already_sent"]

    if message and not non_dedupe_blockers:
        if duplicate:
            status = "NO_REPLY"
        if args.send:
            if not duplicate:
                chunk_results = [
                    send_telegram(args.channel, args.target, item, args.timeout_seconds)
                    for item in delivery_messages
                ]
                send_result = {
                    "chunk_count": len(chunk_results),
                    "chunks": chunk_results,
                    "ok": bool(chunk_results) and all(item.get("ok") for item in chunk_results),
                }
                if send_result.get("ok"):
                    sent_count = len(chunk_results)
                    status = "SENT"
                    sent_keys[key] = {"sent_at_utc": utc_now(), "message_kind": kind}
                    state["sent_keys"] = sent_keys
                    atomic_write_json(state_path, state)
                else:
                    status = "SEND_FAILED"
                    blockers.append("openclaw_message_send_failed")
        elif not duplicate:
            status = "DRY_RUN_READY"
    elif message and non_dedupe_blockers:
        status = "BLOCKED"
    elif non_dedupe_blockers:
        status = "BLOCKED"

    result = {
        "schema": "veritas.wf85_paper_deployment_telegram_notifier.v1",
        "generated_at_utc": utc_now(),
        "workflow": "WF85/WF67",
        "status": status,
        "mode": mode,
        "channel": args.channel,
        "target": args.target,
        "message_kind": kind,
        "dedupe_key": key,
        "duplicate": duplicate,
        "digest_age_minutes": age,
        "sent_count": sent_count,
        "blockers": blockers,
        "market_hours_gate": market_gate,
        "message_preview": message,
        "delivery_message_preview": "\n".join(delivery_messages) if delivery_messages else None,
        "delivery_messages_preview": delivery_messages,
        "delivery_chunk_count": len(delivery_messages),
        "send_result": send_result,
        "source_artifacts": {
            "digest": rel(digest_path),
            "state": rel(state_path),
        },
        "authority": AUTHORITY,
        "authority_clean": authority_clean(AUTHORITY),
        "boundary": BOUNDARY,
    }
    if args.write or True:
        atomic_write_json(output, result)
    print(json.dumps({
        "status": status,
        "mode": mode,
        "message_kind": kind,
        "sent_count": sent_count,
        "blockers": blockers,
        "output": rel(output),
    }, indent=2, sort_keys=True))
    return 0 if status in {"SENT", "DRY_RUN_READY", "NO_REPLY", "BLOCKED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
