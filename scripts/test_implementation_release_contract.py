#!/usr/bin/env python3
from __future__ import annotations

import implementation_release_contract as irc


TEST_PROOF_FRESHNESS = {
    "source_mtime_ns": 100,
    "artifact_mtime_ns": 200,
}


def build_test_payload(**kwargs: object) -> dict:
    kwargs.setdefault("proof_freshness_test_metadata", TEST_PROOF_FRESHNESS)
    return irc.build_payload(**kwargs)


def clean_cron_artifact() -> dict:
    return {
        "status": "ok",
        "summary": {
            "drift_count": 0,
            "missing_live_job_count": 0,
            "unsupported_model_route_count": 0,
            "contract_prompt_integrity_error_count": 0,
            "live_prompt_integrity_error_count": 0,
            "prompt_bloat_count": 0,
            "multiline_truncation_risk_count": 0,
        },
        "sources": {"live": {"ok": True}},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def clean_go_artifacts() -> dict:
    return {
        "go_binary": {"status": "ok", "validation": {"status": "ok", "errors": [], "warnings": []}},
        "go_fast": {
            "status": "ok",
            "profile": "implementation",
            "summary": {"failed_count": 0, "critical_count": 0, "warning_count": 0},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    }


def clean_warning_residue_artifact(class_counts: dict[str, int] | None = None) -> dict:
    return {
        "status": "ok",
        "summary": {
            "critical": 0,
            "warnings": 0,
            "unclassified_count": 0,
            "critical_finding_count": 0,
            "class_counts": class_counts or {},
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def clean_manifest() -> dict:
    return {
        "schema": "veritas.producer_consumer_contracts.v1",
        "status": "ok",
        "summary": {
            "producer_count": 7,
            "required_surface_families": [
                "cron_contracts",
                "provider_failure_policy",
                "pm_queue",
                "source_lineage",
                "closeout",
                "go_validators",
                "finance_proof",
            ],
            "final_proof_after_last_producer": True,
        },
        "producers": {
            "cron_contracts": {},
            "provider_failure_policy": {},
            "pm_queue": {},
            "source_lineage": {},
            "closeout": {},
            "go_validators": {},
            "finance_proof": {},
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def clean_provider_artifact() -> dict:
    return {
        "status": "ok",
        "summary": {
            "target_count": 4,
            "ok_count": 4,
            "error_count": 0,
            "cached_overlay_count": 0,
            "provider_warning_count": 0,
            "proposal_count": 0,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def clean_pm_artifacts() -> dict:
    return {
        "pm_control": {
            "status": "ok",
            "summary": {"implementation_queue": {
                "job_count": 1,
                "ready_job_count": 1,
                "owner_decision_job_count": 0,
                "blocked_job_count": 0,
                "completed_by_ledger_job_count": 0,
                "active_job_count": 1,
                "top_ready_job_id": "pm-ready-job",
            }},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "pm_queue": {
            "status": "ok",
            "summary": {
                "job_count": 1,
                "ready_job_count": 1,
                "owner_decision_job_count": 0,
                "blocked_job_count": 0,
                "completed_by_ledger_job_count": 0,
                "active_job_count": 1,
                "top_ready_job_id": "pm-ready-job",
            },
            "jobs": [{"job_id": "pm-ready-job", "status": "ready"}],
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "pm_handoff": {
            "status": "ready_for_main_session",
            "summary": {"selected_job_id": "pm-ready-job"},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    }


def clean_skill_guard_artifact() -> dict:
    return {
        "status": "warning",
        "summary": {
            "critical_count": 0,
            "live_error_count": 0,
            "live_warning_count": 1,
            "pair_status": None,
        },
        "validation": {"status": "warning", "errors": [], "warnings": ["sqlite_skill_missing_h1"]},
    }


def active_lane_register() -> dict:
    return {
        "status": "ok",
        "lanes": [
            {
                "lane_id": "RUNTIME::TEST::lane",
                "status": "running",
                "allowed_writes": [
                    "scripts/implementation_release_contract.py",
                    "scripts/go/*",
                    "tmp/go-fast-proof-validators.json",
                ],
            }
        ],
        "summary": {"active_lane_count": 1},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def test_cron_contract_path_requires_live_roundtrip_gate() -> None:
    payload = build_test_payload(
        paths=["state/cron-contracts/sample.json"],
        phase="advisory",
        artifact_overrides={"cron_contract": clean_cron_artifact(), "producer_manifest": clean_manifest()},
    )
    assert "cron_contracts" in payload["surfaces"]
    assert "cron_runtime_roundtrip" in payload["surfaces"]
    gate = next(item for item in payload["release_gates"] if item["name"] == "cron_live_roundtrip_clean")
    assert gate["required"] is True
    assert gate["ok"] is True
    assert any("cron_contract_validator.py" in item["command"] for item in payload["required_commands"])


def test_cron_prompt_bloat_keeps_release_not_ready() -> None:
    cron = clean_cron_artifact()
    cron["summary"]["prompt_bloat_count"] = 1
    payload = build_test_payload(paths=["state/cron-contracts/sample.json"], artifact_overrides={"cron_contract": cron, "producer_manifest": clean_manifest()})
    assert payload["summary"]["ready_to_close"] is False
    gate = next(item for item in payload["release_gates"] if item["name"] == "cron_live_roundtrip_clean")
    assert gate["ok"] is False


def test_cron_unsupported_model_route_blocks_release() -> None:
    cron = clean_cron_artifact()
    cron["summary"]["unsupported_model_route_count"] = 1
    payload = build_test_payload(
        paths=["state/cron-contracts/sample.json"],
        artifact_overrides={"cron_contract": cron, "producer_manifest": clean_manifest()},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "cron_live_roundtrip_clean")
    assert gate["ok"] is False
    assert gate["detail"]["hard_error_counts"]["unsupported_model_route_count"] == 1


def test_cron_prompt_integrity_error_blocks_release() -> None:
    for field in ("contract_prompt_integrity_error_count", "live_prompt_integrity_error_count"):
        cron = clean_cron_artifact()
        cron["summary"][field] = 1
        payload = build_test_payload(
            paths=["state/cron-contracts/sample.json"],
            artifact_overrides={"cron_contract": cron, "producer_manifest": clean_manifest()},
        )
        gate = next(item for item in payload["release_gates"] if item["name"] == "cron_live_roundtrip_clean")
        assert gate["ok"] is False
        assert gate["detail"]["hard_error_counts"][field] == 1


def test_cron_multiline_mismatch_blocks_release() -> None:
    cron = clean_cron_artifact()
    cron["summary"]["multiline_truncation_risk_count"] = 1
    payload = build_test_payload(
        paths=["state/cron-contracts/sample.json"],
        artifact_overrides={"cron_contract": cron, "producer_manifest": clean_manifest()},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "cron_live_roundtrip_clean")
    assert gate["ok"] is False
    assert gate["detail"]["hard_error_counts"]["multiline_truncation_risk_count"] == 1


def test_cron_validator_non_ok_blocks_release() -> None:
    for location in ("status", "validation"):
        cron = clean_cron_artifact()
        if location == "status":
            cron["status"] = "warning"
        else:
            cron["validation"]["status"] = "warning"
        payload = build_test_payload(
            paths=["state/cron-contracts/sample.json"],
            artifact_overrides={"cron_contract": cron, "producer_manifest": clean_manifest()},
        )
        gate = next(item for item in payload["release_gates"] if item["name"] == "cron_live_roundtrip_clean")
        assert gate["ok"] is False


def test_unknown_warning_blocks_blocking_phase() -> None:
    payload = build_test_payload(
        paths=["scripts/go/internal/example/example.go"],
        phase="blocking",
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "go_binary": {"status": "ok", "validation": {"status": "ok", "errors": [], "warnings": []}},
            "go_fast": {"status": "ok", "summary": {"failed_count": 0, "critical_count": 0}, "validation": {"status": "warning", "warnings": ["mystery residue"]}},
        },
    )
    assert payload["status"] == "blocked"
    assert payload["summary"]["unknown_warning_count"] >= 1
    assert "unknown_warning:go_fast" in payload["validation"]["errors"]


def test_provider_rate_limit_warning_is_classified() -> None:
    assert irc.classify_warning("earnings provider rate limit; no-op with zero proposals") == "provider_unavailable_noop"


def test_main_session_escalation_residue_is_monitor_only() -> None:
    assert irc.classify_warning("main_session_escalation_consumer_unresolved_residue") == "monitor_only"


def test_main_session_greenkeeper_warning_status_is_monitor_only() -> None:
    assert irc.classify_warning("main_session_greenkeeper_status:warning") == "monitor_only"


def test_source_lineage_requires_post_producer_proof() -> None:
    payload = build_test_payload(
        paths=["scripts/sql_source_lineage_artifact_registry_repair.py"],
        artifact_overrides={
            **clean_go_artifacts(),
            "producer_manifest": clean_manifest(),
            "source_freshness": {
                "status": "ok",
                "summary": {"hash_mismatch_count": 0},
                "validation": {"status": "ok", "warnings": []},
            },
            "source_producer": {
                "status": "ok",
                "summary": {"hash_drift_count": 0, "registry_gap_count": 0},
                "validation": {"status": "ok", "warnings": []},
            },
            "warning_residue": clean_warning_residue_artifact(),
        },
    )
    assert "source_lineage" in payload["surfaces"]
    gate = next(item for item in payload["release_gates"] if item["name"] == "source_lineage_post_producer_clean")
    assert gate["required"] is True
    assert gate["ok"] is True
    assert "post_producer_source_lineage_proof" in payload["finalization_order"]


def test_source_lineage_allows_classified_source_freshness_residue() -> None:
    payload = build_test_payload(
        paths=["scripts/sql_source_lineage_artifact_registry_repair.py"],
        artifact_overrides={
            **clean_go_artifacts(),
            "producer_manifest": clean_manifest(),
            "source_freshness": {
                "status": "warning",
                "summary": {
                    "critical": 0,
                    "warnings": 3,
                    "hash_mismatch_count": 0,
                    "missing_source_artifact_row_count": 0,
                    "stale_artifact_count": 3,
                    "blocked_source_status_count": 0,
                    "forbidden_authority_status_count": 0,
                },
                "validation": {"status": "warning", "warnings": ["source_generated_at_fresh"]},
            },
            "source_producer": {
                "status": "ok",
                "summary": {"hash_drift_count": 0, "registry_gap_count": 0},
                "validation": {"status": "ok", "warnings": []},
            },
            "warning_residue": clean_warning_residue_artifact({"source_artifact_freshness_residue": 3}),
        },
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "source_lineage_post_producer_clean")
    assert gate["ok"] is True


def test_source_lineage_allows_classified_source_hash_drift_residue() -> None:
    payload = build_test_payload(
        paths=["scripts/sql_source_lineage_artifact_registry_repair.py"],
        artifact_overrides={
            **clean_go_artifacts(),
            "producer_manifest": clean_manifest(),
            "source_freshness": {
                "status": "warning",
                "summary": {
                    "critical": 0,
                    "warnings": 4,
                    "hash_mismatch_count": 4,
                    "missing_source_artifact_row_count": 0,
                    "stale_artifact_count": 0,
                    "blocked_source_status_count": 0,
                    "forbidden_authority_status_count": 0,
                },
                "validation": {"status": "warning", "warnings": ["source_artifact_hash_matches_lineage"]},
            },
            "source_producer": {
                "status": "ok",
                "summary": {"source_artifact_drift_count": 4, "registry_gap_count": 0},
                "validation": {"status": "ok", "warnings": []},
            },
            "warning_residue": clean_warning_residue_artifact({"source_artifact_hash_drift": 4}),
        },
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "source_lineage_post_producer_clean")
    assert gate["ok"] is True


def test_source_lineage_blocks_unclassified_source_freshness_residue() -> None:
    warning_residue = clean_warning_residue_artifact()
    warning_residue["summary"]["unclassified_count"] = 1
    payload = build_test_payload(
        paths=["scripts/sql_source_lineage_artifact_registry_repair.py"],
        phase="blocking",
        artifact_overrides={
            **clean_go_artifacts(),
            "producer_manifest": clean_manifest(),
            "source_freshness": {
                "status": "warning",
                "summary": {
                    "critical": 0,
                    "warnings": 1,
                    "hash_mismatch_count": 0,
                    "missing_source_artifact_row_count": 0,
                    "stale_artifact_count": 1,
                    "blocked_source_status_count": 0,
                    "forbidden_authority_status_count": 0,
                },
                "validation": {"status": "warning", "warnings": ["source_generated_at_fresh"]},
            },
            "source_producer": {
                "status": "ok",
                "summary": {"hash_drift_count": 0, "registry_gap_count": 0},
                "validation": {"status": "ok", "warnings": []},
            },
            "warning_residue": warning_residue,
        },
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "source_lineage_post_producer_clean")
    assert gate["ok"] is False
    assert "missing_gate:source_lineage_post_producer_clean" in payload["validation"]["errors"]


def test_provider_unavailable_zero_proposals_is_clean_noop() -> None:
    provider = clean_provider_artifact()
    provider["status"] = "warning"
    provider["validation"]["status"] = "warning"
    provider["validation"]["warnings"] = ["provider rate limit; no-op with zero proposals"]
    payload = build_test_payload(
        paths=["scripts/event_calendar_provider.py"],
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "earnings_calendar": provider,
            "post_close_quote_ledger": clean_provider_artifact(),
        },
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "provider_failure_policy_clean")
    assert gate["required"] is True
    assert gate["ok"] is True


def test_provider_unavailable_with_proposals_blocks() -> None:
    provider = clean_provider_artifact()
    provider["status"] = "warning"
    provider["summary"]["proposal_count"] = 1
    provider["validation"]["status"] = "warning"
    provider["validation"]["warnings"] = ["provider unavailable while mutation proposal is staged"]
    payload = build_test_payload(
        paths=["scripts/event_calendar_provider.py"],
        phase="blocking",
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "earnings_calendar": provider,
            "post_close_quote_ledger": clean_provider_artifact(),
        },
    )
    assert payload["status"] == "blocked"
    assert "missing_gate:provider_failure_policy_clean" in payload["validation"]["errors"]


def test_cached_complete_overlay_is_review_clean() -> None:
    provider = clean_provider_artifact()
    provider["summary"].update({"target_count": 3, "ok_count": 3, "cached_overlay_count": 3, "error_count": 0})
    payload = build_test_payload(
        paths=["scripts/post_close_final_quote_ledger.py"],
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "earnings_calendar": clean_provider_artifact(),
            "post_close_quote_ledger": provider,
        },
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "provider_failure_policy_clean")
    assert gate["ok"] is True


def test_complete_provider_success_with_partial_cached_overlay_is_review_clean() -> None:
    provider = clean_provider_artifact()
    provider["status"] = "warning"
    provider["summary"].update({
        "target_count": 130,
        "ok_count": 130,
        "cached_overlay_count": 38,
        "error_count": 0,
        "provider_warning_count": 38,
    })
    provider["validation"]["warnings"] = ["cached overlay used for stale provider rows"]
    payload = build_test_payload(
        paths=["scripts/post_close_final_quote_ledger.py"],
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "earnings_calendar": clean_provider_artifact(),
            "post_close_quote_ledger": provider,
        },
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "provider_failure_policy_clean")
    assert gate["ok"] is True


def test_cached_incomplete_overlay_blocks() -> None:
    provider = clean_provider_artifact()
    provider["summary"].update({"target_count": 3, "ok_count": 2, "cached_overlay_count": 3, "error_count": 1})
    payload = build_test_payload(
        paths=["scripts/post_close_final_quote_ledger.py"],
        phase="blocking",
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "earnings_calendar": clean_provider_artifact(),
            "post_close_quote_ledger": provider,
        },
    )
    assert "missing_gate:provider_failure_policy_clean" in payload["validation"]["errors"]


def test_pm_handoff_cannot_select_ledger_completed_job() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 1,
        "ready_job_count": 0,
        "completed_by_ledger_job_count": 1,
        "active_job_count": 0,
        "top_ready_job_id": "",
        "top_completed_job_id": "pm-done-job",
    })
    pm["pm_queue"]["jobs"] = [{"job_id": "pm-done-job", "status": "completed_by_ledger_resolved"}]
    pm["pm_handoff"]["summary"] = {"selected_job_id": "pm-done-job"}
    payload = build_test_payload(
        paths=["scripts/pm_main_session_handoff.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    assert "missing_gate:pm_queue_authority_current" in payload["validation"]["errors"]


def test_pm_quiet_success_requires_no_ready_work() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 1,
        "ready_job_count": 0,
        "completed_by_ledger_job_count": 1,
        "active_job_count": 0,
        "top_ready_job_id": "",
        "top_completed_job_id": "pm-done-job",
    })
    pm["pm_queue"]["jobs"] = [{"job_id": "pm-done-job", "status": "completed_by_ledger_resolved"}]
    pm["pm_handoff"]["status"] = "quiet_success"
    pm["pm_handoff"]["summary"] = {}
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True


def test_pm_ready_handoff_without_selected_job_is_clean_when_queue_drained() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 1,
        "ready_job_count": 0,
        "completed_by_ledger_job_count": 1,
        "active_job_count": 0,
        "top_ready_job_id": "",
        "top_completed_job_id": "pm-done-job",
    })
    pm["pm_queue"]["jobs"] = [{"job_id": "pm-done-job", "status": "completed_by_ledger_resolved"}]
    pm["pm_handoff"]["status"] = "ready_for_main_session"
    pm["pm_handoff"]["summary"] = {"selected_action": "non_queue_handoff"}
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True
    assert gate["detail"]["drained_clean"] is True


def test_pm_review_only_queue_blocker_does_not_block_ready_handoff() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 2,
        "ready_job_count": 1,
        "blocked_job_count": 1,
        "active_job_count": 2,
        "top_ready_job_id": "pm-ready-job",
    })
    pm["pm_queue"]["jobs"] = [
        {"job_id": "pm-ready-job", "status": "ready_for_main_or_helper", "allowed_execution_mode": "main_review_only_proof_refresh", "closeout_mode": "pm_state"},
        {"job_id": "pm-review-blocked", "status": "blocked", "allowed_execution_mode": "main_session_review", "closeout_mode": "queue_only", "owner_gate_required": False},
    ]
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True
    assert gate["detail"]["blocked_job_count"] == 1
    assert gate["detail"]["blocking_blocked_job_count"] == 0
    assert gate["detail"]["review_only_blocked_job_count"] == 1


def test_pm_review_only_pm_state_and_handoff_blockers_do_not_block_ready_handoff() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 3,
        "ready_job_count": 1,
        "blocked_job_count": 2,
        "active_job_count": 3,
        "top_ready_job_id": "pm-ready-job",
    })
    pm["pm_queue"]["jobs"] = [
        {"job_id": "pm-ready-job", "status": "ready_for_main_or_helper", "allowed_execution_mode": "main_review_only_proof_refresh", "closeout_mode": "pm_state"},
        {"job_id": "pm-review-pm-state", "status": "blocked", "allowed_execution_mode": "main_session_review", "closeout_mode": "pm_state", "owner_gate_required": False},
        {"job_id": "pm-review-handoff", "status": "blocked", "allowed_execution_mode": "main_session_review", "closeout_mode": "handoff", "owner_gate_required": False},
    ]
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True
    assert gate["detail"]["blocked_job_count"] == 2
    assert gate["detail"]["blocking_blocked_job_count"] == 0
    assert gate["detail"]["review_only_blocked_job_count"] == 2


def test_pm_review_only_handoff_blocker_is_monitor_only_when_no_ready_work() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 1,
        "ready_job_count": 0,
        "blocked_job_count": 1,
        "completed_by_ledger_job_count": 0,
        "active_job_count": 1,
        "top_ready_job_id": "",
        "top_completed_job_id": "",
    })
    pm["pm_queue"]["jobs"] = [
        {
            "job_id": "pm-review-handoff",
            "status": "blocked",
            "allowed_execution_mode": "main_session_review",
            "closeout_mode": "handoff",
            "owner_gate_required": False,
        }
    ]
    pm["pm_handoff"]["status"] = "ready_for_main_session"
    pm["pm_handoff"]["summary"] = {"selected_action": "non_queue_handoff"}
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True
    assert gate["detail"]["review_only_drained_clean"] is True
    assert gate["detail"]["review_only_blocked_job_count"] == 1


def test_pm_executable_blocked_job_still_blocks() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 2,
        "ready_job_count": 1,
        "blocked_job_count": 1,
        "active_job_count": 2,
        "top_ready_job_id": "pm-ready-job",
    })
    pm["pm_queue"]["jobs"] = [
        {"job_id": "pm-ready-job", "status": "ready_for_main_or_helper", "allowed_execution_mode": "main_review_only_proof_refresh", "closeout_mode": "pm_state"},
        {"job_id": "pm-auto-blocked", "status": "blocked", "allowed_execution_mode": "auto_main_executable", "closeout_mode": "handoff", "owner_gate_required": False},
    ]
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is False
    assert gate["detail"]["blocking_blocked_job_count"] == 1
    assert "missing_gate:pm_queue_authority_current" in payload["validation"]["errors"]


def test_pm_recently_dispatched_non_queue_handoff_is_clean_when_queue_drained() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 1,
        "ready_job_count": 0,
        "completed_by_ledger_job_count": 1,
        "active_job_count": 0,
        "top_ready_job_id": "",
        "top_completed_job_id": "pm-done-job",
    })
    pm["pm_queue"]["jobs"] = [{"job_id": "pm-done-job", "status": "completed_by_ledger_resolved"}]
    pm["pm_handoff"]["status"] = "recently_dispatched"
    pm["pm_handoff"]["summary"] = {"selected_action": "non_queue_handoff"}
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True
    assert gate["detail"]["drained_clean"] is True


def test_pm_recently_dispatched_review_queue_is_monitor_only() -> None:
    pm = clean_pm_artifacts()
    pm["pm_queue"]["summary"].update({
        "job_count": 2,
        "ready_job_count": 1,
        "blocked_job_count": 1,
        "completed_by_ledger_job_count": 0,
        "active_job_count": 2,
        "top_ready_job_id": "pm-ready-job",
    })
    pm["pm_queue"]["jobs"] = [
        {"job_id": "pm-ready-job", "status": "ready_for_main_or_helper", "allowed_execution_mode": "main_review_only_proof_refresh", "closeout_mode": "pm_state"},
        {"job_id": "pm-review-blocked", "status": "blocked", "allowed_execution_mode": "main_session_review", "closeout_mode": "queue_only", "owner_gate_required": False},
    ]
    pm["pm_handoff"]["status"] = "recently_dispatched"
    pm["pm_handoff"]["summary"] = {"selected_action": "non_queue_handoff"}
    payload = build_test_payload(
        paths=["scripts/pm_control_packet.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **pm},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "pm_queue_authority_current")
    assert gate["ok"] is True
    assert gate["detail"]["recent_dispatch_clean"] is True
    assert gate["detail"]["review_only_blocked_job_count"] == 1


def test_go_source_change_requires_binary_freshness_proof() -> None:
    payload = build_test_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        artifact_overrides={"producer_manifest": clean_manifest(), **clean_go_artifacts()},
    )
    assert "go_validators" in payload["surfaces"]
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
    assert gate["required"] is True
    assert any("go_binary_freshness_guard.py" in item["command"] for item in payload["required_commands"])


def test_stale_go_proof_blocks_blocking_release() -> None:
    metadata = {
        "source_mtime_ns": 100,
        "artifact_mtime_ns": 200,
        "artifacts": {"go_fast": {"artifact_mtime_ns": 99}},
    }
    payload = irc.build_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **clean_go_artifacts()},
        proof_freshness_test_metadata=metadata,
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
    go_fast = next(item for item in gate["detail"]["proof_freshness"]["artifacts"] if item["artifact"] == "go_fast")
    assert gate["detail"]["content_ok_before_freshness"] is True
    assert go_fast["status"] == "stale"
    assert gate["ok"] is False
    assert payload["summary"]["stale_proof_artifact_count"] >= 1
    assert "missing_gate:go_implementation_proof_clean" in payload["validation"]["errors"]


def test_artifact_override_without_explicit_freshness_metadata_is_unproven() -> None:
    payload = irc.build_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **clean_go_artifacts()},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
    overridden_rows = [
        item
        for item in gate["detail"]["proof_freshness"]["artifacts"]
        if item["artifact"] in {"go_binary", "go_fast"}
    ]
    assert all(item["artifact_metadata_source"] == "override_metadata_required" for item in overridden_rows)
    assert all(item["status"] == "unproven" for item in overridden_rows)
    assert gate["ok"] is False


def test_go_warning_count_requires_explicit_residue_classification() -> None:
    artifacts = clean_go_artifacts()
    artifacts["go_fast"]["status"] = "warning"
    artifacts["go_fast"]["summary"]["warning_count"] = 1
    residue = clean_warning_residue_artifact()
    payload = build_test_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **artifacts, "warning_residue": residue},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
    assert gate["detail"]["go_warnings_classified"] is False
    assert gate["ok"] is False

    residue["summary"]["classified_warning_count"] = 1
    residue["summary"]["class_counts"] = {"source_artifact_freshness_residue": 1}
    classified = build_test_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        artifact_overrides={"producer_manifest": clean_manifest(), **artifacts, "warning_residue": residue},
    )
    classified_gate = next(item for item in classified["release_gates"] if item["name"] == "go_implementation_proof_clean")
    assert classified_gate["detail"]["go_warnings_classified"] is True
    assert classified_gate["ok"] is True


def test_post_residue_closeout_warning_does_not_require_pre_closeout_classification() -> None:
    artifacts = clean_go_artifacts()
    artifacts["go_fast"]["status"] = "warning"
    artifacts["go_fast"]["summary"].update({
        "warning_count": 2,
        "residue_classifiable_warning_count": 1,
        "post_residue_warning_count": 1,
    })
    residue = clean_warning_residue_artifact({"monitor_only": 1})
    residue["summary"]["classified_warning_count"] = 1
    residue["summary"]["warning_finding_count"] = 1
    payload = build_test_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **artifacts, "warning_residue": residue},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
    assert gate["detail"]["go_warning_partition_valid"] is True
    assert gate["detail"]["go_residue_classifiable_warning_count"] == 1
    assert gate["detail"]["go_post_residue_warning_count"] == 1
    assert gate["detail"]["go_warnings_classified"] is True
    assert gate["ok"] is True


def test_partial_or_inconsistent_warning_partition_fails_closed() -> None:
    for summary_update in (
        {"warning_count": 1, "residue_classifiable_warning_count": 1},
        {"warning_count": 1, "residue_classifiable_warning_count": 0, "post_residue_warning_count": 0},
        {"warning_count": 1, "residue_classifiable_warning_count": -1, "post_residue_warning_count": 2},
    ):
        artifacts = clean_go_artifacts()
        artifacts["go_fast"]["status"] = "warning"
        artifacts["go_fast"]["summary"].update(summary_update)
        payload = build_test_payload(
            paths=["scripts/go/internal/closeoutledger/lint.go"],
            phase="blocking",
            artifact_overrides={
                "producer_manifest": clean_manifest(),
                **artifacts,
                "warning_residue": clean_warning_residue_artifact({"monitor_only": 1}),
            },
        )
        gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
        assert gate["detail"]["go_warning_partition_valid"] is False
        assert gate["ok"] is False

    artifacts = clean_go_artifacts()
    artifacts["go_fast"]["status"] = "warning"
    artifacts["go_fast"]["summary"].update({
        "warning_count": 1,
        "residue_classifiable_warning_count": 1,
        "post_residue_warning_count": 0,
    })
    residue = clean_warning_residue_artifact({"monitor_only": 1})
    residue["summary"].update({"classified_warning_count": 1, "warning_finding_count": 0})
    payload = build_test_payload(
        paths=["scripts/go/internal/closeoutledger/lint.go"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **artifacts, "warning_residue": residue},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")
    assert gate["detail"]["go_warning_partition_valid"] is True
    assert gate["detail"]["go_warning_residue_count_matches"] is False
    assert gate["ok"] is False


def test_bundle_go_profile_cannot_satisfy_release_closeout() -> None:
    artifacts = clean_go_artifacts()
    artifacts["go_fast"]["profile"] = "bundle"
    payload = build_test_payload(
        paths=["scripts/go_fast_proof_validators.py"],
        phase="blocking",
        artifact_overrides={"producer_manifest": clean_manifest(), **artifacts},
    )
    gate = next(item for item in payload["release_gates"] if item["name"] == "go_implementation_proof_clean")

    assert gate["detail"]["go_fast_profile"] == "bundle"
    assert gate["ok"] is False


def test_skill_surface_requires_body_guard_proof() -> None:
    payload = build_test_payload(
        paths=["skills/example/SKILL.md"],
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "skill_workshop_body_guard": clean_skill_guard_artifact(),
        },
    )
    assert "skill_workshop_guard" in payload["surfaces"]
    gate = next(item for item in payload["release_gates"] if item["name"] == "skill_workshop_body_guard_clean")
    assert gate["required"] is True
    assert gate["ok"] is True
    assert any("skill_workshop_body_guard.py" in item["command"] for item in payload["required_commands"])
    assert "skill_workshop_body_guard" in payload["finalization_order"]


def test_skill_body_guard_critical_blocks_release() -> None:
    skill_guard = clean_skill_guard_artifact()
    skill_guard["summary"]["critical_count"] = 1
    payload = build_test_payload(
        paths=["skills/example/SKILL.md"],
        phase="blocking",
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "skill_workshop_body_guard": skill_guard,
        },
    )
    assert payload["status"] == "blocked"
    assert "missing_gate:skill_workshop_body_guard_clean" in payload["validation"]["errors"]


def test_advisory_warning_is_classified_monitor_only() -> None:
    assert irc.classify_warning("advisory residue retained for review context") == "monitor_only"


def test_generated_tmp_proof_artifacts_do_not_drive_surface_scope() -> None:
    assert irc.classify_path("tmp/go-sql-source-artifact-freshness-lint.json") == set()


def test_active_lane_allowed_writes_scope_overrides_dirty_workspace_route() -> None:
    payload = build_test_payload(
        paths=None,
        artifact_overrides={
            "producer_manifest": clean_manifest(),
            "lane_register": active_lane_register(),
            **clean_go_artifacts(),
        },
    )
    assert payload["surface_scope"]["source"] == "active_lane_allowed_writes"
    assert "go_validators" in payload["surfaces"]
    assert "source_lineage" not in payload["surfaces"]


if __name__ == "__main__":
    test_cron_contract_path_requires_live_roundtrip_gate()
    test_cron_prompt_bloat_keeps_release_not_ready()
    test_cron_unsupported_model_route_blocks_release()
    test_cron_prompt_integrity_error_blocks_release()
    test_cron_multiline_mismatch_blocks_release()
    test_cron_validator_non_ok_blocks_release()
    test_unknown_warning_blocks_blocking_phase()
    test_provider_rate_limit_warning_is_classified()
    test_main_session_escalation_residue_is_monitor_only()
    test_main_session_greenkeeper_warning_status_is_monitor_only()
    test_source_lineage_requires_post_producer_proof()
    test_source_lineage_allows_classified_source_freshness_residue()
    test_source_lineage_allows_classified_source_hash_drift_residue()
    test_source_lineage_blocks_unclassified_source_freshness_residue()
    test_provider_unavailable_zero_proposals_is_clean_noop()
    test_provider_unavailable_with_proposals_blocks()
    test_cached_complete_overlay_is_review_clean()
    test_cached_incomplete_overlay_blocks()
    test_pm_handoff_cannot_select_ledger_completed_job()
    test_pm_quiet_success_requires_no_ready_work()
    test_pm_ready_handoff_without_selected_job_is_clean_when_queue_drained()
    test_pm_review_only_queue_blocker_does_not_block_ready_handoff()
    test_pm_executable_blocked_job_still_blocks()
    test_pm_recently_dispatched_non_queue_handoff_is_clean_when_queue_drained()
    test_pm_recently_dispatched_review_queue_is_monitor_only()
    test_go_source_change_requires_binary_freshness_proof()
    test_stale_go_proof_blocks_blocking_release()
    test_artifact_override_without_explicit_freshness_metadata_is_unproven()
    test_go_warning_count_requires_explicit_residue_classification()
    test_post_residue_closeout_warning_does_not_require_pre_closeout_classification()
    test_partial_or_inconsistent_warning_partition_fails_closed()
    test_bundle_go_profile_cannot_satisfy_release_closeout()
    test_skill_surface_requires_body_guard_proof()
    test_skill_body_guard_critical_blocks_release()
    test_advisory_warning_is_classified_monitor_only()
    test_generated_tmp_proof_artifacts_do_not_drive_surface_scope()
    test_active_lane_allowed_writes_scope_overrides_dirty_workspace_route()
    print("implementation_release_contract_tests_passed")
