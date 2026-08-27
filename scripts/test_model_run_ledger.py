from __future__ import annotations

import json
import tempfile
from pathlib import Path

from concurrent_lane_manager import (
    USAGE_SOURCE_RECEIPTS_SCHEMA,
    bounded_usage_receipt,
    build_attempt_correlation_key,
)
import model_run_ledger as ledger


TEST_PRICING = {
    "schema": "veritas.model_token_pricing.v1",
    "pricing_basis": {"short_context_input_limit_tokens": 272_000},
    "model_aliases": {"openai-codex/gpt-5.6-sol": "openai/gpt-5.6-sol"},
    "models": {
        "openai/gpt-5.4-mini": {
            "input_per_million": 0.75,
            "cached_input_per_million": 0.075,
            "output_per_million": 4.5,
            "status": "official",
        },
        "openai/gpt-5.6-sol": {
            "input_per_million": 5.0,
            "cached_input_per_million": 0.5,
            "output_per_million": 30.0,
            "long_context_input_per_million": 10.0,
            "long_context_cached_input_per_million": 1.0,
            "long_context_output_per_million": 45.0,
            "status": "official",
        },
    },
}


def cron_entry(usage: dict, *, run_id: str = "run-1", ts: object = 1_700_000_000_000) -> dict:
    return {
        "action": "finished",
        "runId": run_id,
        "jobId": "job-1",
        "jobName": "Runtime Proof",
        "provider": "openai",
        "model": "gpt-5.4-mini",
        "status": "ok",
        "durationMs": 1000,
        "sessionId": "session-1",
        "ts": ts,
        "usage": usage,
    }


def test_lane_register_rows_stamp_session_and_model_when_present() -> None:
    payload = {
        "generated_at_utc": "2026-06-12T20:00:00Z",
        "lanes": [
            {
                "lane_id": "WF74::otel-collection",
                "workflow_id": "WF74",
                "workstream_id": "otel-collection",
                "owner": "webchat-main",
                "status": "complete",
                "started_at_utc": "2026-06-12T20:01:00Z",
                "completed_at_utc": "2026-06-12T20:05:00Z",
                "runtime": {
                    "session_id": "session-1",
                    "session_key": "agent:main",
                    "session_label": "webchat-main",
                    "task_name": "otel-collection",
                    "model_path": "openai/gpt-5.5",
                },
                "acceptance_commands": ["python scripts\\test_model_run_ledger.py"],
                "proof_artifacts": ["tmp/proof.json"],
            }
        ],
    }
    rows = ledger.lane_register_rows(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row["producer"] == "concurrent_lane_manager"
    assert row["workflow_id"] == "WF74"
    assert row["model_path"] == "openai/gpt-5.5"
    assert row["model_provider"] == "openai"
    assert row["session_id"] == "session-1"
    assert row["session_label"] == "webchat-main"
    assert row["task_name"] == "otel-collection"
    assert row["attribution"]["model_present"] is True
    assert row["attribution"]["session_present"] is True
    assert row["model_support"]["status"] == "supported_or_unclassified"
    assert row["model_support"]["active_route_countable"] is True
    assert row["authority_boundary"]["runtime_config_mutation_allowed"] is False


def test_post_cutover_unverified_model_lane_is_audit_only() -> None:
    payload = {
        "generated_at_utc": "2026-08-13T21:15:00Z",
        "lanes": [
            {
                "lane_id": "WF74::unverified-model-lane",
                "workflow_id": "WF74",
                "workstream_id": "unverified-model-lane",
                "status": "complete",
                "created_at_utc": "2026-08-13T21:00:00Z",
                "started_at_utc": "2026-08-13T21:01:00Z",
                "completed_at_utc": "2026-08-13T21:05:00Z",
                "runtime": {
                    "model_path": "openai/gpt-5.6-terra",
                    "usage_creditable": True,
                    "source_reverification_status": "blocked",
                    "usage_credit_block_reasons": ["codex_dispatch_binding_required"],
                },
            }
        ],
    }
    row = ledger.lane_register_rows(payload)[0]
    attribution = row["attribution"]
    assert row["status"] == "complete"  # factual work status is audit-visible
    assert attribution["model_present"] is True
    assert attribution["model_applicable"] is False
    assert attribution["telemetry_eligible"] is False
    assert attribution["telemetry_credit_status"] == "blocked_unverified_usage_source"
    assert "source_reverification_not_verified" in attribution["telemetry_block_reasons"]
    assert row["telemetry_requirement"]["performance_cost_latency_reliability_savings_eligible"] is False

    ledger_payload = ledger.build_ledger({
        "runtime_perf": {},
        "otel_ops": {},
        "cron_spark_canary": {},
        "cron_runs": {"status": "ok", "entries": [], "selected_job_count": 0, "queried_job_count": 0, "error_count": 0, "timeout_count": 0},
        "lane_register": payload,
        "pricing": {},
    })
    assert ledger_payload["summary"]["attribution_applicable_rows"] == 0
    assert ledger_payload["summary"]["lane_audit_only_uncredited_rows"] == 1
    assert ledger_payload["summary"]["supported_model_capacity_rows"] == 0
    assert ledger_payload["summary"]["session_attribution_applicable_rows"] == 0
    assert ledger_payload["summary"]["session_attributed_rows"] == 0
    assert ledger_payload["summary"]["session_attribution_applicable_coverage"] == 0.0


def test_post_cutover_coherent_writable_receipt_stays_blocked_without_source_reopen() -> None:
    lane = {
        "lane_id": "WF74::forged-receipt-lane",
        "status": "complete",
        "created_at_utc": "2026-08-13T21:00:00Z",
        "completed_at_utc": "2026-08-13T21:05:00Z",
    }
    runtime = {
        "model_path": "openai/gpt-5.6-terra",
        "usage_creditable": True,
        "source_reverification_status": "verified",
        "token_attribution_source": "openclaw_isolated_session_store_v1",
        "agent_id": "finance-source-scout",
        "run_id": "forged-source-run",
        "source_snapshot_fingerprint": "forged-source-snapshot",
        "session_ref_hash": "forged-session-reference",
        "parent_job_id": "forged-parent",
        "phase": "implementation",
        "retry_count": 0,
        "input_tokens": 10,
        "cached_input_tokens": 2,
        "cache_write_tokens": 0,
        "output_tokens": 3,
        "total_tokens": 15,
        "source_input_total_tokens": 12,
        "source_total_tokens_fresh": True,
        "input_token_semantics": "exclusive_cached",
    }
    correlation = build_attempt_correlation_key(
        parent_job_id=runtime["parent_job_id"],
        lane_id=lane["lane_id"],
        phase=runtime["phase"],
        retry_count=runtime["retry_count"],
    )
    assert correlation is not None
    runtime["attempt_correlation"] = correlation
    receipt = bounded_usage_receipt(lane, runtime)
    assert receipt is not None
    runtime["usage_source_receipt_id"] = receipt["receipt_id"]
    payload = {"lanes": [{**lane, "runtime": runtime}]}
    with tempfile.TemporaryDirectory() as directory:
        register_path = Path(directory) / "register.json"
        receipt_path = register_path.with_suffix(".usage-receipts.json")
        receipt_path.write_text(json.dumps({
            "schema": USAGE_SOURCE_RECEIPTS_SCHEMA,
            "metadata_only": True,
            "receipts": [receipt],
        }), encoding="utf-8")
        row = ledger.lane_register_rows(payload, register_path=register_path)[0]
    assert row["attribution"]["model_applicable"] is False
    assert row["attribution"]["telemetry_eligible"] is False
    assert row["attribution"]["telemetry_credit_status"] == "blocked_unverified_usage_source"
    assert "isolated_source_reverification_mismatch" in row["attribution"]["telemetry_block_reasons"]


def test_cron_run_rows_inclusive_cached_semantics() -> None:
    cron_runs = {
        "entries": [
            cron_entry({
                "input_tokens": 1300,
                "cached_input_tokens": 300,
                "output_tokens": 200,
                "total_tokens": 1500,
            })
        ]
    }
    rows = ledger.cron_run_rows(cron_runs, TEST_PRICING)
    assert len(rows) == 1
    row = rows[0]
    assert row["model_path"] == "openai/gpt-5.4-mini"
    assert row["tokens"] == 1500
    assert row["cached_input_tokens"] == 300
    assert row["input_token_semantics"] == "inclusive_cached"
    assert row["uncached_input_tokens"] == 1000
    assert row["token_semantics_status"] == "valid"
    assert row["api_equivalent_cost_label"] == "API-equivalent benchmark"
    assert abs(row["api_equivalent_cost_usd"] - 0.001672) < 0.000001
    assert abs(row["cost"] - 0.001672) < 0.000001
    assert row["cost"] == row["api_equivalent_cost_usd"]
    assert row["cost_semantics"] == "deprecated_alias_of_api_equivalent_cost_usd"
    assert row["cost_pricing_status"] == "estimated"
    assert row["cost_estimate_only"] is True
    assert row["usage_at_utc"] == "2023-11-14T22:13:20Z"
    assert row["usage_time_source"] == "entry.ts_epoch_milliseconds"
    assert row["attribution"]["model_applicable"] is True
    assert row["attribution"]["telemetry_eligible"] is True
    assert row["attribution"]["telemetry_credit_status"] == "direct_gateway_cron_usage"
    assert row["authority_boundary"]["runtime_config_mutation_allowed"] is False


def test_cron_run_rows_exclusive_cached_semantics() -> None:
    rows = ledger.cron_run_rows({
        "entries": [cron_entry({
            "input_tokens": 1000,
            "cache_read_tokens": 300,
            "output_tokens": 200,
            "total_tokens": 1500,
        })]
    }, TEST_PRICING)
    row = rows[0]
    assert row["input_token_semantics"] == "exclusive_cached"
    assert row["cached_input_tokens"] == 300
    assert row["cache_read_tokens"] == 300
    assert row["uncached_input_tokens"] == 1000
    assert row["token_semantics_status"] == "valid"
    assert abs(row["api_equivalent_cost_usd"] - 0.001672) < 0.000001


def test_cron_run_rows_no_cache_semantics() -> None:
    rows = ledger.cron_run_rows({
        "entries": [cron_entry({
            "input_tokens": 1000,
            "output_tokens": 200,
            "total_tokens": 1200,
        })]
    }, TEST_PRICING)
    row = rows[0]
    assert row["input_token_semantics"] == "no_cache"
    assert row["cached_input_tokens"] == 0
    assert row["uncached_input_tokens"] == 1000
    assert row["token_semantics_status"] == "valid"
    assert row["api_equivalent_cost_usd"] == 0.00165


def test_cost_estimator_resolves_aliases_and_long_context_rates() -> None:
    standard = ledger.estimate_cost(
        "openai/gpt-5.6-sol",
        272_000,
        0,
        0,
        TEST_PRICING,
        input_token_semantics="no_cache",
        token_semantics_status="valid",
    )
    long_context = ledger.estimate_cost(
        "openai-codex/gpt-5.6-sol",
        1_000_000,
        1_000_000,
        0,
        TEST_PRICING,
        input_token_semantics="no_cache",
        token_semantics_status="valid",
    )
    assert standard["api_equivalent_cost_usd"] == 1.36
    assert standard["pricing_context_class"] == "standard_context"
    assert long_context["api_equivalent_cost_usd"] == 55.0
    assert long_context["pricing_model_path"] == "openai/gpt-5.6-sol"
    assert long_context["pricing_resolution"] == "alias"
    assert long_context["pricing_context_class"] == "long_context"


def test_invalid_token_semantics_disable_cost_estimate() -> None:
    rows = ledger.cron_run_rows({
        "entries": [
            cron_entry({
                "input_tokens": 100,
                "cached_input_tokens": 200,
                "output_tokens": 10,
                "total_tokens": 110,
            }, run_id="cached-over-input"),
            cron_entry({
                "input_tokens": 100,
                "output_tokens": 10,
                "total_tokens": 120,
            }, run_id="inconsistent-total"),
        ]
    }, TEST_PRICING)
    for row in rows:
        assert row["token_semantics_status"] == "invalid"
        assert row["uncached_input_tokens"] is None
        assert row["api_equivalent_cost_usd"] is None
        assert row["cost"] is None
        assert row["cost_pricing_status"] == "invalid_token_semantics"
    assert rows[1]["token_total_delta"] == 10
    assert rows[1]["token_total_tolerance_tokens"] == 2


def test_conflicting_cache_fields_are_ambiguous_and_unpriced() -> None:
    rows = ledger.cron_run_rows({
        "entries": [cron_entry({
            "input_tokens": 1300,
            "cached_input_tokens": 300,
            "cache_read_tokens": 200,
            "output_tokens": 200,
            "total_tokens": 1500,
        })]
    }, TEST_PRICING)
    row = rows[0]
    assert row["input_token_semantics"] == "ambiguous"
    assert row["token_semantics_status"] == "ambiguous"
    assert row["uncached_input_tokens"] is None
    assert row["api_equivalent_cost_usd"] is None
    assert row["cost"] is None
    assert any("conflict" in reason for reason in row["token_semantics_reasons"])


def test_total_tolerance_allows_only_small_counter_drift() -> None:
    rows = ledger.cron_run_rows({
        "entries": [cron_entry({
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 112,
        })]
    }, TEST_PRICING)
    row = rows[0]
    assert row["token_semantics_status"] == "valid"
    assert row["token_total_delta"] == 2
    assert row["api_equivalent_cost_usd"] is not None


def test_cron_usage_timestamp_preserves_epoch_seconds_milliseconds_and_iso() -> None:
    rows = ledger.cron_run_rows({
        "entries": [
            cron_entry({"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, run_id="ms", ts=1_700_000_000_000),
            cron_entry({"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, run_id="seconds", ts="1700000000"),
            cron_entry({"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, run_id="iso", ts="2026-08-09T07:30:00-07:00"),
        ]
    }, TEST_PRICING)
    by_id = {row["run_id"]: row for row in rows}
    assert by_id["ms"]["usage_at_utc"] == "2023-11-14T22:13:20Z"
    assert by_id["ms"]["usage_time_source"] == "entry.ts_epoch_milliseconds"
    assert by_id["seconds"]["usage_at_utc"] == "2023-11-14T22:13:20Z"
    assert by_id["seconds"]["usage_time_source"] == "entry.ts_epoch_seconds"
    assert by_id["iso"]["usage_at_utc"] == "2026-08-09T14:30:00Z"
    assert by_id["iso"]["usage_time_source"] == "entry.ts_iso8601"
    assert ledger.row_observed_at(by_id["iso"]) == "2026-08-09T14:30:00Z"


def test_load_cron_runs_respects_query_budget_and_timeout_metadata() -> None:
    calls: list[tuple[tuple[str, ...], int]] = []

    def fake_run(args: list[str], timeout: int = 30) -> dict:
        calls.append((tuple(args), timeout))
        if args[:3] == ["cron", "list", "--json"]:
            return {
                "jobs": [
                    {"id": "job-1", "name": "Job 1", "enabled": True, "payload": {"kind": "agentTurn", "model": "gpt"}, "state": {"lastRunAtMs": 3}},
                    {"id": "job-2", "name": "Job 2", "enabled": True, "payload": {"kind": "agentTurn", "model": "gpt"}, "state": {"lastRunAtMs": 2}},
                    {"id": "job-3", "name": "Job 3", "enabled": True, "payload": {"kind": "agentTurn", "model": "gpt"}, "state": {"lastRunAtMs": 1}},
                ]
            }
        if args[3] == "job-1":
            return {"entries": [{"action": "finished", "jobId": "job-1"}]}
        return {"status": "timeout", "error_type": "timeout", "timeout_seconds": timeout, "error": "timed out"}

    original = ledger.run_openclaw_json
    ledger.run_openclaw_json = fake_run
    try:
        payload = ledger.load_cron_runs(job_limit=2, limit_per_job=2, list_timeout=7, runs_timeout=5)
    finally:
        ledger.run_openclaw_json = original

    assert payload["queried_job_count"] == 2
    assert payload["job_limit"] == 2
    assert payload["run_limit_per_job"] == 2
    assert payload["list_timeout_seconds"] == 7
    assert payload["runs_timeout_seconds"] == 5
    assert payload["error_count"] == 1
    assert payload["timeout_count"] == 1
    assert len(payload["entries"]) == 1
    assert calls == [
        (("cron", "list", "--json"), 7),
        (("cron", "runs", "--id", "job-1", "--limit", "2"), 5),
        (("cron", "runs", "--id", "job-2", "--limit", "2"), 5),
    ]


def test_cron_collection_errors_are_validation_warnings() -> None:
    payload = ledger.build_ledger({
        "runtime_perf": {},
        "otel_ops": {},
        "cron_spark_canary": {},
        "cron_runs": {
            "status": "warning",
            "entries": [],
            "selected_job_count": 1,
            "queried_job_count": 1,
            "error_count": 1,
            "timeout_count": 1,
            "errors": [{"job_id": "job-1", "error_type": "timeout"}],
            "skipped": False,
            "job_limit": 1,
            "run_limit_per_job": 1,
        },
        "lane_register": {},
        "pricing": {},
    })
    validation = ledger.validate(payload)
    details = [row["detail"] for row in validation["findings"]]
    assert validation["status"] == "warning"
    assert any("cron run history collection had errors or timeouts" in detail for detail in details)


def test_unsupported_fable_rows_are_auditable_but_not_capacity() -> None:
    payload = ledger.build_ledger({
        "runtime_perf": {},
        "otel_ops": {},
        "cron_spark_canary": {},
        "cron_runs": {"status": "ok", "entries": [], "selected_job_count": 0, "queried_job_count": 0, "error_count": 0, "timeout_count": 0},
        "lane_register": {
            "generated_at_utc": "2026-06-29T00:00:00Z",
            "lanes": [
                {
                    "lane_id": "WF73::legacy-fable",
                    "workflow_id": "WF73",
                    "workstream_id": "legacy-fable",
                    "status": "complete",
                    "started_at_utc": "2026-06-12T00:00:00Z",
                    "completed_at_utc": "2026-06-12T00:05:00Z",
                    "runtime": {
                        "model_path": "claude-cli/claude-fable-5",
                        "task_name": "legacy_fable_audit",
                    },
                }
            ],
        },
        "pricing": {},
    })
    summary = payload["summary"]
    row = payload["rows"][0]
    validation = ledger.validate(payload)
    assert row["model_support"]["status"] == "unsupported_legacy"
    assert row["model_support"]["active_route_countable"] is False
    assert summary["unsupported_legacy_model_rows"] == 1
    assert summary["supported_model_capacity_rows"] == 0
    assert validation["status"] == "warning"
    assert any("unsupported legacy model" in finding["detail"] for finding in validation["findings"])


if __name__ == "__main__":
    test_lane_register_rows_stamp_session_and_model_when_present()
    test_post_cutover_unverified_model_lane_is_audit_only()
    test_post_cutover_coherent_writable_receipt_stays_blocked_without_source_reopen()
    test_cron_run_rows_inclusive_cached_semantics()
    test_cron_run_rows_exclusive_cached_semantics()
    test_cron_run_rows_no_cache_semantics()
    test_invalid_token_semantics_disable_cost_estimate()
    test_conflicting_cache_fields_are_ambiguous_and_unpriced()
    test_total_tolerance_allows_only_small_counter_drift()
    test_cron_usage_timestamp_preserves_epoch_seconds_milliseconds_and_iso()
    test_load_cron_runs_respects_query_budget_and_timeout_metadata()
    test_cron_collection_errors_are_validation_warnings()
    test_unsupported_fable_rows_are_auditable_but_not_capacity()
    print("model_run_ledger_tests_passed")
