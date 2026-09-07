#!/usr/bin/env python3
"""Build the WF88 wiki synthesis packet and durable wiki pages.

This is a review-only synthesis layer. It reads current WF88, WF74, PM, OTEL,
RSI, scorecard, and improvement-ledger artifacts; writes a machine-readable
packet; and can refresh durable wiki pages that route future sessions back to
the exact proof artifacts.

It does not create canon, approval, execution, cron, portfolio, or model
training authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import project_implementation_router as implementation_router
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
WIKI = ROOT / "wiki"

OUT = TMP / "wf88-wiki-synthesis-packet.json"
MD_OUT = TMP / "wf88-wiki-synthesis-packet.md"
SCHEMA = "veritas.wf88_wiki_synthesis_packet.v1"
CLAIM_INDEX_SCHEMA = "veritas.wf88_wiki_claim_index.v1"
REVIEW_EVENT_SCHEMA = "veritas.wf88_wiki_review_events.v1"
REVIEW_EVENT_FILENAME = "wf88-wiki-review-events.json"
STARTUP_EFFICIENCY_SEMANTIC_SCHEMA = implementation_router.EFFICIENCY_SEMANTIC_CONTRACT_SCHEMA

SOURCES = {
    "wf88_os2_control": {"path": "tmp/wf88-os2-control-packet.json", "required": True, "max_age_hours": 24},
    "otel_ops_control": {"path": "tmp/otel-ops-control.json", "required": True, "max_age_hours": 24},
    "otel_ops_window_summary": {"path": "tmp/otel-ops-window-summary.json", "required": False, "max_age_hours": 24},
    "model_learning_metadata_ledger": {"path": "tmp/model-learning-metadata-ledger.json", "required": True, "max_age_hours": 24},
    "wf74_improvement_opportunity_queue": {"path": "tmp/wf74-improvement-opportunity-queue.json", "required": True, "max_age_hours": 24},
    "wf74_reflection_to_proposal_autopilot": {"path": "tmp/wf74-reflection-to-proposal-autopilot.json", "required": True, "max_age_hours": 24},
    "wf74_auto_patch_proposer": {"path": "tmp/wf74-auto-patch-proposer.json", "required": True, "max_age_hours": 24},
    "wf74_autonomy_work_router": {"path": "tmp/wf74-autonomy-work-router.json", "required": True, "max_age_hours": 24},
    "wf74_decision_docket": {"path": "tmp/wf74-decision-docket.json", "required": True, "max_age_hours": 24},
    "wf74_wf88_loop_trace": {"path": "tmp/wf74-wf88-loop-trace.json", "required": True, "max_age_hours": 24},
    "long_work_job_status": {"path": "tmp/long-work-job-status-packet.json", "required": True, "max_age_hours": 24},
    "wf74_learning_loop_eval_harness": {"path": "tmp/wf74-learning-loop-eval-harness.json", "required": True, "max_age_hours": 72},
    "wf74_outcome_eval_suite_v2": {"path": "tmp/wf74-outcome-eval-suite-v2.json", "required": True, "max_age_hours": 168},
    "model_quality_scorecard": {"path": "tmp/model-quality-scorecard.json", "required": True, "max_age_hours": 72},
    "veritas_harness_scorecard": {"path": "tmp/veritas-harness-scorecard.json", "required": False, "max_age_hours": 168},
    "retrieval_quality_scorecard": {"path": "tmp/retrieval-quality-scorecard.json", "required": True, "max_age_hours": 168},
    "frontier_capability_eval_spine": {"path": "tmp/frontier-capability-eval-spine.json", "required": True, "max_age_hours": 168},
    "wf88_decision_compiler": {"path": "tmp/wf88-decision-compiler.json", "required": True, "max_age_hours": 24},
    "rsi_outcome_scorecard": {"path": "tmp/rsi-outcome-scorecard.json", "required": True, "max_age_hours": 24},
    "advanced_capability_pilot_packet": {"path": "tmp/advanced-capability-pilot-packet.json", "required": True, "max_age_hours": 168},
    "route_efficiency_scorecard": {"path": "tmp/route-efficiency-scorecard.json", "required": False, "max_age_hours": 24},
    "token_usage_ledger": {"path": "tmp/token-usage-ledger-current.json", "required": False, "max_age_hours": 24},
    "token_budget_status": {"path": "tmp/token-budget-status.json", "required": False, "max_age_hours": 24},
    "token_efficiency_scorecard": {"path": "tmp/token-efficiency-scorecard.json", "required": False, "max_age_hours": 24},
    "implementation_token_attribution_bridge": {"path": "tmp/implementation-token-attribution-bridge.json", "required": False, "max_age_hours": 24},
    "coding_outcome_ledger": {"path": "tmp/coding-outcome-ledger-current.json", "required": False, "max_age_hours": 24},
    "pm_control_packet": {"path": "tmp/pm-control-packet.json", "required": True, "max_age_hours": 12},
    "recommendation_outcome_ledger": {"path": "tmp/recommendation-outcome-ledger-current.json", "required": True, "max_age_hours": 168},
    "improvement_ledger": {"path": "tmp/improvement-ledger-current.json", "required": True, "max_age_hours": 24},
    "actionable_improvement_queue": {"path": "tmp/actionable-improvement-queue.json", "required": True, "max_age_hours": 24},
    "no_orphan_validator": {"path": "tmp/no-orphan-validator.json", "required": True, "max_age_hours": 24},
}

COMPATIBILITY_SURFACES = {
    "wf74_legacy_rsi_evaluation_harness": {
        "path": "tmp/wf74-rsi-evaluation-harness.json",
        "status": "deprecated_compatibility_drill_in_only",
        "first_hop_truth": False,
        "required_source": False,
        "producer": "python scripts\\wf74_rsi.py",
        "validate_only_command": "python scripts\\wf74_rsi.py --validate-only",
    }
}

EXPECTED_WIKI_PAGES = [
    "wiki/README.md",
    "wiki/index.md",
    "wiki/syntheses/Cold Session Operating Routes.md",
    "wiki/os2/OTEL To Proposal Route.md",
    "wiki/scorecards-and-evals/Current Map.md",
    "wiki/scorecards-and-evals/Frontier Capability Eval.md",
    "wiki/scorecards-and-evals/Advanced Capability Pilots.md",
    "wiki/scorecards-and-evals/Token Efficiency Map.md",
    "wiki/decisions/Decision Compiler.md",
    "wiki/self-improvement/Prompt Book RSI Loop.md",
    "wiki/self-improvement/RSI Control Loop.md",
    "wiki/recommendations/Action Promotion Map.md",
    "wiki/gaps/Open Follow Up Debt.md",
    "wiki/source-map/WF88 Wiki Source Map.md",
    "wiki/changes/What Changed Since Last Refresh.md",
]

# These labels describe generated-page purpose only. They never change source
# authority or create a Wiki-to-compiler input path.
VALID_PAGE_TYPES = {
    "landing",
    "index",
    "route_map",
    "scorecard_map",
    "evaluation_contract",
    "decision_map",
    "promotion_map",
    "debt_view",
    "source_map",
    "refresh_delta",
    "knowledge_guide",
}

WIKI_PAGE_TYPES = {
    "wiki/README.md": "landing",
    "wiki/index.md": "index",
    "wiki/syntheses/Cold Session Operating Routes.md": "knowledge_guide",
    "wiki/os2/OTEL To Proposal Route.md": "route_map",
    "wiki/scorecards-and-evals/Current Map.md": "scorecard_map",
    "wiki/scorecards-and-evals/Frontier Capability Eval.md": "evaluation_contract",
    "wiki/scorecards-and-evals/Advanced Capability Pilots.md": "evaluation_contract",
    "wiki/scorecards-and-evals/Token Efficiency Map.md": "scorecard_map",
    "wiki/decisions/Decision Compiler.md": "decision_map",
    "wiki/self-improvement/Prompt Book RSI Loop.md": "route_map",
    "wiki/self-improvement/RSI Control Loop.md": "evaluation_contract",
    "wiki/recommendations/Action Promotion Map.md": "promotion_map",
    "wiki/gaps/Open Follow Up Debt.md": "debt_view",
    "wiki/source-map/WF88 Wiki Source Map.md": "source_map",
    "wiki/changes/What Changed Since Last Refresh.md": "refresh_delta",
}

RETRIEVAL_VAULT_REL = "state/wiki-retrieval"
RETRIEVAL_SOURCE_REL = f"{RETRIEVAL_VAULT_REL}/sources/WF88 Compiled Wiki.md"
RETRIEVAL_PAGE_DIR_REL = f"{RETRIEVAL_VAULT_REL}/sources/canonical"

# Keep these terse and specific. They improve lexical recall for the queries a
# cold session is likely to use; they do not change canonical page content or
# authority. Every canonical page gets a stable retrieval identity and aliases.
RETRIEVAL_PAGE_ALIASES = {
    "wiki/README.md": ["wiki retrieval startup", "wiki source authority", "WF88 synthesis map"],
    "wiki/index.md": ["wiki page index", "wiki navigation route", "cold session wiki map"],
    "wiki/syntheses/Cold Session Operating Routes.md": ["cron failure triage", "implementation routing", "cold session startup"],
    "wiki/os2/OTEL To Proposal Route.md": ["OTEL proposal route", "WF74 WF88 routing", "operational telemetry followup"],
    "wiki/scorecards-and-evals/Current Map.md": ["current scorecard map", "evaluation status", "quality proof route"],
    "wiki/scorecards-and-evals/Frontier Capability Eval.md": ["frontier capability evaluation", "matched model eval", "blind scorer contract"],
    "wiki/scorecards-and-evals/Advanced Capability Pilots.md": ["advanced capability pilots", "isolated pilot gate", "pilot execution evidence"],
    "wiki/scorecards-and-evals/Token Efficiency Map.md": ["token attribution", "implementation token efficiency", "route retry tax"],
    "wiki/decisions/Decision Compiler.md": ["decision object compiler", "evidence to decision", "review only decision route"],
    "wiki/self-improvement/Prompt Book RSI Loop.md": ["prompt book loop", "prompt evaluation friction", "WF74 skill workshop route"],
    "wiki/self-improvement/RSI Control Loop.md": ["recursive self improvement", "RSI control loop", "guarded improvement evidence"],
    "wiki/recommendations/Action Promotion Map.md": ["recommendation promotion", "action routing", "no orphan followup"],
    "wiki/gaps/Open Follow Up Debt.md": ["open followup triage", "improvement debt", "unrouted action backlog"],
    "wiki/source-map/WF88 Wiki Source Map.md": ["WF88 source map", "owner artifact lookup", "source open proof"],
    "wiki/changes/What Changed Since Last Refresh.md": ["wiki refresh delta", "recent wiki changes", "claim catalog change"],
}

REVIEW_EVENT_DISPOSITIONS = {
    "confirmed",
    "stale",
    "conflicting",
    "needs_evidence",
    "superseded",
    "route_to_owner",
    "outcome_recorded",
}
REVIEW_EVENT_REASON_CODES = {
    "evidence_verified",
    "source_stale",
    "source_conflict",
    "evidence_missing",
    "superseded_by_source",
    "owner_review_required",
    "outcome_link_recorded",
}
REVIEW_EVENT_WORK_REQUIRED = {"stale", "conflicting", "needs_evidence", "route_to_owner"}
REVIEW_EVENT_ALLOWED_KEYS = {
    "event_id",
    "event_at_utc",
    "claim_id",
    "disposition",
    "reason_code",
    "source_ref",
    "followup_ref",
}
REVIEW_EVENT_ALLOWED_ROUTES = {"WF74", "PM", "Skill Workshop"}
REVIEW_EVENT_ROUTE_SOURCE_KEYS = {
    "WF74": {
        "wf74_decision_docket",
        "wf74_autonomy_work_router",
        "wf74_improvement_opportunity_queue",
        "wf74_reflection_to_proposal_autopilot",
        "wf74_auto_patch_proposer",
        "wf74_wf88_loop_trace",
    },
    "PM": {"pm_control_packet"},
    "Skill Workshop": {"wf74_auto_patch_proposer", "improvement_ledger"},
}
REVIEW_EVENT_FORBIDDEN_KEYS = {
    "approval",
    "apply",
    "apply_allowed",
    "auto_apply",
    "execution",
    "state",
    "action_state",
    "claim_value",
    "normalized_value",
    "raw_prompt",
    "raw_response",
    "tool_payload",
    "comment",
    "note",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "synthesis_only": True,
    "routes_existing_artifacts": True,
    "creates_canon": False,
    "approval_authority": False,
    "delete_archive_or_move_allowed": False,
    "apply_allowed": False,
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
    "raw_prompt_or_tool_capture_allowed": False,
    "owner_approval_inferred": False,
}

SELF_PROMPTS = [
    "What changed in the evidence, and which exact artifact proves it?",
    "Is this a one-time note, a wiki synthesis update, a WF74 proposal, a PM lane, a skill proposal, or a validator gap?",
    "What action should surface next, and which stop line prevents overreach?",
    "Did an improvement recommendation route to a docket, PM job, owner packet, or monitor-only state?",
    "Does any wording imply canon, approval, execution, or model-performance authority that the source artifacts do not grant?",
    "What should a new session open first before repeating this decision?",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def wiki_markdown_paths() -> list[str]:
    """Return the physical canonical wiki Markdown set, not a manifest count."""
    if not WIKI.exists():
        return []
    return sorted(rel(path) for path in WIKI.rglob("*.md") if path.is_file())


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def load_json_bytes(raw: bytes) -> dict[str, Any]:
    """Match the artifact loader while retaining one immutable source read."""
    cleaned = raw.replace(b"\x00", b"").strip()
    if not cleaned:
        return {}
    try:
        text = cleaned.decode("utf-8")
    except UnicodeDecodeError:
        text = cleaned.decode("utf-8", errors="replace")
    try:
        return as_dict(json.loads(text))
    except json.JSONDecodeError:
        try:
            value, _ = json.JSONDecoder().raw_decode(text)
            return as_dict(value)
        except Exception:
            return {}


def source_path(name: str) -> Path:
    return ROOT / str(SOURCES[name]["path"])


def source_descriptor(
    name: str,
    *,
    payload: dict[str, Any] | None = None,
    present: bool | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    config = SOURCES[name]
    path = ROOT / str(config["path"])
    snapshot_payload = payload if payload is not None else load(path)
    snapshot_present = path.exists() if present is None else present
    generated_at = snapshot_payload.get("generated_at_utc")
    generated_dt = parse_utc(generated_at)
    age_hours = None
    freshness = "missing" if not snapshot_present else "unknown_generated_at"
    max_age = config.get("max_age_hours")
    if generated_dt is not None:
        age_hours = round((datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600.0, 2)
        freshness = "fresh" if max_age is None or age_hours <= float(max_age) else "stale"
    return {
        "path": rel(path),
        "present": snapshot_present,
        "required": bool(config.get("required")),
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "max_age_hours": max_age,
        "freshness_status": freshness,
        "status": snapshot_payload.get("status"),
        "validation_status": as_dict(snapshot_payload.get("validation")).get("status"),
        "sha256": content_sha256 if content_sha256 is not None else sha256_file(path),
    }


def source_snapshot(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read each upstream artifact once for one build's values and provenance."""
    path = source_path(name)
    try:
        raw = path.read_bytes()
    except OSError:
        raw = b""
        present = False
    else:
        present = True
    payload = load_json_bytes(raw)
    content_sha256 = hashlib.sha256(raw).hexdigest() if present else None
    return payload, source_descriptor(
        name,
        payload=payload,
        present=present,
        content_sha256=content_sha256,
    )


def source_snapshots() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    snapshots = {name: source_snapshot(name) for name in SOURCES}
    return (
        {name: payload for name, (payload, _) in snapshots.items()},
        {name: descriptor for name, (_, descriptor) in snapshots.items()},
    )


def source_descriptors() -> dict[str, dict[str, Any]]:
    return source_snapshots()[1]


def source_ref(inputs: dict[str, dict[str, Any]], source_key: str, json_pointer: str) -> dict[str, Any]:
    descriptor = as_dict(inputs.get(source_key))
    return {
        "source_key": source_key,
        "path": descriptor.get("path"),
        "json_pointer": json_pointer,
        "generated_at_utc": descriptor.get("generated_at_utc"),
        "sha256": descriptor.get("sha256"),
    }


def source_refs(inputs: dict[str, dict[str, Any]], *specs: tuple[str, str]) -> list[dict[str, Any]]:
    return [source_ref(inputs, source_key, json_pointer) for source_key, json_pointer in specs]


def json_pointer_get(payload: Any, pointer: Any) -> tuple[bool, Any]:
    """Resolve a small RFC 6901 JSON Pointer without ever interpreting Markdown."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False, None
    current = payload
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def _claim(
    claim_id: str,
    claim_kind: str,
    page_paths: list[str],
    normalized_value: Any,
    refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "claim_kind": claim_kind,
        "page_paths": page_paths,
        "normalized_value": normalized_value,
        "source_refs": refs,
        "authority": "review_only",
    }


def build_claim_index(
    inputs: dict[str, dict[str, Any]], summary: dict[str, Any], actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Expose only decision-bearing, metadata-safe Wiki claims and upstream proof refs."""
    action_sources: dict[str, list[tuple[str, str]]] = {
        "refresh-wf88-wiki-synthesis": [("wf88_os2_control", "/status")],
        "grade-recommendation-outcomes": [("wf88_os2_control", "/summary/recommendation_current_preview_later_outcome_graded_rows")],
        "mature-rsi-eval-harness": [("wf74_learning_loop_eval_harness", "/rsi_maturity/status")],
        "route-open-improvement-followups": [("improvement_ledger", "/summary/followup_required_open_count")],
        "enforce-no-orphan-improvement-actions": [("no_orphan_validator", "/validation/status")],
        "maintain-wf74-wf88-loop-trace": [
            ("wf74_wf88_loop_trace", "/summary/high_priority_unrouted_count"),
            ("wf74_wf88_loop_trace", "/summary/duplicate_pm_job_id_count"),
            ("wf74_wf88_loop_trace", "/summary/downstream_stale_after_router_count"),
            ("wf74_wf88_loop_trace", "/summary/lane_link_missing_count"),
        ],
        "maintain-long-work-job-status": [
            ("long_work_job_status", "/validation/status"),
            ("long_work_job_status", "/summary/blocked_job_count"),
            ("long_work_job_status", "/summary/resumable_job_count"),
            ("long_work_job_status", "/summary/stale_active_job_count"),
            ("long_work_job_status", "/summary/active_job_count"),
        ],
        "optimize-token-heavy-cron-api-calls": [
            ("token_efficiency_scorecard", "/summary/api_call_reduction_candidate_count"),
        ],
        "close-implementation-token-attribution-gap": [
            ("implementation_token_attribution_bridge", "/summary/implementation_token_gap_count"),
        ],
        "maintain-wf88-retrieval-regression-corpus": [
            ("retrieval_quality_scorecard", "/status"),
            ("retrieval_quality_scorecard", "/validation/status"),
        ],
        "collect-frontier-capability-eval-results": [
            ("frontier_capability_eval_spine", "/status"),
            ("frontier_capability_eval_spine", "/validation/status"),
            ("frontier_capability_eval_spine", "/result_collection/row_count"),
            ("frontier_capability_eval_spine", "/comparison_readiness/cross_model_ranking_allowed"),
        ],
        "compile-wf88-decision-objects": [
            ("wf88_decision_compiler", "/status"),
            ("wf88_decision_compiler", "/validation/status"),
            ("wf88_decision_compiler", "/summary/decision_object_count"),
            ("wf88_decision_compiler", "/leak_guard/pass"),
        ],
        "close-rsi-outcome-linkage-debt": [
            ("rsi_outcome_scorecard", "/status"),
            ("rsi_outcome_scorecard", "/validation/status"),
            ("rsi_outcome_scorecard", "/maturity_gate/mature"),
            ("rsi_outcome_scorecard", "/summary/live_complete_stable_count"),
            ("rsi_outcome_scorecard", "/summary/missing_link_debt_item_count"),
        ],
        "run-isolated-advanced-capability-pilots": [
            ("advanced_capability_pilot_packet", "/status"),
            ("advanced_capability_pilot_packet", "/summary/executed_pilot_count"),
            ("advanced_capability_pilot_packet", "/summary/promotion_ready_count"),
        ],
        "preserve-zero-auto-apply": [("wf74_auto_patch_proposer", "/summary/auto_apply_count")],
    }
    claims = [
        _claim(
            f"action-state:{action.get('id')}",
            "rendered_action_state",
            ["wiki/README.md", "wiki/recommendations/Action Promotion Map.md"],
            {"state": action.get("state")},
            source_refs(inputs, *action_sources.get(str(action.get("id")), [])),
        )
        for action in actions
    ]
    claims.extend([
        _claim(
            "promotion-leak-guard-health",
            "promotion_leak_guard_health",
            ["wiki/os2/OTEL To Proposal Route.md", "wiki/recommendations/Action Promotion Map.md"],
            {
                "pass": int(summary.get("open_unrouted_recommendation_count") or 0) == 0
                and int(summary.get("auto_apply_count") or 0) == 0,
                "open_unrouted_recommendation_count": int(summary.get("open_unrouted_recommendation_count") or 0),
                "auto_apply_count": int(summary.get("auto_apply_count") or 0),
            },
            source_refs(
                inputs,
                ("wf74_autonomy_work_router", "/summary/open_unrouted_recommendation_count"),
                ("wf74_auto_patch_proposer", "/summary/auto_apply_count"),
            ),
        ),
        _claim(
            "recommendation-outcome-closure",
            "recommendation_outcome_closure",
            ["wiki/scorecards-and-evals/Current Map.md", "wiki/recommendations/Action Promotion Map.md"],
            {
                "later_outcome_graded_rows": summary.get("recommendation_later_outcome_graded_rows"),
                "current_preview_later_outcome_graded_rows": summary.get("recommendation_current_preview_later_outcome_graded_rows"),
                "durable_later_outcome_graded_rows": summary.get("recommendation_durable_later_outcome_graded_rows"),
                "grade_history_graded_ledger_event_count": summary.get("recommendation_grade_history_graded_ledger_event_count"),
            },
            source_refs(
                inputs,
                ("wf88_os2_control", "/summary/recommendation_later_outcome_graded_rows"),
                ("wf88_os2_control", "/summary/recommendation_current_preview_later_outcome_graded_rows"),
                ("wf88_os2_control", "/summary/recommendation_durable_later_outcome_graded_rows"),
                ("wf88_os2_control", "/summary/recommendation_grade_history_graded_ledger_event_count"),
            ),
        ),
        _claim(
            "followup-no-orphan-health",
            "followup_no_orphan_health",
            ["wiki/gaps/Open Follow Up Debt.md", "wiki/recommendations/Action Promotion Map.md"],
            {
                "followup_required_open_count": summary.get("followup_required_open_count"),
                "actionable_orphan_count": summary.get("actionable_orphan_count"),
                "actionable_missing_contract_count": summary.get("actionable_missing_contract_count"),
                "no_orphan_validation": summary.get("no_orphan_validation"),
            },
            source_refs(
                inputs,
                ("improvement_ledger", "/summary/followup_required_open_count"),
                ("actionable_improvement_queue", "/summary/orphan_count"),
                ("actionable_improvement_queue", "/summary/missing_contract_count"),
                ("no_orphan_validator", "/validation/status"),
            ),
        ),
    ])
    return {
        "schema": CLAIM_INDEX_SCHEMA,
        "authority": "review_only",
        "claim_count": len(claims),
        "claims": claims,
    }


def review_event_path() -> Path:
    return TMP / REVIEW_EVENT_FILENAME


def review_event_contract() -> dict[str, Any]:
    return {
        "schema": REVIEW_EVENT_SCHEMA,
        "path": rel(review_event_path()),
        "optional": True,
        "upstream_owned": True,
        "writer_present": False,
        "rendering": "references_only",
        "allowed_event_fields": sorted(REVIEW_EVENT_ALLOWED_KEYS),
        "allowed_dispositions": sorted(REVIEW_EVENT_DISPOSITIONS),
        "allowed_reason_codes": sorted(REVIEW_EVENT_REASON_CODES),
        "work_required_routes": sorted(REVIEW_EVENT_ALLOWED_ROUTES),
        "followup_ref_shape": "{route, source_ref}; source_ref must resolve to an existing route-owned upstream artifact",
        "route_source_keys": {
            route: sorted(source_keys) for route, source_keys in REVIEW_EVENT_ROUTE_SOURCE_KEYS.items()
        },
        "forbidden_effects": [
            "claim_mutation",
            "action_mutation",
            "approval",
            "apply",
            "execution",
            "compiler_input",
            "raw_prompt_response_or_tool_payload_retention",
        ],
    }


def _source_ref_identity(ref: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any]:
    return (
        ref.get("source_key"),
        ref.get("path"),
        ref.get("json_pointer"),
        ref.get("generated_at_utc"),
        ref.get("sha256"),
    )


def _safe_ref_id(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", value))


def _normalize_followup_ref(
    value: Any, inputs: dict[str, dict[str, Any]], source_payloads: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, dict) or set(value) != {"route", "source_ref"}:
        return None, "followup_ref_must_be_exact_route_and_source_ref"
    route = value.get("route")
    if route not in REVIEW_EVENT_ALLOWED_ROUTES:
        return None, "followup_ref_route_not_existing_owner_surface"
    ref = as_dict(value.get("source_ref"))
    if set(ref) != {"source_key", "path", "json_pointer", "generated_at_utc", "sha256"}:
        return None, "followup_ref_source_shape_invalid"
    source_key = ref.get("source_key")
    if source_key not in REVIEW_EVENT_ROUTE_SOURCE_KEYS.get(str(route), set()):
        return None, "followup_ref_source_not_owned_by_route"
    descriptor = as_dict(inputs.get(str(source_key)))
    if not descriptor or _source_ref_identity(ref) != _source_ref_identity({
        "source_key": source_key,
        "path": descriptor.get("path"),
        "json_pointer": ref.get("json_pointer"),
        "generated_at_utc": descriptor.get("generated_at_utc"),
        "sha256": descriptor.get("sha256"),
    }):
        return None, "followup_ref_source_descriptor_mismatch"
    pointer_valid, _ = json_pointer_get(source_payloads.get(str(source_key)), ref.get("json_pointer"))
    if not pointer_valid:
        return None, "followup_ref_source_pointer_invalid"
    return {"route": str(route), "source_ref": ref}, None


def review_event_intake(
    claim_index: dict[str, Any], inputs: dict[str, dict[str, Any]], source_payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Read a strictly metadata-only, upstream-owned review reference file.

    The generator never writes this file. Invalid material stays out of the
    rendered reference list and makes validation fail closed.
    """
    path = review_event_path()
    intake: dict[str, Any] = {
        "path": rel(path),
        "present": path.exists(),
        "mode": "optional_upstream_reference_only",
        "event_count": 0,
        "events": [],
        "errors": [],
    }
    if not path.exists():
        intake["status"] = "not_present_optional"
        return intake

    raw = load(path)
    intake["schema"] = raw.get("schema")
    intake["generated_at_utc"] = raw.get("generated_at_utc")
    outer_allowed = {"schema", "generated_at_utc", "events"}
    outer_extra = sorted(set(raw) - outer_allowed)
    if outer_extra:
        intake["errors"].append(f"review_event_intake_unallowed_field:{','.join(outer_extra)}")
    if raw.get("schema") != REVIEW_EVENT_SCHEMA:
        intake["errors"].append("review_event_intake_schema_invalid")
    if parse_utc(raw.get("generated_at_utc")) is None:
        intake["errors"].append("review_event_intake_generated_at_invalid")
    raw_events = raw.get("events")
    if not isinstance(raw_events, list):
        intake["errors"].append("review_event_intake_events_not_list")
        intake["status"] = "invalid"
        return intake

    claims = {
        str(as_dict(claim).get("claim_id")): as_dict(claim)
        for claim in as_list(claim_index.get("claims"))
    }
    valid_events: list[dict[str, Any]] = []
    for index, raw_event in enumerate(raw_events):
        event = as_dict(raw_event)
        prefix = f"review_event:{index}"
        if not isinstance(raw_event, dict):
            intake["errors"].append(f"{prefix}:not_object")
            continue
        unknown_keys = sorted(set(event) - REVIEW_EVENT_ALLOWED_KEYS)
        forbidden_keys = sorted(set(event) & REVIEW_EVENT_FORBIDDEN_KEYS)
        if forbidden_keys:
            intake["errors"].append(f"{prefix}:forbidden_field:{','.join(forbidden_keys)}")
        if unknown_keys:
            intake["errors"].append(f"{prefix}:unallowed_field:{','.join(unknown_keys)}")
        event_id = event.get("event_id")
        event_at = event.get("event_at_utc")
        claim_id = event.get("claim_id")
        disposition = event.get("disposition")
        reason_code = event.get("reason_code")
        if not _safe_ref_id(event_id):
            intake["errors"].append(f"{prefix}:invalid_event_id")
        if parse_utc(event_at) is None:
            intake["errors"].append(f"{prefix}:invalid_event_at_utc")
        if not isinstance(claim_id, str) or claim_id not in claims:
            intake["errors"].append(f"{prefix}:unknown_claim_id")
        if disposition not in REVIEW_EVENT_DISPOSITIONS:
            authority_word = str(disposition or "").lower()
            code = "authoritative_disposition" if any(
                word in authority_word for word in ("approv", "apply", "execut", "promot", "override")
            ) else "invalid_disposition"
            intake["errors"].append(f"{prefix}:{code}")
        if reason_code not in REVIEW_EVENT_REASON_CODES:
            intake["errors"].append(f"{prefix}:invalid_reason_code")
        ref = as_dict(event.get("source_ref"))
        if set(ref) != {"source_key", "path", "json_pointer", "generated_at_utc", "sha256"}:
            intake["errors"].append(f"{prefix}:source_ref_shape_invalid")
        ref_path = str(ref.get("path") or "").replace("\\", "/")
        if ref_path.startswith("wiki/") or ref_path.endswith(".md") or ref_path in {
            "tmp/wf88-wiki-synthesis-packet.json",
            "tmp/wf88-wiki-synthesis-packet.md",
        }:
            intake["errors"].append(f"{prefix}:source_ref_prohibited_path")
        claim_refs = [as_dict(item) for item in as_list(as_dict(claims.get(str(claim_id))).get("source_refs"))]
        if _source_ref_identity(ref) not in {_source_ref_identity(item) for item in claim_refs}:
            intake["errors"].append(f"{prefix}:source_ref_not_owned_by_claim")
        followup_ref, followup_error = (
            _normalize_followup_ref(event.get("followup_ref"), inputs, source_payloads)
            if event.get("followup_ref") is not None
            else (None, None)
        )
        if followup_error:
            intake["errors"].append(f"{prefix}:{followup_error}")
        if disposition in REVIEW_EVENT_WORK_REQUIRED and followup_ref is None:
            intake["errors"].append(f"{prefix}:work_required_followup_ref_missing")
        if unknown_keys or forbidden_keys or any(
            message.startswith(f"{prefix}:") for message in as_list(intake.get("errors"))
        ):
            continue
        valid_events.append({
            "event_id": event_id,
            "event_at_utc": event_at,
            "claim_id": claim_id,
            "disposition": disposition,
            "reason_code": reason_code,
            "source_ref": ref,
            "followup_ref": followup_ref,
        })
    intake["events"] = valid_events
    intake["event_count"] = len(valid_events)
    intake["status"] = "ok" if not intake["errors"] else "invalid"
    return intake


def _claim_catalog(claim_index: Any) -> dict[str, dict[str, Any]] | None:
    index = as_dict(claim_index)
    if index.get("schema") != CLAIM_INDEX_SCHEMA or index.get("authority") != "review_only":
        return None
    claims = as_list(index.get("claims"))
    catalog: dict[str, dict[str, Any]] = {}
    for raw_claim in claims:
        claim = as_dict(raw_claim)
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id or claim_id in catalog:
            return None
        catalog[claim_id] = claim
    return catalog


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_refresh_delta(claim_index: dict[str, Any], previous_packet: dict[str, Any] | None) -> dict[str, Any]:
    """Compare claim catalogues only; never use a prior summary or action state."""
    current = _claim_catalog(claim_index)
    previous = _claim_catalog(as_dict(previous_packet).get("claim_index"))
    if current is None:
        return {
            "status": "unavailable",
            "reason": "current_claim_catalog_invalid",
            "added_claim_ids": [],
            "removed_claim_ids": [],
            "changed_claim_ids": [],
            "source_ref_changed_claim_ids": [],
        }
    if previous is None:
        return {
            "status": "unavailable",
            "reason": "prior_claim_catalog_missing_or_incompatible",
            "baseline_generated_at_utc": as_dict(previous_packet).get("generated_at_utc"),
            "added_claim_ids": [],
            "removed_claim_ids": [],
            "changed_claim_ids": [],
            "source_ref_changed_claim_ids": [],
        }
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed: list[str] = []
    ref_changed: list[str] = []
    for claim_id in sorted(set(current) & set(previous)):
        current_claim = current[claim_id]
        previous_claim = previous[claim_id]
        if _stable_json(current_claim.get("normalized_value")) != _stable_json(previous_claim.get("normalized_value")):
            changed.append(claim_id)
        current_refs = sorted(_source_ref_identity(as_dict(ref)) for ref in as_list(current_claim.get("source_refs")))
        previous_refs = sorted(_source_ref_identity(as_dict(ref)) for ref in as_list(previous_claim.get("source_refs")))
        if current_refs != previous_refs:
            ref_changed.append(claim_id)
    return {
        "status": "available",
        "baseline_generated_at_utc": as_dict(previous_packet).get("generated_at_utc"),
        "added_claim_ids": added,
        "removed_claim_ids": removed,
        "changed_claim_ids": changed,
        "source_ref_changed_claim_ids": ref_changed,
    }


def summary_from(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    wf88_summary = as_dict(payloads["wf88_os2_control"].get("summary"))
    auto_patch_summary = as_dict(payloads["wf74_auto_patch_proposer"].get("summary"))
    router_summary = as_dict(payloads["wf74_autonomy_work_router"].get("summary"))
    loop_trace_summary = as_dict(payloads["wf74_wf88_loop_trace"].get("summary"))
    loop_trace_source_spine = as_dict(payloads["wf74_wf88_loop_trace"].get("source_spine"))
    long_work_summary = as_dict(payloads["long_work_job_status"].get("summary"))
    docket_summary = as_dict(payloads["wf74_decision_docket"].get("summary"))
    improvement_summary = as_dict(payloads["improvement_ledger"].get("summary"))
    eval_summary = as_dict(payloads["wf74_learning_loop_eval_harness"].get("summary"))
    outcome_eval_summary = as_dict(payloads["wf74_outcome_eval_suite_v2"].get("summary"))
    model_quality_summary = as_dict(payloads["model_quality_scorecard"].get("summary"))
    recommendation_summary = as_dict(payloads["recommendation_outcome_ledger"].get("summary"))
    otel_summary = as_dict(payloads["otel_ops_control"].get("summary"))
    actionable_summary = as_dict(payloads["actionable_improvement_queue"].get("summary"))
    no_orphan_summary = as_dict(payloads["no_orphan_validator"].get("summary"))
    token_summary = as_dict(payloads["token_usage_ledger"].get("summary"))
    token_budget_summary = as_dict(payloads["token_budget_status"].get("summary"))
    token_efficiency_summary = as_dict(payloads["token_efficiency_scorecard"].get("summary"))
    token_bridge_summary = as_dict(payloads["implementation_token_attribution_bridge"].get("summary"))
    coding_outcome_summary = as_dict(payloads["coding_outcome_ledger"].get("ledger_summary"))
    coding_outcome_gate = as_dict(coding_outcome_summary.get("comparable_cohort_sample_gate"))
    token_billing_semantics = (
        as_dict(payloads["token_usage_ledger"].get("billing_semantics"))
        or as_dict(payloads["token_budget_status"].get("billing_semantics"))
        or as_dict(payloads["token_efficiency_scorecard"].get("billing_semantics"))
    )
    token_oauth_capacity = (
        as_dict(payloads["token_usage_ledger"].get("oauth_capacity_control"))
        or as_dict(payloads["token_budget_status"].get("oauth_capacity_control"))
        or as_dict(payloads["token_efficiency_scorecard"].get("oauth_capacity_control"))
    )
    token_usage_pace = (
        as_dict(payloads["token_usage_ledger"].get("usage_pace"))
        or as_dict(payloads["token_budget_status"].get("usage_pace"))
        or as_dict(payloads["token_efficiency_scorecard"].get("usage_pace"))
    )
    retrieval_summary = as_dict(payloads["retrieval_quality_scorecard"].get("summary"))
    retrieval_freshness = as_dict(retrieval_summary.get("freshness_proof"))
    retrieval_measurement = as_dict(payloads["retrieval_quality_scorecard"].get("measurement_contract"))
    retrieval_freshness_contract = as_dict(retrieval_measurement.get("freshness"))
    frontier_fixture = as_dict(payloads["frontier_capability_eval_spine"].get("fixture_integrity"))
    frontier_design = as_dict(payloads["frontier_capability_eval_spine"].get("study_design"))
    frontier_results = as_dict(payloads["frontier_capability_eval_spine"].get("result_collection"))
    frontier_legacy_proof = as_dict(frontier_results.get("proof_verification"))
    frontier_local_integrity = as_dict(frontier_results.get("local_integrity_validation"))
    frontier_attestation = as_dict(frontier_results.get("independent_attestation"))
    frontier_comparison = as_dict(payloads["frontier_capability_eval_spine"].get("comparison_readiness"))
    frontier_attribution = as_dict(payloads["frontier_capability_eval_spine"].get("baseline_attribution_context"))
    frontier_recent_attribution = as_dict(frontier_attribution.get("recent_model_attribution"))
    frontier_usage_attribution = as_dict(frontier_attribution.get("usage_attribution"))
    compiler_summary = as_dict(payloads["wf88_decision_compiler"].get("summary"))
    compiler_leak_guard = as_dict(payloads["wf88_decision_compiler"].get("leak_guard"))
    compiler_runtime = as_dict(payloads["wf88_decision_compiler"].get("runtime_dependency_contract"))
    rsi_outcome_summary = as_dict(payloads["rsi_outcome_scorecard"].get("summary"))
    rsi_outcome_maturity = as_dict(payloads["rsi_outcome_scorecard"].get("maturity_gate"))
    advanced_summary = as_dict(payloads["advanced_capability_pilot_packet"].get("summary"))
    advanced_boundary = as_dict(payloads["advanced_capability_pilot_packet"].get("authority_boundary"))
    learning_eval = payloads["wf74_learning_loop_eval_harness"]
    rsi = as_dict(learning_eval.get("rsi_maturity"))
    eval_surface_contract = as_dict(learning_eval.get("eval_surface_contract"))
    primary_surface = as_dict(eval_surface_contract.get("primary_surface"))
    secondary_surfaces = [as_dict(row) for row in as_list(eval_surface_contract.get("secondary_surfaces"))]
    deprecated_surfaces = [as_dict(row) for row in as_list(eval_surface_contract.get("deprecated_surfaces"))]
    return {
        "wf88_status": payloads["wf88_os2_control"].get("status"),
        "wf88_canonical_action_count": wf88_summary.get("canonical_action_count"),
        "wf88_blocked_or_followup_action_count": wf88_summary.get("blocked_or_followup_action_count"),
        "recommendation_tracked_row_count": wf88_summary.get("recommendation_tracked_row_count") or recommendation_summary.get("preview_row_count"),
        "recommendation_later_outcome_graded_rows": wf88_summary.get("recommendation_later_outcome_graded_rows"),
        "recommendation_later_outcome_metric_scope": wf88_summary.get("recommendation_later_outcome_metric_scope"),
        "recommendation_current_preview_later_outcome_graded_rows": wf88_summary.get("recommendation_current_preview_later_outcome_graded_rows"),
        "recommendation_durable_later_outcome_graded_rows": wf88_summary.get("recommendation_durable_later_outcome_graded_rows"),
        "recommendation_grade_history_graded_ledger_event_count": wf88_summary.get("recommendation_grade_history_graded_ledger_event_count"),
        "scoreable_decision_count": wf88_summary.get("scoreable_decision_count"),
        "model_performance_claim_allowed_now": wf88_summary.get("model_performance_claim_allowed_now"),
        "otel_event_count_24h": otel_summary.get("event_count"),
        "model_learning_rows": as_dict(payloads["model_learning_metadata_ledger"].get("summary")).get("row_count"),
        "wf74_opportunity_count": as_dict(payloads["wf74_improvement_opportunity_queue"].get("summary")).get("opportunity_count"),
        "wf74_reflection_proposal_count": as_dict(payloads["wf74_reflection_to_proposal_autopilot"].get("summary")).get("proposal_count"),
        "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
        "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count"),
        "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
        "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
        "auto_apply_candidate_count": auto_patch_summary.get("auto_apply_candidate_count"),
        "auto_apply_count": auto_patch_summary.get("auto_apply_count"),
        "open_unrouted_recommendation_count": router_summary.get("open_unrouted_recommendation_count"),
        "routed_to_pm_recommendation_count": router_summary.get("routed_to_pm_recommendation_count"),
        "recommendation_to_route_conversion_rate": router_summary.get("recommendation_to_route_conversion_rate"),
        "route_to_pm_job_conversion_rate": router_summary.get("route_to_pm_job_conversion_rate"),
        "loop_trace_status": payloads["wf74_wf88_loop_trace"].get("status"),
        "loop_trace_validation_status": as_dict(payloads["wf74_wf88_loop_trace"].get("validation")).get("status"),
        "loop_trace_row_count": loop_trace_summary.get("trace_row_count"),
        "loop_trace_missing_destination_count": loop_trace_summary.get("missing_destination_count"),
        "loop_trace_high_priority_unrouted_count": loop_trace_summary.get("high_priority_unrouted_count"),
        "loop_trace_pm_job_link_count": loop_trace_summary.get("pm_job_link_count"),
        "loop_trace_lane_link_count": loop_trace_summary.get("lane_link_count"),
        "loop_trace_lane_link_missing_count": loop_trace_summary.get("lane_link_missing_count"),
        "loop_trace_completed_lane_missing_closeout_count": loop_trace_summary.get("completed_lane_missing_closeout_count"),
        "loop_trace_completed_lane_missing_memory_ref_count": loop_trace_summary.get("completed_lane_missing_memory_ref_count"),
        "loop_trace_duplicate_pm_job_id_count": loop_trace_summary.get("duplicate_pm_job_id_count"),
        "loop_trace_downstream_stale_after_router_count": loop_trace_summary.get("downstream_stale_after_router_count"),
        "loop_trace_otel_event_count": loop_trace_source_spine.get("otel_event_count"),
        "loop_trace_model_learning_row_count": loop_trace_source_spine.get("model_learning_row_count"),
        "loop_trace_next_safe_action": loop_trace_summary.get("next_safe_action"),
        "long_work_status": payloads["long_work_job_status"].get("status"),
        "long_work_validation_status": as_dict(payloads["long_work_job_status"].get("validation")).get("status"),
        "long_work_job_count": long_work_summary.get("job_count"),
        "long_work_active_job_count": long_work_summary.get("active_job_count"),
        "long_work_terminal_job_count": long_work_summary.get("terminal_job_count"),
        "long_work_resumable_job_count": long_work_summary.get("resumable_job_count"),
        "long_work_blocked_job_count": long_work_summary.get("blocked_job_count"),
        "long_work_stale_active_job_count": long_work_summary.get("stale_active_job_count"),
        "long_work_status_counts": long_work_summary.get("status_counts"),
        "long_work_resumable_job_ids": long_work_summary.get("resumable_job_ids"),
        "long_work_blocked_job_ids": long_work_summary.get("blocked_job_ids"),
        "long_work_stale_active_job_ids": long_work_summary.get("stale_active_job_ids"),
        "long_work_next_safe_action": long_work_summary.get("next_safe_action"),
        "decision_docket_row_count": docket_summary.get("row_count"),
        "decision_docket_active_action_count": docket_summary.get("active_action_count"),
        "decision_docket_fix_now_count": docket_summary.get("fix_now_count"),
        "decision_docket_owner_decision_count": docket_summary.get("owner_decision_count"),
        "decision_docket_hard_stop_count": docket_summary.get("hard_stop_count"),
        "decision_docket_next_safe_action": docket_summary.get("next_safe_action"),
        "improvement_open_count": improvement_summary.get("latest_open_count"),
        "followup_required_open_count": improvement_summary.get("followup_required_open_count"),
        "pending_skill_proposal_count": improvement_summary.get("pending_skill_proposal_count"),
        "improvement_high_priority_overdue_open_count": improvement_summary.get("high_priority_overdue_open_count"),
        "actionable_queue_status": payloads["actionable_improvement_queue"].get("status"),
        "actionable_queue_validation": as_dict(payloads["actionable_improvement_queue"].get("validation")).get("status"),
        "actionable_open_input_count": actionable_summary.get("open_input_count"),
        "actionable_item_count": actionable_summary.get("action_item_count"),
        "actionable_orphan_count": actionable_summary.get("orphan_count"),
        "actionable_missing_contract_count": actionable_summary.get("missing_contract_count"),
        "actionable_owner_decision_count": actionable_summary.get("owner_decision_count"),
        "actionable_hard_stop_count": actionable_summary.get("hard_stop_count"),
        "actionable_monitor_only_count": actionable_summary.get("monitor_only_count"),
        "actionable_top_action_title": actionable_summary.get("top_action_title"),
        "actionable_top_action_destination": actionable_summary.get("top_action_destination"),
        "actionable_top_next_action": actionable_summary.get("top_next_action"),
        "no_orphan_status": payloads["no_orphan_validator"].get("status"),
        "no_orphan_validation": as_dict(payloads["no_orphan_validator"].get("validation")).get("status"),
        "no_orphan_validation_passed": no_orphan_summary.get("validation_passed"),
        "rsi_status": rsi.get("status") or rsi.get("maturity_stage"),
        "rsi_maturity_stage": rsi.get("maturity_stage"),
        "rsi_rubric_dimension_count": len(as_list(rsi.get("rubric_dimensions"))),
        "wf74_eval_primary_surface": primary_surface.get("artifact"),
        "wf74_eval_primary_surface_class": primary_surface.get("surface_class"),
        "wf74_eval_primary_first_hop_truth": primary_surface.get("first_hop_truth"),
        "wf74_eval_secondary_surface_count": len(secondary_surfaces),
        "wf74_eval_deprecated_surface_count": len(deprecated_surfaces),
        "wf74_legacy_rsi_first_hop_truth": any(
            row.get("artifact") == "tmp/wf74-rsi-evaluation-harness.json" and row.get("first_hop_truth")
            for row in deprecated_surfaces
        ),
        "wf74_learning_eval_case_count": eval_summary.get("case_count"),
        "wf74_learning_eval_passed_count": eval_summary.get("passed_count"),
        "wf74_learning_eval_failed_count": eval_summary.get("failed_count"),
        "outcome_eval_categories": first_present(outcome_eval_summary.get("categories"), payloads["wf74_outcome_eval_suite_v2"].get("categories")),
        "outcome_eval_fixtures": first_present(outcome_eval_summary.get("fixtures"), payloads["wf74_outcome_eval_suite_v2"].get("fixtures")),
        "outcome_eval_failed_classifications": first_present(outcome_eval_summary.get("failed_classifications"), payloads["wf74_outcome_eval_suite_v2"].get("failed_classifications")),
        "model_quality_status": payloads["model_quality_scorecard"].get("status"),
        "model_quality_findings": model_quality_summary.get("findings"),
        "token_usage_status": payloads["token_usage_ledger"].get("status"),
        "token_budget_status": payloads["token_budget_status"].get("status"),
        "token_efficiency_status": payloads["token_efficiency_scorecard"].get("status"),
        "token_efficiency_validation_status": as_dict(payloads["token_efficiency_scorecard"].get("validation")).get("status"),
        "implementation_token_bridge_status": payloads["implementation_token_attribution_bridge"].get("status"),
        "implementation_token_bridge_validation_status": as_dict(payloads["implementation_token_attribution_bridge"].get("validation")).get("status"),
        "token_event_count": token_summary.get("token_event_count") or token_budget_summary.get("token_event_count") or token_efficiency_summary.get("token_event_count"),
        "total_tokens_observed": token_summary.get("total_tokens") or token_budget_summary.get("total_tokens") or token_efficiency_summary.get("total_tokens"),
        "api_equivalent_token_cost_usd": first_present(
            token_summary.get("api_equivalent_cost_usd"),
            token_budget_summary.get("api_equivalent_cost_usd"),
            token_efficiency_summary.get("api_equivalent_cost_usd"),
            token_summary.get("estimated_cost_total"),
            token_budget_summary.get("estimated_cost_total"),
            token_efficiency_summary.get("estimated_cost_total"),
        ),
        "api_equivalent_estimate_status": first_present(
            token_summary.get("api_equivalent_estimate_status"),
            token_budget_summary.get("api_equivalent_estimate_status"),
            token_efficiency_summary.get("api_equivalent_estimate_status"),
        ),
        "api_equivalent_cost_rows": first_present(
            token_summary.get("api_equivalent_cost_rows"),
            token_budget_summary.get("api_equivalent_cost_rows"),
            token_efficiency_summary.get("api_equivalent_cost_rows"),
        ),
        "api_equivalent_cost_event_coverage_percent": first_present(
            token_summary.get("api_equivalent_cost_event_coverage_percent"),
            token_budget_summary.get("api_equivalent_cost_event_coverage_percent"),
            token_efficiency_summary.get("api_equivalent_cost_event_coverage_percent"),
        ),
        "estimated_token_cost_total": first_present(
            token_summary.get("api_equivalent_cost_usd"),
            token_budget_summary.get("api_equivalent_cost_usd"),
            token_efficiency_summary.get("api_equivalent_cost_usd"),
            token_summary.get("estimated_cost_total"),
            token_budget_summary.get("estimated_cost_total"),
            token_efficiency_summary.get("estimated_cost_total"),
        ),
        "estimated_token_cost_total_deprecated_alias_for": "api_equivalent_token_cost_usd",
        "estimated_chatgpt_credits": first_present(
            token_summary.get("estimated_chatgpt_credits"),
            token_budget_summary.get("estimated_chatgpt_credits"),
            token_efficiency_summary.get("estimated_chatgpt_credits"),
        ),
        "chatgpt_credit_estimate_status": first_present(
            token_summary.get("chatgpt_credit_estimate_status"),
            token_budget_summary.get("chatgpt_credit_estimate_status"),
            token_efficiency_summary.get("chatgpt_credit_estimate_status"),
        ),
        "estimated_chatgpt_credit_rows": first_present(
            token_summary.get("estimated_chatgpt_credit_rows"),
            token_budget_summary.get("estimated_chatgpt_credit_rows"),
            token_efficiency_summary.get("estimated_chatgpt_credit_rows"),
        ),
        "chatgpt_credit_event_coverage_percent": first_present(
            token_summary.get("chatgpt_credit_event_coverage_percent"),
            token_budget_summary.get("chatgpt_credit_event_coverage_percent"),
            token_efficiency_summary.get("chatgpt_credit_event_coverage_percent"),
        ),
        "unknown_or_invalid_input_token_semantics_event_count": first_present(
            token_summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            token_budget_summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            token_efficiency_summary.get("unknown_or_invalid_input_token_semantics_event_count"),
        ),
        "rolling_5h_total_tokens": as_dict(token_usage_pace.get("rolling_5h")).get("total_tokens"),
        "rolling_7d_observed_total_tokens": as_dict(token_usage_pace.get("rolling_7d_observed")).get("total_tokens"),
        "usage_timestamp_coverage_percent": token_usage_pace.get("usage_timestamp_coverage_percent"),
        "actual_billed_cost_usd": first_present(
            token_summary.get("actual_billed_cost_usd"),
            token_budget_summary.get("actual_billed_cost_usd"),
            token_efficiency_summary.get("actual_billed_cost_usd"),
        ),
        "token_api_equivalent_is_not_invoice": token_billing_semantics.get("api_equivalent_is_not_invoice"),
        "token_credit_estimate_is_not_observed_debit": token_billing_semantics.get("credit_estimate_is_not_observed_debit"),
        "oauth_quota_state": token_oauth_capacity.get("state") or token_oauth_capacity.get("status"),
        "oauth_remaining_percent": token_oauth_capacity.get("remaining_percent"),
        "oauth_days_to_reset": token_oauth_capacity.get("days_to_reset"),
        "oauth_automatic_action_allowed": token_oauth_capacity.get("automatic_action_allowed"),
        "cron_token_event_count": token_summary.get("cron_token_event_count") or token_budget_summary.get("cron_token_event_count") or token_efficiency_summary.get("cron_token_event_count"),
        "implementation_token_event_count": token_bridge_summary.get("implementation_token_event_count") or token_summary.get("implementation_token_event_count"),
        "implementation_token_gap_count": token_bridge_summary.get("implementation_token_gap_count") or token_summary.get("implementation_token_gap_count"),
        "implementation_token_unclassified_supported_runtime_gap_count": token_bridge_summary.get("unclassified_supported_runtime_gap_count"),
        "implementation_token_closeout_enforcement_required": token_bridge_summary.get("closeout_enforcement_required"),
        "token_api_call_reduction_candidate_count": token_efficiency_summary.get("api_call_reduction_candidate_count"),
        "token_prompt_compression_candidate_count": token_efficiency_summary.get("prompt_compression_candidate_count"),
        "token_failure_cost_candidate_count": token_efficiency_summary.get("failure_cost_candidate_count"),
        "token_top_candidate": token_efficiency_summary.get("top_candidate"),
        "implementation_token_provider_run_join_ready": token_bridge_summary.get("provider_run_join_ready"),
        "coding_outcome_status": payloads["coding_outcome_ledger"].get("status"),
        "coding_outcome_validation_status": as_dict(payloads["coding_outcome_ledger"].get("validation")).get("status"),
        "coding_outcome_route_conformant_count": coding_outcome_summary.get("route_conformant_count"),
        "coding_outcome_route_mismatch_count": coding_outcome_summary.get("route_mismatch_count"),
        "coding_outcome_incident_row_count": coding_outcome_summary.get("incident_row_count"),
        "coding_outcome_invalid_token_integrity_row_count": coding_outcome_summary.get("invalid_token_integrity_row_count"),
        "coding_outcome_total_retry_count": coding_outcome_summary.get("total_retry_count"),
        "coding_outcome_comparable_cohort_count": len(as_dict(coding_outcome_summary.get("comparable_cohorts"))),
        "coding_outcome_required_accepted_count": coding_outcome_gate.get("required_accepted_count"),
        "coding_outcome_eligible_cohort_count": coding_outcome_gate.get("eligible_cohort_count"),
        "coding_outcome_route_ranking_or_promotion_before_gate": coding_outcome_gate.get("route_ranking_or_promotion_before_gate"),
        "retrieval_quality_status": payloads["retrieval_quality_scorecard"].get("status"),
        "retrieval_quality_validation_status": as_dict(payloads["retrieval_quality_scorecard"].get("validation")).get("status"),
        "retrieval_fixture_count": retrieval_summary.get("fixtures"),
        "retrieval_passed_count": retrieval_summary.get("passed"),
        "retrieval_failed_count": retrieval_summary.get("failed"),
        "retrieval_average_score": retrieval_summary.get("average_score"),
        "retrieval_class_count": len(as_list(retrieval_summary.get("classes"))),
        "retrieval_conflict_fixture_count": retrieval_summary.get("conflict_fixture_count"),
        "retrieval_freshness_assessment_mode_counts": retrieval_freshness.get("assessment_mode_counts"),
        "retrieval_live_source_timestamp_age_assessment_count": retrieval_freshness.get("live_source_timestamp_age_assessment_count"),
        "retrieval_live_source_status_counts": retrieval_freshness.get("live_source_status_counts"),
        "retrieval_label_only_cases_are_live_source_proof": retrieval_freshness_contract.get("label_only_cases_are_live_source_proof"),
        "retrieval_declared_labels_are_authoritative": retrieval_freshness_contract.get("declared_labels_are_authoritative"),
        "retrieval_source_timestamp_age_is_live_source_proof": retrieval_freshness_contract.get("source_timestamp_age_is_live_source_proof"),
        "frontier_eval_status": payloads["frontier_capability_eval_spine"].get("status"),
        "frontier_eval_validation_status": as_dict(payloads["frontier_capability_eval_spine"].get("validation")).get("status"),
        "frontier_fixture_count": frontier_fixture.get("case_count"),
        "frontier_assignment_count": frontier_design.get("assignment_count"),
        "frontier_result_row_count": frontier_results.get("row_count"),
        "frontier_fully_verified_result_count": (
            min(
                int(frontier_attestation.get(key) or 0)
                for key in (
                    "cryptographically_verified_execution_count",
                    "cryptographically_verified_output_artifact_count",
                    "cryptographically_verified_independent_grader_count",
                )
            )
            if frontier_attestation
            else frontier_legacy_proof.get("fully_verified_result_count")
        ),
        "frontier_model_execution_state": first_present(
            frontier_attestation.get("verification_state"),
            frontier_legacy_proof.get("model_execution_state"),
            frontier_design.get("model_execution_state"),
        ),
        "frontier_all_assignment_execution_proven": first_present(
            frontier_attestation.get("all_assignment_execution_independently_attested"),
            frontier_legacy_proof.get("all_assignment_execution_proven"),
        ),
        "frontier_proof_index_chain_verified": first_present(
            frontier_local_integrity.get("local_index_integrity_valid"),
            frontier_legacy_proof.get("proof_index_chain_verified"),
        ),
        "frontier_all_comparison_gates_passed": frontier_comparison.get("all_comparison_gates_passed"),
        "frontier_trusted_execution_attestation_verified": frontier_comparison.get("trusted_execution_attestation_verified"),
        "frontier_trusted_output_artifact_attestation_verified": frontier_comparison.get("trusted_output_artifact_attestation_verified"),
        "frontier_trusted_grader_attestation_verified": frontier_comparison.get("trusted_grader_attestation_verified"),
        "frontier_cross_model_ranking_allowed": frontier_comparison.get("cross_model_ranking_allowed"),
        "frontier_promotion_action_allowed": frontier_comparison.get("promotion_action_allowed"),
        "frontier_recent_model_attribution_coverage": frontier_recent_attribution.get("coverage"),
        "frontier_provider_run_join_ready": frontier_usage_attribution.get("provider_run_join_ready"),
        "decision_compiler_status": payloads["wf88_decision_compiler"].get("status"),
        "decision_compiler_validation_status": as_dict(payloads["wf88_decision_compiler"].get("validation")).get("status"),
        "decision_object_count": compiler_summary.get("decision_object_count"),
        "decision_state_counts": compiler_summary.get("state_counts"),
        "decision_conflict_count": compiler_summary.get("conflict_count"),
        "decision_uncertain_count": compiler_summary.get("uncertain_count"),
        "decision_owner_review_required_count": compiler_summary.get("owner_review_required_count"),
        "decision_blocked_count": compiler_summary.get("blocked_count"),
        "decision_compiler_leak_guard_pass": compiler_leak_guard.get("pass"),
        "decision_compiler_runtime_cycle_forbidden": compiler_runtime.get("wiki_or_os2_inputs_forbidden"),
        "rsi_outcome_status": payloads["rsi_outcome_scorecard"].get("status"),
        "rsi_outcome_validation_status": as_dict(payloads["rsi_outcome_scorecard"].get("validation")).get("status"),
        "rsi_outcome_maturity_status": rsi_outcome_summary.get("maturity_status"),
        "rsi_outcome_mature": rsi_outcome_maturity.get("mature"),
        "rsi_live_trace_row_count": rsi_outcome_summary.get("live_trace_row_count"),
        "rsi_live_trace_raw_row_count": rsi_outcome_summary.get("live_trace_raw_row_count"),
        "rsi_live_trace_unique_correlation_id_count": rsi_outcome_summary.get("live_trace_unique_correlation_id_count"),
        "rsi_live_trace_duplicate_correlation_id_count": rsi_outcome_summary.get("live_trace_duplicate_correlation_id_count"),
        "rsi_live_trace_missing_correlation_id_count": rsi_outcome_summary.get("live_trace_missing_correlation_id_count"),
        "rsi_live_trace_noncanonical_correlation_id_count": rsi_outcome_summary.get("live_trace_noncanonical_correlation_id_count"),
        "rsi_correlation_integrity_gate_met": rsi_outcome_maturity.get("correlation_integrity_gate_met"),
        "rsi_live_complete_stable_count": rsi_outcome_summary.get("live_complete_stable_count"),
        "rsi_live_closed_unverified_durability_count": rsi_outcome_summary.get("live_closed_unverified_durability_count"),
        "rsi_missing_link_debt_item_count": rsi_outcome_summary.get("missing_link_debt_item_count"),
        "rsi_live_authority_violation_count": rsi_outcome_summary.get("live_authority_violation_count"),
        "advanced_pilot_status": payloads["advanced_capability_pilot_packet"].get("status"),
        "advanced_pilot_validation_status": as_dict(payloads["advanced_capability_pilot_packet"].get("validation")).get("status"),
        "advanced_pilot_count": advanced_summary.get("pilot_count"),
        "advanced_pilot_executed_count": advanced_summary.get("executed_pilot_count"),
        "advanced_pilot_promotion_ready_count": advanced_summary.get("promotion_ready_count"),
        "advanced_pilot_external_api_calls_performed": advanced_summary.get("external_api_calls_performed"),
        "advanced_pilot_raw_content_stored": advanced_summary.get("raw_content_stored"),
        "advanced_pilot_fixture_contract_safe": (
            payloads["advanced_capability_pilot_packet"].get("status") == "fixture_ready_no_execution_authority"
            and as_dict(payloads["advanced_capability_pilot_packet"].get("validation")).get("status") == "ok"
            and int(advanced_summary.get("executed_pilot_count") or 0) == 0
            and int(advanced_summary.get("promotion_ready_count") or 0) == 0
            and advanced_summary.get("external_api_calls_performed") is False
            and advanced_summary.get("raw_content_stored") is False
            and advanced_boundary.get("raw_prompt_capture") is False
            and advanced_boundary.get("raw_response_capture") is False
            and advanced_boundary.get("runtime_or_config_mutation") is False
            and advanced_boundary.get("model_route_mutation") is False
        ),
        "wiki_page_count": len(EXPECTED_WIKI_PAGES),
        "self_prompt_count": len(SELF_PROMPTS),
    }


def _blocked_component_status(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return not normalized or normalized == "error" or "blocked" in normalized


def _warning_component_status(value: Any) -> bool:
    return "warning" in str(value or "").strip().lower()


def _retrieval_action_state(summary: dict[str, Any]) -> str:
    if summary.get("retrieval_quality_status") != "ok" or summary.get("retrieval_quality_validation_status") != "ok":
        return "blocked"
    ready = (
        int(summary.get("retrieval_fixture_count") or 0) >= 30
        and int(summary.get("retrieval_failed_count") or 0) == 0
        and int(summary.get("retrieval_passed_count") or 0) == int(summary.get("retrieval_fixture_count") or 0)
        and int(summary.get("retrieval_live_source_timestamp_age_assessment_count") or 0) >= 1
        and summary.get("retrieval_label_only_cases_are_live_source_proof") is False
        and summary.get("retrieval_declared_labels_are_authoritative") is False
        and summary.get("retrieval_source_timestamp_age_is_live_source_proof") is True
    )
    return "clean" if ready else "repair_required"


def _frontier_action_state(summary: dict[str, Any]) -> str:
    if summary.get("frontier_eval_validation_status") != "ok" or _blocked_component_status(summary.get("frontier_eval_status")):
        return "blocked"
    ready = (
        int(summary.get("frontier_result_row_count") or 0) > 0
        and not _warning_component_status(summary.get("frontier_eval_status"))
        and summary.get("frontier_all_assignment_execution_proven") is True
        and summary.get("frontier_proof_index_chain_verified") is True
        and summary.get("frontier_all_comparison_gates_passed") is True
        and summary.get("frontier_trusted_execution_attestation_verified") is True
        and summary.get("frontier_trusted_output_artifact_attestation_verified") is True
        and summary.get("frontier_trusted_grader_attestation_verified") is True
        and summary.get("frontier_cross_model_ranking_allowed") is True
    )
    return "comparison_ready_review_only" if ready else "evidence_collection_required"


def _compiler_action_state(summary: dict[str, Any]) -> str:
    validation_status = summary.get("decision_compiler_validation_status")
    source_status = summary.get("decision_compiler_status")
    if validation_status in {None, "blocked", "error"} or _blocked_component_status(source_status):
        return "blocked"
    if validation_status == "warning" or _warning_component_status(source_status):
        return "warning_review_only"
    ready = (
        validation_status == "ok"
        and summary.get("decision_compiler_leak_guard_pass") is True
        and int(summary.get("decision_object_count") or 0) > 0
        and int(summary.get("decision_blocked_count") or 0) == 0
        and int(summary.get("decision_conflict_count") or 0) == 0
    )
    return "review_ready" if ready else "repair_required"


def _rsi_action_state(summary: dict[str, Any]) -> str:
    integrity_blocked = (
        summary.get("rsi_outcome_validation_status") in {None, "blocked", "error"}
        or _blocked_component_status(summary.get("rsi_outcome_status"))
        or int(summary.get("rsi_live_authority_violation_count") or 0) > 0
        or int(summary.get("rsi_live_trace_duplicate_correlation_id_count") or 0) > 0
        or int(summary.get("rsi_live_trace_missing_correlation_id_count") or 0) > 0
        or int(summary.get("rsi_live_trace_noncanonical_correlation_id_count") or 0) > 0
        or summary.get("rsi_correlation_integrity_gate_met") is not True
    )
    if integrity_blocked:
        return "blocked"
    mature = (
        summary.get("rsi_outcome_validation_status") == "ok"
        and not _warning_component_status(summary.get("rsi_outcome_status"))
        and summary.get("rsi_outcome_mature") is True
        and int(summary.get("rsi_live_complete_stable_count") or 0) > 0
        and int(summary.get("rsi_missing_link_debt_item_count") or 0) == 0
    )
    return "mature_review_only" if mature else "evidence_linkage_required"


def _advanced_pilot_action_state(summary: dict[str, Any]) -> str:
    if summary.get("advanced_pilot_fixture_contract_safe") is not True:
        return "blocked"
    return "fixture_ready_execution_gated"


def _token_cron_optimization_action_state(summary: dict[str, Any]) -> str:
    """Keep token optimization review-only and fail closed on blocked inputs.

    A warning scorecard may still identify a review-only candidate, but a
    blocked/error/missing scorecard or attribution bridge is not adequate
    evidence to call that candidate review-ready.
    """
    evidence_blocked = any(
        (
            _blocked_component_status(summary.get("token_efficiency_status")),
            _blocked_component_status(summary.get("token_efficiency_validation_status")),
            _blocked_component_status(summary.get("implementation_token_bridge_status")),
            _blocked_component_status(summary.get("implementation_token_bridge_validation_status")),
            int(summary.get("implementation_token_unclassified_supported_runtime_gap_count") or 0) > 0,
            summary.get("implementation_token_closeout_enforcement_required") is True,
        )
    )
    if evidence_blocked:
        return "repair_required"
    return "review_ready" if int(summary.get("token_api_call_reduction_candidate_count") or 0) else "monitor"


def action_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "refresh-wf88-wiki-synthesis",
            "state": "active",
            "owner_workflow": "WF88",
            "next_action": "Run the wiki synthesis packet after WF88/WF74/PM/OTEL producers refresh or after material implementation closeout.",
            "command": "python scripts\\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate",
            "stop_line": "Review-only wiki synthesis; no canon, approval, execution, or cron mutation.",
        },
        {
            "id": "grade-recommendation-outcomes",
            "state": "followup_required"
            if int(summary.get("recommendation_current_preview_later_outcome_graded_rows") or 0) == 0
            else "monitor",
            "owner_workflow": "WF88",
            "next_action": "Grade mature outcomes represented in the current recommendation preview before making decision-quality claims; historical grades do not satisfy current-preview evidence.",
            "command": "python scripts\\finance_decision_performance_digest.py --write --write-md --validate",
            "stop_line": "No predictive/model-performance claim until source packets explicitly allow it.",
        },
        {
            "id": "mature-rsi-eval-harness",
            "state": (
                "pilot_not_mature"
                if summary.get("rsi_status") == "pilot_ready"
                else "proof_worker_ready"
                if summary.get("rsi_status") == "proof_worker_ready"
                else "monitor"
            ),
            "owner_workflow": "WF74",
            "next_action": "Keep RSI guarded; supervised proof refresh may run, while cron proof execution still requires explicit graduation proof.",
            "command": "python scripts\\wf74_learning_loop_eval_harness.py --write --validate",
            "compatibility_command": "python scripts\\wf74_rsi.py --validate-only",
            "stop_line": "No base-model self-modification, autonomous doctrine change, or raw prompt/tool capture.",
        },
        {
            "id": "route-open-improvement-followups",
            "state": "followup_required" if int(summary.get("followup_required_open_count") or 0) else "monitor",
            "owner_workflow": "WF74",
            "next_action": "Route open follow-up debt through WF74 docket, PM jobs, owner packets, or monitor-only rows; do not leave it as chat residue.",
            "command": "python scripts\\improvement_ledger.py --write --write-md --validate",
            "stop_line": "Generated recommendations do not apply patches, skills, cron, config, or finance state by themselves.",
        },
        {
            "id": "enforce-no-orphan-improvement-actions",
            "state": (
                "blocked"
                if summary.get("no_orphan_validation") == "blocked"
                else "warning" if summary.get("no_orphan_validation") == "warning" else "clean"
            ),
            "owner_workflow": "WF88",
            "next_action": "Refresh the actionable improvement queue and no-orphan validator so every open improvement has a durable destination and next action.",
            "command": "python scripts\\actionable_improvement_queue.py --write --write-md --validate",
            "validator_command": "python scripts\\no_orphan_validator.py --write --validate",
            "stop_line": "Queue/validator surfaces prove routing only; they do not approve apply, execution, cron mutation, or owner decisions.",
        },
        {
            "id": "maintain-wf74-wf88-loop-trace",
            "state": (
                "blocked"
                if int(summary.get("loop_trace_high_priority_unrouted_count") or 0)
                or int(summary.get("loop_trace_duplicate_pm_job_id_count") or 0)
                else "warning"
                if int(summary.get("loop_trace_downstream_stale_after_router_count") or 0)
                or int(summary.get("loop_trace_lane_link_missing_count") or 0)
                else "clean"
            ),
            "owner_workflow": "WF74-WF88",
            "next_action": "Use the stitched loop trace to verify each current opportunity has a durable destination, PM/lane link when applicable, and WF88 consumer refresh.",
            "command": "python scripts\\wf74_wf88_loop_trace_packet.py --write --write-md --validate",
            "stop_line": "Trace-only; no apply, execution, cron mutation, runtime mutation, or owner approval inference.",
        },
        {
            "id": "maintain-long-work-job-status",
            "state": (
                "blocked"
                if int(summary.get("long_work_blocked_job_count") or 0)
                or summary.get("long_work_validation_status") == "blocked"
                else "resume_ready"
                if int(summary.get("long_work_resumable_job_count") or 0)
                else "warning"
                if int(summary.get("long_work_stale_active_job_count") or 0)
                or int(summary.get("long_work_active_job_count") or 0)
                or summary.get("long_work_validation_status") == "warning"
                else "clean"
            ),
            "owner_workflow": "RUNTIME",
            "next_action": "Use the long-work status packet to resume provider-backed or full-source local jobs in bounded slices before rerunning expensive foreground commands.",
            "command": "python scripts\\long_work_job_status_packet.py --write --write-md --validate",
            "stop_line": "Status/resume only; no cron schedule mutation, runtime/config mutation, finance/canon mutation, paper/live execution, external delivery, delete/archive, or approval inference.",
        },
        {
            "id": "optimize-token-heavy-cron-api-calls",
            "state": _token_cron_optimization_action_state(summary),
            "owner_workflow": "WF88",
            "next_action": "Use the token efficiency scorecard to pick changed-only prefilter or prompt-compression candidates before modifying any cron command.",
            "command": "python scripts\\token_efficiency_scorecard.py --write --write-md --validate",
            "stop_line": "Scorecard recommends only; no cron schedule, runtime config, model routing, or API-call behavior changes without a separate validated patch.",
        },
        {
            "id": "close-implementation-token-attribution-gap",
            "state": "repair_required" if int(summary.get("implementation_token_gap_count") or 0) else "monitor",
            "owner_workflow": "WF88",
            "next_action": "Use concurrent_lane_manager closeout token fields plus the implementation token attribution bridge when provider usage is exposed.",
            "command": "python scripts\\implementation_token_attribution_bridge.py --write --write-md --validate",
            "stop_line": "Metadata-only stamping; no raw prompt, response, tool payload, secret, header, or model-training capture.",
        },
        {
            "id": "maintain-wf88-retrieval-regression-corpus",
            "state": _retrieval_action_state(summary),
            "owner_workflow": "WF88",
            "next_action": "Keep the retrieval corpus current as source ownership changes; preserve SQL/thin-Markdown authority, derive eligible freshness from timestamps/age, and keep label-only scenarios outside live-source proof.",
            "command": "python scripts\\retrieval_quality_scorecard.py --write --write-md --validate",
            "stop_line": "Retrieval scoring routes to exact sources; it does not create canon, vector/KG authority, or a production answer path.",
        },
        {
            "id": "collect-frontier-capability-eval-results",
            "state": _frontier_action_state(summary),
            "owner_workflow": "WF88",
            "next_action": "Collect source-identical, metadata-only matched results through the blinded scorer surface; do not rank from the empty scaffold.",
            "command": "python scripts\\frontier_capability_eval_spine.py --write --write-md --validate",
            "stop_line": "No raw content capture, route/runtime/config mutation, model promotion, or ranking until every analytical gate passes; promotion remains owner-gated.",
        },
        {
            "id": "compile-wf88-decision-objects",
            "state": _compiler_action_state(summary),
            "owner_workflow": "WF88",
            "next_action": "Use the deterministic compiler as the decision-object first hop, then let wiki synthesis render those objects without feeding wiki/OS2 back into the compiler.",
            "command": "python scripts\\wf88_decision_compiler.py --write --write-md --validate",
            "stop_line": "Decision objects are review-only routing surfaces; no apply, execution, canon, finance, cron, runtime, model-route, or owner-approval authority.",
        },
        {
            "id": "close-rsi-outcome-linkage-debt",
            "state": _rsi_action_state(summary),
            "owner_workflow": "WF74-WF88",
            "next_action": "Add exact RSI correlation IDs and recurrence, stayed-closed, SLA, token/cost, and later-grade observations at owner sources.",
            "command": "python scripts\\rsi_outcome_scorecard.py --write --write-md --validate",
            "stop_line": "Fixtures and broad ledgers do not prove RSI causality, frontier reasoning, AGI/ASI, predictive skill, model ranking, or autonomous apply readiness.",
        },
        {
            "id": "run-isolated-advanced-capability-pilots",
            "state": _advanced_pilot_action_state(summary),
            "owner_workflow": "WF88",
            "next_action": "Keep the six capability contracts fixture-only until a separately scoped isolated runner has cost limits, matched baselines, privacy-safe attribution, and stop-line proof.",
            "command": "python scripts\\advanced_capability_pilot_packet.py --write --write-md --validate",
            "stop_line": "No API execution, raw prompt/response/reasoning/tool storage, route/runtime/config mutation, or capability promotion from this fixture packet.",
        },
        {
            "id": "preserve-zero-auto-apply",
            "state": "blocked" if int(summary.get("auto_apply_count") or 0) else "clean",
            "owner_workflow": "WF74",
            "next_action": "Treat any nonzero auto_apply_count as a hard blocker before startup/status surfaces can call the loop healthy.",
            "command": "python scripts\\wf74_auto_patch_proposer.py --write --write-md --validate",
            "stop_line": "Auto-apply remains disabled unless a future exact gate is approved.",
        },
    ]


def routing_contract() -> list[dict[str, str]]:
    return [
        {
            "from": "OTEL operational signals",
            "to": "model-learning metadata ledger",
            "purpose": "Convert runtime evidence into metadata-safe learning inputs.",
        },
        {
            "from": "model-learning metadata ledger",
            "to": "WF74 improvement opportunity queue",
            "purpose": "Classify repeated friction, warnings, and failures into durable opportunities.",
        },
        {
            "from": "WF74 opportunity queue",
            "to": "reflection-to-proposal autopilot and auto-patch proposer",
            "purpose": "Turn findings into bounded proposals while preserving auto-apply equals zero.",
        },
        {
            "from": "WF74 router and PM packet",
            "to": "WF74 -> WF88 loop trace",
            "purpose": "Stitch each opportunity to router, docket, PM job, lane, closeout proof, memory refs, and consumer freshness.",
        },
        {
            "from": "WF74 -> WF88 loop trace",
            "to": "WF88 OS 2.0 control packet",
            "purpose": "Surface stitched action state, missing links, owner gates, scorecards, and route outcomes in one control layer.",
        },
        {
            "from": "Long-work job status packet",
            "to": "WF88 OS 2.0 control packet and wiki synthesis",
            "purpose": "Keep long provider-backed or full-source local jobs resumable through bounded slices instead of one blocking foreground tool call.",
        },
        {
            "from": "WF88 OS 2.0 control packet",
            "to": "WF88 wiki synthesis",
            "purpose": "Create durable human-readable maps and startup-visible recommendations without becoming canon.",
        },
        {
            "from": "Improvement Ledger",
            "to": "actionable improvement queue and no-orphan validator",
            "purpose": "Force open improvement debt into a durable destination with a next action, proof, and review rule.",
        },
        {
            "from": "Token usage ledger",
            "to": "token efficiency scorecard and implementation attribution bridge",
            "purpose": "Convert metadata-only token events into API-call reduction candidates and implementation usage attribution repairs.",
        },
        {
            "from": "WF88 wiki synthesis",
            "to": "Startup/status/future-session packets and workflow router",
            "purpose": "Make new sessions open the map, see action rows, and route recommendations to PM/WF74 instead of losing them.",
        },
    ]


def claim_card_lines(packet: dict[str, Any], page_path: str) -> str:
    cards = [
        as_dict(claim)
        for claim in as_list(as_dict(packet.get("claim_index")).get("claims"))
        if page_path in as_list(as_dict(claim).get("page_paths"))
    ]
    if not cards:
        return "- No decision-bearing claim cards are rendered on this page."
    lines = []
    for claim in cards:
        refs = ", ".join(
            f"`{as_dict(ref).get('source_key')}#{as_dict(ref).get('json_pointer')}`"
            for ref in as_list(claim.get("source_refs"))
        )
        lines.append(
            f"- `{claim.get('claim_id')}`: `{_stable_json(claim.get('normalized_value'))}`; "
            f"authority `{claim.get('authority')}`; source refs {refs}."
        )
    return "\n".join(lines)


def refresh_delta_lines(packet: dict[str, Any]) -> str:
    delta = as_dict(packet.get("refresh_delta"))
    if delta.get("status") != "available":
        return "\n".join([
            "- Baseline: unavailable.",
            f"- Reason: `{delta.get('reason')}`.",
            "- This is a first or incompatible claim-catalog baseline; no change is inferred.",
        ])
    rows = [
        f"- Baseline generated: `{delta.get('baseline_generated_at_utc')}`.",
        f"- Added claim IDs: `{', '.join(as_list(delta.get('added_claim_ids'))) or 'none'}`.",
        f"- Removed claim IDs: `{', '.join(as_list(delta.get('removed_claim_ids'))) or 'none'}`.",
        f"- Changed claim IDs: `{', '.join(as_list(delta.get('changed_claim_ids'))) or 'none'}`.",
        f"- Source-reference changes: `{', '.join(as_list(delta.get('source_ref_changed_claim_ids'))) or 'none'}`.",
    ]
    return "\n".join(rows)


def review_event_ref_lines(packet: dict[str, Any]) -> str:
    intake = as_dict(packet.get("review_event_intake"))
    if not intake.get("present"):
        return "- Optional upstream review-event intake is not present."
    rows = [
        f"- Intake status: `{intake.get('status')}`; valid reference count `{intake.get('event_count')}`.",
    ]
    for event in as_list(intake.get("events")):
        row = as_dict(event)
        followup = as_dict(row.get("followup_ref"))
        followup_source = as_dict(followup.get("source_ref"))
        route = (
            f"; follow-up `{followup.get('route')}:{followup_source.get('source_key')}#{followup_source.get('json_pointer')}`"
            if followup else ""
        )
        rows.append(
            f"- `{row.get('event_id')}` -> `{row.get('claim_id')}`: `{row.get('disposition')}` / "
            f"`{row.get('reason_code')}`{route}."
        )
    if as_list(intake.get("errors")):
        rows.append("- Intake is invalid and validation is blocked; untrusted event data is not rendered.")
    return "\n".join(rows)


def page_header(title: str, sources: list[str], page_path: str) -> str:
    page_type = WIKI_PAGE_TYPES.get(page_path)
    if page_type not in VALID_PAGE_TYPES:
        raise ValueError(f"unknown_wiki_page_type:{page_path}:{page_type}")
    source_lines = "\n".join(f"- `{source}`" for source in sources)
    return "\n".join([
        f"# {title}",
        "",
        "Status: synthesis only",
        "Owner workflow: WF88",
        f"Generated page type: {page_type}",
        "Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.",
        "Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.",
        "",
        "## Source artifacts",
        "",
        source_lines,
        "",
    ])


def wiki_pages(packet: dict[str, Any]) -> dict[str, str]:
    summary = as_dict(packet.get("summary"))
    efficiency_policy = as_dict(packet.get("execution_efficiency_policy"))
    policy_schema = efficiency_policy.get("schema")
    actions = as_list(packet.get("action_items"))
    prompt_lines = "\n".join(f"- {prompt}" for prompt in as_list(packet.get("self_prompting_contract")))
    action_lines = "\n".join(
        f"- `{as_dict(row).get('id')}`: `{as_dict(row).get('state')}` - {as_dict(row).get('next_action')}"
        for row in actions
    )
    route_lines = "\n".join(
        f"- {as_dict(row).get('from')} -> {as_dict(row).get('to')}: {as_dict(row).get('purpose')}"
        for row in as_list(packet.get("routing_contract"))
    )
    scorecard_lines = "\n".join([
        f"- WF74 learning eval: `{summary.get('wf74_learning_eval_passed_count')}/{summary.get('wf74_learning_eval_case_count')}` passed; failed `{summary.get('wf74_learning_eval_failed_count')}`.",
        f"- WF74 outcome eval suite: categories `{summary.get('outcome_eval_categories')}`, fixtures `{summary.get('outcome_eval_fixtures')}`, failed classifications `{summary.get('outcome_eval_failed_classifications')}`.",
        f"- Model quality scorecard status: `{summary.get('model_quality_status')}`.",
        f"- Retrieval regression corpus: `{summary.get('retrieval_passed_count')}/{summary.get('retrieval_fixture_count')}` passed across `{summary.get('retrieval_class_count')}` classes; average `{summary.get('retrieval_average_score')}`; live timestamp-age proofs `{summary.get('retrieval_live_source_timestamp_age_assessment_count')}`.",
        f"- Frontier eval: `{summary.get('frontier_eval_status')}` with `{summary.get('frontier_fixture_count')}` frozen cases, `{summary.get('frontier_result_row_count')}` results, `{summary.get('frontier_fully_verified_result_count')}` fully proof-verified, execution `{summary.get('frontier_model_execution_state')}`, ranking `{summary.get('frontier_cross_model_ranking_allowed')}`.",
        f"- Decision compiler: `{summary.get('decision_object_count')}` objects; conflicts `{summary.get('decision_conflict_count')}`; leak guard `{summary.get('decision_compiler_leak_guard_pass')}`.",
        f"- RSI later-outcome maturity: `{summary.get('rsi_outcome_maturity_status')}`; stable closures `{summary.get('rsi_live_complete_stable_count')}`; linkage debt `{summary.get('rsi_missing_link_debt_item_count')}`.",
        f"- Advanced capability pilots: `{summary.get('advanced_pilot_count')}` fixture-ready, `{summary.get('advanced_pilot_executed_count')}` executed, `{summary.get('advanced_pilot_promotion_ready_count')}` promotion-ready.",
        f"- Recommendation later-outcome rows (current preview / durable / grade history): `{summary.get('recommendation_current_preview_later_outcome_graded_rows')}` / `{summary.get('recommendation_durable_later_outcome_graded_rows')}` / `{summary.get('recommendation_grade_history_graded_ledger_event_count')}`. The aggregate `{summary.get('recommendation_later_outcome_graded_rows')}` uses scope `{summary.get('recommendation_later_outcome_metric_scope')}`; model-performance claim allowed now: `{summary.get('model_performance_claim_allowed_now')}`.",
        f"- RSI maturity status from primary WF74 eval: `{summary.get('rsi_status')}`.",
        f"- WF74 eval primary first-hop surface: `{summary.get('wf74_eval_primary_surface')}`.",
    ])
    token_lines = "\n".join([
        f"- Token usage ledger status: `{summary.get('token_usage_status')}`.",
        f"- Token efficiency scorecard status: `{summary.get('token_efficiency_status')}`.",
        f"- Token events observed: `{summary.get('token_event_count')}`.",
        f"- Total observed tokens: `{summary.get('total_tokens_observed')}`.",
        f"- API-equivalent token benchmark (not an invoice): `{summary.get('api_equivalent_token_cost_usd')}` (`{summary.get('api_equivalent_estimate_status')}`; `{summary.get('api_equivalent_cost_rows')}/{summary.get('token_event_count')}` events priced).",
        f"- Estimated ChatGPT credits (not an observed debit): `{summary.get('estimated_chatgpt_credits')}` (`{summary.get('chatgpt_credit_estimate_status')}`; `{summary.get('estimated_chatgpt_credit_rows')}/{summary.get('token_event_count')}` events priced).",
        f"- Rolling 5h / observed 7d tokens: `{summary.get('rolling_5h_total_tokens')}` / `{summary.get('rolling_7d_observed_total_tokens')}`; usage timestamp coverage `{summary.get('usage_timestamp_coverage_percent')}`%.",
        f"- Actual billed cost (owner-entered only): `{summary.get('actual_billed_cost_usd')}`.",
        f"- OAuth quota state / remaining / days to reset: `{summary.get('oauth_quota_state')}` / `{summary.get('oauth_remaining_percent')}` / `{summary.get('oauth_days_to_reset')}`.",
        f"- Cron token events: `{summary.get('cron_token_event_count')}`.",
        f"- Implementation token events: `{summary.get('implementation_token_event_count')}`.",
        f"- Implementation token gaps: `{summary.get('implementation_token_gap_count')}`.",
        f"- API-call reduction candidates: `{summary.get('token_api_call_reduction_candidate_count')}`.",
        f"- Prompt-compression candidates: `{summary.get('token_prompt_compression_candidate_count')}`.",
        f"- Failure-cost candidates: `{summary.get('token_failure_cost_candidate_count')}`.",
        f"- Top token candidate: `{summary.get('token_top_candidate')}`.",
    ])
    page_map = {
        "wiki/README.md": page_header("Veritas Wiki", ["tmp/wf88-wiki-synthesis-packet.json"], "wiki/README.md") + "\n".join([
            "This folder is the durable synthesis layer for Veritas OS 2.0.",
            "",
            "It exists to help new sessions retrieve the right proof, understand the current learning loop, and route recommendations into action. It is not canon or approval authority.",
            "",
            "Start with `wiki/index.md`. Cold sessions should use `wiki/syntheses/Cold Session Operating Routes.md`, then drill into the exact owner artifacts named on each page.",
            "Material implementation sessions must consume the versioned efficiency route from `scripts/project_implementation_router.py`; the wiki only retrieves and explains that owner contract.",
            "",
            "## Current action posture",
            "",
            action_lines,
            "",
            "## Claim evidence",
            "",
            claim_card_lines(packet, "wiki/README.md"),
            "",
        ]),
        "wiki/index.md": page_header("Wiki Index", ["tmp/wf88-wiki-synthesis-packet.json", "tmp/wf88-os2-control-packet.json"], "wiki/index.md") + "\n".join([
            "## Sections",
            "",
            "- `wiki/os2/OTEL To Proposal Route.md` - operational signal to proposal routing.",
            "- `wiki/scorecards-and-evals/Current Map.md` - scorecards, evals, and limits.",
            "- `wiki/scorecards-and-evals/Frontier Capability Eval.md` - frozen matched frontier design and evidence gates.",
            "- `wiki/scorecards-and-evals/Advanced Capability Pilots.md` - isolated newer-model capability contracts and stop lines.",
            "- `wiki/scorecards-and-evals/Token Efficiency Map.md` - quality-weighted token attribution, route conformance, retry tax, and comparable-cohort gates.",
            "- `wiki/decisions/Decision Compiler.md` - deterministic evidence-to-decision-object route and retrieval contract.",
            "- `wiki/syntheses/Cold Session Operating Routes.md` - durable how-to routes for cold sessions, including efficient implementation, ticker questions, and cron failures.",
            "- `wiki/self-improvement/Prompt Book RSI Loop.md` - owner-precedence route for reusable prompt and eval friction.",
            "- `wiki/self-improvement/RSI Control Loop.md` - guarded self-prompting and recursive self-improvement.",
            "- `wiki/recommendations/Action Promotion Map.md` - how recommendations become action rows.",
            "- `wiki/gaps/Open Follow Up Debt.md` - current unresolved improvement debt.",
            "- `wiki/source-map/WF88 Wiki Source Map.md` - exact source artifacts.",
            "- `wiki/changes/What Changed Since Last Refresh.md` - claim-catalog changes since the prior refresh.",
            "",
            "## Current summary",
            "",
            f"- WF88 action rows: `{summary.get('wf88_canonical_action_count')}`.",
            f"- Open unrouted recommendations: `{summary.get('open_unrouted_recommendation_count')}`.",
            f"- Loop trace rows: `{summary.get('loop_trace_row_count')}`.",
            f"- Loop trace missing lane links: `{summary.get('loop_trace_lane_link_missing_count')}`.",
            f"- Long-work jobs active/resumable/blocked: `{summary.get('long_work_active_job_count')}` / `{summary.get('long_work_resumable_job_count')}` / `{summary.get('long_work_blocked_job_count')}`.",
            f"- Auto-apply count: `{summary.get('auto_apply_count')}`.",
            f"- Follow-up-required open improvements: `{summary.get('followup_required_open_count')}`.",
            "",
        ]),
        "wiki/syntheses/Cold Session Operating Routes.md": page_header("Cold Session Operating Routes", [
            "AGENTS.md",
            "TOOLS.md",
            "06. Playbooks/Startup Truth Index.md",
            "scripts/README.md",
        ], "wiki/syntheses/Cold Session Operating Routes.md") + "\n".join([
            "This is durable routing knowledge for a session that starts without recent conversational context. Exact owner files and live artifacts remain authoritative when they conflict with this guide.",
            "",
            "## First five minutes",
            "",
            "1. Read the session bootstrap files required by `AGENTS.md`; do not treat this wiki as identity, policy, approval, or execution authority.",
            "2. Use `wiki/index.md` to select a route, then open the exact source artifacts listed on that page.",
            "3. Check timestamps and validation state before repeating a current-state claim. A generated packet routes proof; it does not become canon merely because it is fresh.",
            "4. If an owner source and a generated summary conflict, stop at the owner source and report the contradiction.",
            "",
            "## How to route implementation efficiently",
            "",
            f"The startup contract is `{policy_schema}`, owned by `scripts/project_implementation_router.py`. Semantic retrieval anchor: model-free Terra Codex-native Main Sol.",
            "",
            "1. Use `model_free_command` first when both a deterministic command and deterministic proof are available.",
            "2. Use `codex_native_subagent` only by explicit opt-in for bounded read-only work at Terra/low or one exact leased implementation file at Terra/medium.",
            "3. Use Main/Sol only for an explicit quick fix, final integration, or authority-sensitive judgment exception. Main is not a silent fallback for blocked helper transport.",
            "4. Route remaining bounded helper work to a `persistent_isolated_agent` on Terra only when persistent isolated agent transport proof is fresh, strict, and capability-valid.",
            "5. Record and compare expected versus actual backend/model/thinking. Any actual backend/model/thinking mismatch blocks closeout.",
            "6. Preflight the explicit base path, file/context budget, manifest hashes, and frozen snapshot before model review. Preserve attempt/retry identity and issue a provisional incident update within 90 seconds.",
            "",
            "## Natural-language retrieval anchors",
            "",
            "- What implementation route should a cold session use? Start with deterministic model-free proof, then an eligible explicit Codex-native lane, then an explicit Main/Sol exception, and otherwise a persistent Terra agent with proven transport.",
            "- What proof is required before dispatching a persistent isolated agent? Require a fresh strict capability-valid context-transport proof plus an explicit base path, bounded frozen manifest, hashes, and expected route.",
            "- Should blocked helper transport fall back to Main? No. Stop, repair transport, or explicitly rescope through the router.",
            "",
            "## How to answer a ticker question",
            "",
            "1. Run `python scripts\\finance_sql_canon_access.py --write --validate` to prove the structured finance route is usable.",
            "2. Read `python scripts\\finance_intelligence_state.py ticker <TICKER> --pretty` for the current structured state.",
            "3. Route through WF84 and WF85 for review-only decision context; source-open when evidence is stale, blocked, material, or contradictory.",
            "4. Distinguish data readiness from review readiness, and review readiness from capital or execution approval.",
            "5. Include missing price, band, stop/invalidation, source freshness, and no-chase context as explicit gaps rather than filling them by inference.",
            "",
            "## How to investigate a cron failure",
            "",
            "1. Build `python scripts\\cron_control_packet.py --write --validate` and identify the exact job, attempt, scheduler result, and child artifact.",
            "2. Separate scheduler failure, wrapper timeout, child-script validation failure, and stale carryover state; they are not interchangeable.",
            "3. Open the failing producer artifact and its validator before proposing a repair. A timeout is inconclusive unless the child produced evidence of the underlying defect.",
            "4. Patch code or validation semantics inside the approved workspace boundary. Cron schedule or runtime/config changes require their own authority.",
            "5. Close only after focused tests and the normal scheduled run or an equivalent bounded rerun prove the repair.",
            "",
            "## How to use WF74, WF88, and OTEL",
            "",
            "- Start with `tmp/wiki-bootstrap-proof.json` and `wiki/os2/OTEL To Proposal Route.md`.",
            "- OTEL observations are evidence. WF74 routes improvement candidates. WF88 synthesizes review-only knowledge and proof.",
            "- A recommendation becomes action only after it reaches its named owner route with acceptance proof; no wiki page grants apply authority.",
            "",
            "## Common failure modes",
            "",
            "- Reading a counter without its scope field, especially historical-max metrics presented beside current-preview metrics.",
            "- Treating a missing or timed-out dependency check as evidence that the dependency is broken.",
            "- Trusting a manifest-derived page count without comparing the physical filesystem path set.",
            "- Letting generated summaries outrank owner doctrine, finance canon, or explicit approval boundaries.",
            "- Calling a helper result complete before main-session verification against live files and validators.",
            "",
        ]),
        "wiki/os2/OTEL To Proposal Route.md": page_header("OTEL To Proposal Route", [
            "tmp/otel-ops-control.json",
            "tmp/model-learning-metadata-ledger.json",
            "tmp/wf74-improvement-opportunity-queue.json",
            "tmp/wf74-reflection-to-proposal-autopilot.json",
            "tmp/wf74-auto-patch-proposer.json",
            "tmp/wf74-autonomy-work-router.json",
            "tmp/wf74-wf88-loop-trace.json",
            "tmp/long-work-job-status-packet.json",
            "tmp/pm-control-packet.json",
            "tmp/wf88-os2-control-packet.json",
        ], "wiki/os2/OTEL To Proposal Route.md") + "\n".join([
            "## Route",
            "",
            route_lines,
            "",
            "## Leak Guard",
            "",
            f"- Open unrouted recommendations: `{summary.get('open_unrouted_recommendation_count')}`.",
            f"- Loop trace rows: `{summary.get('loop_trace_row_count')}`.",
            f"- Loop trace missing destinations: `{summary.get('loop_trace_missing_destination_count')}`.",
            f"- Loop trace PM/lane links: `{summary.get('loop_trace_pm_job_link_count')}` / `{summary.get('loop_trace_lane_link_count')}`.",
            f"- Loop trace stale consumers: `{summary.get('loop_trace_downstream_stale_after_router_count')}`.",
            f"- Long-work active/resumable/blocked jobs: `{summary.get('long_work_active_job_count')}` / `{summary.get('long_work_resumable_job_count')}` / `{summary.get('long_work_blocked_job_count')}`.",
            f"- Long-work next safe action: {summary.get('long_work_next_safe_action')}",
            f"- Recommendation to route conversion: `{summary.get('recommendation_to_route_conversion_rate')}`.",
            f"- Route to PM job conversion: `{summary.get('route_to_pm_job_conversion_rate')}`.",
            f"- Auto-apply count: `{summary.get('auto_apply_count')}`.",
            "",
            "## Claim evidence",
            "",
            claim_card_lines(packet, "wiki/os2/OTEL To Proposal Route.md"),
            "",
        ]),
        "wiki/scorecards-and-evals/Current Map.md": page_header("Current Scorecards And Evals", [
            "tmp/wf74-learning-loop-eval-harness.json",
            "tmp/wf74-outcome-eval-suite-v2.json",
            "tmp/model-quality-scorecard.json",
            "tmp/wf87-shadow-outcome-scorecard.json",
            "tmp/retrieval-quality-scorecard.json",
            "tmp/frontier-capability-eval-spine.json",
            "tmp/wf88-decision-compiler.json",
            "tmp/rsi-outcome-scorecard.json",
            "tmp/advanced-capability-pilot-packet.json",
            "tmp/route-efficiency-scorecard.json",
            "tmp/token-efficiency-scorecard.json",
        ], "wiki/scorecards-and-evals/Current Map.md") + "\n".join([
            "## Current eval state",
            "",
            scorecard_lines,
            "",
            "## Token efficiency state",
            "",
            token_lines,
            "",
            "## Interpretation",
            "",
            "These scorecards prove routing, regression behavior, and cost-attribution targets, not investment skill, model performance, or execution readiness.",
            "",
            "## Claim evidence",
            "",
            claim_card_lines(packet, "wiki/scorecards-and-evals/Current Map.md"),
            "",
        ]),
        "wiki/scorecards-and-evals/Frontier Capability Eval.md": page_header("Frontier Capability Eval", [
            "tmp/frontier-capability-eval-spine.json",
            "data/evals/frontier-capability-eval-fixtures.json",
            "tmp/model-quality-scorecard.json",
            "tmp/implementation-token-attribution-bridge.json",
        ], "wiki/scorecards-and-evals/Frontier Capability Eval.md") + "\n".join([
            "## Current contract",
            "",
            f"- Status: `{summary.get('frontier_eval_status')}`; validation: `{summary.get('frontier_eval_validation_status')}`.",
            f"- Frozen cases / assignments: `{summary.get('frontier_fixture_count')}` / `{summary.get('frontier_assignment_count')}`.",
            f"- Collected result rows: `{summary.get('frontier_result_row_count')}`.",
            f"- Fully trusted result rows: `{summary.get('frontier_fully_verified_result_count')}`; execution state: `{summary.get('frontier_model_execution_state')}`.",
            f"- Trusted execution/output/grader attestations: `{summary.get('frontier_trusted_execution_attestation_verified')}` / `{summary.get('frontier_trusted_output_artifact_attestation_verified')}` / `{summary.get('frontier_trusted_grader_attestation_verified')}`.",
            f"- Cross-model ranking allowed: `{summary.get('frontier_cross_model_ranking_allowed')}`.",
            f"- Promotion action allowed: `{summary.get('frontier_promotion_action_allowed')}`.",
            f"- Recent attribution coverage: `{summary.get('frontier_recent_model_attribution_coverage')}`; provider-run join ready: `{summary.get('frontier_provider_run_join_ready')}`.",
            "",
            "## Interpretation",
            "",
            "The frozen 100-case design is ready to collect blinded, source-identical metadata results. Zero collected rows means there is no frontier ranking or promotion evidence yet. Local producer labels and unkeyed hashes establish consistency only; they cannot prove execution, output existence, or independent grading. The grader must receive only the scorer surface, never the coordinator route-to-alias map.",
            "",
        ]),
        "wiki/scorecards-and-evals/Advanced Capability Pilots.md": page_header("Advanced Capability Pilots", [
            "tmp/advanced-capability-pilot-packet.json",
            "data/evals/advanced-capability-pilot-fixtures.json",
            "tmp/frontier-capability-eval-spine.json",
        ], "wiki/scorecards-and-evals/Advanced Capability Pilots.md") + "\n".join([
            "## Current pilot state",
            "",
            f"- Fixture-ready pilots: `{summary.get('advanced_pilot_count')}`.",
            f"- Executed pilots: `{summary.get('advanced_pilot_executed_count')}`.",
            f"- Promotion-ready pilots: `{summary.get('advanced_pilot_promotion_ready_count')}`.",
            f"- Validation: `{summary.get('advanced_pilot_validation_status')}`.",
            "",
            "The current contracts cover strict Structured Outputs, programmatic tool recovery, Responses multi-agent beta, explicit prompt caching, persisted reasoning, and max/pro reasoning. The explicit-cache contract now requires a stable cache key, a supported explicit breakpoint, at least 1,024 prefix tokens, a variable suffix, two matched requests, and cached/write token usage fields. These contracts define isolated request and measurement shapes only; they made no external API calls and captured no raw prompts, responses, reasoning, or tool payloads.",
            "",
            "A later runner needs matched baselines, privacy-safe attribution, cost limits, failure injection, and authority-stop proof. No model route, runtime, configuration, or promotion follows from this page.",
            "",
        ]),
        "wiki/scorecards-and-evals/Token Efficiency Map.md": page_header("Token Efficiency Map", [
            "tmp/token-usage-ledger-current.json",
            "tmp/token-budget-status.json",
            "tmp/token-efficiency-scorecard.json",
            "tmp/implementation-token-attribution-bridge.json",
            "tmp/model-run-ledger-current.json",
            "tmp/concurrent-lane-register.json",
            "tmp/coding-outcome-ledger-current.json",
        ], "wiki/scorecards-and-evals/Token Efficiency Map.md") + "\n".join([
            "## Current token posture",
            "",
            token_lines,
            "",
            "## What this proves",
            "",
            "WF88 can now see which cron/API model calls are token-heavy, which ones are candidates for changed-only prefilters or prompt compression, where implementation lanes are missing usage attribution, and whether accepted jobs conformed to their expected route.",
            "",
            "## Quality-weighted implementation efficiency",
            "",
            "- Optimize uncached input tokens per Main-accepted job and gross tokens per Main-accepted job, not raw token minima.",
            "- Track first-pass acceptance, elapsed time to accepted proof, retry tax, and escaped defects for each parent/phase/attempt route.",
            f"- Current route-conformant / mismatch rows: `{summary.get('coding_outcome_route_conformant_count')}` / `{summary.get('coding_outcome_route_mismatch_count')}`.",
            f"- Current incidents / invalid-token-integrity rows / retry tax: `{summary.get('coding_outcome_incident_row_count')}` / `{summary.get('coding_outcome_invalid_token_integrity_row_count')}` / `{summary.get('coding_outcome_total_retry_count')}`.",
            f"- Comparable cohorts / eligible cohorts: `{summary.get('coding_outcome_comparable_cohort_count')}` / `{summary.get('coding_outcome_eligible_cohort_count')}`.",
            "- Evaluation mode: owner-directed on-demand evidence review.",
            "- Use available token attribution, elapsed-time, retry, first-pass/Main-acceptance, and escaped-defect evidence; prefer like-for-like comparisons when available; no fixed cohort pilot is required.",
            "- Keep normal routing light. Load these ledgers only for an explicit review with `python scripts\\project_implementation_router.py --example --include-efficiency-observation --validate`.",
            "- automatic route ranking and promotion remain disabled; a route-policy change requires explicit Main/owner review.",
            "- Incidents, invalid telemetry, unavailable actual-route data, and mismatches are cost or trust signals; they receive no efficiency success credit.",
            "",
            "## Natural-language retrieval anchors",
            "",
            "- How should a new session measure token efficiency? Use accepted-outcome metrics: uncached and gross tokens per Main-accepted job, first-pass acceptance, time to accepted proof, retry tax, and escaped defects.",
            "- When can an implementation route be promoted? Never automatically; review available evidence on demand, then require an explicit Main/owner policy change.",
            "",
            "## What it does not prove",
            "",
            "Token efficiency does not prove answer quality, model skill, investment performance, or execution readiness. Any API-call reduction must pass a separate regression harness before changing cron commands or model routing.",
            "",
            "## Next safe actions",
            "",
            "- Refresh `tmp/token-efficiency-scorecard.json` after token ledger refreshes.",
            "- Refresh `tmp/implementation-token-attribution-bridge.json` after implementation lane closeouts.",
            "- Use changed-input/source-hash prefilters before model calls where the scorecard identifies safe candidates.",
            "- Use fixture-based prompt-compression checks before accepting shorter prompts.",
            "- Run deterministic path/hash/budget preflight before independent QA, reuse the same frozen snapshot, and send only changed-file deltas on repair.",
            "",
        ]),
        "wiki/self-improvement/RSI Control Loop.md": page_header("RSI Control Loop", [
            "tmp/wf74-learning-loop-eval-harness.json",
            "tmp/wf74-outcome-eval-suite-v2.json",
            "tmp/rsi-outcome-scorecard.json",
            "tmp/wf74-decision-docket.json",
            "tmp/improvement-ledger-current.json",
        ], "wiki/self-improvement/RSI Control Loop.md") + "\n".join([
            "## Self-prompting contract",
            "",
            prompt_lines,
            "",
            "## Current RSI state",
            "",
            f"- RSI maturity status: `{summary.get('rsi_status')}`.",
            f"- RSI maturity stage: `{summary.get('rsi_maturity_stage')}`.",
            f"- Rubric dimensions: `{summary.get('rsi_rubric_dimension_count')}`.",
            f"- Primary first-hop eval: `{summary.get('wf74_eval_primary_surface')}`.",
            f"- Legacy RSI first-hop truth: `{summary.get('wf74_legacy_rsi_first_hop_truth')}`.",
            f"- Decision docket rows: `{summary.get('decision_docket_row_count')}`.",
            f"- Decision docket active actions: `{summary.get('decision_docket_active_action_count')}`.",
            f"- Decision docket hard stops: `{summary.get('decision_docket_hard_stop_count')}`.",
            f"- Live RSI trace rows / stable closures: `{summary.get('rsi_live_trace_row_count')}` / `{summary.get('rsi_live_complete_stable_count')}`.",
            f"- RSI correlation IDs unique/duplicate/missing/noncanonical: `{summary.get('rsi_live_trace_unique_correlation_id_count')}` / `{summary.get('rsi_live_trace_duplicate_correlation_id_count')}` / `{summary.get('rsi_live_trace_missing_correlation_id_count')}` / `{summary.get('rsi_live_trace_noncanonical_correlation_id_count')}`; integrity gate `{summary.get('rsi_correlation_integrity_gate_met')}`.",
            f"- Closed claims with durability unverified: `{summary.get('rsi_live_closed_unverified_durability_count')}`.",
            f"- Missing outcome-link/metric debt: `{summary.get('rsi_missing_link_debt_item_count')}`.",
            f"- RSI later-outcome maturity: `{summary.get('rsi_outcome_maturity_status')}`.",
            "",
            "`tmp/wf74-rsi-evaluation-harness.json` remains compatibility/drill-in only for one transition cycle and is not first-hop truth.",
            "",
            "RSI remains guarded evaluation and routing. It does not change base-model weights or live doctrine by itself.",
            "",
        ]),
        "wiki/decisions/Decision Compiler.md": page_header("Decision Compiler", [
            "tmp/wf88-decision-compiler.json",
            "tmp/retrieval-quality-scorecard.json",
            "tmp/actionable-improvement-queue.json",
            "tmp/wf74-decision-docket.json",
            "tmp/wf74-autonomy-work-router.json",
            "tmp/wf74-wf88-loop-trace.json",
            "tmp/improvement-ledger-current.json",
            "tmp/recommendation-outcome-ledger-current.json",
        ], "wiki/decisions/Decision Compiler.md") + "\n".join([
            "## Current compiler state",
            "",
            f"- Status / validation: `{summary.get('decision_compiler_status')}` / `{summary.get('decision_compiler_validation_status')}`.",
            f"- Decision objects: `{summary.get('decision_object_count')}`; states: `{summary.get('decision_state_counts')}`.",
            f"- Conflicts / uncertainties: `{summary.get('decision_conflict_count')}` / `{summary.get('decision_uncertain_count')}`.",
            f"- Owner review required / blocked: `{summary.get('decision_owner_review_required_count')}` / `{summary.get('decision_blocked_count')}`.",
            f"- Leak guard: `{summary.get('decision_compiler_leak_guard_pass')}`; wiki/OS2 runtime inputs forbidden: `{summary.get('decision_compiler_runtime_cycle_forbidden')}`.",
            "",
            "## Retrieval contract",
            "",
            f"- Retrieval fixtures: `{summary.get('retrieval_passed_count')}/{summary.get('retrieval_fixture_count')}` passed across `{summary.get('retrieval_class_count')}` classes.",
            f"- Conflict fixtures: `{summary.get('retrieval_conflict_fixture_count')}`; average score: `{summary.get('retrieval_average_score')}`.",
            f"- Freshness modes: `{summary.get('retrieval_freshness_assessment_mode_counts')}`; live source timestamp-age assessments: `{summary.get('retrieval_live_source_timestamp_age_assessment_count')}`; live states: `{summary.get('retrieval_live_source_status_counts')}`.",
            f"- Declared labels authoritative: `{summary.get('retrieval_declared_labels_are_authoritative')}`; label-only cases count as live-source proof: `{summary.get('retrieval_label_only_cases_are_live_source_proof')}`.",
            "",
            "The compiler selects deterministic upstream evidence first, records source precedence/freshness/conflict/authority/expiry/later-outcome fields, and emits review-only decision objects. Runtime direction is upstream artifacts -> compiler -> wiki. The compiler must never read wiki or OS2 as decision inputs.",
            "",
        ]),
        "wiki/recommendations/Action Promotion Map.md": page_header("Action Promotion Map", [
            "tmp/wf74-reflection-to-proposal-autopilot.json",
            "tmp/wf74-auto-patch-proposer.json",
            "tmp/wf74-autonomy-work-router.json",
            "tmp/wf74-wf88-loop-trace.json",
            "tmp/pm-control-packet.json",
            "tmp/wf88-os2-control-packet.json",
            "tmp/actionable-improvement-queue.json",
            "tmp/no-orphan-validator.json",
        ], "wiki/recommendations/Action Promotion Map.md") + "\n".join([
            "## Promotion states",
            "",
            action_lines,
            "",
            "## Claim evidence",
            "",
            claim_card_lines(packet, "wiki/recommendations/Action Promotion Map.md"),
            "",
            "## Required rule",
            "",
            "A recommendation is not action until it is routed into WF74 docket, PM job, owner packet, Skill Workshop proposal, validator patch, or monitor-only state with proof. Open improvement rows must also pass the no-orphan validator.",
            "",
        ]),
        "wiki/gaps/Open Follow Up Debt.md": page_header("Open Follow Up Debt", [
            "tmp/improvement-ledger-current.json",
            "tmp/actionable-improvement-queue.json",
            "tmp/no-orphan-validator.json",
            "tmp/wf74-decision-docket.json",
            "tmp/wf88-os2-control-packet.json",
        ], "wiki/gaps/Open Follow Up Debt.md") + "\n".join([
            "## Current debt",
            "",
            f"- Improvement open count: `{summary.get('improvement_open_count')}`.",
            f"- Follow-up-required open count: `{summary.get('followup_required_open_count')}`.",
            f"- High-priority overdue open count: `{summary.get('improvement_high_priority_overdue_open_count')}`.",
            f"- Pending skill proposal count: `{summary.get('pending_skill_proposal_count')}`.",
            f"- Actionable queue items: `{summary.get('actionable_item_count')}`.",
            f"- Actionable queue orphans: `{summary.get('actionable_orphan_count')}`.",
            f"- No-orphan validation: `{summary.get('no_orphan_validation')}`.",
            f"- Top actionable destination: `{summary.get('actionable_top_action_destination')}`.",
            f"- Top actionable next action: {summary.get('actionable_top_next_action')}",
            "",
            "## Claim evidence",
            "",
            claim_card_lines(packet, "wiki/gaps/Open Follow Up Debt.md"),
            "",
            "Follow-up debt is real until closed as a verified fix, owner packet, applied skill proposal, pending skill proposal, monitor-only row, or superseded open improvement.",
            "",
        ]),
        "wiki/self-improvement/Prompt Book RSI Loop.md": page_header("Prompt Book RSI Loop", [
            "skills/veritas-prompt-book-operator/SKILL.md",
            "06. Playbooks/Veritas Prompt Book.md",
            "06. Playbooks/Model Prompt Operations.md",
            "tmp/prompt-book-registry.json",
            "tmp/prompt-book-lint.json",
            "tmp/prompt-book-eval-gap-packet.json",
            "tmp/prompt-book-pm-job-packet.json",
        ], "wiki/self-improvement/Prompt Book RSI Loop.md") + "\n".join([
            "The owner skill and playbooks listed above control when they conflict with this retrieval page. This page is a route map, not a raw prompt vault, model-training surface, or apply authority.",
            "",
            "## Loop",
            "",
            "1. Detect repeated prompt, helper, workflow, PM, cron, or self-improvement friction.",
            "2. Check whether the Prompt Book already owns the pattern before creating another family.",
            "3. Route missing evidence through the eval-gap and PM-job packets; keep prompt content privacy-safe.",
            "4. Use Skill Workshop for proposed reusable doctrine or skill changes.",
            "5. Apply nothing automatically; the exact owner route and its approval contract still govern.",
            "",
            "## Retrieval and precedence",
            "",
            "- Use `skills/veritas-prompt-book-operator/SKILL.md` for the operating procedure.",
            "- Use `06. Playbooks/Veritas Prompt Book.md` and `06. Playbooks/Model Prompt Operations.md` for durable doctrine and evaluation rules.",
            "- Use the JSON packets above for current registry, lint, evidence-gap, and PM-job state. Do not hardcode their counters into this page.",
            "- WF74 owns improvement and Skill Workshop candidate routing; WF88 owns review-only synthesis and retrieval; PM owns implementation-job packaging.",
            "",
            "## Stop lines",
            "",
            "- No raw system prompt, response, tool payload, secret, or credential capture.",
            "- No model self-training or AGI/ASI claim.",
            "- No live skill or doctrine apply without the owner route's explicit approval.",
            "- No finance/canon/portfolio/cash/sizing/risk, capital, paper/live/account, cron schedule, runtime/config, destructive, or external mutation.",
            "",
        ]),
        "wiki/changes/What Changed Since Last Refresh.md": page_header("What Changed Since Last Refresh", [
            "tmp/wf88-wiki-synthesis-packet.json",
            "tmp/wf88-wiki-review-events.json",
        ], "wiki/changes/What Changed Since Last Refresh.md") + "\n".join([
            "## Claim-catalog delta",
            "",
            refresh_delta_lines(packet),
            "",
            "## Review event references",
            "",
            review_event_ref_lines(packet),
            "",
            "This page compares metadata-only claim catalogs. It does not change source artifacts, actions, routing, validation, approval state, or compiler inputs.",
            "",
        ]),
        "wiki/source-map/WF88 Wiki Source Map.md": page_header("WF88 Wiki Source Map", list(SOURCES[name]["path"] for name in SOURCES), "wiki/source-map/WF88 Wiki Source Map.md") + "\n".join([
            "## Source freshness",
            "",
            "\n".join(
                f"- `{name}`: `{as_dict(desc).get('freshness_status')}` / `{as_dict(desc).get('status')}` / `{as_dict(desc).get('path')}` / sha256 `{as_dict(desc).get('sha256')}`"
                for name, desc in as_dict(packet.get("inputs")).items()
            ),
            "",
            "The source map routes readers to exact artifacts. It does not replace source-open inspection when material claims depend on those artifacts.",
            "",
        ]),
    }
    return page_map


def rendered_content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def wiki_source_snapshot_sha256(packet: dict[str, Any]) -> str:
    """Hash only immutable source identity/content fields, never wall-clock freshness."""
    rows = []
    for source_key, raw in sorted(as_dict(packet.get("inputs")).items()):
        descriptor = as_dict(raw)
        rows.append({
            "source_key": source_key,
            "path": descriptor.get("path"),
            "present": descriptor.get("present"),
            "sha256": descriptor.get("sha256"),
        })
    return canonical_json_sha256(rows)


def rendered_page_metadata(page_map: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        page_path: {
            "rendered_sha256": rendered_content_sha256(content),
            "rendered_line_count": len(content.splitlines()),
        }
        for page_path, content in page_map.items()
    }


def retrieval_mirror_path(page_path: str) -> str:
    """Map one canonical wiki path to its stable first-class retrieval source."""
    if not page_path.startswith("wiki/"):
        raise ValueError(f"canonical wiki path must start with wiki/: {page_path}")
    relative_path = page_path.removeprefix("wiki/")
    # The plugin owns every nested index.md as a generated directory index;
    # using that reserved name silently removes the canonical page from search.
    if relative_path == "index.md":
        relative_path = "Wiki Index.md"
    return f"{RETRIEVAL_PAGE_DIR_REL}/{relative_path}"


def retrieval_page_aliases(page_path: str) -> list[str]:
    aliases = RETRIEVAL_PAGE_ALIASES.get(page_path)
    if not isinstance(aliases, list) or not aliases or any(not isinstance(alias, str) or not alias for alias in aliases):
        raise ValueError(f"retrieval aliases missing or invalid for {page_path}")
    return aliases.copy()


def canonical_page_title(page_path: str, content: str) -> str:
    """Keep each source page identifiable in the plugin index and search results."""
    for line in content.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return Path(page_path).stem


def render_retrieval_page(packet: dict[str, Any], page_path: str, content: str) -> str:
    """Render one canonical page as a page-granular plugin-native source."""
    aliases = retrieval_page_aliases(page_path)
    sections = [
        "<!-- openclaw:wiki:raw-source -->",
        f"# {canonical_page_title(page_path, content)}",
        "",
        f"Canonical page: `{page_path}`",
        f"Canonical rendered SHA-256: `{rendered_content_sha256(content)}`.",
        f"Source snapshot SHA-256: `{wiki_source_snapshot_sha256(packet)}`.",
        "Authority: review-only retrieval mirror; canonical wiki and named owner artifacts remain authoritative.",
        "",
        "## Query aliases",
        "",
        *[f"- {alias}" for alias in aliases],
        "",
        "## Canonical content",
        "",
        content.rstrip(),
        "",
    ]
    return "\n".join(sections).rstrip() + "\n"


def retrieval_page_map(packet: dict[str, Any], page_map: dict[str, str]) -> dict[str, str]:
    """Return first-class retrieval sources keyed by their vault-relative paths."""
    return {
        retrieval_mirror_path(page_path): render_retrieval_page(packet, page_path, page_map[page_path])
        for page_path in EXPECTED_WIKI_PAGES
    }


def retrieval_page_contract(packet: dict[str, Any], page_map: dict[str, str]) -> list[dict[str, Any]]:
    rendered_pages = retrieval_page_map(packet, page_map)
    return [
        {
            "canonical_path": page_path,
            "mirror_path": retrieval_mirror_path(page_path),
            "canonical_rendered_sha256": rendered_content_sha256(page_map[page_path]),
            "rendered_sha256": rendered_content_sha256(rendered_pages[retrieval_mirror_path(page_path)]),
            "query_aliases": retrieval_page_aliases(page_path),
        }
        for page_path in EXPECTED_WIKI_PAGES
    ]


def render_retrieval_source(packet: dict[str, Any], page_map: dict[str, str]) -> str:
    """Render a compact index that points the plugin at page-granular sources."""
    sections = [
        "<!-- openclaw:wiki:raw-source -->",
        "# WF88 Wiki Retrieval Index",
        "",
        "This is a generated index for page-granular mirrors of the canonical `wiki/**/*.md` contract. It is review-only, creates no canon or approval authority, and must defer to the named owner sources.",
        "",
        f"Source snapshot SHA-256: `{wiki_source_snapshot_sha256(packet)}`.",
        f"Canonical page count: `{len(page_map)}`.",
        "",
    ]
    for page_path in EXPECTED_WIKI_PAGES:
        sections.extend([
            f"## Canonical page: `{page_path}`",
            "",
            f"Retrieval mirror: `{retrieval_mirror_path(page_path)}`.",
            f"Canonical rendered SHA-256: `{rendered_content_sha256(page_map[page_path])}`.",
            f"Query aliases: {', '.join(retrieval_page_aliases(page_path))}.",
            "",
        ])
    return "\n".join(sections).rstrip() + "\n"


def physical_rendered_wiki_verification(
    expected_pages: dict[str, dict[str, Any]],
    *,
    verify: bool | None = None,
    contract_source: str,
) -> dict[str, Any]:
    """Verify page bytes against hashes/line counts without retaining page bodies."""
    expected_paths = list(EXPECTED_WIKI_PAGES)
    filesystem_paths = wiki_markdown_paths()
    filesystem_set = set(filesystem_paths)
    expected_set = set(expected_paths)
    uncontracted_paths = sorted(filesystem_set - expected_set)
    missing_contracted_paths = sorted(expected_set - filesystem_set)
    metadata_errors: list[str] = []
    if set(expected_pages) != set(expected_paths):
        metadata_errors.append("wiki_rendered_page_metadata_set_mismatch")
    disk_paths = {page_path: ROOT / page_path for page_path in expected_paths}
    existing_paths = [page_path for page_path, path in disk_paths.items() if path.exists()]
    should_verify = bool(existing_paths) if verify is None else bool(verify)
    page_results: list[dict[str, Any]] = []
    errors = list(metadata_errors)
    if should_verify:
        errors.extend(f"wiki_rendered_uncontracted_page:{path}" for path in uncontracted_paths)
    if not should_verify:
        for page_path, path in disk_paths.items():
            page_results.append({
                "path": page_path,
                "present": path.exists(),
                "status": "not_checked",
            })
        return {
            "contract_source": contract_source,
            "status": "not_checked" if not errors else "mismatch",
            "checked": False,
            "expected_page_count": len(expected_paths),
            "present_page_count": len(existing_paths),
            "filesystem_page_count": len(filesystem_paths),
            "filesystem_pages": filesystem_paths,
            "uncontracted_page_paths": uncontracted_paths,
            "missing_contracted_page_paths": missing_contracted_paths,
            "page_results": page_results,
            "errors": errors,
        }
    if not existing_paths:
        for page_path in expected_paths:
            page_results.append({"path": page_path, "present": False, "status": "absent"})
        return {
            "contract_source": contract_source,
            "status": "not_present_tolerated" if not errors else "mismatch",
            "checked": True,
            "expected_page_count": len(expected_paths),
            "present_page_count": 0,
            "filesystem_page_count": len(filesystem_paths),
            "filesystem_pages": filesystem_paths,
            "uncontracted_page_paths": uncontracted_paths,
            "missing_contracted_page_paths": missing_contracted_paths,
            "page_results": page_results,
            "errors": errors,
        }
    if len(existing_paths) != len(expected_paths):
        errors.append(f"wiki_rendered_page_set_incomplete:present={len(existing_paths)}:expected={len(expected_paths)}")
    for page_path in expected_paths:
        expected = as_dict(expected_pages.get(page_path))
        expected_sha256 = expected.get("rendered_sha256")
        expected_line_count = expected.get("rendered_line_count")
        metadata_valid = (
            isinstance(expected_sha256, str)
            and len(expected_sha256) == 64
            and isinstance(expected_line_count, int)
            and expected_line_count >= 0
        )
        path = disk_paths[page_path]
        if not path.exists():
            page_results.append({"path": page_path, "present": False, "status": "missing"})
            errors.append(f"wiki_rendered_page_missing:{page_path}")
            continue
        if not path.is_file():
            page_results.append({"path": page_path, "present": True, "status": "not_regular_file"})
            errors.append(f"wiki_rendered_page_not_regular_file:{page_path}")
            continue
        if not metadata_valid:
            page_results.append({"path": page_path, "present": True, "status": "expected_metadata_invalid"})
            errors.append(f"wiki_rendered_page_expected_metadata_invalid:{page_path}")
            continue
        try:
            observed_content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            page_results.append({"path": page_path, "present": True, "status": "unreadable"})
            errors.append(f"wiki_rendered_page_unreadable:{page_path}")
            continue
        observed_sha256 = rendered_content_sha256(observed_content)
        observed_line_count = len(observed_content.splitlines())
        hash_match = observed_sha256 == expected_sha256
        line_match = observed_line_count == expected_line_count
        page_results.append({
            "path": page_path,
            "present": True,
            "status": "match" if hash_match and line_match else "render_mismatch",
            "observed_sha256": observed_sha256,
            "observed_line_count": observed_line_count,
        })
        if not hash_match:
            errors.append(f"wiki_rendered_page_sha256_mismatch:{page_path}")
        if not line_match:
            errors.append(f"wiki_rendered_page_line_count_mismatch:{page_path}")
    return {
        "contract_source": contract_source,
        "status": "verified" if not errors else "mismatch",
        "checked": True,
        "expected_page_count": len(expected_paths),
        "present_page_count": len(existing_paths),
        "filesystem_page_count": len(filesystem_paths),
        "filesystem_pages": filesystem_paths,
        "uncontracted_page_paths": uncontracted_paths,
        "missing_contracted_page_paths": missing_contracted_paths,
        "page_results": page_results,
        "errors": errors,
    }


def rendered_wiki_verification(page_map: dict[str, str], *, verify: bool | None = None) -> dict[str, Any]:
    return physical_rendered_wiki_verification(
        rendered_page_metadata(page_map),
        verify=verify,
        contract_source="current_build",
    )


def persisted_rendered_wiki_verification(persisted_packet: dict[str, Any], *, verify: bool | None = True) -> dict[str, Any]:
    persisted_rows = {
        str(as_dict(row).get("path")): as_dict(row)
        for row in as_list(persisted_packet.get("wiki_pages"))
    }
    expected_pages = {
        page_path: {
            "rendered_sha256": as_dict(persisted_rows.get(page_path)).get("rendered_sha256"),
            "rendered_line_count": as_dict(persisted_rows.get(page_path)).get("rendered_line_count"),
        }
        for page_path in EXPECTED_WIKI_PAGES
    }
    verification = physical_rendered_wiki_verification(
        expected_pages,
        verify=verify,
        contract_source="persisted_packet",
    )
    if set(persisted_rows) != set(EXPECTED_WIKI_PAGES):
        verification["errors"].append("wiki_rendered_persisted_page_metadata_missing_or_extra")
        verification["status"] = "mismatch"
    if verification.get("checked") and verification.get("present_page_count") == 0:
        # `not_present_tolerated` is only safe for a first-run fixture with no
        # persisted render contract. Once a packet has attested page hashes,
        # losing every contractual page is a physical-render failure.
        verification["errors"].append(
            f"wiki_rendered_persisted_page_set_missing_all:present=0:expected={len(EXPECTED_WIKI_PAGES)}"
        )
        verification["status"] = "mismatch"
    return verification


def rendered_wiki_source_drift(
    packet: dict[str, Any], persisted_packet: dict[str, Any],
) -> dict[str, Any]:
    """Compare immutable current source metadata to the rendered packet baseline.

    This is intentionally a metadata-only drift guard.  It does not use Wiki
    Markdown as an input and does not mutate the candidate claim catalog.
    """
    current_inputs = {
        str(name): as_dict(descriptor)
        for name, descriptor in as_dict(packet.get("inputs")).items()
    }
    persisted_inputs = {
        str(name): as_dict(descriptor)
        for name, descriptor in as_dict(persisted_packet.get("inputs")).items()
    }
    errors: list[str] = []
    source_keys_checked: list[str] = []
    descriptor_fields = ("path", "present", "generated_at_utc", "sha256")
    for source_key in SOURCES:
        current = current_inputs.get(source_key)
        persisted = persisted_inputs.get(source_key)
        if not persisted:
            errors.append(f"wiki_rendered_persisted_source_snapshot_missing:{source_key}")
            continue
        if not current:
            errors.append(f"wiki_rendered_current_source_snapshot_missing:{source_key}")
            continue
        source_keys_checked.append(source_key)
        for field in descriptor_fields:
            if persisted.get(field) != current.get(field):
                errors.append(f"wiki_rendered_source_snapshot_drift:{source_key}:{field}")

    persisted_catalog = _claim_catalog(as_dict(persisted_packet).get("claim_index"))
    claim_source_refs_checked = 0
    if persisted_catalog is None:
        errors.append("wiki_rendered_persisted_claim_catalog_missing_or_incompatible")
    else:
        for claim_id, claim in sorted(persisted_catalog.items()):
            seen_source_keys: set[str] = set()
            for raw_ref in as_list(claim.get("source_refs")):
                ref = as_dict(raw_ref)
                source_key = ref.get("source_key")
                if not isinstance(source_key, str) or source_key not in SOURCES:
                    errors.append(f"wiki_rendered_persisted_claim_source_ref_invalid:{claim_id}")
                    continue
                if source_key in seen_source_keys:
                    continue
                seen_source_keys.add(source_key)
                current = current_inputs.get(source_key)
                persisted = persisted_inputs.get(source_key)
                if not current or not persisted:
                    errors.append(f"wiki_rendered_persisted_claim_source_ref_unavailable:{claim_id}:{source_key}")
                    continue
                claim_source_refs_checked += 1
                for field in ("path", "generated_at_utc", "sha256"):
                    if ref.get(field) != persisted.get(field):
                        errors.append(
                            f"wiki_rendered_persisted_claim_source_ref_mismatch:{claim_id}:{source_key}:{field}"
                        )
                    if ref.get(field) != current.get(field):
                        errors.append(
                            f"wiki_rendered_claim_source_ref_drift:{claim_id}:{source_key}:{field}"
                        )

    stable_errors = sorted(set(errors))
    return {
        "contract_source": "persisted_packet",
        "status": "clean" if not stable_errors else "drifted_or_invalid",
        "source_keys_checked": source_keys_checked,
        "claim_source_refs_checked": claim_source_refs_checked,
        "errors": stable_errors,
    }


def apply_rendered_wiki_metadata(packet: dict[str, Any], verification: dict[str, Any]) -> None:
    """Attach physical observation metadata only; never alter rendered claim values."""
    results = {
        str(as_dict(result).get("path")): as_dict(result)
        for result in as_list(verification.get("page_results"))
    }
    for raw_page in as_list(packet.get("wiki_pages")):
        page = as_dict(raw_page)
        result = as_dict(results.get(str(page.get("path"))))
        if page.get("physical_state") == "planned_write" and verification.get("status") == "not_checked":
            continue
        if result:
            page["present"] = result.get("present")
            page["physical_state"] = result.get("status")
            if result.get("observed_sha256") is not None:
                page["observed_sha256"] = result.get("observed_sha256")
            else:
                page.pop("observed_sha256", None)
            if result.get("observed_line_count") is not None:
                page["observed_line_count"] = result.get("observed_line_count")
            else:
                page.pop("observed_line_count", None)
    packet["rendered_wiki_verification"] = verification
    summary = as_dict(packet.get("summary"))
    summary["filesystem_wiki_page_count"] = verification.get("filesystem_page_count")
    summary["uncontracted_wiki_page_count"] = len(as_list(verification.get("uncontracted_page_paths")))
    summary["missing_contracted_wiki_page_count"] = len(as_list(verification.get("missing_contracted_page_paths")))
    summary["wiki_filesystem_contract_match"] = (
        summary["uncontracted_wiki_page_count"] == 0
        and summary["missing_contracted_wiki_page_count"] == 0
    )


def rendered_wiki_validation_errors(packet: dict[str, Any]) -> list[str]:
    verification = as_dict(packet.get("rendered_wiki_verification"))
    errors: list[str] = []
    if verification.get("contract_source") not in {"current_build", "persisted_packet"}:
        errors.append("wiki_rendered_verification_contract_source_invalid")
    if verification.get("status") not in {"not_checked", "not_present_tolerated", "verified", "mismatch"}:
        errors.append("wiki_rendered_verification_status_invalid")
    if verification.get("expected_page_count") != len(EXPECTED_WIKI_PAGES):
        errors.append("wiki_rendered_verification_expected_page_count_mismatch")
    if verification.get("filesystem_page_count") != len(as_list(verification.get("filesystem_pages"))):
        errors.append("wiki_rendered_verification_filesystem_page_count_mismatch")
    results = [as_dict(result) for result in as_list(verification.get("page_results"))]
    if {str(result.get("path")) for result in results} != set(EXPECTED_WIKI_PAGES):
        errors.append("wiki_rendered_verification_page_result_set_mismatch")
    for error in as_list(verification.get("errors")):
        if not isinstance(error, str) or not error.startswith("wiki_rendered_"):
            errors.append("wiki_rendered_verification_error_invalid")
        else:
            errors.append(error)
    return errors


def sync_packet_status(packet: dict[str, Any]) -> None:
    validation = as_dict(packet.get("validation"))
    if validation.get("status") != "ok":
        packet["status"] = "wiki_synthesis_warning_no_apply_authority"
    else:
        packet["status"] = "wiki_synthesis_ready_no_apply_authority"
    as_dict(packet.get("summary"))["status"] = packet["status"]


def merge_rendered_wiki_validation(packet: dict[str, Any], extra_errors: list[str] | None = None) -> None:
    """Replace only physical-render/immutable-source validation errors."""
    validation = as_dict(packet.get("validation"))
    prior_errors = [
        error for error in as_list(validation.get("errors"))
        if not isinstance(error, str) or not error.startswith("wiki_rendered_")
    ]
    errors = list(dict.fromkeys([
        *prior_errors,
        *rendered_wiki_validation_errors(packet),
        *as_list(extra_errors),
    ]))
    warnings = as_list(validation.get("warnings"))
    packet["validation"] = {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }
    sync_packet_status(packet)


def finalize_rendered_wiki_verification(packet: dict[str, Any], page_map: dict[str, str]) -> None:
    """Verify pages just written from this exact candidate packet."""
    verification = rendered_wiki_verification(page_map, verify=True)
    apply_rendered_wiki_metadata(packet, verification)
    merge_rendered_wiki_validation(packet)


def finalize_persisted_rendered_wiki_validation(
    packet: dict[str, Any], persisted_packet: dict[str, Any],
) -> None:
    """Validate existing pages against their persisted render contract only.

    A read-only validation build has a fresh refresh-delta page by design, so
    comparing it to the current prospective page map would create a false
    mismatch.  The source-drift guard below separately blocks stale renders.
    """
    verification = persisted_rendered_wiki_verification(persisted_packet, verify=True)
    source_drift = rendered_wiki_source_drift(packet, persisted_packet)
    packet["rendered_wiki_verification"] = verification
    packet["rendered_wiki_source_drift"] = source_drift
    merge_rendered_wiki_validation(packet, as_list(source_drift.get("errors")))


def build_packet(
    previous_packet: dict[str, Any] | None = None,
    *,
    verify_rendered_files: bool | None = None,
    planned_write_wiki: bool = False,
) -> dict[str, Any]:
    payloads, inputs = source_snapshots()
    summary = summary_from(payloads)
    semantic_contract = implementation_router.execution_efficiency_semantic_contract()
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "wiki_synthesis_ready_no_apply_authority",
        "purpose": "Durable review-only wiki synthesis for OTEL, WF74, PM, RSI, scorecards, recommendations, and WF88 action routing.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "inputs": inputs,
        "compatibility_surfaces": COMPATIBILITY_SURFACES,
        "wf74_eval_surface_contract": as_dict(payloads["wf74_learning_loop_eval_harness"].get("eval_surface_contract")),
        "wf74_rsi_maturity": as_dict(payloads["wf74_learning_loop_eval_harness"].get("rsi_maturity")),
        "routing_contract": routing_contract(),
        "self_prompting_contract": SELF_PROMPTS,
        "execution_efficiency_policy": implementation_router.execution_efficiency_policy(),
        "startup_efficiency_semantic_contract": {
            "schema": semantic_contract["schema"],
            "owner": "scripts/project_implementation_router.py",
            "pages": list(semantic_contract["required_markers_by_page"]),
            "required_anchors": semantic_contract["required_markers_by_page"],
            "legacy_v1_sufficient_for_material_implementation": semantic_contract["legacy_v1_sufficient_for_material_implementation"],
        },
        "summary": summary,
    }
    packet["action_items"] = action_items(summary)
    packet["claim_index"] = build_claim_index(inputs, summary, [as_dict(row) for row in packet["action_items"]])
    packet["review_event_contract"] = review_event_contract()
    packet["review_event_intake"] = review_event_intake(
        as_dict(packet["claim_index"]), inputs, payloads,
    )
    packet["refresh_delta"] = build_refresh_delta(as_dict(packet["claim_index"]), previous_packet)
    packet["wiki_page_contract"] = {
        "expected_page_count": len(EXPECTED_WIKI_PAGES),
        "pages": EXPECTED_WIKI_PAGES,
        "required_markers": [
            "Status: synthesis only",
            "Owner workflow: WF88",
            "Generated page type:",
            "Authority boundary:",
            "Promotion path:",
            "## Source artifacts",
        ],
        "valid_generated_page_types": sorted(VALID_PAGE_TYPES),
        "page_types": WIKI_PAGE_TYPES.copy(),
    }
    packet["recommendation_leak_guard"] = {
        "open_unrouted_recommendation_count": summary.get("open_unrouted_recommendation_count"),
        "auto_apply_count": summary.get("auto_apply_count"),
        "decision_docket_active_action_count": summary.get("decision_docket_active_action_count"),
        "pm_route_conversion_rate": summary.get("route_to_pm_job_conversion_rate"),
        "pass": int(summary.get("open_unrouted_recommendation_count") or 0) == 0 and int(summary.get("auto_apply_count") or 0) == 0,
    }
    page_map = wiki_pages(packet)
    retrieval_source = render_retrieval_source(packet, page_map)
    retrieval_pages = retrieval_page_contract(packet, page_map)
    packet["wiki_retrieval_contract"] = {
        "schema": "veritas.wf88_wiki_retrieval_mirror.v2",
        "plugin": "memory-wiki",
        "vault_mode": "isolated",
        "corpus": "wiki",
        "canonical_page_count": len(page_map),
        "source_path": RETRIEVAL_SOURCE_REL,
        "rendered_sha256": rendered_content_sha256(retrieval_source),
        "page_granular": True,
        "page_count": len(retrieval_pages),
        "pages": retrieval_pages,
        "authority": "review_only_retrieval_mirror",
    }
    packet["wiki_pages"] = [
        {
            "path": page_path,
            "present": True if planned_write_wiki else (ROOT / page_path).is_file(),
            "physical_state": "planned_write" if planned_write_wiki else "not_checked",
            "owner_workflow": "WF88",
            "status": "synthesis_only",
            "generated_page_type": WIKI_PAGE_TYPES.get(page_path),
            "rendered_sha256": rendered_content_sha256(content),
            "rendered_line_count": len(content.splitlines()),
        }
        for page_path, content in page_map.items()
    ]
    verification = rendered_wiki_verification(page_map, verify=verify_rendered_files)
    apply_rendered_wiki_metadata(packet, verification)
    packet["wiki_page_preview"] = {
        page_path: {
            "line_count": len(content.splitlines()),
            "rendered_sha256": rendered_content_sha256(content),
            "has_source_artifacts": "## Source artifacts" in content,
            "has_authority_boundary": "Authority boundary:" in content,
            "has_promotion_path": "Promotion path:" in content,
            "generated_page_type": WIKI_PAGE_TYPES.get(page_path),
            "has_generated_page_type": f"Generated page type: {WIKI_PAGE_TYPES.get(page_path)}" in content,
        }
        for page_path, content in page_map.items()
    }
    packet["validation"] = validate_packet(packet, page_map, payloads)
    sync_packet_status(packet)
    return packet


def validate_packet(
    packet: dict[str, Any], page_map: dict[str, str], payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    source_payloads = payloads if payloads is not None else source_snapshots()[0]
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    efficiency_policy = as_dict(packet.get("execution_efficiency_policy"))
    if efficiency_policy != implementation_router.execution_efficiency_policy():
        errors.append("execution_efficiency_policy_owner_mismatch")
    semantic_contract = as_dict(packet.get("startup_efficiency_semantic_contract"))
    canonical_semantics = implementation_router.execution_efficiency_semantic_contract()
    if semantic_contract.get("schema") != canonical_semantics["schema"]:
        errors.append("startup_efficiency_semantic_contract_schema_invalid")
    if as_dict(semantic_contract.get("required_anchors")) != canonical_semantics["required_markers_by_page"]:
        errors.append("startup_efficiency_semantic_contract_owner_mismatch")
    for path, markers in as_dict(semantic_contract.get("required_anchors")).items():
        content = page_map.get(path, "")
        for marker in as_list(markers):
            if str(marker) not in content:
                errors.append(f"startup_efficiency_semantic_anchor_missing:{path}:{marker}")
    for name, descriptor in as_dict(packet.get("inputs")).items():
        desc = as_dict(descriptor)
        if desc.get("required") and not desc.get("present"):
            errors.append(f"missing_required_source:{name}:{desc.get('path')}")
        if desc.get("freshness_status") == "stale":
            warnings.append(f"stale_source:{name}:age_hours={desc.get('age_hours')}:max_age_hours={desc.get('max_age_hours')}")
    if "wf74_rsi_evaluation_harness" in as_dict(packet.get("inputs")):
        errors.append("legacy_rsi_harness_must_not_be_required_source")
    contract = as_dict(packet.get("wf74_eval_surface_contract"))
    primary_surface = as_dict(contract.get("primary_surface"))
    secondary_surfaces = [as_dict(row) for row in as_list(contract.get("secondary_surfaces"))]
    deprecated_surfaces = [as_dict(row) for row in as_list(contract.get("deprecated_surfaces"))]
    surface_rows = [primary_surface, *secondary_surfaces, *deprecated_surfaces]
    primary_count = sum(1 for row in surface_rows if row.get("surface_class") == "primary")
    if primary_count != 1:
        errors.append(f"wf74_eval_primary_surface_count:{primary_count}")
    if primary_surface.get("artifact") != "tmp/wf74-learning-loop-eval-harness.json":
        errors.append("wf74_eval_primary_surface_must_be_learning_loop_harness")
    if primary_surface.get("first_hop_truth") is not True:
        errors.append("wf74_eval_primary_surface_must_be_first_hop_truth")
    if not any(row.get("artifact") == "tmp/wf74-outcome-eval-suite-v2.json" for row in secondary_surfaces):
        errors.append("wf74_eval_secondary_outcome_suite_missing")
    legacy_rows = [row for row in deprecated_surfaces if row.get("artifact") == "tmp/wf74-rsi-evaluation-harness.json"]
    if not legacy_rows:
        errors.append("wf74_legacy_rsi_compatibility_surface_missing")
    if any(row.get("first_hop_truth") for row in legacy_rows):
        errors.append("wf74_legacy_rsi_must_not_be_first_hop_truth")
    maturity = as_dict(packet.get("wf74_rsi_maturity"))
    readiness_stages = {str(as_dict(row).get("stage")) for row in as_list(maturity.get("readiness_ladder"))}
    if not readiness_stages:
        errors.append("wf74_rsi_maturity_missing_readiness_ladder")
    elif maturity.get("status") not in readiness_stages:
        errors.append(f"wf74_rsi_maturity_status_not_in_ladder:{maturity.get('status')}")
    current_allowed = as_dict(maturity.get("current_allowed_automation"))
    if current_allowed:
        if current_allowed.get("cron_proof_worker") is not False:
            errors.append("wf74_rsi_cron_proof_worker_enabled_without_wf88_gate")
        for key in (
            "direct_apply",
            "code_patch_without_owner_review",
            "skill_apply_without_owner_approval",
            "sql_import_or_promotion",
            "finance_canon_or_portfolio_mutation",
        ):
            if current_allowed.get(key) is not False:
                errors.append(f"wf74_rsi_forbidden_automation_enabled:{key}")
    if maturity.get("legacy_artifact_required_for_first_hop_truth") is not False:
        errors.append("wf74_rsi_maturity_legacy_artifact_must_not_be_first_hop_truth")
    expected_pages = set(EXPECTED_WIKI_PAGES)
    actual_pages = set(page_map)
    if expected_pages != actual_pages:
        errors.append("wiki_page_set_mismatch")
    if set(WIKI_PAGE_TYPES) != expected_pages:
        errors.append("wiki_page_type_map_mismatch")
    if set(RETRIEVAL_PAGE_ALIASES) != expected_pages:
        errors.append("wiki_retrieval_alias_coverage_mismatch")
    page_contract = as_dict(packet.get("wiki_page_contract"))
    if set(as_dict(page_contract.get("page_types"))) != expected_pages:
        errors.append("wiki_page_contract_type_coverage_mismatch")
    if set(as_list(page_contract.get("valid_generated_page_types"))) != VALID_PAGE_TYPES:
        errors.append("wiki_page_contract_valid_type_set_mismatch")
    page_rows = {str(as_dict(row).get("path")): as_dict(row) for row in as_list(packet.get("wiki_pages"))}
    if set(page_rows) != expected_pages:
        errors.append("wiki_page_metadata_set_mismatch")
    required_markers = as_list(page_contract.get("required_markers"))
    for page_path, content in page_map.items():
        for marker in required_markers:
            if marker not in content:
                errors.append(f"wiki_page_missing_marker:{page_path}:{marker}")
        expected_type = WIKI_PAGE_TYPES.get(page_path)
        if expected_type not in VALID_PAGE_TYPES:
            errors.append(f"wiki_page_invalid_type:{page_path}:{expected_type}")
        if f"Generated page type: {expected_type}" not in content:
            errors.append(f"wiki_page_type_marker_mismatch:{page_path}:{expected_type}")
        page_row = as_dict(page_rows.get(page_path))
        if page_row.get("generated_page_type") != expected_type:
            errors.append(f"wiki_page_metadata_type_mismatch:{page_path}:{expected_type}")
        expected_rendered_sha256 = rendered_content_sha256(content)
        if page_row.get("rendered_sha256") != expected_rendered_sha256:
            errors.append(f"wiki_page_rendered_sha256_mismatch:{page_path}")
        if page_row.get("rendered_line_count") != len(content.splitlines()):
            errors.append(f"wiki_page_rendered_line_count_mismatch:{page_path}")
    retrieval_contract = as_dict(packet.get("wiki_retrieval_contract"))
    if retrieval_contract.get("schema") != "veritas.wf88_wiki_retrieval_mirror.v2":
        errors.append("wiki_retrieval_contract_schema_invalid")
    if retrieval_contract.get("page_granular") is not True:
        errors.append("wiki_retrieval_contract_page_granular_required")
    retrieval_rows = {
        str(as_dict(row).get("canonical_path")): as_dict(row)
        for row in as_list(retrieval_contract.get("pages"))
    }
    if retrieval_contract.get("page_count") != len(EXPECTED_WIKI_PAGES) or set(retrieval_rows) != expected_pages:
        errors.append("wiki_retrieval_contract_page_set_mismatch")
    retrieval_pages = retrieval_page_map(packet, page_map)
    for page_path in EXPECTED_WIKI_PAGES:
        row = as_dict(retrieval_rows.get(page_path))
        mirror_path = retrieval_mirror_path(page_path)
        if row.get("mirror_path") != mirror_path:
            errors.append(f"wiki_retrieval_contract_mirror_path_mismatch:{page_path}")
        if row.get("canonical_rendered_sha256") != rendered_content_sha256(page_map[page_path]):
            errors.append(f"wiki_retrieval_contract_canonical_sha256_mismatch:{page_path}")
        if row.get("rendered_sha256") != rendered_content_sha256(retrieval_pages[mirror_path]):
            errors.append(f"wiki_retrieval_contract_rendered_sha256_mismatch:{page_path}")
        if row.get("query_aliases") != retrieval_page_aliases(page_path):
            errors.append(f"wiki_retrieval_contract_alias_mismatch:{page_path}")
    errors.extend(rendered_wiki_validation_errors(packet))

    claim_index = as_dict(packet.get("claim_index"))
    claims = [as_dict(row) for row in as_list(claim_index.get("claims"))]
    if claim_index.get("schema") != CLAIM_INDEX_SCHEMA:
        errors.append("claim_index_schema_invalid")
    if claim_index.get("authority") != "review_only":
        errors.append("claim_index_authority_must_be_review_only")
    if claim_index.get("claim_count") != len(claims):
        errors.append("claim_index_count_mismatch")
    claim_ids = [claim.get("claim_id") for claim in claims]
    if len(claim_ids) != len(set(claim_ids)) or any(not _safe_ref_id(claim_id) for claim_id in claim_ids):
        errors.append("claim_index_ids_invalid_or_duplicate")
    action_claim_ids = {f"action-state:{as_dict(row).get('id')}" for row in as_list(packet.get("action_items"))}
    observed_action_claim_ids = {
        str(claim.get("claim_id")) for claim in claims if claim.get("claim_kind") == "rendered_action_state"
    }
    if action_claim_ids != observed_action_claim_ids:
        errors.append("claim_index_rendered_action_state_coverage_mismatch")
    required_aggregate_claims = {
        "promotion-leak-guard-health",
        "recommendation-outcome-closure",
        "followup-no-orphan-health",
    }
    if not required_aggregate_claims.issubset(set(str(item) for item in claim_ids)):
        errors.append("claim_index_required_aggregate_claim_missing")
    inputs = {str(name): as_dict(desc) for name, desc in as_dict(packet.get("inputs")).items()}
    prohibited_ref_paths = {
        rel(OUT).replace("\\", "/"),
        "tmp/wf88-wiki-synthesis-packet.json",
        "tmp/wf88-wiki-synthesis-packet.md",
    }
    claim_by_id = {str(claim.get("claim_id")): claim for claim in claims}
    for claim in claims:
        if claim.get("authority") != "review_only":
            errors.append(f"claim_authority_invalid:{claim.get('claim_id')}")
        page_paths = as_list(claim.get("page_paths"))
        if not page_paths or any(path not in expected_pages for path in page_paths):
            errors.append(f"claim_page_paths_invalid:{claim.get('claim_id')}")
        refs = [as_dict(ref) for ref in as_list(claim.get("source_refs"))]
        if not refs:
            errors.append(f"claim_source_refs_empty:{claim.get('claim_id')}")
        for ref in refs:
            if set(ref) != {"source_key", "path", "json_pointer", "generated_at_utc", "sha256"}:
                errors.append(f"claim_source_ref_shape_invalid:{claim.get('claim_id')}")
                continue
            source_key = ref.get("source_key")
            ref_path = str(ref.get("path") or "").replace("\\", "/")
            if source_key not in SOURCES or source_key not in inputs:
                errors.append(f"claim_source_ref_unknown_source:{claim.get('claim_id')}:{source_key}")
                continue
            expected_descriptor = inputs[source_key]
            if ref_path != expected_descriptor.get("path"):
                errors.append(f"claim_source_ref_path_mismatch:{claim.get('claim_id')}:{source_key}")
            if ref_path in prohibited_ref_paths or ref_path.startswith("wiki/") or ref_path.endswith(".md"):
                errors.append(f"claim_source_ref_prohibited_path:{claim.get('claim_id')}:{ref_path}")
            if ref.get("generated_at_utc") != expected_descriptor.get("generated_at_utc"):
                errors.append(f"claim_source_ref_generated_at_mismatch:{claim.get('claim_id')}:{source_key}")
            if ref.get("sha256") != expected_descriptor.get("sha256") or not isinstance(ref.get("sha256"), str):
                errors.append(f"claim_source_ref_hash_mismatch:{claim.get('claim_id')}:{source_key}")
            pointer_valid, _ = json_pointer_get(source_payloads.get(str(source_key)), ref.get("json_pointer"))
            if not pointer_valid:
                errors.append(f"claim_source_ref_pointer_invalid:{claim.get('claim_id')}:{source_key}:{ref.get('json_pointer')}")

    review_contract = as_dict(packet.get("review_event_contract"))
    if review_contract.get("schema") != REVIEW_EVENT_SCHEMA:
        errors.append("review_event_contract_schema_invalid")
    if review_contract.get("path") != rel(review_event_path()):
        errors.append("review_event_contract_path_invalid")
    if review_contract.get("optional") is not True or review_contract.get("upstream_owned") is not True:
        errors.append("review_event_contract_owner_boundary_invalid")
    if review_contract.get("writer_present") is not False or review_contract.get("rendering") != "references_only":
        errors.append("review_event_contract_writer_or_rendering_invalid")
    if set(as_list(review_contract.get("allowed_event_fields"))) != REVIEW_EVENT_ALLOWED_KEYS:
        errors.append("review_event_contract_field_set_invalid")
    if set(as_list(review_contract.get("allowed_dispositions"))) != REVIEW_EVENT_DISPOSITIONS:
        errors.append("review_event_contract_disposition_set_invalid")
    if set(as_list(review_contract.get("allowed_reason_codes"))) != REVIEW_EVENT_REASON_CODES:
        errors.append("review_event_contract_reason_set_invalid")
    if set(as_list(review_contract.get("work_required_routes"))) != REVIEW_EVENT_ALLOWED_ROUTES:
        errors.append("review_event_contract_route_set_invalid")
    if review_contract.get("followup_ref_shape") != "{route, source_ref}; source_ref must resolve to an existing route-owned upstream artifact":
        errors.append("review_event_contract_followup_shape_invalid")
    contract_route_sources = {
        str(route): set(as_list(source_keys))
        for route, source_keys in as_dict(review_contract.get("route_source_keys")).items()
    }
    if contract_route_sources != REVIEW_EVENT_ROUTE_SOURCE_KEYS:
        errors.append("review_event_contract_route_source_map_invalid")

    review_intake = as_dict(packet.get("review_event_intake"))
    if review_intake.get("mode") != "optional_upstream_reference_only":
        errors.append("review_event_intake_mode_invalid")
    if review_intake.get("present") is False and review_intake.get("status") != "not_present_optional":
        errors.append("review_event_intake_missing_must_be_informational")
    for review_error in as_list(review_intake.get("errors")):
        errors.append(f"review_event_intake:{review_error}")
    review_events = [as_dict(row) for row in as_list(review_intake.get("events"))]
    if review_intake.get("event_count") != len(review_events):
        errors.append("review_event_intake_count_mismatch")
    for event in review_events:
        if set(event) != REVIEW_EVENT_ALLOWED_KEYS:
            errors.append("review_event_normalized_shape_invalid")
            continue
        if event.get("claim_id") not in claim_by_id:
            errors.append("review_event_unknown_claim_id")
        if event.get("disposition") not in REVIEW_EVENT_DISPOSITIONS:
            errors.append("review_event_invalid_disposition")
        if event.get("reason_code") not in REVIEW_EVENT_REASON_CODES:
            errors.append("review_event_invalid_reason_code")
        event_ref = as_dict(event.get("source_ref"))
        claim_refs = [as_dict(ref) for ref in as_list(as_dict(claim_by_id.get(str(event.get("claim_id")))).get("source_refs"))]
        if _source_ref_identity(event_ref) not in {_source_ref_identity(ref) for ref in claim_refs}:
            errors.append("review_event_source_ref_not_owned_by_claim")
        followup = event.get("followup_ref")
        normalized_followup, followup_error = (
            _normalize_followup_ref(followup, inputs, source_payloads)
            if followup is not None
            else (None, None)
        )
        if followup_error or (followup is not None and normalized_followup != followup):
            errors.append("review_event_followup_ref_invalid")
        if event.get("disposition") in REVIEW_EVENT_WORK_REQUIRED and normalized_followup is None:
            errors.append("review_event_work_required_without_existing_route")

    refresh_delta = as_dict(packet.get("refresh_delta"))
    allowed_delta_keys = {
        "status",
        "reason",
        "baseline_generated_at_utc",
        "added_claim_ids",
        "removed_claim_ids",
        "changed_claim_ids",
        "source_ref_changed_claim_ids",
    }
    if set(refresh_delta) - allowed_delta_keys:
        errors.append("refresh_delta_must_be_comparison_only")
    if refresh_delta.get("status") not in {"available", "unavailable"}:
        errors.append("refresh_delta_status_invalid")
    if refresh_delta.get("status") == "available" and refresh_delta.get("reason") is not None:
        errors.append("refresh_delta_available_has_reason")
    if refresh_delta.get("status") == "unavailable" and not refresh_delta.get("reason"):
        errors.append("refresh_delta_unavailable_missing_reason")
    for field in ("added_claim_ids", "removed_claim_ids", "changed_claim_ids", "source_ref_changed_claim_ids"):
        ids = as_list(refresh_delta.get(field))
        if ids != sorted(set(ids)) or any(not isinstance(item, str) for item in ids):
            errors.append(f"refresh_delta_{field}_invalid")
    summary = as_dict(packet.get("summary"))
    if int(summary.get("auto_apply_count") or 0) != 0:
        errors.append("auto_apply_count_must_be_zero")
    if int(summary.get("open_unrouted_recommendation_count") or 0) != 0:
        errors.append("open_unrouted_recommendations_must_be_zero")
    if int(summary.get("decision_docket_hard_stop_count") or 0) != 0:
        errors.append("decision_docket_hard_stop_count_must_be_zero")
    if int(summary.get("wf74_learning_eval_failed_count") or 0) != 0:
        errors.append("wf74_learning_eval_failed_count_must_be_zero")
    if int(summary.get("outcome_eval_failed_classifications") or 0) != 0:
        errors.append("outcome_eval_failed_classifications_must_be_zero")
    if int(summary.get("recommendation_current_preview_later_outcome_graded_rows") or 0) == 0:
        warnings.append("recommendation_current_preview_later_outcome_graded_rows_zero")
    if int(summary.get("followup_required_open_count") or 0) > 0:
        warnings.append(f"followup_required_open_count:{summary.get('followup_required_open_count')}")
    if int(summary.get("actionable_orphan_count") or 0):
        errors.append(f"actionable_orphan_count:{summary.get('actionable_orphan_count')}")
    if int(summary.get("actionable_missing_contract_count") or 0):
        errors.append(f"actionable_missing_contract_count:{summary.get('actionable_missing_contract_count')}")
    if summary.get("no_orphan_validation") == "blocked":
        errors.append("no_orphan_validator_blocked")
    if summary.get("no_orphan_validation") == "warning":
        warnings.append("no_orphan_validator_warning")
    if summary.get("loop_trace_validation_status") == "blocked":
        errors.append("loop_trace_validation_blocked")
    elif summary.get("loop_trace_validation_status") == "warning":
        warnings.append("loop_trace_validation_warning")
    if int(summary.get("loop_trace_duplicate_pm_job_id_count") or 0):
        errors.append(f"loop_trace_duplicate_pm_job_id_count:{summary.get('loop_trace_duplicate_pm_job_id_count')}")
    if int(summary.get("loop_trace_high_priority_unrouted_count") or 0):
        errors.append(f"loop_trace_high_priority_unrouted_count:{summary.get('loop_trace_high_priority_unrouted_count')}")
    if int(summary.get("loop_trace_downstream_stale_after_router_count") or 0):
        warnings.append(f"loop_trace_downstream_stale_after_router_count:{summary.get('loop_trace_downstream_stale_after_router_count')}")
    if int(summary.get("loop_trace_lane_link_missing_count") or 0):
        warnings.append(f"loop_trace_lane_link_missing_count:{summary.get('loop_trace_lane_link_missing_count')}")
    if summary.get("long_work_validation_status") == "blocked":
        errors.append("long_work_job_status_validation_blocked")
    elif summary.get("long_work_validation_status") == "warning":
        warnings.append("long_work_job_status_validation_warning")
    if int(summary.get("long_work_blocked_job_count") or 0):
        errors.append(f"long_work_blocked_job_count:{summary.get('long_work_blocked_job_count')}")
    if int(summary.get("long_work_resumable_job_count") or 0):
        warnings.append(f"long_work_resumable_job_count:{summary.get('long_work_resumable_job_count')}")
    if int(summary.get("long_work_stale_active_job_count") or 0):
        warnings.append(f"long_work_stale_active_job_count:{summary.get('long_work_stale_active_job_count')}")
    if summary.get("rsi_status") == "pilot_ready":
        warnings.append("rsi_harness_pilot_ready_not_mature")
    if int(summary.get("implementation_token_gap_count") or 0) > 0:
        warnings.append(f"implementation_token_gap_count:{summary.get('implementation_token_gap_count')}")
    if (
        summary.get("api_equivalent_token_cost_usd") is not None
        and summary.get("token_api_equivalent_is_not_invoice") is not True
    ):
        errors.append("token_api_equivalent_cost_missing_not_invoice_guard")
    if summary.get("api_equivalent_token_cost_usd") is not None and not summary.get("api_equivalent_estimate_status"):
        errors.append("token_api_equivalent_estimate_coverage_status_missing")
    if summary.get("api_equivalent_estimate_status") not in {None, "complete"}:
        warnings.append("token_api_equivalent_estimate_coverage_incomplete")
    if summary.get("estimated_chatgpt_credits") is not None and summary.get("token_credit_estimate_is_not_observed_debit") is not True:
        errors.append("token_credit_estimate_missing_not_observed_debit_guard")
    if summary.get("estimated_chatgpt_credits") is not None and not summary.get("chatgpt_credit_estimate_status"):
        errors.append("token_credit_estimate_coverage_status_missing")
    if summary.get("chatgpt_credit_estimate_status") not in {None, "complete"}:
        warnings.append("token_credit_estimate_coverage_incomplete")
    if summary.get("oauth_quota_state") not in {None, "unavailable", "stale"} and summary.get("oauth_automatic_action_allowed") is not False:
        errors.append("oauth_capacity_automatic_action_must_be_false")
    if int(summary.get("token_api_call_reduction_candidate_count") or 0) > 0:
        warnings.append(f"token_api_call_reduction_candidate_count:{summary.get('token_api_call_reduction_candidate_count')}")
    if summary.get("token_efficiency_status") == "blocked":
        errors.append("token_efficiency_scorecard_blocked")
    if any(
        (
            _blocked_component_status(summary.get("implementation_token_bridge_status")),
            _blocked_component_status(summary.get("implementation_token_bridge_validation_status")),
        )
    ):
        # The bridge governs implementation-efficiency credit, not wiki content
        # integrity. Keep token optimization fail-closed through its action state
        # while allowing independently verified wiki/bootstrap content to route.
        warnings.append("implementation_token_attribution_bridge_blocked_efficiency_claims_only")
    if summary.get("coding_outcome_validation_status") == "blocked":
        errors.append("coding_outcome_ledger_blocked")
    coding_outcome_present = as_dict(as_dict(packet.get("inputs")).get("coding_outcome_ledger")).get("present") is True
    if coding_outcome_present and summary.get("coding_outcome_route_ranking_or_promotion_before_gate") is not False:
        errors.append("coding_outcome_premature_route_ranking_or_promotion")
    if summary.get("retrieval_quality_status") != "ok":
        errors.append(f"retrieval_quality_status_not_ok:{summary.get('retrieval_quality_status')}")
    if summary.get("retrieval_quality_validation_status") != "ok":
        errors.append(f"retrieval_quality_validation_not_ok:{summary.get('retrieval_quality_validation_status')}")
    if int(summary.get("retrieval_fixture_count") or 0) < 30:
        errors.append(f"retrieval_fixture_count_below_30:{summary.get('retrieval_fixture_count')}")
    if int(summary.get("retrieval_class_count") or 0) < 10:
        errors.append(f"retrieval_class_count_below_10:{summary.get('retrieval_class_count')}")
    if int(summary.get("retrieval_failed_count") or 0):
        errors.append(f"retrieval_failed_count:{summary.get('retrieval_failed_count')}")
    if int(summary.get("retrieval_live_source_timestamp_age_assessment_count") or 0) < 1:
        errors.append("retrieval_live_source_timestamp_age_assessment_missing")
    if summary.get("retrieval_label_only_cases_are_live_source_proof") is not False:
        errors.append("retrieval_label_only_cases_must_not_be_live_source_proof")
    if summary.get("retrieval_declared_labels_are_authoritative") is not False:
        errors.append("retrieval_declared_labels_must_not_be_authoritative")
    if summary.get("retrieval_source_timestamp_age_is_live_source_proof") is not True:
        errors.append("retrieval_source_timestamp_age_proof_contract_missing")
    if _blocked_component_status(summary.get("frontier_eval_status")):
        errors.append(f"frontier_eval_status_blocked:{summary.get('frontier_eval_status')}")
    if summary.get("frontier_eval_validation_status") != "ok":
        errors.append(f"frontier_eval_validation_not_ok:{summary.get('frontier_eval_validation_status')}")
    if int(summary.get("frontier_fixture_count") or 0) < 100:
        errors.append(f"frontier_fixture_count_below_100:{summary.get('frontier_fixture_count')}")
    if int(summary.get("frontier_result_row_count") or 0) == 0:
        warnings.append("frontier_eval_result_rows_zero_no_ranking_evidence")
    if summary.get("frontier_promotion_action_allowed") is True:
        errors.append("frontier_promotion_action_must_remain_false")
    if summary.get("frontier_cross_model_ranking_allowed") is True and not all(
        summary.get(key) is True
        for key in (
            "frontier_all_assignment_execution_proven",
            "frontier_proof_index_chain_verified",
            "frontier_all_comparison_gates_passed",
            "frontier_trusted_execution_attestation_verified",
            "frontier_trusted_output_artifact_attestation_verified",
            "frontier_trusted_grader_attestation_verified",
        )
    ):
        errors.append("frontier_ranking_without_complete_trusted_attestation")
    if _blocked_component_status(summary.get("decision_compiler_status")):
        errors.append(f"decision_compiler_status_blocked:{summary.get('decision_compiler_status')}")
    if summary.get("decision_compiler_leak_guard_pass") is not True:
        errors.append("decision_compiler_leak_guard_failed")
    if summary.get("decision_compiler_validation_status") in {"blocked", "error", None}:
        errors.append(f"decision_compiler_validation_blocked:{summary.get('decision_compiler_validation_status')}")
    elif summary.get("decision_compiler_validation_status") == "warning":
        warnings.append("decision_compiler_upstream_warning_visible")
    if int(summary.get("decision_object_count") or 0) == 0:
        errors.append("decision_object_count_zero")
    if int(summary.get("decision_blocked_count") or 0):
        errors.append(f"decision_blocked_count:{summary.get('decision_blocked_count')}")
    if _blocked_component_status(summary.get("rsi_outcome_status")):
        errors.append(f"rsi_outcome_status_blocked:{summary.get('rsi_outcome_status')}")
    if summary.get("rsi_outcome_validation_status") in {"blocked", "error", None}:
        errors.append(f"rsi_outcome_validation_blocked:{summary.get('rsi_outcome_validation_status')}")
    if int(summary.get("rsi_live_authority_violation_count") or 0):
        errors.append(f"rsi_live_authority_violation_count:{summary.get('rsi_live_authority_violation_count')}")
    if int(summary.get("rsi_live_trace_duplicate_correlation_id_count") or 0):
        errors.append(f"rsi_duplicate_correlation_id_count:{summary.get('rsi_live_trace_duplicate_correlation_id_count')}")
    if int(summary.get("rsi_live_trace_missing_correlation_id_count") or 0):
        errors.append(f"rsi_missing_correlation_id_count:{summary.get('rsi_live_trace_missing_correlation_id_count')}")
    if int(summary.get("rsi_live_trace_noncanonical_correlation_id_count") or 0):
        errors.append(f"rsi_noncanonical_correlation_id_count:{summary.get('rsi_live_trace_noncanonical_correlation_id_count')}")
    if summary.get("rsi_correlation_integrity_gate_met") is not True:
        errors.append("rsi_correlation_integrity_gate_not_met")
    if summary.get("rsi_outcome_mature") is not True:
        warnings.append("rsi_outcome_maturity_not_met")
    if summary.get("advanced_pilot_status") != "fixture_ready_no_execution_authority":
        errors.append(f"advanced_pilot_status_invalid:{summary.get('advanced_pilot_status')}")
    if summary.get("advanced_pilot_validation_status") != "ok":
        errors.append(f"advanced_pilot_validation_not_ok:{summary.get('advanced_pilot_validation_status')}")
    if int(summary.get("advanced_pilot_count") or 0) < 6:
        errors.append(f"advanced_pilot_count_below_6:{summary.get('advanced_pilot_count')}")
    if int(summary.get("advanced_pilot_executed_count") or 0) == 0:
        warnings.append("advanced_capability_pilots_unexecuted_fixture_only")
    if int(summary.get("advanced_pilot_promotion_ready_count") or 0) != 0:
        errors.append("advanced_pilot_promotion_ready_must_be_zero")
    if summary.get("advanced_pilot_fixture_contract_safe") is not True:
        errors.append("advanced_pilot_fixture_contract_not_safe")
    if summary.get("model_performance_claim_allowed_now") is True:
        errors.append("model_performance_claim_allowed_now_must_not_be_true")
    if len(as_list(packet.get("action_items"))) == 0:
        errors.append("action_items_empty")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    leak = as_dict(packet.get("recommendation_leak_guard"))
    lines = [
        "# WF88 Wiki Synthesis Packet",
        "",
        "## Verdict",
        "",
        "WF88 wiki synthesis is a durable review-only map. It connects OTEL, WF74, PM, RSI, scorecards, recommendations, and WF88 control evidence without creating canon or approval authority.",
        "",
        "## Summary",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Wiki pages: `{summary.get('wiki_page_count')}`",
        f"- Self-prompts: `{summary.get('self_prompt_count')}`",
        f"- WF88 action rows: `{summary.get('wf88_canonical_action_count')}`",
        f"- WF74 proposals: `{summary.get('wf74_reflection_proposal_count')}`",
        f"- Auto-patch plans: `{summary.get('auto_patch_plan_count')}`",
        f"- Auto-apply count: `{summary.get('auto_apply_count')}`",
        f"- Open unrouted recommendations: `{summary.get('open_unrouted_recommendation_count')}`",
        f"- Loop trace rows: `{summary.get('loop_trace_row_count')}`",
        f"- Loop trace PM/lane links: `{summary.get('loop_trace_pm_job_link_count')}` / `{summary.get('loop_trace_lane_link_count')}`",
        f"- Loop trace stale consumers: `{summary.get('loop_trace_downstream_stale_after_router_count')}`",
        f"- Long-work jobs active/resumable/blocked: `{summary.get('long_work_active_job_count')}` / `{summary.get('long_work_resumable_job_count')}` / `{summary.get('long_work_blocked_job_count')}`",
        f"- Recommendation leak guard pass: `{leak.get('pass')}`",
        f"- RSI status: `{summary.get('rsi_status')}`",
        f"- WF74 eval primary surface: `{summary.get('wf74_eval_primary_surface')}`",
        f"- Legacy RSI first-hop truth: `{summary.get('wf74_legacy_rsi_first_hop_truth')}`",
        f"- Learning eval pass/fail: `{summary.get('wf74_learning_eval_passed_count')}/{summary.get('wf74_learning_eval_failed_count')}`",
        f"- Follow-up-required open improvements: `{summary.get('followup_required_open_count')}`",
        f"- Actionable improvement items: `{summary.get('actionable_item_count')}`",
        f"- Actionable improvement orphans: `{summary.get('actionable_orphan_count')}`",
        f"- No-orphan validation: `{summary.get('no_orphan_validation')}`",
        f"- Recommendation later-outcome graded rows: `{summary.get('recommendation_later_outcome_graded_rows')}`",
        f"- Recommendation later-outcome metric scope: `{summary.get('recommendation_later_outcome_metric_scope')}`",
        f"- Recommendation preview/durable/grade-history graded rows: `{summary.get('recommendation_current_preview_later_outcome_graded_rows')}` / `{summary.get('recommendation_durable_later_outcome_graded_rows')}` / `{summary.get('recommendation_grade_history_graded_ledger_event_count')}`",
        f"- Retrieval fixtures/classes/score: `{summary.get('retrieval_passed_count')}/{summary.get('retrieval_fixture_count')}` / `{summary.get('retrieval_class_count')}` / `{summary.get('retrieval_average_score')}`",
        f"- Frontier fixtures/results/ranking: `{summary.get('frontier_fixture_count')}` / `{summary.get('frontier_result_row_count')}` / `{summary.get('frontier_cross_model_ranking_allowed')}`",
        f"- Decision objects/conflicts/leak guard: `{summary.get('decision_object_count')}` / `{summary.get('decision_conflict_count')}` / `{summary.get('decision_compiler_leak_guard_pass')}`",
        f"- RSI stable closures/linkage debt/maturity: `{summary.get('rsi_live_complete_stable_count')}` / `{summary.get('rsi_missing_link_debt_item_count')}` / `{summary.get('rsi_outcome_maturity_status')}`",
        f"- Advanced pilots fixture-ready/executed/promotion-ready: `{summary.get('advanced_pilot_count')}` / `{summary.get('advanced_pilot_executed_count')}` / `{summary.get('advanced_pilot_promotion_ready_count')}`",
        f"- Token events / total tokens: `{summary.get('token_event_count')}` / `{summary.get('total_tokens_observed')}`",
        f"- API-equivalent token benchmark (not an invoice): `{summary.get('api_equivalent_token_cost_usd')}` (`{summary.get('api_equivalent_estimate_status')}`; `{summary.get('api_equivalent_cost_rows')}/{summary.get('token_event_count')}` events priced)",
        f"- Estimated ChatGPT credits (not an observed debit): `{summary.get('estimated_chatgpt_credits')}` (`{summary.get('chatgpt_credit_estimate_status')}`; `{summary.get('estimated_chatgpt_credit_rows')}/{summary.get('token_event_count')}` events priced)",
        f"- Actual billed cost (owner-entered only): `{summary.get('actual_billed_cost_usd')}`",
        f"- OAuth quota state / remaining: `{summary.get('oauth_quota_state')}` / `{summary.get('oauth_remaining_percent')}`",
        f"- Token API-call reduction candidates: `{summary.get('token_api_call_reduction_candidate_count')}`",
        f"- Implementation token events/gaps: `{summary.get('implementation_token_event_count')}` / `{summary.get('implementation_token_gap_count')}`",
        "",
        "## Actions",
        "",
    ]
    for row in as_list(packet.get("action_items")):
        item = as_dict(row)
        lines.append(f"- `{item.get('id')}`: `{item.get('state')}` - {item.get('next_action')}")
    lines.extend([
        "",
        "## Wiki Pages",
        "",
    ])
    for row in as_list(packet.get("wiki_pages")):
        page = as_dict(row)
        lines.append(f"- `{page.get('path')}`: present `{page.get('present')}`")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Generated wiki pages are synthesis and retrieval maps only.",
        "- No portfolio/canon mutation, execution, cron mutation, model training claim, raw prompt/tool capture, or owner approval inference.",
        "",
    ])
    return "\n".join(lines)


def write_rendered_text_if_changed(path: Path, content: str) -> dict[str, Any]:
    """Write rendered text only when its normalized UTF-8 content changed."""
    existed = path.exists() and path.is_file()
    previous_text = path.read_text(encoding="utf-8") if existed else None
    previous_rendered_sha256 = rendered_content_sha256(previous_text) if previous_text is not None else None
    rendered_sha256 = rendered_content_sha256(content)
    changed = previous_text != content
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, content)
    return {
        "path": rel(path),
        "status": "written_changed" if existed and changed else ("written_new" if changed else "unchanged"),
        "changed": changed,
        "previous_rendered_sha256": previous_rendered_sha256,
        "rendered_sha256": rendered_sha256,
        "rendered_bytes": len(content.encode("utf-8")),
    }


def write_wiki_pages(packet: dict[str, Any], page_map: dict[str, str] | None = None) -> dict[str, Any]:
    rendered_pages = page_map if page_map is not None else wiki_pages(packet)
    rows = [
        write_rendered_text_if_changed(ROOT / rel_path, rendered_pages[rel_path])
        for rel_path in sorted(rendered_pages)
    ]
    retrieval_pages = retrieval_page_map(packet, rendered_pages)
    rows.extend(
        write_rendered_text_if_changed(ROOT / rel_path, retrieval_pages[rel_path])
        for rel_path in sorted(retrieval_pages)
    )
    retrieval_out = ROOT / RETRIEVAL_SOURCE_REL
    retrieval_content = render_retrieval_source(packet, rendered_pages)
    rows.append(write_rendered_text_if_changed(retrieval_out, retrieval_content))
    render_contract = {
        "pages": [
            {"path": path, "rendered_sha256": rendered_content_sha256(rendered_pages[path])}
            for path in sorted(rendered_pages)
        ],
        "retrieval": {
            "path": RETRIEVAL_SOURCE_REL,
            "rendered_sha256": rendered_content_sha256(retrieval_content),
        },
        "retrieval_pages": [
            {"path": path, "rendered_sha256": rendered_content_sha256(retrieval_pages[path])}
            for path in sorted(retrieval_pages)
        ],
    }
    changed_count = sum(1 for row in rows if row["changed"])
    return {
        "schema": "veritas.wf88_wiki_changed_only_write.v1",
        "status": "changed" if changed_count else "unchanged",
        "source_snapshot_sha256": wiki_source_snapshot_sha256(packet),
        "render_contract_sha256": canonical_json_sha256(render_contract),
        "changed_count": changed_count,
        "unchanged_count": len(rows) - changed_count,
        "artifact_count": len(rows),
        "artifacts": rows,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--write-wiki", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    # Snapshot once before any packet/page write. Post-write verification
    # reuses this packet; source inputs are not read again after page writes.
    previous_packet = load(out) if out.exists() else None
    use_persisted_render_contract = bool(
        args.validate
        and not args.write
        and not args.write_wiki
        and previous_packet is not None
    )
    packet = build_packet(
        previous_packet=previous_packet,
        verify_rendered_files=False if (args.write_wiki or use_persisted_render_contract) else (True if args.validate else None),
        planned_write_wiki=args.write_wiki,
    )
    page_map = wiki_pages(packet)
    if args.write_wiki:
        packet["wiki_changed_only_write"] = write_wiki_pages(packet, page_map)
        finalize_rendered_wiki_verification(packet, page_map)
    elif use_persisted_render_contract:
        finalize_persisted_rendered_wiki_validation(packet, as_dict(previous_packet))
    if args.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, packet)
    if args.write_md:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(md_out, render_markdown(packet))
    if args.pretty:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_markdown(packet))
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
