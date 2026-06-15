#!/usr/bin/env python3
"""Build local review-only candidates for future eval/fine-tune datasets.

This script never exports data, uploads files, calls model training APIs, or
captures raw prompts. It turns existing proof artifacts into metadata-only
candidate rows so a later human-gated process can decide what is safe to use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
MEMORY = ROOT / "memory"
OUT = TMP / "training-dataset-candidates.json"
SCHEMA = "veritas.training_dataset_candidate_builder.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "raw_prompt_capture_allowed": False,
    "raw_chat_capture_allowed": False,
    "secret_or_credential_capture_allowed": False,
    "external_upload_allowed": False,
    "training_or_finetune_call_allowed": False,
    "model_weight_mutation_allowed": False,
    "model_ranking_claim": False,
    "wf55_outcome_grade_assignment_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

SOURCE_ARTIFACTS = [
    "tmp/wf74-model-quality-collection-cron-runner.json",
    "tmp/future-session-enhancement-packet.json",
    "tmp/wf74-cron-duplication-audit.json",
    "tmp/model-run-ledger-current.json",
    "tmp/finance-recommendation-correctness-ledger-current.json",
    "tmp/model-quality-scorecard.json",
    "tmp/veritas-harness-scorecard.json",
    "tmp/changed-file-validator-router.json",
    "tmp/control-closeout-bundle.json",
    "tmp/repeatable-work-closeout.json",
    "tmp/cron-control-packet.json",
]

SENSITIVE_HINTS = re.compile(
    r"(api[_-]?key|secret|password|credential|oauth|bearer|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)


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


def stable_id(*parts: Any) -> str:
    text = "|".join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def source_state(path: str) -> dict[str, Any]:
    full = ROOT / path
    data = as_dict(load_json_artifact(full))
    validation = as_dict(data.get("validation"))
    try:
        stat = full.stat()
    except FileNotFoundError:
        return {"path": path, "exists": False}
    return {
        "path": path,
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "schema": data.get("schema") or data.get("schema_version"),
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def candidate_base(
    *,
    source_path: str,
    evidence_type: str,
    task_family: str,
    item_key: str,
    generated_at_utc: str | None,
    validation_paths: list[str],
) -> dict[str, Any]:
    return {
        "candidate_id": stable_id(source_path, evidence_type, item_key),
        "source_path": source_path,
        "source_item_key": item_key,
        "source_generated_at_utc": generated_at_utc,
        "evidence_type": evidence_type,
        "task_family": task_family,
        "validation_proof_paths": validation_paths,
        "content_policy": {
            "raw_content_included": False,
            "metadata_only": True,
            "requires_redaction_before_export": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def boundary_risk_flags(boundary: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for key in (
        "owner_approval_inferred",
        "capital_deployment_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "portfolio_or_canon_mutation_allowed",
        "canon_or_portfolio_mutation_allowed",
        "training_or_finetune_call_allowed",
        "external_upload_allowed",
    ):
        if boundary.get(key) is True:
            flags.append(f"unsafe_boundary:{key}")
    return flags


def sensitive_key_flags(value: Any, prefix: str = "") -> list[str]:
    flags: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if key_path.startswith("authority_boundary."):
                continue
            if SENSITIVE_HINTS.search(str(key)):
                flags.append(f"sensitive_key:{key_path}")
            flags.extend(sensitive_key_flags(item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value[:25]):
            flags.extend(sensitive_key_flags(item, f"{prefix}[{index}]"))
    return flags[:20]


def finalize_candidate(
    candidate: dict[str, Any],
    *,
    quality_signals: list[str],
    risk_flags: list[str],
    why_useful: str,
    recommended_use: str | None = None,
) -> dict[str, Any]:
    risk_flags = sorted(set(risk_flags))
    quality_signals = sorted(set(quality_signals))
    if any(flag.startswith("unsafe_boundary") or flag.startswith("sensitive_key") for flag in risk_flags):
        eligibility = "rejected"
        redaction = "blocked_sensitive_or_unsafe"
        use = "reject"
    elif "finance" in candidate["task_family"] or "finance" in candidate["evidence_type"]:
        eligibility = "holdout_eval_only"
        redaction = "finance_boundary_review_required"
        use = recommended_use or "eval_only"
    elif "raw_memory_surface" in candidate["evidence_type"]:
        eligibility = "needs_redaction"
        redaction = "needs_human_redaction_review"
        use = recommended_use or "redaction_review"
    elif quality_signals:
        eligibility = "eligible"
        redaction = "clean_metadata_only"
        use = recommended_use or "eval_or_routing_benchmark"
    else:
        eligibility = "needs_redaction"
        redaction = "insufficient_quality_signals"
        use = recommended_use or "review_only"

    candidate.update(
        {
            "eligibility_status": eligibility,
            "redaction_status": redaction,
            "recommended_use": use,
            "quality_signals": quality_signals,
            "risk_flags": risk_flags,
            "why_useful": why_useful,
        }
    )
    return candidate


def candidates_from_rsi_artifact(path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    observation = as_dict(data.get("rsi_observation"))
    if not observation:
        return []
    boundary = as_dict(data.get("authority_boundary"))
    candidate = candidate_base(
        source_path=path,
        evidence_type="rsi_observation",
        task_family="self_improvement_or_startup_recovery",
        item_key=observation.get("source") or "rsi_observation",
        generated_at_utc=data.get("generated_at_utc"),
        validation_paths=[path],
    )
    quality = [
        "has_structured_rsi_observation",
        "has_owner_surface",
        "has_future_session_lesson",
    ]
    risk = boundary_risk_flags(boundary) + sensitive_key_flags(observation)
    if as_dict(data.get("validation")).get("status") == "ok":
        quality.append("source_validation_ok")
    return [finalize_candidate(candidate, quality_signals=quality, risk_flags=risk, why_useful="Structured RSI observation can seed future behavior evals without storing raw chat.")]


def candidates_from_model_run_ledger(path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in as_list(data.get("rows")) if isinstance(row, dict)]
    candidates: list[dict[str, Any]] = []
    for row in rows[:50]:
        boundary = as_dict(row.get("authority_boundary"))
        run_id = row.get("run_id") or row.get("source_artifact") or len(candidates)
        candidate = candidate_base(
            source_path=path,
            evidence_type="model_run_metadata",
            task_family="model_routing_or_performance_benchmark",
            item_key=str(run_id),
            generated_at_utc=row.get("source_generated_at_utc") or data.get("generated_at_utc"),
            validation_paths=[path, "tmp/model-quality-scorecard.json"],
        )
        quality: list[str] = []
        if row.get("model_path"):
            quality.append("model_attributed")
        if row.get("session_id"):
            quality.append("session_attributed")
        if row.get("status") == "ok":
            quality.append("run_status_ok")
        if row.get("tokens"):
            quality.append("token_metadata_available")
        risk = boundary_risk_flags(boundary) + sensitive_key_flags(row)
        candidates.append(
            finalize_candidate(
                candidate,
                quality_signals=quality,
                risk_flags=risk,
                why_useful="Run metadata supports routing/performance evals without exporting task content.",
                recommended_use="routing_benchmark",
            )
        )
    return candidates


def candidates_from_finance_ledger(path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in as_list(data.get("rows")) if isinstance(row, dict)]
    candidates: list[dict[str, Any]] = []
    for row in rows[:50]:
        boundary = as_dict(row.get("authority_boundary"))
        item_key = row.get("recommendation_id") or row.get("row_id") or row.get("ticker") or len(candidates)
        candidate = candidate_base(
            source_path=path,
            evidence_type="finance_correctness_metadata",
            task_family="finance_boundary_eval",
            item_key=str(item_key),
            generated_at_utc=row.get("generated_at_utc") or data.get("generated_at_utc"),
            validation_paths=[path, "tmp/finance-recommendation-correctness-ledger-current.json"],
        )
        quality = ["has_finance_boundary_checks"]
        if row.get("status") == "ok":
            quality.append("finance_checks_ok")
        if row.get("later_outcome_grade_status"):
            quality.append("wf55_grade_status_explicit")
        risk = boundary_risk_flags(boundary) + sensitive_key_flags(row)
        candidates.append(
            finalize_candidate(
                candidate,
                quality_signals=quality,
                risk_flags=risk,
                why_useful="Finance rows are useful only as holdout boundary evals until WF55 outcome grading matures.",
                recommended_use="eval_only",
            )
        )
    return candidates


def candidates_from_harness(path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [check for check in as_list(data.get("checks")) if isinstance(check, dict)]
    candidates: list[dict[str, Any]] = []
    for check in checks[:75]:
        item_key = check.get("name") or len(candidates)
        candidate = candidate_base(
            source_path=path,
            evidence_type="harness_check_metadata",
            task_family="implementation_or_boundary_eval",
            item_key=str(item_key),
            generated_at_utc=data.get("generated_at_utc"),
            validation_paths=[path],
        )
        quality = ["has_harness_check"]
        if check.get("status") in {"pass", "ok"}:
            quality.append("check_passed")
        risk = boundary_risk_flags(as_dict(data.get("authority_boundary"))) + sensitive_key_flags(check)
        candidates.append(finalize_candidate(candidate, quality_signals=quality, risk_flags=risk, why_useful="Harness checks can become regression/eval fixtures without raw workflow content."))
    return candidates


def candidates_from_validator_artifact(path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    validation = as_dict(data.get("validation"))
    if not validation:
        return []
    candidate = candidate_base(
        source_path=path,
        evidence_type="validator_artifact_metadata",
        task_family="validator_or_closeout_eval",
        item_key=data.get("schema") or data.get("schema_version") or Path(path).stem,
        generated_at_utc=data.get("generated_at_utc"),
        validation_paths=[path],
    )
    quality = ["has_validation_contract"]
    if validation.get("status") == "ok":
        quality.append("validation_ok")
    if as_dict(data.get("summary")):
        quality.append("has_summary")
    risk = boundary_risk_flags(as_dict(data.get("authority_boundary"))) + sensitive_key_flags(data)
    return [finalize_candidate(candidate, quality_signals=quality, risk_flags=risk, why_useful="Validator metadata can train/evaluate closeout discipline without raw prompts or private content.")]


def memory_surface_candidates(now: datetime) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for day in (now.date(), now.date() - timedelta(days=1)):
        path = MEMORY / f"{day.isoformat()}.md"
        if not path.exists():
            continue
        rel_path = rel(path)
        stat = path.stat()
        candidate = candidate_base(
            source_path=rel_path,
            evidence_type="raw_memory_surface",
            task_family="continuity_or_closeout_eval",
            item_key=day.isoformat(),
            generated_at_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            validation_paths=[rel_path],
        )
        candidates.append(
            finalize_candidate(
                candidate,
                quality_signals=["daily_memory_exists", "metadata_only_reference"],
                risk_flags=["raw_memory_requires_manual_review"],
                why_useful="Daily memory can identify closeout examples, but any text use requires separate redaction review.",
                recommended_use="redaction_review",
            )
        )
    return candidates


def build_candidates(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = [source_state(path) for path in SOURCE_ARTIFACTS]
    candidates: list[dict[str, Any]] = []
    for source in sources:
        if not source.get("exists"):
            continue
        path = str(source["path"])
        data = as_dict(load_json_artifact(ROOT / path))
        candidates.extend(candidates_from_rsi_artifact(path, data))
        if path.endswith("model-run-ledger-current.json"):
            candidates.extend(candidates_from_model_run_ledger(path, data))
        elif path.endswith("finance-recommendation-correctness-ledger-current.json"):
            candidates.extend(candidates_from_finance_ledger(path, data))
        elif path.endswith("veritas-harness-scorecard.json"):
            candidates.extend(candidates_from_harness(path, data))
        elif "validator-router" in path or "closeout" in path or "control-packet" in path or "duplication-audit" in path or "scorecard" in path:
            candidates.extend(candidates_from_validator_artifact(path, data))
    candidates.extend(memory_surface_candidates(now))
    return candidates, sources


def summarize(candidates: list[dict[str, Any]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_use: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for candidate in candidates:
        by_status[candidate["eligibility_status"]] = by_status.get(candidate["eligibility_status"], 0) + 1
        by_use[candidate["recommended_use"]] = by_use.get(candidate["recommended_use"], 0) + 1
        by_family[candidate["task_family"]] = by_family.get(candidate["task_family"], 0) + 1
    return {
        "source_count": len(sources),
        "sources_found": sum(1 for source in sources if source.get("exists")),
        "candidate_count": len(candidates),
        "eligibility_counts": dict(sorted(by_status.items())),
        "recommended_use_counts": dict(sorted(by_use.items())),
        "task_family_counts": dict(sorted(by_family.items())),
        "next_safe_action": "Use eligible rows for local eval/routing design only; manually review/redact before any training-file export.",
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    candidates = [candidate for candidate in as_list(payload.get("candidates")) if isinstance(candidate, dict)]
    if not candidates:
        findings.append({"severity": "warning", "detail": "no candidates built"})
    for candidate in candidates:
        if as_dict(candidate.get("content_policy")).get("raw_content_included") is not False:
            findings.append({"severity": "critical", "detail": f"raw content included: {candidate.get('candidate_id')}"})
        if candidate.get("recommended_use") in {"fine_tune_candidate", "training_candidate"} and candidate.get("eligibility_status") != "eligible":
            findings.append({"severity": "critical", "detail": f"unsafe training recommendation: {candidate.get('candidate_id')}"})
        if candidate.get("recommended_use") in {"fine_tune_candidate", "training_candidate"} and "finance" in str(candidate.get("task_family")):
            findings.append({"severity": "critical", "detail": f"finance row recommended for training: {candidate.get('candidate_id')}"})
        for key, expected in AUTHORITY_BOUNDARY.items():
            if as_dict(candidate.get("authority_boundary")).get(key) is not expected:
                findings.append({"severity": "critical", "detail": f"candidate boundary mismatch {key}: {candidate.get('candidate_id')}"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def build_payload(now: datetime) -> dict[str, Any]:
    candidates, sources = build_candidates(now)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "posture": "local_review_only_training_dataset_candidate_index",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "sources": sources,
        "summary": summarize(candidates, sources),
        "candidates": candidates,
        "stop_lines": [
            "This script does not create training files, upload data, call OpenAI fine-tuning, or mutate model weights.",
            "All rows are metadata-only references. Any raw example export requires separate redaction and owner approval.",
            "Finance rows are eval-only boundary fixtures unless a future gated process explicitly approves otherwise.",
            "WF55 later outcome grading remains blocked outside the WF55 gated outcome process.",
        ],
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] == "critical":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    lines = [
        "# Training Dataset Candidate Builder",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {validation.get('status')}",
        f"- Sources found: {summary.get('sources_found')} / {summary.get('source_count')}",
        f"- Candidate count: {summary.get('candidate_count')}",
        f"- Eligibility: {json.dumps(summary.get('eligibility_counts'), sort_keys=True)}",
        f"- Recommended use: {json.dumps(summary.get('recommended_use_counts'), sort_keys=True)}",
        "",
        "## Stop Lines",
    ]
    for line in payload.get("stop_lines", []):
        lines.append(f"- {line}")
    lines.extend(["", "## Task Families"])
    for family, count in as_dict(summary.get("task_family_counts")).items():
        lines.append(f"- {family}: {count}")
    if validation.get("findings"):
        lines.extend(["", "## Validation Findings"])
        for finding in validation["findings"]:
            lines.append(f"- [{finding.get('severity')}] {finding.get('detail')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local review-only training/eval dataset candidates.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload(datetime.now(timezone.utc))
    if args.write:
        atomic_write_json(args.out, payload)
        if args.write_md:
            atomic_write_text(args.out.with_suffix(".md"), render_md(payload))
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"candidates={summary.get('candidate_count')} sources={summary.get('sources_found')}/{summary.get('source_count')}"
    )
    for finding in payload["validation"]["findings"]:
        print(f"  [{finding['severity']}] {finding['detail']}")
    if args.validate and payload["validation"]["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
