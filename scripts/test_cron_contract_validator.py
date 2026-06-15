from __future__ import annotations

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


if __name__ == "__main__":
    test_compare_contract_ok()
    test_compare_contract_reports_payload_drift()
    test_compare_contract_supports_nested_delivery_fields()
    test_missing_live_job_respects_required_flag()
    test_find_live_job_by_name()
    print("ok")
