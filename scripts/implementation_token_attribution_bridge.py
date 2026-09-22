#!/usr/bin/env python3
"""Build a metadata-only implementation token attribution bridge packet.

The token usage ledger already proves cron token usage well. This packet
focuses on the remaining implementation-lane attribution gap: completed model
lanes that have model/runtime metadata but no token-bearing provider run id or
token totals. It is a review-only bridge contract, not a runtime mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from isolated_agent_usage_metadata import CONFIGURED_ISOLATED_AGENT_IDS
from concurrent_lane_manager import telemetry_enforcement_applies, verify_usage_source_receipt


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
TOKEN_USAGE = TMP / "token-usage-ledger-current.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
CODING_OUTCOME = TMP / "coding-outcome-ledger-current.json"
# WF89 D2a credit reader (attribution contract v0.2): optional, fail-closed,
# read-only per-run join source refreshed upstream in the radar sequence.
CREDIT_READER_OUT = TMP / "wf89-credit-reader-current.json"
CREDIT_READER_SCHEMA = "veritas.wf89_credit_reader.v1"
OUT = TMP / "implementation-token-attribution-bridge.json"
MD_OUT = OUT.with_suffix(".md")
SCHEMA = "veritas.implementation_token_attribution_bridge.v1"
USAGE_SOURCE_RECEIPTS_SCHEMA = "veritas.model_usage_source_receipts.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "local_only": True,
    "writes_runtime_state": False,
    "writes_cron_schedule": False,
    "captures_raw_prompt": False,
    "captures_raw_response": False,
    "captures_tool_payload": False,
    "captures_secret_or_header": False,
    "changes_model_weights": False,
    "model_training_claim_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_STAMPING_FIELDS = [
    "runtime.agent_id",
    "runtime.parent_job_id",
    "runtime.phase",
    "runtime.authority_class",
    "runtime.objective",
    "runtime.deliverable",
    "runtime.closeout_destination",
    "runtime.session_ref_hash",
    "runtime.run_id",
    "runtime.model_path",
    "runtime.model_provider",
    "runtime.token_attribution_source",
    "runtime.input_token_semantics",
    "runtime.input_tokens",
    "runtime.cached_input_tokens",
    "runtime.cache_write_tokens",
    "runtime.output_tokens",
    "runtime.total_tokens",
    "runtime.source_input_total_tokens",
    "runtime.source_total_tokens_fresh",
    "runtime.access_mode",
    "runtime.speed_mode",
    "runtime.usage_at_utc",
    "runtime.usage_time_source",
    "runtime.outcome_status",
    "runtime.main_acceptance_status",
    "runtime.main_acceptance_evidence",
]

# 2026-09-18 Phase 2 (owner-directed): shared definition lives in
# scripts/token_usage_classifications.py. self_declared_usage_rejected stays in
# this bridge set so pre-cutover lanes that closed on self-declared totals are
# named and rejected; it remains deliberately absent from the closeout gate.
from token_usage_classifications import BRIDGE_ACCEPTED_MISSING_USAGE_CLASSIFICATIONS
ACCEPTED_MISSING_USAGE_CLASSIFICATIONS = set(BRIDGE_ACCEPTED_MISSING_USAGE_CLASSIFICATIONS)

# Legacy register values written before the strict cutover. No current producer emits these,
# so this set cannot grow and the classification below cannot apply to new work.
LEGACY_SELF_DECLARED_USAGE_SOURCES = {
    "session_status_current",
    "session_status_current_approx",
}

TOKEN_STAMPING_ENFORCEMENT_START_UTC = "2026-06-27T00:00:00Z"
TOKEN_CLOSEOUT_GUARD_START_UTC = "2026-07-03T19:30:00Z"
CURRENT_CHAT_BACKFILL_CUTOFF_UTC = "2026-07-06T22:30:00Z"
ATTRIBUTION_GRADE_ALL_LANES_ENFORCEMENT_START_UTC = "2026-08-09T00:00:00Z"
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"

# 2026-08-25 canary aged out uncredited after isolated-session rotation; warning-only threshold.
UNCREDITED_LANE_AGE_WARNING_HOURS = 168

UNSUPPORTED_LEGACY_MODEL_PATHS = {
    "claude-cli/claude-fable-5",
}

CURRENT_CHAT_SESSION_LABEL_TOKENS = (
    "webchat",
    "telegram",
)

CLOSEOUT_STAMP_COMMAND_TEMPLATE = (
    "python scripts\\concurrent_lane_manager.py --complete <WF##> --workstream <workstream> "
    "--agent-id <agent> --parent-job-id <job> --phase implementation --authority-class workspace-write "
    "--run-id <provider-or-runtime-run-id> --model-path <provider/model> "
    "--input-token-semantics <exclusive_cached|inclusive_cached|no_cache> "
    "--input-tokens <n> --cached-input-tokens <n> --cache-write-tokens <n> --output-tokens <n> "
    "--total-tokens <n> --access-mode <chatgpt|apikey|unknown> --speed-mode <standard|fast|unknown> "
    "--usage-at-utc <timestamp> --usage-time-source <source> "
    "--token-attribution-source provider_usage --write --validate"
)

FORBIDDEN_TEXT = (
    "sk-",
    "bearer ",
    "authorization:",
    "access_token",
    "refresh_token",
    "oauth_token",
    "system_prompt",
    "tool_input",
    "tool_output",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def load_usage_source_receipts(register_path: Path) -> list[dict[str, Any]]:
    payload = load(register_path.with_suffix(".usage-receipts.json"))
    if payload.get("schema") != USAGE_SOURCE_RECEIPTS_SCHEMA:
        return []
    return [row for row in as_list(payload.get("receipts")) if isinstance(row, dict)]


def source_receipt_matches_lane(
    lane: dict[str, Any],
    receipts: list[dict[str, Any]],
    *,
    register_path: Path = LANE_REGISTER,
) -> bool:
    """Require the shared source re-opener; the sidecar alone is cache-only."""
    del receipts
    return not verify_usage_source_receipt(
        lane,
        as_dict(lane.get("runtime")),
        register_path.with_suffix(".usage-receipts.json"),
    )


def source_status(path: Path) -> dict[str, Any]:
    payload = load(path)
    return {
        "path": rel(path),
        "present": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def load_credit_reader_index(path: Path = CREDIT_READER_OUT) -> dict[str, Any]:
    """Fail-closed WF89 credit-reader join index.

    Only CREDITABLE rows with verified=True and a usage dict enter the index;
    they carry per-run usage bound to run_id inside the executor-store window.
    A missing or invalid artifact contributes nothing and never blocks the
    bridge; credit is never inferred from any other source.
    """
    status = source_status(path)
    if not path.exists():
        return {
            "status": "unavailable",
            "reason": "credit_reader_artifact_missing",
            "by_run_id": {},
            "scanned_run_count": 0,
            "creditable_run_count": 0,
            "source_status": status,
        }
    payload = load(path)
    if payload.get("schema") != CREDIT_READER_SCHEMA:
        return {
            "status": "schema_mismatch",
            "reason": f"expected {CREDIT_READER_SCHEMA}",
            "by_run_id": {},
            "scanned_run_count": 0,
            "creditable_run_count": 0,
            "source_status": status,
        }
    by_run_id: dict[str, dict[str, Any]] = {}
    for record in as_list(payload.get("records")):
        if not isinstance(record, dict):
            continue
        if record.get("state") != "CREDITABLE" or record.get("verified") is not True:
            continue
        if not as_dict(record.get("usage")):
            continue
        run_id = str(record.get("run_id") or "")
        if run_id:
            by_run_id[run_id] = record
    return {
        "status": "ok",
        "reason": None,
        "by_run_id": by_run_id,
        "scanned_run_count": int(payload.get("total_scanned") or 0),
        "creditable_run_count": len(by_run_id),
        "source_status": status,
    }


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def completion_cohort(lane: dict[str, Any]) -> str:
    completed = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    cutoff = parse_utc(ATTRIBUTION_GRADE_ALL_LANES_ENFORCEMENT_START_UTC)
    if completed is None or cutoff is None:
        return "completion_time_unknown"
    return "post_cutoff" if completed >= cutoff else "historical_pre_cutoff"


def strict_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def token_stamp_assessment(lane: dict[str, Any]) -> dict[str, Any]:
    runtime = as_dict(lane.get("runtime"))
    token_keys = ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens")
    any_token = any(
        runtime.get(key) not in (None, "")
        for key in (*token_keys, "source_input_total_tokens")
    )
    missing = [key for key in token_keys if strict_nonnegative_int(runtime.get(key)) is None]
    semantics = str(runtime.get("input_token_semantics") or "")
    if semantics not in {"exclusive_cached", "inclusive_cached", "no_cache"}:
        missing.append("input_token_semantics")
    if missing:
        return {
            "any_token": any_token,
            "token_valid": False,
            "pricing_grade": False,
            "status": "attribution_incomplete",
            "missing_fields": sorted(set(missing)),
            "reasons": [],
        }
    input_tokens = int(runtime["input_tokens"])
    cached = int(runtime["cached_input_tokens"])
    cache_write = int(runtime["cache_write_tokens"])
    output = int(runtime["output_tokens"])
    total = int(runtime["total_tokens"])
    reasons: list[str] = []
    if semantics == "no_cache":
        if cached or cache_write:
            reasons.append("no_cache_conflicts_with_cache_tokens")
        expected = input_tokens + output
    elif semantics == "inclusive_cached":
        if cached > input_tokens:
            reasons.append("inclusive_cached_exceeds_input_tokens")
        expected = input_tokens + cache_write + output
    else:
        expected = input_tokens + cached + cache_write + output
    if total != expected:
        reasons.append("token_total_mismatch")
    source = str(runtime.get("token_attribution_source") or "")
    if source.startswith("openclaw_isolated_session_store"):
        source_input_total = strict_nonnegative_int(runtime.get("source_input_total_tokens"))
        if source_input_total != input_tokens + cached + cache_write:
            reasons.append("source_input_total_mismatch")
        if runtime.get("source_total_tokens_fresh") is not True:
            reasons.append("source_total_tokens_fresh_not_proven")
    token_valid = not reasons
    pricing_grade = token_valid and cache_write == 0
    return {
        "any_token": any_token,
        "token_valid": token_valid,
        "pricing_grade": pricing_grade,
        "status": (
            "pricing_grade" if pricing_grade else (
                "usage_exact_rate_unavailable" if token_valid else "invalid_usage"
            )
        ),
        "missing_fields": [],
        "reasons": reasons,
        "token_total_expected": expected,
    }


def has_token_stamp(lane: dict[str, Any]) -> bool:
    """Compatibility name: true only for complete, reconciled usage metadata."""
    return token_stamp_assessment(lane).get("token_valid") is True


def new_isolated_implementation_contract(lane: dict[str, Any]) -> bool:
    runtime = as_dict(lane.get("runtime"))
    return (
        new_attribution_grade_contract(lane)
        and runtime.get("agent_id") in CONFIGURED_ISOLATED_AGENT_IDS
        and str(runtime.get("phase") or "").lower() in {"implementation", "build", "integration", "repair", "refactor"}
    )


def new_attribution_grade_contract(lane: dict[str, Any]) -> bool:
    runtime = as_dict(lane.get("runtime"))
    # Use the manager's shared scope rule: creation time wins; a terminal
    # model lane with no usable time is in scope and therefore blocks rather
    # than becoming a silent historical exception.
    return telemetry_enforcement_applies(lane, runtime)


def missing_usage_classification(lane: dict[str, Any]) -> str | None:
    runtime = as_dict(lane.get("runtime"))
    value = runtime.get("token_attribution_source") or lane.get("token_attribution_source")
    if not value:
        return None
    text = str(value)
    if text == "unavailable_in_webchat":
        return "current_chat_runtime_unavailable"
    return text if text in ACCEPTED_MISSING_USAGE_CLASSIFICATIONS else None


def inferred_current_chat_runtime_unavailable(lane: dict[str, Any], completed: datetime | None) -> bool:
    runtime = as_dict(lane.get("runtime"))
    cutoff = parse_utc(CURRENT_CHAT_BACKFILL_CUTOFF_UTC)
    if completed is None or cutoff is None or completed > cutoff:
        return False
    session_label = str(runtime.get("session_label") or lane.get("session_label") or "").lower()
    if not any(token in session_label for token in CURRENT_CHAT_SESSION_LABEL_TOKENS):
        return False
    return runtime.get("run_id") is None


def token_gap_by_lane(token_gap_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("lane_id")): row
        for row in token_gap_rows
        if row.get("lane_id")
    }


def inferred_missing_usage_classification(lane: dict[str, Any], token_gap: dict[str, Any] | None) -> str | None:
    explicit = missing_usage_classification(lane)
    if explicit:
        return explicit
    support = as_dict(as_dict(token_gap).get("model_support"))
    runtime = as_dict(lane.get("runtime"))
    model_path = runtime.get("model_path") or lane.get("model_path")
    if support.get("status") == "unsupported_legacy":
        return "unsupported_legacy_model_route"
    if model_path in UNSUPPORTED_LEGACY_MODEL_PATHS:
        return "unsupported_legacy_model_route"
    completed = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc"))
    raw_source = runtime.get("token_attribution_source") or lane.get("token_attribution_source")
    cutover = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    if (
        raw_source in LEGACY_SELF_DECLARED_USAGE_SOURCES
        and completed is not None
        and cutover is not None
        and completed < cutover
    ):
        return "self_declared_usage_rejected"
    enforcement = parse_utc(TOKEN_STAMPING_ENFORCEMENT_START_UTC)
    if completed is not None and enforcement is not None and completed < enforcement:
        return "historical_pre_token_stamping_unavailable"
    guard_start = parse_utc(TOKEN_CLOSEOUT_GUARD_START_UTC)
    if completed is not None and guard_start is not None and completed < guard_start:
        return "historical_pre_token_closeout_guard_unavailable"
    if inferred_current_chat_runtime_unavailable(lane, completed):
        return "current_chat_runtime_unavailable"
    return None


def gap_model_capacity(lane: dict[str, Any], token_gap: dict[str, Any] | None) -> str:
    support = as_dict(as_dict(token_gap).get("model_support"))
    if support.get("status") == "unsupported_legacy":
        return "unsupported_legacy"
    if support.get("active_route_countable") is True:
        return "supported"
    runtime = as_dict(lane.get("runtime"))
    model_path = runtime.get("model_path") or lane.get("model_path")
    if model_path in UNSUPPORTED_LEGACY_MODEL_PATHS:
        return "unsupported_legacy"
    if model_path:
        return "supported"
    return "unclassified"


def completed_model_lanes(register: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in as_list(register.get("lanes")):
        if not isinstance(lane, dict) or lane.get("status") != "complete":
            continue
        runtime = as_dict(lane.get("runtime"))
        model_path = runtime.get("model_path") or lane.get("model_path")
        if model_path or new_attribution_grade_contract(lane):
            rows.append(lane)
    return rows


def missing_runtime_fields(lane: dict[str, Any]) -> list[str]:
    runtime = as_dict(lane.get("runtime"))
    missing: list[str] = []
    for field in REQUIRED_STAMPING_FIELDS:
        key = field.split(".", 1)[1]
        if runtime.get(key) in (None, ""):
            missing.append(field)
    return missing


def workflow_gap_summary(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row.get("workflow_id") or "unknown") for row in gaps)
    return [
        {"workflow_id": workflow_id, "gap_count": count}
        for workflow_id, count in counts.most_common()
    ]


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("prompt", "response", "tool_input", "tool_output", "authorization", "secret", "credential", "header")):
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_TEXT):
            findings.append(f"forbidden_value:{path}")
    return findings


def build_payload(token_usage_path: Path = TOKEN_USAGE, register_path: Path = LANE_REGISTER, coding_outcome_path: Path = CODING_OUTCOME, credit_reader_path: Path | None = None) -> dict[str, Any]:
    # Resolve lazily so patched-module TMP (tests) stays hermetic.
    credit_reader_path = credit_reader_path or (TMP / "wf89-credit-reader-current.json")
    token_usage = load(token_usage_path)
    register = load(register_path)
    source_receipts = load_usage_source_receipts(register_path)
    credit_reader = load_credit_reader_index(credit_reader_path)
    credit_by_run_id = as_dict(credit_reader.get("by_run_id"))
    token_summary = as_dict(token_usage.get("summary"))
    token_gap_rows = [as_dict(row) for row in as_list(token_usage.get("implementation_token_gaps"))]
    gaps_by_lane = token_gap_by_lane(token_gap_rows)
    lanes = completed_model_lanes(register)
    assessments = {str(lane.get("lane_id")): token_stamp_assessment(lane) for lane in lanes}
    receipt_verified = {
        str(lane.get("lane_id")): source_receipt_matches_lane(
            lane,
            source_receipts,
            register_path=register_path,
        )
        for lane in lanes
    }
    stamped_lanes = [
        lane for lane in lanes
        if assessments[str(lane.get("lane_id"))].get("token_valid") is True
        and (
            not new_attribution_grade_contract(lane)
            or (
                as_dict(lane.get("runtime")).get("usage_creditable") is True
                and as_dict(lane.get("runtime")).get("usage_credit_status") == "creditable"
                and receipt_verified[str(lane.get("lane_id"))]
            )
        )
    ]
    pricing_grade_lanes = [lane for lane in lanes if assessments[str(lane.get("lane_id"))].get("pricing_grade") is True]
    pricing_grade_lanes = [
        lane for lane in pricing_grade_lanes
        if not new_attribution_grade_contract(lane) or (
            as_dict(lane.get("runtime")).get("usage_creditable") is True
            and as_dict(lane.get("runtime")).get("usage_credit_status") == "creditable"
            and receipt_verified[str(lane.get("lane_id"))]
        )
    ]
    rate_unavailable_lanes = [
        lane for lane in lanes
        if assessments[str(lane.get("lane_id"))].get("status") == "usage_exact_rate_unavailable"
    ]
    invalid_usage_lanes = [
        lane for lane in lanes
        if assessments[str(lane.get("lane_id"))].get("status") == "invalid_usage"
    ]
    attribution_incomplete_lanes = [
        lane for lane in lanes
        if assessments[str(lane.get("lane_id"))].get("status") == "attribution_incomplete"
    ]
    runtime_gap_rows = []
    credit_resolved_rows: list[dict[str, Any]] = []
    credit_matched_usage_totals: dict[str, float] = {}
    for lane in lanes:
        assessment = assessments[str(lane.get("lane_id"))]
        runtime = as_dict(lane.get("runtime"))
        new_attribution_contract = new_attribution_grade_contract(lane)
        source_receipt_verified = receipt_verified[str(lane.get("lane_id"))]
        usage_creditable = (
            runtime.get("usage_creditable") is True
            and runtime.get("usage_credit_status") == "creditable"
            and source_receipt_verified
        )
        if assessment.get("token_valid") is True and (not new_attribution_contract or usage_creditable):
            continue
        # WF89 credit-reader join: a verified CREDITABLE provider run bound to
        # this lane's runtime.run_id resolves the gap deterministically. The
        # resolved rows stay local; only counts and aggregate usage are emitted.
        lane_run_id = str(runtime.get("run_id") or "")
        reader_record = credit_by_run_id.get(lane_run_id) if lane_run_id else None
        if reader_record is not None:
            for usage_key, usage_value in as_dict(reader_record.get("usage")).items():
                if isinstance(usage_value, (int, float)) and not isinstance(usage_value, bool):
                    credit_matched_usage_totals[usage_key] = credit_matched_usage_totals.get(usage_key, 0) + usage_value
            credit_resolved_rows.append({
                "lane_id": lane.get("lane_id"),
                "workflow_id": lane.get("workflow_id"),
                "run_id": lane_run_id,
            })
            continue
        token_gap = gaps_by_lane.get(str(lane.get("lane_id")))
        classification = inferred_missing_usage_classification(lane, token_gap)
        capacity = gap_model_capacity(lane, token_gap)
        new_isolated_contract = new_isolated_implementation_contract(lane)
        exact_unavailable = (
            assessment.get("any_token") is not True
            and classification == "provider_usage_unavailable"
            and not new_attribution_contract
        )
        attribution_classification_valid = not new_attribution_contract or exact_unavailable
        isolated_classification_valid = not new_isolated_contract or exact_unavailable
        cohort = completion_cohort(lane)
        terminal_unavailable = (
            assessment.get("any_token") is not True
            and classification in ACCEPTED_MISSING_USAGE_CLASSIFICATIONS
            and attribution_classification_valid
            and isolated_classification_valid
        )
        phase_missing = not str(runtime.get("phase") or "").strip()
        runtime_gap_rows.append({
            "lane_id": lane.get("lane_id"),
            "workflow_id": lane.get("workflow_id"),
            "workstream_id": lane.get("workstream_id"),
            "task_name": runtime.get("task_name") or lane.get("workstream_id"),
            "model_path": runtime.get("model_path") or lane.get("model_path"),
            "model_capacity": capacity,
            "token_attribution_source": runtime.get("token_attribution_source") or lane.get("token_attribution_source"),
            "usage_credit_status": runtime.get("usage_credit_status"),
            "usage_creditable": usage_creditable,
            "usage_source_receipt_verified": source_receipt_verified,
            "missing_usage_classification": classification,
            "missing_usage_classified": classification is not None,
            "completion_cohort": cohort,
            "completed_at_utc": lane.get("completed_at_utc") or lane.get("ended_at_utc"),
            "phase_missing": phase_missing,
            "terminal_unavailable": terminal_unavailable,
            "unresolved_supported_gap": (
                capacity == "supported"
                and cohort != "historical_pre_cutoff"
                and not terminal_unavailable
            ),
            "token_closeout_status": assessment.get("status"),
            "missing_token_fields": assessment.get("missing_fields"),
            "invalid_usage_reasons": assessment.get("reasons"),
            "missing_fields": missing_runtime_fields(lane),
            "new_attribution_grade_contract": new_attribution_contract,
            "new_attribution_grade_missing_usage_classification_valid": attribution_classification_valid,
            "new_isolated_implementation_contract": new_isolated_contract,
            "new_isolated_missing_usage_classification_valid": isolated_classification_valid,
            "reason": (
                "provider/runtime counters were unavailable before the strict telemetry cutover and the absence is retained as historical audit context"
                if terminal_unavailable else
                "completed model lane lacks complete reconciled usage from a deterministic trusted source; provider-unavailable and self-declared totals are not accepted post-cutover closeouts"
            ),
        })
    implementation_gap_count = int(token_summary.get("implementation_token_gap_count") or len(runtime_gap_rows))
    credit_reader_resolved_runtime_gap_count = len(credit_resolved_rows)
    classified_runtime_gap_count = sum(1 for row in runtime_gap_rows if row.get("missing_usage_classified") is True)
    unclassified_runtime_gap_count = max(len(runtime_gap_rows) - classified_runtime_gap_count, 0)
    classification_counts = Counter(str(row.get("missing_usage_classification") or "unclassified") for row in runtime_gap_rows)
    supported_runtime_gap_count = sum(1 for row in runtime_gap_rows if row.get("model_capacity") == "supported")
    unsupported_legacy_runtime_gap_count = sum(1 for row in runtime_gap_rows if row.get("model_capacity") == "unsupported_legacy")
    unclassified_supported_runtime_gap_count = sum(
        1
        for row in runtime_gap_rows
        if row.get("model_capacity") == "supported" and row.get("missing_usage_classified") is not True
    )
    historical_supported_runtime_gap_count = sum(
        1 for row in runtime_gap_rows
        if row.get("model_capacity") == "supported"
        and row.get("completion_cohort") == "historical_pre_cutoff"
    )
    post_cutoff_supported_runtime_gap_count = sum(
        1 for row in runtime_gap_rows
        if row.get("model_capacity") == "supported"
        and row.get("completion_cohort") == "post_cutoff"
    )
    post_cutoff_supported_terminal_unavailable_count = sum(
        1 for row in runtime_gap_rows
        if row.get("model_capacity") == "supported"
        and row.get("completion_cohort") == "post_cutoff"
        and row.get("terminal_unavailable") is True
    )
    post_cutoff_supported_unresolved_gap_count = sum(
        1 for row in runtime_gap_rows
        if row.get("model_capacity") == "supported"
        and row.get("completion_cohort") == "post_cutoff"
        and row.get("terminal_unavailable") is not True
    )
    unknown_completion_supported_unresolved_gap_count = sum(
        1 for row in runtime_gap_rows
        if row.get("model_capacity") == "supported"
        and row.get("completion_cohort") == "completion_time_unknown"
        and row.get("terminal_unavailable") is not True
    )
    post_cutoff_supported_missing_phase_count = sum(
        1 for row in runtime_gap_rows
        if row.get("model_capacity") == "supported"
        and row.get("completion_cohort") == "post_cutoff"
        and row.get("phase_missing") is True
    )
    action_required_supported_runtime_gap_count = (
        post_cutoff_supported_unresolved_gap_count
        + unknown_completion_supported_unresolved_gap_count
    )
    # Warning-only rotation-age check (2026-08-25 canary). Additive only.
    # runtime_gap_rows are uncredited gaps by construction; no credit/join logic touched.
    _age_now = None
    try:
        _age_now = parse_utc(utc_now())
    except Exception:
        _age_now = None
    _uncredited_ages = []
    if _age_now is not None:
        for _row in runtime_gap_rows:
            try:
                if not isinstance(_row, dict):
                    continue
                if _row.get("completion_cohort") != "post_cutoff":
                    continue
                if _row.get("terminal_unavailable"):
                    continue
                _dt = parse_utc(_row.get("completed_at_utc") or "")
                if _dt is None:
                    continue
                _h = (_age_now - _dt).total_seconds() / 3600.0
                if _h < 0 or not _row.get("lane_id"):
                    continue
                _uncredited_ages.append((_row.get("lane_id"), float(_h)))
            except Exception:
                continue
    _uncredited_ages.sort(key=lambda t: t[1], reverse=True)
    oldest_uncredited_lane_age_hours = float(_uncredited_ages[0][1]) if _uncredited_ages else None
    uncredited_aging_lane_ids = [lid for lid, h in _uncredited_ages if h > UNCREDITED_LANE_AGE_WARNING_HOURS][:25]
    new_isolated_contract_gap_count = sum(
        1 for row in runtime_gap_rows
        if row.get("new_isolated_implementation_contract") is True
        and row.get("new_isolated_missing_usage_classification_valid") is not True
    )
    new_attribution_grade_contract_gap_count = sum(
        1 for row in runtime_gap_rows
        if row.get("new_attribution_grade_contract") is True
        and row.get("new_attribution_grade_missing_usage_classification_valid") is not True
    )
    raw_gap_count = max(implementation_gap_count, len(runtime_gap_rows))
    bridge_status = "ok" if raw_gap_count == 0 else "warning"
    gap_resolution_status = (
        "complete"
        if raw_gap_count == 0 else (
            "stamp_required"
            if action_required_supported_runtime_gap_count else (
                "terminal_unavailable_only"
                if post_cutoff_supported_terminal_unavailable_count else "historical_or_classified_unavailable_only"
            )
        )
    )
    summary = {
        "token_ledger_status": token_usage.get("status"),
        "token_ledger_validation": as_dict(token_usage.get("validation")).get("status"),
        "completed_model_lane_count": len(lanes),
        "usage_source_receipt_count": len(source_receipts),
        "token_stamped_completed_model_lane_count": len(stamped_lanes),
        "attribution_grade_completed_model_lane_count": len(stamped_lanes),
        "pricing_grade_completed_model_lane_count": len(pricing_grade_lanes),
        "usage_exact_rate_unavailable_lane_count": len(rate_unavailable_lanes),
        "invalid_usage_lane_count": len(invalid_usage_lanes),
        "attribution_incomplete_lane_count": len(attribution_incomplete_lanes),
        "new_isolated_implementation_contract_gap_count": new_isolated_contract_gap_count,
        "new_attribution_grade_contract_gap_count": new_attribution_grade_contract_gap_count,
        "implementation_token_event_count": int(token_summary.get("implementation_token_event_count") or 0),
        "isolated_agent_session_event_count": int(token_summary.get("isolated_agent_session_event_count") or 0),
        "isolated_agent_attribution_grade_event_count": int(token_summary.get("isolated_agent_attribution_grade_event_count") or 0),
        "isolated_agent_pricing_grade_event_count": int(token_summary.get("isolated_agent_pricing_grade_event_count") or 0),
        "implementation_token_gap_count": implementation_gap_count,
        "implementation_token_gap_count_source": "token_usage_ledger_summary",
        "supported_implementation_token_gap_count": int(token_summary.get("supported_implementation_token_gap_count") or supported_runtime_gap_count),
        "unsupported_legacy_implementation_token_gap_count": int(token_summary.get("unsupported_legacy_implementation_token_gap_count") or unsupported_legacy_runtime_gap_count),
        "token_ledger_gap_sample_count": len(token_gap_rows),
        "runtime_gap_total_count": len(runtime_gap_rows),
        "runtime_gap_sample_count": len(runtime_gap_rows[:25]),
        "credit_reader_status": credit_reader.get("status"),
        "credit_reader_reason": credit_reader.get("reason"),
        "credit_reader_scanned_run_count": credit_reader.get("scanned_run_count"),
        "credit_reader_creditable_run_count": credit_reader.get("creditable_run_count"),
        "credit_reader_resolved_runtime_gap_count": credit_reader_resolved_runtime_gap_count,
        "credit_reader_matched_usage_totals": credit_matched_usage_totals or None,
        "classified_runtime_gap_count": classified_runtime_gap_count,
        "unclassified_runtime_gap_count": unclassified_runtime_gap_count,
        "supported_runtime_gap_count": supported_runtime_gap_count,
        "unsupported_legacy_runtime_gap_count": unsupported_legacy_runtime_gap_count,
        "unclassified_supported_runtime_gap_count": unclassified_supported_runtime_gap_count,
        "historical_supported_runtime_gap_count": historical_supported_runtime_gap_count,
        "post_cutoff_supported_runtime_gap_count": post_cutoff_supported_runtime_gap_count,
        "post_cutoff_supported_terminal_unavailable_count": post_cutoff_supported_terminal_unavailable_count,
        "post_cutoff_supported_unresolved_gap_count": post_cutoff_supported_unresolved_gap_count,
        "unknown_completion_supported_unresolved_gap_count": unknown_completion_supported_unresolved_gap_count,
        "action_required_supported_runtime_gap_count": action_required_supported_runtime_gap_count,
        "oldest_uncredited_lane_age_hours": oldest_uncredited_lane_age_hours,
        "uncredited_aging_lane_ids": uncredited_aging_lane_ids,
        "post_cutoff_supported_missing_phase_count": post_cutoff_supported_missing_phase_count,
        "completion_cohort_counts": dict(sorted(Counter(str(row.get("completion_cohort")) for row in runtime_gap_rows).items())),
        "missing_usage_classification_counts": dict(sorted(classification_counts.items())),
        "provider_run_join_ready": raw_gap_count == 0,
        "attribution_grade_closeout_ready": (
            action_required_supported_runtime_gap_count == 0
            and new_isolated_contract_gap_count == 0
            and new_attribution_grade_contract_gap_count == 0
        ),
        "gap_resolution_status": gap_resolution_status,
        "bridge_status": bridge_status,
        "closeout_enforcement_required": action_required_supported_runtime_gap_count > 0,
        "next_safe_action": (
            "Repair the unresolved post-cutoff/unknown-time supported lanes with truthful phase and usage metadata; never reconstruct counters that the provider did not expose."
            if action_required_supported_runtime_gap_count else
            "No supported runtime usage repair is required for terminal-unavailable rows; require explicit phase on future lanes and monitor the unresolved count for growth."
        ),
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": bridge_status,
        "purpose": "Review-only bridge packet for closing implementation token attribution gaps without raw content capture.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_artifacts": {
            "token_usage_ledger": rel(token_usage_path),
            "concurrent_lane_register": rel(register_path),
            "usage_source_receipts": rel(register_path.with_suffix(".usage-receipts.json")),
            "coding_outcome_ledger": rel(coding_outcome_path),
            "wf89_credit_reader": rel(credit_reader_path),
        },
        "source_status": [
            source_status(token_usage_path),
            source_status(register_path),
            source_status(register_path.with_suffix(".usage-receipts.json")),
            source_status(coding_outcome_path),
            as_dict(credit_reader.get("source_status")),
        ],
        "summary": summary,
        "required_stamping_fields": REQUIRED_STAMPING_FIELDS,
        "closeout_enforcement_contract": {
            "required_when": "on or after the strict telemetry cutover, every model-driven lane must close with a deterministic trusted source-to-lane-to-attempt join",
            "required_fields": REQUIRED_STAMPING_FIELDS,
            "accepted_missing_classifications": sorted(ACCEPTED_MISSING_USAGE_CLASSIFICATIONS),
            "new_model_lane_missing_usage_classifications": [],
            "terminal_status_vocabulary": [
                "pricing_grade",
                "usage_exact_rate_unavailable",
                "provider_usage_unavailable",
                "invalid_usage",
                "attribution_incomplete",
            ],
            "token_stamping_enforcement_start_utc": TOKEN_STAMPING_ENFORCEMENT_START_UTC,
            "token_closeout_guard_start_utc": TOKEN_CLOSEOUT_GUARD_START_UTC,
            "attribution_grade_all_lanes_enforcement_start_utc": STRICT_TELEMETRY_CUTOVER_UTC,
            "current_chat_backfill_cutoff_utc": CURRENT_CHAT_BACKFILL_CUTOFF_UTC,
            "must_not_capture": [
                "raw prompt",
                "raw response",
                "tool payload",
                "secret",
                "header",
            ],
            "acceptance": "new in-scope completed lanes require complete reconciled usage from a deterministic source run, a matching attempt correlation, and an importer-issued source receipt. provider_usage_unavailable is historical audit vocabulary only and cannot close a post-cutover gap.",
        },
        "closeout_stamp_command_template": CLOSEOUT_STAMP_COMMAND_TEMPLATE,
        "workflow_gap_summary": workflow_gap_summary(runtime_gap_rows)[:15],
        "token_ledger_gap_samples": token_gap_rows[:15],
        "runtime_gap_samples": runtime_gap_rows[:15],
        "action_items": action_items(summary),
        "blocked_actions": [
            "no raw prompt, response, tool payload, secret, or header capture",
            "no runtime/config/cron mutation from this packet",
            "no model-training or self-modifying-weight claim",
            "no finance, portfolio, paper/live, brokerage, or account action",
        ],
    }
    payload["privacy_scan"] = {
        "status": "ok",
        "findings": scan_forbidden({
            "summary": payload["summary"],
            "required_stamping_fields": payload["required_stamping_fields"],
            "gap_samples": payload["runtime_gap_samples"],
        }),
    }
    if payload["privacy_scan"]["findings"]:
        payload["privacy_scan"]["status"] = "blocked"
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] == "blocked":
        payload["status"] = "blocked"
    return payload


def action_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    state = str(summary.get("gap_resolution_status") or "repair_required")
    return [
        {
            "id": "stamp-implementation-token-runtime-metadata",
            "state": state,
            "owner_surface": "scripts/concurrent_lane_manager.py and coding outcome closeout producers",
            "next_action": "Use concurrent_lane_manager closeout fields for run/agent/phase, input-token semantics, input/cache-read/cache-write/output/total counts, usage timestamp provenance, outcome, and Main acceptance when exposed.",
            "acceptance": "new completed implementation lanes with exposed token counts create lane_runtime token events and do not add new missing_usage gaps.",
            "stop_line": "Metadata fields only; no raw prompt, response, or tool payload capture.",
        },
        {
            "id": "join-token-usage-ledger-to-implementation-lanes",
            "state": state,
            "owner_surface": "scripts/token_usage_ledger.py",
            "next_action": "After lane stamps exist, rerun the token usage ledger and verify implementation_token_event_count rises.",
            "acceptance": "provider_run_join_ready is true or every remaining gap is explicitly classified as provider-missing.",
            "stop_line": "Cost attribution does not rank implementation quality by itself.",
        },
    ]


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    if as_dict(payload.get("privacy_scan")).get("status") != "ok":
        errors.append("privacy_scan_not_ok")
    summary = as_dict(payload.get("summary"))
    if int(summary.get("implementation_token_gap_count") or 0) > 0:
        warnings.append(f"implementation_token_gap_count:{summary.get('implementation_token_gap_count')}")
    if int(summary.get("unclassified_runtime_gap_count") or 0) > 0:
        warnings.append(f"unclassified_runtime_gap_count:{summary.get('unclassified_runtime_gap_count')}")
    if int(summary.get("unclassified_supported_runtime_gap_count") or 0) > 0:
        warnings.append(f"unclassified_supported_runtime_gap_count:{summary.get('unclassified_supported_runtime_gap_count')}")
    if int(summary.get("post_cutoff_supported_unresolved_gap_count") or 0) > 0:
        warnings.append(f"post_cutoff_supported_unresolved_gap_count:{summary.get('post_cutoff_supported_unresolved_gap_count')}")
    if int(summary.get("unknown_completion_supported_unresolved_gap_count") or 0) > 0:
        warnings.append(f"unknown_completion_supported_unresolved_gap_count:{summary.get('unknown_completion_supported_unresolved_gap_count')}")
    if int(summary.get("post_cutoff_supported_missing_phase_count") or 0) > 0:
        warnings.append(f"post_cutoff_supported_missing_phase_count:{summary.get('post_cutoff_supported_missing_phase_count')}")
    if str(summary.get("credit_reader_status") or "") == "schema_mismatch":
        warnings.append("credit_reader_artifact_schema_mismatch")
    if int(summary.get("new_isolated_implementation_contract_gap_count") or 0) > 0:
        errors.append(f"new_isolated_implementation_contract_gap_count:{summary.get('new_isolated_implementation_contract_gap_count')}")
    if int(summary.get("new_attribution_grade_contract_gap_count") or 0) > 0:
        errors.append(f"new_attribution_grade_contract_gap_count:{summary.get('new_attribution_grade_contract_gap_count')}")
    post_cutoff_terminal_unavailable = int(summary.get("post_cutoff_supported_terminal_unavailable_count") or 0)
    terminal_unavailable_is_only_remaining_gap = (
        post_cutoff_terminal_unavailable > 0
        and str(summary.get("gap_resolution_status") or "") == "terminal_unavailable_only"
        and int(summary.get("action_required_supported_runtime_gap_count") or 0) == 0
        and int(summary.get("new_isolated_implementation_contract_gap_count") or 0) == 0
        and int(summary.get("new_attribution_grade_contract_gap_count") or 0) == 0
    )
    if post_cutoff_terminal_unavailable > 0:
        if terminal_unavailable_is_only_remaining_gap:
            warnings.append(f"post_cutoff_provider_usage_unavailable_terminal_only:{post_cutoff_terminal_unavailable}")
        else:
            errors.append("post_cutoff_provider_usage_unavailable_is_not_a_valid_closeout")
    attribution_grade = int(summary.get("attribution_grade_completed_model_lane_count") or 0)
    pricing_grade = int(summary.get("pricing_grade_completed_model_lane_count") or 0)
    rate_unavailable = int(summary.get("usage_exact_rate_unavailable_lane_count") or 0)
    if attribution_grade != pricing_grade + rate_unavailable:
        errors.append("attribution_grade_lane_classification_mismatch")
    if int(summary.get("invalid_usage_lane_count") or 0) > 0:
        warnings.append(f"invalid_usage_lane_count:{summary.get('invalid_usage_lane_count')}")
    if int(summary.get("attribution_incomplete_lane_count") or 0) > 0:
        warnings.append(f"attribution_incomplete_lane_count:{summary.get('attribution_incomplete_lane_count')}")
    if not as_list(payload.get("required_stamping_fields")):
        errors.append("required_stamping_fields_empty")
    # Rotation-age warnings only; never errors. No other validate() behavior touched.
    try:
        _v_ids = list((payload.get("summary", {}) or {}).get("uncredited_aging_lane_ids", []) or [])
    except Exception:
        _v_ids = []
    if _v_ids:
        try:
            _v_by_id = {r.get("lane_id"): r for r in (payload.get("runtime_gap_samples", []) or []) if isinstance(r, dict) and r.get("lane_id")}
        except Exception:
            _v_by_id = {}
        try:
            _v_now = parse_utc(utc_now())
        except Exception:
            _v_now = None
        for _v_lid in _v_ids[:25]:
            _v_h = None
            try:
                _v_dt = parse_utc((_v_by_id.get(_v_lid, {}) or {}).get("completed_at_utc") or "")
                if _v_dt is not None and _v_now is not None:
                    _v_h = int(round((_v_now - _v_dt).total_seconds() / 3600.0))
            except Exception:
                _v_h = None
            if _v_h is None:
                warnings.append(f"uncredited_lane_aging:{_v_lid}")
            else:
                warnings.append(f"uncredited_lane_aging:{_v_lid}:{_v_h}")
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Implementation Token Attribution Bridge",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Completed model lanes: {summary.get('completed_model_lane_count')}",
        f"- Token-stamped completed lanes: {summary.get('token_stamped_completed_model_lane_count')}",
        f"- Implementation token events/gaps: {summary.get('implementation_token_event_count')} / {summary.get('implementation_token_gap_count')}",
        f"- Implementation gap count source: `{summary.get('implementation_token_gap_count_source')}`",
        f"- Runtime gap total: {summary.get('runtime_gap_total_count')}",
        f"- WF89 credit reader: {summary.get('credit_reader_status')} scanned={summary.get('credit_reader_scanned_run_count')} creditable={summary.get('credit_reader_creditable_run_count')} gaps_resolved_by_run_join={summary.get('credit_reader_resolved_runtime_gap_count')}",
        f"- Classified/unclassified runtime gaps: {summary.get('classified_runtime_gap_count')} / {summary.get('unclassified_runtime_gap_count')}",
        f"- Historical/post-cutoff supported gaps: {summary.get('historical_supported_runtime_gap_count')} / {summary.get('post_cutoff_supported_runtime_gap_count')}",
        f"- Post-cutoff terminal-unavailable/unresolved: {summary.get('post_cutoff_supported_terminal_unavailable_count')} / {summary.get('post_cutoff_supported_unresolved_gap_count')}",
        f"- Provider run join ready: {summary.get('provider_run_join_ready')}",
        f"- Oldest uncredited lane age (hours): {summary.get('oldest_uncredited_lane_age_hours')}",
        f"- Uncredited aging lane ids: {summary.get('uncredited_aging_lane_ids')}",
        f"- Closeout stamp command: `{payload.get('closeout_stamp_command_template')}`",
        "",
        "## Required Stamping Fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in as_list(payload.get("required_stamping_fields")))
    lines.extend(["", "## Top Workflow Gaps", ""])
    for row in as_list(payload.get("workflow_gap_summary"))[:10]:
        item = as_dict(row)
        lines.append(f"- {item.get('workflow_id')}: {item.get('gap_count')}")
    lines.extend(["", "## Actions", ""])
    for row in as_list(payload.get("action_items")):
        item = as_dict(row)
        lines.append(f"- `{item.get('id')}`: `{item.get('state')}` - {item.get('next_action')}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--token-usage", type=Path, default=TOKEN_USAGE)
    parser.add_argument("--lane-register", type=Path, default=LANE_REGISTER)
    parser.add_argument("--coding-outcome", type=Path, default=CODING_OUTCOME)
    parser.add_argument("--credit-reader", type=Path, default=CREDIT_READER_OUT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token_usage = args.token_usage if args.token_usage.is_absolute() else ROOT / args.token_usage
    lane_register = args.lane_register if args.lane_register.is_absolute() else ROOT / args.lane_register
    coding_outcome = args.coding_outcome if args.coding_outcome.is_absolute() else ROOT / args.coding_outcome
    credit_reader = args.credit_reader if args.credit_reader.is_absolute() else ROOT / args.credit_reader
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    payload = build_payload(token_usage, lane_register, coding_outcome, credit_reader)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = as_dict(payload.get("summary"))
        print(
            f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
            f"implementation_events={summary.get('implementation_token_event_count')} "
            f"implementation_gaps={summary.get('implementation_token_gap_count')}"
        )
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
