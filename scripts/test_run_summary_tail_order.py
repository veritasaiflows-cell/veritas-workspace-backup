from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from chain_manifest import manifest_steps
from dashboard_run_summary_consumer import propagate_run_summary
from run_summary_refresh import build_run_summary, normalized_chain_status


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def script_order(window: str) -> list[str]:
    return [str(step.get("script") or "") for step in manifest_steps(window)]


def test_pipeline_consistency_precedes_run_summary(errors: list[str]) -> None:
    for window in ("morning", "post-close", "sunday"):
        order = script_order(window)
        expect("pipeline_state_consistency_check.py" in order, f"{window}: pipeline consistency check missing", errors)
        expect("run_summary_refresh.py" in order, f"{window}: run summary step missing", errors)
        if "pipeline_state_consistency_check.py" in order and "run_summary_refresh.py" in order:
            expect(
                order.index("pipeline_state_consistency_check.py") < order.index("run_summary_refresh.py"),
                f"{window}: pipeline consistency check must run before run_summary_refresh.py so final validation is reflected in the run summary",
                errors,
            )


def test_sql_canon_entry_stop_refresh_precedes_drift_gate(errors: list[str]) -> None:
    for window in ("morning", "post-close", "post-earnings", "sunday"):
        order = script_order(window)
        for script in ("canon_volatile_execution_board_sync.py", "sql_canon_field_family_preflight.py", "wf72_entry_stop_sql_activate.py", "canon_drift_freshness_gate.py"):
            expect(script in order, f"{window}: {script} missing from SQL-canon drift gate path", errors)
        if all(script in order for script in ("canon_volatile_execution_board_sync.py", "sql_canon_field_family_preflight.py", "wf72_entry_stop_sql_activate.py", "canon_drift_freshness_gate.py")):
            expect(
                order.index("canon_volatile_execution_board_sync.py")
                < order.index("sql_canon_field_family_preflight.py")
                < order.index("wf72_entry_stop_sql_activate.py")
                < order.index("canon_drift_freshness_gate.py"),
                f"{window}: WF72 SQL-canon entry/stop refresh must run after canon sync and before canon_drift_freshness_gate.py",
                errors,
            )


def test_regime_scoring_uses_fresh_trigger_state(errors: list[str]) -> None:
    for window in ("morning", "post-close", "sunday"):
        order = script_order(window)
        for script in ("deployment_check.py", "trigger_sheet_refresh.py", "regime_scoring_refresh.py"):
            expect(script in order, f"{window}: {script} missing", errors)
        if all(script in order for script in ("deployment_check.py", "trigger_sheet_refresh.py", "regime_scoring_refresh.py")):
            expect(
                order.index("deployment_check.py") < order.index("trigger_sheet_refresh.py") < order.index("regime_scoring_refresh.py"),
                f"{window}: regime scoring must run after fresh deployment/trigger state",
                errors,
            )


def test_pipeline_consistency_manifest_windows(errors: list[str]) -> None:
    expected_windows = {
        "morning": "morning",
        "post-close": "post-close",
        "sunday": "sunday",
        "full": "post-close",
    }
    for window, expected_window in expected_windows.items():
        steps = [step for step in manifest_steps(window) if step.get("script") == "pipeline_state_consistency_check.py"]
        expect(len(steps) == 1, f"{window}: expected exactly one pipeline consistency step, got {len(steps)}", errors)
        if not steps:
            continue
        args = list(steps[0].get("args") or [])
        expect(args == ["--window", expected_window], f"{window}: pipeline consistency step must pass explicit --window {expected_window}, got {args}", errors)
        expect("auto" not in args, f"{window}: scheduled manifest must not use manual/debug auto mode", errors)


def test_run_summary_post_tail(errors: list[str]) -> None:
    expected_tails = {
        "morning": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "daily_price_trend_signals.py",
            "market_intelligence_event_router.py",
            "sector_correlation_check.py",
            "sector_expansion_board.py",
            "watchlist_promotion_radar.py",
            "daily_review_objects.py",
            "portfolio_mutation_proposal_generator.py",
            "capital_deployment_recommendation_report.py",
            "capital_deployment_recommendation_validator.py",
            "probability_readiness_report.py",
            "probability_readiness_validator.py",
            "board_canon_guardrail.py",
            "stale_intelligence_guardrail.py",
            "canonical_note_patch_proposal.py",
            "full_portfolio_view.py",
            "full_portfolio_view_validate.py",
            "portfolio_snapshot_patch_proposal.py",
            "finance_discrepancy_resolver.py",
            "current_window_artifact_index.py",
            "artifact_index.py",
        ],
        "post-close": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "daily_price_trend_signals.py",
            "market_intelligence_event_router.py",
            "sector_correlation_check.py",
            "sector_expansion_board.py",
            "watchlist_promotion_radar.py",
            "daily_review_objects.py",
            "portfolio_mutation_proposal_generator.py",
            "capital_deployment_recommendation_report.py",
            "capital_deployment_recommendation_validator.py",
            "probability_readiness_report.py",
            "probability_readiness_validator.py",
            "board_canon_guardrail.py",
            "stale_intelligence_guardrail.py",
            "canonical_note_patch_proposal.py",
            "full_portfolio_view.py",
            "full_portfolio_view_validate.py",
            "portfolio_snapshot_patch_proposal.py",
            "finance_discrepancy_resolver.py",
            "proposal_patch_scope_validator.py",
            "canonical_status_invariant_validator.py",
            "portfolio_pro_forma_risk_validator.py",
            "authority_vocabulary_consistency_check.py",
            "post_apply_validation_chain.py",
            "state_history_capture.py",
            "current_window_artifact_index.py",
            "artifact_index.py",
        ],
        "post-earnings": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "daily_price_trend_signals.py",
            "market_intelligence_event_router.py",
            "daily_review_objects.py",
            "current_window_artifact_index.py",
            "artifact_index.py",
        ],
        "sunday": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "daily_price_trend_signals.py",
            "market_intelligence_event_router.py",
            "sector_correlation_check.py",
            "sector_expansion_board.py",
            "daily_review_objects.py",
            "portfolio_mutation_proposal_generator.py",
            "capital_deployment_recommendation_report.py",
            "capital_deployment_recommendation_validator.py",
            "probability_readiness_report.py",
            "probability_readiness_validator.py",
            "board_canon_guardrail.py",
            "stale_intelligence_guardrail.py",
            "canonical_note_patch_proposal.py",
            "full_portfolio_view.py",
            "full_portfolio_view_validate.py",
            "portfolio_snapshot_patch_proposal.py",
            "finance_discrepancy_resolver.py",
            "archive_suggester.py",
            "current_window_artifact_index.py",
            "artifact_index.py",
        ],
    }
    for window, expected in expected_tails.items():
        order = script_order(window)
        tail = order[order.index("run_summary_refresh.py"):]
        expect(
            tail == expected,
            f"{window}: expected final post-summary tail {expected}, got {tail}",
            errors,
        )


def test_success_tail_normalizes_terminal_state(errors: list[str]) -> None:
    chain_execution = {
        "status": "running",
        "recovery": {"triggered": False},
        "steps": [
            {"script": "validate_dashboard_state.py", "status": "ok"},
            {"script": "pipeline_state_consistency_check.py", "status": "ok"},
            {"script": "run_summary_refresh.py", "status": "running"},
            {"script": "dashboard_run_summary_consumer.py", "status": "pending"},
            {"script": "deployment_readiness_surface.py", "status": "pending"},
            {"script": "daily_price_trend_signals.py", "status": "pending"},
            {"script": "market_intelligence_event_router.py", "status": "pending"},
            {"script": "watchlist_promotion_radar.py", "status": "pending"},
            {"script": "daily_review_objects.py", "status": "pending"},
            {"script": "portfolio_mutation_proposal_generator.py", "status": "pending"},
            {"script": "capital_deployment_recommendation_report.py", "status": "pending"},
            {"script": "capital_deployment_recommendation_validator.py", "status": "pending"},
            {"script": "probability_readiness_report.py", "status": "pending"},
            {"script": "probability_readiness_validator.py", "status": "pending"},
            {"script": "board_canon_guardrail.py", "status": "pending"},
            {"script": "stale_intelligence_guardrail.py", "status": "pending"},
            {"script": "canonical_note_patch_proposal.py", "status": "pending"},
            {"script": "full_portfolio_view.py", "status": "pending"},
            {"script": "full_portfolio_view_validate.py", "status": "pending"},
            {"script": "portfolio_snapshot_patch_proposal.py", "status": "pending"},
            {"script": "finance_discrepancy_resolver.py", "status": "pending"},
            {"script": "current_window_artifact_index.py", "status": "pending"},
            {"script": "artifact_index.py", "status": "pending"},
        ],
    }
    status, reason, normalized = normalized_chain_status(chain_execution)
    expect(status == "ok", f"successful post-summary tail should normalize to ok, got {status}", errors)
    expect(normalized is True, "successful post-summary tail should normalize terminal state", errors)
    expect("finalizer self-observation" in reason, f"unexpected normalization reason: {reason}", errors)


def test_run_summary_contract_fields(errors: list[str]) -> None:
    summary = build_run_summary("morning")
    expect(isinstance(summary.get("operator_action_required"), list), "run summary must emit operator_action_required as a list", errors)
    expect("next_action" in summary and isinstance(summary.get("next_action"), str), "run summary must emit next_action as a string", errors)
    if isinstance(summary.get("operator_action_required"), list):
        expect(all(isinstance(item, str) and item.strip() for item in summary["operator_action_required"]), "operator_action_required entries must be non-empty strings", errors)
    if summary.get("status") in {"blocked", "warning", "error"}:
        expect(bool(str(summary.get("next_action") or "").strip()), "non-ok run summaries must name a concrete next_action", errors)


def test_run_summary_downstream_authority_fail_closed(errors: list[str]) -> None:
    for window in ("morning", "post-close", "post-earnings", "sunday"):
        downstream = build_run_summary(window).get("downstream") or {}
        expect(downstream.get("canonical_note_mutation_allowed") is False, f"{window}: canonical note mutation must remain disabled", errors)
        expect(downstream.get("presentation_allowed") is False, f"{window}: presentation must remain disabled", errors)


def test_run_summary_surfaces_sql_artifact_index_health(errors: list[str]) -> None:
    summary = build_run_summary("post-close")
    artifact_index = summary.get("artifact_index") or {}
    expect(isinstance(artifact_index, dict), "run summary must include derived SQL artifact_index health", errors)
    expect(artifact_index.get("enabled") is True, "artifact_index health must be enabled", errors)
    expect(
        artifact_index.get("authority_boundary") == "derived_review_only_index_not_canon_not_apply",
        "artifact_index health must preserve derived/review-only/non-apply boundary",
        errors,
    )
    expect("checks" in artifact_index, "artifact_index health must include validation check summary", errors)
    expect("safety_counts" in artifact_index, "artifact_index health must include safety counts", errors)
    expect("drift_fingerprint_tables" in artifact_index, "artifact_index health must expose drift fingerprint coverage", errors)


def test_dashboard_consumer_propagates_sql_artifact_index_health(errors: list[str]) -> None:
    summary = build_run_summary("post-close")
    payload = {"trust": {"existing": True}, "ui": {"alerts": []}}
    propagated = propagate_run_summary(payload, summary)
    trust = propagated.get("trust") or {}
    artifact_index = trust.get("artifact_index") or {}
    summary_artifact_index = summary.get("artifact_index") or {}
    expect(trust.get("existing") is True, "dashboard run-summary propagation must preserve existing trust fields", errors)
    expect(artifact_index.get("status") == summary_artifact_index.get("status"), "dashboard trust must mirror SQL artifact-index status", errors)
    expect(
        artifact_index.get("authority_boundary") == "derived_review_only_index_not_canon_not_apply",
        "dashboard artifact-index trust must preserve derived/review-only/non-apply boundary",
        errors,
    )
    expect("safety_counts" in artifact_index, "dashboard artifact-index trust must include safety counts", errors)
    expect("drift_fingerprint_tables" in artifact_index, "dashboard artifact-index trust must include drift fingerprint coverage", errors)

    degraded_summary = {
        "window": "post-close",
        "status": "ok",
        "execution": {"chain_status": "ok", "chain_status_normalized": True},
        "downstream": {"presentation_allowed": False, "canonical_note_mutation_allowed": False},
        "artifact_index": {
            "enabled": True,
            "status": "warning",
            "operator_action_required": True,
            "authority_boundary": "derived_review_only_index_not_canon_not_apply",
            "operator_next_action": "Run python scripts/artifact_index.py incremental, then validate.",
            "safety_counts": {"forbidden_true_authority_flags": 0},
            "checks": {"failed": 1},
            "drift_fingerprint_tables": 15,
        },
    }
    degraded = propagate_run_summary({"ui": {"alerts": []}}, degraded_summary)
    alerts = ((degraded.get("ui") or {}).get("alerts") or [])
    first_alert = alerts[0] if alerts else {}
    expect(first_alert.get("tone") == "warn", "degraded SQL artifact-index health should warn in dashboard alert", errors)
    expect(
        "Derived SQL artifact-index health needs attention" in str(first_alert.get("detail") or ""),
        "dashboard alert must explain degraded SQL artifact-index health",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    test_pipeline_consistency_precedes_run_summary(errors)
    test_sql_canon_entry_stop_refresh_precedes_drift_gate(errors)
    test_regime_scoring_uses_fresh_trigger_state(errors)
    test_pipeline_consistency_manifest_windows(errors)
    test_run_summary_post_tail(errors)
    test_success_tail_normalizes_terminal_state(errors)
    test_run_summary_contract_fields(errors)
    test_run_summary_downstream_authority_fail_closed(errors)
    test_run_summary_surfaces_sql_artifact_index_health(errors)
    test_dashboard_consumer_propagates_sql_artifact_index_health(errors)
    if errors:
        print("run_summary_tail_order_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("run_summary_tail_order_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
