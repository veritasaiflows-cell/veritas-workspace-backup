#!/usr/bin/env python3
"""Guard WF74/WF78 source-open recurrence before finance quality scoring.

This is a review-only proof packet. It verifies that the WF78 source-open patch
orchestrator is a hard producer before the finance response-quality slice in
the WF74 daily collection runner, and that the quality slice exposes source,
decision-readiness, and non-blocking thin-monitor buckets separately.

It does not mutate cron schedules, finance canon, portfolio state, paper/live
execution state, runtime config, or infer owner approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

import wf74_model_quality_collection_cron_runner as wf74_runner

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "wf78-source-open-recurrence-guard.json"
SCHEMA = "veritas.wf74_source_open_recurrence_guard.v1"

SOURCE_OPEN_PATCH = TMP / "wf78-source-open-patch-current.json"
FINANCE_RESPONSE_QUALITY = TMP / "finance-response-quality-slice.json"
WF74_RUNNER_PACKET = TMP / "wf74-model-quality-collection-cron-runner.json"

REQUIRED_BLOCKER_BUCKETS = {
    "source_freshness_blocked",
    "source_open_blocked",
    "primary_state_blocked",
    "below_stop_blocked",
    "tier_c_thin_monitor_non_blocking",
    "scoped_thin_monitor_not_required_non_blocking",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
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


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def runner_order() -> dict[str, Any]:
    names = [name for name, _command, _timeout in wf74_runner.command_plan(include_harness=False)]
    source_index = names.index("wf78_source_open_patch_orchestrator") if "wf78_source_open_patch_orchestrator" in names else None
    quality_index = names.index("finance_response_quality_slice") if "finance_response_quality_slice" in names else None
    return {
        "plan_step_count": len(names),
        "source_open_orchestrator_present": source_index is not None,
        "finance_response_quality_present": quality_index is not None,
        "source_open_orchestrator_index": source_index,
        "finance_response_quality_index": quality_index,
        "source_open_before_quality": (
            source_index is not None
            and quality_index is not None
            and source_index < quality_index
        ),
        "source_open_orchestrator_blocking": not wf74_runner.is_non_blocking_step("wf78_source_open_patch_orchestrator"),
        "neighboring_steps": names[max(0, (source_index or 0) - 2): min(len(names), (quality_index or 0) + 3)] if source_index is not None and quality_index is not None else names[:8],
    }


def finance_taxonomy(finance_packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(finance_packet.get("summary"))
    counts = as_dict(summary.get("blocker_category_counts"))
    semantics = as_dict(summary.get("scorecard_blocker_semantics"))
    missing = sorted(REQUIRED_BLOCKER_BUCKETS.difference(counts.keys()))
    return {
        "finance_response_quality_status": finance_packet.get("status"),
        "finance_response_quality_validation": as_dict(finance_packet.get("validation")).get("status"),
        "source_open_blocked_count": as_int(summary.get("source_open_blocked_count")),
        "source_freshness_blocked_count": as_int(summary.get("source_freshness_blocked_count")),
        "primary_state_blocked_count": as_int(summary.get("primary_state_blocked_count")),
        "below_stop_blocked_count": as_int(summary.get("below_stop_blocked_count")),
        "tier_c_thin_monitor_non_blocking_count": as_int(summary.get("tier_c_thin_monitor_non_blocking_count")),
        "scoped_thin_monitor_not_required_non_blocking_count": as_int(summary.get("scoped_thin_monitor_not_required_non_blocking_count")),
        "blocker_category_counts": counts,
        "missing_blocker_buckets": missing,
        "blocking_categories": semantics.get("blocking_categories") or [],
        "decision_readiness_categories": semantics.get("decision_readiness_categories") or [],
        "non_blocking_categories": semantics.get("non_blocking_categories") or [],
        "source_open_recurrence_detected": as_int(summary.get("source_open_blocked_count")) > 0,
        "source_freshness_recurrence_detected": as_int(summary.get("source_freshness_blocked_count")) > 0,
    }


def patch_status(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(SOURCE_OPEN_PATCH),
        "exists": SOURCE_OPEN_PATCH.exists(),
        "status": packet.get("status"),
        "validation": as_dict(packet.get("validation")).get("status"),
        "generated_at_utc": packet.get("generated_at_utc"),
        "write_mode": packet.get("write_mode"),
        "summary": as_dict(packet.get("summary")),
    }


def build_payload() -> dict[str, Any]:
    patch_packet = as_dict(load_json_artifact(SOURCE_OPEN_PATCH))
    finance_packet = as_dict(load_json_artifact(FINANCE_RESPONSE_QUALITY))
    wf74_packet = as_dict(load_json_artifact(WF74_RUNNER_PACKET))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Prove source-open repair runs before finance response-quality scoring and split recurrence blockers by root cause.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "runner_order": runner_order(),
        "source_open_patch": patch_status(patch_packet),
        "finance_taxonomy": finance_taxonomy(finance_packet),
        "wf74_runner_artifact": {
            "path": rel(WF74_RUNNER_PACKET),
            "exists": WF74_RUNNER_PACKET.exists(),
            "status": wf74_packet.get("status"),
            "validation": as_dict(wf74_packet.get("validation")).get("status"),
            "generated_at_utc": wf74_packet.get("generated_at_utc"),
        },
        "sources": [
            rel(SOURCE_OPEN_PATCH),
            rel(FINANCE_RESPONSE_QUALITY),
            rel(WF74_RUNNER_PACKET),
            "scripts/wf74_model_quality_collection_cron_runner.py",
            "scripts/finance_response_quality_slice.py",
            "scripts/wf78_source_open_patch_orchestrator.py",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    if validation["errors"]:
        payload["status"] = "blocked"
    elif validation["warnings"]:
        payload["status"] = "attention"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    order = as_dict(payload.get("runner_order"))
    taxonomy = as_dict(payload.get("finance_taxonomy"))
    patch = as_dict(payload.get("source_open_patch"))
    if not order.get("source_open_orchestrator_present"):
        errors.append("missing_wf78_source_open_patch_orchestrator_step")
    if not order.get("finance_response_quality_present"):
        errors.append("missing_finance_response_quality_slice_step")
    if not order.get("source_open_before_quality"):
        errors.append("wf78_source_open_patch_orchestrator_not_before_finance_response_quality_slice")
    if order.get("source_open_orchestrator_blocking") is not True:
        errors.append("wf78_source_open_patch_orchestrator_must_be_blocking")
    if taxonomy.get("missing_blocker_buckets"):
        errors.append(f"missing_blocker_buckets:{','.join(taxonomy['missing_blocker_buckets'])}")
    if "source_open_blocked" not in taxonomy.get("blocking_categories", []):
        errors.append("source_open_blocked_not_marked_blocking")
    if "source_freshness_blocked" not in taxonomy.get("blocking_categories", []):
        errors.append("source_freshness_blocked_not_marked_blocking")
    if "primary_state_blocked" not in taxonomy.get("decision_readiness_categories", []):
        errors.append("primary_state_blocked_not_decision_readiness")
    if "below_stop_blocked" not in taxonomy.get("decision_readiness_categories", []):
        errors.append("below_stop_blocked_not_decision_readiness")
    if "scoped_thin_monitor_not_required_non_blocking" not in taxonomy.get("non_blocking_categories", []):
        errors.append("scoped_thin_monitor_not_required_not_non_blocking")
    if "tier_c_thin_monitor_non_blocking" not in taxonomy.get("non_blocking_categories", []):
        errors.append("tier_c_thin_monitor_not_non_blocking")
    if patch.get("exists") is not True:
        warnings.append("source_open_patch_artifact_missing_until_runner_executes")
    elif patch.get("validation") not in {"ok", None}:
        warnings.append("source_open_patch_artifact_validation_not_ok")
    if taxonomy.get("source_open_recurrence_detected"):
        warnings.append("source_open_recurrence_detected_after_orchestrator")
    if taxonomy.get("source_freshness_recurrence_detected"):
        warnings.append("source_freshness_recurrence_detected_after_orchestrator")
    return {
        "status": "blocked" if errors else ("attention" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF74/WF78 source-open recurrence guard proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload["status"],
        "validation": payload["validation"]["status"],
        "out": rel(out),
        "errors": payload["validation"]["errors"],
        "warnings": payload["validation"]["warnings"],
    }, indent=2))
    if args.validate and payload["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
