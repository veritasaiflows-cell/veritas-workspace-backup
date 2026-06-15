#!/usr/bin/env python3
"""Build a bounded approval packet for model/tool/failure/coding learning capture.

The packet is review-only. It proposes the next metadata-only capture and
scoring layer needed for WF74/model-quality learning, while preserving the
hard boundary against raw prompt, response, tool payload, secret, account,
finance-execution, or autonomous self-modification capture.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "model-learning-capture-approval-packet.json"
OUT_MD = TMP / "model-learning-capture-approval-packet.md"
SCHEMA = "veritas.model_learning_capture_approval_packet.v1"

OTEL_OPS = TMP / "otel-ops-control.json"
OTEL_WINDOWS = TMP / "otel-ops-window-summary.json"
MODEL_QUALITY = TMP / "model-quality-scorecard.json"
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
FINANCE_CORRECTNESS = TMP / "finance-recommendation-correctness-ledger-current.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"
FAST_PATH_QA = TMP / "fast-path-qa.json"

FORBIDDEN_CAPTURE = [
    "raw prompt text",
    "raw model response text",
    "tool input payloads",
    "tool output payloads",
    "system prompts",
    "secrets, tokens, OAuth credentials, API keys, authorization headers, cookies",
    "customer/account/PII/suitability/brokerage details",
    "portfolio/canon mutation authority",
    "paper/live trade or account action authority",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") or payload.get("validation", {}).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def current_state() -> dict[str, Any]:
    otel = as_dict(load_json_artifact(OTEL_OPS))
    otel_health = as_dict(otel.get("collector_health"))
    model_quality = as_dict(load_json_artifact(MODEL_QUALITY))
    model_run = as_dict(load_json_artifact(MODEL_RUN_LEDGER))
    model_run_summary = as_dict(model_run.get("summary"))
    wf74_runner = as_dict(load_json_artifact(WF74_RUNNER))
    runner_summary = as_dict(wf74_runner.get("summary"))
    perf_track = as_dict(as_dict(model_quality.get("tracks")).get("performance"))
    otel_dimensions = as_dict(perf_track.get("otel_operational_dimensions"))
    return {
        "otel_status": otel.get("status"),
        "otel_collector_health": otel_health.get("status"),
        "otel_listening": otel_health.get("listening"),
        "model_quality_status": model_quality.get("status"),
        "model_run_ledger_status": model_run.get("status"),
        "model_run_rows": model_run_summary.get("row_count"),
        "model_attribution_coverage": model_run_summary.get("model_attribution_coverage"),
        "session_attribution_coverage": model_run_summary.get("session_attribution_coverage"),
        "cost_rows": model_run_summary.get("cost_rows"),
        "token_rows": model_run_summary.get("token_rows"),
        "wf74_runner_status": wf74_runner.get("status"),
        "wf74_steps_ok": runner_summary.get("steps_ok"),
        "wf74_steps_blocked": runner_summary.get("steps_blocked"),
        "currently_missing_from_basic_otel": {
            key: value
            for key, value in otel_dimensions.items()
            if isinstance(value, str) and "not_available" in value
        },
    }


def build_packet() -> dict[str, Any]:
    capture_plan = [
        {
            "domain": "model",
            "fields": [
                "provider",
                "model_path",
                "thinking_level",
                "request_started_at_utc",
                "request_ended_at_utc",
                "duration_ms",
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "cache_write_tokens",
                "estimated_cost_usd",
                "status",
                "error_category",
                "retry_count",
            ],
            "allowed": True,
            "payload_capture": False,
            "scoring_use": "cost, latency, reliability, attribution coverage, and cache-efficiency scoring",
        },
        {
            "domain": "tools",
            "fields": [
                "tool_name",
                "tool_namespace",
                "operation_category",
                "started_at_utc",
                "ended_at_utc",
                "duration_ms",
                "status",
                "failure_kind",
                "retry_count",
                "output_size_bucket",
            ],
            "allowed": True,
            "payload_capture": False,
            "scoring_use": "tool reliability, latency, blocked-tool, and repeated-failure scoring",
        },
        {
            "domain": "failures",
            "fields": [
                "failure_kind",
                "root_cause_bucket",
                "surface",
                "recoverable",
                "repeated_pattern",
                "validation_gap",
                "owner_action_required",
            ],
            "allowed": True,
            "payload_capture": False,
            "scoring_use": "failure taxonomy, repair prioritization, and skill/validator proposal routing",
        },
        {
            "domain": "coding",
            "fields": [
                "changed_file_count",
                "changed_file_categories",
                "validator_commands",
                "validator_statuses",
                "test_pass_rate",
                "py_compile_status",
                "lint_or_contract_status",
                "closeout_status",
                "rework_required",
            ],
            "allowed": True,
            "payload_capture": False,
            "scoring_use": "implementation-quality, validator-coverage, and repeated-rework scoring",
        },
    ]
    scoring_tracks = [
        {
            "track": "implementation_quality",
            "owner_surface": "tmp/model-quality-scorecard.json",
            "inputs": ["validator pass rate", "surface readiness", "coding closeout status", "rework flags"],
            "allowed_claim": "workflow/coding execution quality trend",
            "blocked_claim": "base model superiority or autonomous self-modification",
        },
        {
            "track": "performance",
            "owner_surface": "tmp/model-run-ledger-current.json + tmp/otel-ops-control.json",
            "inputs": ["model attribution", "latency", "token/cost rows", "tool durations", "failure categories"],
            "allowed_claim": "operational cost/speed/reliability trend",
            "blocked_claim": "finance correctness or model ranking without graded outcomes",
        },
        {
            "track": "tool_reliability",
            "owner_surface": "future metadata-only tool-run ledger",
            "inputs": ["tool name", "namespace", "status", "duration", "failure kind", "retry count"],
            "allowed_claim": "which tools and workflows need repair or wrapper hardening",
            "blocked_claim": "raw tool payload review, secret capture, or external monitoring export",
        },
        {
            "track": "decision_quality",
            "owner_surface": "finance correctness ledger + future WF55 outcome grades",
            "inputs": ["ex-ante boundary correctness", "recommendation structure", "later gated outcome labels"],
            "allowed_claim": "recommendation process quality after enough reviewed outcomes exist",
            "blocked_claim": "investment correctness from OTEL/runtime metrics alone",
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "approval_ready_packet_only_not_enabled",
        "purpose": (
            "Approve the next metadata-only capture and scoring layer so Veritas can learn from "
            "model runs, tool usage, failures, and coding outcomes without capturing raw content "
            "or expanding finance/execution authority."
        ),
        "authority_boundary": {
            "review_only": True,
            "approval_packet_only": True,
            "config_mutation_allowed_by_this_packet": False,
            "runtime_restart_allowed_by_this_packet": False,
            "external_export_allowed": False,
            "raw_prompt_capture_allowed": False,
            "raw_response_capture_allowed": False,
            "tool_payload_capture_allowed": False,
            "system_prompt_capture_allowed": False,
            "secret_or_header_capture_allowed": False,
            "base_model_self_modification_allowed": False,
            "model_ranking_claim_allowed_now": False,
            "investment_correctness_from_runtime_metrics_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "current_state": current_state(),
        "sources": [
            source_status(path)
            for path in [
                OTEL_OPS,
                OTEL_WINDOWS,
                MODEL_QUALITY,
                MODEL_RUN_LEDGER,
                FINANCE_CORRECTNESS,
                WF74_RUNNER,
                CHANGED_FILE_ROUTER,
                FAST_PATH_QA,
            ]
        ],
        "capture_plan_after_explicit_approval_only": capture_plan,
        "forbidden_capture": FORBIDDEN_CAPTURE,
        "scoring_tracks": scoring_tracks,
        "minimum_viable_implementation_after_approval": [
            "Keep OTEL endpoint loopback-only at http://127.0.0.1:4318 unless Randall separately approves another endpoint.",
            "Add metadata-only model/tool run rows to the existing WF74 collection path.",
            "Capture tool names/status/timing/failure class, not tool inputs or outputs.",
            "Capture model/provider/token/cost/timing/status fields where available, not prompts or responses.",
            "Extend model_run_ledger or add a sibling tool_run_ledger with the same false authority flags.",
            "Refresh model_quality_scorecard so model, tool, failure, and coding tracks are scored from the new metadata.",
            "Run privacy validation that scans emitted rows for forbidden content markers before calling the lane clean.",
        ],
        "acceptance_criteria": [
            "OpenClaw collector is local-only and healthy before and after the change.",
            "No raw prompt, response, system prompt, tool input, or tool output appears in emitted artifacts.",
            "No auth headers, tokens, cookies, API keys, OAuth secrets, or credentials appear in emitted artifacts.",
            "Model-run attribution coverage improves or the packet clearly reports why it did not.",
            "Tool-run rows include tool name, namespace, status, timing, and failure class.",
            "Failure taxonomy distinguishes provider error, timeout, validation failure, tool failure, policy/authority block, stale-source block, and user-approval gate.",
            "Coding score uses validator/test/closeout evidence, not vibes.",
            "Scorecard remains review-only and does not claim model ranking, investment correctness, or authority expansion.",
        ],
        "approval_language": (
            "Randall approves a local-only metadata capture and scoring enhancement for WF74/OpenClaw learning. "
            "Approved capture is limited to model/provider identifiers, timing, token/cache/cost counts where available, "
            "tool names/namespaces, tool status/timing/failure classes, validation/test/closeout outcomes, and failure taxonomy metadata. "
            "Raw prompts, model responses, tool inputs, tool outputs, system prompts, secrets, credentials, auth headers, cookies, "
            "customer/account/PII/suitability/brokerage data, external export, base-model self-modification, finance/canon/portfolio mutation, "
            "paper/live/account action, and inferred future authority remain blocked. Implementation must preserve loopback-only OTEL, "
            "write validator proof, and keep all scoring review-only until separate explicit approval changes the boundary."
        ),
        "rollback_plan": [
            "Disable the new metadata collector/ledger route while leaving the existing OTEL health packet intact.",
            "Re-run privacy scan and model-quality scorecard to prove no new rows are emitted.",
            "Remove any newly scheduled metadata collector job if one was added under separate approval.",
            "Preserve before/after packet hashes and report whether any local prototype data should be deleted.",
        ],
        "next_safe_action_after_owner_approval": (
            "Implement the smallest metadata-only extension: a tool/model/failure run ledger plus privacy validator, "
            "then wire it into model_quality_scorecard without enabling content capture."
        ),
    }


def validate(packet: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    false_flags = [
        "config_mutation_allowed_by_this_packet",
        "runtime_restart_allowed_by_this_packet",
        "external_export_allowed",
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "system_prompt_capture_allowed",
        "secret_or_header_capture_allowed",
        "base_model_self_modification_allowed",
        "model_ranking_claim_allowed_now",
        "investment_correctness_from_runtime_metrics_allowed",
        "canon_or_portfolio_mutation_allowed",
        "paper_or_live_or_account_action_allowed",
        "owner_approval_inferred",
    ]
    for flag in false_flags:
        if boundary.get(flag) is not False:
            errors.append(f"authority flag must be false: {flag}")
    for item in packet.get("capture_plan_after_explicit_approval_only", []):
        if item.get("payload_capture") is not False:
            errors.append(f"payload_capture must be false for {item.get('domain')}")
    serialized = json.dumps(packet, sort_keys=True).lower()
    for forbidden in ["raw prompts enabled", "tool outputs enabled", "external export allowed"]:
        if forbidden in serialized:
            errors.append(f"forbidden phrase present: {forbidden}")
    state = as_dict(packet.get("current_state"))
    if state.get("otel_status") != "ok" or state.get("otel_collector_health") != "ok":
        warnings.append("OTEL is not currently green; implementation should not proceed until collector health is ok.")
    missing = as_dict(state.get("currently_missing_from_basic_otel"))
    if not missing:
        warnings.append("Expected basic-OTEL field-depth gaps were not detected; verify model_quality_scorecard schema before implementation.")
    return ("failed" if errors else "ok", errors, warnings)


def render_md(packet: dict[str, Any], status: str, errors: list[str], warnings: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Model Learning Capture Approval Packet")
    lines.append("")
    lines.append(f"Generated: `{packet['generated_at_utc']}`")
    lines.append(f"Status: `{packet['status']}`")
    lines.append("")
    lines.append("## Bottom Line")
    lines.append("")
    lines.append(
        "Approval packet only. It proposes metadata-only capture for model runs, tool use, "
        "failures, and coding outcomes so WF74 can score learning signals. It does not "
        "enable content capture, external export, model ranking, finance correctness claims, "
        "or execution authority."
    )
    lines.append("")
    lines.append("## Current State")
    lines.append("")
    state = as_dict(packet.get("current_state"))
    for key in [
        "otel_status",
        "otel_collector_health",
        "model_quality_status",
        "model_run_ledger_status",
        "model_run_rows",
        "model_attribution_coverage",
        "session_attribution_coverage",
        "cost_rows",
        "token_rows",
    ]:
        lines.append(f"- `{key}`: `{state.get(key)}`")
    lines.append("")
    lines.append("## Proposed Capture")
    lines.append("")
    lines.append("| Domain | Metadata fields | Payload capture | Scoring use |")
    lines.append("|---|---|---:|---|")
    for row in packet["capture_plan_after_explicit_approval_only"]:
        fields = ", ".join(row["fields"])
        lines.append(f"| {row['domain']} | {fields} | {row['payload_capture']} | {row['scoring_use']} |")
    lines.append("")
    lines.append("## Scoring Tracks")
    lines.append("")
    lines.append("| Track | Owner surface | Allowed claim | Blocked claim |")
    lines.append("|---|---|---|---|")
    for row in packet["scoring_tracks"]:
        lines.append(f"| {row['track']} | {row['owner_surface']} | {row['allowed_claim']} | {row['blocked_claim']} |")
    lines.append("")
    lines.append("## Forbidden Capture")
    lines.append("")
    for item in packet["forbidden_capture"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Exact Approval Language")
    lines.append("")
    lines.append(f"> {packet['approval_language']}")
    lines.append("")
    lines.append("## Acceptance Criteria")
    lines.append("")
    for item in packet["acceptance_criteria"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Rollback Plan")
    lines.append("")
    for item in packet["rollback_plan"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append(f"- Status: `{status}`")
    for error in errors:
        lines.append(f"- ERROR: {error}")
    for warning in warnings:
        lines.append(f"- WARNING: {warning}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_packet()
    validation_status, errors, warnings = validate(packet)
    packet["validation"] = {"status": validation_status, "errors": errors, "warnings": warnings}
    if args.write:
        atomic_write_json(OUT_JSON, packet)
    if args.write_md:
        atomic_write_text(OUT_MD, render_md(packet, validation_status, errors, warnings))
    if args.validate:
        print(
            json.dumps(
                {
                    "status": validation_status,
                    "json": rel(OUT_JSON),
                    "md": rel(OUT_MD),
                    "errors": errors,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
        return 1 if errors else 0
    if not args.write and not args.write_md:
        print(json.dumps(packet, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
