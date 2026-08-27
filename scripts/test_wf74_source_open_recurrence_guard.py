from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf74_source_open_recurrence_guard as guard


def test_runner_order_has_source_open_orchestrator_before_quality_slice() -> None:
    order = guard.runner_order()

    assert order["source_open_orchestrator_present"] is True
    assert order["finance_response_quality_present"] is True
    assert order["source_open_before_quality"] is True
    assert order["source_open_orchestrator_blocking"] is True


def test_finance_taxonomy_requires_split_buckets_and_nonblocking_thin_monitor() -> None:
    packet = {
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {
            "source_open_blocked_count": 0,
            "source_freshness_blocked_count": 0,
            "primary_state_blocked_count": 2,
            "below_stop_blocked_count": 3,
            "tier_c_thin_monitor_non_blocking_count": 4,
            "scoped_thin_monitor_not_required_non_blocking_count": 5,
            "blocker_category_counts": {
                "source_open_blocked": 0,
                "source_freshness_blocked": 0,
                "primary_state_blocked": 2,
                "below_stop_blocked": 3,
                "tier_c_thin_monitor_non_blocking": 4,
                "scoped_thin_monitor_not_required_non_blocking": 5,
            },
            "scorecard_blocker_semantics": {
                "blocking_categories": ["source_freshness_blocked", "source_open_blocked"],
                "decision_readiness_categories": ["primary_state_blocked", "below_stop_blocked"],
                "non_blocking_categories": [
                    "tier_c_thin_monitor_non_blocking",
                    "scoped_thin_monitor_not_required_non_blocking",
                ],
            },
        },
    }

    taxonomy = guard.finance_taxonomy(packet)

    assert taxonomy["missing_blocker_buckets"] == []
    assert taxonomy["primary_state_blocked_count"] == 2
    assert taxonomy["below_stop_blocked_count"] == 3
    assert taxonomy["scoped_thin_monitor_not_required_non_blocking_count"] == 5
    assert taxonomy["source_open_recurrence_detected"] is False


def test_validation_blocks_missing_required_taxonomy() -> None:
    payload = {
        "runner_order": {
            "source_open_orchestrator_present": True,
            "finance_response_quality_present": True,
            "source_open_before_quality": True,
            "source_open_orchestrator_blocking": True,
        },
        "finance_taxonomy": {
            "missing_blocker_buckets": ["primary_state_blocked"],
            "blocking_categories": ["source_freshness_blocked", "source_open_blocked"],
            "decision_readiness_categories": ["below_stop_blocked"],
            "non_blocking_categories": ["tier_c_thin_monitor_non_blocking"],
        },
        "source_open_patch": {"exists": True, "validation": "ok"},
    }

    validation = guard.validate(payload)

    assert validation["status"] == "blocked"
    assert any("missing_blocker_buckets" in err for err in validation["errors"])
    assert "primary_state_blocked_not_decision_readiness" in validation["errors"]
    assert "scoped_thin_monitor_not_required_not_non_blocking" in validation["errors"]


if __name__ == "__main__":
    test_runner_order_has_source_open_orchestrator_before_quality_slice()
    test_finance_taxonomy_requires_split_buckets_and_nonblocking_thin_monitor()
    test_validation_blocks_missing_required_taxonomy()
    print("ok: wf74 source-open recurrence guard")
