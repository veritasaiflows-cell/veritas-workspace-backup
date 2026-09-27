from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path

import recommendation_funnel as f
import thesis_record_validator as validator

WORKSPACE = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 24)

PIN_SHA = "ab" * 32
PIN_PATH = f"state/finance/baselines/test-baseline-{PIN_SHA}.json"
GUARD_REL = "tmp/test-guard.json"

LOW, HIGH, INV = 100.0, 110.0, 95.0


def ctl_row(ticker, price, *, conf=40, state="band_entry"):
    return {"ticker": ticker, "latest_price": price, "reference_low": 100.0, "reference_high": 110.0,
            "invalidation_threshold": 95.0, "alert_state": state, "level_relationship_state": state,
            "sql_reference": {"reference_price_low": LOW, "reference_price_high": HIGH,
                              "reference_invalidation_level": INV, "reference_confidence": conf}}


def thesis(ticker, conviction, fav=(), disfav=()):
    return {
        "schema": "veritas.thesis_record.v1",
        "ticker": ticker,
        "thesis_version": 1,
        "status": "accepted",
        "thesis_type": "quality_compounder",
        "thesis_statement": "A durable franchise with pricing power and steady cash flow for holders. " * 2,
        "timeframe": "long_term_12m_plus",
        "cases": {
            "base": {"summary": "Steady growth with resilient margins over time.", "drivers": ["pricing"]},
            "bull": {"summary": "Accelerated growth with expanding margins over time.", "drivers": ["growth"]},
            "bear": {"summary": "Slower growth but the franchise remains intact here.", "drivers": ["stable"]},
        },
        "key_risks": ["valuation risk if growth slows materially", "regulatory risk in core markets"],
        "invalidation_reasons": {"price": "breaks below invalidation level", "fundamental": ["margin collapse"]},
        "catalysts": [],
        "conviction": conviction,
        "regime_fit": {"favored_postures": list(fav), "disfavored_postures": list(disfav)},
        "benchmark": {"market": "SPY", "sector": "XLB"},
        "evidence": [{"claim": "steady cash flow evidence", "source": "filings", "as_of": "2026-09-01"}],
        "thesis_as_of": "2026-09-01",
        "review_due": "2026-12-31",
        "drafted_by": "test",
        "owner_accepted_at": "2026-09-01T00:00:00Z",
    }


def _write_same_version(root: Path, rows) -> None:
    canon = root / "state/finance/finance-canon.sqlite"
    canon.parent.mkdir(parents=True, exist_ok=True)
    if canon.exists():
        canon.unlink()
    for suffix in ("-wal", "-shm", "-journal"):
        p = Path(str(canon) + suffix)
        if p.exists():
            p.unlink()
    con = sqlite3.connect(str(canon))
    try:
        con.execute("CREATE TABLE reference_levels (ticker TEXT PRIMARY KEY, reference_price_low REAL, "
                    "reference_price_high REAL, reference_invalidation_level REAL, reference_confidence REAL, "
                    "reference_band_status TEXT, source_artifact_path TEXT, source_artifact_sha256 TEXT, "
                    "source_generated_at_utc TEXT, fallback_rule TEXT, authority_class TEXT, raw_json TEXT)")
        con.execute("CREATE TABLE finance_state_meta (key TEXT PRIMARY KEY, value TEXT)")
        meta = {"baseline_path": PIN_PATH, "baseline_sha256": PIN_SHA, "path": PIN_PATH,
                "sha256": PIN_SHA, "key": "alerts_os_reference_baseline_v1"}
        con.execute("INSERT INTO finance_state_meta (key, value) VALUES (?, ?)",
                    ("alerts_os_reference_baseline_v1", json.dumps(meta)))
        for r in rows:
            sref = r["sql_reference"]
            con.execute(
                "INSERT INTO reference_levels (ticker, reference_price_low, reference_price_high, "
                "reference_invalidation_level, reference_confidence, reference_band_status, "
                "source_artifact_path, source_artifact_sha256, source_generated_at_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (r["ticker"], sref["reference_price_low"], sref["reference_price_high"],
                 sref["reference_invalidation_level"], sref["reference_confidence"],
                 "NEAR_BAND", PIN_PATH, PIN_SHA, "2026-09-26T16:00:07Z"))
        con.commit()
    finally:
        con.close()
    tickers = sorted(r["ticker"] for r in rows)
    guard = {"status": "ok", "tickers": tickers, "database_path": str(f.FINANCE_CANON_REL),
             "reference_levels": {}, "lineage": {}}
    for r in rows:
        t = r["ticker"]
        sref = r["sql_reference"]
        guard["reference_levels"][t] = dict(sref)
        guard["lineage"][t] = {"fields": [
            {"field_name": fn, "source_artifact_path": PIN_PATH, "source_artifact_sha256": PIN_SHA}
            for fn in f.SQL_FIELDS]}
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")


def seed(tmp: Path, rows, theses, posture="selective_with_watch_flags", earnings=None,
         controller_generated_at="2026-09-26T14:00:00Z", renewal="non-applied") -> Path:
    folder = tmp / validator.THESIS_REL
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(WORKSPACE / validator.THESIS_REL / validator.SCHEMA_FILE, folder / validator.SCHEMA_FILE)
    for rec in theses:
        (folder / f"{rec['ticker']}.json").write_text(json.dumps(rec), encoding="utf-8")
    (tmp / "tmp").mkdir(exist_ok=True)
    controller = {"rows": rows, "source_artifacts": {"sql_guard": GUARD_REL}}
    if controller_generated_at is not None:
        controller["generated_at_utc"] = controller_generated_at
    (tmp / f.CONTROLLER_REL).write_text(json.dumps(controller), encoding="utf-8")
    if renewal == "non-applied":
        (tmp / f.RENEWAL_PACKET_REL).write_text(json.dumps(
            {"status": "needs_owner_review", "applied": False}), encoding="utf-8")
    elif isinstance(renewal, str):
        applied_renewal(tmp, renewal)
    (tmp / f.MACRO_REL).write_text(json.dumps({"summary": {"macro_posture": posture}}), encoding="utf-8")
    (tmp / f.EARNINGS_REL).write_text(json.dumps({"records": [{"ticker": t, "next_earnings_date": d}
                                                              for t, d in (earnings or {}).items()]}), encoding="utf-8")
    _write_same_version(tmp, rows)
    return tmp


def _db_hash(root: Path) -> str:
    return hashlib.sha256((root / "state/finance/finance-canon.sqlite").read_bytes()).hexdigest()


def _assert_no_wal(root: Path) -> None:
    base = root / "state/finance/finance-canon.sqlite"
    for suffix in ("-wal", "-shm"):
        assert not Path(str(base) + suffix).exists(), f"SQLite residue {suffix} created"


def flat(symbol):
    return [100.0] * 80


def applied_renewal(tmp: Path, finished, applied=True) -> Path:
    (tmp / f.RENEWAL_PACKET_REL).write_text(json.dumps(
        {"status": "applied" if applied else "needs_owner_review",
         "applied": applied, "finished_at_utc": finished}), encoding="utf-8")
    return tmp


def exploding_closes(symbol):
    raise AssertionError(f"ranking must not run on stale provenance (closes called for {symbol})")


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


def test_data_confidence_uses_canon_percent_scale(tmp_path):
    # 2026-09-24: canon stores whole-number percent; 40 must not read as 0.
    root = seed(tmp_path, [ctl_row("AAA", 101, conf=40)], [thesis("AAA", "high")])
    entry = by(f.evaluate(root, closes=flat, today=TODAY))["AAA"]
    assert entry["components"]["data_confidence"] == 0.8


def test_fresh_controller_newer_than_applied_renewal_still_ranks(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T17:00:00Z")
    applied_renewal(root, "2026-09-26T16:00:00Z")
    out = f.evaluate(root, closes=flat, today=TODAY)
    assert out["candidates"] == ["AAA"] and by(out)["AAA"]["stage"] == "review_candidate"


def test_non_applied_renewal_does_not_suppress(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T14:00:00Z")
    applied_renewal(root, "2026-09-26T16:00:00Z", applied=False)
    assert f.evaluate(root, closes=flat, today=TODAY)["candidates"] == ["AAA"]


def test_stale_controller_suppressed_before_ranking(tmp_path):
    # Defect 2026-09-26: funnel 15:00Z built from controller 2026-09-25 20:45Z,
    # applied renewal finished 2026-09-26 16:00Z (ranked CME 255.5971 vs SQL 249.92).
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-25T20:45:00Z")
    applied_renewal(root, "2026-09-26T16:00:00Z")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["candidates"] == [] and out["names"] == []
    assert out["status"] == "stale_suppressed" and "16:00:00Z" in out["stale_reason"]
    assert all(v == 0 for v in out["counts"].values())


def test_missing_controller_provenance_suppressed(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")], controller_generated_at=None)
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["candidates"] == [] and out["status"] == "stale_suppressed"


def test_invalid_provenance_timestamps_suppressed(tmp_path):
    root = seed(tmp_path / "a", [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="not-a-timestamp")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "b", [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T17:00:00Z")
    applied_renewal(root, "bad-timestamp")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"


def test_missing_renewal_packet_suppressed(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")], renewal="absent")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["candidates"] == [] and out["status"] == "stale_suppressed"
    assert "renewal" in out["stale_reason"]


def test_naive_timestamps_rejected_as_invalid(tmp_path):
    root = seed(tmp_path / "a", [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T14:00:00")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "b", [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T17:00:00Z")
    applied_renewal(root, "2026-09-26T16:00:00")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"


def test_malformed_and_inconsistent_renewal_suppressed(tmp_path):
    docs = [{}, {"session": "2026-09-25"},
            {"applied": True, "status": "apply_failed", "finished_at_utc": "2026-09-26T16:00:00Z"},
            {"applied": True, "status": "needs_owner_review", "finished_at_utc": "2026-09-26T16:00:00Z"},
            {"applied": False, "status": "applied", "finished_at_utc": "2026-09-26T16:00:00Z"}]
    for i, doc in enumerate(docs):
        root = seed(tmp_path / f"case{i}", [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                    controller_generated_at="2026-09-26T17:00:00Z")
        (root / f.RENEWAL_PACKET_REL).write_text(json.dumps(doc), encoding="utf-8")
        out = f.evaluate(root, closes=exploding_closes, today=TODAY)
        assert out["candidates"] == [] and out["status"] == "stale_suppressed", doc


def test_gate_passed_not_applied_renewal_stays_fresh(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T14:00:00Z")
    (root / f.RENEWAL_PACKET_REL).write_text(json.dumps(
        {"status": "gate_passed_not_applied", "applied": False}), encoding="utf-8")
    assert f.evaluate(root, closes=flat, today=TODAY)["candidates"] == ["AAA"]


def test_non_dict_controller_suppresses_without_crash(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    (root / f.CONTROLLER_REL).write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["candidates"] == [] and out["status"] == "stale_suppressed"


# ---- Phase 4 same-version lineage guard ----

def test_positive_same_version_ranks_without_network(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    before = _db_hash(root)
    out = f.evaluate(root, closes=flat, today=TODAY)
    assert out.get("status") != "stale_suppressed" and out["candidates"] == ["AAA"]
    assert _db_hash(root) == before
    _assert_no_wal(root)


def test_newer_timestamp_with_old_band_suppressed_before_closes(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")],
                controller_generated_at="2026-09-26T17:00:00Z")
    applied_renewal(root, "2026-09-26T16:00:00Z")
    con = sqlite3.connect(str(root / "state/finance/finance-canon.sqlite"))
    con.execute("UPDATE reference_levels SET reference_price_low = 258.87 WHERE ticker = 'AAA'")
    con.commit()
    con.close()
    before = _db_hash(root)
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["candidates"] == [] and out["status"] == "stale_suppressed"
    assert "AAA" in out["stale_reason"]
    assert _db_hash(root) == before
    _assert_no_wal(root)


def test_guard_value_tamper_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["reference_levels"]["AAA"]["reference_price_low"] = 1.5
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "AAA" in out["stale_reason"]


def test_lineage_hash_mismatch_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["lineage"]["AAA"]["fields"][0]["source_artifact_sha256"] = "00" * 32
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "lineage" in out["stale_reason"]


def test_lineage_path_mismatch_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["lineage"]["AAA"]["fields"][1]["source_artifact_path"] = "state/finance/baselines/other.json"
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "AAA" in out["stale_reason"]


def test_active_pin_change_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    new_sha = "cd" * 32
    new_path = f"state/finance/baselines/test-baseline-{new_sha}.json"
    con = sqlite3.connect(str(root / "state/finance/finance-canon.sqlite"))
    con.execute("UPDATE reference_levels SET source_artifact_sha256 = ?, source_artifact_path = ? WHERE ticker = 'AAA'",
                (new_sha, new_path))
    con.execute("UPDATE finance_state_meta SET value = ? WHERE key = 'alerts_os_reference_baseline_v1'",
                (json.dumps({"baseline_path": new_path, "baseline_sha256": new_sha}),))
    con.commit()
    con.close()
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "AAA" in out["stale_reason"]


def test_missing_guard_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    (root / GUARD_REL).unlink()
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed"


def test_absolute_and_traversal_guard_path_suppress(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    ctl = json.loads((root / f.CONTROLLER_REL).read_text(encoding="utf-8"))
    ctl["source_artifacts"]["sql_guard"] = "/tmp/evil.json"
    (root / f.CONTROLLER_REL).write_text(json.dumps(ctl), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    ctl["source_artifacts"]["sql_guard"] = "../outside.json"
    (root / f.CONTROLLER_REL).write_text(json.dumps(ctl), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"


def test_missing_and_malformed_pin_suppress(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    con = sqlite3.connect(str(root / "state/finance/finance-canon.sqlite"))
    con.execute("DELETE FROM finance_state_meta WHERE key = 'alerts_os_reference_baseline_v1'")
    con.commit()
    con.close()
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "b", [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    con = sqlite3.connect(str(root / "state/finance/finance-canon.sqlite"))
    con.execute("UPDATE finance_state_meta SET value = ? WHERE key = 'alerts_os_reference_baseline_v1'",
                (json.dumps({"baseline_path": PIN_PATH, "baseline_sha256": "not-hex"}),))
    con.commit()
    con.close()
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "pin" in out["stale_reason"]


def test_missing_db_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    (root / "state/finance/finance-canon.sqlite").unlink()
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed"
    assert not Path(str(root / "state/finance/finance-canon.sqlite") + "-wal").exists()


def test_scope_extra_missing_duplicate_suppress(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101), ctl_row("BBB", 101)],
                [thesis("AAA", "high"), thesis("BBB", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["tickers"] = ["AAA"]
    guard["reference_levels"].pop("BBB", None)
    guard["lineage"].pop("BBB", None)
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "b", [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["tickers"] = ["AAA", "AAA"]
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "c", [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    ctl = json.loads((root / f.CONTROLLER_REL).read_text(encoding="utf-8"))
    ctl["rows"] = ctl["rows"] + [copy.deepcopy(ctl["rows"][0])]
    (root / f.CONTROLLER_REL).write_text(json.dumps(ctl), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"


def test_missing_and_duplicate_lineage_fields_suppress(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["lineage"]["AAA"]["fields"] = [e for e in guard["lineage"]["AAA"]["fields"]
                                         if e["field_name"] != "reference_confidence"]
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "b", [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    guard = json.loads((root / GUARD_REL).read_text(encoding="utf-8"))
    guard["lineage"]["AAA"]["fields"].append(copy.deepcopy(guard["lineage"]["AAA"]["fields"][0]))
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "duplicate" in out["stale_reason"]


def test_missing_sql_ticker_suppresses(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    con = sqlite3.connect(str(root / "state/finance/finance-canon.sqlite"))
    con.execute("DELETE FROM reference_levels WHERE ticker = 'AAA'")
    con.commit()
    con.close()
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed" and "AAA" in out["stale_reason"]


def test_tolerance_boundary_and_malformed_numeric(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    ctl = json.loads((root / f.CONTROLLER_REL).read_text(encoding="utf-8"))
    ctl["rows"][0]["sql_reference"]["reference_price_low"] = LOW + 5e-10
    (root / f.CONTROLLER_REL).write_text(json.dumps(ctl), encoding="utf-8")
    assert f.evaluate(root, closes=flat, today=TODAY)["candidates"] == ["AAA"]
    ctl["rows"][0]["sql_reference"]["reference_price_low"] = LOW + 2e-9
    (root / f.CONTROLLER_REL).write_text(json.dumps(ctl), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"
    root = seed(tmp_path / "b", [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    ctl = json.loads((root / f.CONTROLLER_REL).read_text(encoding="utf-8"))
    ctl["rows"][0]["sql_reference"]["reference_confidence"] = True
    (root / f.CONTROLLER_REL).write_text(json.dumps(ctl), encoding="utf-8")
    assert f.evaluate(root, closes=exploding_closes, today=TODAY)["status"] == "stale_suppressed"


def test_db_byte_identity_preserved_on_success_and_failure(tmp_path):
    root = seed(tmp_path, [ctl_row("AAA", 101)], [thesis("AAA", "high")])
    before = _db_hash(root)
    f.evaluate(root, closes=flat, today=TODAY)
    assert _db_hash(root) == before
    _assert_no_wal(root)
    con = sqlite3.connect(str(root / "state/finance/finance-canon.sqlite"))
    con.execute("UPDATE reference_levels SET reference_confidence = 41 WHERE ticker = 'AAA'")
    con.commit()
    con.close()
    before = _db_hash(root)
    out = f.evaluate(root, closes=exploding_closes, today=TODAY)
    assert out["status"] == "stale_suppressed"
    assert _db_hash(root) == before
    _assert_no_wal(root)
