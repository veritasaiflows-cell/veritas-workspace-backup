#!/usr/bin/env python3
"""Review-only Telegram delivery for the P2 disciplined-band staleness alert.

Reads the review-only staleness artifact produced by ``daily_review_objects.py``
(via ``disciplined_band_gate.build_staleness_alert_payload``) and delivers a
compact, dedupe-guarded digest to Randall's Telegram:

- Auto-dropped names (no-chase: price > 8% above the disciplined band high).
- Stale disciplined bands (age > 30d OR price > 2 ATR from the disciplined
  midpoint) that need an owner-set band refresh.

Delivery only. Never approves, applies, mutates canon/portfolio, or executes.
The underlying gate stays review-only; this only surfaces its proof to Telegram.
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

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_ALERT = TMP / "disciplined-band-staleness-alerts.json"
DEFAULT_STATE = TMP / "disciplined-band-staleness-telegram-state.json"
DEFAULT_OUTPUT = TMP / "disciplined-band-staleness-notifier.json"
DEFAULT_MD = TMP / "disciplined-band-staleness.md"
DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"
PHX_TZ = ZoneInfo("America/Phoenix")

AUTHORITY = {
    "posture": "telegram_delivery_review_only_disciplined_band_staleness_alert",
    "telegram_delivery_allowed": True,
    "review_packet_generation_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "owner_approval_inferred": False,
}

BOUNDARY = (
    "Review-only: disciplined-band staleness/no-chase surfacing, not an approval. "
    "No trade, account, paper, or capital action is authorized or inferred. "
    "Owner should re-set stale disciplined bands; owner decision required on every name."
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
        "capital", "trade", "execution", "order", "submit", "cancel", "sell",
        "account", "brokerage", "money", "portfolio", "canonical", "approval", "mutation",
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


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def stale_reason(alert: dict[str, Any]) -> str:
    staleness = as_dict(alert.get("staleness"))
    parts: list[str] = []
    age = staleness.get("band_age_days")
    max_age = staleness.get("max_age_days") or 30
    if isinstance(age, (int, float)) and age > max_age:
        parts.append(f"age {int(age)}d")
    atr_dist = staleness.get("atr_distance_from_midpoint")
    atr_mult = staleness.get("atr_mult") or 2.0
    if isinstance(atr_dist, (int, float)) and atr_dist > atr_mult:
        parts.append(f"{atr_dist:g} ATR")
    if alert.get("band_state") == "BACKFILLED":
        parts.append("backfilled placeholder")
    return ", ".join(parts) if parts else "stale"


def summarize(alert_payload: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(alert_payload.get("summary"))
    alerts = [a for a in as_list(alert_payload.get("alerts")) if isinstance(a, dict)]

    extended_rows: list[dict[str, Any]] = []
    stale_rows: list[dict[str, Any]] = []
    for a in alerts:
        extension = as_dict(a.get("extension"))
        staleness = as_dict(a.get("staleness"))
        ticker = a.get("ticker") or "UNKNOWN"
        if extension.get("auto_drop"):
            extended_rows.append({
                "ticker": ticker,
                "extension_pct": _num(extension.get("extension_pct_above_high")),
                "disciplined_band_high": _num(a.get("disciplined_band_high")),
                "price": _num(a.get("price")),
            })
        if staleness.get("stale"):
            stale_rows.append({
                "ticker": ticker,
                "reason": stale_reason(a),
                "band_state": a.get("band_state"),
            })

    extended_rows.sort(key=lambda r: (r["extension_pct"] is None, -(r["extension_pct"] or 0.0)))
    stale_rows.sort(key=lambda r: r["ticker"])

    return {
        "window": alert_payload.get("window"),
        "as_of": alert_payload.get("as_of"),
        "generated_at_utc": alert_payload.get("generated_at_utc"),
        "disciplined_band_count": summary.get("disciplined_band_count") or len(alerts),
        "backfilled_band_count": summary.get("backfilled_band_count"),
        "stale_count": summary.get("stale_count", len(stale_rows)),
        "extended_auto_drop_count": summary.get("extended_auto_drop_count", len(extended_rows)),
        "extended_rows": extended_rows,
        "stale_rows": stale_rows,
    }


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def render_lines(summary: dict[str, Any]) -> list[str]:
    window = str(summary.get("window") or "unspecified")
    total = summary.get("disciplined_band_count") or 0
    stale = summary.get("stale_count") or 0
    extended = summary.get("extended_auto_drop_count") or 0
    lines = [
        f"DISCIPLINED BAND STALENESS ALERT ({window})",
        f"{total} disciplined bands | {stale} stale | {extended} auto-dropped (no-chase >8% above disciplined high)",
    ]

    extended_rows = summary.get("extended_rows") or []
    if extended_rows:
        lines.append("")
        parts = []
        for r in extended_rows:
            pct = r.get("extension_pct")
            parts.append(f"{r['ticker']} +{pct:.1f}%" if isinstance(pct, float) else f"{r['ticker']}")
        lines.append("Auto-dropped to watch (no-chase, price extended above disciplined high): " + ", ".join(parts))

    stale_rows = summary.get("stale_rows") or []
    if stale_rows:
        lines.append("")
        lines.append("Stale disciplined bands need owner re-set (age > 30d OR > 2 ATR from midpoint):")
        for group in _chunk(stale_rows, 10):
            lines.append("")
            lines.append(", ".join(f"{r['ticker']} ({r['reason']})" for r in group))
    else:
        lines.append("")
        lines.append("No stale disciplined bands and no auto-drops this window.")

    lines.append("")
    lines.append(BOUNDARY)
    return lines


def flatten_section(section: str) -> str:
    return " | ".join(line.strip() for line in section.splitlines() if line.strip())


def telegram_safe_messages(text: str, max_chars: int = 2800) -> list[str]:
    sections = [flatten_section(s) for s in text.strip().split("\n\n")]
    sections = [s for s in sections if s]
    chunks: list[str] = []
    current = ""
    for section in sections:
        if not current:
            current = section
        elif len(current) + 4 + len(section) <= max_chars:
            current = f"{current} || {section}"
        else:
            chunks.append(current)
            current = section
    if current:
        chunks.append(current)
    total = len(chunks)
    return [f"Disciplined Band Staleness part {i}/{total}: {c}" for i, c in enumerate(chunks, start=1)]


def dedupe_key(summary: dict[str, Any], window: str) -> str | None:
    generated = parse_utc(summary.get("generated_at_utc"))
    if generated is None:
        return None
    raw = json.dumps(
        {
            "day": generated.date().isoformat(),
            "window": window,
            "stale": summary.get("stale_count"),
            "extended": summary.get("extended_auto_drop_count"),
            "stale_tickers": [r.get("ticker") for r in summary.get("stale_rows", [])],
            "extended_tickers": [r.get("ticker") for r in summary.get("extended_rows", [])],
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert", type=Path, default=DEFAULT_ALERT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--window", default=None, help="Override dedupe window label; defaults to alert window.")
    parser.add_argument("--max-age-minutes", type=int, default=1440)
    parser.add_argument("--render", action="store_true", help="Print the readable digest (on-demand surface).")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--weekday-only", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    alert_path = args.alert if args.alert.is_absolute() else ROOT / args.alert
    state_path = args.state if args.state.is_absolute() else ROOT / args.state
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output

    payload = load_json(alert_path, {})
    blockers: list[str] = []
    if not isinstance(payload, dict) or not payload:
        blockers.append("staleness_alert_missing_or_invalid")
        payload = {}
    if not authority_clean(AUTHORITY):
        blockers.append("notifier_authority_drift")

    summary = summarize(payload)
    window = str(args.window or summary.get("window") or "unspecified").strip().lower() or "unspecified"
    digest_text = "\n".join(render_lines(summary))

    if args.render:
        print(digest_text)

    age = age_minutes(summary.get("generated_at_utc"))
    if age is None:
        blockers.append("staleness_generated_at_missing")
    elif age > args.max_age_minutes:
        blockers.append(f"staleness_stale:{age}min_gt_{args.max_age_minutes}min")

    now_phx = datetime.now(timezone.utc).astimezone(PHX_TZ)
    weekday = now_phx.weekday() < 5
    weekday_gate_blocked = args.weekday_only and not weekday
    if weekday_gate_blocked:
        blockers.append("weekday_only_gate_off_hours")

    nothing_to_alert = (summary.get("stale_count") or 0) == 0 and (summary.get("extended_auto_drop_count") or 0) == 0

    key = dedupe_key(summary, window)
    state = load_json(state_path, {"sent_keys": {}})
    sent_keys = state.get("sent_keys") if isinstance(state.get("sent_keys"), dict) else {}
    duplicate = bool(key and key in sent_keys and not args.force)
    if duplicate:
        blockers.append("dedupe_key_already_sent")

    non_dedupe_hard = [
        b for b in blockers
        if b not in {"dedupe_key_already_sent", "weekday_only_gate_off_hours"}
    ]

    delivery_messages = telegram_safe_messages(digest_text)
    mode = "send" if args.send else "dry_run"
    status = "DRY_RUN_READY"
    sent_count = 0
    send_result: dict[str, Any] | None = None

    if non_dedupe_hard:
        status = "BLOCKED"
    elif duplicate or weekday_gate_blocked or nothing_to_alert:
        status = "NO_REPLY"
    elif args.send:
        chunk_results = [send_telegram(args.channel, args.target, item, args.timeout_seconds) for item in delivery_messages]
        send_result = {
            "chunk_count": len(chunk_results),
            "chunks": chunk_results,
            "ok": bool(chunk_results) and all(item.get("ok") for item in chunk_results),
        }
        if send_result.get("ok"):
            sent_count = len(chunk_results)
            status = "SENT"
            sent_keys[key] = {"sent_at_utc": utc_now(), "window": window}
            state["sent_keys"] = sent_keys
            atomic_write_json(state_path, state)
        else:
            status = "SEND_FAILED"
            blockers.append("openclaw_message_send_failed")

    result = {
        "schema": "veritas.disciplined_band_staleness_notifier.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": mode,
        "channel": args.channel,
        "target": args.target,
        "window": window,
        "dedupe_key": key,
        "duplicate": duplicate,
        "weekday_gate_blocked": weekday_gate_blocked,
        "nothing_to_alert": nothing_to_alert,
        "alert_age_minutes": age,
        "sent_count": sent_count,
        "blockers": blockers,
        "summary": {k: v for k, v in summary.items() if k not in ("extended_rows", "stale_rows")},
        "extended_rows": summary.get("extended_rows"),
        "stale_rows": summary.get("stale_rows"),
        "digest_text": digest_text,
        "delivery_messages_preview": delivery_messages,
        "send_result": send_result,
        "source_artifacts": {"alert": rel(alert_path), "state": rel(state_path)},
        "authority": AUTHORITY,
        "authority_clean": authority_clean(AUTHORITY),
        "boundary": BOUNDARY,
    }

    if args.write:
        atomic_write_json(output, result)
    if args.write_md:
        atomic_write_text(md_output, digest_text + "\n")

    if not args.render:
        print(json.dumps({
            "status": status,
            "mode": mode,
            "stale_count": summary.get("stale_count"),
            "extended_auto_drop_count": summary.get("extended_auto_drop_count"),
            "sent_count": sent_count,
            "blockers": blockers,
            "output": rel(output),
        }, indent=2, sort_keys=True))

    if args.validate and status in {"BLOCKED", "SEND_FAILED"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
