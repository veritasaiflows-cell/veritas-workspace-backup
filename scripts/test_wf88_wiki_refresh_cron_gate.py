from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf88_wiki_refresh_cron_gate as gate


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def paths(base: Path) -> dict[str, Path]:
    return {
        "grading": base / "grading.json",
        "recommendation_ledger": base / "recommendation.json",
        "finance_digest": base / "digest.json",
        "wf88_os2": base / "os2.json",
        "wf88_wiki": base / "wiki.json",
    }


def seed(base: Path, *, leak_guard_pass: bool = True, auto_apply_count: int = 0, graded_rows: int = 3) -> dict[str, Path]:
    p = paths(base)
    write_json(p["grading"], {
        "validation": {"status": "ok"},
        "summary": {"existing_grade_event_count": graded_rows, "total_grade_event_count_after_append": graded_rows},
    })
    write_json(p["recommendation_ledger"], {"durable_v2_ledger": {"later_outcome_graded_rows": graded_rows}})
    write_json(p["finance_digest"], {"wf55_recommendation_outcomes": {"outcome_grade_assigned_count": graded_rows}})
    write_json(p["wf88_os2"], {
        "summary": {"recommendation_later_outcome_graded_rows": graded_rows},
        "validation": {"status": "blocked", "errors": ["wiki_synthesis_validation_blocked"]},
    })
    write_json(p["wf88_wiki"], {
        "summary": {"recommendation_later_outcome_graded_rows": graded_rows},
        "recommendation_leak_guard": {
            "pass": leak_guard_pass,
            "open_unrouted_recommendation_count": 0,
            "auto_apply_count": auto_apply_count,
        },
        "validation": {"status": "blocked", "errors": ["decision_docket_hard_stop_count_must_be_zero"]},
    })
    return p


def test_gate_allows_unrelated_packet_warnings_when_hard_checks_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = gate.build_payload(seed(Path(tmp)))
        assert payload["validation"]["status"] == "ok"
        assert payload["summary"]["recommendation_later_outcome_graded_rows"] == 3
        assert "wiki_validation_status:blocked" in payload["validation"]["warnings"]


def test_gate_blocks_leak_guard_or_missing_grades() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = gate.build_payload(seed(Path(tmp), leak_guard_pass=False, auto_apply_count=1, graded_rows=0))
        assert payload["validation"]["status"] == "blocked"
        assert "recommendation_leak_guard_pass" in payload["validation"]["errors"]
        assert "auto_apply_count_zero" in payload["validation"]["errors"]
        assert "recommendation_ledger_grade_count_positive" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_gate_allows_unrelated_packet_warnings_when_hard_checks_pass()
    test_gate_blocks_leak_guard_or_missing_grades()
    print("wf88_wiki_refresh_cron_gate_tests_passed")
