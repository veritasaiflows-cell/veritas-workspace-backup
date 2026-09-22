#!/usr/bin/env python3
"""Run the bounded review-only earnings evidence refresh for cron."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "earnings-evidence-cron-runner.json"
TRACKED_SCOPE = 31

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "declared_commands_only": True,
    "watchlist_closeout_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "alert_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}


class Step(NamedTuple):
    name: str
    args: tuple[str, ...]
    artifact: Path | None
    timeout_seconds: int = 600


STEPS = (
    Step("earnings_calendar", ("scripts\\earnings_calendar_enrichment.py",), TMP / "earnings-calendar.json"),
    Step("earnings_date_confidence", ("scripts\\earnings_date_source_confidence.py",), TMP / "earnings-date-source-confidence.json"),
    Step(
        "earnings_rollforward_guard",
        (
            "scripts\\earnings_rollforward_guard.py",
            "--all-tracked",
            "--auto-capture",
            "--write",
            "--validate",
        ),
        TMP / "earnings-rollforward-guard.json",
    ),
    Step("official_capture_validation", ("scripts\\official_ir_capture_validator.py", "--all", "--write"), None),
    Step("official_capture_registry", ("scripts\\official_capture_period_registry.py", "--write"), TMP / "wf70-official-capture-period-registry.json"),
    Step("fundamental_ir_reconciliation", ("scripts\\fundamental_ir_reconciliation_packets.py", "--write"), TMP / "fundamental-ir-reconciliation-packets.json"),
    Step("fundamental_ir_validation", ("scripts\\validate_fundamental_ir_reconciliation.py", "--write"), TMP / "fundamental-ir-reconciliation-validation.json"),
    Step("official_earnings_bridge", ("scripts\\official_earnings_bridge.py", "--write"), TMP / "official-earnings-bridge.json"),
    Step("official_earnings_bridge_validation", ("scripts\\validate_official_earnings_bridge.py", "--write"), TMP / "official-earnings-bridge-validation.json"),
    Step("post_earnings_prep", ("scripts\\post_earnings_prep.py",), TMP / "post-earnings-prep.json"),
    Step("post_earnings_note_targets", ("scripts\\post_earnings_note_targets.py",), TMP / "post-earnings-note-targets.json"),
)

HARD_STATUSES = {"blocked", "critical", "error", "fail", "failed", "invalid"}
WARNING_STATUSES = {"manual_confirmed_partial", "partial", "warning"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def run_step(step: Step) -> dict[str, Any]:
    started = utc_now()
    command = [sys.executable, *step.args]
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=step.timeout_seconds,
            check=False,
        )
        return {
            "name": step.name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": (completed.stdout or "")[-1200:],
            "stderr_tail": (completed.stderr or "")[-800:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": step.name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "error": "step_timeout",
            "stdout_tail": (exc.stdout or "")[-1200:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-800:] if isinstance(exc.stderr, str) else "",
        }


def read_artifact(step: Step, run_started: datetime) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    if step.artifact is None:
        return None, [], []
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(step.artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"artifact_unreadable:{step.name}:{type(exc).__name__}"], []
    if not isinstance(payload, dict):
        return None, [f"artifact_not_object:{step.name}"], []

    generated = parse_utc(payload.get("generated_at_utc"))
    if generated is None or generated < run_started:
        errors.append(f"artifact_not_regenerated:{step.name}")
    status = str(payload.get("status") or "unknown").strip().lower()
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    validation_status = str(validation.get("status") or "").strip().lower()
    if status in HARD_STATUSES or validation_status in HARD_STATUSES:
        errors.append(f"artifact_hard_status:{step.name}:{status or validation_status}")
    elif status in WARNING_STATUSES or validation_status in WARNING_STATUSES:
        warnings.append(f"artifact_warning_status:{step.name}:{status or validation_status}")
    return payload, errors, warnings


def semantic_errors(artifacts: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    calendar = artifacts.get("earnings_calendar") or {}
    if len(calendar.get("records") or []) < TRACKED_SCOPE:
        errors.append("earnings_calendar_scope_below_31")

    guard = artifacts.get("earnings_rollforward_guard") or {}
    guard_scope = guard.get("scope") if isinstance(guard.get("scope"), dict) else {}
    if int(guard_scope.get("tracked_ticker_count") or 0) != TRACKED_SCOPE:
        errors.append("earnings_rollforward_scope_not_31")

    registry = artifacts.get("official_capture_registry") or {}
    registry_summary = registry.get("summary") if isinstance(registry.get("summary"), dict) else {}
    if int(registry_summary.get("tickers") or 0) != TRACKED_SCOPE:
        errors.append("official_capture_registry_scope_not_31")

    packets = artifacts.get("fundamental_ir_reconciliation") or {}
    packet_summary = packets.get("summary") if isinstance(packets.get("summary"), dict) else {}
    if int(packet_summary.get("packets") or 0) != TRACKED_SCOPE:
        errors.append("fundamental_reconciliation_scope_not_31")

    bridge = artifacts.get("official_earnings_bridge") or {}
    bridge_summary = bridge.get("summary") if isinstance(bridge.get("summary"), dict) else {}
    if int(bridge_summary.get("bridges") or 0) != TRACKED_SCOPE:
        errors.append("official_earnings_bridge_scope_not_31")
    return errors


def build_packet(*, dry_run: bool = False) -> dict[str, Any]:
    started_at_utc = utc_now()
    started_at = parse_utc(started_at_utc) or datetime.now(timezone.utc)
    steps: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[str] = []

    if dry_run:
        return {
            "schema": "veritas.earnings_evidence_cron_runner.v1",
            "generated_at_utc": utc_now(),
            "status": "dry_run",
            "review_only": True,
            "tracked_scope": TRACKED_SCOPE,
            "commands": [[sys.executable, *step.args] for step in STEPS],
            "authority_boundary": AUTHORITY_BOUNDARY,
        }

    for step in STEPS:
        record = run_step(step)
        steps.append(record)
        if not record["ok"]:
            errors.append(f"step_failed:{step.name}")
            break
        artifact, artifact_errors, artifact_warnings = read_artifact(step, started_at)
        if artifact is not None:
            artifacts[step.name] = artifact
        errors.extend(artifact_errors)
        warnings.extend(artifact_warnings)
        if artifact_errors:
            break

    if not errors:
        errors.extend(semantic_errors(artifacts))
    status = "blocked" if errors else "warning" if warnings else "ok"
    return {
        "schema": "veritas.earnings_evidence_cron_runner.v1",
        "generated_at_utc": utc_now(),
        "started_at_utc": started_at_utc,
        "status": status,
        "review_only": True,
        "tracked_scope": TRACKED_SCOPE,
        "summary": {
            "declared_steps": len(STEPS),
            "executed_steps": len(steps),
            "failed_steps": [step["name"] for step in steps if not step["ok"]],
            "near_earnings_warning_count": len((artifacts.get("post_earnings_prep") or {}).get("near_earnings_warning_queue") or []),
            "post_earnings_reconciliation_count": len((artifacts.get("post_earnings_prep") or {}).get("post_earnings_reconciliation_queue") or []),
        },
        "errors": errors,
        "warnings": warnings,
        "steps": steps,
        "artifacts": {
            step.name: {
                "path": rel(step.artifact),
                "status": (artifacts.get(step.name) or {}).get("status"),
                "generated_at_utc": (artifacts.get(step.name) or {}).get("generated_at_utc"),
            }
            for step in STEPS
            if step.artifact is not None
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the review-only earnings evidence cron chain.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    packet = build_packet(dry_run=args.dry_run)
    if args.write and not args.dry_run:
        atomic_write_json(OUT, packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 2 if args.validate and packet.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
