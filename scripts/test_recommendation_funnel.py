from __future__ import annotations

import copy
import json
import shutil
from datetime import date
from pathlib import Path

import recommendation_funnel as f
import thesis_record_validator as validator

WORKSPACE = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 24)


def ctl_row(ticker, price, *, conf=0.4, state="band_entry"):
    return {"ticker": ticker, "latest_price": price, "reference_low": 100.0, "reference_high": 110.0,
            "invalidation_threshold": 95.0, "alert_state": state, "level_relationship_state": state,
            "sql_reference": {"reference_confidence": conf}}


def thesis(ticker, conviction, fav=(), disfav=()):
    rec = json.loads((WORKSPACE / validator.THESIS_REL / "LIN.json").read_text(encoding="utf-8"))
    rec.update({"ticker": ticker, "conviction": conviction,
                "regime_fit": {"favored_postures": list(fav), "disfavored_postures": list(disfav)}})
    rec["benchmark"] = {"market": "SPY", "sector": "XLB"}
    return rec


def seed(tmp: Path, rows, theses, posture="selective_with_watch_flags", earnings=None) -> Path:
    folder = tmp / validator.THESIS_REL
    folder.mkdir(parents=True)
    shutil.copy(WORKSPACE / validator.THESIS_REL / validator.SCHEMA_FILE, folder / validator.SCHEMA_FILE)
    for rec in theses:
        (folder / f"{rec['ticker']}.json").write_text(json.dumps(rec), encoding="utf-8")
    (tmp / "tmp").mkdir()
    (tmp / f.CONTROLLER_REL).write_text(json.dumps({"rows": rows}), encoding="utf-8")
    (tmp / f.MACRO_REL).write_text(json.dumps({"summary": {"macro_posture": posture}}), encoding="utf-8")
    (tmp / f.EARNINGS_REL).write_text(json.dumps({"records": [{"ticker": t, "next_earnings_date": d}
                                                              for t, d in (earnings or {}).items()]}), encoding="utf-8")
    return tmp


def flat(symbol):
    return [100.0] * 80


def by(out):
    return {n["ticker"]: n for n in out["names"]}


def test_no_thesis_is_monitor_only_and_band_edge_ranks(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101), ctl_row("BBB", 109), ctl_row("CCC", 101)],
                [thesis("AAA", "medium"), thesis("BBB", "medium")])
    out = by(f.evaluate(root, closes=flat, today=TODAY))
    assert out["CCC"]["stage"] == "monitor_only"
    assert out["AAA"]["score"] > out["BBB"]["score"]  # nearer band low ranks higher
    assert out["AAA"]["stage"] == "review_candidate"


def test_defensive_posture_requires_high_conviction(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101), ctl_row("BBB", 101)],
                [thesis("AAA", "medium"), thesis("BBB", "high")], posture="defensive_review_bias")
    out = by(f.evaluate(root, closes=flat, today=TODAY))
    assert out["AAA"]["stage"] == "board_only" and out["BBB"]["stage"] == "review_candidate"


def test_disfavored_posture_is_board_only(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high", disfav=["selective_with_watch_flags"])])
    assert by(f.evaluate(root, closes=flat, today=TODAY))["AAA"]["stage"] == "board_only"


def test_earnings_window_flags_and_penalises(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101), ctl_row("BBB", 101)],
                [thesis("AAA", "medium"), thesis("BBB", "medium")], earnings={"AAA": "2026-09-30"})
    out = by(f.evaluate(root, closes=flat, today=TODAY))
    assert any("binary_event" in x for x in out["AAA"]["flags"]) and out["AAA"]["score"] < out["BBB"]["score"]


def test_below_invalidation_and_stale_are_excluded_and_above_band_not_candidate(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 90), ctl_row("BBB", 101, state="freshness_decay"), ctl_row("CCC", 120)],
                [thesis("AAA", "high"), thesis("BBB", "high"), thesis("CCC", "high")])
    out = by(f.evaluate(root, closes=flat, today=TODAY))
    assert out["AAA"]["stage"] == "monitor_only" and out["BBB"]["stage"] == "monitor_only"
    assert out["CCC"]["stage"] == "ranked_not_candidate"


def test_relative_strength_moves_score(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101), ctl_row("BBB", 101)],
                [thesis("AAA", "medium"), thesis("BBB", "medium")])
    def closes(sym):
        return [100.0] * 70 + [120.0] if sym == "AAA" else [100.0] * 71
    out = by(f.evaluate(root, closes=closes, today=TODAY))
    assert out["AAA"]["relative_strength_63d"]["vs_spy"] == 0.2 and out["AAA"]["score"] > out["BBB"]["score"]


def test_output_carries_no_position_fields(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    assert not validator._forbidden(f.evaluate(root, closes=flat, today=TODAY))


def test_defensive_posture_admits_medium_conviction_that_favors_it(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "medium", fav=["defensive_review_bias"])],
                posture="defensive_review_bias")
    assert by(f.evaluate(root, closes=flat, today=TODAY))["AAA"]["stage"] == "review_candidate"
