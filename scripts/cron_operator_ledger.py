from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CRON_STORE = WORKSPACE.parent / "cron" / "jobs.json"
OUT_JSON = TMP / "cron-operator-ledger.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA_VERSION = 1
GATEWAY_CRON_COMMAND = ("openclaw", "cron", "list", "--all", "--json", "--timeout", "30000")

WINDOWS = ("morning", "post-close", "post-earnings", "sunday")

AUTHORITY = {
    "posture": "json_first_cron_operator_ledger",
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_external_delivery_allowed": False,
    "paper_trade_submit_cancel_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def cron_jobs_from_store() -> list[dict[str, Any]]:
    data = load_json(CRON_STORE)
    if isinstance(data, dict):
        for key in ("jobs", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if all(isinstance(value, dict) for value in data.values()):
            return [value for value in data.values() if isinstance(value, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def cron_jobs_from_gateway() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    executable = shutil.which(GATEWAY_CRON_COMMAND[0])
    if not executable:
        return [], {"available": False, "error": "openclaw_cli_not_found"}
    completed = subprocess.run(
        [executable, *GATEWAY_CRON_COMMAND[1:]],
        cwd=str(WORKSPACE),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=45,
    )
    meta: dict[str, Any] = {
        "available": True,
        "command": list(GATEWAY_CRON_COMMAND),
        "returncode": completed.returncode,
    }
    if completed.returncode != 0:
        meta["error"] = "openclaw_cron_list_failed"
        meta["stderr_tail"] = (completed.stderr or "")[-2000:]
        return [], meta
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        meta["error"] = f"openclaw_cron_list_unparseable:{exc.msg}"
        meta["stdout_tail"] = (completed.stdout or "")[-2000:]
        return [], meta
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        meta["error"] = "openclaw_cron_list_missing_jobs"
        return [], meta
    meta["total"] = payload.get("total")
    meta["has_more"] = payload.get("hasMore")
    return [item for item in jobs if isinstance(item, dict)], meta


def cron_jobs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    store_jobs = cron_jobs_from_store()
    if store_jobs or CRON_STORE.exists():
        return store_jobs, {
            "source": "legacy_file_store",
            "legacy_path": rel(CRON_STORE),
            "legacy_exists": CRON_STORE.exists(),
            "gateway_fallback_used": False,
        }
    gateway_jobs, gateway_meta = cron_jobs_from_gateway()
    return gateway_jobs, {
        "source": "gateway_cli_fallback",
        "legacy_path": rel(CRON_STORE),
        "legacy_exists": CRON_STORE.exists(),
        "gateway_fallback_used": True,
        "gateway": gateway_meta,
    }


def job_name(job: dict[str, Any]) -> str:
    for key in ("name", "title", "description"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(job.get("id") or "unnamed")


def job_enabled(job: dict[str, Any]) -> bool:
    for key in ("enabled", "is_enabled", "active"):
        if key in job:
            return bool(job.get(key))
    if "disabled" in job:
        return not bool(job.get("disabled"))
    return True


def schedule_text(job: dict[str, Any]) -> str:
    for key in ("schedule", "cron", "rrule", "when"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return ""


def session_target(job: dict[str, Any]) -> str:
    raw = job.get("session") or job.get("session_target") or job.get("sessionTarget") or job.get("target") or job.get("run_context")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("type", "name", "mode"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def next_run(job: dict[str, Any]) -> str:
    for key in ("nextRunAt", "next_run_at", "nextRunAtMs", "next_run_at_ms"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and value > 0:
            try:
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            except Exception:
                return str(value)
    state = job.get("state")
    if isinstance(state, dict):
        for key in ("nextRunAt", "next_run_at", "nextRunAtMs", "next_run_at_ms"):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (int, float)) and value > 0:
                try:
                    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                except Exception:
                    return str(value)
    return ""


def summarize_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for job in jobs:
        state = as_dict(job.get("state"))
        prompt = job.get("prompt") or job.get("message") or job.get("task") or ""
        payload = job.get("payload")
        if not prompt and isinstance(payload, dict):
            prompt = payload.get("text") or payload.get("message") or ""
        prompt_text = prompt if isinstance(prompt, str) else json.dumps(prompt, sort_keys=True) if prompt else ""
        schedule = job.get("schedule")
        timezone = ""
        if isinstance(schedule, dict):
            timezone = str(schedule.get("tz") or schedule.get("timezone") or "")
        records.append(
            {
                "id": str(job.get("id") or job.get("job_id") or ""),
                "name": job_name(job),
                "enabled": job_enabled(job),
                "schedule": schedule_text(job),
                "timezone": str(job.get("timezone") or job.get("tz") or timezone),
                "session_target": session_target(job),
                "next_run_utc": next_run(job),
                "prompt_bytes": len(prompt_text.encode("utf-8")),
                "prompt_kind": "inline_prompt" if prompt_text else "unknown",
                "last_status": str(state.get("lastStatus") or state.get("lastRunStatus") or job.get("status") or ""),
                "consecutive_errors": int(state.get("consecutiveErrors") or 0),
                "last_error": str(state.get("lastError") or state.get("lastDiagnosticSummary") or ""),
                "failure_alert": job.get("failureAlert") if isinstance(job.get("failureAlert"), dict) else None,
            }
        )
    return sorted(records, key=lambda item: (not item["enabled"], item["name"].lower()))


def run_summary(window: str) -> dict[str, Any]:
    path = TMP / f"run-summary-{window}.json"
    data = load_json(path)
    if not isinstance(data, dict):
        return {"window": window, "path": rel(path), "exists": path.exists(), "status": "missing"}
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    return {
        "window": window,
        "path": rel(path),
        "exists": True,
        "status": str(data.get("status") or "unknown"),
        "stop_line": bool(data.get("stop_line")),
        "generated_at_utc": str(data.get("generated_at_utc") or ""),
        "chain_status": str(execution.get("chain_status") or ""),
        "failed_step": execution.get("failed_step"),
        "skipped_steps": execution.get("skipped_steps") or [],
        "acceptance_passed": bool(validation.get("acceptance_passed")),
        "operator_action_required": data.get("operator_action_required") or [],
        "next_action": str(data.get("next_action") or ""),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
    }


def current_window_index() -> dict[str, Any]:
    path = TMP / "current-window-artifacts.json"
    data = load_json(path)
    if not isinstance(data, dict):
        return {"path": rel(path), "exists": path.exists(), "status": "missing"}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "path": rel(path),
        "exists": True,
        "window": str(data.get("window") or ""),
        "status": str(data.get("status") or ""),
        "generated_at_utc": str(data.get("generated_at_utc") or ""),
        "artifact_count": summary.get("artifact_count"),
        "existing_artifact_count": summary.get("existing_artifact_count"),
        "missing_required_roles": summary.get("missing_required_roles") or [],
        "critical_or_unreadable_roles": summary.get("critical_or_unreadable_roles") or [],
    }


def surface(path_text: str, role: str, target: str) -> dict[str, Any]:
    path = WORKSPACE / path_text
    return {
        "path": path_text,
        "role": role,
        "target_posture": target,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def build_ledger() -> dict[str, Any]:
    raw_jobs, cron_source = cron_jobs()
    jobs = summarize_jobs(raw_jobs)
    summaries = [run_summary(window) for window in WINDOWS]
    stop_lines = [item for item in summaries if item.get("stop_line")]
    blocked = [item for item in summaries if item.get("status") in {"blocked", "error"}]
    warnings = [item for item in summaries if item.get("status") == "warning"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "blocked" if blocked else "warning" if warnings else "ok",
        "authority": AUTHORITY,
        "cron_store": {
            "path": rel(CRON_STORE),
            "exists": CRON_STORE.exists(),
            "source": cron_source.get("source"),
            "gateway_fallback_used": cron_source.get("gateway_fallback_used"),
            "job_count": len(jobs),
            "enabled_count": sum(1 for job in jobs if job.get("enabled")),
            "disabled_count": sum(1 for job in jobs if not job.get("enabled")),
            "source_detail": cron_source,
        },
        "jobs": jobs,
        "run_summaries": summaries,
        "current_window_artifacts": current_window_index(),
        "operator_attention": {
            "stop_line_windows": [item["window"] for item in stop_lines],
            "blocked_windows": [item["window"] for item in blocked],
            "warning_windows": [item["window"] for item in warnings],
            "next_actions": [
                {"window": item["window"], "next_action": item.get("next_action", "")}
                for item in summaries
                if item.get("next_action")
            ],
        },
        "markdown_surfaces": [
            surface("06. Playbooks/Cron Run Ledger.md", "legacy_operator_ledger", "thin_operator_digest_after_migration"),
            surface("06. Playbooks/Cron Job Protocol.md", "procedure", "keep_as_procedure_only"),
            surface("06. Playbooks/Automation Run Summary Contract.md", "contract", "keep_as_machine_contract"),
            surface(rel((TMP / "current-window-artifacts.json").with_suffix(".md")), "rendered_duplicate", "on_demand_digest_only"),
            surface(rel(OUT_MD), "generated_digest", "on_demand_human_digest_from_json"),
        ],
        "source_of_truth": {
            "current_operator_status": rel(OUT_JSON),
            "window_closure": "tmp/run-summary-<window>.json",
            "raw_step_trace": "tmp/run-chain-<window>.json",
            "artifact_routing": "tmp/current-window-artifacts.json",
            "human_digest": "optional on-demand Markdown beside the JSON ledger",
            "legacy_historical_md": "06. Playbooks/Cron Run Ledger.md",
        },
        "notes": [
            "This ledger is additive and read-only. It does not edit cron jobs or scheduled windows.",
            "Markdown should render this state for humans; downstream automation should consume the JSON artifacts above.",
            "Historical Markdown should not be thinned until job IDs, stop lines, schedules, authority boundaries, and latest proof are represented in validated JSON.",
        ],
    }


def render_md(ledger: dict[str, Any]) -> str:
    lines = ["# Cron Operator Ledger", ""]
    lines.append(f"- Generated: `{ledger['generated_at_utc']}`")
    lines.append(f"- Status: **{ledger['status']}**")
    store = ledger["cron_store"]
    lines.append(f"- Cron jobs: {store['enabled_count']} enabled / {store['job_count']} total")
    attention = ledger["operator_attention"]
    if attention["stop_line_windows"]:
        lines.append(f"- Stop-line windows: {', '.join(attention['stop_line_windows'])}")
    if attention["blocked_windows"]:
        lines.append(f"- Blocked windows: {', '.join(attention['blocked_windows'])}")
    if attention["warning_windows"]:
        lines.append(f"- Warning windows: {', '.join(attention['warning_windows'])}")
    lines.append("")
    lines.append("## Current Windows")
    lines.append("| Window | Status | Stop line | Chain | Acceptance | Next action |")
    lines.append("|---|---|---:|---|---:|---|")
    for item in ledger["run_summaries"]:
        next_action = str(item.get("next_action") or "").replace("|", "/")
        if len(next_action) > 140:
            next_action = next_action[:137] + "..."
        lines.append(
            f"| {item['window']} | {item.get('status')} | {str(item.get('stop_line')).lower()} | "
            f"{item.get('chain_status', '')} | {str(item.get('acceptance_passed')).lower()} | {next_action} |"
        )
    lines.append("")
    lines.append("## Enabled Jobs")
    lines.append("| Job | Schedule | Session | Next run |")
    lines.append("|---|---|---|---|")
    for job in ledger["jobs"]:
        if not job.get("enabled"):
            continue
        name = str(job.get("name") or "").replace("|", "/")
        schedule = str(job.get("schedule") or "").replace("|", "/")
        session = str(job.get("session_target") or "").replace("|", "/")
        lines.append(f"| {name} | {schedule} | {session} | {job.get('next_run_utc', '')} |")
    lines.append("")
    lines.append("## Truth Routing")
    for key, value in ledger["source_of_truth"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("Authority: review-only. This digest grants no cron mutation, canon/portfolio mutation, customer delivery, paper/live/account action, or owner approval.")
    return "\n".join(lines) + "\n"


def validate(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if ledger.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    cron_store = ledger.get("cron_store", {})
    if not cron_store.get("exists") and cron_store.get("source") != "gateway_cli_fallback":
        errors.append("cron_store_missing")
    if int(cron_store.get("enabled_count") or 0) <= 0:
        errors.append("enabled_jobs_missing")
    for key, value in AUTHORITY.items():
        if isinstance(value, bool) and key != "review_only" and ledger.get("authority", {}).get(key) is not False:
            errors.append(f"authority_not_false:{key}")
    if ledger.get("authority", {}).get("review_only") is not True:
        errors.append("review_only_not_true")
    if not ledger.get("run_summaries"):
        errors.append("run_summaries_missing")
    if not any(item.get("path") == "06. Playbooks/Cron Run Ledger.md" for item in ledger.get("markdown_surfaces", [])):
        errors.append("legacy_ledger_surface_missing")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a JSON-first current cron operator ledger and optional human digest.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger = build_ledger()
    errors = validate(ledger) if args.validate else []
    if args.write:
        atomic_write_json(OUT_JSON, ledger, indent=2)
        if args.write_md:
            atomic_write_text(OUT_MD, render_md(ledger))
    print(json.dumps({"status": "error" if errors else "ok", "out": rel(OUT_JSON), "md": rel(OUT_MD), "errors": errors}, indent=2))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
