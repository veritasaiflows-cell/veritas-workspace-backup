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
    expect(result["summary"]["model"] == "openai/gpt-5.6-sol", "model summary should preserve the configured Main model", errors)


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


def test_main_default_is_not_misclassified(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["model_route"] = {
        "model": "openai/gpt-5.6-sol",
        "execution_backend": "main",
        "expected_role": "main_integration_final_judgment",
        "trust_label": "route metadata only; Main verifies and accepts",
        "smoke_proof": "native_tool_loop_available",
        "resource_reason": "Sol is the configured Main integration model.",
    }
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect("model_role_mismatch" not in codes, "configured Main route must not be mislabeled as a role mismatch", errors)

    packet["model_route"]["expected_role"] = "qa-redteam_specialist"
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect(result["status"] == "error", "Main model claiming qa-redteam_specialist must be critical", errors)
    expect("specialist_model_mismatch" in codes, "Main model specialist mismatch must be critical", errors)


def test_wrong_known_model_qa_role_is_flagged(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["model_route"] = {
        "model": "ollama-cloud/glm-5.3-flash:cloud",
        "execution_backend": "persistent_isolated_agent",
        "expected_role": "qa_helper",
        "trust_label": "untrusted review draft; Main verifies and accepts",
        "smoke_proof": "native_tool_loop_available",
        "resource_reason": "legacy role-label regression probe",
    }
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect("model_role_mismatch" in codes, "a non-QA known model claiming a QA role must be surfaced", errors)


def test_specialist_strict_matrix(errors: list[str]) -> None:
    pairs = [
        ("ollama-cloud/deepseek-v4.1-flash:cloud", "research-scout_specialist"),
        ("ollama-cloud/deepseek-v4.1-flash:cloud", "finance-source-scout_specialist"),
        ("ollama-cloud/glm-5.3:cloud", "finance-redteam_specialist"),
        ("meta/muse-spark-1.3-contributor", "implementation-builder_specialist"),
        ("ollama-cloud/glm-5.3:cloud", "qa-redteam_specialist"),
        ("ollama-cloud/deepseek-v4.1-flash:cloud", "docs-continuity-editor_specialist"),
    ]
    def run(model, role):
        p = linter.example_packet()
        if model == "ollama-cloud/glm-5.3-flash:cloud":
            # Flash lanes are continuity/evidence only: the generic example packet
            # is task_type=implementation, which correctly keeps the frozen
            # flash_write_implementation_lane flag on code lanes.
            p["task_type"] = "continuity"
        p["model_route"] = {"model": model, "expected_role": role, "trust_label": "untrusted draft scaffold", "smoke_proof": "tool_loop_passed", "resource_reason": "r"}
        return linter.validate_packet(p, stage="spawn", register=base_register(p))
    for model, role in pairs:
        expect(run(model, role)["status"] == "ok", f"valid {role} should pass", errors)
    rb = run("xai/grok-4.6", "qa-redteam_specialist")
    expect(rb["status"] == "error" and "specialist_model_mismatch" in {f["code"] for f in rb["findings"]}, "wrong known model must be critical", errors)
    ru = run("unknown/model-x", "qa-redteam_specialist")
    expect(ru["status"] == "error" and "specialist_model_mismatch" in {f["code"] for f in ru["findings"]}, "unknown model must be critical", errors)
    rz = run("xai/grok-4.6", "bogus_specialist")
    expect(rz["status"] == "error" and "unknown_specialist_role" in {f["code"] for f in rz["findings"]}, "unknown specialist must be critical", errors)
    ra = run("ollama-cloud/glm-5.3-flash:cloud", "qa_helper")
    expect(ra["status"] != "error" and "model_role_mismatch" in {f["code"] for f in ra["findings"]}, "advisory qa_helper must stay warning", errors)


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


def test_legacy_and_opus_denied_in_specialist_scope(errors: list[str]) -> None:
    for legacy in ("openai/gpt-5.5", "openai/gpt-5.4", "openai/gpt-5.4-mini"):
        packet = linter.example_packet()
        packet["model_route"] = {"model": legacy, "expected_role": "qa-redteam_specialist", "trust_label": "legacy probe", "smoke_proof": "native_tool_loop_available", "resource_reason": "legacy denial probe"}
        result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
        expect(result["status"] == "error" and "legacy_model_denied" in {f["code"] for f in result["findings"]}, f"{legacy} specialist use must be critically denied", errors)
    packet = linter.example_packet()
    packet["model_route"] = {"model": "anthropic/claude-opus-5", "expected_role": "qa-redteam_specialist", "trust_label": "opus probe", "smoke_proof": "native_tool_loop_available", "resource_reason": "opus denial probe"}
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    expect(result["status"] == "error" and "opus_persistent_denied" in {f["code"] for f in result["findings"]}, "Opus specialist use must be critically denied", errors)


def test_main_ondemand_opus_and_historical_records_not_denied(errors: list[str]) -> None:
    # Scope probe only: an on_demand_advisory Opus task must not attract
    # persistent-model denial. This asserts nothing about route acceptance:
    # independent actual runtime/role proof remains required before any use.
    packet = linter.example_packet()
    packet["model_route"] = {"model": "anthropic/claude-opus-5", "expected_role": "on_demand_advisory", "trust_label": "main-session routed advisory; actual runtime proof required", "smoke_proof": "native_tool_loop_available", "resource_reason": "Main on-demand advisory scope probe"}
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    codes = {finding["code"] for finding in result["findings"]}
    expect("opus_persistent_denied" not in codes, "Main on-demand Opus advisory must not be denied as a persistent model", errors)
    historical = linter.example_packet()
    historical["model_route"] = {"model": "openai/gpt-5.5", "expected_role": "primary_fallback", "trust_label": "historical record probe", "smoke_proof": "native_tool_loop_available", "resource_reason": "historical record probe"}
    hresult = linter.validate_packet(historical, stage="spawn", register=base_register(historical))
    expect("legacy_model_denied" not in {f["code"] for f in hresult["findings"]}, "non-specialist historical record must not be denied", errors)


def test_specialist_fallbacks_denied(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["model_route"] = {"model": "ollama-cloud/glm-5.3:cloud", "expected_role": "qa-redteam_specialist", "trust_label": "untrusted draft scaffold", "smoke_proof": "tool_loop_passed", "resource_reason": "r", "fallbacks": ["ollama-cloud/glm-5.3:cloud"]}
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    expect(result["status"] == "error" and "specialist_automatic_fallback_denied" in {f["code"] for f in result["findings"]}, "specialist fallbacks array must be critically denied", errors)


def test_docs_deepseek_continuity_ok_but_flash_coding_flagged(errors: list[str]) -> None:
    packet = linter.example_packet()
    packet["task_type"] = "continuity"
    packet["model_route"] = {"model": "ollama-cloud/deepseek-v4.1-flash:cloud", "expected_role": "docs-continuity-editor_specialist", "trust_label": "untrusted continuity draft; Main verifies", "smoke_proof": "tool_loop_passed", "resource_reason": "DeepSeek 4.1 Flash docs-continuity route"}
    result = linter.validate_packet(packet, stage="spawn", register=base_register(packet))
    expect(result["status"] != "error", "DeepSeek 4.1 Flash docs-continuity lane must not error", errors)
    expect("specialist_model_mismatch" not in {f["code"] for f in result["findings"]}, "DeepSeek 4.1 Flash docs-continuity role must match", errors)
    coding = linter.example_packet()
    coding["model_route"] = {"model": "ollama-cloud/glm-5.3-flash:cloud", "expected_role": "deterministic_cron_helper", "trust_label": "untrusted proof digest; Main verifies", "smoke_proof": "tool_loop_passed", "resource_reason": "GLM 5.3 Flash coding probe"}
    coding_result = linter.validate_packet(coding, stage="spawn", register=base_register(coding))
    expect("flash_write_implementation_lane" in {f["code"] for f in coding_result["findings"]}, "GLM 5.3 Flash implementation write must keep the frozen continuity-only flag", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_valid_spawn_packet,
        test_ollama_write_requires_tool_loop,
        test_main_default_is_not_misclassified,
        test_wrong_known_model_qa_role_is_flagged,
        test_legacy_and_opus_denied_in_specialist_scope,
        test_main_ondemand_opus_and_historical_records_not_denied,
        test_specialist_fallbacks_denied,
        test_docs_deepseek_continuity_ok_but_flash_coding_flagged,
        test_read_only_cannot_have_leased_paths,
        test_closeout_requires_terminal_lane_and_proof,
        test_closeout_blocks_non_terminal_lane,
        test_packet_missing_from_lane_register,
        test_project_artifact_is_coerced_to_packet,
        test_raw_model_free_project_artifact_passes_without_invented_model,
        test_specialist_strict_matrix,
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
