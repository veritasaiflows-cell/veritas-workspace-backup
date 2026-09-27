from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

import veritas_mcp_server as srv

WORKSPACE = Path(__file__).resolve().parents[1]

PIN_SHA = "ab" * 32
PIN_PATH = f"state/finance/baselines/test-baseline-{PIN_SHA}.json"
GUARD_REL = "tmp/test-guard.json"
LIN_SQL = {"reference_price_low": 454.19, "reference_price_high": 485.87,
           "reference_invalidation_level": 443.52, "reference_confidence": 0.3}


def _write_same_version(root: Path) -> None:
    canon = root / srv.CANON_REL
    canon.parent.mkdir(parents=True, exist_ok=True)
    if canon.exists():
        canon.unlink()
    for suffix in ("-wal", "-shm", "-journal"):
        p = Path(str(canon) + suffix)
        if p.exists():
            p.unlink()
    con = sqlite3.connect(str(canon))
    try:
        con.execute("CREATE TABLE IF NOT EXISTS reference_levels (ticker TEXT PRIMARY KEY, "
                    "reference_price_low REAL, reference_price_high REAL, "
                    "reference_invalidation_level REAL, reference_confidence REAL, "
                    "reference_band_status TEXT, source_artifact_path TEXT, source_artifact_sha256 TEXT, "
                    "source_generated_at_utc TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS finance_state_meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute("DELETE FROM reference_levels WHERE ticker = 'LIN'")
        con.execute("INSERT INTO reference_levels VALUES ('LIN', 454.19, 485.87, 443.52, 0.3, "
                    "'NEAR_BAND', ?, ?, '2026-09-24T01:13:21Z')", (PIN_PATH, PIN_SHA))
        meta = {"baseline_path": PIN_PATH, "baseline_sha256": PIN_SHA, "path": PIN_PATH, "sha256": PIN_SHA}
        con.execute("INSERT OR REPLACE INTO finance_state_meta (key, value) VALUES (?, ?)",
                    ("alerts_os_reference_baseline_v1", json.dumps(meta)))
        con.commit()
    finally:
        con.close()
    guard = {"status": "ok", "tickers": ["LIN"],
             "reference_levels": {"LIN": dict(LIN_SQL)},
             "lineage": {"LIN": {"fields": [
                 {"field_name": fn, "source_artifact_path": PIN_PATH, "source_artifact_sha256": PIN_SHA}
                 for fn in ("reference_price_low", "reference_price_high",
                            "reference_invalidation_level", "reference_confidence")]}}}
    (root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")


def _db_hash(root: Path) -> str:
    return hashlib.sha256((root / srv.CANON_REL).read_bytes()).hexdigest()


def _assert_no_wal(root: Path) -> None:
    base = root / srv.CANON_REL
    for suffix in ("-wal", "-shm"):
        assert not Path(str(base) + suffix).exists(), f"SQLite residue {suffix} created"


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    (tmp_path / "state/finance/thesis").mkdir(parents=True)
    (tmp_path / "tmp").mkdir(exist_ok=True)
    _write_same_version(tmp_path)
    (tmp_path / srv.THESIS_REL / "LIN.json").write_text(json.dumps({"ticker": "LIN", "status": "accepted"}), encoding="utf-8")
    (tmp_path / srv.ARTIFACTS["funnel"]).write_text(json.dumps({
        "generated_at_utc": "2026-09-26T17:05:00Z",
        "funnel_version": "funnel-v1", "candidates": ["LIN"], "counts": {"review_candidate": 1},
        "names": [{"ticker": "LIN", "stage": "review_candidate", "score": 0.66, "components": {"x": 1}},
                  {"ticker": "ZZZ", "stage": "monitor_only"}]}), encoding="utf-8")
    _controller(tmp_path, CTL_FRESH)
    monkeypatch.setenv("VERITAS_ROOT", str(tmp_path))
    return tmp_path


def test_reference_band_reads_canon(fake_root):
    band = srv.reference_band("lin")
    assert band["found"] and band["low"] == 454.19 and band["reference_confidence"] == 0.3
    assert srv.reference_band("XOM")["found"] is False


def test_invalid_ticker_rejected(fake_root):
    for bad in ("", "lin; drop table", "../etc", "A" * 12):
        with pytest.raises(ValueError):
            srv.reference_band(bad)
        with pytest.raises(ValueError):
            srv.thesis(bad)


def test_thesis_and_missing(fake_root):
    assert srv.thesis("LIN")["record"]["status"] == "accepted"
    assert srv.thesis("XOM")["found"] is False


def test_funnel_trims_monitor_only_and_internals(fake_root):
    _renewal(fake_root, None, applied=False)  # non-applied renewal on record keeps the artifact fresh
    before = _db_hash(fake_root)
    out = srv.funnel()
    assert out["candidates"] == ["LIN"] and [n["ticker"] for n in out["names"]] == ["LIN"]
    assert "components" not in out["names"][0]
    assert _db_hash(fake_root) == before
    _assert_no_wal(fake_root)


def test_missing_artifacts_report_unavailable(fake_root):
    assert srv.thesis_review()["available"] is False
    assert srv.gap_repair_report()["available"] is False
    assert srv.weekly_renewal()["available"] is False
    assert srv.ledger_verify()["available"] is False


def test_canon_opened_read_only(fake_root):
    before = (fake_root / srv.CANON_REL).read_bytes()
    srv.reference_band("LIN")
    assert (fake_root / srv.CANON_REL).read_bytes() == before


def test_server_exposes_only_read_tools():
    tools = asyncio.run(srv.build_server().list_tools())
    names = sorted(t.name for t in tools)
    assert names == sorted(["get_reference_band", "get_thesis", "get_recommendation_funnel", "get_thesis_review",
                            "get_gap_repair_report", "get_weekly_renewal_packet", "verify_alert_ledger"])
    assert not any(w in n for n in names for w in ("write", "apply", "set", "delete", "send", "update"))
    assert all(t.annotations and t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in tools)


def test_live_workspace_band_matches_canon(monkeypatch):
    canon = WORKSPACE / srv.CANON_REL
    if not canon.is_file():
        pytest.skip("live canon DB not present in scratch (environmental)")
    monkeypatch.setenv("VERITAS_ROOT", str(WORKSPACE))
    band = srv.reference_band("MSFT")
    assert band["found"] and band["invalidation"] < band["low"] and band["reference_confidence"] is not None


CTL_FRESH = "2026-09-26T17:00:00Z"
CTL_STALE = "2026-09-25T20:45:00Z"
FUNNEL_TS = "2026-09-26T15:00:00Z"
RENEWAL_FINISHED = "2026-09-26T16:00:00Z"


def _write(root, rel, doc):
    (root / rel).write_text(json.dumps(doc), encoding="utf-8")


def _controller(root, generated_at):
    doc = {"rows": [{"ticker": "LIN", "sql_reference": dict(LIN_SQL)}],
           "source_artifacts": {"sql_guard": GUARD_REL}}
    if generated_at is not None:
        doc["generated_at_utc"] = generated_at
    _write(root, srv.CONTROLLER_REL, doc)


def _renewal(root, finished, applied=True):
    doc = {"status": "applied" if applied else "needs_owner_review", "applied": applied}
    if finished is not None:
        doc["finished_at_utc"] = finished
    _write(root, srv.ARTIFACTS["weekly_renewal"], doc)


def _funnel_artifact(root, generated_at):
    art = json.loads((root / srv.ARTIFACTS["funnel"]).read_text(encoding="utf-8"))
    if generated_at is None:
        art.pop("generated_at_utc", None)
    else:
        art["generated_at_utc"] = generated_at
    _write(root, srv.ARTIFACTS["funnel"], art)


def test_funnel_fresh_when_newer_than_applied_renewal(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, RENEWAL_FINISHED)
    before = _db_hash(fake_root)
    out = srv.funnel()
    assert out["candidates"] == ["LIN"] and [n["ticker"] for n in out["names"]] == ["LIN"]
    assert "status" not in out
    assert _db_hash(fake_root) == before
    _assert_no_wal(fake_root)


def test_funnel_suppresses_stale_controller(fake_root):
    _controller(fake_root, CTL_STALE)
    _funnel_artifact(fake_root, FUNNEL_TS)
    _renewal(fake_root, RENEWAL_FINISHED)
    out = srv.funnel()
    assert out["candidates"] == [] and out["names"] == []
    assert out["status"] == "stale_suppressed" and "controller" in out["stale_reason"]


def test_funnel_suppresses_stale_funnel_artifact(fake_root):
    _controller(fake_root, CTL_FRESH)
    _funnel_artifact(fake_root, FUNNEL_TS)
    _renewal(fake_root, RENEWAL_FINISHED)
    out = srv.funnel()
    assert out["candidates"] == [] and out["names"] == []
    assert out["status"] == "stale_suppressed" and "funnel generated" in out["stale_reason"]


def test_funnel_suppresses_invalid_provenance(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, None)  # applied renewal without a finish timestamp
    assert srv.funnel()["status"] == "stale_suppressed"
    _renewal(fake_root, RENEWAL_FINISHED)
    _controller(fake_root, "not-a-timestamp")
    assert srv.funnel()["status"] == "stale_suppressed"
    _controller(fake_root, CTL_FRESH)
    _funnel_artifact(fake_root, None)
    assert srv.funnel()["status"] == "stale_suppressed"


def test_funnel_suppresses_missing_renewal_packet(fake_root):
    _controller(fake_root, CTL_FRESH)
    out = srv.funnel()
    assert out["candidates"] == [] and out["names"] == []
    assert out["status"] == "stale_suppressed" and "renewal" in out["stale_reason"]


def test_funnel_suppresses_naive_timestamps(fake_root):
    _controller(fake_root, "2026-09-26T17:00:00")  # naive controller timestamp
    _renewal(fake_root, RENEWAL_FINISHED)
    assert srv.funnel()["status"] == "stale_suppressed"
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, "2026-09-26T16:00:00")  # naive renewal timestamp
    assert srv.funnel()["status"] == "stale_suppressed"


def test_funnel_non_applied_renewal_stays_fresh(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, RENEWAL_FINISHED, applied=False)
    out = srv.funnel()
    assert out["candidates"] == ["LIN"] and "status" not in out


def test_funnel_suppresses_malformed_renewal_status(fake_root):
    _controller(fake_root, CTL_FRESH)
    for doc in ({}, {"session": "2026-09-25"},
                {"applied": True, "status": "apply_failed", "finished_at_utc": RENEWAL_FINISHED},
                {"applied": True, "status": "needs_owner_review", "finished_at_utc": RENEWAL_FINISHED},
                {"applied": False, "status": "applied", "finished_at_utc": RENEWAL_FINISHED}):
        _write(fake_root, srv.ARTIFACTS["weekly_renewal"], doc)
        out = srv.funnel()
        assert out["candidates"] == [] and out["status"] == "stale_suppressed", doc


def test_funnel_gate_passed_not_applied_stays_fresh(fake_root):
    _controller(fake_root, CTL_FRESH)
    _write(fake_root, srv.ARTIFACTS["weekly_renewal"],
           {"status": "gate_passed_not_applied", "applied": False})
    out = srv.funnel()
    assert out["candidates"] == ["LIN"] and "status" not in out


def test_funnel_honors_stored_stale_status_after_controller_refresh(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, RENEWAL_FINISHED)
    art = json.loads((fake_root / srv.ARTIFACTS["funnel"]).read_text(encoding="utf-8"))
    art.update({"status": "stale_suppressed",
                "stale_reason": "applied band renewal finished at 2026-09-26T16:00:00Z",
                "candidates": ["LIN"],
                "names": [{"ticker": "LIN", "stage": "review_candidate", "score": 0.66}]})
    _write(fake_root, srv.ARTIFACTS["funnel"], art)
    out = srv.funnel()
    assert out["candidates"] == [] and out["names"] == []
    assert out["status"] == "stale_suppressed" and out["stale_reason"]


def test_funnel_suppresses_after_sql_changed_since_write(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, RENEWAL_FINISHED)
    _funnel_artifact(fake_root, "2026-09-26T17:05:00Z")
    before = _db_hash(fake_root)
    assert srv.funnel()["candidates"] == ["LIN"]
    assert _db_hash(fake_root) == before
    con = sqlite3.connect(str(fake_root / srv.CANON_REL))
    con.execute("UPDATE reference_levels SET reference_price_low = 400.0 WHERE ticker = 'LIN'")
    con.commit()
    con.close()
    after_change = _db_hash(fake_root)
    assert after_change != before
    out = srv.funnel()
    assert out["candidates"] == [] and out["names"] == []
    assert out["status"] == "stale_suppressed" and "LIN" in out["stale_reason"]
    assert _db_hash(fake_root) == after_change
    _assert_no_wal(fake_root)


def test_funnel_suppresses_on_guard_tamper_and_pin_change(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, RENEWAL_FINISHED)
    guard = json.loads((fake_root / GUARD_REL).read_text(encoding="utf-8"))
    guard["reference_levels"]["LIN"]["reference_price_high"] = 1.0
    (fake_root / GUARD_REL).write_text(json.dumps(guard), encoding="utf-8")
    out = srv.funnel()
    assert out["status"] == "stale_suppressed" and "LIN" in out["stale_reason"]
    _write_same_version(fake_root)
    _controller(fake_root, CTL_FRESH)
    con = sqlite3.connect(str(fake_root / srv.CANON_REL))
    new_sha = "ef" * 32
    new_path = f"state/finance/baselines/test-baseline-{new_sha}.json"
    con.execute("UPDATE reference_levels SET source_artifact_sha256 = ?, source_artifact_path = ? WHERE ticker = 'LIN'",
                (new_sha, new_path))
    con.execute("UPDATE finance_state_meta SET value = ? WHERE key = 'alerts_os_reference_baseline_v1'",
                (json.dumps({"baseline_path": new_path, "baseline_sha256": new_sha}),))
    con.commit()
    con.close()
    before = _db_hash(fake_root)
    out = srv.funnel()
    assert out["status"] == "stale_suppressed" and "LIN" in out["stale_reason"]
    assert _db_hash(fake_root) == before
    _assert_no_wal(fake_root)


def test_reference_band_read_only_under_hash_in_root_path(tmp_path, monkeypatch):
    root = tmp_path / "we#ird"
    (root / "tmp").mkdir(parents=True)
    _write_same_version(root)
    monkeypatch.setenv("VERITAS_ROOT", str(root))
    before = _db_hash(root)
    band = srv.reference_band("LIN")
    assert band["found"] and band["low"] == 454.19
    assert _db_hash(root) == before
    assert not (tmp_path / "we").exists()
    _assert_no_wal(root)
    uri = srv._readonly_uri(root / srv.CANON_REL)
    assert uri.endswith("?mode=ro") and uri.count("?") == 1 and "%23" in uri and "immutable" not in uri


def test_funnel_suppresses_missing_guard_and_db(fake_root):
    _controller(fake_root, CTL_FRESH)
    _renewal(fake_root, RENEWAL_FINISHED)
    (fake_root / GUARD_REL).unlink()
    assert srv.funnel()["status"] == "stale_suppressed"
    _write_same_version(fake_root)
    _controller(fake_root, CTL_FRESH)
    (fake_root / srv.CANON_REL).unlink()
    out = srv.funnel()
    assert out["status"] == "stale_suppressed"
    assert not Path(str(fake_root / srv.CANON_REL) + "-wal").exists()
