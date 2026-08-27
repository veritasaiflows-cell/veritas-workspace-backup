#!/usr/bin/env python3
"""Build a stitched WF74 -> WF88 learning-loop trace packet.

The packet is a review-only proof surface. It follows each current WF74
opportunity through the router, decision docket, PM job queue, lane register,
closeout proof, and memory references when the links exist. It also keeps the
upstream OTEL/model-learning/token surfaces visible so WF88 can see whether the
loop is measured end to end.

It does not create canon, approval, execution, cron, runtime, portfolio, or
model-training authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from concurrent_lane_manager import verify_usage_source_receipt


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
MEMORY = ROOT / "memory"

OUT = TMP / "wf74-wf88-loop-trace.json"
MD_OUT = TMP / "wf74-wf88-loop-trace.md"
SCHEMA = "veritas.wf74_wf88_loop_trace_packet.v1"
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"

SOURCE_PATHS = {
    "otel_ops_control": TMP / "otel-ops-control.json",
    "model_learning_metadata_ledger": TMP / "model-learning-metadata-ledger.json",
    "token_efficiency_scorecard": TMP / "token-efficiency-scorecard.json",
    "implementation_token_attribution_bridge": TMP / "implementation-token-attribution-bridge.json",
    "wf74_improvement_opportunity_queue": TMP / "wf74-improvement-opportunity-queue.json",
    "wf74_autonomy_work_router": TMP / "wf74-autonomy-work-router.json",
    "wf74_decision_docket": TMP / "wf74-decision-docket.json",
    "pm_implementation_job_queue": TMP / "pm-implementation-job-queue.json",
    "concurrent_lane_register": TMP / "concurrent-lane-register.json",
    "control_closeout_bundle": TMP / "control-closeout-bundle.json",
    "implementation_release_contract": TMP / "implementation-release-contract.json",
    "wf88_wiki_synthesis_packet": TMP / "wf88-wiki-synthesis-packet.json",
    "wf88_os2_control_packet": TMP / "wf88-os2-control-packet.json",
}

REQUIRED_SOURCES = {
    "wf74_improvement_opportunity_queue",
    "wf74_autonomy_work_router",
    "wf74_decision_docket",
    "pm_implementation_job_queue",
    "concurrent_lane_register",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "trace_packet_only": True,
    "derived_routing_proof_only": True,
    "creates_canon": False,
    "approval_authority": False,
    "auto_apply_allowed": False,
    "delete_archive_or_move_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_or_source_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "model_training_claim_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "raw_tool_payload_capture_allowed": False,
    "owner_approval_inferred": False,
}

REVIEW_EVENT_REF_SCHEMA = "veritas.wf74_rsi_review_event_ref.v1"
REVIEW_EVENT_KINDS = {"coding_outcome_event", "recommendation_outcome_grade"}
REVIEW_EVENT_LINK_STATUSES = {"linked_exact", "unlinked", "unresolved"}
REVIEW_EVENT_SOURCE_BY_KIND = {
    "coding_outcome_event": "data/state-history/coding-outcome-ledger.jsonl",
    "recommendation_outcome_grade": "data/state-history/recommendation-outcome-grades.jsonl",
}
REVIEW_EVENT_REF_FIELDS = {
    "schema",
    "metadata_only",
    "link_status",
    "event_kind",
    "lifecycle_id",
    "source_path",
    "record_id",
    "record_hash",
    "ledger_event_id",
    "recommendation_id",
    "linked_at_utc",
    "source_freshness",
    "authority_boundary",
}
REVIEW_EVENT_FRESHNESS_FIELDS = {
    "generated_at_utc",
    "observed_at_utc",
    "age_hours",
    "status",
    "fresh",
    "max_age_hours",
}
REVIEW_EVENT_FRESHNESS_STATUSES = {"ok", "warning", "fresh", "stale", "blocked", "missing", "error", "unknown"}
REVIEW_EVENT_AUTHORITY_FIELDS = {"review_only", "owner_approval_inferred"}


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
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def source_descriptor(name: str, path: Path) -> dict[str, Any]:
    payload = load(path)
    generated_at = payload.get("generated_at_utc")
    generated_dt = parse_utc(generated_at)
    age_hours = None
    if generated_dt is not None:
        age_hours = round((datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600.0, 2)
    return {
        "path": rel(path),
        "present": path.exists(),
        "required": name in REQUIRED_SOURCES,
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
    }


def stable_id(*parts: Any) -> str:
    material = "|".join(str(part) for part in parts if part not in (None, ""))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def compact_identifier(value: Any) -> str:
    text = str(value or "")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
    return text if text and len(text) <= 256 and set(text) <= allowed else ""


def metadata_only_review_event_ref(
    value: Any,
    *,
    lifecycle_id: str,
    recommendation_id: str,
) -> dict[str, Any] | None:
    """Revalidate the router's compact reference before rendering it downstream."""
    ref = as_dict(value)
    if not ref or set(ref) - REVIEW_EVENT_REF_FIELDS:
        return None
    if ref.get("schema") != REVIEW_EVENT_REF_SCHEMA or ref.get("metadata_only") is not True:
        return None
    link_status = str(ref.get("link_status") or "")
    event_kind = str(ref.get("event_kind") or "")
    ref_lifecycle_id = compact_identifier(ref.get("lifecycle_id"))
    if (
        link_status not in REVIEW_EVENT_LINK_STATUSES
        or event_kind not in REVIEW_EVENT_KINDS
        or (ref.get("lifecycle_id") is not None and not ref_lifecycle_id)
        or (ref_lifecycle_id and lifecycle_id and ref_lifecycle_id != lifecycle_id)
    ):
        return None
    source_path = str(ref.get("source_path") or "").replace("\\", "/")
    if source_path and source_path != REVIEW_EVENT_SOURCE_BY_KIND[event_kind]:
        return None
    record_id = compact_identifier(ref.get("record_id"))
    if ref.get("record_id") is not None and not record_id:
        return None
    if link_status == "linked_exact" and (not ref_lifecycle_id or not source_path or not record_id):
        return None
    record_hash = str(ref.get("record_hash") or "")
    if record_hash and (len(record_hash) != 64 or set(record_hash.casefold()) - set("0123456789abcdef")):
        return None
    ref_recommendation_id = compact_identifier(ref.get("recommendation_id"))
    if ref.get("recommendation_id") is not None and not ref_recommendation_id:
        return None
    if ref_recommendation_id and recommendation_id and ref_recommendation_id != recommendation_id:
        return None
    boundary = as_dict(ref.get("authority_boundary"))
    if ref.get("authority_boundary") is not None and (
        set(boundary) != REVIEW_EVENT_AUTHORITY_FIELDS
        or boundary.get("review_only") is not True
        or boundary.get("owner_approval_inferred") is not False
    ):
        return None
    if ref.get("ledger_event_id") is not None and not compact_identifier(ref.get("ledger_event_id")):
        return None
    linked_at_utc = str(ref.get("linked_at_utc") or "")
    if ref.get("linked_at_utc") is not None and (not linked_at_utc or len(linked_at_utc) > 64):
        return None
    freshness = as_dict(ref.get("source_freshness"))
    if ref.get("source_freshness") is not None:
        if not isinstance(ref.get("source_freshness"), dict) or set(freshness) - REVIEW_EVENT_FRESHNESS_FIELDS:
            return None
        if any(
            key in freshness and not isinstance(freshness[key], (str, int, float, bool))
            for key in freshness
        ):
            return None
        if "status" in freshness and str(freshness["status"]) not in REVIEW_EVENT_FRESHNESS_STATUSES:
            return None
        if "fresh" in freshness and type(freshness["fresh"]) is not bool:
            return None
        if any(
            key in freshness and (type(freshness[key]) is bool or not isinstance(freshness[key], (int, float)))
            for key in ("age_hours", "max_age_hours")
        ):
            return None
        if any(
            key in freshness and (not isinstance(freshness[key], str) or len(freshness[key]) > 64)
            for key in ("generated_at_utc", "observed_at_utc")
        ):
            return None
    if ref.get("record_id") is not None and not record_id:
        return None
    result: dict[str, Any] = {
        "schema": REVIEW_EVENT_REF_SCHEMA,
        "metadata_only": True,
        "link_status": link_status,
        "event_kind": event_kind,
        "lifecycle_id": lifecycle_id or ref_lifecycle_id,
    }
    result["source_path"] = source_path if source_path else None
    if record_id:
        result["record_id"] = record_id
    if record_hash:
        result["record_hash"] = record_hash
    for key in ("ledger_event_id", "recommendation_id"):
        item = compact_identifier(ref.get(key))
        if item:
            result[key] = item
    if linked_at_utc:
        result["linked_at_utc"] = linked_at_utc
    if freshness:
        result["source_freshness"] = freshness
    if boundary:
        result["authority_boundary"] = {
            "review_only": True,
            "owner_approval_inferred": False,
        }
    return result


def review_event_provenance(ref: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not ref:
        return []
    return [{
        "event_kind": ref.get("event_kind"),
        "link_status": ref.get("link_status"),
        "source_path": ref.get("source_path"),
        "record_id": ref.get("record_id"),
        "record_hash": ref.get("record_hash"),
    }]


def list_by_key(rows: list[Any], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        value = row_dict.get(key)
        if isinstance(value, str) and value:
            result[value] = row_dict
    return result


def collect_routes(router: dict[str, Any]) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for row in as_list(router.get("opportunity_routes")):
        route = as_dict(row)
        key = route.get("source_key")
        if isinstance(key, str) and key:
            routes[key] = route
    for row in as_list(router.get("recommendation_action_ledger")):
        action = as_dict(row)
        key = action.get("opportunity_id") or action.get("source_key") or action.get("recommendation_id")
        if isinstance(key, str) and key and key not in routes:
            routes[key] = action
    return routes


def collect_pm_jobs(pm_queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for job in as_list(pm_queue.get("jobs")):
        row = as_dict(job)
        for key in (
            row.get("job_id"),
            row.get("source_opportunity_id"),
            row.get("source_action_id"),
            row.get("source_recommendation_id"),
        ):
            if isinstance(key, str) and key:
                jobs[key] = row
    return jobs


def collect_lanes(lane_register: dict[str, Any]) -> list[dict[str, Any]]:
    return [as_dict(row) for row in as_list(lane_register.get("lanes"))]


def lane_matches(lane: dict[str, Any], terms: set[str]) -> bool:
    if not terms:
        return False
    fields: list[str] = []
    for key in ("lane_id", "workflow_id", "workstream_id", "status", "owner"):
        value = lane.get(key)
        if isinstance(value, str):
            fields.append(value.lower())
    for key in ("allowed_writes", "proof_artifacts", "acceptance_commands", "notes"):
        for value in as_list(lane.get(key)):
            if isinstance(value, str):
                fields.append(value.lower())
    haystack = "\n".join(fields)
    return any(term.lower() in haystack for term in terms if len(term) >= 8)


def choose_lane(lanes: list[dict[str, Any]], terms: set[str]) -> dict[str, Any]:
    matches = [lane for lane in lanes if lane_matches(lane, terms)]
    if not matches:
        return {}
    status_rank = {"running": 5, "leased": 4, "complete": 3, "blocked": 2, "cancelled": 1}
    matches.sort(
        key=lambda row: (
            status_rank.get(str(row.get("status") or ""), 0),
            str(row.get("updated_at_utc") or row.get("completed_at_utc") or row.get("created_at_utc") or ""),
        ),
        reverse=True,
    )
    return matches[0]


def lane_telemetry_credit_state(lane: dict[str, Any]) -> dict[str, Any]:
    """Project operational completion separately from receipt-backed outcome credit."""
    runtime = as_dict(lane.get("runtime"))
    model_path = runtime.get("model_path") or lane.get("model_path")
    observed = parse_utc(lane.get("created_at_utc") or lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    cutoff = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    terminal = str(lane.get("status") or "") in {"complete", "blocked", "cancelled", "failed", "error", "rejected"}
    # A missing timestamp on a terminal model lane is not historical evidence.
    # The lane manager itself treats it as attribution-blocking, and the trace
    # must preserve that fail-closed posture rather than turning it into a
    # completion fallback in RSI.
    if model_path and terminal and observed is None:
        return {
            "required": True,
            "eligible": False,
            "status": "blocked",
            "receipt_verified": False,
            "reasons": ["telemetry_timestamp_required"],
        }
    required = bool(model_path and observed and cutoff and observed >= cutoff)
    if not required:
        return {
            "required": False,
            "eligible": True,
            "status": "not_required_or_historical",
            "receipt_verified": False,
            "reasons": [],
        }
    reasons = verify_usage_source_receipt(
        lane,
        runtime,
        SOURCE_PATHS["concurrent_lane_register"].with_suffix(".usage-receipts.json"),
    )
    eligible = bool(
        runtime.get("usage_creditable") is True
        and runtime.get("usage_credit_status") == "creditable"
        and not reasons
    )
    return {
        "required": True,
        "eligible": eligible,
        "status": "creditable" if eligible else "blocked",
        "receipt_verified": not reasons,
        "reasons": reasons,
    }


def pm_job_allows_missing_lane(pm_job: dict[str, Any]) -> bool:
    status = str(pm_job.get("status") or "").lower()
    return status in {
        "completed_by_ledger",
        "completed_by_ledger_resolved",
        "resolved_by_ledger",
    }


def memory_refs_for_terms(terms: set[str], *, max_refs: int = 4) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if not MEMORY.exists():
        return refs
    normalized = [term for term in terms if isinstance(term, str) and len(term) >= 10]
    if not normalized:
        return refs
    for path in sorted(MEMORY.glob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines, start=1):
            lower = line.lower()
            if any(term.lower() in lower for term in normalized):
                refs.append({"path": rel(path), "line": index})
                if len(refs) >= max_refs:
                    return refs
    return refs


def summarize_source_spine(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    otel = as_dict(payloads["otel_ops_control"].get("summary"))
    model = as_dict(payloads["model_learning_metadata_ledger"].get("summary"))
    token = as_dict(payloads["token_efficiency_scorecard"].get("summary"))
    bridge = as_dict(payloads["implementation_token_attribution_bridge"].get("summary"))
    router = as_dict(payloads["wf74_autonomy_work_router"].get("summary"))
    wf88 = as_dict(payloads["wf88_os2_control_packet"].get("summary"))
    return {
        "otel_event_count": otel.get("event_count"),
        "model_learning_row_count": model.get("row_count"),
        "model_learning_failure_rows": model.get("failure_rows"),
        "model_learning_runtime_otel_rows": model.get("runtime_otel_rows"),
        "token_event_count": token.get("token_event_count"),
        "implementation_token_gap_count": bridge.get("implementation_token_gap_count") or token.get("implementation_token_gap_count"),
        "api_call_reduction_candidate_count": token.get("api_call_reduction_candidate_count"),
        "prompt_compression_candidate_count": token.get("prompt_compression_candidate_count"),
        "failure_cost_candidate_count": token.get("failure_cost_candidate_count"),
        "wf74_routed_opportunity_count": router.get("routed_opportunity_count"),
        "wf74_pm_job_candidate_count": router.get("pm_job_candidate_count"),
        "wf88_status": payloads["wf88_os2_control_packet"].get("status"),
        "wf88_stale_input_count": wf88.get("stale_input_count"),
        "wf88_missing_required_input_count": wf88.get("missing_required_input_count"),
    }


def build_trace_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    queue = payloads["wf74_improvement_opportunity_queue"]
    router = payloads["wf74_autonomy_work_router"]
    docket = payloads["wf74_decision_docket"]
    pm_queue = payloads["pm_implementation_job_queue"]
    lane_register = payloads["concurrent_lane_register"]

    routes = collect_routes(router)
    docket_rows = list_by_key(as_list(docket.get("rows")), "source_id")
    pm_jobs = collect_pm_jobs(pm_queue)
    lanes = collect_lanes(lane_register)
    trace_rows: list[dict[str, Any]] = []

    for opportunity in as_list(queue.get("opportunities")):
        opp = as_dict(opportunity)
        opportunity_id = str(opp.get("opportunity_id") or "")
        route = routes.get(opportunity_id, {})
        origin_opportunity_id = str(route.get("origin_opportunity_id") or opp.get("origin_opportunity_id") or opportunity_id)
        lifecycle_id = str(route.get("lifecycle_id") or opp.get("lifecycle_id") or f"lifecycle-{stable_id('wf74', origin_opportunity_id)}")
        recommendation_id = str(route.get("recommendation_id") or opportunity_id)
        review_event_ref = metadata_only_review_event_ref(
            route.get("review_event_ref") or opp.get("review_event_ref"),
            lifecycle_id=lifecycle_id,
            recommendation_id=recommendation_id,
        )
        docket_row = docket_rows.get(opportunity_id, {})
        pm_job_id = route.get("pm_job_id")
        pm_job = pm_jobs.get(str(pm_job_id or "")) or pm_jobs.get(opportunity_id) or {}
        lane_id = pm_job.get("lane_id") or route.get("lane_id") or route.get("route")
        link_terms = {
            opportunity_id,
            str(pm_job_id or ""),
            str(lane_id or ""),
            str(pm_job.get("collision_group") or ""),
            str(route.get("implementation_class") or ""),
        }
        link_terms = {term for term in link_terms if term and term != "None"}
        lane = choose_lane(lanes, link_terms)
        proof_artifacts = [
            artifact for artifact in as_list(lane.get("proof_artifacts")) if isinstance(artifact, str)
        ]
        memory_refs = memory_refs_for_terms({
            opportunity_id,
            str(pm_job_id or ""),
            str(opp.get("title") or ""),
        })
        missing_links: list[str] = []
        if not route:
            missing_links.append("missing_router_route")
        if route and route.get("route_status") == "pm_job_candidate" and not pm_job:
            missing_links.append("missing_pm_job")
        lane_resolution = None
        if pm_job and not lane and pm_job_allows_missing_lane(pm_job):
            lane_resolution = "completed_by_ledger_no_live_lane_required"
        elif pm_job and not lane:
            missing_links.append("missing_lane_link")
        if lane and lane.get("status") == "complete" and not proof_artifacts:
            missing_links.append("completed_lane_missing_proof_artifacts")
        if lane and lane.get("status") == "complete" and not memory_refs:
            missing_links.append("completed_lane_missing_memory_ref")
        telemetry = lane_telemetry_credit_state(lane) if lane else {
            "required": False,
            "eligible": True,
            "status": "no_lane_link",
            "receipt_verified": False,
            "reasons": [],
        }
        if lane and lane.get("status") == "complete" and telemetry["required"] and not telemetry["eligible"]:
            missing_links.append("completed_lane_telemetry_unverified")

        trace_row = {
            "schema": "veritas.wf74_wf88_loop_trace_row.v1",
            "trace_id": f"trace-{stable_id(opportunity_id, pm_job_id, lane_id)}",
            "opportunity_id": opportunity_id,
            "origin_opportunity_id": origin_opportunity_id,
            "lifecycle_id": lifecycle_id,
            "recommendation_id": recommendation_id,
            "category": opp.get("category"),
            "title": opp.get("title"),
            "priority": opp.get("priority"),
            "signal": opp.get("signal"),
            "completion_status": opp.get("completion_status"),
            "route_status": route.get("route_status"),
            "route": route.get("route"),
            "route_next_action": route.get("next_action") or route.get("recommended_action"),
            "decision_docket_id": docket_row.get("docket_id"),
            "decision_action_state": docket_row.get("action_state"),
            "decision_next_action": docket_row.get("next_action"),
            "pm_job_id": pm_job_id or pm_job.get("job_id"),
            "pm_job_status": pm_job.get("status"),
            "pm_job_lane_id": lane_id,
            "pm_job_readiness_score": pm_job.get("readiness_score"),
            "lane_id": lane.get("lane_id"),
            "lane_status": lane.get("status"),
            "lane_operational_status": lane.get("status"),
            "lane_telemetry_credit_eligible": telemetry["eligible"],
            "lane_telemetry_credit_status": telemetry["status"],
            "lane_telemetry_receipt_verified": telemetry["receipt_verified"],
            "lane_telemetry_block_reasons": telemetry["reasons"],
            "lane_resolution": lane_resolution,
            "lane_updated_at_utc": lane.get("updated_at_utc"),
            "lane_completed_at_utc": lane.get("completed_at_utc"),
            "closeout_proof_artifacts": proof_artifacts,
            "memory_refs": memory_refs,
            "missing_links": missing_links,
            "authority_boundary": {
                "review_only": True,
                "trace_row_only": True,
                "auto_apply_allowed": False,
                "owner_approval_inferred": False,
            },
        }
        if review_event_ref is not None:
            trace_row["review_event_ref"] = review_event_ref
            trace_row["review_event_provenance"] = review_event_provenance(review_event_ref)
        trace_rows.append(trace_row)
    return trace_rows


def summarize_trace(trace_rows: list[dict[str, Any]], payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing_destination = [
        row for row in trace_rows
        if not row.get("route_status") or row.get("route_status") in {"unrouted", "not_routed"}
    ]
    high_priority_unrouted = [
        row for row in missing_destination
        if int(row.get("priority") or 0) >= 80
    ]
    pm_linked = [row for row in trace_rows if row.get("pm_job_id")]
    lane_linked = [row for row in trace_rows if row.get("lane_id")]
    lane_link_missing = [
        row for row in trace_rows
        if "missing_lane_link" in as_list(row.get("missing_links"))
    ]
    completed_lane_missing_closeout = [
        row for row in trace_rows
        if row.get("lane_status") == "complete" and not row.get("closeout_proof_artifacts")
    ]
    completed_lane_missing_memory = [
        row for row in trace_rows
        if row.get("lane_status") == "complete" and not row.get("memory_refs")
    ]
    completed_lane_telemetry_unverified = [
        row for row in trace_rows
        if "completed_lane_telemetry_unverified" in as_list(row.get("missing_links"))
    ]
    duplicate_pm_job_ids: dict[str, int] = {}
    for candidate in as_list(payloads["wf74_autonomy_work_router"].get("pm_job_candidates")):
        job_id = as_dict(candidate).get("job_id")
        if isinstance(job_id, str) and job_id:
            duplicate_pm_job_ids[job_id] = duplicate_pm_job_ids.get(job_id, 0) + 1
    duplicate_pm_job_id_count = sum(1 for count in duplicate_pm_job_ids.values() if count > 1)
    router_generated = parse_utc(payloads["wf74_autonomy_work_router"].get("generated_at_utc"))
    wf88_generated = parse_utc(payloads["wf88_os2_control_packet"].get("generated_at_utc"))
    wiki_generated = parse_utc(payloads["wf88_wiki_synthesis_packet"].get("generated_at_utc"))
    downstream_stale_after_router = {
        "wf88_os2_control_packet": bool(router_generated and wf88_generated and wf88_generated < router_generated),
        "wf88_wiki_synthesis_packet": bool(router_generated and wiki_generated and wiki_generated < router_generated),
    }
    warning_count = 0
    warning_count += len(completed_lane_missing_closeout)
    warning_count += len(completed_lane_missing_memory)
    warning_count += len(completed_lane_telemetry_unverified)
    warning_count += sum(1 for value in downstream_stale_after_router.values() if value)
    warning_count += int(as_dict(payloads["implementation_token_attribution_bridge"].get("summary")).get("implementation_token_gap_count") or 0)
    status = "ok"
    if high_priority_unrouted or duplicate_pm_job_id_count:
        status = "blocked"
    elif warning_count or missing_destination:
        status = "warning"
    return {
        "status": status,
        "trace_row_count": len(trace_rows),
        "missing_destination_count": len(missing_destination),
        "high_priority_unrouted_count": len(high_priority_unrouted),
        "pm_job_link_count": len(pm_linked),
        "lane_link_count": len(lane_linked),
        "lane_link_missing_count": len(lane_link_missing),
        "completed_lane_missing_closeout_count": len(completed_lane_missing_closeout),
        "completed_lane_missing_memory_ref_count": len(completed_lane_missing_memory),
        "completed_lane_telemetry_unverified_count": len(completed_lane_telemetry_unverified),
        "duplicate_pm_job_id_count": duplicate_pm_job_id_count,
        "downstream_stale_after_router": downstream_stale_after_router,
        "downstream_stale_after_router_count": sum(1 for value in downstream_stale_after_router.values() if value),
        "implementation_token_gap_count": as_dict(payloads["implementation_token_attribution_bridge"].get("summary")).get("implementation_token_gap_count"),
        "next_safe_action": (
            "Fix high-priority unrouted or duplicate PM job links before calling the loop healthy."
            if status == "blocked"
            else "Refresh WF88 consumers after WF74 router updates and use missing-link rows to pick the next repair."
        ),
    }


def next_actions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": "refresh-loop-trace-after-wf74-router",
            "state": "active",
            "owner_workflow": "WF74-WF88",
            "next_action": "Regenerate the stitched loop trace after WF74 router, PM queue, or lane-register changes.",
            "command": "python scripts\\wf74_wf88_loop_trace_packet.py --write --write-md --validate",
            "stop_line": "Trace-only; no apply, execution, cron mutation, or owner approval inference.",
        },
        {
            "id": "repair-missing-loop-destinations",
            "state": "blocked" if int(summary.get("high_priority_unrouted_count") or 0) else ("warning" if int(summary.get("missing_destination_count") or 0) else "clean"),
            "owner_workflow": "WF74",
            "next_action": "Route unrouted opportunities into PM job, validator ticket, Skill Workshop proposal, owner packet, or monitor-only state.",
            "command": "python scripts\\wf74_autonomy_work_router.py --write --validate",
            "stop_line": "WF74 routing creates destinations only; it does not apply patches or skills.",
        },
        {
            "id": "refresh-wf88-consumers-after-router",
            "state": "warning" if int(summary.get("downstream_stale_after_router_count") or 0) else "clean",
            "owner_workflow": "WF88",
            "next_action": "Refresh WF88 wiki and OS2 packets when they are older than the latest WF74 router.",
            "command": "python scripts\\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate; python scripts\\wf88_os2_control_packet.py --write --write-md --validate",
            "stop_line": "Consumer refresh only; no cron schedule or runtime mutation.",
        },
    ]
    return rows


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    for name, descriptor in as_dict(packet.get("inputs")).items():
        desc = as_dict(descriptor)
        if desc.get("required") and not desc.get("present"):
            errors.append(f"missing_required_source:{name}:{desc.get('path')}")
    summary = as_dict(packet.get("summary"))
    if int(summary.get("duplicate_pm_job_id_count") or 0):
        errors.append(f"duplicate_pm_job_id_count:{summary.get('duplicate_pm_job_id_count')}")
    if int(summary.get("high_priority_unrouted_count") or 0):
        errors.append(f"high_priority_unrouted_count:{summary.get('high_priority_unrouted_count')}")
    if int(summary.get("missing_destination_count") or 0):
        warnings.append(f"missing_destination_count:{summary.get('missing_destination_count')}")
    if int(summary.get("lane_link_missing_count") or 0):
        warnings.append(f"lane_link_missing_count:{summary.get('lane_link_missing_count')}")
    if int(summary.get("downstream_stale_after_router_count") or 0):
        warnings.append(f"downstream_stale_after_router_count:{summary.get('downstream_stale_after_router_count')}")
    if int(summary.get("completed_lane_missing_closeout_count") or 0):
        warnings.append(f"completed_lane_missing_closeout_count:{summary.get('completed_lane_missing_closeout_count')}")
    if int(summary.get("completed_lane_missing_memory_ref_count") or 0):
        warnings.append(f"completed_lane_missing_memory_ref_count:{summary.get('completed_lane_missing_memory_ref_count')}")
    if int(summary.get("implementation_token_gap_count") or 0):
        warnings.append(f"implementation_token_gap_count:{summary.get('implementation_token_gap_count')}")
    trace_rows = as_list(packet.get("trace_rows"))
    if not trace_rows:
        errors.append("trace_rows_empty")
    for value in trace_rows:
        row = as_dict(value)
        trace_id = str(row.get("trace_id") or "unknown")
        lifecycle_id = str(row.get("lifecycle_id") or "")
        if not lifecycle_id or not str(row.get("origin_opportunity_id") or ""):
            errors.append(f"trace_row_missing_lifecycle_identity:{trace_id}")
        review_event_ref = row.get("review_event_ref")
        if review_event_ref is not None and metadata_only_review_event_ref(
            review_event_ref,
            lifecycle_id=lifecycle_id,
            recommendation_id=str(row.get("recommendation_id") or row.get("opportunity_id") or ""),
        ) is None:
            errors.append(f"trace_row_invalid_review_event_ref:{trace_id}")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def build_packet() -> dict[str, Any]:
    payloads = {name: load(path) for name, path in SOURCE_PATHS.items()}
    inputs = {name: source_descriptor(name, path) for name, path in SOURCE_PATHS.items()}
    trace_rows = build_trace_rows(payloads)
    source_spine = summarize_source_spine(payloads)
    summary = summarize_trace(trace_rows, payloads)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF74-WF88",
        "status": "loop_trace_ready_no_apply_authority",
        "purpose": "Stitch OTEL/model/token/WF74/PM/lane/WF88 evidence into one review-only loop trace.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "inputs": inputs,
        "source_spine": source_spine,
        "summary": summary,
        "trace_rows": trace_rows,
        "next_actions": next_actions(summary),
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "loop_trace_blocked_no_apply_authority"
    elif packet["validation"]["status"] == "warning":
        packet["status"] = "loop_trace_warning_no_apply_authority"
    packet["summary"]["status"] = packet["status"]
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    source_spine = as_dict(packet.get("source_spine"))
    lines = [
        "# WF74 -> WF88 Loop Trace Packet",
        "",
        "## Verdict",
        "",
        "Review-only stitched trace for the WF74/WF88 learning loop. It exposes missing links and stale consumers; it does not approve apply, execution, cron/runtime mutation, portfolio/canon mutation, or model training.",
        "",
        "## Summary",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Trace rows: `{summary.get('trace_row_count')}`",
        f"- Missing destinations: `{summary.get('missing_destination_count')}`",
        f"- High-priority unrouted: `{summary.get('high_priority_unrouted_count')}`",
        f"- PM job links: `{summary.get('pm_job_link_count')}`",
        f"- Lane links: `{summary.get('lane_link_count')}`",
        f"- Lane links missing: `{summary.get('lane_link_missing_count')}`",
        f"- Completed lanes missing closeout proof: `{summary.get('completed_lane_missing_closeout_count')}`",
        f"- Completed lanes missing memory refs: `{summary.get('completed_lane_missing_memory_ref_count')}`",
        f"- Duplicate PM job IDs: `{summary.get('duplicate_pm_job_id_count')}`",
        f"- Downstream stale after WF74 router: `{summary.get('downstream_stale_after_router_count')}`",
        f"- Implementation token gaps: `{summary.get('implementation_token_gap_count')}`",
        "",
        "## Source Spine",
        "",
        f"- OTEL events: `{source_spine.get('otel_event_count')}`",
        f"- Model-learning rows: `{source_spine.get('model_learning_row_count')}`",
        f"- Failure rows: `{source_spine.get('model_learning_failure_rows')}`",
        f"- Runtime/OTEL learning rows: `{source_spine.get('model_learning_runtime_otel_rows')}`",
        f"- Token events: `{source_spine.get('token_event_count')}`",
        f"- API-call reduction candidates: `{source_spine.get('api_call_reduction_candidate_count')}`",
        f"- Prompt-compression candidates: `{source_spine.get('prompt_compression_candidate_count')}`",
        f"- Failure-cost candidates: `{source_spine.get('failure_cost_candidate_count')}`",
        f"- WF88 stale inputs: `{source_spine.get('wf88_stale_input_count')}`",
        "",
        "## Trace Rows",
        "",
    ]
    for row in as_list(packet.get("trace_rows")):
        item = as_dict(row)
        lines.append(
            f"- `{item.get('trace_id')}` `{item.get('opportunity_id')}`: "
            f"route `{item.get('route_status')}` -> PM `{item.get('pm_job_id')}` / "
            f"lane `{item.get('lane_status')}`; missing `{item.get('missing_links')}`"
        )
    lines.extend([
        "",
        "## Next Actions",
        "",
    ])
    for row in as_list(packet.get("next_actions")):
        item = as_dict(row)
        lines.append(f"- `{item.get('id')}`: `{item.get('state')}` - {item.get('next_action')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Review-only trace packet.",
        "- No apply, owner approval inference, cron mutation, runtime/config mutation, portfolio/canon mutation, paper/live execution, external delivery, raw payload capture, or model-training claim.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the WF74 -> WF88 loop trace packet.")
    parser.add_argument("--write", action="store_true", help="Write JSON output.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown sidecar.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero on validation errors.")
    parser.add_argument("--pretty", action="store_true", help="Print the packet.")
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        atomic_write_json(OUT, packet)
    if args.write_md:
        atomic_write_text(MD_OUT, render_markdown(packet))
    if args.pretty or not args.write:
        print(json.dumps(packet, indent=2, sort_keys=True))
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
