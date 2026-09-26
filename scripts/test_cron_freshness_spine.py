#!/usr/bin/env python3
"""Focused regressions for cron freshness spine warning classification."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cron_freshness_spine import (
    AUTHORITY_BOUNDARY,
    JOB_CONTRACTS,
    RETIRED_LEGACY_JOB_CONTRACTS,
    artifact_record,
    attention_bucket,
    attention_class,
    build_payload,
    classify_job,
    expected_warning_quiet,
    merged_job_contracts,
    router_lineage,
    schedule_kind,
    validate_payload,
)


def test_quote_first_warning_is_quiet_with_nonfresh_backlog() -> None:
    payload = {
        "status": "warning",
        "validation": {
            "status": "ok",
            "warnings": ["wf78_event_queue_keeps_fresh_quote_first"],
        },
        "summary": {
            "critical_count": 0,
            "missing_required_symbols": [],
            "nonfresh_snapshot_count": 21,
            "stale_or_missing_snapshot_count": 0,
        },
    }

    assert expected_warning_quiet(payload) is True


def test_quote_first_warning_does_not_quiet_stale_or_critical() -> None:
    critical_payload = {
        "status": "warning",
        "validation": {
            "status": "ok",
            "warnings": ["wf78_event_queue_keeps_fresh_quote_first"],
        },
        "summary": {
            "critical_count": 1,
            "missing_required_symbols": [],
            "nonfresh_snapshot_count": 0,
            "stale_or_missing_snapshot_count": 0,
        },
    }
    stale_payload = {
        "status": "warning",
        "validation": {
            "status": "ok",
            "warnings": ["wf78_event_queue_keeps_fresh_quote_first"],
        },
        "summary": {
            "critical_count": 0,
            "missing_required_symbols": [],
            "nonfresh_snapshot_count": 0,
            "stale_or_missing_snapshot_count": 1,
        },
    }

    assert expected_warning_quiet(critical_payload) is False
    assert expected_warning_quiet(stale_payload) is False


def test_no_reply_operator_action_is_not_handoff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trade-grade-os-freshness-cron-runner.json"
        path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "operator_action": "NO_REPLY",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "trade_grade_os_freshness_cron_runner",
                "path": str(path),
                "required": True,
            },
            default_freshness_hours=36,
        )

    assert record["operator_action"] == "NO_REPLY"
    assert record["main_handoff_semantic"] is False
    assert record["owner_decision_semantic"] is False


def test_cron_operator_ledger_warning_rollup_quiet_only_when_clean() -> None:
    payload = {
        "schema_version": 1,
        "status": "warning",
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": [],
            "warning_windows": ["morning", "post-close"],
        },
        "artifact_inventory": {
            "missing_required_roles": [],
            "critical_or_unreadable_roles": [],
        },
    }
    blocked_payload = {
        **payload,
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": ["post-close"],
            "warning_windows": ["morning"],
        },
    }

    assert expected_warning_quiet(payload) is True
    assert expected_warning_quiet(blocked_payload) is False


def test_pm_no_action_status_refresh_residue_is_quiet() -> None:
    payload = {
        "schema": "veritas.pm_autonomy_verifier.v1",
        "status": "warning",
        "summary": {"action_type": "no_action"},
        "validation": {
            "status": "ok",
            "warnings": ["status_packet_refresh_validation_residue"],
        },
    }

    assert expected_warning_quiet(payload) is True


def test_main_session_action_executor_no_action_warning_is_quiet() -> None:
    payload = {
        "schema": "veritas.main_session_action_executor.v1",
        "status": "warning",
        "summary": {
            "action_type": "no_action",
            "classification": "no_reply",
            "executed": False,
            "execution_failed": [],
        },
        "validation": {
            "status": "ok",
            "warnings": ["no_action_available"],
        },
    }
    blocked_payload = {
        **payload,
        "summary": {
            **payload["summary"],
            "execution_failed": ["pm_execution_loop"],
        },
    }

    assert expected_warning_quiet(payload) is True
    assert expected_warning_quiet(blocked_payload) is False


def test_pm_worker_ignores_stale_blocked_subordinate_execution_loop_when_parent_is_quiet() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        worker = tmp_path / "pm-job-worker-runner.json"
        loop = tmp_path / "pm-execution-loop.json"
        worker.write_text(
            json.dumps(
                {
                    "schema": "veritas.pm_job_worker_runner.v1",
                    "status": "quiet_success",
                    "generated_at_utc": now,
                    "summary": {
                        "action_type": "no_action",
                        "execution_failures": [],
                    },
                    "validation": {"status": "ok", "errors": [], "warnings": []},
                }
            ),
            encoding="utf-8",
        )
        loop.write_text(
            json.dumps(
                {
                    "schema": "veritas.pm_execution_loop.v1",
                    "status": "blocked",
                    "generated_at_utc": now,
                    "validation": {"status": "blocked", "errors": ["implementation_completion_ledger"]},
                }
            ),
            encoding="utf-8",
        )

        job = {
            "name": "PM - GPT-5.5 Auto Implementation Proof Runner",
            "enabled": True,
            "schedule": {"expr": "45 4,12,20 * * *", "kind": "cron", "tz": "America/Phoenix"},
            "last_status": "ok",
            "consecutive_errors": 0,
        }
        contract = {
            "owner_workflow": "test",
            "freshness_hours": 36,
            "expected_artifacts": [
                {"path": str(worker), "role": "pm_job_worker_runner", "required": True, "blocking": True},
                {"path": str(loop), "role": "pm_execution_loop", "required": True, "blocking": True},
            ],
        }

        classified = classify_job(job, contract)

    assert classified["status"] == "fresh"
    assert classified["signal_class"] == "NO_REPLY"
    loop_record = next(item for item in classified["expected_artifacts"] if item["role"] == "pm_execution_loop")
    assert loop_record["blocked_semantic"] is True
    assert loop_record["blocking"] is False


def test_status_card_cron_migration_self_loop_residue_is_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "veritas-status-card.json"
        path.write_text(
            json.dumps(
                {
                    "status": "critical",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {
                        "status": "critical",
                        "errors": ["wf74_pickup.missing_cron_migration_repair"],
                    },
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "veritas_status_card",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=36,
        )

    assert record["blocked_semantic"] is False
    assert record["authority_widened"] is False


def test_startup_brief_wf88_wiki_status_residue_is_not_main_dispatcher_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "startup-brief-packet.json"
        path.write_text(
            json.dumps(
                {
                    "status": "critical",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {
                        "status": "critical",
                        "errors": ["wf88_wiki_synthesis.validation_blocked"],
                    },
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "startup_brief_packet",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=36,
        )

    assert record["blocked_semantic"] is False
    assert record["authority_widened"] is False


def test_attention_class_separates_known_review_from_new_review() -> None:
    job = {
        "name": "Finance - Ticker Card Freshness Owner Runner",
        "signal_class": "MAIN_SESSION_REQUIRED",
        "status": "needs_review",
        "reason": "artifact_requests_or_warns_for_review",
    }
    previous_jobs = {
        job["name"]: {
            "signal_class": "MAIN_SESSION_REQUIRED",
            "status": "needs_review",
            "reason": "artifact_requests_or_warns_for_review",
        }
    }
    changed_previous = {
        job["name"]: {
            "signal_class": "NO_REPLY",
            "status": "fresh",
            "reason": "required_artifacts_fresh",
        }
    }

    assert attention_class(job, previous_jobs) == "known_monitor_only"
    assert attention_class(job, changed_previous) == "new_or_changed"


def test_known_review_uses_underlying_signal_when_prior_run_was_quieted() -> None:
    job = {
        "name": "Finance - Ticker Card Freshness Owner Runner",
        "signal_class": "MAIN_SESSION_REQUIRED",
        "status": "needs_review",
        "reason": "artifact_requests_or_warns_for_review",
        "underlying_signal_class": "MAIN_SESSION_REQUIRED",
        "underlying_status": "needs_review",
        "underlying_reason": "artifact_requests_or_warns_for_review",
    }
    previous_jobs = {
        job["name"]: {
            "signal_class": "NO_REPLY",
            "status": "standing_review_quiet",
            "reason": "standing_review_quiet",
            "underlying_signal_class": "MAIN_SESSION_REQUIRED",
            "underlying_status": "needs_review",
            "underlying_reason": "artifact_requests_or_warns_for_review",
        }
    }

    assert attention_class(job, previous_jobs) == "known_monitor_only"


def test_known_monitor_only_bucket_is_quiet_success() -> None:
    job = {
        "signal_class": "NO_REPLY",
        "standing_review_quiet": True,
    }

    assert attention_bucket(job) == "quiet_success"


def test_standing_review_quiet_removes_stable_review_from_attention_queue() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof = tmp_path / "review-proof.json"
        ledger = tmp_path / "cron-ledger.json"
        operating = tmp_path / "operating-spine.json"
        out = tmp_path / "cron-freshness-spine.json"
        proof.write_text(
            json.dumps({"status": "warning", "generated_at_utc": now, "validation": {"status": "ok", "warnings": ["review"]}}),
            encoding="utf-8",
        )
        ledger.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "id": "test-job",
                            "name": "Finance - Morning Control Digest Proof Refresh",
                            "enabled": True,
                            "schedule": {"expr": "12 7 * * 1-5", "kind": "cron", "tz": "America/Phoenix"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        operating.write_text(json.dumps({"implemented_phases": []}), encoding="utf-8")
        out.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "name": "Finance - Morning Control Digest Proof Refresh",
                            "signal_class": "MAIN_SESSION_REQUIRED",
                            "status": "needs_review",
                            "reason": "artifact_requests_or_warns_for_review",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        payload = build_payload(ledger, operating, out_path=out, job_contracts={
            "Finance - Morning Control Digest Proof Refresh": {
                "owner_workflow": "test",
                "freshness_hours": 36,
                "expected_artifacts": [{"path": str(proof), "role": "proof", "required": True, "blocking": True}],
            }
        })

    summary = payload["summary"]
    assert payload["status"] == "ok"
    assert summary["requires_attention_count"] == 0
    assert summary["review_queue_count"] == 0
    assert summary["standing_review_quiet_count"] == 1
    assert payload["jobs"][0]["standing_review_quiet"] is True


def test_paper_positions_blocked_packet_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "paper-positions.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "authority_boundary": {
                        "trade_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "paper_positions_state",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=36,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_wf87_runtime_blocked_packet_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf87-position-sizing-runtime-check.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf87_position_sizing_runtime_check",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=12,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_wf85_delivered_blocker_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf85-paper-deployment-telegram-cron-runner.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "operator_action": "TELEGRAM_BLOCKER_SENT",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf85_paper_deployment_telegram_cron_runner",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_paper_recommendation_blocked_card_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "morning-paper-deployment-recommendation-cards.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "summary": {
                        "candidate_count": 0,
                        "clean_approval_card_count": 0,
                        "next_safe_action": "Do not ask for approval yet; repair/freshness/posture blockers remain.",
                    },
                    "authority_boundary": {
                        "review_only": True,
                        "capital_deployment_allowed": False,
                        "trade_or_execution_allowed": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "morning_paper_deployment_recommendation_cards",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_wf78_owner_card_prep_no_rows_ok_no_work_is_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf78-owner-card-prep-loop.json"
        path.write_text(
            json.dumps(
                {
                    "status": "ok_no_work",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {
                        "status": "ok",
                        "warnings": ["no_capital_review_card_preparable_rows"],
                    },
                    "summary": {
                        "capital_review_rows": 0,
                        "owner_cards_written": 0,
                        "wf67_request_artifacts_written": 0,
                        "reducer_status": "ok",
                    },
                    "authority_boundary": {
                        "review_only": True,
                        "non_executing_owner_card_prep_allowed": True,
                        "capital_deployment_allowed": False,
                        "trade_or_execution_allowed": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf78_owner_card_prep_loop",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is False
    assert record["main_handoff_semantic"] is False
    assert record["authority_widened"] is False


def test_wf78_owner_card_prep_wf67_blocked_warning_is_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf78-owner-card-prep-loop.json"
        path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {
                        "status": "ok",
                        "warnings": ["wf67_request_generation_blocked_review_only:NVDA"],
                    },
                    "summary": {
                        "capital_review_rows": 1,
                        "owner_cards_written": 1,
                        "wf67_request_artifacts_written": 0,
                        "wf67_request_blocked_count": 1,
                        "reducer_status": "ok",
                    },
                    "authority_boundary": {
                        "review_only": True,
                        "non_executing_owner_card_prep_allowed": True,
                        "capital_deployment_allowed": False,
                        "trade_or_execution_allowed": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf78_owner_card_prep_loop",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is False
    assert record["main_handoff_semantic"] is False
    assert record["authority_widened"] is False


def test_wf85_undelivered_blocker_stays_urgent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf85-paper-deployment-telegram-cron-runner.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "operator_action": "BLOCKED",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "blocked", "errors": ["blocked_digest_not_delivered"]},
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf85_paper_deployment_telegram_cron_runner",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is True
    assert record["review_only_blocked_semantic"] is False
    assert record["main_handoff_semantic"] is False
    assert record["operator_action"] == "BLOCKED"


def test_retired_wf85_radar_history_keeps_runner_as_nonblocking_source_context() -> None:
    for job_name in (
        "Finance - WF85 Paper Deployment Telegram Radar",
        "Finance - WF85 Open-Ready Telegram Radar",
        "Finance - WF85 Post-Refresh Paper Deployment Telegram Radar",
    ):
        specs = RETIRED_LEGACY_JOB_CONTRACTS[job_name]["expected_artifacts"]
        runner_specs = [item for item in specs if item["role"] == "trade_grade_os_freshness_cron_runner"]
        assert runner_specs, job_name
        assert runner_specs[0]["blocking"] is False


def test_retired_deployment_history_preserves_prior_artifact_order() -> None:
    for job_name in (
        "Finance - Morning Paper Deployment Recommendation Cards",
        "Finance - Midday Paper Deployment Recommendation Cards",
        "Finance - Open-Ready Paper Deployment Recommendation Cards",
        "Finance - WF85 Paper Deployment Telegram Radar",
        "Finance - WF85 Open-Ready Telegram Radar",
        "Finance - WF85 Post-Refresh Paper Deployment Telegram Radar",
        "Finance - Weekday Post-Close Review Refresh",
    ):
        specs = RETIRED_LEGACY_JOB_CONTRACTS[job_name]["expected_artifacts"]
        roles = [item["role"] for item in specs]

        assert "finance_decision_sync_spine" in roles, job_name
        assert "veritas_finance_brief" in roles, job_name
        assert roles.index("finance_decision_sync_spine") < roles.index("veritas_finance_brief"), job_name

        md_specs = [item for item in specs if item["role"] == "veritas_finance_brief_md"]
        assert md_specs, job_name
        assert md_specs[0]["required"] is False
        assert md_specs[0]["blocking"] is False


def test_retired_pm_autonomous_proof_worker_is_not_active() -> None:
    assert "PM - Autonomous Implementation Proof Worker" not in JOB_CONTRACTS
    contract = RETIRED_LEGACY_JOB_CONTRACTS["PM - Autonomous Implementation Proof Worker"]
    roles = [item["role"] for item in contract["expected_artifacts"]]

    assert contract["freshness_hours"] == 24
    assert roles[:3] == ["pm_autonomy_dispatcher", "pm_job_worker_runner", "pm_autonomy_verifier"]

    inbox_specs = [item for item in contract["expected_artifacts"] if item["role"] == "pm_main_session_action_inbox"]
    assert inbox_specs
    assert inbox_specs[0]["required"] is False
    assert inbox_specs[0]["blocking"] is False


def test_embedded_legacy_contracts_never_enter_active_merge() -> None:
    assert RETIRED_LEGACY_JOB_CONTRACTS
    assert not any(name.startswith("Finance -") for name in JOB_CONTRACTS)
    assert not any(name.startswith("Finance Delivery Series -") for name in JOB_CONTRACTS)
    assert not any(name.startswith("GPT54mini canary -") for name in JOB_CONTRACTS)

    contracts = merged_job_contracts()
    for name in RETIRED_LEGACY_JOB_CONTRACTS:
        assert name not in contracts
    for name, contract in contracts.items():
        if name.startswith("Finance -"):
            assert str(contract.get("contract_source") or "").startswith("state/cron-contracts/"), name


def test_new_file_backed_otel_and_security_contracts_are_active() -> None:
    contracts = merged_job_contracts()
    expected = {
        "Runtime - OTEL Collector Log Retention": "state/cron-contracts/runtime-otel-collector-log-retention.json",
        "Security Audit - Daily Bounded Hardening": "state/cron-contracts/security-audit-daily-bounded-hardening.json",
    }
    for name, source in expected.items():
        assert contracts[name]["contract_source"] == source


def test_file_backed_semantic_memory_contract_registers_active_artifact() -> None:
    contracts = merged_job_contracts()
    contract = contracts["Runtime - Semantic Memory Cache Maintenance"]
    roles = [item["role"] for item in contract["expected_artifacts"]]

    assert contract["contract_source"] == "state/cron-contracts/runtime-semantic-memory-cache-maintenance.json"
    assert roles == ["semantic_memory_maintenance"]


def test_file_backed_alert_chain_contracts_surface_active_proofs() -> None:
    contracts = merged_job_contracts()
    morning = contracts["Finance - Weekday Morning Alerts and Recommendations Refresh"]
    post_close = contracts["Finance - Weekday Post-Close Alerts and Recommendations Refresh"]
    morning_roles = [item["role"] for item in morning["expected_artifacts"]]
    post_close_roles = [item["role"] for item in post_close["expected_artifacts"]]

    assert morning["contract_source"] == "state/cron-contracts/finance-weekday-morning-review-refresh.json"
    assert post_close["contract_source"] == "state/cron-contracts/finance-weekday-post-close-review-refresh.json"
    assert morning_roles == [
        "alerts_recommendations_chain_morning",
        "alert_level_freshness_controller",
        "finance_alert_os_morning_digest",
        "quote_snapshot_proof",
        "quote_snapshot_proof_validation",
        "finance_sql_canon_access_validation",
    ]
    assert post_close_roles == [
        "alerts_recommendations_chain_post_close",
        "alert_level_freshness_controller",
        "finance_alert_os_post_close_digest",
        "quote_snapshot_proof",
        "quote_snapshot_proof_validation",
        "finance_sql_canon_access_validation",
    ]


def test_weekly_os_radar_keeps_cron_control_packet_as_nonblocking_context() -> None:
    for job_name in (
        "Runtime - Weekly OS Improvement Radar Proof Refresh",
        "Runtime - Weekly OS Improvement Radar Review",
    ):
        contract = merged_job_contracts()[job_name]
        specs = [item for item in contract["expected_artifacts"] if item["role"] == "cron_control_packet"]
        assert specs, job_name
        assert specs[0]["required"] is True
        assert specs[0]["blocking"] is False


def test_cron_control_packet_context_does_not_block_freshness_spine() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cron-control-packet.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "veritas.cron_control_packet.v1",
                    "status": "error",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "error", "errors": ["freshness_status_not_ok"]},
                    "authority_boundary": {
                        "cron_state_mutation_allowed": False,
                        "cron_schedule_mutation_allowed": False,
                        "runtime_config_mutation_allowed": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "cron_control_packet",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is True
    assert record["blocking"] is False
    assert record["authority_widened"] is False


def test_wf78_tier_semantic_lineage_mismatch_blocks_inside_generic_ttl() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        router_path = tmp_path / "wf78-auto-tier-routing.json"
        truth_map_path = tmp_path / "wf78-truth-layer-map.json"
        published_router = {
            "status": "ok",
            "generated_at_utc": "2026-08-08T12:00:00Z",
            "rows": [{"ticker": "NVDA", "auto_tier": "Tier B", "auto_state": "B-VALIDATED"}],
        }
        live_router = {
            "status": "ok",
            "generated_at_utc": "2026-08-08T12:05:00Z",
            "rows": [{"ticker": "NVDA", "auto_tier": "Tier A", "auto_state": "A-READY"}],
        }
        published_lineage = router_lineage(published_router, router_path)
        router_path.write_text(json.dumps(live_router), encoding="utf-8")
        truth_map_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "generated_at_utc": now,
                    "validation": {"status": "ok"},
                    "source_router_lineage": published_lineage,
                    "source_roster_lineage": {
                        "path": "tmp/wf78-clean-tier-roster.json",
                        "source_router_lineage": published_lineage,
                    },
                }
            ),
            encoding="utf-8",
        )
        job = {
            "name": "WF78 lineage test",
            "enabled": True,
            "schedule": {"expr": "0 * * * *", "kind": "cron", "tz": "America/Phoenix"},
            "last_status": "ok",
            "consecutive_errors": 0,
        }
        contract = {
            "owner_workflow": "test",
            "freshness_hours": 36,
            "expected_artifacts": [
                {
                    "path": str(truth_map_path),
                    "role": "wf78_truth_layer_map",
                    "required": True,
                    "blocking": False,
                    "source_router_path": str(router_path),
                }
            ],
        }

        classified = classify_job(job, contract)

    record = classified["expected_artifacts"][0]
    assert record["stale"] is False
    assert record["blocking"] is True
    assert record["wf78_tier_semantic_lineage"]["status"] == "mismatched"
    assert record["wf78_tier_semantic_lineage_blocked"] is True
    assert classified["status"] == "blocked"
    assert classified["signal_class"] == "BLOCKED"
    assert classified["reason"] == "wf78_tier_semantic_lineage_missing_or_mismatched"


def test_newer_clean_artifact_deescalates_failed_scheduler_until_natural_canary() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory() as raw:
        artifact = Path(raw) / "proof.json"
        artifact.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "generated_at_utc": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                }
            ),
            encoding="utf-8",
        )
        job = {
            "name": "Recovered scheduler test",
            "enabled": True,
            "schedule": {"expr": "0 * * * *", "kind": "cron", "tz": "America/Phoenix"},
            "last_status": "error",
            "consecutive_errors": 3,
            "last_run_utc": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "last_error": "command exited with code 1",
        }
        contract = {
            "owner_workflow": "test",
            "freshness_hours": 36,
            "expected_artifacts": [
                {"path": str(artifact), "role": "recovery_proof", "required": True, "blocking": True}
            ],
        }

        recovered = classify_job(job, contract)
        job["last_run_utc"] = now.isoformat().replace("+00:00", "Z")
        not_recovered = classify_job(job, contract)

    assert recovered["status"] == "recovered_waiting_scheduler_canary"
    assert recovered["signal_class"] == "STALE_OR_NOISE"
    assert recovered["reason"] == "fresh_artifacts_prove_recovery_after_last_scheduler_failure"
    assert recovered["live_scheduler_last_status"] == "error"
    assert recovered["live_scheduler_consecutive_errors"] == 3
    assert recovered["live_scheduler_last_error"] == "command exited with code 1"
    assert not_recovered["status"] == "scheduler_error"
    assert not_recovered["signal_class"] == "BLOCKED"


def test_known_platform_failure_quiets_only_exact_error_on_recorded_version() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory() as raw:
        artifact = Path(raw) / "AGENTS.md"
        artifact.write_text("# role\n", encoding="utf-8")
        job = {
            "name": "skill-collection-review-locked-lab",
            "enabled": True,
            "schedule": {"kind": "every", "everyMs": 604800000},
            "last_status": "error",
            "consecutive_errors": 2,
            "last_run_utc": now.isoformat().replace("+00:00", "Z"),
            "last_error": "sandbox workspace is not read-write; collection review skipped",
        }
        contract = {
            "owner_workflow": "test",
            "freshness_hours": 192,
            "expected_artifacts": [{"path": str(artifact), "required": True, "blocking": False}],
            "known_platform_failure": {
                "error_substring": "sandbox workspace is not read-write",
                "openclaw_version": "2026.9.4",
                "upstream": "openclaw/openclaw#144515",
                "owner_approved_at": "2026-09-23",
            },
        }

        quiet = classify_job(job, contract, "2026.9.4")
        new_version = classify_job(job, contract, "2026.9.5")
        no_version = classify_job(job, contract, None)
        other_error = classify_job({**job, "last_error": "Failed to inspect sandbox image"}, contract, "2026.9.4")
        unapproved = classify_job(
            job,
            {**contract, "known_platform_failure": {**contract["known_platform_failure"], "owner_approved_at": ""}},
            "2026.9.4",
        )
        missing_artifact = classify_job(
            job,
            {**contract, "expected_artifacts": [{"path": str(Path(raw) / "gone.md"), "required": True}]},
            "2026.9.4",
        )

    assert quiet["status"] == "known_platform_failure"
    assert quiet["signal_class"] == "STALE_OR_NOISE"
    assert quiet["reason"] == "owner_approved_known_platform_failure:openclaw/openclaw#144515"
    assert quiet["live_scheduler_last_error"] == job["last_error"]
    for escalated in (new_version, no_version, other_error, unapproved):
        assert escalated["status"] == "scheduler_error"
        assert escalated["signal_class"] == "BLOCKED"
    assert missing_artifact["signal_class"] == "BLOCKED"
    assert missing_artifact["status"] == "scheduler_error"

    with tempfile.TemporaryDirectory() as raw:
        contract_dir = Path(raw)
        (contract_dir / "locked-lab.json").write_text(
            json.dumps({**contract, "name": job["name"], "expected_artifacts": [{"path": "AGENTS.md", "required": True}]}),
            encoding="utf-8",
        )
        merged = merged_job_contracts(contract_dir)
    assert merged[job["name"]]["known_platform_failure"] == contract["known_platform_failure"]


def test_known_platform_failure_extra_substrings_quiet_only_listed_errors() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    bind_error = 'Sandbox security: bind mount "C:\\lab\\AGENTS.md:/role/AGENTS.md:ro" source "C:/lab/AGENTS.md" is outside allowed roots (C:/x). Use a dangerous override'
    with tempfile.TemporaryDirectory() as raw:
        artifact = Path(raw) / "AGENTS.md"
        artifact.write_text("# role\n", encoding="utf-8")
        job = {
            "name": "skill-collection-review-locked-lab",
            "enabled": True,
            "schedule": {"kind": "every", "everyMs": 604800000},
            "last_status": "error",
            "consecutive_errors": 2,
            "last_run_utc": now.isoformat().replace("+00:00", "Z"),
            "last_error": bind_error,
        }
        known = {
            "error_substring": "sandbox workspace is not read-write",
            "error_substrings": ['Sandbox security: bind mount "C:\\lab\\AGENTS.md:/role/AGENTS.md:ro" source "C:/lab/AGENTS.md" is outside allowed roots ('],
            "openclaw_version": "2026.9.4",
            "upstream": "openclaw/openclaw#144515",
            "owner_approved_at": "2026-09-26",
        }
        contract = {
            "owner_workflow": "test",
            "freshness_hours": 192,
            "expected_artifacts": [{"path": str(artifact), "required": True, "blocking": False}],
            "known_platform_failure": known,
        }
        bind_quiet = classify_job(job, contract, "2026.9.4")
        rw_quiet = classify_job({**job, "last_error": "sandbox workspace is not read-write; collection review skipped"}, contract, "2026.9.4")
        other_bind = classify_job({**job, "last_error": bind_error.replace("AGENTS.md", "SOUL.md")}, contract, "2026.9.4")
        new_version = classify_job(job, contract, "2026.9.5")
        not_a_list = classify_job(job, {**contract, "known_platform_failure": {**known, "error_substrings": known["error_substrings"][0]}}, "2026.9.4")

    assert bind_quiet["status"] == "known_platform_failure"
    assert rw_quiet["status"] == "known_platform_failure"
    for escalated in (other_bind, new_version, not_a_list):
        assert escalated["status"] == "scheduler_error"
        assert escalated["signal_class"] == "BLOCKED"


def test_newer_warning_artifact_keeps_review_signal_without_scheduler_escalation() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory() as raw:
        artifact = Path(raw) / "proof.json"
        artifact.write_text(
            json.dumps(
                {
                    "status": "warning",
                    "generated_at_utc": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "warning"},
                }
            ),
            encoding="utf-8",
        )
        classified = classify_job(
            {
                "name": "Recovered warning scheduler test",
                "enabled": True,
                "schedule": {"expr": "0 * * * *", "kind": "cron", "tz": "America/Phoenix"},
                "last_status": "error",
                "consecutive_errors": 3,
                "last_run_utc": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            },
            {
                "owner_workflow": "test",
                "freshness_hours": 36,
                "expected_artifacts": [
                    {"path": str(artifact), "role": "warning_recovery_proof", "required": True, "blocking": True}
                ],
            },
        )

    assert classified["status"] == "needs_review"
    assert classified["signal_class"] == "MAIN_SESSION_REQUIRED"
    assert classified["reason"] == "artifact_requests_or_warns_for_review"
    assert classified["live_scheduler_reconciliation"] == (
        "newer_nonblocking_artifacts_prove_execution_recovery_waiting_natural_canary"
    )


def test_contractless_one_shot_at_job_is_exempt_pending() -> None:
    job = {
        "id": "c261f6e6-669d-4715-afce-ef625f720068",
        "name": "Follow-up: Future Session Packet re-check",
        "enabled": True,
        "schedule": {"kind": "at", "at": "2026-09-14T14:00:00.000Z"},
    }

    classified = classify_job(job, None)

    assert classified["status"] == "one_shot_pending"
    assert classified["signal_class"] == "NO_REPLY"
    assert classified["attention"] == "quiet_success"
    assert classified["reason"] == "one_shot_at_job_exempt_from_standing_freshness_contract"
    assert classified["expected_artifacts"] == []

    string_job = dict(job)
    string_job["schedule"] = json.dumps({"kind": "at", "at": "2026-09-14T14:00:00.000Z"})
    assert schedule_kind(job) == "at"
    assert schedule_kind(string_job) == "at"
    string_classified = classify_job(string_job, None)
    assert string_classified["status"] == "one_shot_pending"
    assert string_classified["signal_class"] == "NO_REPLY"

    payload = {
        "jobs": [classified],
        "signals": [],
        "summary": {},
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    validation = validate_payload(payload)
    assert validation["status"] == "ok"
    assert validation["errors"] == []


def test_contractless_one_shot_at_job_failure_still_blocks() -> None:
    job = {
        "id": "c261f6e6-669d-4715-afce-ef625f720068",
        "name": "Follow-up: Future Session Packet re-check",
        "enabled": True,
        "schedule": {"kind": "at", "at": "2026-09-14T14:00:00.000Z"},
        "last_status": "error",
        "consecutive_errors": 1,
        "last_error": "command exited with code 1",
    }

    classified = classify_job(job, None)

    assert classified["status"] == "one_shot_scheduler_error"
    assert classified["signal_class"] == "BLOCKED"
    assert classified["attention"] == "requires_main_attention"
    assert classified["reason"] == "one_shot_job_last_run_failed"
    assert classified["expected_artifacts"] == []


def test_contractless_cron_job_still_unregistered() -> None:
    job = {
        "id": "cron-regression-guard",
        "name": "Cron Regression Guard",
        "enabled": True,
        "schedule": {"expr": "0 * * * *", "kind": "cron", "tz": "America/Phoenix"},
    }

    classified = classify_job(job, None)

    assert classified["status"] == "unregistered"
    assert classified["signal_class"] == "BLOCKED"
    assert classified["reason"] == "enabled_job_missing_freshness_contract"


if __name__ == "__main__":
    test_quote_first_warning_is_quiet_with_nonfresh_backlog()
    test_quote_first_warning_does_not_quiet_stale_or_critical()
    test_no_reply_operator_action_is_not_handoff()
    test_cron_operator_ledger_warning_rollup_quiet_only_when_clean()
    test_pm_no_action_status_refresh_residue_is_quiet()
    test_status_card_cron_migration_self_loop_residue_is_not_urgent_blocker()
    test_attention_class_separates_known_review_from_new_review()
    test_known_review_uses_underlying_signal_when_prior_run_was_quieted()
    test_known_monitor_only_bucket_is_quiet_success()
    test_standing_review_quiet_removes_stable_review_from_attention_queue()
    test_paper_positions_blocked_packet_is_review_only_handoff_not_urgent_blocker()
    test_wf87_runtime_blocked_packet_is_review_only_handoff_not_urgent_blocker()
    test_wf85_delivered_blocker_is_review_only_handoff_not_urgent_blocker()
    test_paper_recommendation_blocked_card_is_review_only_handoff_not_urgent_blocker()
    test_wf78_owner_card_prep_no_rows_ok_no_work_is_not_urgent_blocker()
    test_wf78_owner_card_prep_wf67_blocked_warning_is_not_urgent_blocker()
    test_wf85_undelivered_blocker_stays_urgent()
    test_retired_wf85_radar_history_keeps_runner_as_nonblocking_source_context()
    test_retired_pm_autonomous_proof_worker_is_not_active()
    test_file_backed_semantic_memory_contract_registers_active_artifact()
    test_file_backed_alert_chain_contracts_surface_active_proofs()
    test_weekly_os_radar_keeps_cron_control_packet_as_nonblocking_context()
    test_cron_control_packet_context_does_not_block_freshness_spine()
    test_wf78_tier_semantic_lineage_mismatch_blocks_inside_generic_ttl()
    test_newer_clean_artifact_deescalates_failed_scheduler_until_natural_canary()
    test_newer_warning_artifact_keeps_review_signal_without_scheduler_escalation()
    test_contractless_one_shot_at_job_is_exempt_pending()
    test_contractless_one_shot_at_job_failure_still_blocks()
    test_contractless_cron_job_still_unregistered()
    print("cron_freshness_spine_tests_passed")
