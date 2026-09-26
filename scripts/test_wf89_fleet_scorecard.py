from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf89_fleet_scorecard as sc


def rec(run_id: str, agent: str = "implementation-builder", label: str = "Fix WF88 gate", state: str = "CREDITABLE",
        usage: dict | None = None) -> dict:
    return {
        "run_id": run_id,
        "task_id": f"task-{run_id}",
        "agent_id": agent,
        "label": label,
        "status": "succeeded",
        "state": state,
        "usage": usage if usage is not None else {"input": 1000, "output": 200, "total": 5000, "cacheRead": 3800},
    }


def patch_reader(monkeypatch, records: list[dict], cli_records: list[dict] | None = None,
                 timing: dict | None = None, bypass_rows: list[dict] | None = None) -> None:
    monkeypatch.setattr(sc.reader, "read_task", lambda **_: {"records": records, "counts": {"CREDITABLE": len(records)}})
    bypassed: dict[str, int] = {}
    for row in bypass_rows or []:
        bypassed[row["agent_id"]] = bypassed.get(row["agent_id"], 0) + 1
    monkeypatch.setattr(sc.reader, "read_cli", lambda *_a, **_k: {
        "records": cli_records or [], "counts": {}, "cli_rows_without_dispatch_record_by_agent": {"qa-redteam": 4},
        "cli_rows_bypassing_dispatch_wrapper_by_agent": bypassed, "cli_bypass_rows": bypass_rows or [],
        "cli_exec_background_rows": 7,
    })
    monkeypatch.setattr(sc, "task_timing", lambda _db, ids: {
        i: (timing or {}).get(i, {"started_at_utc": "2026-09-25T10:00:00Z", "ended_at_utc": "2026-09-25T10:01:00Z",
                                  "duration_seconds": 60.0, "tool_use_count": 3, "terminal_outcome": None})
        for i in ids
    })


def build(tmp: Path, *, write: bool = True) -> dict:
    return sc.build(tmp / "g.sqlite", tmp / "agents", tmp / "dispatch", tmp / "history.jsonl", write=write,
                    outcomes_path=tmp / "outcomes.jsonl")


def test_benchmark_labels_separate_model_comparisons_from_real_work() -> None:
    for label in ("Sol T3 case", "Arena A T2 rep1", "DS chain B T4a", "Arena D mission-2",
                  "glm::code-debug-offbyone", "glm-5.3-flash::v3-fix-failing-tests", "GLM multi-turn TTL pilot"):
        assert sc.is_benchmark(label), label
    for label in ("Harden arena transport and grading", "Prepare four benchmark cases",
                  "Fix WF88 lane proof-loss register warning", "Retire obsolete pilot scaffolds", None):
        assert not sc.is_benchmark(label), label


def test_appends_only_new_creditable_runs_and_is_idempotent(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a"), rec("b"), rec("c", state="INCOMPLETE")])
        first = build(tmp)
        assert first["history"]["rows_appended"] == 2
        second = build(tmp)
        assert second["history"]["rows_appended"] == 0
        rows = [json.loads(line) for line in (tmp / "history.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [r["run_id"] for r in rows] == ["a", "b"]
        assert rows[0]["usage"]["fresh"] == 1200
        assert rows[0]["duration_seconds"] == 60.0


def test_history_survives_window_expiry(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a"), rec("b"), rec("c")])
        build(tmp)
        patch_reader(monkeypatch, [])  # task_runs rows expired
        payload = build(tmp)
        assert payload["history"]["rows_total"] == 3
        assert payload["lanes"]["implementation-builder"]["work"]["credited_runs"] == 3
        assert payload["lanes"]["implementation-builder"]["work"]["median_fresh_tokens"] == 1200


def test_medians_withheld_below_minimum_and_benchmarks_excluded(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a"), rec("b"), rec("x", label="Sol T1 case"), rec("y", label="Sol T2 case")])
        payload = build(tmp)
        lane = payload["lanes"]["implementation-builder"]
        assert lane["work"]["credited_runs"] == 2
        assert lane["work"]["median_fresh_tokens"] is None
        assert lane["benchmark_runs"] == 2
        assert "no_lane_has_enough_credited_work_runs_for_medians" in payload["observations"]
        assert payload["status"] == "ok"


def test_dry_run_writes_nothing(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a")])
        payload = build(tmp, write=False)
        assert payload["history"]["rows_pending_append"] == 1
        assert not (tmp / "history.jsonl").exists()


def test_corrupt_history_is_an_error_and_cli_gap_is_reported(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "history.jsonl").write_text("{not json\n", encoding="utf-8")
        patch_reader(monkeypatch, [rec("a")])
        payload = build(tmp, write=False)
        assert payload["validation"]["status"] == "error"
        assert payload["window"]["cli_rows_without_dispatch_record_by_agent"] == {"qa-redteam": 4}


def test_pre_go_live_cli_gap_is_an_observation_not_a_failure(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        patch_reader(monkeypatch, [rec("a")])
        payload = build(Path(t), write=False)
        assert payload["status"] == "ok"
        assert "cli_runs_without_dispatch_record_are_uncreditable" in payload["observations"]
        assert payload["window"]["cli_exec_background_rows_excluded"] == 7


def test_new_wrapper_bypass_fails_once_then_stays_a_warning(monkeypatch) -> None:
    now_ms = int(sc.datetime.now(sc.timezone.utc).timestamp() * 1000)
    fresh = {"agent_id": "qa-redteam", "task_id": "t1", "created_at": now_ms - 3_600_000}
    stale = {"agent_id": "main", "task_id": "t2", "created_at": now_ms - 30 * 3_600_000}
    with tempfile.TemporaryDirectory() as t:
        patch_reader(monkeypatch, [rec("a")], bypass_rows=[fresh, stale])
        payload = build(Path(t), write=False)
        assert payload["status"] == "error"
        assert payload["validation"]["errors"] == ["cli_run_bypassed_dispatch_wrapper:qa-redteam:1"]
        assert "cli_run_bypassed_dispatch_wrapper_in_window:main:1" in payload["validation"]["warnings"]
        patch_reader(monkeypatch, [rec("a")], bypass_rows=[stale])
        later = build(Path(t), write=False)
        assert later["status"] == "ok"
        assert later["window"]["cli_rows_bypassing_dispatch_wrapper_by_agent"] == {"main": 1}


def test_main_share_counts_work_runs_only(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a", agent="main"), rec("b", agent="main", label="Sol T1 case"),
                                   rec("c"), rec("d", state="INCOMPLETE", agent="qa-redteam")])
        payload = build(tmp, write=False)
        assert payload["window"]["main_share_of_work_runs"] == round(1 / 3, 3)



def test_duplicate_run_in_one_batch_is_appended_once(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a")], cli_records=[rec("a")])
        payload = build(tmp)
        assert payload["history"]["rows_appended"] == 1
        rows = (tmp / "history.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1


def test_never_launched_dispatch_is_not_counted_as_work(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        pending = {"agent_id": "implementation-builder", "label": "Fix gate", "state": "PENDING"}
        patch_reader(monkeypatch, [rec("a", agent="main")], cli_records=[pending])
        payload = build(Path(t), write=False)
        assert payload["window"]["delegated_runs_by_agent"] == {"main": {"work": 1, "benchmark": 0}}
        assert payload["window"]["main_share_of_work_runs"] == 1.0


def test_explicit_prefix_overrides_label_heuristic() -> None:
    assert sc.classify_label("work: build eval case set") == (False, "prefix")
    assert sc.classify_label("bench:arena-v2 fix") == (True, "prefix")
    assert sc.classify_label("Sol T3 case") == (True, "heuristic")
    assert sc.classify_label("Fix WF88 gate") == (False, "heuristic")


def test_history_row_records_model_and_class_source(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        r = rec("a", label="work: case set review")
        r.update(window_model="glm-5.3:cloud", window_model_provider="ollama-cloud")
        patch_reader(monkeypatch, [r])
        build(tmp)
        row = json.loads((tmp / "history.jsonl").read_text(encoding="utf-8"))
        assert row["model"] == "ollama-cloud/glm-5.3:cloud"
        assert row["benchmark"] is False and row["class_source"] == "prefix"


def test_cost_per_accepted_task_uses_main_outcomes(monkeypatch) -> None:
    import wf89_run_outcome as ro

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a"), rec("b"), rec("c")])
        build(tmp)
        history, _ = sc.load_history(tmp / "history.jsonl")
        out = tmp / "outcomes.jsonl"
        for run_id, outcome, minutes in (("a", "accepted", 5), ("b", "rework", 10), ("a", "accepted", 4)):
            assert ro.main(["--run-id", run_id, "--outcome", outcome, "--main-review-minutes", str(minutes),
                            "--history", str(tmp / "history.jsonl"), "--outcomes", str(out)]) == 0
        assert ro.main(["--run-id", "zzz", "--outcome", "accepted", "--history", str(tmp / "history.jsonl"),
                        "--outcomes", str(out)]) == 2
        lane = build(tmp, write=False)["lanes"]["implementation-builder"]["work_outcomes"]
        assert lane["runs_judged"] == 2 and lane["runs_unjudged"] == 1
        assert lane["accepted"] == 1 and lane["rework"] == 1
        assert lane["fresh_tokens_per_accepted_task"] == 2400
        assert lane["main_review_minutes_total"] == 14.0


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
