#!/usr/bin/env python3
"""Consolidated control digest runner for cron reduction Phase 1."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.cron_runner_guardrails import (
    artifact_record,
    build_runner_payload,
    print_status,
    py_cmd,
    run_step,
    write_payload,
)

OUT = Path("tmp/cron-control-digest-runner.json")
ROOT = Path(__file__).resolve().parents[1]
# Reuse is only for duplicate/back-to-back invocations.  Scheduled control
# windows are seven or more hours apart and must always gather fresh evidence.
# Reused packets are never rewritten, so this TTL cannot renew itself.
PREFILTER_MAX_AGE_HOURS = 0.25
WINDOW_OUTS = {
    "control": Path("tmp/cron-control-digest-runner-control.json"),
    "morning": Path("tmp/cron-control-digest-runner-morning.json"),
    "post-close": Path("tmp/cron-control-digest-runner-post-close.json"),
    "all": OUT,
}

SOURCE_JOBS = [
    "Cron - Main Session Auto-Green Watchdog",
    "Operating Leverage - Escalation Trigger Check",
    "Finance - Morning Control Digest Proof Refresh",
    "Finance - Post-Close Control Digest Consolidated Handoff",
    "Finance - Layered Morning Advancement Audit",
    "Finance - Layered Post-Close Advancement Audit",
]
NON_BLOCKING_CONTRACT_VALIDATOR_WARNINGS = {"cron_prompt_bloat_present"}


def build_steps(window: str, deep: bool) -> list[tuple[str, list[str], int]]:
    steps: list[tuple[str, list[str], int]] = [
        ("cron_contract_validator", py_cmd("scripts\\cron_contract_validator.py", "--require-contracts", "--fail-on-drift", "--write", "--validate"), 180),
        ("cron_operator_ledger", py_cmd("scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"), 180),
        ("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180),
        ("pm_control_packet", py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 240),
        ("escalation_trigger", py_cmd("scripts\\escalation_trigger.py", "--write", "--validate"), 180),
        ("main_session_greenkeeper_controller", py_cmd("scripts\\main_session_greenkeeper_controller.py", "--refresh-frontdoors", "--write", "--validate", "--append-ledger"), 240),
    ]
    if window in {"morning", "all"}:
        steps.append(("morning_control_digest", py_cmd("scripts\\morning_control_digest.py", "--write", "--write-md", "--validate"), 240))
    if window in {"post-close", "all"}:
        steps.append(("post_close_control_digest", py_cmd("scripts\\post_close_control_digest.py", "--write", "--write-md", "--validate"), 240))
    if deep:
        steps.append(("changed_file_validator_router", py_cmd("scripts\\changed_file_validator_router.py", "--write", "--validate"), 120))
    return steps


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(value: Any, now: datetime | None = None) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - parsed).total_seconds() / 3600


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    full = path if path.is_absolute() else ROOT / path
    if not full.exists():
        return {}
    try:
        payload = json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def source_file_state(label: str, path: Path) -> dict[str, Any]:
    full = path if path.is_absolute() else ROOT / path
    return {
        "label": label,
        "path": rel(full),
        "exists": full.exists(),
        "sha256": sha256_file(full),
    }


def build_input_signature(window: str, deep: bool) -> dict[str, Any]:
    steps = build_steps(window, deep)
    source_paths = [
        Path(__file__).resolve(),
        ROOT / "scripts" / "lib" / "cron_runner_guardrails.py",
        ROOT / "state" / "cron-contracts" / "cron-reduction-control-fail-closed-dispatcher.json",
    ]
    for _name, command, _timeout in steps:
        if len(command) >= 2 and str(command[1]).startswith("scripts\\"):
            source_paths.append(ROOT / str(command[1]))
    sources = [source_file_state(f"source:{index}", path) for index, path in enumerate(source_paths)]
    command_fingerprint = {
        "window": window,
        "deep": deep,
        "steps": [{"name": name, "command": command, "timeout": timeout} for name, command, timeout in steps],
    }
    body = json.dumps({"sources": sources, "commands": command_fingerprint}, sort_keys=True, separators=(",", ":"))
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "source_count": len(sources),
        "sources": sources,
        "command_fingerprint": command_fingerprint,
    }


def prefilter_decision(out: Path, current_signature: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    previous = load_json(out)
    previous_signature = previous.get("input_signature") if isinstance(previous.get("input_signature"), dict) else {}
    previous_validation = previous.get("validation") if isinstance(previous.get("validation"), dict) else {}
    previous_age = age_hours(previous.get("generated_at_utc"), now)
    source_unchanged = bool(previous_signature.get("hash") and previous_signature.get("hash") == current_signature.get("hash"))
    previous_ok = previous.get("status") == "ok" and previous_validation.get("status") == "ok"
    previous_fresh = previous_age is not None and previous_age <= PREFILTER_MAX_AGE_HOURS
    can_reuse = source_unchanged and previous_ok and previous_fresh
    if not previous:
        reason = "missing_previous_packet"
    elif not previous_signature.get("hash"):
        reason = "missing_previous_input_signature"
    elif not source_unchanged:
        reason = "source_signature_changed"
    elif not previous_ok:
        reason = "previous_packet_not_ok"
    elif not previous_fresh:
        reason = "previous_packet_not_fresh"
    else:
        reason = "unchanged_inputs_and_fresh_control_digest"
    return {
        "status": "reuse_existing_packet" if can_reuse else "refresh_required",
        "can_reuse_existing_packet": can_reuse,
        "reason": reason,
        "source_unchanged": source_unchanged,
        "previous_packet_exists": bool(previous),
        "previous_generated_at_utc": previous.get("generated_at_utc"),
        "previous_age_hours": round(previous_age, 3) if previous_age is not None else None,
        "max_age_hours": PREFILTER_MAX_AGE_HOURS,
        "previous_status": previous.get("status"),
        "previous_validation_status": previous_validation.get("status"),
        "previous_input_hash": previous_signature.get("hash"),
        "current_input_hash": current_signature.get("hash"),
    }


def reuse_existing_payload(out: Path, prefilter: dict[str, Any]) -> dict[str, Any]:
    """Return prior proof for status output without renewing its evidence time.

    The persisted runner packet is an evidence surface.  Rewriting it during a
    skip would make cached evidence appear freshly gathered and could allow a
    succession of skips to mask dynamic scheduler/control degradation.  Keep
    the prior packet byte-for-byte unchanged and expose the skip only in the
    current process output.
    """
    previous = load_json(out)
    payload = dict(previous)
    payload["runtime_reuse_check"] = {
        "mode": "nonrenewing_duplicate_invocation_skip",
        "checked_at_utc": utc_now(),
        "evidence_generated_at_utc": previous.get("generated_at_utc"),
        "reason": prefilter.get("reason"),
        "max_age_hours": PREFILTER_MAX_AGE_HOURS,
        "persisted_packet_rewritten": False,
    }
    return payload


def output_path_for_window(window: str, requested_out: Path | None) -> Path:
    if requested_out is not None:
        return requested_out
    return WINDOW_OUTS.get(window, OUT)


def artifact_plan(window: str) -> list[dict[str, Any]]:
    artifacts = [
        contract_validator_artifact_record(),
        artifact_record(
            "cron_operator_ledger",
            "tmp/cron-operator-ledger.json",
            max_age_hours=24,
            allowed_statuses={"ok", "warning", "blocked"},
        ),
        artifact_record("cron_control_packet", "tmp/cron-control-packet.json", max_age_hours=24),
        artifact_record("pm_control_packet", "tmp/pm-control-packet.json", max_age_hours=24),
        artifact_record("escalation_trigger", "tmp/escalation-trigger.json", max_age_hours=24),
        artifact_record("main_session_greenkeeper", "tmp/main-session-greenkeeper-controller.json", max_age_hours=24),
    ]
    domain_blocker_statuses = {"ok", "warning", "blocked", "critical"}
    if window in {"morning", "all"}:
        artifacts.append(
            artifact_record(
                "morning_control_digest",
                "tmp/morning-control-digest.json",
                max_age_hours=36,
                allowed_statuses=domain_blocker_statuses,
            )
        )
    if window in {"post-close", "all"}:
        artifacts.append(
            artifact_record(
                "post_close_control_digest",
                "tmp/post-close-control-digest.json",
                max_age_hours=36,
                allowed_statuses=domain_blocker_statuses,
            )
        )
    return artifacts


def contract_validator_artifact_record(path: Path = Path("tmp/cron-contract-validator.json")) -> dict[str, Any]:
    record = artifact_record(
        "cron_contract_validator",
        path,
        max_age_hours=24,
        allowed_statuses={"ok", "warning"},
    )
    if record["status"] != "warning":
        return record

    warnings = load_json(path).get("validation", {}).get("warnings", [])
    warning_codes = {str(item) for item in warnings if isinstance(item, str)}
    if warning_codes and warning_codes.issubset(NON_BLOCKING_CONTRACT_VALIDATOR_WARNINGS):
        record["accepted_warning_codes"] = sorted(warning_codes)
        return record

    record["ok"] = False
    record["unaccepted_warning_codes"] = sorted(warning_codes)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", choices=["control", "morning", "post-close", "all"], default="control")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass the changed-input prefilter and rerun all control steps.")
    parser.add_argument("--prefilter-only", action="store_true", help="Report whether the existing control digest can be reused.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out = output_path_for_window(args.window, args.out)

    input_signature = build_input_signature(args.window, args.deep)
    prefilter = prefilter_decision(out, input_signature)
    if args.prefilter_only:
        print(f"status={prefilter['status']} can_reuse={prefilter['can_reuse_existing_packet']} reason={prefilter['reason']} input_hash={prefilter['current_input_hash']}")
        return 0
    if not args.force_refresh and prefilter.get("can_reuse_existing_packet"):
        payload = reuse_existing_payload(out, prefilter)
        print_status(payload)
        return 0

    steps = [run_step(name, command, timeout) for name, command, timeout in build_steps(args.window, args.deep)]
    artifacts = artifact_plan(args.window)

    payload = build_runner_payload(
        runner="cron_control_digest_runner",
        phase="phase1",
        target_seconds=120 if args.window == "control" else 240,
        hard_timeout_seconds=600,
        model_posture="Mini-safe command wrapper; local scripts own sequencing.",
        source_jobs=SOURCE_JOBS,
        steps=steps,
        artifacts=artifacts,
        extra={
            "window": args.window,
            "deep": args.deep,
            "replacement_intent": "Replace duplicate control proof and handoff jobs after shadow proof is clean.",
            "input_signature": input_signature,
            "prefilter": prefilter,
        },
    )
    payload["input_signature"] = input_signature
    payload["prefilter"] = prefilter
    write_payload(out, payload, write=args.write, write_md=args.write_md)
    print_status(payload)
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
