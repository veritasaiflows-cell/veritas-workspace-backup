#!/usr/bin/env python3
"""Build metadata-only coding-runtime KPIs for WF74 and PM.

This probe measures implementation-loop behavior from local proof surfaces:
changed-file routing, validator timing, closeout, WF74 collection, and the
metadata ledger. It never captures raw diffs, file contents, prompts, model
responses, tool payloads, secrets, or credentials.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "coding-runtime-kpi-probe.json"
OUT_MD = TMP / "coding-runtime-kpi-probe.md"
SCHEMA = "veritas.coding_runtime_kpi_probe.v1"

CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"
VALIDATOR_TIMING = TMP / "validator-timing-ledger.json"
REPEATABLE_CLOSEOUT = TMP / "repeatable-work-closeout.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
CODING_OUTCOME_LEDGER = TMP / "coding-outcome-ledger-current.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "raw_diff_capture_allowed": False,
    "raw_file_content_capture_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "model_ranking_claim_allowed": False,
    "investment_correctness_from_runtime_metrics_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_KEYS = {
    "diff",
    "patch",
    "content",
    "raw_content",
    "prompt",
    "response",
    "tool_input",
    "tool_output",
    "authorization",
    "cookie",
    "api_key",
    "oauth_token",
    "bearer",
    "secret",
    "credential",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def run_git(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return completed.returncode, completed.stdout.strip()


def git_metadata() -> dict[str, Any]:
    short_code, shortstat = run_git(["diff", "--shortstat"])
    name_code, names = run_git(["diff", "--name-status"])
    staged_code, staged = run_git(["diff", "--cached", "--name-status"])
    untracked_code, untracked = run_git(["ls-files", "--others", "--exclude-standard"])
    status_counts: Counter[str] = Counter()
    paths: set[str] = set()
    for text in (names, staged):
        for line in text.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0][:1] if parts else "?"
            status_counts[status] += 1
            if len(parts) > 1:
                paths.add(parts[-1].replace("\\", "/"))
    untracked_paths = [line.strip().replace("\\", "/") for line in untracked.splitlines() if line.strip()]
    return {
        "git_available": short_code == 0 and name_code == 0 and staged_code == 0 and untracked_code == 0,
        "shortstat": shortstat,
        "changed_path_count": len(paths),
        "untracked_path_count": len(untracked_paths),
        "status_counts": dict(sorted(status_counts.items())),
        "sample_paths": sorted(paths)[:25],
        "sample_untracked_paths": sorted(untracked_paths)[:25],
        "captures_raw_diff": False,
    }


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def failure_buckets(*payloads: dict[str, Any]) -> dict[str, int]:
    buckets: Counter[str] = Counter()
    for payload in payloads:
        for step in as_list(payload.get("steps")):
            if not isinstance(step, dict):
                continue
            ok = step.get("ok")
            status = step.get("status")
            if ok is False or status == "blocked":
                name = str(step.get("name") or "unknown")
                if "compile" in name:
                    buckets["compile"] += 1
                elif "test" in name:
                    buckets["test"] += 1
                elif "otel" in name:
                    buckets["otel"] += 1
                elif "closeout" in name:
                    buckets["closeout"] += 1
                else:
                    buckets["validator_or_command"] += 1
    return dict(sorted(buckets.items()))


def build_probe() -> dict[str, Any]:
    changed = as_dict(load_json_artifact(CHANGED_FILE_ROUTER))
    timing = as_dict(load_json_artifact(VALIDATOR_TIMING))
    closeout = as_dict(load_json_artifact(REPEATABLE_CLOSEOUT))
    wf74 = as_dict(load_json_artifact(WF74_RUNNER))
    ledger = as_dict(load_json_artifact(MODEL_LEARNING_LEDGER))
    coding_outcome = as_dict(load_json_artifact(CODING_OUTCOME_LEDGER))

    changed_summary = as_dict(changed.get("summary"))
    timing_summary = as_dict(timing.get("summary"))
    closeout_summary = as_dict(closeout.get("summary"))
    wf74_summary = as_dict(wf74.get("summary"))
    ledger_summary = as_dict(ledger.get("summary"))
    coding_outcome_summary = as_dict(coding_outcome.get("ledger_summary"))
    timing_failed = as_list(timing_summary.get("failed_commands"))
    closeout_failed = as_list(closeout_summary.get("failed_steps"))
    wf74_blocked = int(as_num(wf74_summary.get("steps_blocked")))
    failure_counts = failure_buckets(timing, closeout, wf74)
    rework_required = bool(timing_failed or closeout_failed or wf74_blocked or failure_counts)
    first_pass_clean = not rework_required

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Metadata-only coding-runtime KPI probe for implementation learning, validator selection, PM monitoring, and WF74 scoring.",
        "source_status": [
            source_status(CHANGED_FILE_ROUTER),
            source_status(VALIDATOR_TIMING),
            source_status(REPEATABLE_CLOSEOUT),
            source_status(WF74_RUNNER),
            source_status(MODEL_LEARNING_LEDGER),
            source_status(CODING_OUTCOME_LEDGER),
        ],
        "git_metadata": git_metadata(),
        "kpis": {
            "changed_file_router_status": changed.get("status"),
            "changed_path_count": changed_summary.get("changed_path_count"),
            "recommended_budget": changed_summary.get("recommended_budget"),
            "recommended_validator_count": changed_summary.get("recommendation_count"),
            "validator_timing_status": timing.get("status"),
            "validator_profile": timing.get("profile"),
            "validator_elapsed_seconds": timing_summary.get("elapsed_seconds"),
            "validator_target_seconds": timing_summary.get("target_seconds"),
            "validator_slow": timing_summary.get("slow"),
            "validator_failed_count": len(timing_failed),
            "closeout_status": closeout.get("status"),
            "closeout_steps_run": closeout_summary.get("steps_run"),
            "closeout_failed_count": len(closeout_failed),
            "wf74_status": wf74.get("status"),
            "wf74_steps_ok": wf74_summary.get("steps_ok"),
            "wf74_steps_blocked": wf74_summary.get("steps_blocked"),
            "learning_coding_rows": ledger_summary.get("coding_rows"),
            "learning_coding_outcome_rows": ledger_summary.get("coding_outcome_rows"),
            "learning_runtime_otel_rows": ledger_summary.get("runtime_otel_rows"),
            "learning_privacy_scan_status": ledger_summary.get("privacy_scan_status"),
            "coding_outcome_ledger_rows": coding_outcome_summary.get("ledger_row_count"),
            "coding_outcome_run_attributed_count": coding_outcome_summary.get("run_attributed_count"),
            "coding_outcome_session_attributed_count": coding_outcome_summary.get("session_attributed_count"),
            "coding_outcome_model_attributed_count": coding_outcome_summary.get("model_attributed_count"),
            "coding_outcome_validator_proxy_passed_count": coding_outcome_summary.get("validator_proxy_passed_count"),
            "coding_outcome_total_retry_count": coding_outcome_summary.get("total_retry_count"),
            "first_pass_validation_clean": first_pass_clean,
            "rework_required": rework_required,
            "failure_bucket_counts": failure_counts,
        },
        "scoring_use": {
            "validator_selection": "Use budget/recommendation counts and failure buckets to tune future proof paths.",
            "implementation_quality": "Use first-pass clean rate, closeout status, and rework flags for coding workflow quality.",
            "performance_control": "Use validator elapsed/target/slow fields to avoid unnecessary proof drag.",
            "pm_monitoring": "Expose KPI status and rework/failure state in PM control packet.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "limits": [
            "Git metadata is counts/status/sample-paths only; raw diffs and file contents are not captured.",
            "A dirty worktree can inflate changed-path counts; use trends and failure categories more than one-off path counts.",
            "Coding KPIs are workflow evidence, not model ranking, finance correctness, or execution authority.",
        ],
    }


def privacy_scan(value: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                lowered = str(key).lower()
                if lowered in FORBIDDEN_KEYS:
                    findings.append({"path": f"{path}.{key}", "reason": "forbidden key"})
                walk(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")

    walk(value, "probe")
    return findings


def validate(probe: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(probe.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    findings = privacy_scan(probe)
    if findings:
        errors.append(f"privacy scan found forbidden keys: {len(findings)}")
    if as_dict(probe.get("kpis")).get("learning_privacy_scan_status") not in {"ok", None}:
        errors.append("learning ledger privacy scan is not ok")
    if as_dict(probe.get("git_metadata")).get("changed_path_count", 0) and as_dict(probe.get("git_metadata")).get("changed_path_count", 0) > 250:
        warnings.append("large dirty worktree; changed-path count is context, not a single-session KPI")
    return {"status": "failed" if errors else "ok", "errors": errors, "warnings": warnings, "privacy_findings": findings[:25]}


def render_md(probe: dict[str, Any]) -> str:
    kpis = as_dict(probe.get("kpis"))
    git = as_dict(probe.get("git_metadata"))
    lines = [
        "# Coding Runtime KPI Probe",
        "",
        f"- Generated: {probe.get('generated_at_utc')}",
        f"- Status: {probe.get('status')}",
        f"- Changed paths: {kpis.get('changed_path_count')} (git metadata count: {git.get('changed_path_count')})",
        f"- Recommended budget: {kpis.get('recommended_budget')}",
        f"- Validator elapsed: {kpis.get('validator_elapsed_seconds')}s / target {kpis.get('validator_target_seconds')}s",
        f"- Closeout status: {kpis.get('closeout_status')}",
        f"- First-pass clean: {kpis.get('first_pass_validation_clean')}",
        f"- Rework required: {kpis.get('rework_required')}",
        f"- Failure buckets: `{json.dumps(kpis.get('failure_bucket_counts'), sort_keys=True)}`",
        f"- Learning rows: coding={kpis.get('learning_coding_rows')}, coding_outcome={kpis.get('learning_coding_outcome_rows')}, runtime_otel={kpis.get('learning_runtime_otel_rows')}",
        f"- Coding outcome ledger rows: {kpis.get('coding_outcome_ledger_rows')} session-attributed={kpis.get('coding_outcome_session_attributed_count')}",
        "",
        "## Limits",
    ]
    for item in as_list(probe.get("limits")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(OUT_JSON))
    args = parser.parse_args(argv)

    probe = build_probe()
    validation = validate(probe)
    probe["validation"] = validation
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, probe)
    if args.write_md:
        atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(probe))
    if args.validate:
        print(json.dumps({"status": validation["status"], "json": rel(out), "errors": validation["errors"], "warnings": validation["warnings"]}, indent=2))
        return 1 if validation["errors"] else 0
    if not args.write and not args.write_md:
        print(json.dumps(probe, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
