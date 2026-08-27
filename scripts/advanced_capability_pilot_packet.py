#!/usr/bin/env python3
"""Build fixture-only GPT-5.6 advanced-capability pilot contracts.

This packet defines isolated eval manifests and metadata-only result contracts.
It never calls an external API, reads credentials, changes model routes, or
stores runtime prompt, response, reasoning, or tool payload bodies.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "evals" / "advanced-capability-pilot-fixtures.json"
JSON_OUT = ROOT / "tmp" / "advanced-capability-pilot-packet.json"
MD_OUT = ROOT / "tmp" / "advanced-capability-pilot-packet.md"
SCHEMA = "veritas.advanced_capability_pilot_packet.v1"

EXPECTED_CAPABILITIES = {
    "structured_outputs",
    "programmatic_tool_calling",
    "responses_multi_agent_beta",
    "explicit_prompt_caching",
    "persisted_reasoning",
    "max_and_pro_reasoning",
}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "fixture_only": True,
    "external_api_calls_performed": False,
    "api_key_or_secret_access": False,
    "raw_prompt_capture": False,
    "raw_response_capture": False,
    "raw_reasoning_capture": False,
    "raw_tool_payload_capture": False,
    "model_route_mutation": False,
    "runtime_or_config_mutation": False,
    "cron_mutation": False,
    "skill_or_doctrine_apply": False,
    "finance_canon_or_portfolio_mutation": False,
    "capital_or_execution_action": False,
    "paper_live_brokerage_or_account_action": False,
    "external_delivery": False,
    "owner_approval_inference": False,
}

DECISION_OBJECT_SCHEMA: dict[str, Any] = {
    "$id": "decision_object_v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema",
        "decision_id",
        "question",
        "state",
        "recommendation",
        "alternatives",
        "source_pointers",
        "source_selection",
        "freshness",
        "conflict_uncertainty",
        "authority_class",
        "owner_route",
        "stop_lines",
        "next_action",
        "next_command",
        "acceptance_proof",
        "expiry_reopen",
        "later_outcome_pointer",
    ],
    "properties": {
        "schema": {"type": "string"},
        "decision_id": {"type": "string"},
        "question": {"type": "string"},
        "state": {"type": "string"},
        "recommendation": {"type": "string"},
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["alternative_id", "description"],
                "properties": {
                    "alternative_id": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "source_pointers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["exact_pointer", "json_pointer", "path", "role", "selected", "source_name"],
                "properties": {
                    "exact_pointer": {"type": "string"},
                    "json_pointer": {"type": "string"},
                    "path": {"type": "string"},
                    "role": {"type": "string"},
                    "selected": {"type": "boolean"},
                    "source_name": {"type": "string"},
                },
            },
        },
        "source_selection": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "stable_key",
                "primary_source_pointer",
                "candidate_source_pointers",
                "field_precedence",
                "selection_reason",
                "generated_review_only",
                "source_open_required_for_material_claim",
            ],
            "properties": {
                "stable_key": {"type": "string"},
                "primary_source_pointer": {"type": "string"},
                "candidate_source_pointers": {"type": "array", "items": {"type": "string"}},
                "field_precedence": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "question_state_recommendation_next_action",
                        "route_and_acceptance_proof",
                        "authority_and_stop_lines",
                        "later_outcome",
                    ],
                    "properties": {
                        "question_state_recommendation_next_action": {"type": "string"},
                        "route_and_acceptance_proof": {"type": "string"},
                        "authority_and_stop_lines": {"type": "string"},
                        "later_outcome": {"type": "string"},
                    },
                },
                "selection_reason": {"type": "string"},
                "generated_review_only": {"type": "boolean"},
                "source_open_required_for_material_claim": {"type": "boolean"},
            },
        },
        "freshness": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "status",
                "generated_at_utc",
                "age_hours",
                "max_age_hours",
                "expires_at_utc",
                "source_statuses",
                "expiry_behavior",
            ],
            "properties": {
                "status": {"type": "string"},
                "generated_at_utc": {"type": ["string", "null"]},
                "age_hours": {"type": ["number", "null"]},
                "max_age_hours": {"type": "number"},
                "expires_at_utc": {"type": ["string", "null"]},
                "source_statuses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["source_name", "path", "freshness_status", "validation_status"],
                        "properties": {
                            "source_name": {"type": "string"},
                            "path": {"type": "string"},
                            "freshness_status": {"type": "string"},
                            "validation_status": {"type": ["string", "null"]},
                        },
                    },
                },
                "expiry_behavior": {"type": "string"},
            },
        },
        "conflict_uncertainty": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "conflict",
                "recommendation_conflict",
                "state_conflict",
                "uncertainties",
                "conflicting_source_pointers",
                "resolution_rule",
            ],
            "properties": {
                "conflict": {"type": "boolean"},
                "recommendation_conflict": {"type": "boolean"},
                "state_conflict": {"type": "boolean"},
                "uncertainties": {"type": "array", "items": {"type": "string"}},
                "conflicting_source_pointers": {"type": "array", "items": {"type": "string"}},
                "resolution_rule": {"type": "string"},
            },
        },
        "authority_class": {"type": "string"},
        "owner_route": {
            "type": "object",
            "additionalProperties": False,
            "required": ["owner_workflow", "route", "route_id", "secondary_routes", "requires_owner_decision"],
            "properties": {
                "owner_workflow": {"type": "string"},
                "route": {"type": "string"},
                "route_id": {"type": "string"},
                "secondary_routes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["route_id", "state", "title"],
                        "properties": {
                            "route_id": {"type": "string"},
                            "state": {"type": "string"},
                            "title": {"type": "string"},
                        },
                    },
                },
                "requires_owner_decision": {"type": "boolean"},
            },
        },
        "stop_lines": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
        "next_command": {
            "type": "object",
            "additionalProperties": False,
            "required": ["command", "execution_posture", "requires_separate_authority_if_scope_crosses_stop_line"],
            "properties": {
                "command": {"type": "string"},
                "execution_posture": {"type": "string"},
                "requires_separate_authority_if_scope_crosses_stop_line": {"type": "boolean"},
            },
        },
        "acceptance_proof": {
            "type": "object",
            "additionalProperties": False,
            "required": ["proof_artifacts", "proof_commands", "close_condition", "source_contract_requirements"],
            "properties": {
                "proof_artifacts": {"type": "array", "items": {"type": "string"}},
                "proof_commands": {"type": "array", "items": {"type": "string"}},
                "close_condition": {"type": "string"},
                "source_contract_requirements": {"type": "array", "items": {"type": "string"}},
            },
        },
        "expiry_reopen": {
            "type": "object",
            "additionalProperties": False,
            "required": ["expires_at_utc", "review_by_utc", "reopen_trigger", "expiry_behavior"],
            "properties": {
                "expires_at_utc": {"type": ["string", "null"]},
                "review_by_utc": {"type": ["string", "null"]},
                "reopen_trigger": {"type": "string"},
                "expiry_behavior": {"type": "string"},
            },
        },
        "later_outcome_pointer": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "path",
                "json_pointer",
                "exact_pointer",
                "match_key",
                "status",
                "outcome_state",
                "current_tracking_pointer",
                "closed_outcome_pointer",
                "future_collection_pointer",
            ],
            "properties": {
                "path": {"type": "string"},
                "json_pointer": {"type": "string"},
                "exact_pointer": {"type": "string"},
                "match_key": {"type": "string"},
                "status": {"type": "string"},
                "outcome_state": {"type": ["string", "null"]},
                "current_tracking_pointer": {"type": ["string", "null"]},
                "closed_outcome_pointer": {"type": ["string", "null"]},
                "future_collection_pointer": {"type": "string"},
            },
        },
    },
}

FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "prompt_text",
    "response_text",
    "reasoning_text",
    "tool_payload",
    "raw_prompt",
    "raw_response",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_contract() -> dict[str, Any]:
    return {
        "stores_content_bodies": False,
        "required_fields": [
            "pilot_id",
            "case_id",
            "candidate_blind_id",
            "model_attribution_source",
            "task_complete",
            "validator_status",
            "authority_violation_count",
            "latency_ms",
            "token_usage_or_unavailable_classification",
            "metric_values",
        ],
        "optional_fields": [
            "input_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost_usd",
        ],
        "forbidden_fields": sorted(FORBIDDEN_KEYS),
    }


def promotion_gate() -> dict[str, Any]:
    return {
        "promotion_allowed": False,
        "minimum_matched_cases": 20,
        "minimum_graded_outputs_per_candidate": 50,
        "required_attribution_coverage": 1.0,
        "maximum_authority_violations": 0,
        "validator_regression_allowed": False,
        "confidence_intervals_required": True,
        "owner_gate_required_for_runtime_or_route_change": True,
    }


def build_packet(fixture_path: Path = FIXTURE_PATH) -> dict[str, Any]:
    fixture = load_json(fixture_path)
    pilots: list[dict[str, Any]] = []
    for row in fixture.get("pilots") or []:
        if not isinstance(row, dict):
            continue
        pilot = copy.deepcopy(row)
        if pilot.get("capability") == "structured_outputs":
            text_format = (
                pilot.setdefault("request_shape", {})
                .setdefault("api_request_template", {})
                .setdefault("text", {})
                .setdefault("format", {})
            )
            text_format.pop("schema_ref", None)
            text_format["schema"] = copy.deepcopy(DECISION_OBJECT_SCHEMA)
        pilot.update(
            {
                "status": "fixture_ready_execution_disabled",
                "external_call_performed": False,
                "result_count": 0,
                "promotion_gate": promotion_gate(),
            }
        )
        pilots.append(pilot)

    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "fixture_ready_no_execution_authority",
        "purpose": "Isolated metadata-only pilots for newer GPT-5.6 and Responses capabilities before any live integration decision.",
        "fixture_source": {
            "path": fixture_path.relative_to(ROOT).as_posix() if fixture_path.is_relative_to(ROOT) else fixture_path.as_posix(),
            "sha256": sha256_file(fixture_path),
            "version": fixture.get("fixture_version"),
        },
        "official_sources": fixture.get("official_sources") or [],
        "summary": {
            "pilot_count": len(pilots),
            "fixture_ready_count": len(pilots),
            "executed_pilot_count": 0,
            "promotion_ready_count": 0,
            "external_api_calls_performed": False,
            "raw_content_stored": False,
            "next_safe_action": "Run only through a separately approved isolated runner with privacy-safe attribution, cost limits, and matched baseline/variant cases.",
        },
        "decision_object_schema": DECISION_OBJECT_SCHEMA,
        "metadata_only_result_contract": result_contract(),
        "pilots": pilots,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] != "ok":
        packet["status"] = "blocked"
    return packet


def _scan_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_KEYS:
                findings.append(f"forbidden_key:{path}.{key}")
            findings.extend(_scan_forbidden_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_scan_forbidden_keys(child, f"{path}[{index}]"))
    return findings


def _strict_schema_errors(schema: Any, path: str = "decision_object") -> list[str]:
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"strict_schema_not_object:{path}"]
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return [f"strict_schema_properties_missing:{path}"]
        if schema.get("additionalProperties") is not False:
            errors.append(f"strict_schema_additional_properties_not_false:{path}")
        required = schema.get("required")
        if set(required or []) != set(properties):
            errors.append(f"strict_schema_required_property_mismatch:{path}")
        for key, child in properties.items():
            errors.extend(_strict_schema_errors(child, f"{path}.{key}"))
    elif schema_type == "array":
        errors.extend(_strict_schema_errors(schema.get("items"), f"{path}[]"))
    return errors


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    pilots = packet.get("pilots") if isinstance(packet.get("pilots"), list) else []
    capabilities = {row.get("capability") for row in pilots if isinstance(row, dict)}
    if capabilities != EXPECTED_CAPABILITIES:
        errors.append("capability_set_mismatch")
    if len(pilots) != len(EXPECTED_CAPABILITIES):
        errors.append("pilot_count_mismatch")
    if len({row.get("pilot_id") for row in pilots if isinstance(row, dict)}) != len(pilots):
        errors.append("pilot_ids_not_unique")

    for row in pilots:
        if not isinstance(row, dict):
            errors.append("pilot_not_object")
            continue
        pilot_id = row.get("pilot_id") or "unknown"
        for key in ["baseline", "variant", "case_set", "request_shape", "measures"]:
            if not row.get(key):
                errors.append(f"{pilot_id}:missing:{key}")
        request_shape = row.get("request_shape") or {}
        api_template = request_shape.get("api_request_template") or {}
        runner_requirements = request_shape.get("runner_requirements") or {}
        if request_shape.get("contract_kind") != "api_request_template":
            errors.append(f"{pilot_id}:request_contract_kind_invalid")
        if not api_template.get("model"):
            errors.append(f"{pilot_id}:api_request_template_model_missing")
        if runner_requirements.get("api") != "responses":
            errors.append(f"{pilot_id}:responses_runner_requirement_missing")
        if row.get("external_call_performed") is not False:
            errors.append(f"{pilot_id}:external_call_must_be_false")
        gate = row.get("promotion_gate") or {}
        if gate.get("promotion_allowed") is not False:
            errors.append(f"{pilot_id}:promotion_must_be_false")

    boundary = packet.get("authority_boundary") or {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    summary = packet.get("summary") or {}
    if summary.get("executed_pilot_count") != 0:
        errors.append("executed_pilot_count_must_be_zero")
    if summary.get("promotion_ready_count") != 0:
        errors.append("promotion_ready_count_must_be_zero")
    if summary.get("external_api_calls_performed") is not False:
        errors.append("summary_external_calls_must_be_false")
    if summary.get("raw_content_stored") is not False:
        errors.append("summary_raw_content_stored_must_be_false")

    schema = packet.get("decision_object_schema") or {}
    if schema.get("additionalProperties") is not False:
        errors.append("decision_schema_must_reject_additional_properties")
    required = set(schema.get("required") or [])
    for field in ["authority_class", "stop_lines", "acceptance_proof", "expiry_reopen", "later_outcome_pointer"]:
        if field not in required:
            errors.append(f"decision_schema_missing_required:{field}")
    errors.extend(_strict_schema_errors(schema))
    structured_rows = [row for row in pilots if isinstance(row, dict) and row.get("capability") == "structured_outputs"]
    structured_format = (((((structured_rows[0].get("request_shape") or {}).get("api_request_template") or {}).get("text") or {}).get("format") or {})) if structured_rows else {}
    if structured_format.get("strict") is not True:
        errors.append("structured_output_request_must_be_strict")
    if structured_format.get("schema") != schema:
        errors.append("structured_output_request_schema_mismatch")

    by_capability = {
        str(row.get("capability")): row
        for row in pilots
        if isinstance(row, dict)
    }
    ptc_shape = as_dict(by_capability.get("programmatic_tool_calling", {}).get("request_shape"))
    ptc_template = as_dict(ptc_shape.get("api_request_template"))
    ptc_tools = [as_dict(tool) for tool in ptc_template.get("tools") or []]
    if not any(tool.get("type") == "programmatic_tool_calling" for tool in ptc_tools):
        errors.append("programmatic_tool_calling_tool_missing")
    eligible_ptc_tools = [tool for tool in ptc_tools if tool.get("type") != "programmatic_tool_calling"]
    if not eligible_ptc_tools or any("programmatic" not in (tool.get("allowed_callers") or []) for tool in eligible_ptc_tools):
        errors.append("programmatic_allowed_callers_missing")

    multi_shape = as_dict(by_capability.get("responses_multi_agent_beta", {}).get("request_shape"))
    multi_template = as_dict(multi_shape.get("api_request_template"))
    multi_contract = as_dict(multi_template.get("multi_agent"))
    multi_runner = as_dict(multi_shape.get("runner_requirements"))
    if multi_contract.get("enabled") is not True or int(multi_contract.get("max_concurrent_subagents") or 0) < 2:
        errors.append("multi_agent_api_contract_invalid")
    if multi_runner.get("beta_opt_in_header_value") != "responses_multi_agent=v1":
        errors.append("multi_agent_beta_opt_in_missing")

    cache_shape = as_dict(by_capability.get("explicit_prompt_caching", {}).get("request_shape"))
    cache_template = as_dict(cache_shape.get("api_request_template"))
    cache_runner = as_dict(cache_shape.get("runner_requirements"))
    if as_dict(cache_template.get("prompt_cache_options")).get("mode") != "explicit":
        errors.append("explicit_prompt_cache_contract_invalid")
    if not str(cache_template.get("prompt_cache_key") or "").strip():
        errors.append("explicit_prompt_cache_key_missing")
    cache_messages = [as_dict(item) for item in cache_template.get("input") or []]
    cache_content_blocks = [
        as_dict(block)
        for message in cache_messages
        for block in message.get("content") or []
        if isinstance(block, dict)
    ]
    breakpoint_indexes = [
        index
        for index, block in enumerate(cache_content_blocks)
        if block.get("type") in {"input_text", "input_image", "input_file"}
        and as_dict(block.get("prompt_cache_breakpoint")).get("mode") == "explicit"
    ]
    if not breakpoint_indexes:
        errors.append("explicit_prompt_cache_breakpoint_missing")
    elif breakpoint_indexes[-1] >= len(cache_content_blocks) - 1:
        errors.append("explicit_prompt_cache_variable_suffix_missing")
    else:
        breakpoint_block = cache_content_blocks[breakpoint_indexes[-1]]
        suffix_blocks = cache_content_blocks[breakpoint_indexes[-1] + 1 :]
        if breakpoint_block.get("text") != "{{synthetic_stable_prefix_min_1024_tokens}}":
            errors.append("explicit_prompt_cache_stable_prefix_placeholder_invalid")
        if not any(block.get("text") == "{{synthetic_variable_case_metadata}}" for block in suffix_blocks):
            errors.append("explicit_prompt_cache_variable_suffix_placeholder_invalid")
    if int(cache_runner.get("minimum_cacheable_prefix_tokens") or 0) < 1024:
        errors.append("explicit_prompt_cache_minimum_prefix_below_1024")
    for requirement in (
        "stable_prefix_hash_required",
        "rendered_prefix_token_count_verification_required",
        "same_prompt_cache_key_required",
        "variable_suffix_after_breakpoint_required",
        "two_request_measurement_required",
        "cache_write_and_read_measurement_required",
    ):
        if cache_runner.get(requirement) is not True:
            errors.append(f"explicit_prompt_cache_runner_requirement_missing:{requirement}")
    required_usage_fields = set(cache_runner.get("required_usage_fields") or [])
    expected_usage_fields = {
        "usage.input_tokens_details.cached_tokens",
        "usage.input_tokens_details.cache_write_tokens",
    }
    if not expected_usage_fields.issubset(required_usage_fields):
        errors.append("explicit_prompt_cache_usage_measurements_incomplete")

    persisted_shape = as_dict(by_capability.get("persisted_reasoning", {}).get("request_shape"))
    persisted_template = as_dict(persisted_shape.get("api_request_template"))
    persisted_runner = as_dict(persisted_shape.get("runner_requirements"))
    if as_dict(persisted_template.get("reasoning")).get("context") != "all_turns":
        errors.append("persisted_reasoning_context_invalid")
    if persisted_runner.get("previous_response_id_required") is not True:
        errors.append("persisted_reasoning_continuation_requirement_missing")

    quality_template = as_dict(as_dict(by_capability.get("max_and_pro_reasoning", {}).get("request_shape")).get("api_request_template"))
    quality_reasoning = as_dict(quality_template.get("reasoning"))
    if quality_reasoning.get("effort") != "max" or quality_reasoning.get("mode") != "pro":
        errors.append("max_pro_reasoning_contract_invalid")

    official_sources = packet.get("official_sources") or []
    if len(official_sources) < 3:
        errors.append("official_sources_incomplete")
    for source in official_sources:
        url = str((source or {}).get("url") or "")
        if not url.startswith("https://developers.openai.com/"):
            errors.append("non_official_source_url")

    errors.extend(_scan_forbidden_keys(packet))
    return {
        "status": "ok" if not errors else "blocked",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Advanced Capability Pilot Packet",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Pilots: `{summary.get('pilot_count')}`",
        "- Execution mode: `fixture_only`",
        "- External API calls performed: `false`",
        "- Raw prompt/response/reasoning/tool content stored: `false`",
        "- Runtime/model-route/config changes: `false`",
        "",
        "| Pilot | Capability | Baseline | Variant | State |",
        "|---|---|---|---|---|",
    ]
    for row in packet.get("pilots") or []:
        lines.append(
            f"| `{row.get('pilot_id')}` | `{row.get('capability')}` | `{row.get('baseline')}` | `{row.get('variant')}` | `{row.get('status')}` |"
        )
    lines.extend(
        [
            "",
            "## Promotion boundary",
            "",
            "No pilot is promotion-ready. A later isolated runner must produce matched cases, complete attribution or accepted unavailable classifications, zero authority violations, no validator regression, and confidence-aware outcome proof.",
            "",
            "## Official references",
            "",
        ]
    )
    for source in packet.get("official_sources") or []:
        lines.append(f"- {source.get('url')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_packet()
    validation = packet.get("validation") or {}
    if args.write:
        JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(JSON_OUT, packet)
    if args.write_md:
        MD_OUT.parent.mkdir(parents=True, exist_ok=True)
        MD_OUT.write_text(render_markdown(packet), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": packet.get("status"),
                "pilot_count": (packet.get("summary") or {}).get("pilot_count"),
                "executed_pilot_count": (packet.get("summary") or {}).get("executed_pilot_count"),
                "validation": validation,
                "written": [
                    path.relative_to(ROOT).as_posix()
                    for enabled, path in [(args.write, JSON_OUT), (args.write_md, MD_OUT)]
                    if enabled
                ],
            },
            indent=2,
        )
    )
    return 0 if (not args.validate or validation.get("status") == "ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
