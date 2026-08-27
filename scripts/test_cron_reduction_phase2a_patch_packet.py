#!/usr/bin/env python3
from __future__ import annotations

import cron_reduction_phase2a_patch_packet as packet


def stub_runner_ok(path) -> dict:
    return {
        "status": "ok",
        "validation": {"status": "ok"},
        "operator_action": "NO_REPLY",
        "generated_at_utc": "2026-06-22T23:49:01Z",
        "elapsed_seconds": 2.0,
    }


def component(name: str, status: str = "ok", safe: bool = True) -> dict:
    return {
        "name": name,
        "status": status,
        "validation_status": "ok" if status == "ok" else "blocked",
        "safe_to_disable_source_jobs": safe,
        "generated_at_utc": "2026-06-22T23:49:01Z",
    }


def source_job(job_id: str, name: str) -> dict:
    return {
        "id": job_id,
        "name": name,
        "enabled": True,
        "schedule": {"kind": "cron", "expr": "1 2 * * 1-5", "tz": "America/Phoenix"},
    }


def contract(contract_id: str, replacement: str, sources: list[dict]) -> dict:
    return {
        "id": contract_id,
        "replacement_job_name": replacement,
        "runner_command": "python scripts\\example_runner.py --write --write-md --validate",
        "hard_timeout_seconds": 600,
        "source_jobs": [job["name"] for job in sources],
        "source_jobs_found": sources,
        "disable_gate": "fresh proof required",
    }


def inventory(replacement_exists: bool = False) -> dict:
    postclose_sources = [
        source_job("paper-refresh-id", "Finance - WF63/WF67 Paper Position Read-Only Refresh"),
        source_job("shadow-recon-id", "Finance - WF86 Daily Shadow and Paper Reconciliation"),
    ]
    wf68_sources = [
        source_job("wf68-producer-id", "Finance - WF68 Intraday Alert Producer"),
        source_job("wf68-digest-id", "Finance - WF68 Grouped Alert Digest Handoff"),
    ]
    enabled_jobs = postclose_sources + wf68_sources
    if replacement_exists:
        enabled_jobs.append(source_job("replacement-id", "Finance - WF68 Alert Producer and Digest"))
    return {
        "summary": {"total_jobs": 81, "enabled_jobs": 47, "disabled_jobs": 34},
        "enabled_jobs": enabled_jobs,
        "disabled_jobs": [],
        "contracts": [
            contract(
                "phase2_postclose_paper_reconciliation",
                "Finance - Post-Close Paper State Reconciliation",
                postclose_sources,
            ),
            contract(
                "phase2_wf68_alert_digest",
                "Finance - WF68 Alert Producer and Digest",
                wf68_sources,
            ),
        ],
    }


def phase2(postclose_status: str = "ok", wf68_status: str = "ok") -> dict:
    return {
        "status": "blocked",
        "validation": {"status": "blocked"},
        "components": [
            component("postclose_paper_reconciliation", postclose_status, postclose_status == "ok"),
            component("wf68_alert_digest", wf68_status, wf68_status == "ok"),
            component("morning_market_paper", "blocked", False),
            component("midday_market_paper", "blocked", False),
        ],
    }


def test_phase2a_packet_is_review_only_and_counts_savings() -> None:
    original_load_json = packet.load_json
    packet.load_json = stub_runner_ok
    try:
        payload = packet.build_payload(inventory(), phase2())
    finally:
        packet.load_json = original_load_json


    assert payload["status"] == "ok"
    assert payload["authority_boundary"]["cron_schedule_mutation_allowed"] is False
    assert payload["authority_boundary"]["job_add_disable_delete_allowed"] is False
    assert payload["phase2a_patch_summary"]["replacement_jobs_to_create"] == 2
    assert payload["phase2a_patch_summary"]["source_jobs_to_disable"] == 4
    assert payload["phase2a_patch_summary"]["expected_net_enabled_savings"] == 2
    assert payload["phase2a_patch_summary"]["projected_enabled_jobs_after_patch"] == 45


def test_blocked_component_blocks_packet() -> None:
    original_load_json = packet.load_json
    packet.load_json = stub_runner_ok
    try:
        payload = packet.build_payload(inventory(), phase2(postclose_status="blocked"))
    finally:
        packet.load_json = original_load_json

    assert payload["status"] == "error"
    assert any("phase2_postclose_paper_reconciliation:component_status_not_ok" in error for error in payload["validation"]["errors"])


def test_existing_replacement_blocks_packet() -> None:
    original_load_json = packet.load_json
    packet.load_json = stub_runner_ok
    try:
        payload = packet.build_payload(inventory(replacement_exists=True), phase2())
    finally:
        packet.load_json = original_load_json

    assert payload["status"] == "error"
    assert "phase2_wf68_alert_digest:replacement_job_already_exists" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_phase2a_packet_is_review_only_and_counts_savings()
    test_blocked_component_blocks_packet()
    test_existing_replacement_blocks_packet()
    print("ok")
