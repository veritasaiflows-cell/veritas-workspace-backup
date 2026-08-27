#!/usr/bin/env python3
"""Focused regression tests for the advanced-capability pilot packet."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import advanced_capability_pilot_packet as subject


ROOT = Path(__file__).resolve().parents[1]


def assert_matches_schema(value, schema, path="$") -> None:
    schema_type = schema.get("type")
    allowed_types = schema_type if isinstance(schema_type, list) else [schema_type]
    if value is None:
        assert "null" in allowed_types, f"{path}: null not allowed"
        return
    if "object" in allowed_types:
        assert isinstance(value, dict), f"{path}: expected object"
        properties = schema["properties"]
        assert set(value) == set(properties), f"{path}: key mismatch"
        for key, child_schema in properties.items():
            assert_matches_schema(value[key], child_schema, f"{path}.{key}")
        return
    if "array" in allowed_types:
        assert isinstance(value, list), f"{path}: expected array"
        for index, item in enumerate(value):
            assert_matches_schema(item, schema["items"], f"{path}[{index}]")
        return
    if "string" in allowed_types:
        assert isinstance(value, str), f"{path}: expected string"
        return
    if "boolean" in allowed_types:
        assert isinstance(value, bool), f"{path}: expected boolean"
        return
    if "number" in allowed_types:
        assert isinstance(value, (int, float)) and not isinstance(value, bool), f"{path}: expected number"
        return
    raise AssertionError(f"{path}: unsupported schema type {schema_type}")


def test_fixture_packet_is_bounded_and_complete() -> None:
    packet = subject.build_packet()
    assert packet["status"] == "fixture_ready_no_execution_authority"
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["pilot_count"] == 6
    assert packet["summary"]["executed_pilot_count"] == 0
    assert packet["summary"]["promotion_ready_count"] == 0
    assert packet["summary"]["external_api_calls_performed"] is False
    assert packet["summary"]["raw_content_stored"] is False
    assert {row["capability"] for row in packet["pilots"]} == subject.EXPECTED_CAPABILITIES


def test_authority_widening_fails_closed() -> None:
    packet = subject.build_packet()
    widened = copy.deepcopy(packet)
    widened["authority_boundary"]["model_route_mutation"] = True
    result = subject.validate_packet(widened)
    assert result["status"] == "blocked"
    assert "authority_boundary_mismatch:model_route_mutation" in result["errors"]


def test_raw_capture_key_fails_closed() -> None:
    packet = subject.build_packet()
    leaked = copy.deepcopy(packet)
    leaked["pilots"][0]["prompt_text"] = "synthetic but still forbidden"
    result = subject.validate_packet(leaked)
    assert result["status"] == "blocked"
    assert any(error.startswith("forbidden_key:") for error in result["errors"])


def test_capability_or_promotion_drift_fails_closed() -> None:
    packet = subject.build_packet()
    drifted = copy.deepcopy(packet)
    drifted["pilots"][0]["capability"] = "unknown_feature"
    drifted["pilots"][1]["promotion_gate"]["promotion_allowed"] = True
    result = subject.validate_packet(drifted)
    assert result["status"] == "blocked"
    assert "capability_set_mismatch" in result["errors"]
    assert any(error.endswith(":promotion_must_be_false") for error in result["errors"])


def test_decision_schema_matches_compiler_and_is_strict_request_ready() -> None:
    packet = subject.build_packet()
    schema = packet["decision_object_schema"]
    required = set(schema["required"])
    assert schema["additionalProperties"] is False
    assert required == set(schema["properties"])
    assert {
        "authority_class",
        "stop_lines",
        "acceptance_proof",
        "source_selection",
        "conflict_uncertainty",
        "expiry_reopen",
        "later_outcome_pointer",
    }.issubset(required)
    structured = next(row for row in packet["pilots"] if row["capability"] == "structured_outputs")
    request_format = structured["request_shape"]["api_request_template"]["text"]["format"]
    assert request_format["strict"] is True
    assert request_format["schema"] == schema
    assert "schema_ref" not in request_format
    compiler_packet = json.loads((ROOT / "tmp" / "wf88-decision-compiler.json").read_text(encoding="utf-8"))
    assert compiler_packet["decisions"]
    for index, decision in enumerate(compiler_packet["decisions"]):
        assert_matches_schema(decision, schema, f"$.decisions[{index}]")


def test_official_api_templates_are_split_from_runner_requirements() -> None:
    packet = subject.build_packet()
    by_capability = {row["capability"]: row for row in packet["pilots"]}
    for row in by_capability.values():
        shape = row["request_shape"]
        assert shape["contract_kind"] == "api_request_template"
        assert shape["api_request_template"]["model"]
        assert shape["runner_requirements"]["api"] == "responses"
    ptc_tools = by_capability["programmatic_tool_calling"]["request_shape"]["api_request_template"]["tools"]
    assert any(tool["type"] == "programmatic_tool_calling" for tool in ptc_tools)
    assert all("programmatic" in tool["allowed_callers"] for tool in ptc_tools if tool["type"] != "programmatic_tool_calling")
    multi_shape = by_capability["responses_multi_agent_beta"]["request_shape"]
    assert multi_shape["api_request_template"]["multi_agent"] == {"enabled": True, "max_concurrent_subagents": 3}
    assert multi_shape["runner_requirements"]["beta_opt_in_header_value"] == "responses_multi_agent=v1"


def test_explicit_prompt_cache_contract_has_breakpoint_key_and_usage_proof() -> None:
    packet = subject.build_packet()
    cache = next(row for row in packet["pilots"] if row["capability"] == "explicit_prompt_caching")
    shape = cache["request_shape"]
    template = shape["api_request_template"]
    runner = shape["runner_requirements"]
    blocks = [block for message in template["input"] for block in message.get("content", [])]
    assert template["prompt_cache_options"] == {"mode": "explicit"}
    assert template["prompt_cache_key"]
    assert any(block.get("prompt_cache_breakpoint") == {"mode": "explicit"} for block in blocks)
    assert runner["minimum_cacheable_prefix_tokens"] >= 1024
    assert runner["rendered_prefix_token_count_verification_required"] is True
    assert runner["two_request_measurement_required"] is True
    assert {
        "usage.input_tokens_details.cached_tokens",
        "usage.input_tokens_details.cache_write_tokens",
    }.issubset(set(runner["required_usage_fields"]))


def test_explicit_prompt_cache_contract_tampering_fails_closed() -> None:
    packet = subject.build_packet()
    cache_index = next(index for index, row in enumerate(packet["pilots"]) if row["capability"] == "explicit_prompt_caching")

    cases = []
    no_breakpoint = copy.deepcopy(packet)
    del no_breakpoint["pilots"][cache_index]["request_shape"]["api_request_template"]["input"][0]["content"][0]["prompt_cache_breakpoint"]
    cases.append((no_breakpoint, "explicit_prompt_cache_breakpoint_missing"))

    no_key = copy.deepcopy(packet)
    no_key["pilots"][cache_index]["request_shape"]["api_request_template"]["prompt_cache_key"] = ""
    cases.append((no_key, "explicit_prompt_cache_key_missing"))

    short_prefix = copy.deepcopy(packet)
    short_prefix["pilots"][cache_index]["request_shape"]["runner_requirements"]["minimum_cacheable_prefix_tokens"] = 1023
    cases.append((short_prefix, "explicit_prompt_cache_minimum_prefix_below_1024"))

    missing_usage = copy.deepcopy(packet)
    missing_usage["pilots"][cache_index]["request_shape"]["runner_requirements"]["required_usage_fields"] = []
    cases.append((missing_usage, "explicit_prompt_cache_usage_measurements_incomplete"))

    unverified_rendered_prefix = copy.deepcopy(packet)
    unverified_rendered_prefix["pilots"][cache_index]["request_shape"]["runner_requirements"]["rendered_prefix_token_count_verification_required"] = False
    cases.append((unverified_rendered_prefix, "explicit_prompt_cache_runner_requirement_missing:rendered_prefix_token_count_verification_required"))

    wrong_prefix_placeholder = copy.deepcopy(packet)
    wrong_prefix_placeholder["pilots"][cache_index]["request_shape"]["api_request_template"]["input"][0]["content"][0]["text"] = "too_short"
    cases.append((wrong_prefix_placeholder, "explicit_prompt_cache_stable_prefix_placeholder_invalid"))

    for tampered, expected_error in cases:
        result = subject.validate_packet(tampered)
        assert result["status"] == "blocked"
        assert expected_error in result["errors"]


if __name__ == "__main__":
    tests = [
        test_fixture_packet_is_bounded_and_complete,
        test_authority_widening_fails_closed,
        test_raw_capture_key_fails_closed,
        test_capability_or_promotion_drift_fails_closed,
        test_decision_schema_matches_compiler_and_is_strict_request_ready,
        test_official_api_templates_are_split_from_runner_requirements,
        test_explicit_prompt_cache_contract_has_breakpoint_key_and_usage_proof,
        test_explicit_prompt_cache_contract_tampering_fails_closed,
    ]
    for test in tests:
        test()
    print("advanced capability pilot packet tests passed")
