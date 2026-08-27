#!/usr/bin/env python3
"""Ingest closed-loop WF74 outcomes into local review eval cases.

This is append-only and review-gated: it turns already-generated proof packets
into small labeled regression cases. It does not apply improvements, mutate
runtime config, or store raw prompts/model outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import wf74_learning_loop_eval_harness as eval_harness
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"

DEFAULT_CASES = DATA / "wf74-learning-loop-evals" / "cases.json"
DEFAULT_JSON = TMP / "wf74-feedback-ingest.json"
DEFAULT_IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
DEFAULT_WF88 = TMP / "wf88-os2-control-packet.json"
DEFAULT_FINANCE_QUALITY = TMP / "finance-response-quality-slice.json"
DEFAULT_RECURRENCE_GUARD = TMP / "wf78-source-open-recurrence-guard.json"
DEFAULT_PROMPT_LEDGER = TMP / "wf74-prompt-variant-ledger.json"

SCHEMA = "veritas.wf74_outcome_feedback_ingest.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "append_only": True,
    "eval_case_append_allowed": True,
    "raw_prompt_or_response_capture_allowed": False,
    "raw_tool_payload_capture_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
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


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def stable_hash(value: Any, length: int = 16) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def load_cases(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {"schema": "veritas.wf74_learning_loop_eval_cases.v1", "cases": []}


def recurrence_guard_clean(finance_quality: dict[str, Any], recurrence_guard: dict[str, Any]) -> bool:
    finance_summary = as_dict(finance_quality.get("summary"))
    guard_summary = as_dict(recurrence_guard.get("summary"))
    return all((
        finance_quality.get("status") == "ok",
        recurrence_guard.get("status") == "ok",
        as_int(finance_summary.get("source_open_blocked_count")) == 0,
        as_int(finance_summary.get("source_freshness_blocked_count")) == 0,
        as_int(guard_summary.get("source_open_step_order_error_count")) == 0,
    ))


def build_candidate_cases(
    improvement_ledger: dict[str, Any],
    wf88: dict[str, Any],
    finance_quality: dict[str, Any],
    recurrence_guard: dict[str, Any],
    prompt_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    improvement_summary = as_dict(improvement_ledger.get("summary"))
    wf88_summary = as_dict(wf88.get("summary"))
    prompt_summary = as_dict(prompt_ledger.get("summary"))

    if recurrence_guard_clean(finance_quality, recurrence_guard):
        candidates.append({
            "case_id": "wf74_source_open_recurrence_guard_clean_proof",
            "title": "Source-open recurrence guard clean proof should stay proof-refresh routed",
            "item": {
                "source_kind": "outcome_feedback",
                "source_id": "wf74-source-open-recurrence-guard",
                "category": "workflow_maturity",
                "title": "WF74 source-open recurrence guard proof is clean after hard producer ordering",
                "priority": 72,
                "next_action": "Keep the recurrence guard in daily proof and rerun if source-open/freshness blockers reappear.",
                "details": "proof clean; finance response-quality source_open/source_freshness blockers are zero; review-only recurrence prevention",
            },
            "context": {
                "cron": {"blocked_count": 0, "escalation_signal_count": 0, "stale_count": 0}
            },
            "expected_action_state": "proof_refresh",
        })

    if as_int(improvement_summary.get("unclassified_closed_followup_count")) == 0:
        candidates.append({
            "case_id": "wf74_closed_improvements_need_successor_artifact_or_class",
            "title": "Closed improvement rows must carry successor or durable follow-up classification",
            "item": {
                "source_kind": "outcome_feedback",
                "source_id": "closed-followup-classification",
                "category": "workflow_maturity",
                "title": "Improvement ledger closure proof has no unclassified closed follow-ups",
                "priority": 64,
                "next_action": "Refresh improvement-ledger proof when closure rows lack successor artifacts or durable follow-up class.",
                "details": "proof outcome feedback; no unclassified closed follow-up rows; successor artifact discipline",
            },
            "context": {
                "cron": {"blocked_count": 0, "escalation_signal_count": 0, "stale_count": 0}
            },
            "expected_action_state": "proof_refresh",
        })

    if prompt_summary.get("current_prompt_id") and as_int(prompt_summary.get("auto_apply_count")) == 0:
        candidates.append({
            "case_id": "wf74_self_prompt_variant_metadata_only",
            "title": "Self-review variants are metadata-only review signals",
            "item": {
                "source_kind": "outcome_feedback",
                "source_id": "self-review-variant-ledger",
                "category": "workflow_maturity",
                "title": "Self-review variant ledger records metadata-only proof without auto-apply",
                "priority": 58,
                "next_action": "Use review-variant metadata to compare proposal outcomes; do not store raw text or apply changes automatically.",
                "details": "proof metadata-only; review identifiers only; no content capture",
            },
            "context": {
                "cron": {"blocked_count": 0, "escalation_signal_count": 0, "stale_count": 0}
            },
            "expected_action_state": "proof_refresh",
        })

    if as_int(wf88_summary.get("delete_ready_count")) == 0:
        candidates.append({
            "case_id": "wf88_delete_readiness_zero_stays_monitor_only",
            "title": "WF88 zero delete readiness should not create cleanup implementation work",
            "item": {
                "source_kind": "outcome_feedback",
                "source_id": "wf88-delete-readiness-zero",
                "category": "os2_cleanup",
                "title": "WF88 delete readiness is zero and should remain monitor-only",
                "priority": 42,
                "next_action": "Monitor; do not create destructive cleanup work without exact approval and ready delete packet.",
                "details": "delete readiness zero; no destructive/archive authority",
            },
            "context": {
                "cron": {"blocked_count": 0, "escalation_signal_count": 0, "stale_count": 0}
            },
            "expected_action_state": "monitor_only",
        })

    return candidates


def validate_cases(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    results = [eval_harness.run_case(case) for case in cases]
    errors = [
        f"candidate_case_failed:{row.get('case_id')}:{row.get('actual_action_state')}!={row.get('expected_action_state')}"
        for row in results
        if not row.get("passed")
    ]
    return results, errors


def merge_cases(existing_payload: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    existing_cases = [case for case in as_list(existing_payload.get("cases")) if isinstance(case, dict)]
    existing_ids = {str(case.get("case_id")) for case in existing_cases if case.get("case_id")}
    append_cases = [case for case in candidates if str(case.get("case_id")) not in existing_ids]
    merged = dict(existing_payload)
    merged.setdefault("schema", "veritas.wf74_learning_loop_eval_cases.v1")
    merged.setdefault("purpose", "Local regression cases for WF74 V2 review/routing classification.")
    merged["generated_at_utc"] = utc_now()
    merged["cases"] = [*existing_cases, *append_cases]
    return merged, append_cases


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    if not as_list(payload.get("candidate_cases")):
        warnings.append("no_candidate_cases")
    if as_list(payload.get("candidate_validation_errors")):
        errors.extend(str(error) for error in as_list(payload.get("candidate_validation_errors")))
    for flag in (
        "raw_prompt_or_response_capture_allowed",
        "raw_tool_payload_capture_allowed",
        "code_mutation_allowed",
        "skill_application_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary_not_false:{flag}")
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    cases_path = workspace_path(args.cases, DEFAULT_CASES)
    improvement_path = workspace_path(args.improvement_ledger, DEFAULT_IMPROVEMENT_LEDGER)
    wf88_path = workspace_path(args.wf88_control, DEFAULT_WF88)
    finance_quality_path = workspace_path(args.finance_quality, DEFAULT_FINANCE_QUALITY)
    recurrence_guard_path = workspace_path(args.recurrence_guard, DEFAULT_RECURRENCE_GUARD)
    prompt_ledger_path = workspace_path(args.prompt_ledger, DEFAULT_PROMPT_LEDGER)

    existing_cases_payload = load_cases(cases_path)
    candidates = build_candidate_cases(
        as_dict(load_json_artifact(improvement_path)),
        as_dict(load_json_artifact(wf88_path)),
        as_dict(load_json_artifact(finance_quality_path)),
        as_dict(load_json_artifact(recurrence_guard_path)),
        as_dict(load_json_artifact(prompt_ledger_path)),
    )
    candidate_results, candidate_errors = validate_cases(candidates)
    merged_cases_payload, append_cases = merge_cases(existing_cases_payload, candidates)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Append reviewed outcome feedback cases into the WF74 local eval suite.",
        "source_artifacts": [
            rel(improvement_path),
            rel(wf88_path),
            rel(finance_quality_path),
            rel(recurrence_guard_path),
            rel(prompt_ledger_path),
        ],
        "cases_path": rel(cases_path),
        "summary": {
            "existing_case_count": len(as_list(existing_cases_payload.get("cases"))),
            "candidate_case_count": len(candidates),
            "append_case_count": len(append_cases),
            "merged_case_count": len(as_list(merged_cases_payload.get("cases"))),
            "append_case_ids": [case.get("case_id") for case in append_cases],
        },
        "candidate_cases": candidates,
        "candidate_results": candidate_results,
        "candidate_validation_errors": candidate_errors,
        "append_cases": append_cases,
        "merged_cases_payload_hash": stable_hash(merged_cases_payload, 24),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["errors"]:
        payload["status"] = "blocked"
    payload["_merged_cases_payload"] = merged_cases_payload
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append WF74 outcome feedback into local eval cases.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--out", default=str(DEFAULT_JSON))
    parser.add_argument("--improvement-ledger", default=str(DEFAULT_IMPROVEMENT_LEDGER))
    parser.add_argument("--wf88-control", default=str(DEFAULT_WF88))
    parser.add_argument("--finance-quality", default=str(DEFAULT_FINANCE_QUALITY))
    parser.add_argument("--recurrence-guard", default=str(DEFAULT_RECURRENCE_GUARD))
    parser.add_argument("--prompt-ledger", default=str(DEFAULT_PROMPT_LEDGER))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out = workspace_path(args.out, DEFAULT_JSON)
    cases_path = workspace_path(args.cases, DEFAULT_CASES)
    merged = payload.pop("_merged_cases_payload")
    if args.write and payload["validation"]["status"] in {"ok", "warning"}:
        atomic_write_json(cases_path, merged)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
        "write_result": {"out": rel(out), "cases": rel(cases_path)} if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and payload.get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
