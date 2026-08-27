from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import cron_contract_validator as ccv


def sample_job() -> dict:
    return {
        "id": "job-1",
        "name": "Ops - Sample",
        "enabled": True,
        "description": "sample",
        "schedule": {"cron": "0 * * * *"},
        "payload": {
            "message": "run",
            "model": "openai/gpt-5.4",
            "thinking": "high",
            "timeoutSeconds": 300,
            "lightContext": False,
        },
        "failureAlert": {"after": 1, "mode": "announce"},
    }


def test_compare_contract_ok() -> None:
    contract = {
        "name": "Ops - Sample",
        "enabled": True,
        "payload": {"model": "openai/gpt-5.4", "thinking": "high", "timeoutSeconds": 300},
    }
    result = ccv.compare_contract(contract, sample_job())
    assert result["status"] == "ok"
    assert result["drift"] == []


def test_compare_contract_reports_payload_drift() -> None:
    contract = {
        "name": "Ops - Sample",
        "payload": {"model": "openai/gpt-5.5", "thinking": "high"},
    }
    result = ccv.compare_contract(contract, sample_job())
    assert result["status"] == "drift"
    assert result["drift"][0]["field"] == "payload.model"


def test_compare_contract_supports_nested_delivery_fields() -> None:
    job = sample_job()
    job["delivery"] = {"mode": "none", "bestEffort": True}
    contract = {
        "name": "Ops - Sample",
        "delivery": {"mode": "last", "bestEffort": True},
        "compare_fields": ["delivery.mode", "delivery.bestEffort"],
    }
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "drift"
    assert result["drift"] == [{"field": "delivery.mode", "expected": "last", "actual": "none"}]


def test_missing_live_job_respects_required_flag() -> None:
    result = ccv.compare_contract({"name": "Missing", "required": False}, None)
    assert result["status"] == "missing_live_job"
    assert result["severity"] == "warning"


def test_find_live_job_by_name() -> None:
    assert ccv.find_live_job({"name": "Ops - Sample"}, [sample_job()])["id"] == "job-1"


def test_compare_contract_reports_prompt_bloat() -> None:
    job = sample_job()
    job["payload"]["message"] = "x" * 10
    contract = {"name": "Ops - Sample", "payload": {"message": "x" * 10}}
    result = ccv.compare_contract(contract, job, max_prompt_chars=5)
    assert result["status"] == "ok"
    assert result["prompt_bloat"][0]["source"] == "expected"


def test_compare_contract_detects_multiline_truncation() -> None:
    job = sample_job()
    job["payload"]["message"] = "first line"
    contract = {"name": "Ops - Sample", "payload": {"message": "first line\nsecond line"}}
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "drift"
    assert result["multiline_live_intact"] is False


def test_compare_contract_blocks_unsupported_fable_route() -> None:
    job = sample_job()
    job["payload"]["model"] = "claude-cli/claude-fable-5"
    contract = {"name": "Ops - Sample", "payload": {"model": "claude-cli/claude-fable-5"}}
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "unsupported_model"
    assert result["severity"] == "error"
    assert result["unsupported_model_routes"][0]["model"] == "claude-cli/claude-fable-5"


def test_compare_contract_blocks_quiet_only_agentturn_prompt() -> None:
    message = (
        "QUIET CRON OUTPUT RULE (hard): this job uses delivery.mode=none. "
        "When the success/no-action path says NO_REPLY, your entire final response must be exactly NO_REPLY."
    )
    job = sample_job()
    job["payload"]["kind"] = "agentTurn"
    job["payload"]["message"] = message
    contract = {"name": "Ops - Sample", "payload": {"kind": "agentTurn", "message": message}}
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "prompt_integrity_error"
    assert result["severity"] == "error"
    assert result["prompt_integrity_findings"][0]["issue"] == "quiet_only_agentturn_prompt"


def test_prompt_integrity_allows_quiet_rule_with_task_body() -> None:
    job = sample_job()
    job["payload"]["kind"] = "agentTurn"
    job["payload"]["message"] = (
        "QUIET CRON OUTPUT RULE (hard): reply exactly NO_REPLY on success.\n\n"
        "Work in C:\\Users\\Veritas\\.openclaw\\workspace.\n"
        "Objective: run proof.\n"
        "Execute exactly: python scripts\\sample.py --write --validate"
    )
    assert ccv.prompt_integrity_findings(job, source="live") == []


def build_args(contract_dir: Path, live_file: Path) -> argparse.Namespace:
    return argparse.Namespace(
        contract_dir=contract_dir,
        live_file=live_file,
        contract=None,
        max_prompt_chars=ccv.DEFAULT_MAX_PROMPT_CHARS,
        max_message_lines=ccv.DEFAULT_MAX_MESSAGE_LINES,
        require_contracts=True,
        fail_on_drift=True,
        fail_on_prompt_bloat=False,
    )


def test_summary_reports_detected_routes_separately_from_configured_denylist() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        contract_dir = root / "contracts"
        contract_dir.mkdir()
        contract_path = contract_dir / "sample.json"
        live_path = root / "live.json"
        contract = {
            "job_id": "job-1",
            "name": "Ops - Sample",
            "payload": {"model": "openai/gpt-5.4", "thinking": "high", "timeoutSeconds": 300},
        }
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        live_path.write_text(json.dumps({"jobs": [sample_job()]}), encoding="utf-8")
        clean = ccv.build_payload(build_args(contract_dir, live_path))
        assert clean["summary"]["unsupported_model_route_count"] == 0
        assert clean["summary"]["unsupported_model_routes"] == []
        assert clean["summary"]["configured_unsupported_model_routes"] == sorted(ccv.UNSUPPORTED_MODEL_ROUTES)

        contract["payload"]["model"] = "claude-cli/claude-fable-5"
        live = sample_job()
        live["payload"]["model"] = "claude-cli/claude-fable-5"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        live_path.write_text(json.dumps({"jobs": [live]}), encoding="utf-8")
        detected = ccv.build_payload(build_args(contract_dir, live_path))
        routes = detected["summary"]["unsupported_model_routes"]
        assert detected["summary"]["unsupported_model_route_count"] == len(routes) == 1
        assert routes[0]["model"] == "claude-cli/claude-fable-5"
        assert routes[0]["detection_count"] == 2
        assert routes[0]["sources"] == ["contract", "live"]


if __name__ == "__main__":
    test_compare_contract_ok()
    test_compare_contract_reports_payload_drift()
    test_compare_contract_supports_nested_delivery_fields()
    test_missing_live_job_respects_required_flag()
    test_find_live_job_by_name()
    test_compare_contract_reports_prompt_bloat()
    test_compare_contract_detects_multiline_truncation()
    test_compare_contract_blocks_unsupported_fable_route()
    test_compare_contract_blocks_quiet_only_agentturn_prompt()
    test_prompt_integrity_allows_quiet_rule_with_task_body()
    test_summary_reports_detected_routes_separately_from_configured_denylist()
    print("ok")
