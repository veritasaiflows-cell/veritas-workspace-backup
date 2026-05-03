from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"

STATUS_ORDER = {"ok": 0, "warning": 1, "blocked": 2, "error": 3}
FRESHNESS_ORDER = {"ok": 0, "usable_with_caution": 1, "partial": 2, "stale": 3, "missing": 4}

WINDOW_OWNER = "scripts/run_finance_refresh_chain.py"
WINDOW_ENTRYPOINTS = {
    "morning": "python scripts/run_finance_refresh_chain.py morning",
    "post-close": "python scripts/run_finance_refresh_chain.py post-close",
    "post-earnings": "python scripts/run_finance_refresh_chain.py post-earnings",
    "sunday": "python scripts/run_finance_refresh_chain.py sunday",
}
WINDOW_REQUIRED_OUTPUTS: dict[str, dict[str, dict[str, Any]]] = {
    "morning": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "premarket_snapshot": {"path": TMP / "premarket-snapshot.json", "kind": "json"},
    },
    "post-close": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "post_earnings_prep": {"path": TMP / "post-earnings-prep.json", "kind": "json"},
        "post_earnings_note_targets": {"path": TMP / "post-earnings-note-targets.json", "kind": "json"},
        "postmarket_snapshot": {"path": TMP / "postmarket-snapshot.json", "kind": "json"},
        "daily_executive_brief": {"path": TMP / "daily-executive-brief.json", "kind": "json"},
    },
    "post-earnings": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "post_earnings_prep": {"path": TMP / "post-earnings-prep.json", "kind": "json"},
        "post_earnings_note_targets": {"path": TMP / "post-earnings-note-targets.json", "kind": "json"},
    },
    "sunday": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "weekly_macro_snapshot": {"path": TMP / "weekly-macro-snapshot.json", "kind": "json"},
        "weekly_intelligence_brief": {"path": TMP / "weekly-intelligence-brief.json", "kind": "json"},
        "postmarket_snapshot": {"path": TMP / "postmarket-snapshot.json", "kind": "json"},
        "daily_executive_brief": {"path": TMP / "daily-executive-brief.json", "kind": "json"},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write machine-readable run summary for a workflow window.")
    parser.add_argument("--window", required=True, choices=sorted(WINDOW_REQUIRED_OUTPUTS.keys()))
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else None


def chain_state_path(window: str) -> Path:
    return TMP / f"run-chain-{window}.json"


def load_chain_execution(window: str) -> dict[str, Any] | None:
    data = read_json(chain_state_path(window))
    return data if isinstance(data, dict) else None


def file_generated_at(path: Path, data: dict[str, Any] | None = None) -> str:
    if data:
        for key in ("generated_at_utc", "generated_at"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                if key == "generated_at_utc":
                    return value
                return value.replace(" UTC", "Z") if value.endswith(" UTC") else value
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def output_status(path: Path, kind: str, attempt_started_at: datetime | None = None) -> tuple[str, dict[str, Any] | None, str]:
    if not path.exists():
        return "missing", None, ""
    if kind == "file":
        data: dict[str, Any] | None = None
        status = "ok"
    else:
        data = read_json(path)
        if data is None:
            return "failed", None, file_generated_at(path)
        status_value = str(data.get("status") or data.get("overall_status") or data.get("overall") or "").strip().lower()
        if status_value in {"partial", "warning", "usable_with_caution", "stale"}:
            status = "partial"
        elif status_value in {"error", "failed", "critical", "missing", "blocked"}:
            status = "failed"
        else:
            status = "ok"

    generated_at = file_generated_at(path, data)
    generated_dt = parse_iso(generated_at)
    if attempt_started_at and generated_dt and generated_dt < attempt_started_at:
        return "stale", data, generated_at
    return status, data, generated_at


def current_exec_freshness() -> str:
    dashboard_data = read_json(TMP / "dashboard-data.json")
    freshness = str((dashboard_data or {}).get("exec_freshness") or "").strip().lower()
    return freshness if freshness in FRESHNESS_ORDER else "missing"


def detect_fallbacks(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return []
    reasons: list[str] = []
    for warning in validation.get("warnings", []):
        code = warning.get("code")
        if code in {
            "macro_manual_dependency",
            "policy_expectations_fallback_source",
            "policy_expectations_manual_dependency",
            "timing_sensitive_earnings_dates",
        }:
            reasons.append(warning.get("message", code))
    return reasons


def failed_steps(chain_execution: dict[str, Any] | None) -> list[dict[str, Any]]:
    steps = (chain_execution or {}).get("steps") or []
    return [step for step in steps if step.get("status") == "failed"]


def skipped_steps(chain_execution: dict[str, Any] | None) -> list[dict[str, Any]]:
    steps = (chain_execution or {}).get("steps") or []
    return [step for step in steps if step.get("status") == "skipped_after_failure"]


def normalized_chain_status(chain_execution: dict[str, Any] | None) -> tuple[str, str, bool]:
    raw_status = str((chain_execution or {}).get("status") or "unknown")
    steps = (chain_execution or {}).get("steps") or []
    recovery = (chain_execution or {}).get("recovery") or {}
    if raw_status in {"ok", "failed", "completed_with_recovery", "unknown"}:
        return raw_status, "runtime status already terminal", False

    running_steps = [step for step in steps if step.get("status") == "running"]
    pending_steps = [step for step in steps if step.get("status") == "pending"]
    blocking_unfinished = [
        step
        for step in steps
        if step.get("status") not in {"ok", "failed", "skipped_after_failure", "running", "pending"}
    ]

    if (
        len(running_steps) == 1
        and not blocking_unfinished
        and str(running_steps[0].get("script") or "") == "run_summary_refresh.py"
    ):
        pending_scripts = {str(step.get("script") or "") for step in pending_steps}
        allowed_pending_tail = {"dashboard_run_summary_consumer.py", "deployment_readiness_surface.py", "tmp_cleanup.py"}
        if pending_scripts and not pending_scripts.issubset(allowed_pending_tail):
            return raw_status, "runtime state not safe to normalize", False
        if bool(recovery.get("triggered")):
            return "completed_with_recovery", "normalized from finalizer self-observation during run_summary_refresh.py before post-summary tail steps", True
        return "ok", "normalized from finalizer self-observation during run_summary_refresh.py before post-summary tail steps", True

    return raw_status, "runtime state not safe to normalize", False


def determine_status(
    outputs: dict[str, dict[str, Any]],
    acceptance: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    chain_execution: dict[str, Any] | None,
) -> tuple[str, bool, list[str]]:
    blockers: list[str] = []

    chain_failures = failed_steps(chain_execution)
    if chain_failures:
        step = chain_failures[0]
        blockers.append(
            f"Finance refresh chain failed at {step.get('script', 'unknown step')}"
            f" (exit code {step.get('exit_code', 'unknown')})"
        )

    stale_or_missing_required = [name for name, info in outputs.items() if info["status"] in {"missing", "failed", "stale"}]
    if stale_or_missing_required:
        blockers.append("Missing, stale, or failed required outputs: " + ", ".join(stale_or_missing_required))

    acceptance_passed = bool((acceptance or {}).get("summary", {}).get("all_passed"))
    if acceptance is not None and not acceptance_passed:
        blockers.append("Dashboard acceptance did not fully pass")

    critical_count = int(((validation or {}).get("summary") or {}).get("critical", 0) or 0)
    if critical_count > 0:
        blockers.append(f"Dashboard validation surfaced {critical_count} critical issue(s)")

    if blockers:
        return "blocked", True, blockers

    warning_count = int(((validation or {}).get("summary") or {}).get("warning", 0) or 0)
    fallbacks = detect_fallbacks(validation)
    if warning_count > 0 or fallbacks:
        return "warning", False, []
    return "ok", False, []


def canonical_note_mutation_allowed(status: str, stop_line: bool, validation: dict[str, Any] | None) -> tuple[bool, str]:
    if stop_line or status in {"blocked", "error"}:
        return False, f"run summary status={status}"
    return False, "scheduled windows remain fail-closed for canonical note mutation in v1"


def build_run_summary(window: str) -> dict[str, Any]:
    validation_path = TMP / "dashboard-validation.json"
    acceptance_path = TMP / "dashboard-acceptance-report.json"
    workbook_manifest_path = TMP / "workbook-export-manifest.json"

    validation = read_json(validation_path)
    acceptance = read_json(acceptance_path)
    workbook_manifest = read_json(workbook_manifest_path)
    chain_execution = load_chain_execution(window)
    attempt_started_at = parse_iso((chain_execution or {}).get("started_at_utc"))
    attempt_completed_at = parse_iso((chain_execution or {}).get("completed_at_utc"))

    outputs: dict[str, dict[str, Any]] = {}
    timestamps: list[datetime] = []
    for name, spec in WINDOW_REQUIRED_OUTPUTS[window].items():
        path = spec["path"]
        status, data, generated_at = output_status(path, spec["kind"], attempt_started_at=attempt_started_at)
        generated_dt = parse_iso(generated_at)
        if generated_dt and (attempt_started_at is None or generated_dt >= attempt_started_at):
            timestamps.append(generated_dt)
        outputs[name] = {
            "status": status,
            "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
            "generated_at_utc": generated_at,
        }

    status, stop_line, blockers = determine_status(outputs, acceptance, validation, chain_execution)
    warnings = [w.get("message", "") for w in (validation or {}).get("warnings", []) if w.get("message")]
    fallback_reasons = detect_fallbacks(validation)

    generated_at = utc_now_iso()
    if attempt_started_at:
        started_dt = attempt_started_at.replace(microsecond=0)
        if attempt_completed_at:
            completed_dt = attempt_completed_at.replace(microsecond=0)
        elif timestamps:
            completed_dt = max(timestamps).replace(microsecond=0)
        else:
            completed_dt = started_dt
    elif timestamps:
        started_dt = min(timestamps).replace(microsecond=0)
        completed_dt = max(timestamps).replace(microsecond=0)
    else:
        completed_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        started_dt = completed_dt
    duration_seconds = max(0, int((completed_dt - started_dt).total_seconds()))

    validation_summary = (validation or {}).get("summary") or {}
    overall_validation = str((validation or {}).get("overall") or status)
    workbook_status = status if status in {"blocked", "error"} else str((workbook_manifest or {}).get("overall_status") or status)
    downstream_badge = "bad" if status in {"blocked", "error"} else ("warn" if status == "warning" else "ok")
    recovery = (chain_execution or {}).get("recovery") or {}
    failed_step = recovery.get("failed_step") or (failed_steps(chain_execution)[0] if failed_steps(chain_execution) else None)
    chain_status, chain_status_reason, chain_status_normalized = normalized_chain_status(chain_execution)

    note_mutation_allowed, note_mutation_reason = canonical_note_mutation_allowed(status, stop_line, validation)

    presentation_allowed = False

    return {
        "window": window,
        "run_id": f"{generated_at.replace(':', '').replace('-', '')}_{window}",
        "generated_at_utc": generated_at,
        "status": status,
        "stop_line": stop_line,
        "owner": {
            "entrypoint": WINDOW_ENTRYPOINTS[window],
            "window_owner": WINDOW_OWNER,
        },
        "timing": {
            "started_at_utc": started_dt.isoformat().replace("+00:00", "Z"),
            "completed_at_utc": completed_dt.isoformat().replace("+00:00", "Z"),
            "duration_seconds": duration_seconds,
        },
        "execution": {
            "chain_status": chain_status,
            "chain_status_raw": str((chain_execution or {}).get("status") or "unknown"),
            "chain_status_normalized": chain_status_normalized,
            "chain_status_reason": chain_status_reason,
            "chain_exit_code": (chain_execution or {}).get("exit_code"),
            "recovery_triggered": bool(recovery.get("triggered")),
            "recovery_reason": str(recovery.get("reason") or ""),
            "failed_step": failed_step,
            "skipped_steps": [step.get("script") for step in skipped_steps(chain_execution)],
            "finalized_after_failure": bool(recovery.get("triggered")),
        },
        "validation": {
            "acceptance_passed": bool((acceptance or {}).get("summary", {}).get("all_passed")),
            "dashboard_validation_status": overall_validation,
            "critical": int(validation_summary.get("critical", 0) or 0),
            "warning": int(validation_summary.get("warning", 0) or 0),
            "info": int(validation_summary.get("info", 0) or 0),
            "exec_freshness": current_exec_freshness(),
        },
        "outputs": outputs,
        "warnings": warnings,
        "blockers": blockers,
        "fallback_state": {
            "used": bool(fallback_reasons),
            "reason": "; ".join(fallback_reasons),
        },
        "downstream": {
            "command_center_badge": downstream_badge,
            "workbook_trust_grade": workbook_status,
            "presentation_allowed": presentation_allowed,
            "canonical_note_mutation_allowed": note_mutation_allowed,
            "canonical_note_mutation_reason": note_mutation_reason,
        },
    }


def main() -> int:
    args = parse_args()
    summary = build_run_summary(args.window)
    out_path = TMP / f"run-summary-{args.window}.json"
    atomic_write_json(out_path, summary)
    print(json.dumps({"status": "ok", "window": args.window, "out": str(out_path), "summary_status": summary["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
