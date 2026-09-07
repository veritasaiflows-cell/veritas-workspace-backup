#!/usr/bin/env python3
"""Review-only surfacing + Telegram delivery for the capital-recommendation slate.

Renders the full reviewed capital-deployment recommendation slate from
`current-capital-deployment-recommendations.json` INCLUDING `no_new_approval`
rows, so a morning where the verdict is "reviewed, no new adds" still surfaces
to Randall instead of collapsing to "nothing".

- `--render` prints the readable multi-line slate (on-demand answer surface).
- `--send` delivers a flattened, dedupe-guarded digest to Telegram.

Delivery only. Never approves, applies, or executes anything.
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

DEFAULT_BUNDLE = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_STATE = TMP / "capital-recommendation-slate-telegram-state.json"
DEFAULT_OUTPUT = TMP / "capital-recommendation-slate-notifier.json"
DEFAULT_MD = TMP / "capital-recommendation-slate.md"
DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"
PHX_TZ = ZoneInfo("America/Phoenix")

AUTHORITY = {
    "posture": "telegram_delivery_review_only_capital_recommendation_slate",
    "telegram_delivery_allowed": True,
    "review_packet_generation_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "per_packet_owner_approval_inferred": False,
    "owner_approval_inferred": False,
}

BOUNDARY = (
    "Review-only: this is the morning recommendation review, not an approval. "
    "No trade, account, paper, or capital action is authorized or inferred. "
    "Owner decision required on every name."
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


def close_vs_band_pct(row: dict[str, Any]) -> float | None:
    """Truthful position of close relative to the DISPLAYED current band edges.

    Positive = above band high; negative = below band low; 0.0 = inside band.
    """
    close = row.get("close")
    low = row.get("band_low")
    high = row.get("band_high")
    if not (isinstance(close, float) and isinstance(low, float) and isinstance(high, float)):
        return None
    if close > high and high:
        return round((close - high) / high * 100, 1)
    if close < low and low:
        return round((close - low) / low * 100, 1)
    return 0.0


def summarize(bundle: dict[str, Any]) -> dict[str, Any]:
    proposals = [p for p in as_list(bundle.get("proposals")) if isinstance(p, dict)]
    rows: list[dict[str, Any]] = []
    for p in proposals:
        current = as_dict(p.get("current_state"))
        technical = as_dict(p.get("technical_gate"))
        why = as_dict(p.get("why_stack")) or as_dict(p.get("decision_rationale"))
        proposed = as_dict(p.get("proposed_state"))
        rows.append({
            "ticker": p.get("ticker") or p.get("ticker_or_scope") or "UNKNOWN",
            "review_state": current.get("daily_review_state") or current.get("deployment_state"),
            "posture": proposed.get("recommendation_posture"),
            "band_status": technical.get("entry_band_status") or technical.get("band_status"),
            "distance_to_band_pct": _num(technical.get("distance_to_band_pct")),
            "close": _num(technical.get("close")),
            "band_low": _num(technical.get("current_band_low")),
            "band_high": _num(technical.get("current_band_high")),
            "band_source": technical.get("band_source"),
            "band_status_note": technical.get("band_status_note"),
            "stop": _num(technical.get("stop_or_invalidation")),
            "entry_reason": why.get("entry_reason") or why.get("setup_reason"),
            "owner_decision_required": bool(p.get("owner_decision_required")),
        })

    for row in rows:
        row["close_vs_band_pct"] = close_vs_band_pct(row)

    def sort_key(row: dict[str, Any]) -> tuple[int, float]:
        dist = row.get("close_vs_band_pct")
        return (0, abs(dist)) if isinstance(dist, float) else (1, 0.0)

    rows.sort(key=sort_key)
    new_adds = [r for r in rows if r.get("posture") not in (None, "no_new_approval")]
    return {
        "window": bundle.get("window"),
        "generated_at_utc": bundle.get("generated_at_utc"),
        "reviewed_count": len(rows),
        "new_add_count": len(new_adds),
        "all_no_new_approval": len(rows) > 0 and len(new_adds) == 0,
        "rows": rows,
    }


def render_lines(summary: dict[str, Any]) -> list[str]:
    window = str(summary.get("window") or "unspecified")
    reviewed = summary.get("reviewed_count") or 0
    new_adds = summary.get("new_add_count") or 0
    lines = [
        f"BAND ALERT REVIEW ({window})",
        f"Watched: {reviewed} | At alert level: {new_adds}"
        + (" | All names review-only" if summary.get("all_no_new_approval") else ""),
        "",
    ]
    if summary.get("all_no_new_approval"):
        lines.append("Verdict: nothing at an actionable alert level. All names are setup/watch.")
    else:
        lines.append("Verdict: at least one name carries a non-default posture — see below.")
    lines.append("")
    lines.append("Watchlist (closest-to-band first):")
    for r in summary.get("rows", []):
        close = f"{r['close']:.2f}" if isinstance(r.get("close"), float) else "n/a"
        band = (
            f"{r['band_low']:.2f}-{r['band_high']:.2f}"
            if isinstance(r.get("band_low"), float) and isinstance(r.get("band_high"), float)
            else "band n/a"
        )
        pos = r.get("close_vs_band_pct")
        if isinstance(pos, float):
            pos_txt = "in-band" if pos == 0.0 else (f"{pos:+.1f}% vs band" if pos else "at edge")
        else:
            pos_txt = "pos n/a"
        stop = f"stop {r['stop']:.2f}" if isinstance(r.get("stop"), float) else "stop n/a"
        posture = r.get("posture") or "n/a"
        line = (
            f"- {r['ticker']}: {r.get('review_state') or 'n/a'}, {r.get('band_status') or 'n/a'} "
            f"(close {close} {pos_txt}; band {band}), {stop} [{posture}]"
        )
        lines.append(line)
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
    return [f"Capital Recommendation Review part {i}/{total}: {c}" for i, c in enumerate(chunks, start=1)]


def dedupe_key(summary: dict[str, Any], window: str) -> str | None:
    generated = parse_utc(summary.get("generated_at_utc"))
    if generated is None:
        return None
    raw = json.dumps(
        {
            "day": generated.date().isoformat(),
            "window": window,
            "reviewed": summary.get("reviewed_count"),
            "new_adds": summary.get("new_add_count"),
            "tickers": [r.get("ticker") for r in summary.get("rows", [])],
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--window", default=None, help="Override dedupe window label; defaults to bundle window.")
    parser.add_argument("--max-age-minutes", type=int, default=1440)
    parser.add_argument("--render", action="store_true", help="Print the readable slate (on-demand surface).")
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
    bundle_path = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
    state_path = args.state if args.state.is_absolute() else ROOT / args.state
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output

    bundle = load_json(bundle_path, {})
    blockers: list[str] = []
    if not isinstance(bundle, dict) or not bundle:
        blockers.append("bundle_missing_or_invalid")
        bundle = {}
    if not authority_clean(AUTHORITY):
        blockers.append("notifier_authority_drift")

    summary = summarize(bundle)
    window = str(args.window or summary.get("window") or "unspecified").strip().lower() or "unspecified"
    slate_text = "\n".join(render_lines(summary))

    if args.render:
        print(slate_text)

    age = age_minutes(summary.get("generated_at_utc"))
    if age is None:
        blockers.append("bundle_generated_at_missing")
    elif age > args.max_age_minutes:
        blockers.append(f"bundle_stale:{age}min_gt_{args.max_age_minutes}min")

    now_phx = datetime.now(timezone.utc).astimezone(PHX_TZ)
    weekday = now_phx.weekday() < 5
    weekday_gate_blocked = args.weekday_only and not weekday
    if weekday_gate_blocked:
        blockers.append("weekday_only_gate_off_hours")

    key = dedupe_key(summary, window)
    state = load_json(state_path, {"sent_keys": {}})
    sent_keys = state.get("sent_keys") if isinstance(state.get("sent_keys"), dict) else {}
    duplicate = bool(key and key in sent_keys and not args.force)
    if duplicate:
        blockers.append("dedupe_key_already_sent")

    non_dedupe_hard = [b for b in blockers if b not in {"dedupe_key_already_sent", "weekday_only_gate_off_hours"}]

    delivery_messages = telegram_safe_messages(slate_text)
    mode = "send" if args.send else "dry_run"
    status = "DRY_RUN_READY"
    sent_count = 0
    send_result: dict[str, Any] | None = None

    if non_dedupe_hard:
        status = "BLOCKED"
    elif duplicate or weekday_gate_blocked:
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
        "schema": "veritas.capital_recommendation_slate_notifier.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": mode,
        "channel": args.channel,
        "target": args.target,
        "window": window,
        "dedupe_key": key,
        "duplicate": duplicate,
        "weekday_gate_blocked": weekday_gate_blocked,
        "bundle_age_minutes": age,
        "sent_count": sent_count,
        "blockers": blockers,
        "summary": {k: v for k, v in summary.items() if k != "rows"},
        "reviewed_slate": summary.get("rows"),
        "slate_text": slate_text,
        "delivery_messages_preview": delivery_messages,
        "send_result": send_result,
        "source_artifacts": {"bundle": rel(bundle_path), "state": rel(state_path)},
        "authority": AUTHORITY,
        "authority_clean": authority_clean(AUTHORITY),
        "boundary": BOUNDARY,
    }

    if args.write:
        atomic_write_json(output, result)
    if args.write_md:
        atomic_write_text(md_output, slate_text + "\n")

    if not args.render:
        print(json.dumps({
            "status": status,
            "mode": mode,
            "reviewed_count": summary.get("reviewed_count"),
            "new_add_count": summary.get("new_add_count"),
            "sent_count": sent_count,
            "blockers": blockers,
            "output": rel(output),
        }, indent=2, sort_keys=True))

    if args.validate and status in {"BLOCKED", "SEND_FAILED"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
