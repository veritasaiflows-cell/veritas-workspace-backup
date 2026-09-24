from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

import veritas_mcp_server as srv

WORKSPACE = Path(__file__).resolve().parents[1]


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    (tmp_path / "state/finance/thesis").mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    con = sqlite3.connect(tmp_path / srv.CANON_REL)
    con.execute("CREATE TABLE reference_levels (ticker TEXT PRIMARY KEY, reference_price_low REAL, "
                "reference_price_high REAL, reference_invalidation_level REAL, reference_confidence REAL, "
                "source_artifact_path TEXT, source_generated_at_utc TEXT)")
    con.execute("INSERT INTO reference_levels VALUES ('LIN', 454.19, 485.87, 443.52, 0.3, 'pin.json', '2026-09-24T01:13:21Z')")
    con.commit(); con.close()
    (tmp_path / srv.THESIS_REL / "LIN.json").write_text(json.dumps({"ticker": "LIN", "status": "accepted"}), encoding="utf-8")
    (tmp_path / srv.ARTIFACTS["funnel"]).write_text(json.dumps({
        "funnel_version": "funnel-v1", "candidates": ["LIN"], "counts": {"review_candidate": 1},
        "names": [{"ticker": "LIN", "stage": "review_candidate", "score": 0.66, "components": {"x": 1}},
                  {"ticker": "ZZZ", "stage": "monitor_only"}]}), encoding="utf-8")
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
    out = srv.funnel()
    assert out["candidates"] == ["LIN"] and [n["ticker"] for n in out["names"]] == ["LIN"]
    assert "components" not in out["names"][0]


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
    monkeypatch.setenv("VERITAS_ROOT", str(WORKSPACE))
    band = srv.reference_band("MSFT")
    assert band["found"] and band["invalidation"] < band["low"] and band["reference_confidence"] is not None
