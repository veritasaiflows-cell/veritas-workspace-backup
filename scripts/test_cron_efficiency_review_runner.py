#!/usr/bin/env python3
"""Focused tests for cron_efficiency_review_runner.py."""
from __future__ import annotations

import cron_efficiency_review_runner as runner


def scorecard_fixture() -> dict:
    return {
        "summary": {
            "total_tokens": 1000,
            "api_call_reduction_candidate_count": 1,
            "prompt_compression_candidate_count": 1,
            "failure_cost_candidate_count": 0,
            "implementation_token_gap_count": 3,
        },
        "api_call_reduction_candidates": [{"cron_job_name": "A"}],
        "prompt_compression_candidates": [{"cron_job_name": "A"}],
        "failure_cost_candidates": [],
        "validation": {"status": "warning", "warnings": ["implementation_token_gap_count:3"]},
    }


def predispatch_fixture() -> dict:
    return {
        "summary": {
            "agent_turn_candidate_count": 1,
            "existing_changed_only_command_gate_count": 0,
        },
        "warnings": ["agent_turn_candidates_require_pre_model_payload_diff"],
    }


def token_review_fixture() -> dict:
    return {
        "status": "review_warning_no_apply_authority",
        "summary": {
            "promotion_ready_count": 0,
            "promotion_incomplete_count": 1,
            "next_changed_only_candidate": "PM - Autonomous Implementation Proof Worker",
            "fallback_changed_only_candidate": "Finance - Ticker Card Freshness Owner Runner",
            "next_prompt_compression_candidate": "Finance - Ticker Card Freshness Owner Runner",
        },
        "automation_queues": {
            "changed_only_prefilter": {
                "state": "proof_incomplete",
                "next_candidate": {"cron_job_name": "PM - Autonomous Implementation Proof Worker"},
                "fallback_candidate": {"cron_job_name": "Finance - Ticker Card Freshness Owner Runner"},
            },
            "prompt_compression": {
                "state": "candidate_available",
                "next_candidate": {"cron_job_name": "Finance - Ticker Card Freshness Owner Runner"},
            },
            "later_outcome_guard": {"state": "enforced_by_agi_os_eval_gate"},
        },
        "validation": {"status": "warning", "warnings": ["implementation_token_gap_count:3"]},
    }


def pm_prefilter_fixture() -> dict:
    return {
        "status": "run_required",
        "action": "run_worker_when_promoted",
        "worker_prefilter": {"reason": "source_signature_changed", "source_unchanged": False},
        "validation": {"status": "ok", "warnings": []},
    }


def ticker_prefilter_fixture() -> dict:
    return {
        "status": "skipped_unchanged",
        "action": "skip_worker",
        "worker_prefilter": {
            "reason": "source_unchanged_and_same_day_successful_output_present",
            "source_unchanged": True,
        },
        "validation": {"status": "ok", "warnings": []},
    }


def agi_eval_fixture() -> dict:
    return {
        "status": "eval_warning_review_only",
        "summary": {"warning_count": 1},
        "validation": {"status": "warning", "warnings": ["token_efficiency_promotion_gate"]},
    }


def agi_harness_fixture() -> dict:
    return {
        "status": "warning",
        "readiness_state": "partial_ready_review_only_with_warnings",
        "summary": {"warning_count": 1},
        "validation": {"status": "warning", "warnings": ["agi_os_eval_gate"]},
    }


def contract_fixture(prompt_errors: int = 0) -> dict:
    return {
        "summary": {
            "drift_count": 0,
            "missing_live_job_count": 0,
            "live_prompt_integrity_error_count": prompt_errors,
        },
        "validation": {"status": "error" if prompt_errors else "ok", "errors": []},
    }


def prompt_book_fixture(*, lint_blocked: bool = False, eval_gaps: int = 0) -> dict:
    lint_status = "blocked" if lint_blocked else ("warning" if eval_gaps else "ok")
    lint_validation = {"status": "blocked" if lint_blocked else "ok", "errors": [], "warnings": []}
    return {
        "registry": {
            "status": "ok",
            "summary": {"entry_count": 12},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "fixtures": {
            "status": "ok",
            "summary": {"fixture_count": 8, "fixture_target_count": 8},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "lint": {
            "status": lint_status,
            "summary": {
                "entry_count": 12,
                "eval_gap_count": eval_gaps,
                "raw_capture_violation_count": 1 if lint_blocked else 0,
                "prompt_text_stored": False,
            },
            "validation": lint_validation,
        },
        "eval_gap": {
            "status": "warning" if eval_gaps else "ok",
            "summary": {
                "eval_gap_count": eval_gaps,
                "high_priority_gap_count": 0,
            },
            "validation": {
                "status": "ok",
                "errors": [],
                "warnings": [] if not eval_gaps else [f"{eval_gaps} prompt-book entries lack covered eval fixtures"],
            },
        },
        "pm_jobs": {
            "status": "ok",
            "summary": {"job_count": 4},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    }


def test_review_payload_warns_without_blocking_efficiency_debt() -> None:
    payload = runner.build_review_payload(
        scorecard=scorecard_fixture(),
        predispatch=predispatch_fixture(),
        token_review_packet=token_review_fixture(),
        pm_prefilter_packet=pm_prefilter_fixture(),
        ticker_prefilter_packet=ticker_prefilter_fixture(),
        agi_eval_packet=agi_eval_fixture(),
        agi_harness_packet=agi_harness_fixture(),
        contract=contract_fixture(),
        prompt_book=prompt_book_fixture(),
    )
    assert payload["status"] == "ok"
    assert payload["review_status"] == "warning"
    assert payload["operator_action"] == "REVIEW_WARNINGS"
    assert payload["validation"]["status"] == "ok"
    assert payload["summary"]["next_changed_only_candidate"] == "PM - Autonomous Implementation Proof Worker"
    assert payload["summary"]["next_prompt_compression_candidate"] == "Finance - Ticker Card Freshness Owner Runner"
    assert payload["summary"]["ticker_card_prefilter_status"] == "skipped_unchanged"
    assert payload["automation_queues"]["later_outcome_guard"]["state"] == "enforced_by_agi_os_eval_gate"
    assert payload["summary"]["prompt_book_lint_status"] == "ok"
    assert payload["summary"]["prompt_book_eval_gap_count"] == 0


def test_review_payload_blocks_prompt_integrity_errors() -> None:
    payload = runner.build_review_payload(
        scorecard=scorecard_fixture(),
        predispatch=predispatch_fixture(),
        token_review_packet=token_review_fixture(),
        pm_prefilter_packet=pm_prefilter_fixture(),
        ticker_prefilter_packet=ticker_prefilter_fixture(),
        agi_eval_packet=agi_eval_fixture(),
        agi_harness_packet=agi_harness_fixture(),
        contract=contract_fixture(prompt_errors=2),
        prompt_book=prompt_book_fixture(),
    )
    assert payload["status"] == "blocked"
    assert payload["operator_action"] == "BLOCKED"
    assert "live_prompt_integrity_errors_present" in payload["errors"]
    assert payload["validation"]["status"] == "error"


def test_review_payload_blocks_scorecard_detail_mismatch() -> None:
    scorecard = scorecard_fixture()
    scorecard["api_call_reduction_candidates"] = []
    payload = runner.build_review_payload(
        scorecard=scorecard,
        predispatch=predispatch_fixture(),
        token_review_packet=token_review_fixture(),
        pm_prefilter_packet=pm_prefilter_fixture(),
        ticker_prefilter_packet=ticker_prefilter_fixture(),
        agi_eval_packet=agi_eval_fixture(),
        agi_harness_packet=agi_harness_fixture(),
        contract=contract_fixture(),
        prompt_book=prompt_book_fixture(),
    )
    assert payload["status"] == "blocked"
    assert any(error.startswith("token_scorecard_detail_mismatch") for error in payload["errors"])


def test_review_payload_blocks_prompt_book_lint_errors() -> None:
    payload = runner.build_review_payload(
        scorecard=scorecard_fixture(),
        predispatch=predispatch_fixture(),
        token_review_packet=token_review_fixture(),
        pm_prefilter_packet=pm_prefilter_fixture(),
        ticker_prefilter_packet=ticker_prefilter_fixture(),
        agi_eval_packet=agi_eval_fixture(),
        agi_harness_packet=agi_harness_fixture(),
        contract=contract_fixture(),
        prompt_book=prompt_book_fixture(lint_blocked=True),
    )
    assert payload["status"] == "blocked"
    assert "prompt_book_lint_blocked" in payload["errors"]
    assert "prompt_book_raw_capture_violation_present" in payload["errors"]


def test_reporting_producers_use_mocked_gateway_and_preserve_order() -> None:
    calls: list[str] = []
    writes: list[str] = []
    timestamps = iter([
        "2026-08-09T18:00:01Z",
        "2026-08-09T18:00:02Z",
        "2026-08-09T18:00:03Z",
        "2026-08-09T18:00:04Z",
    ])

    def gateway_loader(agent_ids, *, days):
        calls.append("gateway")
        assert tuple(agent_ids) == runner.isolated_usage.CONFIGURED_ISOLATED_AGENT_IDS
        assert days == 8
        return {
            "schema": "veritas.isolated_agent_gateway_usage_cost_collection.v1",
            "metadata_only": True,
            "summary": {"blocked_agent_count": 0},
            "agents": [],
        }

    def token_builder(path, *, append, isolated_gateway_usage):
        calls.append("token")
        assert append is False
        assert isolated_gateway_usage["metadata_only"] is True
        return {"generated_at_utc": "2026-08-09T18:00:01Z", "status": "ok"}, []

    def budget_builder(path):
        calls.append("budget")
        return {"generated_at_utc": "2026-08-09T18:00:02Z", "status": "ok"}

    def scorecard_builder(token_path, budget_path, contract_path):
        calls.append("scorecard")
        return {"generated_at_utc": "2026-08-09T18:00:03Z", "status": "ok"}

    chain = runner.run_reporting_producers(
        gateway_loader=gateway_loader,
        token_builder=token_builder,
        budget_builder=budget_builder,
        scorecard_builder=scorecard_builder,
        json_writer=lambda path, payload: writes.append(str(path)),
        now_fn=lambda: next(timestamps),
        append=False,
    )

    assert calls == ["gateway", "token", "budget", "scorecard"]
    assert [row["stage"] for row in chain["stages"]] == [
        "isolated_agent_usage_metadata",
        "token_usage_ledger",
        "token_budget_status",
        "token_efficiency_scorecard",
    ]
    assert len(writes) == 3
    all_stages = chain["stages"] + [
        {"stage": "cron_efficiency_review", "completed_at_utc": "2026-08-09T18:00:05Z"},
        {"stage": "status_card_packet", "completed_at_utc": "2026-08-09T18:00:06Z"},
    ]
    ordering = runner.validate_stage_order(all_stages)
    assert ordering["status"] == "ok"
    assert ordering["producer_before_consumer"] is True


def test_reporting_order_rejects_consumer_before_producer() -> None:
    stages = [
        {"stage": "isolated_agent_usage_metadata", "completed_at_utc": "2026-08-09T18:00:01Z"},
        {"stage": "token_usage_ledger", "completed_at_utc": "2026-08-09T18:00:03Z"},
        {"stage": "token_budget_status", "completed_at_utc": "2026-08-09T18:00:02Z"},
        {"stage": "token_efficiency_scorecard", "completed_at_utc": "2026-08-09T18:00:04Z"},
        {"stage": "cron_efficiency_review", "completed_at_utc": "2026-08-09T18:00:05Z"},
        {"stage": "status_card_packet", "completed_at_utc": "2026-08-09T18:00:06Z"},
    ]
    ordering = runner.validate_stage_order(stages)
    assert ordering["status"] == "blocked"
    assert ordering["producer_before_consumer"] is False
    assert any("token_usage_ledger->token_budget_status" in item for item in ordering["errors"])


def main() -> int:
    test_review_payload_warns_without_blocking_efficiency_debt()
    test_review_payload_blocks_prompt_integrity_errors()
    test_review_payload_blocks_scorecard_detail_mismatch()
    test_review_payload_blocks_prompt_book_lint_errors()
    test_reporting_producers_use_mocked_gateway_and_preserve_order()
    test_reporting_order_rejects_consumer_before_producer()
    print("cron_efficiency_review_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
