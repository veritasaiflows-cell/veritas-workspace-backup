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
                 timing: dict | None = None) -> None:
    monkeypatch.setattr(sc.reader, "read_task", lambda **_: {"records": records, "counts": {"CREDITABLE": len(records)}})
    monkeypatch.setattr(sc.reader, "read_cli", lambda *_a, **_k: {
        "records": cli_records or [], "counts": {}, "cli_rows_without_dispatch_record_by_agent": {"qa-redteam": 4},
    })
    monkeypatch.setattr(sc, "task_timing", lambda _db, ids: {
        i: (timing or {}).get(i, {"started_at_utc": "2026-09-25T10:00:00Z", "ended_at_utc": "2026-09-25T10:01:00Z",
                                  "duration_seconds": 60.0, "tool_use_count": 3, "terminal_outcome": None})
        for i in ids
    })


def build(tmp: Path, *, write: bool = True) -> dict:
    return sc.build(tmp / "g.sqlite", tmp / "agents", tmp / "dispatch", tmp / "history.jsonl", write=write)


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


def test_main_share_counts_work_runs_only(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        patch_reader(monkeypatch, [rec("a", agent="main"), rec("b", agent="main", label="Sol T1 case"),
                                   rec("c"), rec("d", state="INCOMPLETE", agent="qa-redteam")])
        payload = build(tmp, write=False)
        assert payload["window"]["main_share_of_work_runs"] == round(1 / 3, 3)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
