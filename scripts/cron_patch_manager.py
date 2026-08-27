#!/usr/bin/env python3
"""Plan, apply, verify, and rollback narrow Gateway cron patches.

This is intentionally conservative. It patches only fields that are safe to
express through the public `openclaw cron edit` interface and writes a backup
before any live mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
BACKUP_DIR = TMP / "cron-patch-manager-backups"
DEFAULT_OUT = TMP / "cron-patch-manager.json"
SCHEMA = "veritas.cron_patch_manager.v1"

ORDERED_VERIFY_COMMANDS = [
    ["scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"],
    ["scripts\\cron_freshness_spine.py", "--write", "--validate"],
    ["scripts\\cron_signal_scorecard.py", "--write", "--validate"],
    ["scripts\\escalation_trigger.py", "--write", "--validate"],
    ["scripts\\cron_control_packet.py", "--write", "--validate"],
]

ALLOWED_PATCH_KEYS = {
    "description",
    "message",
    "model",
    "thinking",
    "timeoutSeconds",
    "lightContext",
    "failureAlert",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_requires_apply_flag": True,
    "schedule_mutation_allowed": False,
    "delivery_mutation_allowed": False,
    "job_add_delete_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def openclaw_cmd() -> str:
    found = shutil.which("openclaw.cmd") or shutil.which("openclaw") or shutil.which("openclaw.ps1")
    if found:
        return found
    known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(known) if known.exists() else "openclaw.cmd"


def openclaw_command_prefix(platform: str | None = None) -> list[str]:
    """Return an argv-safe OpenClaw CLI prefix.

    Windows npm ``.cmd`` shims expand ``%*`` through ``cmd.exe``. A multiline
    argument can therefore be truncated even though ``subprocess.run`` was
    given a list and the shim exits successfully. Bypass that extra parser
    when the shim's Node entry point is available; retain the existing CLI
    resolution as a conservative fallback on other installs and platforms.
    """
    cli = Path(openclaw_cmd())
    if (platform or sys.platform).startswith("win"):
        entry = cli.parent / "node_modules" / "openclaw" / "openclaw.mjs"
        bundled_node = cli.parent / "node.exe"
        node = str(bundled_node) if bundled_node.is_file() else shutil.which("node.exe") or shutil.which("node")
        if node and entry.is_file():
            return [node, str(entry)]
    return [str(cli)]


def openclaw_command(*args: str) -> list[str]:
    return [*openclaw_command_prefix(), *args]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_command(command: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
    }


def run_openclaw_json(command: list[str], timeout: int = 60) -> tuple[Any, dict[str, Any]]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    result = {
        "command": command,
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
    }
    if completed.returncode != 0:
        return None, result
    try:
        return json.loads(completed.stdout), result
    except json.JSONDecodeError:
        result["ok"] = False
        result["returncode"] = 98
        result["stderr_tail"] = "openclaw_json_parse_failed"
        return None, result


def cron_list() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload, result = run_openclaw_json(
        openclaw_command("cron", "list", "--all", "--json", "--timeout", "30000"),
        timeout=45,
    )
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        return [], {**result, "ok": False, "error": "cron_list_missing_jobs"}
    return [job for job in jobs if isinstance(job, dict)], result


def cron_get(job_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, result = run_openclaw_json(
        openclaw_command("cron", "get", job_id, "--timeout", "30000"),
        timeout=45,
    )
    return (payload if isinstance(payload, dict) else {}), result


def resolve_job(job_id: str | None, name: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if job_id:
        job, result = cron_get(job_id)
        return job, {"mode": "id", "lookup": job_id, "result": result}
    if not name:
        return {}, {"mode": "none", "error": "job_id_or_name_required"}
    jobs, result = cron_list()
    matches = [job for job in jobs if str(job.get("name") or "") == name]
    if len(matches) != 1:
        return {}, {"mode": "name", "lookup": name, "match_count": len(matches), "result": result}
    return matches[0], {"mode": "name", "lookup": name, "match_count": 1, "result": result}


def read_patch_file(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def read_rollback_backup(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Load a cron backup strictly enough that rollback cannot invent state.

    ``load_json_artifact`` intentionally treats missing and malformed artifacts
    as ``None`` for read-side consumers. A rollback source is mutation
    authority, so those states must remain distinguishable and fail closed.
    Backups written by :func:`backup_job` are complete cron job objects with a
    stable id and payload object.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, ["rollback_backup_missing"]
    except OSError as exc:
        return {}, [f"rollback_backup_unreadable:{type(exc).__name__}"]
    if not raw.strip():
        return {}, ["rollback_backup_empty"]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}, ["rollback_backup_invalid_json"]
    if not isinstance(payload, dict):
        return {}, ["rollback_backup_not_object"]

    errors: list[str] = []
    if not isinstance(payload.get("id"), str) or not str(payload.get("id") or "").strip():
        errors.append("rollback_backup_missing_job_id")
    if not isinstance(payload.get("name"), str) or not str(payload.get("name") or "").strip():
        errors.append("rollback_backup_missing_job_name")
    job_payload = payload.get("payload")
    if not isinstance(job_payload, dict):
        errors.append("rollback_backup_payload_not_object")
    elif not isinstance(job_payload.get("kind"), str) or not str(job_payload.get("kind") or "").strip():
        errors.append("rollback_backup_missing_payload_kind")
    elif job_payload.get("kind") == "agentTurn" and (
        not isinstance(job_payload.get("message"), str) or not str(job_payload.get("message") or "").strip()
    ):
        errors.append("rollback_backup_missing_agent_turn_message")
    return payload, errors


def build_requested_patch(args: argparse.Namespace) -> dict[str, Any]:
    patch = read_patch_file(args.patch_file)
    if args.description is not None:
        patch["description"] = args.description
    if args.message is not None:
        patch["message"] = args.message
    if args.message_file is not None:
        patch["message"] = Path(args.message_file).read_text(encoding="utf-8")
    if args.model is not None:
        patch["model"] = args.model
    if args.thinking is not None:
        patch["thinking"] = args.thinking
    if args.timeout_seconds is not None:
        patch["timeoutSeconds"] = args.timeout_seconds
    if args.light_context is not None:
        patch["lightContext"] = args.light_context
    if args.failure_alert_after is not None or args.failure_alert_mode is not None:
        patch["failureAlert"] = {
            "after": args.failure_alert_after if args.failure_alert_after is not None else 1,
            "mode": args.failure_alert_mode or "announce",
        }
    if args.no_failure_alert:
        patch["failureAlert"] = None
    return patch


def current_field(job: dict[str, Any], key: str) -> Any:
    payload = as_dict(job.get("payload"))
    if key in {"message", "model", "thinking", "timeoutSeconds", "lightContext"}:
        return payload.get(key)
    return job.get(key)


def exact_value_equal(expected: Any, actual: Any) -> bool:
    """Compare JSON-like values without Python's bool/int equivalence."""
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return expected.keys() == actual.keys() and all(
            exact_value_equal(expected[key], actual[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            exact_value_equal(expected_item, actual_item)
            for expected_item, actual_item in zip(expected, actual)
        )
    return expected == actual


def text_sha256(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compare_patch_to_live_job(patch: dict[str, Any], live_job: dict[str, Any]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for key in sorted(patch):
        expected = patch[key]
        actual = current_field(live_job, key)
        matches = exact_value_equal(expected, actual)
        field = {
            "field": key,
            "matches": matches,
            "expected": expected,
            "actual": actual,
        }
        if key == "message":
            field.update(
                {
                    "expected_length": len(expected) if isinstance(expected, str) else None,
                    "actual_length": len(actual) if isinstance(actual, str) else None,
                    "expected_sha256": text_sha256(expected),
                    "actual_sha256": text_sha256(actual),
                }
            )
        fields.append(field)
        if not matches:
            mismatches.append(key)
    return {
        "status": "ok" if not mismatches else "error",
        "exact_match": not mismatches,
        "mismatched_fields": mismatches,
        "fields": fields,
    }


def verify_live_round_trip(job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    live_job, lookup_result = cron_get(job_id)
    result = compare_patch_to_live_job(patch, live_job) if live_job else {
        "status": "error",
        "exact_match": False,
        "mismatched_fields": sorted(patch),
        "fields": [],
    }
    result["lookup_result"] = lookup_result
    errors: list[str] = []
    if not lookup_result.get("ok") or not live_job:
        errors.append("round_trip_job_refetch_failed")
    elif str(live_job.get("id") or "") != job_id:
        errors.append("round_trip_job_id_mismatch")
    errors.extend(f"round_trip_field_mismatch:{key}" for key in result.get("mismatched_fields", []))
    result["errors"] = errors
    if errors:
        result["status"] = "error"
        result["exact_match"] = False
    return result


def proposed_job(job: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(job))
    payload = result.setdefault("payload", {})
    for key, value in patch.items():
        if key in {"message", "model", "thinking", "timeoutSeconds", "lightContext"}:
            payload[key] = value
        elif key == "failureAlert":
            if value is None:
                result.pop("failureAlert", None)
            else:
                result["failureAlert"] = value
        elif key == "description":
            result["description"] = value
    return result


def diff_fields(job: dict[str, Any], patch: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for key in sorted(patch):
        before = current_field(job, key)
        after = patch[key]
        if not exact_value_equal(before, after):
            diffs.append({"field": key, "before": before, "after": after})
    return diffs


def classify_impact(patch: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    impact = {
        "payload_mutation": any(key in patch for key in ("message", "model", "thinking", "timeoutSeconds", "lightContext")),
        "description_mutation": "description" in patch,
        "failure_alert_mutation": "failureAlert" in patch,
        "schedule_mutation": False,
        "delivery_mutation": False,
        "finance_sensitive_name": str(job.get("name") or "").startswith("Finance -"),
        "authority_sensitive": False,
        "risk": "low",
    }
    impact["authority_sensitive"] = bool(impact["finance_sensitive_name"] or impact["failure_alert_mutation"])
    if impact["finance_sensitive_name"] and impact["payload_mutation"]:
        impact["risk"] = "finance_control"
    elif impact["payload_mutation"] or impact["failure_alert_mutation"]:
        impact["risk"] = "runtime_control"
    elif impact["description_mutation"]:
        impact["risk"] = "metadata_only"
    return impact


def validate_patch(patch: dict[str, Any], allow_schedule_or_delivery: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    unknown = sorted(set(patch) - ALLOWED_PATCH_KEYS)
    if unknown:
        errors.append(f"unsupported_patch_keys:{','.join(unknown)}")
    if not allow_schedule_or_delivery:
        blocked = sorted(set(patch) & {"schedule", "delivery", "sessionTarget", "wakeMode", "enabled", "deleteAfterRun"})
        if blocked:
            errors.append(f"schedule_or_delivery_or_lifecycle_patch_refused:{','.join(blocked)}")
    if "thinking" in patch and patch["thinking"] not in {"off", "minimal", "low", "medium", "high", "xhigh"}:
        errors.append(f"invalid_thinking:{patch['thinking']}")
    if "timeoutSeconds" in patch:
        try:
            if int(patch["timeoutSeconds"]) < 0:
                errors.append("timeoutSeconds_negative")
        except (TypeError, ValueError):
            errors.append("timeoutSeconds_not_int")
    if "failureAlert" in patch and patch["failureAlert"] is not None:
        fa = patch["failureAlert"]
        if not isinstance(fa, dict):
            errors.append("failureAlert_not_object_or_null")
        elif fa.get("mode") not in {"announce", "webhook"}:
            errors.append(f"failureAlert_invalid_mode:{fa.get('mode')}")
    if not patch:
        warnings.append("empty_patch")
    return errors, warnings


def backup_job(job: dict[str, Any], reason: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(job.get("name") or "job"))[:80]
    path = BACKUP_DIR / f"{stamp}-{job.get('id')}-{safe_name}-{reason}.json"
    atomic_write_json(path, job, indent=2)
    return path


def edit_command(job_id: str, patch: dict[str, Any]) -> list[str]:
    cmd = openclaw_command("cron", "edit", job_id, "--timeout", "30000")
    if "description" in patch:
        cmd += ["--description", str(patch["description"])]
    if "message" in patch:
        cmd += ["--message", str(patch["message"])]
    if "model" in patch:
        cmd += ["--model", str(patch["model"])]
    if "thinking" in patch:
        cmd += ["--thinking", str(patch["thinking"])]
    if "timeoutSeconds" in patch:
        cmd += ["--timeout-seconds", str(int(patch["timeoutSeconds"]))]
    if "lightContext" in patch:
        cmd += ["--light-context" if patch["lightContext"] else "--no-light-context"]
    if "failureAlert" in patch:
        if patch["failureAlert"] is None:
            cmd.append("--no-failure-alert")
        else:
            fa = as_dict(patch["failureAlert"])
            cmd.append("--failure-alert")
            if fa.get("after") is not None:
                cmd += ["--failure-alert-after", str(int(fa["after"]))]
            if fa.get("mode") is not None:
                cmd += ["--failure-alert-mode", str(fa["mode"])]
    return cmd


def patch_from_backup(job: dict[str, Any]) -> dict[str, Any]:
    payload = as_dict(job.get("payload"))
    patch: dict[str, Any] = {}
    for key in ("message", "model", "thinking", "timeoutSeconds", "lightContext"):
        if key in payload:
            patch[key] = payload[key]
    if "description" in job:
        patch["description"] = job.get("description")
    patch["failureAlert"] = job.get("failureAlert") if "failureAlert" in job else None
    return patch


def run_ordered_verify() -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for script_args in ORDERED_VERIFY_COMMANDS:
        steps.append(run_command([sys.executable, *script_args], timeout=180))
    control = load_json_artifact(TMP / "cron-control-packet.json")
    control_summary = as_dict(as_dict(control).get("summary"))
    escalation = as_dict(as_dict(control).get("escalation"))
    errors: list[str] = []
    if not all(step.get("ok") for step in steps):
        errors.append("ordered_verify_command_failed")
    if as_dict(control).get("status") != "ok":
        errors.append(f"cron_control_status_not_ok:{as_dict(control).get('status')}")
    if int(control_summary.get("blocked_count") or 0) != 0:
        errors.append(f"cron_control_blocked_count:{control_summary.get('blocked_count')}")
    if int(control_summary.get("escalation_signal_count") or 0) != 0:
        errors.append(f"cron_control_escalation_signal_count:{control_summary.get('escalation_signal_count')}")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "steps": steps,
        "cron_control_summary": control_summary,
        "cron_control_escalation": {
            "should_wake_main_session": escalation.get("should_wake_main_session"),
            "escalation_signal_count": escalation.get("escalation_signal_count"),
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    mode = "rollback" if args.rollback else "apply" if args.apply else "plan"
    requested_patch: dict[str, Any] = {}
    backup_path = ""
    rollback_source: dict[str, Any] = {}
    rollback_errors: list[str] = []
    if args.rollback:
        backup = Path(args.rollback)
        rollback_source, rollback_errors = read_rollback_backup(backup)
        if rollback_errors:
            job = {}
            lookup = {
                "mode": "rollback",
                "lookup": rel(backup),
                "error": "rollback_source_invalid",
            }
        else:
            requested_patch = patch_from_backup(rollback_source)
            job_id = str(rollback_source.get("id") or "")
            job, lookup = resolve_job(job_id, None)
    else:
        requested_patch = build_requested_patch(args)
        job, lookup = resolve_job(args.job_id, args.name)
    patch_errors, patch_warnings = validate_patch(requested_patch, allow_schedule_or_delivery=False)
    patch_errors = [*rollback_errors, *patch_errors]
    diffs = diff_fields(job, requested_patch) if job else []
    impact = classify_impact(requested_patch, job) if job else {}
    finance_guard_required = bool(
        args.apply
        and not args.rollback
        and impact.get("risk") == "finance_control"
    )
    if finance_guard_required:
        sql_canon_context = {
            **finance_sql_canon_guard_context(consumer=rel(Path(__file__))),
            "required": True,
            "reason": "forward_finance_control_apply",
        }
        if sql_canon_context.get("status") != "ok":
            patch_errors.append("sql_canon_guard_blocked")
    else:
        sql_canon_context = {
            "status": "not_required",
            "required": False,
            "reason": (
                "rollback_must_not_depend_on_unrelated_finance_state"
                if args.rollback
                else "non_finance_control_operation"
            ),
        }
    apply_result: dict[str, Any] | None = None
    round_trip_result: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None
    if args.apply or args.rollback:
        if not job:
            patch_errors.append("job_not_resolved")
        if patch_errors:
            patch_warnings.append("apply_skipped_due_to_validation_errors")
        else:
            backup_path = rel(backup_job(job, "pre-rollback" if args.rollback else "pre-apply"))
            apply_result = run_command(edit_command(str(job.get("id")), requested_patch), timeout=60)
            round_trip_result = verify_live_round_trip(str(job.get("id")), requested_patch)
            if args.verify:
                verify_result = run_ordered_verify()
    elif args.verify:
        verify_result = run_ordered_verify()

    validation_errors = list(patch_errors)
    validation_warnings = list(patch_warnings)
    if not job and "job_not_resolved" not in validation_errors:
        validation_errors.append("job_not_resolved")
    if (args.apply or args.rollback) and apply_result and not apply_result.get("ok"):
        validation_errors.append("cron_edit_failed")
    if round_trip_result and round_trip_result.get("status") != "ok":
        validation_errors.extend(round_trip_result.get("errors", []))
    if verify_result and verify_result.get("status") != "ok":
        validation_errors.extend(f"verify:{error}" for error in verify_result.get("errors", []))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": mode,
        "status": "error" if validation_errors else "ok",
        "operator_action": "BLOCKED" if validation_errors else "NO_REPLY",
        "job": {
            "id": job.get("id"),
            "name": job.get("name"),
            "enabled": job.get("enabled"),
        } if job else {},
        "lookup": lookup,
        "requested_patch": requested_patch,
        "diff": diffs,
        "impact": impact,
        "backup_path": backup_path,
        "apply_result": apply_result,
        "round_trip_result": round_trip_result,
        "verify_result": verify_result,
        "rollback_source": rel(Path(args.rollback)) if args.rollback else "",
        "rollback_source_validation": {
            "status": "error" if rollback_errors else "ok" if args.rollback else "not_applicable",
            "errors": rollback_errors,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_context": sql_canon_context,
        "validation": {
            "status": "error" if validation_errors else "warning" if validation_warnings else "ok",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan/apply/rollback narrow Gateway cron patches.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--job-id")
    target.add_argument("--name")
    parser.add_argument("--patch-file", type=Path)
    parser.add_argument("--description")
    parser.add_argument("--message")
    parser.add_argument("--message-file", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--thinking")
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--light-context", dest="light_context", action="store_true")
    parser.add_argument("--no-light-context", dest="light_context", action="store_false")
    parser.set_defaults(light_context=None)
    parser.add_argument("--failure-alert-after", type=int)
    parser.add_argument("--failure-alert-mode", choices=["announce", "webhook"])
    parser.add_argument("--no-failure-alert", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload, indent=2)
    print(
        f"status={payload['status']} mode={payload['mode']} "
        f"validation={payload['validation']['status']} diffs={len(payload.get('diff') or [])} out={rel(out)}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
