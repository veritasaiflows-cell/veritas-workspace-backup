#!/usr/bin/env python3
"""Targeted tests for review-only same-day ticker repair classification."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ticker_data_repair_controller.py"
FIXED_TIME = "2026-08-10T19:00:00Z"


def load_module():
    spec = importlib.util.spec_from_file_location("ticker_data_repair_controller", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repair(ticker: str, fingerprint: str, *, code: str = "bank_official_capital_period_mismatch") -> dict:
    return {
        "fingerprint": fingerprint,
        "ticker": ticker,
        "code": code,
        "severity": "critical",
        "classification": "bank_capital_period_metadata_reconciliation_required",
        "status": "repair_required",
        "deduplicated_finding_count": 3,
        "blocks_ticker_only": True,
        "source_open_required": True,
        "manual_review_required": True,
        "next_action": f"Source-open {ticker} official filing before revalidation.",
        "evidence": {"local_period_end": "2026-06-30", "official_period": "2026-03-31"},
    }


def inputs(*, repairs: list[dict] | None = None, quote_snapshots: list[dict] | None = None) -> dict:
    repairs = repairs or []
    return {
        "fundamentals": {"repair_queue": deepcopy(repairs)},
        "warning_router": {"sections": {"fundamentals": {"repair_queue": deepcopy(repairs)}}},
        "quote_proof": {"status": "ok", "snapshots": deepcopy(quote_snapshots or [])},
        "quote_validation": {"status": "ok"},
        "source_present": {
            "fundamentals": True,
            "warning_router": True,
            "quote_proof": True,
            "quote_validation": True,
        },
        "source_warnings": [],
    }


def build(module, payload: dict, **kwargs) -> dict:
    return module.build_report(
        **payload,
        generated_at_utc=FIXED_TIME,
        **kwargs,
    )


def test_zero_tickers_is_no_action() -> None:
    module = load_module()
    report = build(module, inputs())
    assert report["status"] == "no_action", report
    assert report["classification"] == "no_action", report
    assert report["summary"]["ticker_count"] == 0, report
    assert report["summary"]["unrelated_chain_work_can_remain_complete"] is True, report
    assert report["execution_record"]["quote_proof_recheck"]["attempted"] is False, report
    assert report["validation"]["status"] == "ok", report


def test_one_ticker_is_scoped_and_deduplicated() -> None:
    module = load_module()
    report = build(module, inputs(repairs=[repair("jpm", "jpm-period"), repair("JPM", "jpm-period")]))
    assert report["classification"] == "ticker_scoped_repair", report
    assert report["summary"]["ticker_count"] == 1, report
    assert report["summary"]["tickers"] == ["JPM"], report
    assert len(report["repair_queue"]) == 1, report
    item = report["repair_queue"][0]
    assert item["repair_mode"] == "manual_source_open_and_revalidate", item
    assert item["automatic_fundamental_repair_allowed"] is False, item
    assert item["source_open_required"] is True, item
    assert report["summary"]["chain_completion_posture"] == "completed_with_ticker_repairs", report
    assert report["validation"]["status"] == "ok", report


def test_fundamental_repair_is_manual_source_open_even_if_upstream_flags_are_missing() -> None:
    module = load_module()
    upstream = repair("JPM", "jpm-period")
    upstream["source_open_required"] = False
    upstream["manual_review_required"] = False
    report = build(module, inputs(repairs=[upstream]))
    item = report["repair_queue"][0]
    assert item["source_open_required"] is True, item
    assert item["manual_review_required"] is True, item
    assert item["repair_mode"] == "manual_source_open_and_revalidate", item
    assert report["validation"]["status"] == "ok", report


def test_two_distinct_tickers_are_systemic() -> None:
    module = load_module()
    report = build(module, inputs(repairs=[repair("JPM", "jpm-period"), repair("GS", "gs-period")]))
    assert report["classification"] == "systemic_data_quality", report
    assert report["summary"]["ticker_count"] == 2, report
    assert report["summary"]["tickers"] == ["GS", "JPM"], report
    assert report["summary"]["systemic_data_quality"] is True, report
    assert report["summary"]["unrelated_chain_work_can_remain_complete"] is True, report
    assert report["summary"]["same_day_cadence"]["cadence_minutes"] == 15, report
    assert report["summary"]["same_day_cadence"]["cron_expression_recommendation"] == "*/15 6-13 * * 1-5", report
    assert "post-close reconciliation" in report["summary"]["same_day_cadence"]["regular_market_window_local"], report
    assert report["validation"]["status"] == "ok", report


def test_two_stale_quote_tickers_are_systemic_and_safe_to_recheck() -> None:
    module = load_module()
    report = build(module, inputs(quote_snapshots=[
        {"symbol": "AAA", "freshness_status": "stale", "calendar_freshness_status": "stale_unexpected"},
        {"symbol": "BBB", "freshness_status": "current_but_not_intraday_fresh", "calendar_freshness_status": "provider_missing"},
    ]))
    assert report["classification"] == "systemic_data_quality", report
    assert report["summary"]["quote_freshness_tickers"] == ["AAA", "BBB"], report
    assert all(item["repair_mode"] == "safe_quote_proof_recheck_only" for item in report["repair_queue"]), report
    assert report["execution_record"]["quote_proof_recheck"]["attempted"] is False, report
    assert report["validation"]["status"] == "ok", report


def test_closed_market_current_last_completed_quotes_do_not_create_false_repairs() -> None:
    module = load_module()
    report = build(module, inputs(quote_snapshots=[
        {"symbol": "AAA", "freshness_status": "current_but_not_intraday_fresh", "calendar_freshness_status": "current_last_completed_session"},
        {"symbol": "BBB", "freshness_status": "stale", "calendar_freshness_status": "market_closed_expected_stale"},
    ]))
    assert report["classification"] == "no_action", report
    assert report["summary"]["quote_freshness_tickers"] == [], report
    assert report["validation"]["status"] == "ok", report


def test_no_fundamental_mutation_or_execution_without_explicit_safe_flag() -> None:
    module = load_module()
    payload = inputs(repairs=[repair("JPM", "jpm-period")])
    before = deepcopy(payload)
    called = {"count": 0}

    def should_not_run() -> dict:
        called["count"] += 1
        raise AssertionError("safe quote recheck ran without --execute-safe")

    report = build(module, payload, quote_recheck_runner=should_not_run)
    assert payload == before, "controller mutated its source inputs"
    assert called["count"] == 0
    assert report["execution_record"]["fundamental_source_mapping_mutated"] is False, report
    assert report["execution_record"]["canonical_or_portfolio_mutated"] is False, report
    assert report["execution_record"]["trade_or_account_action"] is False, report
    assert report["authority_boundary"]["fundamental_auto_repair_or_apply_allowed"] is False, report
    assert report["validation"]["status"] == "ok", report


def test_safe_quote_recheck_requires_explicit_flag() -> None:
    module = load_module()
    called = {"count": 0}

    def fake_recheck() -> dict:
        called["count"] += 1
        return {"requested": True, "attempted": True, "ok": True, "command": "safe proof recheck"}

    report = build(module, inputs(quote_snapshots=[
        {"symbol": "AAA", "freshness_status": "stale", "calendar_freshness_status": "stale_unexpected"},
    ]), execute_safe=True, quote_recheck_runner=fake_recheck)
    assert called["count"] == 1
    assert report["execution_record"]["quote_proof_recheck"]["attempted"] is True, report
    assert report["execution_record"]["fundamental_action"] == "none", report
    reclassification = report["summary"]["quote_recheck_reclassification"]
    assert reclassification["same_invocation_reload"] is False, reclassification
    assert reclassification["next_cadence_reclassification_minutes"] == 15, reclassification
    assert "quote_recheck_completed_reclassification_deferred_to_next_cadence" in report["warnings"], report
    assert report["validation"]["status"] == "ok", report


def test_safe_quote_recheck_skips_when_no_quote_issue_exists() -> None:
    module = load_module()
    called = {"count": 0}

    def should_not_run() -> dict:
        called["count"] += 1
        raise AssertionError("quote recheck should be bounded to quote-freshness issues")

    report = build(module, inputs(repairs=[repair("JPM", "jpm-period")]), execute_safe=True, quote_recheck_runner=should_not_run)
    assert called["count"] == 0
    recheck = report["execution_record"]["quote_proof_recheck"]
    assert recheck["requested"] is True and recheck["attempted"] is False and recheck["skipped"] is True, recheck
    assert report["validation"]["status"] == "ok", report


def in_band_attention_inputs() -> dict:
    payload = inputs(quote_snapshots=[
        {
            "symbol": "CAT",
            "price": 100.0,
            "freshness_status": "fresh",
            "calendar_freshness_status": "fresh_intraday",
            "age_seconds": 20,
            "source_timestamp_utc": FIXED_TIME,
        },
    ])
    payload["quote_proof"]["generated_at_utc"] = FIXED_TIME
    payload.update({
        "band_proposals": {
            "status": "needs_review",
            "rows": [{"ticker": "CAT", "current_band_low": 90.0, "current_band_high": 110.0, "current_stop": 80.0}],
        },
        "auto_router": {
            "status": "ok",
            "generated_at_utc": FIXED_TIME,
            "rows": [{"ticker": "CAT", "auto_tier": "Tier B", "auto_state": "B-CANDIDATE"}],
        },
        "band_hygiene": {"status": "ok", "generated_at_utc": "2026-08-10T18:50:00Z"},
        "decision_sync": {"status": "ok", "generated_at_utc": "2026-08-10T18:50:00Z"},
        "prior_review_attention": {},
    })
    return payload


def test_fresh_in_band_quote_runs_same_invocation_review_sync() -> None:
    called = {"count": 0}

    def fake_review_sync() -> dict:
        called["count"] += 1
        return {"requested": True, "attempted": True, "ok": True, "steps": [{"name": "bridge", "ok": True}]}

    def fresh_attention() -> dict:
        return {
            "status": "ok",
            "summary": {
                "review_attention_count": 1,
                "review_attention_tickers": ["CAT"],
                "repair_attention_count": 0,
                "repair_attention_tickers": [],
                "attention_fingerprint": "cat-main-review-v1",
            },
        }

    report = build(
        load_module(),
        in_band_attention_inputs(),
        execute_safe=True,
        review_sync_runner=fake_review_sync,
        review_attention_reader=fresh_attention,
    )
    assert called["count"] == 1, report
    assert report["classification"] == "in_band_review_attention", report
    assert report["status"] == "warning", report
    attention = report["summary"]["in_band_review_attention"]
    assert attention["trigger_tickers"] == ["CAT"], attention
    assert attention["same_invocation_reload"] is True, attention
    assert attention["attention_new_or_changed"] is True, attention
    assert report["execution_record"]["capital_deployment_approved"] is False, report
    assert report["execution_record"]["trade_or_execution_approved"] is False, report
    assert report["validation"]["status"] == "ok", report


def test_same_in_band_attention_refresh_is_quiet() -> None:
    payload = in_band_attention_inputs()
    payload["prior_review_attention"] = {
        "generated_at_utc": "2026-08-10T18:50:00Z",
        "summary": {"attention_fingerprint": "cat-main-review-v1"},
    }

    def fake_review_sync() -> dict:
        return {"requested": True, "attempted": True, "ok": True, "steps": [{"name": "bridge", "ok": True}]}

    def same_attention() -> dict:
        return {
            "status": "ok",
            "summary": {
                "review_attention_count": 1,
                "review_attention_tickers": ["CAT"],
                "repair_attention_count": 0,
                "repair_attention_tickers": [],
                "attention_fingerprint": "cat-main-review-v1",
            },
        }

    report = build(
        load_module(),
        payload,
        execute_safe=True,
        review_sync_runner=fake_review_sync,
        review_attention_reader=same_attention,
    )
    assert report["classification"] == "no_action", report
    assert report["status"] == "no_action", report
    assert report["summary"]["in_band_review_attention"]["attention_new_or_changed"] is False, report


def test_non_ok_current_review_artifacts_force_sync_and_are_not_silent() -> None:
    payload = in_band_attention_inputs()
    payload["band_hygiene"] = {"status": "blocked", "generated_at_utc": FIXED_TIME}
    payload["decision_sync"] = {"status": "blocked", "generated_at_utc": FIXED_TIME}
    payload["prior_review_attention"] = {"status": "blocked", "generated_at_utc": FIXED_TIME}
    called = {"count": 0}

    def failed_review_sync() -> dict:
        called["count"] += 1
        return {"requested": True, "attempted": True, "ok": False, "steps": [{"name": "bridge", "ok": False}]}

    report = build(
        load_module(),
        payload,
        execute_safe=True,
        review_sync_runner=failed_review_sync,
    )
    assert called["count"] == 1, report
    sync = report["execution_record"]["in_band_review_sync"]
    assert "band_hygiene_status_not_ok:blocked" in sync["trigger_reasons"], sync
    assert "decision_sync_status_not_ok:blocked" in sync["trigger_reasons"], sync
    assert report["classification"] == "in_band_review_sync_degraded", report
    assert report["status"] == "warning", report
    assert report["summary"]["in_band_review_attention"]["sync_degraded"] is True, report
    assert "review_attention_sync_not_clean" in report["warnings"], report
    assert report["validation"]["status"] == "ok", report


def test_non_ok_quote_or_router_proof_forces_sync_and_is_not_silent() -> None:
    for source_key, reason in (
        ("quote_proof", "quote_proof_status_not_ok:blocked"),
        ("auto_router", "tier_router_status_not_ok:blocked"),
    ):
        payload = in_band_attention_inputs()
        payload["quote_proof"]["generated_at_utc"] = FIXED_TIME
        payload["band_hygiene"]["generated_at_utc"] = FIXED_TIME
        payload["decision_sync"]["generated_at_utc"] = FIXED_TIME
        payload["prior_review_attention"] = {"status": "ok", "generated_at_utc": FIXED_TIME, "summary": {}}
        payload[source_key]["status"] = "blocked"
        called = {"count": 0}

        def failed_review_sync() -> dict:
            called["count"] += 1
            return {"requested": True, "attempted": True, "ok": False, "steps": [{"name": "bridge", "ok": False}]}

        report = build(
            load_module(),
            payload,
            execute_safe=True,
            review_sync_runner=failed_review_sync,
        )
        assert called["count"] == 1, report
        sync = report["execution_record"]["in_band_review_sync"]
        assert reason in sync["trigger_reasons"], sync
        assert report["classification"] == "in_band_review_sync_degraded", report
        assert report["status"] == "warning", report
        assert "review_attention_sync_not_clean" in report["warnings"], report
        assert report["validation"]["status"] == "ok", report


def test_stale_router_proof_forces_sync_and_is_not_silent() -> None:
    payload = in_band_attention_inputs()
    payload["auto_router"]["generated_at_utc"] = "2026-08-09T18:00:00Z"
    payload["prior_review_attention"] = {"status": "ok", "generated_at_utc": FIXED_TIME, "summary": {}}
    called = {"count": 0}

    def failed_review_sync() -> dict:
        called["count"] += 1
        return {"requested": True, "attempted": True, "ok": False, "steps": [{"name": "bridge", "ok": False}]}

    report = build(
        load_module(),
        payload,
        execute_safe=True,
        review_sync_runner=failed_review_sync,
    )
    assert called["count"] == 1, report
    sync = report["execution_record"]["in_band_review_sync"]
    assert "tier_router_not_current_for_quote_proof" in sync["trigger_reasons"], sync
    assert report["classification"] == "in_band_review_sync_degraded", report
    assert report["validation"]["status"] == "ok", report


def test_in_band_review_sync_never_runs_without_execute_safe() -> None:
    def should_not_run() -> dict:
        raise AssertionError("review sync ran without --execute-safe")

    report = build(
        load_module(),
        in_band_attention_inputs(),
        review_sync_runner=should_not_run,
    )
    assert report["execution_record"]["in_band_review_sync"]["attempted"] is False, report
    assert report["classification"] == "in_band_review_sync_degraded", report
    assert report["status"] == "warning", report
    assert "review_attention_sync_requires_execute_safe" in report["warnings"], report


def test_review_sync_autonomously_refreshes_review_only_overlay_evidence_and_queue() -> None:
    module = load_module()
    seen: list[tuple[str, list[str]]] = []

    def fake_runner(name: str, command: list[str], timeout: int) -> dict:
        seen.append((name, command))
        return {"name": name, "ok": True, "returncode": 0, "timeout_seconds": timeout}

    def attention() -> dict:
        return {
            "status": "ok",
            "review_attention": [{"ticker": "CAT"}],
            "repair_attention": [{"ticker": "GOOG"}],
        }

    def overlay() -> dict:
        return {
            "status": "ok",
            "validation": {"status": "ok"},
            "rows": [
                {
                    "ticker": "GOOG",
                    "current_price": {
                        "quote_freshness_status": "intraday_review_only_fresh",
                        "review_only_quote": True,
                        "approval_draft_eligible": False,
                    },
                    "source_freshness": {"fresh_for_review": True, "fresh_for_approval": False},
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "paper_or_live_execution_allowed": False,
                },
                {
                    "ticker": "CAT",
                    "current_price": {
                        "quote_freshness_status": "intraday_review_only_fresh",
                        "review_only_quote": True,
                        "approval_draft_eligible": False,
                    },
                    "source_freshness": {"fresh_for_review": True, "fresh_for_approval": False},
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "paper_or_live_execution_allowed": False,
                },
            ],
        }

    result = module.run_review_sync(fake_runner, attention, overlay)
    names = [name for name, _ in seen]
    assert names == [
        "band_hygiene_from_current_quote_proof",
        "finance_decision_sync",
        "in_band_review_attention_bridge",
        "wf85_intraday_review_overlay",
        "targeted_ticker_card_evidence_refresh",
        "wf85_opportunity_visibility_queue",
    ], result
    evidence_command = dict(seen)["targeted_ticker_card_evidence_refresh"]
    assert evidence_command[evidence_command.index("--tickers") + 1:evidence_command.index("--skip-provider-refresh")] == ["CAT", "GOOG"], evidence_command
    assert "--skip-provider-refresh" in evidence_command, evidence_command
    assert evidence_command[evidence_command.index("--full-answer-mode") + 1] == "never", evidence_command
    assert all("trade_grade_decision_cards.py" not in command for _, command in seen), seen
    assert all("wf85_deployment_timing_gate.py" not in command for _, command in seen), seen
    assert result["ok"] is True, result
    assert result["overlay_tickers"] == ["CAT", "GOOG"], result
    assert result["evidence_refresh_tickers"] == ["CAT", "GOOG"], result


def test_review_sync_failure_still_rebuilds_degraded_visibility_queue() -> None:
    module = load_module()
    seen: list[str] = []

    def fake_runner(name: str, command: list[str], timeout: int) -> dict:
        seen.append(name)
        return {"name": name, "ok": name != "wf85_intraday_review_overlay", "returncode": 1 if name == "wf85_intraday_review_overlay" else 0}

    result = module.run_review_sync(fake_runner, lambda: {"status": "ok"}, lambda: {})
    assert result["ok"] is False, result
    assert "targeted_ticker_card_evidence_refresh" in [step["name"] for step in result["steps"]], result
    assert "wf85_opportunity_visibility_queue" in seen, result
    evidence = next(step for step in result["steps"] if step["name"] == "targeted_ticker_card_evidence_refresh")
    assert evidence["skipped"] is True and evidence["ok"] is False, result


def test_quiet_execute_safe_cadence_refreshes_visibility_queue_for_overlay_expiry() -> None:
    module = load_module()
    called = {"count": 0}

    def queue_refresh() -> dict:
        called["count"] += 1
        return {"name": "wf85_opportunity_visibility_queue", "attempted": True, "ok": True}

    report = build(
        module,
        inputs(),
        execute_safe=True,
        visibility_queue_refresh_runner=queue_refresh,
    )
    sync = report["execution_record"]["in_band_review_sync"]
    assert called["count"] == 1, report
    assert sync["skipped"] is True, sync
    assert sync["visibility_queue_refresh_attempted"] is True, sync
    assert sync["visibility_queue_status"] is True, sync
    assert report["classification"] == "no_action", report
    assert report["validation"]["status"] == "ok", report


def test_quiet_execute_safe_queue_failure_is_visible_not_no_action() -> None:
    module = load_module()

    def failed_queue_refresh() -> dict:
        return {"name": "wf85_opportunity_visibility_queue", "attempted": True, "ok": False, "returncode": 1}

    report = build(
        module,
        inputs(),
        execute_safe=True,
        visibility_queue_refresh_runner=failed_queue_refresh,
    )
    sync = report["execution_record"]["in_band_review_sync"]
    assert sync["visibility_queue_refresh_attempted"] is True, sync
    assert sync["visibility_queue_status"] is False, sync
    assert report["classification"] == "in_band_review_sync_degraded", report
    assert "review_visibility_queue_not_clean" in report["warnings"], report
    assert report["validation"]["status"] == "ok", report


def test_missing_sources_are_transparent_no_action_warning() -> None:
    module = load_module()
    report = module.build_report(
        fundamentals={},
        warning_router={},
        quote_proof={},
        quote_validation={},
        source_present={"fundamentals": False, "warning_router": False, "quote_proof": False, "quote_validation": False},
        source_warnings=["missing_source:fundamentals:tmp/fundamental-metrics-validation.json"],
        generated_at_utc=FIXED_TIME,
    )
    assert report["status"] == "warning", report
    assert report["classification"] == "no_action", report
    assert report["summary"]["ticker_count"] == 0, report
    assert report["warnings"], report
    assert report["validation"]["status"] == "ok", report


def main() -> int:
    test_zero_tickers_is_no_action()
    test_one_ticker_is_scoped_and_deduplicated()
    test_fundamental_repair_is_manual_source_open_even_if_upstream_flags_are_missing()
    test_two_distinct_tickers_are_systemic()
    test_two_stale_quote_tickers_are_systemic_and_safe_to_recheck()
    test_closed_market_current_last_completed_quotes_do_not_create_false_repairs()
    test_no_fundamental_mutation_or_execution_without_explicit_safe_flag()
    test_safe_quote_recheck_requires_explicit_flag()
    test_safe_quote_recheck_skips_when_no_quote_issue_exists()
    test_fresh_in_band_quote_runs_same_invocation_review_sync()
    test_same_in_band_attention_refresh_is_quiet()
    test_non_ok_current_review_artifacts_force_sync_and_are_not_silent()
    test_non_ok_quote_or_router_proof_forces_sync_and_is_not_silent()
    test_stale_router_proof_forces_sync_and_is_not_silent()
    test_in_band_review_sync_never_runs_without_execute_safe()
    test_review_sync_autonomously_refreshes_review_only_overlay_evidence_and_queue()
    test_review_sync_failure_still_rebuilds_degraded_visibility_queue()
    test_quiet_execute_safe_cadence_refreshes_visibility_queue_for_overlay_expiry()
    test_quiet_execute_safe_queue_failure_is_visible_not_no_action()
    test_missing_sources_are_transparent_no_action_warning()
    print("ticker_data_repair_controller targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
