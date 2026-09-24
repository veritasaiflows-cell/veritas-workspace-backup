from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import weekly_band_renewal as w

WORKSPACE = Path(__file__).resolve().parents[1]


def row(old_low=100.0, new_low=101.0, *, blocked=False, warn=False, widened=False):
    if blocked:
        return {"classification": "blocked", "old_to_proposed": {"old": None, "proposed": None}}
    old = {"reference_price_low": old_low, "reference_price_high": 110.0, "reference_invalidation_level": 95.0}
    new = {"reference_price_low": new_low, "reference_price_high": 110.0, "reference_invalidation_level": 95.0,
           "band_floor_applied": widened}
    return {"classification": "trend_qualified", "invalidation_ordering_warning": warn,
            "old_to_proposed": {"old": old, "proposed": new}}


CLEAN_DRY = {"drift": 0, "no_mutation": True}


def test_gate_passes_small_clean_moves() -> None:
    g = w.evaluate_gate({"tickers": {"A": row(), "B": row(widened=True)}}, CLEAN_DRY)
    assert g["passed"] and g["floor_widened"] == ["B"]


def test_gate_stops_on_each_condition() -> None:
    assert not w.evaluate_gate({"tickers": {"A": row(blocked=True)}}, CLEAN_DRY)["passed"]
    assert not w.evaluate_gate({"tickers": {"A": row(warn=True)}}, CLEAN_DRY)["passed"]
    over = w.evaluate_gate({"tickers": {"A": row(new_low=106.0)}}, CLEAN_DRY)
    assert not over["passed"] and over["moved_over_limit"] == ["A"]
    assert w.evaluate_gate({"tickers": {"A": row(new_low=105.0)}}, CLEAN_DRY)["passed"]  # exactly 5% is allowed
    assert not w.evaluate_gate({"tickers": {"A": row()}}, {"drift": 1, "no_mutation": True})["passed"]
    assert not w.evaluate_gate({"tickers": {"A": row()}}, None)["passed"]
    assert not w.evaluate_gate({"tickers": {}}, CLEAN_DRY)["passed"]


def _root(tmp: Path, active: bool = True) -> Path:
    (tmp / "state/finance/standing-approvals").mkdir(parents=True)
    (tmp / w.GATE_REL).write_text(json.dumps({"active": active}), encoding="utf-8")
    return tmp


def fake_runner(matrix: dict, calls: list):
    def run(argv, cwd):
        calls.append(argv)
        script = argv[1]
        if "yahoo_reference_level_matrix" in script:
            out = cwd / argv[argv.index("--json-output") + 1]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(matrix), encoding="utf-8")
        if "--dry-run" in argv:
            (cwd / argv[argv.index("--dryrun-path") + 1]).write_text(json.dumps(
                {"old_drift_tickers": [], "missing_tickers": [], "mutation_performed": False}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
    return run


def test_run_applies_only_when_gate_passes_and_flag_set(tmp_path: Path) -> None:
    root = _root(tmp_path)
    calls: list = []
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, calls))
    assert p["status"] == "applied" and any("--apply" in c for c in calls)
    assert (root / w.AUDIT_DIR_REL / "2026-09-25-applied.json").is_file()
    calls.clear()
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-26",
              runner=fake_runner({"tickers": {"A": row(new_low=120.0)}}, calls))
    assert p["status"] == "needs_owner_review" and not any("--apply" in c for c in calls)


def test_revoked_gate_never_applies(tmp_path: Path) -> None:
    root = _root(tmp_path, active=False)
    calls: list = []
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, calls))
    assert p["status"] == "needs_owner_review" and not any("--apply" in c for c in calls)


def test_last_completed_session_skips_open_day() -> None:
    def ts(d):
        return int(datetime.fromisoformat(d + "T09:30:00-04:00").timestamp())
    payload = json.dumps({"chart": {"result": [{"timestamp": [ts("2026-09-24"), ts("2026-09-25")],
                                                 "indicators": {"quote": [{"close": [1.0, 2.0]}]}}]}}).encode()
    during = datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc)   # 11:00 ET, session open
    after = datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc)    # Saturday
    assert w.last_completed_session(lambda u: payload, during) == "2026-09-24"
    assert w.last_completed_session(lambda u: payload, after) == "2026-09-25"


def test_redirected_root_never_touches_production(tmp_path: Path) -> None:
    prod = [WORKSPACE / w.PACKET_REL, WORKSPACE / w.AUDIT_DIR_REL]
    before = [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in prod]
    w.run(_root(tmp_path), python="py", apply_if_gated=False, session="2026-09-25",
          runner=fake_runner({"tickers": {"A": row()}}, []))
    assert before == [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in prod]
