#!/usr/bin/env python3
"""Pick and optionally run the smallest honest validator bundle."""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
import changed_file_validator_router as changed_router

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "validator-bundle-router.json"
DEFAULT_TIMING_LEDGER = TMP / "validator-timing-ledger.json"
SCHEMA = "veritas.validator_bundle_router.v1"
BUDGET_RANK = changed_router.BUDGET_RANK
WINDOWS_SHELL_COMMAND_SAFE_LIMIT = changed_router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "validator_routing_only": True,
    "executes_only_when_execute_flag_set": True,
    "allowed_command_prefixes": ["python", "openclaw"],
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKED_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "--apply", "--submit", "--cancel", "--promote", "--import")

TRADE_GRADE_PRODUCER_PREFIX = "python scripts\\trade_grade_os_freshness_cron_runner.py "
TRADE_GRADE_DEPENDENT_PREFIXES = (
    "python scripts\\finance_response_quality_slice.py ",
    "python scripts\\test_finance_response_quality_slice.py",
    "python scripts\\model_quality_scorecard.py ",
    "python scripts\\test_model_quality_scorecard.py",
    "python scripts\\wf74_model_quality_collection_cron_runner.py ",
)
UNSCOPED_EXECUTION_PATH_LIMIT = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def command_allowed(command: str) -> tuple[bool, str]:
    stripped = command.strip()
    if len(command) > WINDOWS_SHELL_COMMAND_SAFE_LIMIT:
        return (
            False,
            f"windows_shell_command_too_long:{len(command)}>{WINDOWS_SHELL_COMMAND_SAFE_LIMIT}",
        )
    first = stripped.split(maxsplit=1)[0].lower() if stripped else ""
    if first not in {"python", "openclaw"}:
        return False, f"prefix_not_allowed:{first}"
    for token in BLOCKED_TOKENS:
        if token in stripped:
            return False, f"blocked_token:{token}"
    return True, "ok"


def select_recommendations(recommendations: list[dict[str, Any]], max_budget: str) -> list[dict[str, Any]]:
    max_rank = BUDGET_RANK[max_budget]
    return [rec for rec in recommendations if BUDGET_RANK.get(rec.get("budget"), 99) <= max_rank]


def resolve_command(rec: dict[str, Any], manifest: dict[str, Any] | None = None) -> str:
    manifest = manifest or {}
    command_id = rec.get("command_id")
    commands = manifest.get("commands") if isinstance(manifest.get("commands"), dict) else {}
    if command_id and command_id in commands:
        return str(commands[command_id].get("command") or rec.get("command") or "")
    return str(rec.get("command") or "")


def command_has_prefix(command: str, prefixes: tuple[str, ...]) -> bool:
    return any(command.startswith(prefix) for prefix in prefixes)


def command_family(command: Any) -> str | None:
    parts = list(command) if isinstance(command, list) else str(command or "").strip().split()
    if not parts:
        return None
    lowered = [str(part).strip('"').lower() for part in parts]
    if "-m" in lowered:
        index = lowered.index("-m")
        if index + 1 < len(lowered):
            return f"python_module:{lowered[index + 1]}"
    for part in lowered[1:]:
        normalized = part.replace("/", "\\")
        if normalized.startswith("scripts\\") and normalized.endswith(".py"):
            return f"script:{Path(normalized).name}"
    if lowered[0] == "openclaw" and len(lowered) > 1:
        return f"openclaw:{lowered[1]}"
    return lowered[0]


def classify_task_paths(paths: list[str]) -> str:
    classes: set[str] = set()
    for raw in paths:
        path = str(raw).replace("\\", "/").lower()
        if path.startswith("wiki/") or "wiki_" in path or "wf88_wiki" in path:
            classes.add("wiki")
        elif path.startswith("skills/") or "skill_" in path:
            classes.add("skill")
        elif any(token in path for token in ("startup", "status_card", "future_session", "frontdoor")):
            classes.add("startup_frontdoor")
        elif any(token in path for token in ("concurrent_lane", "project_implementation_router", "validator_")):
            classes.add("runtime_control")
        elif any(token in path for token in ("finance", "portfolio", "trade_grade", "wf78", "wf84", "wf85")):
            classes.add("finance")
        else:
            classes.add("generic")
    if not classes:
        return "unscoped"
    return next(iter(classes)) if len(classes) == 1 else "mixed"


def timing_evidence(path: Path) -> dict[str, dict[str, Any]]:
    raw = load_json_artifact(path)
    payload = raw if isinstance(raw, dict) else {}
    if payload.get("schema") != "veritas.validator_timing_ledger.v1":
        return {}
    evidence: dict[str, dict[str, Any]] = {}
    for row in payload.get("commands") if isinstance(payload.get("commands"), list) else []:
        if not isinstance(row, dict):
            continue
        family = command_family(row.get("command"))
        if not family:
            continue
        evidence[family] = {
            "observed_elapsed_seconds": row.get("elapsed_seconds"),
            "sample_count": row.get("sample_count"),
            "measurement_status": "observed" if row.get("elapsed_seconds") is not None else "unavailable",
            "validator_ok": row.get("ok"),
            "source": rel(path),
        }
    return evidence


def add_selection_evidence(
    recommendations: list[dict[str, Any]],
    manifest: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for rec in recommendations:
        row = dict(rec)
        family = command_family(resolve_command(rec, manifest))
        row["command_family"] = family
        row["selection_basis"] = "exact_changed_path_owner_route"
        row["timing_evidence"] = evidence.get(family) or {
            "measurement_status": "unavailable",
            "unavailable_reason": "no_matching_validator_timing_sample",
        }
        enriched.append(row)
    return enriched


def order_recommendations_for_execution(
    recommendations: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Place an artifact producer immediately before its selected consumers.

    Budget ordering is useful for selection but is not a dependency graph. The
    trade-grade composite is deliberately major-budget, while its quality
    consumers are narrow/shared. Preserve the existing order for unrelated
    validators, then use the composite as a producer barrier before consumers.
    """
    manifest = manifest or {}
    producers: list[dict[str, Any]] = []
    dependents: list[dict[str, Any]] = []
    unrelated: list[dict[str, Any]] = []
    for rec in recommendations:
        command = resolve_command(rec, manifest)
        if command.startswith(TRADE_GRADE_PRODUCER_PREFIX):
            producers.append(rec)
        elif command_has_prefix(command, TRADE_GRADE_DEPENDENT_PREFIXES):
            dependents.append(rec)
        else:
            unrelated.append(rec)
    if not producers or not dependents:
        return list(recommendations), {
            "applied": False,
            "producer_count": len(producers),
            "dependent_count": len(dependents),
        }
    return [*unrelated, *producers, *dependents], {
        "applied": True,
        "producer_count": len(producers),
        "dependent_count": len(dependents),
        "rule": "trade_grade_producer_before_quality_consumers",
    }


def dependency_preflight_errors(
    all_recommendations: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Fail closed when a budget selects consumers but excludes their producer."""
    manifest = manifest or {}
    producer_recommended = any(
        resolve_command(rec, manifest).startswith(TRADE_GRADE_PRODUCER_PREFIX)
        for rec in all_recommendations
    )
    producer_selected = any(
        resolve_command(rec, manifest).startswith(TRADE_GRADE_PRODUCER_PREFIX)
        for rec in selected
    )
    dependent_selected = any(
        command_has_prefix(resolve_command(rec, manifest), TRADE_GRADE_DEPENDENT_PREFIXES)
        for rec in selected
    )
    if producer_recommended and dependent_selected and not producer_selected:
        return ["required_trade_grade_producer_excluded_by_budget"]
    return []


def compact_recommendation(rec: dict[str, Any], manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = resolve_command(rec, manifest)
    compact = dict(rec)
    compact["command_length"] = len(resolved)
    if len(resolved) > 500:
        compact["command"] = rec.get("command") or f"<command:{rec.get('command_id')}>"
        compact["command_compacted"] = True
    else:
        compact["command"] = resolved
        compact["command_compacted"] = False
    compact.pop("resolved_command", None)
    return compact


def compact_route(route: dict[str, Any]) -> dict[str, Any]:
    compact = dict(route)
    manifest = compact.get("command_manifest")
    if isinstance(manifest, dict):
        compact["command_manifest"] = {
            "command_count": manifest.get("command_count"),
            "long_command_count": manifest.get("long_command_count"),
            "windows_shell_command_safe_limit": manifest.get("windows_shell_command_safe_limit"),
            "oversize_execution_command_count": manifest.get("oversize_execution_command_count"),
            "commands_omitted_from_output": True,
        }
    return compact


def run_command(command: str, timeout: int) -> dict[str, Any]:
    ok, reason = command_allowed(command)
    if not ok:
        return {"command": command, "ok": False, "returncode": 97, "blocked_reason": reason}
    completed = subprocess.run(
        command,
        cwd=ROOT,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-2000:],
        "stderr_tail": (completed.stderr or "")[-2000:],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    route = changed_router.build_payload(
        args.base,
        args.include_untracked,
        args.path,
        include_command_manifest_commands=True,
    )
    max_budget = args.max_budget or route["summary"]["recommended_budget"]
    selected_by_budget = select_recommendations(route["recommendations"], max_budget)
    manifest = route.get("command_manifest") if isinstance(route.get("command_manifest"), dict) else {}
    timing_path_arg = getattr(args, "timing_ledger", DEFAULT_TIMING_LEDGER)
    timing_path = timing_path_arg if isinstance(timing_path_arg, Path) else Path(timing_path_arg)
    timing_path = timing_path if timing_path.is_absolute() else ROOT / timing_path
    selected_by_budget = add_selection_evidence(selected_by_budget, manifest, timing_evidence(timing_path))
    dependency_errors = dependency_preflight_errors(
        route["recommendations"],
        selected_by_budget,
        manifest,
    )
    selected, execution_ordering = order_recommendations_for_execution(
        selected_by_budget,
        manifest,
    )
    resolved_selected = [{**rec, "resolved_command": resolve_command(rec, manifest)} for rec in selected]
    command_checks = []
    for rec in resolved_selected:
        resolved_command = str(rec.get("resolved_command") or "")
        allowed, reason = command_allowed(resolved_command)
        command_checks.append({
            "command_id": rec.get("command_id"),
            "command": compact_recommendation(rec, manifest)["command"],
            "command_length": len(resolved_command),
            "allowed": allowed,
            "reason": reason,
        })
    run_results: list[dict[str, Any]] = []
    errors: list[str] = []
    route_validation = route.get("validation") if isinstance(route.get("validation"), dict) else {}
    route_errors = route_validation.get("errors") if isinstance(route_validation.get("errors"), list) else []
    if route_errors:
        errors.append("changed_file_route_validation_error")
    errors.extend(dependency_errors)
    explicit_paths = list(args.path or [])
    unscoped_execution_blocked = bool(
        args.execute
        and not explicit_paths
        and int(route["summary"].get("changed_path_count") or 0) > UNSCOPED_EXECUTION_PATH_LIMIT
    )
    if unscoped_execution_blocked:
        errors.append("explicit_changed_paths_required_for_large_worktree_execution")
    if any(not item["allowed"] for item in command_checks):
        errors.append("selected_command_blocked_by_safety_guard")
    execution_preflight_ok = not errors
    if args.execute and execution_preflight_ok:
        for rec in resolved_selected:
            result = run_command(str(rec.get("resolved_command") or rec.get("command") or ""), args.timeout_seconds)
            result["command_id"] = rec.get("command_id")
            run_results.append(result)
            if not result.get("ok"):
                errors.append(f"validator_failed:{rec['command']}")
                if not args.continue_on_failure:
                    break
    warnings = []
    if not selected:
        warnings.append("no_validators_selected")
    status = "error" if errors else "warning" if warnings else "ok"
    executed_count = len(run_results)
    failed_count = sum(1 for item in run_results if not item.get("ok"))
    execution_blocked = bool(args.execute and not execution_preflight_ok)
    proof_mode = "execution_blocked" if execution_blocked else "executed" if args.execute else "plan_only"
    proof_claim = (
        "selected_validators_were_not_executed"
        if execution_blocked or not args.execute
        else "selected_validators_were_executed"
    )
    proof_statement = (
        "Execution was blocked by validator-route or command-safety preflight; 0 selected validator commands were executed."
        if execution_blocked
        else f"{executed_count} selected validator command(s) executed; {failed_count} failed."
        if args.execute
        else (
            f"{len(selected)} validator command(s) selected for the requested budget; "
            "0 were executed because --execute was not supplied."
        )
    )
    selected_bundle_completion_claim_allowed = bool(args.execute and failed_count == 0 and not errors)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "execute" if args.execute else "plan",
        "proof_interpretation": {
            "proof_mode": proof_mode,
            "proof_claim": proof_claim,
            "safe_summary": proof_statement,
            "selected_is_not_executed": bool(not args.execute or execution_blocked),
            "failed_count_meaning": (
                "No validator failure count is available because execution was blocked by preflight."
                if execution_blocked
                else
                "Failures among executed validator commands."
                if args.execute
                else "No failures can be inferred because no selected validator commands were executed."
            ),
            "claim_scope": "selected_validator_bundle_only",
            "selected_bundle_completion_claim_allowed": selected_bundle_completion_claim_allowed,
            "completion_claim_allowed": False,
            "implementation_completion_claim_allowed": False,
            "requires_post_bundle_implementation_proof": True,
            "post_bundle_implementation_command": (
                "python scripts\\go_fast_proof_validators.py --profile implementation --driver inprocess --write --validate"
            ),
        },
        "summary": {
            "changed_path_count": route["summary"]["changed_path_count"],
            "recommended_budget": route["summary"]["recommended_budget"],
            "selected_budget": max_budget,
            "include_untracked": args.include_untracked,
            "selected_command_count": len(selected),
            "executed_command_count": executed_count,
            "failed_command_count": failed_count,
            "long_command_count": route["summary"].get("long_command_count"),
            "command_manifest_available": bool(manifest),
            "execution_preflight_ok": execution_preflight_ok,
            "windows_shell_command_safe_limit": WINDOWS_SHELL_COMMAND_SAFE_LIMIT,
            "dependency_ordering_applied": bool(execution_ordering.get("applied")),
            "task_class": classify_task_paths(explicit_paths),
            "selection_strategy": "exact_scoped_changed_path_route_with_budget_ceiling",
            "scope_provided": bool(explicit_paths),
            "unscoped_execution_path_limit": UNSCOPED_EXECUTION_PATH_LIMIT,
            "unscoped_execution_blocked": unscoped_execution_blocked,
            "timing_evidence_available_count": sum(
                1 for rec in selected if isinstance(rec.get("timing_evidence"), dict) and rec["timing_evidence"].get("measurement_status") == "observed"
            ),
            "next_safe_action": "Run with --execute when the selected bundle is acceptable." if not args.execute else "Review failed_command_count and rerun only after fixing failures.",
        },
        "execution_ordering": execution_ordering,
        "changed_file_route": compact_route(route),
        "selected_validators": [compact_recommendation(rec, manifest) for rec in selected],
        "command_manifest": {
            "command_count": manifest.get("command_count", len(resolved_selected)),
            "long_command_count": manifest.get("long_command_count", 0),
            "windows_shell_command_safe_limit": WINDOWS_SHELL_COMMAND_SAFE_LIMIT,
            "oversize_execution_command_count": manifest.get("oversize_execution_command_count", 0),
            "available_for_execution": bool(manifest and execution_preflight_ok),
            "commands_omitted_from_output": True,
        },
        "command_safety": command_checks,
        "run_results": run_results,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--no-untracked", action="store_false", dest="include_untracked")
    parser.set_defaults(include_untracked=False)
    parser.add_argument("--path", action="append")
    parser.add_argument("--max-budget", choices=sorted(BUDGET_RANK, key=BUDGET_RANK.get))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--timing-ledger", type=Path, default=DEFAULT_TIMING_LEDGER)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} mode={payload['mode']} "
        f"proof={payload['proof_interpretation']['proof_mode']} "
        f"selected={payload['summary']['selected_command_count']} "
        f"executed={payload['summary']['executed_command_count']} "
        f"failed={payload['summary']['failed_command_count']} out={rel(out)}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
