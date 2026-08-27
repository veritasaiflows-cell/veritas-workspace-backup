#!/usr/bin/env python3
"""Focused tests for cron_predispatch_payload_restore.py."""

from __future__ import annotations

import cron_predispatch_payload_restore as restore


def test_quiet_only_detection() -> None:
    job = {
        "payload": {
            "kind": "agentTurn",
            "message": restore.QUIET_ONLY_PREFIX + " exact NO_REPLY",
        }
    }
    assert restore.is_quiet_only_agent_turn(job) is True
    assert restore.is_quiet_only_agent_turn({"payload": {"kind": "command"}}) is False


def test_desired_payload_is_command() -> None:
    spec = restore.SPECS[0]
    payload = restore.desired_payload(spec)
    assert payload["kind"] == "command"
    assert payload["argv"][0] == "python"
    assert "--skip-if-unchanged" in payload["argv"]
    assert payload["timeoutSeconds"] == spec.timeout_seconds


def test_contract_uses_command_compare_fields() -> None:
    spec = next(item for item in restore.SPECS if item.name == "Finance - WF78 Daily Freshness and Promotion Proof")
    live_job = {
        "id": "abc",
        "enabled": True,
        "deleteAfterRun": False,
        "schedule": {"kind": "cron", "expr": "1 2 * * *", "tz": "America/Phoenix"},
        "sessionTarget": "isolated",
        "wakeMode": "now",
        "delivery": {"mode": "none", "bestEffort": True},
        "failureAlert": {"after": 1, "mode": "announce"},
    }
    contract = restore.build_contract(spec, live_job)
    assert contract["payload"]["kind"] == "command"
    assert "payload.argv" in contract["compare_fields"]
    assert "payload.message" not in contract["compare_fields"]
    assert "deleteAfterRun" in contract["compare_fields"]
    assert contract["authority_boundary"]["agent_turn_model_spawn_required"] is False
    assert contract["failureAlert"]["after"] == 1


def test_delete_after_run_compare_is_omitted_when_live_omits_it() -> None:
    spec = restore.SPECS[0]
    live_job = {
        "id": "abc",
        "enabled": True,
        "schedule": {"kind": "cron", "expr": "1 2 * * *", "tz": "America/Phoenix"},
        "sessionTarget": "isolated",
        "wakeMode": "now",
        "delivery": {"mode": "none", "bestEffort": True},
    }
    contract = restore.build_contract(spec, live_job)
    assert "deleteAfterRun" not in contract["compare_fields"]


def test_otel_payload_uses_nonblocking_domain_exit_flag() -> None:
    spec = next(item for item in restore.SPECS if item.name == "Ops - OTEL Local Digest")
    payload = restore.desired_payload(spec)

    assert "--validate" in payload["argv"]
    assert "--cron-nonblocking-domain-exit" in payload["argv"]


def main() -> int:
    test_quiet_only_detection()
    test_desired_payload_is_command()
    test_contract_uses_command_compare_fields()
    test_otel_payload_uses_nonblocking_domain_exit_flag()
    print("cron_predispatch_payload_restore_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
