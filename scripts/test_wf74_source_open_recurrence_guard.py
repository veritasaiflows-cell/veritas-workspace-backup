from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf74_source_open_recurrence_guard as guard


def test_runner_order_has_alerts_boundary_before_quality_slice() -> None:
    order = guard.runner_order()
    assert order["alerts_os_boundary_present"] is True
    assert order["finance_response_quality_present"] is True
    assert order["boundary_before_quality"] is True
    assert order["alerts_os_boundary_blocking"] is True


def test_finance_taxonomy_is_alerts_only() -> None:
    taxonomy = guard.finance_taxonomy({
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {
            "alerts_os_answer_path_ok": True,
            "blocked_archetype_count": 0,
            "source_open_blocked_count": 0,
            "source_freshness_blocked_count": 0,
        },
    })
    assert taxonomy["alerts_os_answer_path_ok"] is True
    assert taxonomy["source_open_blocked_count"] == 0


def test_validation_blocks_missing_boundary() -> None:
    payload = {
        "runner_order": {
            "alerts_os_boundary_present": False,
            "finance_response_quality_present": True,
            "boundary_before_quality": False,
            "alerts_os_boundary_blocking": True,
        },
        "alerts_os_boundary_proof": {"status": "ok", "error_count": 0},
        "finance_taxonomy": {
            "finance_response_quality_status": "ok",
            "finance_response_quality_validation": "ok",
            "alerts_os_answer_path_ok": True,
            "blocked_archetype_count": 0,
            "source_open_blocked_count": 0,
            "source_freshness_blocked_count": 0,
        },
    }
    validation = guard.validate(payload)
    assert validation["status"] == "blocked"
    assert "missing_alerts_os_pivot_validator_step" in validation["errors"]


if __name__ == "__main__":
    test_runner_order_has_alerts_boundary_before_quality_slice()
    test_finance_taxonomy_is_alerts_only()
    test_validation_blocks_missing_boundary()
    print("wf74 alerts OS recurrence guard tests passed")
