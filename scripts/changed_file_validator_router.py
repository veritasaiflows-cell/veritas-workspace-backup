#!/usr/bin/env python3
"""Recommend the smallest honest validator set for the current diff.

This is a routing surface, not an executor. It maps changed files to validation
budgets so routine control-plane edits do not automatically pay DB lifecycle or
WF75 major closeout costs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "changed-file-validator-router.json"

SCHEMA = "veritas.changed_file_validator_router.v1"
IGNORED_PREFIXES = (
    "tmp/",
    "state/workflows/",
    ".pytest_cache/",
    "__pycache__/",
)

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "recommendation_only": True,
    "executes_validators": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

BUDGET_RANK = {"micro": 0, "narrow": 1, "shared": 2, "major": 3}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def run_git(args: list[str]) -> tuple[int, list[str], str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    lines = [normalize(line) for line in proc.stdout.splitlines() if line.strip()]
    return proc.returncode, lines, proc.stderr.strip()


def current_diff_paths(base: str, include_untracked: bool) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    code, changed, err = run_git(["diff", "--name-only", base, "--"])
    if code != 0:
        warnings.append(f"git_diff_failed:{err[:200]}")
        changed = []
    code, staged, err = run_git(["diff", "--cached", "--name-only", "--"])
    if code != 0:
        warnings.append(f"git_diff_cached_failed:{err[:200]}")
        staged = []
    paths = set(changed + staged)
    if include_untracked:
        code, untracked, err = run_git(["ls-files", "--others", "--exclude-standard"])
        if code != 0:
            warnings.append(f"git_untracked_failed:{err[:200]}")
        else:
            paths.update(untracked)
    return sorted(paths), warnings


def ignored(path: str) -> bool:
    return path.startswith(IGNORED_PREFIXES) or "/__pycache__/" in path or path.endswith(".pyc")


def command(command: str, budget: str, reason: str) -> dict[str, Any]:
    return {"command": command, "budget": budget, "reason": reason}


def classify_path(path: str) -> list[dict[str, Any]]:
    p = normalize(path)
    recs: list[dict[str, Any]] = []
    if ignored(p):
        return recs
    if p.endswith(".py") and p.startswith("scripts/"):
        recs.append(command("python -m py_compile <changed-python-files>", "micro", "changed Python script"))
    if p in {
        "scripts/pm_control_packet.py",
        "scripts/lib/pm_control_reader.py",
        "scripts/pm_sidecar_retirement_guard.py",
    } or "pm_" in Path(p).name:
        recs.append(command("python scripts\\pm_control_packet.py --write --write-db --validate", "narrow", "PM control surface changed"))
        recs.append(command("python scripts\\pm_sidecar_retirement_guard.py --write --validate", "narrow", "PM compatibility/sidecar guard changed or may drift"))
    if p.startswith("scripts/cron_") or p in {"scripts/escalation_trigger.py", "scripts/cron_control_packet.py"}:
        recs.append(command("python scripts\\cron_control_packet.py --write --validate", "narrow", "cron control surface changed"))
    if "otel" in p.lower() or p in {
        "scripts/model_quality_scorecard.py",
        "scripts/model_run_ledger.py",
        "scripts/finance_recommendation_correctness_ledger.py",
        "scripts/wf74_model_quality_collection_cron_runner.py",
        "scripts/wf74_cron_duplication_audit.py",
        "scripts/training_dataset_candidate_builder.py",
    }:
        recs.append(command("python scripts\\otel_ops_control.py --write --write-db --validate", "narrow", "OTEL/model-quality telemetry surface changed"))
        recs.append(command("python scripts\\wf74_cron_duplication_audit.py --write --validate", "narrow", "WF74 cron duplication guard may drift"))
        recs.append(command("python scripts\\wf74_model_quality_collection_cron_runner.py --write --validate --include-harness", "shared", "WF74 model-quality collection chain may drift"))
        recs.append(command("python scripts\\model_quality_scorecard.py --write --validate", "narrow", "WF74 model-quality telemetry consumer may drift"))
        recs.append(command("python scripts\\training_dataset_candidate_builder.py --write --write-md --validate", "shared", "training/eval candidate safety contract may drift"))
    if p in {
        "scripts/workflow_router.py",
        "scripts/workflow_routing_index.py",
        "scripts/lib/workflow_control.py",
        "state/workflow-control-overrides.json",
    }:
        recs.append(command("python scripts\\workflow_router.py --all --write-capsules --validate", "shared", "workflow route/capsule contract changed"))
    if p in {
        "TOOLS.md",
        "AGENTS.md",
        "SOUL.md",
        "USER.md",
        "scripts/future_session_enhancement_packet.py",
    } or p.startswith("06. Playbooks/Startup Truth Index"):
        recs.append(command("python scripts\\boot_surface_size_guard.py --write --validate", "narrow", "boot/front-door surface changed"))
        recs.append(command("python scripts\\workflow_hygiene_check.py --write --validate", "narrow", "boot/workflow hygiene may drift"))
    if p == "scripts/future_session_enhancement_packet.py":
        recs.append(command("python scripts\\future_session_enhancement_packet.py --write --write-md --validate", "narrow", "future-session startup packet changed"))
    if p == "scripts/skill_git_checkpoint.py" or p.startswith("skills/") or p == "06. Playbooks/Skills Governance Index.md":
        recs.append(command("python scripts\\skill_git_checkpoint.py --write --validate", "narrow", "skill-layer git checkpoint coverage may drift"))
        recs.append(command("openclaw skills check", "narrow", "workspace skill surface changed"))
    if p.startswith("scripts/") and ("closeout" in p or "validator" in p or "fast_path" in p):
        recs.append(command("python scripts\\fast_path_qa.py --write --validate --no-probes", "narrow", "validator or fast-path surface changed"))
        recs.append(command("python scripts\\repeatable_work_closeout.py --validation-budget narrow --write --validate", "shared", "closeout contract changed"))
    if p.startswith("scripts/") and ("db_lifecycle" in p or "sql" in p.lower() or "sqlite" in p.lower()):
        recs.append(command("python scripts\\db_lifecycle_manifest.py --write --validate", "major", "DB/SQL lifecycle surface changed"))
    if "wf75" in p.lower() or "retail" in p.lower():
        recs.append(command("python scripts\\wf75_closeout_refresh.py --mode handoff-only --validation-budget shared --write --validate", "shared", "WF75/Retail control surface changed"))
    if p.startswith("scripts/") and ("finance" in p.lower() or "ticker" in p.lower() or "portfolio" in p.lower()):
        recs.append(command("python scripts\\truth_surface_inventory.py --write --validate", "shared", "finance/ticker truth-surface route changed"))
    return recs


def dedupe_recommendations(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_command: dict[str, dict[str, Any]] = {}
    for rec in recommendations:
        key = rec["command"]
        existing = by_command.get(key)
        if not existing or BUDGET_RANK[rec["budget"]] > BUDGET_RANK[existing["budget"]]:
            by_command[key] = dict(rec)
        elif existing:
            reasons = {existing["reason"], rec["reason"]}
            existing["reason"] = "; ".join(sorted(reasons))
    return sorted(by_command.values(), key=lambda item: (BUDGET_RANK[item["budget"]], item["command"]))


def py_compile_command(paths: list[str]) -> str | None:
    py_paths = [p.replace("/", "\\") for p in paths if p.startswith("scripts/") and p.endswith(".py") and not ignored(p)]
    if not py_paths:
        return None
    joined = " ".join(f'"{path}"' if " " in path else path for path in sorted(py_paths))
    return f"python -m py_compile {joined}"


def build_payload(base: str, include_untracked: bool, explicit_paths: list[str] | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    raw_paths = [normalize(path) for path in explicit_paths] if explicit_paths else []
    if not raw_paths:
        raw_paths, warnings = current_diff_paths(base, include_untracked)
    paths = sorted(path for path in raw_paths if path and not ignored(path))
    recommendations: list[dict[str, Any]] = []
    for path in paths:
        recommendations.extend(classify_path(path))
    compile_cmd = py_compile_command(paths)
    if compile_cmd:
        recommendations = [rec for rec in recommendations if rec["command"] != "python -m py_compile <changed-python-files>"]
        recommendations.append(command(compile_cmd, "micro", "compile changed Python scripts"))
    recommendations = dedupe_recommendations(recommendations)
    max_budget = "micro"
    for rec in recommendations:
        if BUDGET_RANK[rec["budget"]] > BUDGET_RANK[max_budget]:
            max_budget = rec["budget"]
    if len(paths) > 40:
        warnings.append(f"large_diff_path_count:{len(paths)}")
    if any(path.startswith("tmp/") for path in raw_paths):
        warnings.append("tmp_artifacts_ignored_for_budget")
    if not recommendations:
        recommendations.append(command("python scripts\\changed_file_validator_router.py --write --validate", "micro", "router self-check only"))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "base": base,
        "include_untracked": include_untracked,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "changed_path_count": len(paths),
            "recommendation_count": len(recommendations),
            "recommended_budget": max_budget,
            "heavy_validators_reserved": [
                "db_lifecycle_manifest.py --write --validate",
                "wf75_closeout_refresh.py --mode handoff-only --validation-budget major --write --validate",
            ],
            "next_safe_action": "Run the recommended commands at or below the recommended budget; escalate only when exact changed paths justify it.",
        },
        "changed_paths": paths,
        "recommendations": recommendations,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": warnings,
        },
        "stop_lines": [
            "This router recommends validation only. It does not execute validators, mutate source truth, alter cron/runtime/config, change accounts, or infer approval.",
        ],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Route changed files to the smallest honest validator budget.")
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--no-untracked", action="store_false", dest="include_untracked")
    parser.add_argument("--path", action="append", dest="paths", help="Explicit path to classify; may be repeated.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload(args.base, args.include_untracked, args.paths)
    if args.write:
        atomic_write_json(args.out, payload)
        print(f"wrote {rel(args.out)} status={payload['status']} budget={payload['summary']['recommended_budget']} paths={payload['summary']['changed_path_count']}")
    else:
        print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
