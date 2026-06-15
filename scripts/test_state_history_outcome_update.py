from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import state_history_outcome_update as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base_snapshot() -> dict:
    return {
        "schema_version": 1,
        "row_type": "state_snapshot_v1",
        "capture_run_id": "capture_1",
        "captured_at_utc": "2026-05-10T12:00:00Z",
        "window": "post-close",
        "authority": {},
        "known_at_time": {},
        "future_outcomes": {"realized_outcomes": []},
        "provenance": {},
    }


def build_valid_update(tmp: Path, state_history: Path) -> dict:
    source = tmp / "source.json"
    source.write_text(json.dumps({"generated_at_utc": "2026-05-11T00:00:00Z", "status": "ok"}), encoding="utf-8")
    return mod.build_update(
        linked_capture_run_id="capture_1",
        ticker="GOOG",
        question_id="band_reclaim_question",
        outcome_label="band_reclaim_held",
        observed_at_utc="2026-05-12T12:00:00Z",
        provenance_path=source,
        state_history_path=state_history,
        recorded_at_utc="2026-05-12T13:00:00Z",
    )


def test_valid_update_passes(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state_history = tmp / "state-history-v1.jsonl"
        write_jsonl(state_history, [base_snapshot()])
        update = build_valid_update(tmp, state_history)
        findings = mod.validate_update(update, mod.snapshot_index(state_history))
        expect(not findings, f"valid update should pass: {findings}", errors)


def test_timestamp_must_be_after_snapshot(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state_history = tmp / "state-history-v1.jsonl"
        write_jsonl(state_history, [base_snapshot()])
        update = build_valid_update(tmp, state_history)
        update["observed_at_utc"] = "2026-05-10T12:00:00Z"
        findings = mod.validate_update(update, mod.snapshot_index(state_history))
        expect(any(item.get("issue") == "observed_timestamp_not_after_snapshot" for item in findings), "same-time observed outcome must fail", errors)


def test_forbidden_probability_language_fails(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state_history = tmp / "state-history-v1.jsonl"
        write_jsonl(state_history, [base_snapshot()])
        update = build_valid_update(tmp, state_history)
        update["notes"] = "This is a 55% chance win probability."
        findings = mod.validate_update(update, mod.snapshot_index(state_history))
        expect(any(item.get("issue") == "forbidden_probability_or_modeling_language" for item in findings), "forbidden probability text must fail", errors)


def test_paper_lifecycle_labels_pass(errors: list[str]) -> None:
    labels = [
        "paper_order_accepted_unfilled",
        "paper_order_filled",
        "paper_order_partially_filled",
        "paper_order_expired_unfilled",
        "paper_order_cancelled_unfilled",
        "paper_order_rejected",
        "paper_position_observed",
        "paper_position_closed",
    ]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state_history = tmp / "state-history-v1.jsonl"
        write_jsonl(state_history, [base_snapshot()])
        snapshots = mod.snapshot_index(state_history)
        for label in labels:
            update = build_valid_update(tmp, state_history)
            update["outcome_label"] = label
            update["question_id"] = "paper_pilot_order_resolution"
            findings = mod.validate_update(update, snapshots)
            expect(not findings, f"paper lifecycle label should pass: {label} {findings}", errors)


def test_duplicate_without_supersession_fails(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state_history = tmp / "state-history-v1.jsonl"
        output = tmp / "outcome-updates-v1.jsonl"
        write_jsonl(state_history, [base_snapshot()])
        first = build_valid_update(tmp, state_history)
        second = build_valid_update(tmp, state_history)
        write_jsonl(output, [first, second])
        report = mod.validate_file(output, state_history)
        expect(any(item.get("issue") == "duplicate_outcome_without_supersession" for item in report.get("findings", [])), "duplicate natural key must fail without supersession", errors)


def test_duplicate_with_supersession_passes(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        state_history = tmp / "state-history-v1.jsonl"
        output = tmp / "outcome-updates-v1.jsonl"
        write_jsonl(state_history, [base_snapshot()])
        first = build_valid_update(tmp, state_history)
        second = build_valid_update(tmp, state_history)
        second["supersedes_update_id"] = first["outcome_update_id"]
        write_jsonl(output, [first, second])
        report = mod.validate_file(output, state_history)
        expect(report.get("critical") == 0, f"superseded duplicate should pass: {report}", errors)


def main() -> int:
    errors: list[str] = []
    test_valid_update_passes(errors)
    test_timestamp_must_be_after_snapshot(errors)
    test_forbidden_probability_language_fails(errors)
    test_paper_lifecycle_labels_pass(errors)
    test_duplicate_without_supersession_fails(errors)
    test_duplicate_with_supersession_passes(errors)
    if errors:
        print("state_history_outcome_update_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("state_history_outcome_update_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
