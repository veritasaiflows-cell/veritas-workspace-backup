#!/usr/bin/env python3
"""WF68 Telegram notifier.

Reads WF68 runtime/router artifacts and sends a narrow Telegram alert when the
delivery router reports EXECUTION_PACKET_READY or when runtime proof is blocked.

This is a delivery wrapper only. It does not create/submit/cancel paper orders,
touch Alpaca, mutate portfolio/canon state, infer approval, or make live-account
changes.
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

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_RUNTIME_JSON = OUT_DIR / "runtime-handoff-status.json"
DEFAULT_ROUTER_JSON = OUT_DIR / "delivery-router-status.json"
DEFAULT_STATE_JSON = OUT_DIR / "telegram-notifier-state.json"
DEFAULT_OUTPUT_JSON = OUT_DIR / "telegram-notifier-status.json"
DEFAULT_OUTPUT_MD = OUT_DIR / "telegram-notifier-status.md"
DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"

AUTHORITY = {
    "posture": "telegram_delivery_shadow_pilot",
    "telegram_delivery_allowed": True,
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
    "Telegram delivery only. Reply REVIEW or PREPARE. APPROVE is not active in "
    "the shadow pilot. No paper/live order, brokerage/account action, money "
    "movement, portfolio/canon mutation, or owner approval inference is authorized."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
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


def authority_clean(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, bool) and child is True:
                if any(token in lowered for token in ("trade", "order", "account", "broker", "money", "portfolio", "canonical", "approval", "mutation")):
                    if "telegram_delivery_allowed" != lowered:
                        return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def compact_terms(item: dict[str, Any]) -> str:
    terms = item.get("recommended_order_terms") if isinstance(item.get("recommended_order_terms"), dict) else {}
    ticker = str(item.get("ticker") or terms.get("symbol") or "UNKNOWN").upper()
    side = str(terms.get("side") or "buy").upper()
    qty = terms.get("qty")
    limit_price = terms.get("limit_price")
    tif = terms.get("time_in_force") or "day"
    stop = terms.get("stop_reference")
    packet = item.get("packet_md") or item.get("packet_json") or ""
    qty_text = f"{float(qty):g}" if isinstance(qty, (int, float)) else "missing_qty"
    limit_text = f"${float(limit_price):.2f}" if isinstance(limit_price, (int, float)) else "missing_limit"
    stop_text = f"${float(stop):.2f}" if isinstance(stop, (int, float)) else "missing_stop"
    return f"{ticker}: {side} {qty_text} limit/{tif} @ {limit_text}; stop {stop_text}; proof {packet}"


def message_key(router: dict[str, Any], runtime: dict[str, Any], kind: str) -> str:
    generated = parse_utc(router.get("generated_at_utc") or runtime.get("generated_at_utc"))
    day = generated.date().isoformat() if generated else datetime.now(timezone.utc).date().isoformat()
    items = router.get("immediate_execution_recommendations") if isinstance(router.get("immediate_execution_recommendations"), list) else []
    if kind == "execution":
        tickers = sorted(str(item.get("ticker") or "").upper() for item in items)
        raw = json.dumps({"kind": kind, "day": day, "tickers": tickers}, sort_keys=True)
    else:
        raw = json.dumps({
            "kind": kind,
            "day": day,
            "runtime_status": runtime.get("status"),
            "handoff_status": runtime.get("handoff_status"),
            "failure_reason": runtime.get("failure_reason"),
            "validation_bad": runtime.get("validation_bad"),
        }, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def artifact_age_minutes(router: dict[str, Any], runtime: dict[str, Any]) -> float | None:
    stamp = parse_utc(router.get("generated_at_utc")) or parse_utc(runtime.get("generated_at_utc"))
    if stamp is None:
        return None
    return (datetime.now(timezone.utc) - stamp).total_seconds() / 60


def build_message(router: dict[str, Any], runtime: dict[str, Any]) -> tuple[str, str] | tuple[None, str]:
    runtime_status = runtime.get("status")
    router_status = router.get("status")
    handoff_status = runtime.get("handoff_status")
    validation_bad = runtime.get("validation_bad") if isinstance(runtime.get("validation_bad"), list) else []
    authority_ok = bool(runtime.get("authority_clean")) and bool(router.get("authority_clean", True)) and authority_clean(router.get("authority", {}))

    if runtime_status not in {"ok", "warning"} or validation_bad or not authority_ok:
        text = (
            "WF68 VALIDATION/BLOCKER ALERT\n"
            f"Runtime status: {runtime_status}\n"
            f"Handoff: {handoff_status}\n"
            f"Router: {router_status}\n"
            f"Failure: {runtime.get('failure_reason') or 'none'}\n"
            f"Validation bad: {', '.join(validation_bad) if validation_bad else 'none'}\n"
            f"Proof: {rel(DEFAULT_RUNTIME_JSON)}\n\n"
            f"{BOUNDARY}"
        )
        return text, "blocker"

    if router_status != "EXECUTION_PACKET_READY" and handoff_status != "EXECUTION_PACKET_READY":
        return None, "no_reply"

    items = router.get("immediate_execution_recommendations") if isinstance(router.get("immediate_execution_recommendations"), list) else []
    if not items:
        return None, "no_immediate_recommendations"

    lines = [
        "WF68 PAPER-READY ALERT (SHADOW PILOT)",
        f"Immediate packets: {len(items)}",
        "",
    ]
    for item in items[:4]:
        lines.append(compact_terms(item))
    if len(items) > 4:
        lines.append(f"...plus {len(items) - 4} more packet(s).")
    lines.extend([
        "",
        "Reply REVIEW to inspect, or PREPARE to create a WF67 paper request artifact.",
        "APPROVE is not active in shadow mode.",
        "Live trading blocked. Paper execution requires exact approval, WF67 guard validation, fresh kill switch, paper wrapper, and audit log.",
        f"Router proof: {rel(DEFAULT_ROUTER_JSON)}",
    ])
    return "\n".join(lines), "execution"


def build_delivery_test_message(generated_at_utc: str) -> str:
    return (
        "WF68 TELEGRAM DELIVERY TEST ONLY\n"
        f"Generated UTC: {generated_at_utc}\n"
        "Purpose: confirm OpenClaw CLI delivery to Randall Telegram target.\n"
        "No market signal. No paper-ready packet. No PREPARE action required.\n\n"
        f"{BOUNDARY}"
    )


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


def render_md(result: dict[str, Any]) -> str:
    lines = [
        "# WF68 Telegram Notifier Status",
        "",
        f"- Generated UTC: `{result['generated_at_utc']}`",
        f"- Status: **{result['status']}**",
        f"- Mode: `{result['mode']}`",
        f"- Message kind: `{result.get('message_kind')}`",
        f"- Sent count: `{result.get('sent_count', 0)}`",
        f"- Dedupe key: `{result.get('dedupe_key') or ''}`",
        f"- Artifact age minutes: `{result.get('artifact_age_minutes')}`",
        "",
        "## Boundary",
        "",
        BOUNDARY,
    ]
    if result.get("message_preview"):
        lines.extend(["", "## Message Preview", "", "```text", result["message_preview"], "```"])
    if result.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in result["blockers"])
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send narrow WF68 Telegram alert notifications.")
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME_JSON)
    parser.add_argument("--router", type=Path, default=DEFAULT_ROUTER_JSON)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--max-age-minutes", type=int, default=45)
    parser.add_argument("--send", action="store_true", help="Actually send the Telegram message. Default is dry-run proof only.")
    parser.add_argument("--force", action="store_true", help="Ignore dedupe state for this run.")
    parser.add_argument("--delivery-test", action="store_true", help="Send or preview a clearly labeled Telegram delivery test without reading WF68 market artifacts.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at_utc = utc_now()
    runtime_path = args.runtime if args.runtime.is_absolute() else ROOT / args.runtime
    router_path = args.router if args.router.is_absolute() else ROOT / args.router
    state_path = args.state if args.state.is_absolute() else ROOT / args.state
    output_json = args.output_json if args.output_json.is_absolute() else ROOT / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else ROOT / args.output_md

    state = load_json(state_path, {"sent_keys": {}})
    blockers: list[str] = []

    if args.delivery_test:
        runtime: dict[str, Any] = {}
        router: dict[str, Any] = {}
        message = build_delivery_test_message(generated_at_utc)
        message_kind = "delivery_test"
        age = 0.0
        raw_key = json.dumps(
            {
                "kind": message_kind,
                "generated_minute_utc": generated_at_utc[:16],
                "channel": args.channel,
                "target": args.target,
            },
            sort_keys=True,
        )
        key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]
    else:
        runtime = load_json(runtime_path, {})
        router = load_json(router_path, {})

        if not isinstance(runtime, dict) or not runtime:
            blockers.append("runtime_artifact_missing_or_invalid")
            runtime = {}
        if not isinstance(router, dict) or not router:
            blockers.append("router_artifact_missing_or_invalid")
            router = {}

        message, message_kind = build_message(router, runtime) if not blockers else (None, "artifact_blocker")
        age = artifact_age_minutes(router, runtime)
        if message and age is not None and age > args.max_age_minutes:
            blockers.append(f"artifact_stale:{age:.1f}min_gt_{args.max_age_minutes}min")
        if message and age is None:
            blockers.append("artifact_generated_at_missing")

        key = message_key(router, runtime, message_kind) if message else None
    sent_keys = state.get("sent_keys") if isinstance(state.get("sent_keys"), dict) else {}
    duplicate = bool(key and key in sent_keys and not args.force)
    if duplicate:
        blockers.append("dedupe_key_already_sent")

    send_result: dict[str, Any] | None = None
    sent_count = 0
    mode = "send" if args.send else "dry_run"
    status = "NO_REPLY"

    if message and not blockers:
        if args.send:
            send_result = send_telegram(args.channel, args.target, message, args.timeout_seconds)
            if send_result["ok"]:
                sent_count = 1
                status = "SENT"
                sent_keys[key] = {"sent_at_utc": utc_now(), "message_kind": message_kind}
                state["sent_keys"] = sent_keys
                write_json(state_path, state)
            else:
                status = "SEND_FAILED"
                blockers.append("openclaw_message_send_failed")
        else:
            status = "DRY_RUN_READY"
    elif message and blockers:
        status = "BLOCKED"

    result = {
        "schema_version": "wf68.telegram_notifier_status.v1",
        "workflow": "WF68",
        "generated_at_utc": generated_at_utc,
        "status": status,
        "mode": mode,
        "channel": args.channel,
        "target": args.target,
        "message_kind": message_kind,
        "dedupe_key": key,
        "duplicate": duplicate,
        "artifact_age_minutes": round(age, 2) if age is not None else None,
        "sent_count": sent_count,
        "blockers": blockers,
        "message_preview": message,
        "send_result": send_result,
        "source_artifacts": {
            "runtime": rel(runtime_path),
            "router": rel(router_path),
            "state": rel(state_path),
        },
        "authority": AUTHORITY,
        "authority_clean": authority_clean(AUTHORITY),
        "boundary": BOUNDARY,
    }
    write_json(output_json, result)
    output_md.write_text(render_md(result), encoding="utf-8")
    print(json.dumps({
        "status": status,
        "mode": mode,
        "message_kind": message_kind,
        "sent_count": sent_count,
        "blockers": blockers,
        "output_json": rel(output_json),
    }, indent=2, sort_keys=True))
    return 0 if status in {"SENT", "DRY_RUN_READY", "NO_REPLY", "BLOCKED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
