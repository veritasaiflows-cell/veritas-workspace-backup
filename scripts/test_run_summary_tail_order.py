from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from chain_manifest import manifest_steps
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


def test_run_summary_post_tail(errors: list[str]) -> None:
    expected_tails = {
        "morning": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "market_intelligence_event_router.py",
            "daily_review_objects.py",
        ],
        "post-close": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "market_intelligence_event_router.py",
            "daily_review_objects.py",
        ],
        "post-earnings": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "market_intelligence_event_router.py",
            "daily_review_objects.py",
        ],
        "sunday": [
            "run_summary_refresh.py",
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "market_intelligence_event_router.py",
            "daily_review_objects.py",
        ],
    }
    for window, expected in expected_tails.items():
        order = script_order(window)
        tail = order[-len(expected):]
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
            {"script": "market_intelligence_event_router.py", "status": "pending"},
            {"script": "daily_review_objects.py", "status": "pending"},
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


def main() -> int:
    errors: list[str] = []
    test_pipeline_consistency_precedes_run_summary(errors)
    test_run_summary_post_tail(errors)
    test_success_tail_normalizes_terminal_state(errors)
    test_run_summary_contract_fields(errors)
    if errors:
        print("run_summary_tail_order_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("run_summary_tail_order_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
