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
        "scripts/pm_implementation_job_queue.py",
        "scripts/test_pm_implementation_job_queue_control_packet_preference.py",
        "scripts/lib/pm_control_reader.py",
        "scripts/pm_sidecar_retirement_guard.py",
    } or "pm_" in Path(p).name:
        if p in {
            "scripts/pm_implementation_job_queue.py",
            "scripts/test_pm_implementation_job_queue_control_packet_preference.py",
        }:
            recs.append(command("python scripts\\test_pm_implementation_job_queue_control_packet_preference.py", "narrow", "PM implementation queue must prefer consolidated control packet over stale legacy sidecars"))
            recs.append(command("python scripts\\pm_implementation_job_queue.py --write --write-db --validate", "narrow", "PM implementation queue sidecar may drift from control packet"))
        recs.append(command("python scripts\\pm_control_packet.py --write --write-db --validate", "narrow", "PM control surface changed"))
        recs.append(command("python scripts\\pm_sidecar_retirement_guard.py --write --validate", "narrow", "PM compatibility/sidecar guard changed or may drift"))
    if p.startswith("scripts/cron_") or p in {"scripts/escalation_trigger.py", "scripts/cron_control_packet.py"}:
        recs.append(command("python scripts\\cron_control_packet.py --write --validate", "narrow", "cron control surface changed"))
    if p.startswith("state/cron-contracts/") or p == "scripts/cron_contract_validator.py":
        recs.append(command("python scripts\\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate", "narrow", "cron intended-contract drift route changed"))
        recs.append(command("python scripts\\cron_control_packet.py --write --validate", "narrow", "cron contract changes should preserve cron control visibility"))
    if p in {
        "scripts/market_state_refresh.py",
        "scripts/market_today_answer_packet.py",
        "scripts/test_market_today_answer_packet.py",
    }:
        recs.append(command("python scripts\\market_state_refresh.py", "shared", "market-state broad-index/rates contract changed"))
        recs.append(command("python scripts\\market_today_answer_packet.py --write --validate", "shared", "market-day answer packet contract changed"))
        recs.append(command("python scripts\\test_market_today_answer_packet.py", "narrow", "market-day answer packet regression may drift"))
        recs.append(command("python scripts\\post_close_control_digest.py --write --validate", "shared", "post-close digest consumes market-day answer packet"))
        recs.append(command("python scripts\\cron_control_packet.py --write --validate", "shared", "cron freshness consumes market-day answer packet"))
    if p.startswith("scripts/") and (
        "wf78" in p.lower()
        or "wf67" in p.lower()
        or "canonical_finance_data_plane" in p.lower()
        or "cache_dependency_manifest" in p.lower()
        or "finance_intelligence_state" in p.lower()
        or "trade_grade_decision_os" in p.lower()
        or "trade_grade_decision_cards" in p.lower()
        or "trade_grade_full_answer_assembler" in p.lower()
        or "test_trade_grade_full_answer_macro_context" in p.lower()
        or "trade_grade_repair_conveyor" in p.lower()
        or "tier_ab_band_freshness_cron_guard" in p.lower()
        or "post_close_final_quote_ledger" in p.lower()
        or "paper_deployment" in p.lower()
        or "wf85_paper_deployment" in p.lower()
        or "decision_sync_spine" in p.lower()
        or "band_hygiene_freshness" in p.lower()
        or "auto_apply_entry_band" in p.lower()
        or "entry_band" in p.lower()
        or "paper-readiness" in p.lower()
    ):
        if "wf78_missing_band_context_repair" in p.lower():
            recs.append(command("python scripts\\test_wf78_missing_band_context_repair_policy.py", "narrow", "Tier A/B decision-grade band coverage policy may drift"))
            recs.append(command("python scripts\\wf78_missing_band_context_repair.py --write --validate", "shared", "WF78 Tier A/B missing band-context repair changed"))
        if "tier_ab_band_freshness_cron_guard" in p.lower():
            recs.append(command("python scripts\\test_tier_ab_band_freshness_cron_guard.py", "narrow", "Tier A/B band freshness cron guard may drift"))
            recs.append(command("python scripts\\tier_ab_band_freshness_cron_guard.py --write --validate", "shared", "Tier A/B band freshness cron guard changed"))
        if "wf85_paper_deployment" in p.lower():
            recs.append(command("python scripts\\test_wf85_paper_deployment_notification_digest.py", "narrow", "WF85 paper deployment digest boundary may drift"))
            recs.append(command("python scripts\\test_wf85_paper_deployment_telegram_notifier.py", "narrow", "WF85 Telegram radar delivery boundary may drift"))
            recs.append(command("python scripts\\wf85_paper_deployment_telegram_cron_runner.py --write --validate", "shared", "WF85 paper deployment Telegram radar cron proof may drift"))
        if "post_close_final_quote_ledger" in p.lower():
            recs.append(command("python scripts\\post_close_final_quote_ledger.py --write --validate", "shared", "post-close quote overlay target coverage may drift"))
            recs.append(command("python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate", "shared", "WF84 post-close overlay parity may drift"))
        recs.append(command("python scripts\\truth_surface_inventory.py --write --validate", "shared", "WF78/WF67 paper recommendation truth surface changed"))
        recs.append(command("python scripts\\cron_control_packet.py --write --validate", "narrow", "WF78/WF67 paper recommendation cron surface may drift"))
    if p.startswith("scripts/") and "canonical_finance_data_plane" in p.lower():
        recs.append(command("python scripts\\canonical_finance_data_plane_contract.py --write --validate", "shared", "WF84 canonical finance data-plane contract changed"))
        recs.append(command("python scripts\\canonical_finance_data_plane.py --write --write-db --validate", "major", "WF84 canonical finance data-plane packet/SQLite writer changed"))
        recs.append(command("python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate", "shared", "WF84 duplicate-surface retirement readiness proof changed"))
        recs.append(command("python scripts\\db_lifecycle_manifest.py --write --validate", "major", "WF84 SQLite companion lifecycle classification must remain explicit"))
        recs.append(command("python scripts\\workflow_router.py WF84 --answer all --validate", "shared", "WF84 route/capsule contract may drift"))
    if p.startswith("scripts/") and (
        "cache_dependency_manifest" in p.lower()
        or "finance_intelligence_state" in p.lower()
        or "auto_apply_entry_band" in p.lower()
    ):
        recs.append(command("python scripts\\test_finance_intelligence_state_wf72_guard.py", "narrow", "WF72 support-only finance-answer guard may drift"))
        recs.append(command("python scripts\\cache_dependency_manifest.py --write --validate", "shared", "finance cache dependency/stale-read guard changed"))
    if p.startswith("scripts/") and (
        "trade_grade_decision_os" in p.lower()
        or "trade_grade_decision_cards" in p.lower()
        or "trade_grade_full_answer_assembler" in p.lower()
        or "test_trade_grade_full_answer_macro_context" in p.lower()
        or "trade_grade_repair_conveyor" in p.lower()
        or "tier_ab_band_freshness_cron_guard" in p.lower()
    ):
        recs.append(command("python scripts\\trade_grade_decision_os_contract.py --write --validate", "shared", "WF85 trade-grade decision OS contract changed"))
        recs.append(command("python scripts\\trade_grade_decision_cards.py --write --validate", "shared", "WF85 Phase 1 decision-card builder/gate family changed"))
        recs.append(command("python scripts\\test_trade_grade_full_answer_macro_context.py", "narrow", "WF85 full-answer macro/CPI context may drift"))
        recs.append(command("python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate", "shared", "WF85 full-answer assembler changed"))
        recs.append(command("python scripts\\test_trade_grade_repair_conveyor_scope.py", "narrow", "WF85 repair-conveyor finance-domain blocker scope may drift"))
        recs.append(command("python scripts\\test_wf78_missing_band_context_repair_policy.py", "narrow", "Tier A/B decision-grade band coverage policy may drift"))
        recs.append(command("python scripts\\test_tier_ab_band_freshness_cron_guard.py", "narrow", "Tier A/B band freshness cron guard may drift"))
        recs.append(command("python scripts\\tier_ab_band_freshness_cron_guard.py --write --validate", "shared", "Tier A/B band freshness cron guard may drift"))
        recs.append(command("python scripts\\trade_grade_repair_conveyor.py --write --validate", "shared", "WF85 source/freshness and band/stop repair conveyor changed"))
        recs.append(command("python scripts\\workflow_router.py WF85 --answer all --validate", "shared", "WF85 route/capsule contract may drift"))
        recs.append(command("python scripts\\pm_control_packet.py --write --write-db --validate", "shared", "WF85 PM lane may drift"))
    if p in {
        "scripts/model_quality_scorecard.py",
        "scripts/test_model_quality_scorecard.py",
    }:
        recs.append(command("python scripts\\test_model_quality_scorecard.py", "narrow", "WF74 model-quality scorecard consumer regression may drift"))
        recs.append(command("python scripts\\model_quality_scorecard.py --write --validate", "narrow", "WF74 model-quality scorecard consumer changed"))
        return recs
    if "otel" in p.lower() or "model_quality" in p.lower() or p in {
        "scripts/model_learning_capture_approval_packet.py",
        "scripts/test_model_learning_capture_approval_packet.py",
        "scripts/model_learning_metadata_ledger.py",
        "scripts/test_model_learning_metadata_ledger.py",
        "scripts/otel_runtime_metadata_probe.py",
        "scripts/test_otel_runtime_metadata_probe.py",
        "scripts/coding_runtime_kpi_probe.py",
        "scripts/test_coding_runtime_kpi_probe.py",
        "scripts/finance_response_quality_slice.py",
        "scripts/test_finance_response_quality_slice.py",
        "scripts/model_run_ledger.py",
        "scripts/finance_recommendation_correctness_ledger.py",
        "scripts/wf74_model_quality_collection_cron_runner.py",
        "scripts/wf74_cron_duplication_audit.py",
        "scripts/training_dataset_candidate_builder.py",
    }:
        recs.append(command("python scripts\\test_otel_ops_control.py", "narrow", "OTEL window/compatibility contract may drift"))
        recs.append(command("python scripts\\otel_ops_control.py --write --write-db --multi-window --validate", "narrow", "OTEL/model-quality telemetry surface changed"))
        recs.append(command("python scripts\\wf74_cron_duplication_audit.py --write --validate", "narrow", "WF74 cron duplication guard may drift"))
        recs.append(command("python scripts\\test_model_quality_scorecard.py", "narrow", "WF74 model-quality efficiency-loop regression may drift"))
        recs.append(command("python scripts\\test_model_learning_capture_approval_packet.py", "narrow", "WF74 metadata-only capture approval boundary may drift"))
        recs.append(command("python scripts\\model_learning_capture_approval_packet.py --write --write-md --validate", "narrow", "WF74 metadata-only capture approval packet changed"))
        recs.append(command("python scripts\\test_otel_runtime_metadata_probe.py", "narrow", "WF74 local runtime OTEL metadata/privacy probe may drift"))
        recs.append(command("python scripts\\otel_runtime_metadata_probe.py --write --write-md --validate", "narrow", "WF74 local runtime OTEL metadata/privacy probe changed"))
        recs.append(command("python scripts\\test_coding_runtime_kpi_probe.py", "narrow", "WF74 coding-runtime KPI/privacy probe may drift"))
        recs.append(command("python scripts\\coding_runtime_kpi_probe.py --write --write-md --validate", "narrow", "WF74 coding-runtime KPI probe changed"))
        recs.append(command("python scripts\\test_finance_response_quality_slice.py", "narrow", "internal finance answer-quality slice may drift"))
        recs.append(command("python scripts\\finance_response_quality_slice.py --write --write-md --validate", "narrow", "WF84/WF85 finance response-quality slice changed"))
        recs.append(command("python scripts\\test_model_learning_metadata_ledger.py", "narrow", "WF74 metadata-only model/tool/failure/coding ledger may drift"))
        recs.append(command("python scripts\\model_learning_metadata_ledger.py --write --write-md --validate", "narrow", "WF74 metadata-only model/tool/failure/coding ledger changed"))
        recs.append(command("python scripts\\wf74_model_quality_collection_cron_runner.py --write --validate --include-harness", "shared", "WF74 model-quality collection chain may drift"))
        recs.append(command("python scripts\\model_quality_scorecard.py --write --validate", "narrow", "WF74 model-quality telemetry consumer may drift"))
        recs.append(command("python scripts\\training_dataset_candidate_builder.py --write --write-md --validate", "shared", "training/eval candidate safety contract may drift"))
    if p in {"scripts/full_intelligence_answer_parity.py", "scripts/test_full_intelligence_answer_parity.py"}:
        recs.append(command("python scripts\\test_full_intelligence_answer_parity.py", "narrow", "WF84/WF85 parity semantic drift taxonomy may change"))
        recs.append(command("python scripts\\full_intelligence_answer_parity.py --all --write", "shared", "WF84/WF85 full-answer parity may drift"))
    if p in {
        "scripts/workflow_router.py",
        "scripts/workflow_routing_index.py",
        "scripts/wf73_control_plane_audit.py",
        "scripts/lib/workflow_control.py",
        "state/workflow-control-overrides.json",
    }:
        recs.append(command("python scripts\\workflow_router.py --all --write-capsules --validate", "shared", "workflow route/capsule contract changed"))
    if p in {
        "scripts/wf73_control_plane_audit.py",
        "scripts/workflow_routing_index.py",
        "scripts/fast_path_qa.py",
        "scripts/cron_freshness_spine.py",
        "scripts/pm_control_packet.py",
        "scripts/boot_surface_size_guard.py",
    }:
        recs.append(command("python scripts\\wf73_control_plane_audit.py --write --validate", "shared", "WF73 ordered control-plane audit path changed"))
    if p in {
        "TOOLS.md",
        "AGENTS.md",
        "SOUL.md",
        "USER.md",
        "scripts/future_session_enhancement_packet.py",
        "scripts/startup_brief_packet.py",
        "scripts/test_startup_brief_packet.py",
    } or p.startswith("06. Playbooks/Startup Truth Index"):
        recs.append(command("python scripts\\boot_surface_size_guard.py --write --validate", "narrow", "boot/front-door surface changed"))
        recs.append(command("python scripts\\workflow_hygiene_check.py --write --validate", "narrow", "boot/workflow hygiene may drift"))
    if p == "scripts/future_session_enhancement_packet.py":
        recs.append(command("python scripts\\future_session_enhancement_packet.py --write --write-md --validate", "narrow", "future-session startup packet changed"))
    if p in {"scripts/startup_brief_packet.py", "scripts/test_startup_brief_packet.py"}:
        recs.append(command("python scripts\\test_startup_brief_packet.py", "micro", "fast startup brief packet regression may drift"))
        recs.append(command("python scripts\\startup_brief_packet.py --write --validate", "narrow", "fast startup brief packet changed"))
    if p == "scripts/skill_git_checkpoint.py" or p.startswith("skills/") or p == "06. Playbooks/Skills Governance Index.md":
        recs.append(command("python scripts\\skill_git_checkpoint.py --write --validate", "narrow", "skill-layer git checkpoint coverage may drift"))
        recs.append(command("openclaw skills check", "narrow", "workspace skill surface changed"))
    if p.startswith("scripts/") and ("closeout" in p or "validator" in p or "fast_path" in p or "wf73_control_plane_audit" in p):
        recs.append(command("python scripts\\fast_path_qa.py --write --validate --no-probes", "narrow", "validator or fast-path surface changed"))
        recs.append(command("python scripts\\repeatable_work_closeout.py --validation-budget narrow --write --validate", "shared", "closeout contract changed"))
    if p.startswith("scripts/") and "local_audio_transcriber" in p.lower():
        recs.append(command("python scripts\\test_local_audio_transcriber.py", "narrow", "local audio transcription helper changed"))
    if p in {
        "scripts/macro_signal_spine.py",
        "scripts/test_macro_signal_spine.py",
        "scripts/macro_judgment_draft.py",
    }:
        recs.append(command("python scripts\\test_macro_signal_spine.py", "micro", "macro signal spine deterministic tests changed"))
        recs.append(command("python scripts\\macro_signal_spine.py --write --validate", "narrow", "macro signal spine producer/contract changed"))
        recs.append(command("python scripts\\macro_judgment_draft.py --write --validate", "narrow", "macro judgment consumer changed"))
        recs.append(command("python scripts\\cron_freshness_spine.py --write --validate", "narrow", "macro cron expected-artifact contract may drift"))
        recs.append(command("python scripts\\cron_control_packet.py --write --validate", "narrow", "macro cron control packet may drift"))
    if p in {
        "scripts/sector_expansion_board.py",
        "scripts/test_sector_expansion_board.py",
        "scripts/sector_dashboard_suite.py",
        "scripts/test_sector_dashboard_suite.py",
        "scripts/sector_allocation_decision_matrix.py",
    }:
        recs.append(command("python scripts\\test_sector_expansion_board.py", "micro", "sector board short-term signal contract changed"))
        recs.append(command("python scripts\\sector_expansion_board.py --output tmp\\sector-expansion-board.json", "narrow", "sector board producer changed"))
        recs.append(command("python scripts\\test_sector_dashboard_suite.py", "micro", "sector dashboard rendering contract changed"))
        recs.append(command("python scripts\\sector_dashboard_suite.py --input tmp\\sector-expansion-board.json --output tmp\\sector-dashboard-suite.html", "narrow", "sector dashboard consumer changed"))
        recs.append(command("python scripts\\sector_allocation_decision_matrix.py --write --validate", "narrow", "sector allocation recommendation matrix changed"))
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
