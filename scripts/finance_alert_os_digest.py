#!/usr/bin/env python3
"""Render or deliver a review-only finance alert/recommendation digest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PHOENIX = ZoneInfo("America/Phoenix")
LEVELS = TMP / "alert-level-freshness-controller.json"
GUARD = TMP / "alert-reference-baseline-freshness-guard.json"
DEFAULT_OUT = TMP / "finance-alert-os-digest.json"
DEFAULT_TARGET = "8650152206"
DEFAULT_MAX_CONTROLLER_AGE_HOURS = 6.0
GUARD_MAX_AGE_HOURS = 36.0
CLOCK_SKEW_TOLERANCE_HOURS = 0.25

AUTHORITY = {
    "review_only": True,
    "alerts_and_non_executing_recommendations_only": True,
    "writes_finance_canon": False,
    "maintains_portfolio_state": False,
    "maintains_simulated_account_state": False,
    "capital_or_order_authority": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

BOUNDARY = (
    "Review-only alert and recommendation context. Randall decides; no capital, "
    "order, account, money-movement, or execution action is authorized."
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def controller_age_hours(levels: dict[str, Any], reference: datetime) -> float | None:
    raw = str(levels.get("generated_at_utc") or "").strip()
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (reference - stamp).total_seconds() / 3600.0


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def compact(values: Any, limit: int = 6) -> str:
    items = [str(value).upper() for value in as_list(values) if str(value).strip()]
    if not items:
        return "none"
    shown = ", ".join(items[:limit])
    return shown if len(items) <= limit else f"{shown} (+{len(items) - limit})"


def controller_semantic_errors(levels: dict[str, Any]) -> list[str]:
    summary = as_dict(levels.get("summary"))
    eligible = {
        str(value).upper()
        for value in as_list(summary.get("fresh_intraday_signal_eligible_tickers"))
        if str(value).strip()
    }
    emitted = {
        str(value).upper()
        for key in ("band_entry_signal_tickers", "invalidation_signal_tickers", "no_chase_signal_tickers")
        for value in as_list(summary.get(key))
        if str(value).strip()
    }
    errors: list[str] = []
    if emitted and not eligible:
        errors.append("controller emits alerts without fresh-intraday eligibility proof")
    unexpected = sorted(emitted - eligible)
    if unexpected:
        errors.append("controller emits ineligible alert tickers: " + ", ".join(unexpected))
    return errors


def baseline_guard_line() -> str | None:
    """Name the baseline canon cause when the freshness guard is not healthy.

    Silent when the guard is ok, fresh, and every check passes; otherwise a
    single prepended line so the digest distinguishes cause from symptom.
    """
    guard = load_json(GUARD)
    if not guard:
        return "BASELINE: WARNING - freshness guard proof missing; baseline canon unverified"
    parts: list[str] = []
    for check in as_list(guard.get("checks")):
        entry = as_dict(check)
        if entry.get("status") not in (None, "ok"):
            parts.append(f"{entry.get('name', 'check')}: {entry.get('message', 'not ok')}")
    age_hours = controller_age_hours(guard, datetime.now(timezone.utc))
    if age_hours is None:
        parts.append("guard proof has no usable generated_at_utc stamp")
    elif age_hours > GUARD_MAX_AGE_HOURS:
        parts.append(f"guard proof stale: {age_hours:.1f}h old exceeds {GUARD_MAX_AGE_HOURS:.1f}h")
    status = str(guard.get("status") or "").lower()
    if status == "ok" and not parts:
        return None
    label = "CRITICAL" if status == "critical" or as_list(guard.get("critical_checks")) else "WARNING"
    detail = "; ".join(parts) or str(guard.get("headline") or "see tmp/alert-reference-baseline-freshness-guard.json")
    return f"BASELINE: {label} - {detail}"


def build_message(mode: str, levels: dict[str, Any]) -> str:
    summary = as_dict(levels.get("summary"))
    counts = as_dict(summary.get("alert_state_counts"))
    label = mode.replace("-", " ").upper()
    quote_stamps = [str(value) for value in as_list(summary.get("quote_as_of_utc_values")) if str(value).strip()]
    quote_dates = [str(value) for value in as_list(summary.get("quote_session_dates")) if str(value).strip()]
    monitor_only = as_list(summary.get("monitor_only_tickers"))
    lines = [
        f"FINANCE ALERTS & RECOMMENDATIONS - {label}",
        f"Band-entry alerts: {compact(summary.get('band_entry_signal_tickers'))}",
        f"Invalidation alerts: {compact(summary.get('invalidation_signal_tickers'))}",
        f"No-chase alerts: {compact(summary.get('no_chase_signal_tickers'))}",
        f"Monitor-only: {compact(monitor_only)}",
        f"Freshness review: {compact(summary.get('freshness_review_tickers'))}",
        "Alert states: " + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"),
        f"Quote session date: {', '.join(quote_dates) or 'unknown'}",
        f"Quote evidence as of: {max(quote_stamps) if quote_stamps else 'unknown'}",
        f"Controller generated: {levels.get('generated_at_utc') or 'unknown'}",
        BOUNDARY,
    ]
    guard_line = baseline_guard_line()
    if guard_line:
        lines.insert(1, guard_line)
    if monitor_only:
        lines.insert(
            -1,
            "Fresh intraday alert firing is suppressed; last-completed-session evidence is review-only.",
        )
    return "\n".join(lines)


def resolve_openclaw() -> str:
    return shutil.which("openclaw") or shutil.which("openclaw.cmd") or "openclaw"


def _candidate_entry_points() -> list[Path]:
    """Bounded existing-install entry checks; no broad scans, no shim evaluation."""
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None:
            return
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    for shim in ("openclaw", "openclaw.cmd", "agent-cli", "agent-cli.cmd"):
        try:
            found = shutil.which(shim)
        except Exception:
            found = None
        if found:
            try:
                parent = Path(found).resolve().parent
            except OSError:
                parent = Path(found).parent
            add(parent / "node_modules" / "openclaw" / "openclaw.mjs")
    try:
        add(Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "openclaw" / "openclaw.mjs")
    except Exception:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        try:
            add(Path(appdata) / "npm" / "node_modules" / "openclaw" / "openclaw.mjs")
        except Exception:
            pass
    return candidates[:6]


_BATCH_NODE_SUFFIXES = (".cmd", ".bat", ".ps1", ".com")


def _is_safe_node(path: str | None) -> bool:
    """Reject batch-shim Node so multiline argv cannot fall back to .cmd/.bat."""
    if not path or not isinstance(path, str):
        return False
    lowered = path.lower()
    if lowered.endswith(_BATCH_NODE_SUFFIXES):
        return False
    base = lowered.replace("/", "\\").rsplit("\\", 1)[-1]
    if base in ("node.cmd", "node.bat", "node.ps1", "node.com"):
        return False
    return True


def _windows_node_entry() -> tuple[str, str] | None:
    """Resolve (node, entry_mjs) using only existing install layout; None = fail closed."""
    try:
        node = shutil.which("node")
    except Exception:
        node = None
    if not _is_safe_node(node):
        return None
    for candidate in _candidate_entry_points():
        try:
            if candidate.is_file():
                return (node, str(candidate))
        except OSError:
            continue
    return None


def _is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def resolve_launch_argv(target: str, message: str) -> tuple[list[str] | None, str]:
    """Select a safe argv; Windows avoids .cmd/.bat so multiline argv is preserved.

    Returns (argv_or_None, strategy). None means fail closed; caller must not send.
    """
    if _is_windows():
        resolved = _windows_node_entry()
        if resolved is None:
            return (None, "windows-node-entry-missing")
        node, entry = resolved
        return (
            [node, entry, "message", "send", "--channel", "telegram", "--target", target, "--message", message],
            "windows-node-direct",
        )
    return (
        [resolve_openclaw(), "message", "send", "--channel", "telegram", "--target", target, "--message", message],
        "direct-posix",
    )


def transport_meta(message: str, strategy: str) -> dict[str, Any]:
    encoded = message.encode("utf-8")
    return {
        "strategy": strategy,
        "message_sha256": hashlib.sha256(encoded).hexdigest(),
        "message_bytes": len(encoded),
        "message_lines": message.count("\n") + 1 if message else 0,
    }


def deliver(target: str, message: str, timeout_seconds: int) -> dict[str, Any]:
    """Launch the CLI without shell; transport ok never implies recipient readback."""
    argv, strategy = resolve_launch_argv(target, message)
    meta = transport_meta(message, strategy)
    if argv is None:
        return {
            "ok": False,
            "returncode": None,
            "stderr_tail": "",
            "strategy": strategy,
            "transport": meta,
            "error": "safe-launch-unresolved",
        }
    try:
        run = subprocess.run(
            argv,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": None,
            "stderr_tail": "",
            "strategy": strategy,
            "transport": meta,
            "error": "timeout",
        }
    except (FileNotFoundError, OSError) as exc:
        return {
            "ok": False,
            "returncode": None,
            "stderr_tail": "",
            "strategy": strategy,
            "transport": meta,
            "error": type(exc).__name__,
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "stderr_tail": "",
            "strategy": strategy,
            "transport": meta,
            "error": type(exc).__name__,
        }
    if run.returncode != 0:
        return {
            "ok": False,
            "returncode": run.returncode,
            "stderr_tail": "",
            "strategy": strategy,
            "transport": meta,
            "error": "nonzero-exit",
        }
    return {
        "ok": True,
        "returncode": 0,
        "stderr_tail": "",
        "strategy": strategy,
        "transport": meta,
    }


def build_payload(
    mode: str,
    *,
    generated_at_utc: str | None = None,
    max_controller_age_hours: float = DEFAULT_MAX_CONTROLLER_AGE_HOURS,
) -> dict[str, Any]:
    generated = generated_at_utc or now_utc()
    levels = load_json(LEVELS)
    errors: list[str] = []
    warnings: list[str] = []
    # The controller is written to a fixed path by the alerts chain. When that
    # chain fails fast upstream the previous run's proof survives untouched, so
    # structural validity alone cannot distinguish current from yesterday.
    age_hours = controller_age_hours(levels, datetime.now(timezone.utc)) if levels else None
    if not levels:
        errors.append("alert-level freshness proof is missing")
    elif levels.get("status") != "ok" or as_dict(levels.get("validation")).get("status") != "ok":
        errors.append("alert-level freshness proof failed structural validation")
    elif age_hours is None:
        errors.append("alert-level freshness proof has no usable generated_at_utc stamp")
    elif age_hours < -CLOCK_SKEW_TOLERANCE_HOURS:
        errors.append(
            f"alert-level freshness proof is stamped {abs(age_hours):.1f}h in the future"
        )
    elif age_hours > max_controller_age_hours:
        errors.append(
            f"alert-level freshness proof is stale: {age_hours:.1f}h old "
            f"exceeds the {max_controller_age_hours:.1f}h limit"
        )
    else:
        errors.extend(controller_semantic_errors(levels))
    controller_sha256 = hashlib.sha256(LEVELS.read_bytes()).hexdigest() if LEVELS.is_file() else None
    guard = load_json(GUARD)
    message = build_message(mode, levels) if not errors else None
    status = "blocked" if errors else "ok"
    return {
        "schema": "veritas.finance_alert_os_digest.v2",
        "generated_at_utc": generated,
        "mode": mode,
        "status": status,
        "message_preview": message,
        "authority": dict(AUTHORITY),
        "boundary": BOUNDARY,
        "source_artifacts": {
            "alert_levels": {
                "path": "tmp/alert-level-freshness-controller.json",
                "sha256": controller_sha256,
                "generated_at_utc": levels.get("generated_at_utc"),
                "age_hours": round(age_hours, 3) if age_hours is not None else None,
                "max_age_hours": max_controller_age_hours,
            },
            "baseline_guard": {
                "path": "tmp/alert-reference-baseline-freshness-guard.json",
                "status": guard.get("status"),
                "generated_at_utc": guard.get("generated_at_utc"),
                "surfaced_in_message": bool(message and message.split("\n")[1].startswith("BASELINE:")) if message else False,
            },
        },
        "summary": as_dict(levels.get("summary")),
        "validation": {"status": status, "errors": errors, "warnings": warnings},
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["recommendations", "morning", "midday", "post-close", "weekly"], required=True)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--weekday-only", action="store_true")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument(
        "--max-controller-age-hours",
        type=float,
        default=DEFAULT_MAX_CONTROLLER_AGE_HOURS,
        help="Block delivery when the alert-level freshness proof is older than this.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    output = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(args.mode, max_controller_age_hours=args.max_controller_age_hours)
    local_now = datetime.now(PHOENIX)
    if args.weekday_only and local_now.weekday() >= 5 and payload["status"] == "ok":
        payload["status"] = "weekend_quiet"

    state_path = TMP / "finance-alert-os-digest-state.json"
    state = load_json(state_path)
    sent_keys = as_dict(state.get("sent_keys"))
    message = str(payload.get("message_preview") or "")
    digest_key = hashlib.sha256(
        json.dumps({"date": local_now.date().isoformat(), "mode": args.mode, "message": message}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    payload["digest_key"] = digest_key

    if args.send and payload["status"] == "ok":
        if digest_key in sent_keys:
            payload["status"] = "duplicate_quiet"
        else:
            result = deliver(args.target, message, args.timeout_seconds)
            payload["delivery"] = result
            unconfirmed = (not result["ok"]) and result.get("error") == "timeout"
            payload["status"] = "sent" if result["ok"] else "send_unconfirmed" if unconfirmed else "send_failed"
            if result["ok"] or unconfirmed:
                sent_keys[digest_key] = {"sent_at_utc": payload["generated_at_utc"], "mode": args.mode, "confirmed": bool(result["ok"])}
                write_json(state_path, {"sent_keys": sent_keys})
            if unconfirmed:
                payload["validation"]["warnings"].append("delivery_unconfirmed_transport_timeout")

    if args.write:
        write_json(output, payload)
        mode_output = TMP / f"finance-alert-os-{args.mode}-digest.json"
        if mode_output != output:
            write_json(mode_output, payload)
        if args.write_md:
            output.with_suffix(".md").write_text(
                f"# Finance Alerts and Recommendations - {args.mode.title()}\n\n```text\n{message or 'Blocked'}\n```\n",
                encoding="utf-8",
            )

    acceptable = {"ok", "weekend_quiet", "duplicate_quiet", "sent", "send_unconfirmed"}
    print(json.dumps({
        "status": payload["status"],
        "mode": args.mode,
        "output": output.relative_to(ROOT).as_posix(),
        "warnings": payload["validation"]["warnings"],
    }, indent=2))
    return 1 if args.validate and payload["status"] not in acceptable else 0


if __name__ == "__main__":
    raise SystemExit(main())
