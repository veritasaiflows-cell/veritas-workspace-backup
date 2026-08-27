#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import long_work_packet_linter as linter  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def base_register(packet: dict) -> dict:
    return {
        "schema": "veritas.concurrent_lane_register.v1",
        "lanes": [
            {
                "lane_id": linter.packet_lane_id(packet),
                "workflow_id": packet["workflow_id"],
                "workstream_id": packet["workstream_id"],
                "status": "running",
                "allowed_writes": packet["leased_paths"],
                "proof_artifacts": [],
            }
        ],
    }


def test_valid_spawn_packet(errors: list[str]) -> None:
    packet = linter.example_packet()
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    expect(result["status"] == "ok", f"valid spawn packet should pass: {result['findings']}", errors)
    expect(result["summary"]["model"] == "openai/gpt-5.6-terra", "model summary should be preserved", errors)


def test_ollama_write_requires_tool_loop(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["model_route"] = {
        "model": "ollama-cloud/kimi-k2.7-code:cloud",
        "expected_role": "code_research_draft_helper",
        "trust_label": "untrusted code scaffold",
        "smoke_proof": "no_tool_smoke_passed",
        "resource_reason": "resource reduction canary",
    }
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect(result["status"] == "error", "Ollama write lane without tool-loop proof should fail", errors)
    expect("ollama_write_without_tool_loop_proof" in codes, "expected Ollama tool-loop blocker", errors)


def test_approved_sol_main_exception_is_not_misclassified(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["model_route"] = {
        "model": "openai/gpt-5.6-sol",
        "execution_backend": "main",
        "expected_role": "main_integration_final_judgment",
        "trust_label": "route metadata only; Main verifies and accepts",
        "smoke_proof": "native_tool_loop_available",
        "resource_reason": "Sol is the recorded Main escalation/challenger/QA exception for this bounded route.",
        "main_model_exception": {
            "model_path": "openai/gpt-5.6-sol",
            "use_case": "qa",
            "reason": "Independent QA challenge for a shared runtime control",
            "approved": True,
        },
    }
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect("model_role_mismatch" not in codes, "recorded approved Sol Main exception must not be mislabeled as a role mismatch", errors)

    packet["model_route"]["main_model_exception"]["reason"] = ""
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect("model_role_mismatch" in codes, "Sol Main exception without a reason must remain a warning", errors)


def test_read_only_cannot_have_leased_paths(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["write_mode"] = "read_only"
    result = linter.validate_packet(packet, stage="preflight", register={})
    codes = {finding["code"] for finding in result["findings"]}
    expect(result["status"] == "error", "read-only packet with leased paths should fail", errors)
    expect("read_only_has_leased_paths" in codes, "expected read-only leased path blocker", errors)


def test_closeout_requires_terminal_lane_and_proof(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["closeout_proof"] = {
        "validation_commands": ["python scripts\\test_long_work_packet_linter.py"],
        "proof_artifacts": ["scripts/long_work_packet_linter.py"],
        "helper_outputs_reviewed": True,
        "main_verified": True,
    }
    register = base_register(packet)
    lane = register["lanes"][0]
    lane["status"] = "complete"
    lane["proof_artifacts"] = ["scripts/long_work_packet_linter.py"]
    result = linter.validate_packet(packet, stage="closeout", register=register)
    expect(result["status"] == "ok", f"valid closeout packet should pass: {result['findings']}", errors)


def test_closeout_blocks_non_terminal_lane(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["closeout_proof"] = {
        "validation_commands": ["python scripts\\test_long_work_packet_linter.py"],
        "proof_artifacts": ["scripts/long_work_packet_linter.py"],
        "helper_outputs_reviewed": True,
        "main_verified": True,
    }
    register = base_register(packet)
    result = linter.validate_packet(packet, stage="closeout", register=register)
    codes = {finding["code"] for finding in result["findings"]}
    expect(result["status"] == "error", "closeout with running lane should fail", errors)
    expect("closeout_lane_not_terminal" in codes, "expected non-terminal closeout blocker", errors)


def test_packet_missing_from_lane_register(errors: list[str]) -> None:
    packet = linter.example_packet()
    register = base_register(packet)
    register["lanes"][0]["allowed_writes"] = packet["leased_paths"][:-1]
    result = linter.validate_packet(packet, stage="spawn", register=register)
    codes = {finding["code"] for finding in result["findings"]}
    expect(result["status"] == "error", "missing leased path in lane register should fail", errors)
    expect("leased_paths_not_in_lane_register" in codes, "expected lane-register coverage blocker", errors)


def test_project_artifact_is_coerced_to_packet(errors: list[str]) -> None:
    packet = linter.example_packet()
    project = {
        "schema": linter.PROJECT_SCHEMA,
        "project_id": "project-router-framework-example",
        "workflow_id": packet["workflow_id"],
        "workstream_id": packet["workstream_id"],
        "classification": {
            "task_shape": packet["task_type"],
            "authority_class": packet["authority_class"],
            "validation_budget": packet["validator_budget"],
        },
        "route_owner": packet["route_owner"],
        "frontdoor_proof": packet["frontdoor_proof"],
        "write_mode": packet["write_mode"],
        "leased_paths": packet["leased_paths"],
        "model_route": packet["model_route"],
        "stop_lines": packet["stop_lines"],
        "closeout_proof": {"validation_commands": packet["closeout_required"]},
    }
    coerced = linter.coerce_packet(project)
    result = linter.validate_packet(coerced, stage="preflight", register={})
    expect(coerced["schema"] == linter.SCHEMA, "project artifact should be coerced to linter packet schema", errors)
    expect(result["status"] == "ok", f"coerced project artifact should pass preflight: {result}", errors)
    expect(result["summary"]["project_id"] == "project-router-framework-example", "project id should be retained", errors)


def test_raw_model_free_project_artifact_passes_without_invented_model(errors: list[str]) -> None:
    packet = linter.example_packet()
    project = {
        "schema": linter.PROJECT_SCHEMA,
        "project_id": "model-free-project",
        "workflow_id": packet["workflow_id"],
        "workstream_id": packet["workstream_id"],
        "classification": {
            "task_shape": packet["task_type"],
            "authority_class": packet["authority_class"],
            "validation_budget": packet["validator_budget"],
        },
        "route_owner": packet["route_owner"],
        "frontdoor_proof": packet["frontdoor_proof"],
        "write_mode": packet["write_mode"],
        "leased_paths": packet["leased_paths"],
        "model_route": {
            "execution_backend": "model_free_command",
            "expected_model_path": None,
            "expected_thinking": "none",
            "expected_role": "deterministic_validation",
            "trust_label": "deterministic command proof only",
            "resource_reason": "no model required",
        },
        "stop_lines": packet["stop_lines"],
        "closeout_proof": {"validation_commands": packet["closeout_required"]},
    }
    result = linter.validate_packet(linter.coerce_packet(project), stage="preflight", register={})
    expect(result["status"] == "ok", f"raw model-free project should lint without a model sentinel: {result}", errors)
    codes = {finding["code"] for finding in result["findings"]}
    expect("model_route_missing_field" not in codes, "model-free route must not require a model field", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_valid_spawn_packet,
        test_ollama_write_requires_tool_loop,
        test_approved_sol_main_exception_is_not_misclassified,
        test_read_only_cannot_have_leased_paths,
        test_closeout_requires_terminal_lane_and_proof,
        test_closeout_blocks_non_terminal_lane,
        test_packet_missing_from_lane_register,
        test_project_artifact_is_coerced_to_packet,
        test_raw_model_free_project_artifact_passes_without_invented_model,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: long_work_packet_linter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
