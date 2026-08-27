from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from current_window_artifact_index import build_index, parse_timestamp, status_from_data, window_completion_slo


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "run-chain.json"
        path.write_text("{}", encoding="utf-8")
        require(
            status_from_data(path, {"status": "completed_with_ticker_repairs"}) == "warning",
            "ticker-scoped containment must remain warning-grade in the artifact index",
        )
        require(
            status_from_data(path, {"status": "completed_with_systemic_data_quality"}) == "critical",
            "systemic containment must remain critical in the artifact index",
        )

    now = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)
    launcher = {"status": "launched", "launch_id": "launch-1", "generated_at_utc": "2026-08-10T20:20:00Z"}
    clean_runner = {
        "status": "ok",
        "launch_id": "launch-1",
        "generated_at_utc": "2026-08-10T20:40:00Z",
        "summary": {"run_chain_status": "ok", "run_summary_status": "ok"},
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "ok",
            "run_summary_status": "ok",
            "run_summary_run_id": "run-1",
        },
    }
    clean_chain = {"status": "ok", "completed_at_utc": "2026-08-10T20:39:00Z"}
    clean_summary = {"status": "ok", "run_id": "run-1", "generated_at_utc": "2026-08-10T20:39:00Z", "stop_line": False}
    clean = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=clean_runner,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(clean["state"] == "current_usable", "fresh terminal clean proof should be current usable")
    require(clean["correlation"]["runner_summary_matches_terminal_artifacts"], "runner/child status correlation required")
    require(clean["slo_met"] is True, "on-time correlated clean proof must meet the SLO")

    deduplicated_launcher = dict(launcher)
    deduplicated_launcher["status"] = "recent_success"
    deduplicated_launcher["result_artifact"] = {
        "exists": True,
        "status": "ok",
        "launch_id": "launch-1",
        "skip_chain": False,
    }
    deduplicated = window_completion_slo(
        "post-close", launcher=deduplicated_launcher, terminal_runner=clean_runner,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(deduplicated["state"] == "current_usable", "correlated recent-success dispatch must remain usable")
    require(deduplicated["correlation"]["dispatch_proven"] is True, "recent-success dispatch needs strict correlation")
    mismatched_deduplicated_launcher = dict(deduplicated_launcher)
    mismatched_deduplicated_launcher["result_artifact"] = dict(deduplicated_launcher["result_artifact"])
    mismatched_deduplicated_launcher["result_artifact"]["launch_id"] = "different-launch"
    mismatched_deduplicated = window_completion_slo(
        "post-close", launcher=mismatched_deduplicated_launcher, terminal_runner=clean_runner,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(mismatched_deduplicated["state"] == "invalid_or_uncorrelated_proof", "mismatched recent-success proof must fail closed")
    require(mismatched_deduplicated["correlation"]["recent_success_result_match"] is False, "nested recent-success mismatch must be visible")

    degraded_runner = {
        "status": "completed_with_ticker_repairs",
        "launch_id": "launch-1",
        "generated_at_utc": "2026-08-10T20:40:00Z",
        "summary": {
            "run_chain_status": "completed_with_ticker_repairs",
            "run_summary_status": "warning",
            "run_summary_data_quality_tickers": ["JPM"],
        },
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "completed_with_ticker_repairs",
            "run_summary_status": "warning",
            "run_summary_run_id": "run-1",
        },
    }
    degraded_payload = {"status": "completed_with_ticker_repairs", "completed_at_utc": "2026-08-10T20:39:00Z"}
    degraded_summary = {"status": "warning", "run_id": "run-1", "generated_at_utc": "2026-08-10T20:39:00Z", "stop_line": False}
    degraded = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=degraded_runner,
        run_chain=degraded_payload, run_summary=degraded_summary, now=now,
    )
    require(degraded["state"] == "current_degraded", "ticker-scoped completion should remain usable but degraded")
    require(degraded["current_degraded"] is True, "degraded state must be explicit")
    require(
        degraded["recommendation_usability"] == "blocked_ticker_scoped_pending_exclusion_and_freshness_proof",
        "ticker-scoped pipeline completion cannot imply broad recommendation usability",
    )
    require(degraded["affected_tickers"] == ["JPM"], "affected ticker exclusion set must remain explicit")
    require(degraded["affected_ticker_exclusion_proven"] is False, "observability cannot prove recommendation exclusion")

    failed_runner = {
        "status": "blocked",
        "launch_id": "launch-1",
        "generated_at_utc": "2026-08-10T20:40:00Z",
        "summary": {"run_chain_status": "completed_with_recovery", "run_summary_status": "blocked"},
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "completed_with_recovery",
            "run_summary_status": "blocked",
            "run_summary_run_id": "run-1",
        },
    }
    failed = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=failed_runner,
        run_chain={"status": "completed_with_recovery", "completed_at_utc": "2026-08-10T20:39:00Z"},
        run_summary={"status": "blocked", "run_id": "run-1", "generated_at_utc": "2026-08-10T20:39:00Z", "stop_line": True},
        now=now,
    )
    require(failed["state"] == "current_failed", "terminal child failure must override launcher success")
    require(failed["launcher_success_masks_failed_chain"] is True, "masked launcher success must be surfaced")
    require(failed["current_usable"] is False, "failed terminal proof cannot be current usable")

    systemic_runner = {
        "status": "completed_with_systemic_data_quality",
        "launch_id": "launch-1",
        "generated_at_utc": "2026-08-10T20:40:00Z",
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "completed_with_systemic_data_quality",
            "run_summary_status": "blocked",
            "run_summary_run_id": "run-1",
        },
    }
    systemic = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=systemic_runner,
        run_chain={"status": "completed_with_systemic_data_quality", "completed_at_utc": "2026-08-10T20:39:00Z"},
        run_summary={"status": "blocked", "run_id": "run-1", "generated_at_utc": "2026-08-10T20:39:00Z", "stop_line": True},
        now=now,
    )
    require(systemic["pipeline_completion"] == "completed", "systemic degradation can still complete independent pipeline work")
    require(systemic["recommendation_usability"] == "blocked_systemic", "systemic recommendation use must remain blocked")
    require(systemic["degradation_scope"] == "systemic", "systemic degradation scope must be explicit")

    mismatched_runner = dict(clean_runner)
    mismatched_runner["summary"] = {"run_chain_status": "blocked", "run_summary_status": "ok"}
    mismatched_runner["terminal_completion"] = dict(clean_runner["terminal_completion"])
    mismatched_runner["terminal_completion"]["run_chain_status"] = "blocked"
    mismatched = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=mismatched_runner,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(mismatched["state"] == "invalid_or_uncorrelated_proof", "mismatched child status cannot become usable")
    require(mismatched["correlation"]["proven"] is False, "status mismatch must fail correlation")

    conflicting_runner_sources = dict(clean_runner)
    conflicting_runner_sources["summary"] = {"run_chain_status": "blocked", "run_summary_status": "blocked"}
    conflicting_runner_sources["terminal_completion"] = dict(clean_runner["terminal_completion"])
    conflicting = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=conflicting_runner_sources,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(conflicting["state"] == "invalid_or_uncorrelated_proof", "conflicting nested runner status sources must fail closed")
    require(conflicting["correlation"]["runner_summary_matches_terminal_artifacts"] is False, "all populated status sources must agree")

    missing_launcher = window_completion_slo(
        "post-close", launcher=None, terminal_runner=clean_runner,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(missing_launcher["state"] == "invalid_or_uncorrelated_proof", "missing dispatch proof cannot become usable")
    require(missing_launcher["correlation"]["dispatch_proven"] is False, "missing launcher must fail dispatch correlation")

    wrong_launch = dict(clean_runner)
    wrong_launch["launch_id"] = "launch-2"
    wrong_launch["terminal_completion"] = dict(clean_runner["terminal_completion"])
    wrong_launch["terminal_completion"]["launch_id"] = "launch-2"
    launch_mismatch = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=wrong_launch,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(launch_mismatch["correlation"]["launch_id_match"] is False, "launch ID mismatch must fail closed")

    wrong_run_summary = dict(clean_summary)
    wrong_run_summary["run_id"] = "run-2"
    run_mismatch = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=clean_runner,
        run_chain=clean_chain, run_summary=wrong_run_summary, now=now,
    )
    require(run_mismatch["correlation"]["run_summary_id_match"] is False, "run ID mismatch must fail closed")

    skipped_runner = dict(clean_runner)
    skipped_runner["mode"] = {"skip_chain": True}
    skipped_runner["terminal_completion"] = dict(clean_runner["terminal_completion"])
    skipped_runner["terminal_completion"]["runner_executed_chain"] = False
    skipped = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=skipped_runner,
        run_chain=clean_chain, run_summary=clean_summary, now=now,
    )
    require(skipped["state"] == "invalid_or_uncorrelated_proof", "skip-chain observer rewrite is not terminal proof")
    require(skipped["correlation"]["terminal_runner_executed_chain"] is False, "skip-chain runner must be explicit")

    late_runner = {
        "status": "ok",
        "launch_id": "launch-1",
        "generated_at_utc": "2026-08-11T00:30:00Z",
        "summary": {"run_chain_status": "ok", "run_summary_status": "ok"},
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "ok",
            "run_summary_status": "ok",
            "run_summary_run_id": "run-1",
        },
    }
    late = window_completion_slo(
        "post-close", launcher=launcher, terminal_runner=late_runner,
        run_chain={"status": "ok", "completed_at_utc": "2026-08-11T00:29:00Z"},
        run_summary={"status": "ok", "run_id": "run-1", "generated_at_utc": "2026-08-11T00:29:00Z", "stop_line": False},
        now=datetime(2026, 8, 11, 1, 0, tzinfo=timezone.utc),
    )
    require(late["state"] == "completed_after_slo", "late clean completion must not pass the SLO")
    require(late["data_usability"] == "usable" and late["slo_met"] is False, "timeliness and data usability must be separate")

    future = window_completion_slo(
        "post-close", launcher=launcher,
        terminal_runner={"status": "ok", "launch_id": "launch-1", "generated_at_utc": "2026-08-11T04:00:00Z", "summary": {"run_chain_status": "ok", "run_summary_status": "ok"}, "terminal_completion": {"launch_id": "launch-1", "runner_executed_chain": True, "run_chain_status": "ok", "run_summary_status": "ok", "run_summary_run_id": "run-1"}},
        run_chain={"status": "ok", "completed_at_utc": "2026-08-11T04:00:00Z"},
        run_summary={"status": "ok", "run_id": "run-1", "generated_at_utc": "2026-08-11T04:00:00Z", "stop_line": False},
        now=now,
    )
    require(future["correlation"]["no_future_timestamps"] is False, "future proof must fail closed")
    require(future["state"] == "invalid_or_uncorrelated_proof", "future proof cannot become current usable")
    near_future = window_completion_slo(
        "post-close",
        launcher={**launcher, "generated_at_utc": "2026-08-11T00:00:01Z"},
        terminal_runner={**clean_runner, "generated_at_utc": "2026-08-11T00:00:01Z"},
        run_chain={"status": "ok", "completed_at_utc": "2026-08-11T00:00:01Z"},
        run_summary={"status": "ok", "run_id": "run-1", "generated_at_utc": "2026-08-11T00:00:01Z", "stop_line": False},
        now=now,
    )
    require(near_future["correlation"]["no_future_timestamps"] is False, "+1 second future proof must fail closed")
    require(parse_timestamp("2026-08-10T20:20:00") is None, "timezone-naive proof timestamps must be rejected")

    missed = window_completion_slo(
        "morning",
        launcher={"status": "launched", "generated_at_utc": "2026-08-10T13:05:00Z"},
        terminal_runner=None,
        run_chain=None,
        run_summary=None,
        now=datetime(2026, 8, 10, 18, 0, tzinfo=timezone.utc),
    )
    require(missed["state"] == "missed_after_deadline", "missing terminal result after deadline must miss the SLO")
    require(missed["launcher_success_masks_failed_chain"] is True, "launch-only success must not mask a missing terminal result")
    require(missed["authority"]["chain_rerun_allowed_by_this_surface"] is False, "SLO surface cannot grant rerun authority")

    post_close = build_index("full")
    require(post_close["window"] == "post-close", "full alias should normalize to post-close")
    authority = post_close.get("authority", {})
    for field in (
        "artifact_mutation_allowed_by_this_index",
        "trade_execution_allowed",
        "paper_trade_submit_cancel_allowed_by_this_index",
        "generated_report_is_canonical",
    ):
        require(authority.get(field) is False, f"{field} must stay fail-closed")
    for field in (
        "canonical_mutation_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "deployment_state_mutation_allowed",
        "owner_approval_granted",
    ):
        require(authority.get(field) is False, f"{field} must not be granted by an observability packet")
    require(
        authority.get("standing_context") == "main_session_may_hold_separate_bounded_validator_gated_workspace_maintenance_authority",
        "separate standing context must remain explicit without granting authority",
    )
    require(post_close["rendered_outputs"]["json"] == "tmp/current-window-artifacts.json", "stable JSON output path required")
    roles = {item["role"] for item in post_close["artifacts"]}
    require("run_summary" in roles, "run_summary role should be indexed")
    require("terminal_runner" in roles, "terminal runner role should be indexed")
    require("launcher" in roles, "launcher role should be indexed")
    require("full_portfolio_view" in roles, "post-close portfolio view should be indexed")
    require("capital_deployment_recommendations" in roles, "capital recommendation JSON role should be indexed")
    require("capital_deployment_recommendations_md" in roles, "capital recommendation Markdown role should be indexed")
    require("capital_deployment_recommendation_validation" in roles, "capital recommendation validator role should be indexed")
    require("goog_official_ir_capture" in roles, "official capture aliases should be indexed")
    require("goog_official_ir_capture_validation" in roles, "official capture validation aliases should be indexed")
    aliases = post_close.get("role_aliases", {})
    require(aliases.get("goog_official_ir_capture") == "tmp/official-ir-captures/goog-q1-2026.json", "GOOG alias should preserve current Q1 path")
    completion = post_close.get("window_completion_slo", {})
    require(completion.get("terminal_child_status_authoritative") is True, "terminal child must be authoritative")
    require(completion.get("scheduler_launcher_status_is_terminal") is False, "launcher must not be terminal proof")

    post_earnings = build_index("post-earnings")
    roles = {item["role"] for item in post_earnings["artifacts"]}
    require("post_earnings_prep" in roles, "post-earnings prep should be indexed")
    require("full_portfolio_view" not in roles, "post-earnings should not advertise non-produced portfolio view")
    print("current_window_artifact_index_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
