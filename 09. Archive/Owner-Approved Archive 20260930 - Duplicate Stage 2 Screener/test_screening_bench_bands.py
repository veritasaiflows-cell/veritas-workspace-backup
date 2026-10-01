#!/usr/bin/env python3
"""Hermetic tests for the Stage 2 screening job (D-A, 2026-09-28).

No network, no live canon: the matrix module is faked, the canon is a
throwaway SQLite file, and every output stays under a temp tmp/screening.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import screening_bench_bands as sbb  # noqa: E402


class FakeMatrix:
    MIN_BARS = 3
    BAND_METHODOLOGY_VERSION = "fake-v1"

    @staticmethod
    def parse_iso_date(value: str) -> date:
        return date.fromisoformat(value)

    @staticmethod
    def utc_now_iso(now_fn=None) -> str:
        return "2026-09-28T00:00:00Z"

    @staticmethod
    def build_source_url(symbol: str, as_of: date) -> str:
        return f"https://example.invalid/q/{symbol}?d={as_of.isoformat()}"

    @staticmethod
    def default_http_get(url: str, timeout: int = 25):
        raise AssertionError("network must not be touched in tests")

    @staticmethod
    def safe_json_load(raw: bytes):
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def extract_normalized_bars(payload: dict, as_of, repairs):
        if payload.get("marker") == "extract_fail":
            return None, {"reason": "absent_usable_adjclose"}
        count = int(payload.get("bars", 3))
        final = str(payload.get("final", "2026-09-25"))
        flag = payload.get("flag", "normal")
        bars = [{"session_date": final, "flag": flag} for _ in range(count)]
        return bars, {}

    @staticmethod
    def calculate_metrics(window):
        flag = window[0].get("flag")
        if flag == "error":
            raise ArithmeticError("forced")
        if flag == "geom":
            return {
                "proposed_reference_price_low": 9.0,
                "proposed_reference_price_high": 11.0,
                "proposed_reference_invalidation_level": 9.5,
                "reference_confidence": 0.9,
                "atr20": 1.5,
                "band_floor_applied": False,
                "trend_qualified": True,
            }
        return {
            "proposed_reference_price_low": 9.0,
            "proposed_reference_price_high": 11.0,
            "proposed_reference_invalidation_level": 8.0,
            "reference_confidence": 0.9,
            "atr20": 1.5,
            "band_floor_applied": False,
            "trend_qualified": True,
        }


UNIVERSE = [
    ("AAA", "AAA", "A"),
    ("CCC", "CCC", "C"),
    ("CST", "CST", "C"),
    ("CNS", "", "C"),
    ("CFF", "CFF", "C"),
    ("CBAD", "CBAD", "C"),
    ("CFEW", "CFEW", "C"),
    ("CEXF", "CEXF", "C"),
]

QUOTES = {
    "AAA": {"payload": {"bars": 3, "final": "2026-09-25", "flag": "normal"}},
    "CCC": {"payload": {"bars": 3, "final": "2026-09-25", "flag": "normal"}},
    "CST": {"payload": {"bars": 3, "final": "2026-09-24", "flag": "normal"}},
    "CBAD": {"payload": {"bars": 3, "final": "2026-09-25", "flag": "geom"}},
    "CFEW": {"payload": {"bars": 2, "final": "2026-09-25"}},
    "CEXF": {"payload": {"marker": "extract_fail"}},
}


def _make_canon(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE securities(ticker TEXT, yfinance_symbol TEXT, active INTEGER)")
    conn.execute("CREATE TABLE universe_membership(ticker TEXT, tier TEXT)")
    conn.execute("CREATE TABLE reference_levels(ticker TEXT)")
    conn.executemany(
        "INSERT INTO securities VALUES(?,?,1)", [(t, sym) for t, sym, _ in UNIVERSE]
    )
    conn.executemany(
        "INSERT INTO universe_membership VALUES(?,?)", [(t, tier) for t, _, tier in UNIVERSE]
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    canon = tmp_path / "canon.sqlite"
    _make_canon(canon)
    quotes = tmp_path / "quotes.json"
    quotes.write_text(json.dumps(QUOTES), encoding="utf-8")
    monkeypatch.setattr(sbb, "ROOT", tmp_path)
    monkeypatch.setattr(sbb, "CANON_DB", canon)
    monkeypatch.setattr(sbb, "OUT_DIR", tmp_path / "tmp" / "screening")
    monkeypatch.setattr(sbb, "_load_scripts_module", lambda name: FakeMatrix)
    monkeypatch.setattr(sbb, "_loader_cache", {})
    return {"canon": canon, "quotes": quotes, "tmp": tmp_path}


def _args(env, extra):
    return [
        "--as-of",
        "2026-09-28",
        "--expected-session-date",
        "2026-09-25",
        "--quotes-file",
        str(env["quotes"]),
        *extra,
    ]


def test_full_flow_statuses_packet_and_digest(env):
    rc = sbb.main(
        _args(
            env,
            ["--write", "--json-output", "tmp/screening/w.json"],
        )
    )
    assert rc == 0
    packet = json.loads((env["tmp"] / "tmp" / "screening" / "w.json").read_text("utf-8"))
    by_ticker = {r["ticker"]: r for r in packet["rows"]}
    assert by_ticker["AAA"]["status"] == "ok"
    assert by_ticker["CCC"]["status"] == "ok"
    assert by_ticker["CST"]["status"] == "data_stale"
    assert by_ticker["CNS"]["status"] == "no_symbol"
    assert by_ticker["CFF"]["status"] == "fetch_failed"
    assert by_ticker["CBAD"]["status"] == "band_invalid"
    assert by_ticker["CFEW"]["status"] == "insufficient_bars"
    assert by_ticker["CEXF"]["status"] == "band_invalid"
    assert by_ticker["CCC"]["promotion_candidate_flag"] is True
    assert by_ticker["CST"]["promotion_candidate_flag"] is True
    assert by_ticker["AAA"]["promotion_candidate_flag"] is False
    assert packet["summary"]["universe_count"] == 8
    assert packet["summary"]["status_counts"]["ok"] == 2
    assert packet["summary"]["promotion_candidate_count"] == 2
    assert packet["authority"]["review_only"] is True
    assert "D-A" in packet["authority"]["standing_permission"]
    digest = (env["tmp"] / "tmp" / "screening" / "w.digest.md").read_text("utf-8")
    assert "Never written to reference_levels" in digest
    assert "CST" in digest and "CFF" in digest


def test_canon_is_read_only(env):
    before = env["canon"].read_bytes()
    rc = sbb.main(_args(env, ["--write", "--json-output", "tmp/screening/w.json"]))
    assert rc == 0
    assert env["canon"].read_bytes() == before
    conn = sqlite3.connect(env["canon"])
    assert conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0] == 0
    conn.close()


def test_output_containment_refused(env):
    for bad in ("state/finance/x.json", "tmp/other/w.json", "tmp/screening/w.md"):
        assert sbb.main(_args(env, ["--write", "--json-output", bad])) == 2
    assert sbb.main(
        _args(
            env,
            ["--write", "--json-output", "tmp/screening/w.json", "--digest-output", "tmp/x.md"],
        )
    ) == 2
    assert not (env["tmp"] / "state").exists()
    assert not (env["tmp"] / "tmp" / "screening").exists()


def test_write_requires_flag(env):
    assert sbb.main(_args(env, ["--json-output", "tmp/screening/w.json"])) == 2
    assert not (env["tmp"] / "tmp" / "screening").exists()


def test_derive_expected_session():
    assert sbb.derive_expected_session(date(2026, 9, 28)) == date(2026, 9, 25)
    assert sbb.derive_expected_session(date(2026, 9, 27)) == date(2026, 9, 25)
    assert sbb.derive_expected_session(date(2026, 9, 26)) == date(2026, 9, 25)
    assert sbb.derive_expected_session(date(2026, 9, 29)) == date(2026, 9, 28)


def test_validate_ok_then_corrupt(env):
    assert sbb.main(_args(env, ["--write", "--json-output", "tmp/screening/w.json"])) == 0
    assert sbb.main(["--validate", "--json-output", "tmp/screening/w.json"]) == 0
    path = env["tmp"] / "tmp" / "screening" / "w.json"
    packet = json.loads(path.read_text("utf-8"))
    packet["rows"][0]["status"] = "weird"
    path.write_text(json.dumps(packet), encoding="utf-8")
    assert sbb.main(["--validate", "--json-output", "tmp/screening/w.json"]) == 1
