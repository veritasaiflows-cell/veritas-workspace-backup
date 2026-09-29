"""Tests for scripts/weekly_screening_refresh.py (no network, no live canon)."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import weekly_screening_refresh as wsr  # noqa: E402

SESSION = "2026-09-25"
LIVE_ROOT = Path(__file__).resolve().parent.parent


def _approval(**overrides):
    record = json.loads((LIVE_ROOT / wsr.APPROVAL_REL).read_text(encoding="utf-8"))
    record.update(overrides)
    return record


def _root(tmp_path: Path, approval: dict | None = None) -> Path:
    root = tmp_path / "ws"
    (root / "tmp").mkdir(parents=True)
    if approval is not None:
        p = root / wsr.APPROVAL_REL
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(approval), encoding="utf-8")
    return root


def _payload(n_bars: int = 260, end: str = SESSION, drift: float = 0.2, last_drop: float = 0.0, volume: float = 1_000_000):
    """Daily bars ending on ``end`` (weekdays), gently trending by ``drift`` per bar."""
    end_d = date.fromisoformat(end)
    days = []
    d = end_d
    while len(days) < n_bars:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    days.reverse()
    ts, o, h, l, c, v = [], [], [], [], [], []
    price = 100.0
    for i, day in enumerate(days):
        price += drift
        close = price - (last_drop if i == len(days) - 1 else 0.0)
        ts.append(int(datetime(day.year, day.month, day.day, 14, 30, tzinfo=timezone.utc).timestamp()))
        o.append(close)
        h.append(close + 1.5)
        l.append(close - 1.5)
        c.append(close)
        v.append(volume)
    return {"chart": {"result": [{
        "meta": {"exchangeTimezoneName": "America/New_York"},
        "timestamp": ts,
        "events": {},
        "indicators": {"quote": [{"open": o, "high": h, "low": l, "close": c, "volume": v}],
                       "adjclose": [{"adjclose": list(c)}]},
    }]}}


def _getter(payloads: dict[str, object], calls: list[str]):
    def get(url, timeout=25):
        calls.append(url)
        for sym, body in payloads.items():
            if f"/chart/{sym}?" in url:
                if isinstance(body, Exception):
                    raise body
                if body is None:
                    return 404, b""
                return 200, json.dumps(body).encode()
        return 404, b""
    return get


def _universe(*members):
    return lambda root: [dict(ticker=t, tier=tier, yahoo_symbol=sym, name=t, sector="Tech") for t, tier, sym in members]


def _run(root, universe, payloads, calls, **kw):
    return wsr.run_screening(
        root, http_get=_getter(payloads, calls), universe_loader=universe,
        sleep=lambda s: None, expected_session=SESSION, **kw,
    )


# --- gate: refusals happen before any provider call ---------------------------------

def test_missing_approval_refuses_with_zero_calls(tmp_path):
    root = _root(tmp_path, approval=None)
    calls: list[str] = []
    with pytest.raises(wsr.ScreeningRefused, match="missing"):
        _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, calls)
    assert calls == []


def test_inactive_approval_refuses_with_zero_calls(tmp_path):
    root = _root(tmp_path, _approval(active=False))
    calls: list[str] = []
    with pytest.raises(wsr.ScreeningRefused, match="not active"):
        _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, calls)
    assert calls == []


@pytest.mark.parametrize("bad", [None, "5", -1, True, float("nan")])
def test_malformed_limit_refuses(tmp_path, bad):
    approval = _approval()
    approval["limits"] = dict(approval["limits"], max_names_per_run=bad)
    root = _root(tmp_path, approval)
    calls: list[str] = []
    with pytest.raises(wsr.ScreeningRefused):
        _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, calls)
    assert calls == []


def test_wrong_id_refuses(tmp_path):
    root = _root(tmp_path, _approval(id="band-renewal-option-b"))
    with pytest.raises(wsr.ScreeningRefused, match="wrong id"):
        _run(root, _universe(("AAA", "C", "AAA")), {}, [])


def test_universe_over_limit_refuses_without_truncation(tmp_path):
    approval = _approval()
    approval["limits"] = dict(approval["limits"], max_names_per_run=2)
    root = _root(tmp_path, approval)
    calls: list[str] = []
    with pytest.raises(wsr.ScreeningRefused, match="no truncation"):
        _run(root, _universe(("A1", "C", "A1"), ("A2", "C", "A2"), ("A3", "C", "A3")), {}, calls)
    assert calls == []


def test_empty_universe_refuses(tmp_path):
    root = _root(tmp_path, _approval())
    with pytest.raises(wsr.ScreeningRefused, match="empty"):
        _run(root, lambda r: [], {}, [])


# --- method and classification ----------------------------------------------------

def test_uses_matrix_method_and_matches_candidate_band_math(tmp_path):
    root = _root(tmp_path, _approval())
    packet = _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, [])
    row = packet["rows"][0]
    assert row["status"] == "ok"
    assert packet["method"] == wsr.matrix.BAND_METHODOLOGY_VERSION
    bars, _ = wsr.matrix.extract_normalized_bars(_payload(), date(2026, 9, 26), None)
    m = wsr.matrix.calculate_metrics(bars[-wsr.matrix.MIN_BARS:])
    assert row["bench_low"] == round(m["proposed_reference_price_low"], 4)
    assert row["bench_high"] == round(m["proposed_reference_price_high"], 4)
    assert row["bench_invalidation"] == round(m["proposed_reference_invalidation_level"], 4)
    assert row["bench_invalidation"] < row["bench_low"]


@pytest.mark.parametrize("close,expected", [
    (50.0, "below_invalidation"), (89.0, "below_band"), (90.2, "near_band_low"),
    (95.0, "in_band"), (101.0, "above_band"),
])
def test_classify_position(close, expected):
    assert wsr.classify_position(close, low=90.0, high=100.0, invalidation=80.0, atr20=1.0) == expected


def test_uptrend_above_band_is_not_a_review_candidate(tmp_path):
    root = _root(tmp_path, _approval())
    packet = _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload(volume=10_000_000)}, [])
    row = packet["rows"][0]
    assert row["trend_qualified"] is True
    assert row["position"] == "above_band"
    assert "review_candidate" not in row["flags"]


def test_liquid_tier_c_pullback_is_flagged_but_tier_b_is_not(tmp_path):
    root = _root(tmp_path, _approval())
    # Strong uptrend, then the last close drops back to the SMA50 zone.
    body = _payload(volume=10_000_000, drift=0.4, last_drop=11.0)
    packet = _run(root, _universe(("CCC", "C", "CCC"), ("BBB", "B", "BBB")), {"CCC": body, "BBB": body}, [])
    rows = {r["ticker"]: r for r in packet["rows"]}
    assert rows["CCC"]["position"] in ("near_band_low", "in_band")
    assert rows["CCC"]["flags"] == ["review_candidate"]
    assert rows["BBB"]["flags"] == []
    assert packet["flags"]["review_candidate"] == ["CCC"]


def test_illiquid_tier_c_pullback_is_not_flagged(tmp_path):
    root = _root(tmp_path, _approval())
    body = _payload(volume=10_000, drift=0.4, last_drop=11.0)
    packet = _run(root, _universe(("CCC", "C", "CCC")), {"CCC": body}, [])
    assert packet["rows"][0]["flags"] == []


def test_bench_breakdown_flag(tmp_path):
    root = _root(tmp_path, _approval())
    packet = _run(root, _universe(("DDD", "A", "DDD")), {"DDD": _payload(last_drop=40.0)}, [])
    row = packet["rows"][0]
    assert row["position"] == "below_invalidation"
    assert row["flags"] == ["bench_breakdown"]


# --- data gaps are reported, never patched ------------------------------------------

def test_gap_statuses(tmp_path):
    root = _root(tmp_path, _approval())
    broken = _payload()
    broken["chart"]["result"][0]["indicators"]["quote"][0]["close"][-5] = None
    delisted = _payload()
    delisted["chart"]["result"][0]["timestamp"] = []
    delisted["chart"]["result"][0]["meta"].update(regularMarketPrice=209.7, firstTradeDate=1784295000)
    payloads = {
        "OK": _payload(),
        "GONE": delisted,
        "SHORT": _payload(n_bars=100),
        "STALE": _payload(end="2026-09-24"),
        "BROKEN": broken,
        "DOWN": None,
        "BOOM": TimeoutError("x"),
    }
    universe = _universe(*[(t, "C", t) for t in payloads] + [("NOSYM", "C", "")])
    packet = _run(root, universe, payloads, [])
    status = {r["ticker"]: r["status"] for r in packet["rows"]}
    assert status == {
        "OK": "ok", "GONE": "no_bars_identity_review", "SHORT": "insufficient_history", "STALE": "stale_quote",
        "BROKEN": "needs_repair", "DOWN": "fetch_failed", "BOOM": "fetch_failed",
        "NOSYM": "no_provider_symbol",
    }
    assert packet["run_status"] == "complete_with_gaps"
    assert packet["counts"]["provider_calls"] == 7  # the blank-symbol name makes no call
    gone = next(r for r in packet["rows"] if r["ticker"] == "GONE")
    assert "209.7" in gone["detail"]


def test_repair_list_is_never_applied(tmp_path, monkeypatch):
    seen = []
    real = wsr.matrix.extract_normalized_bars

    def spy(payload, as_of, repairs=None):
        seen.append(repairs)
        return real(payload, as_of, repairs)

    monkeypatch.setattr(wsr.matrix, "extract_normalized_bars", spy)
    root = _root(tmp_path, _approval())
    _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, [])
    assert seen == [None]


# --- run bounds -------------------------------------------------------------------

def test_failure_rate_stop_marks_run_stopped(tmp_path):
    approval = _approval()
    approval["limits"] = dict(approval["limits"], failure_rate_min_sample=4, stop_when_failure_rate_exceeds=0.25)
    root = _root(tmp_path, approval)
    universe = _universe(*[(f"T{i}", "C", f"T{i}") for i in range(10)])
    calls: list[str] = []
    packet = _run(root, universe, {}, calls)  # every fetch 404s
    assert packet["run_status"] == "stopped"
    assert "failure rate" in packet["stop_reason"]
    assert len(calls) == 4
    assert packet["not_attempted"] == [f"T{i}" for i in range(4, 10)]


def test_duration_cap_stops(tmp_path):
    approval = _approval()
    approval["limits"] = dict(approval["limits"], max_run_duration_seconds=10)
    root = _root(tmp_path, approval)
    clock = iter(range(0, 1000, 6))
    universe = _universe(*[(f"T{i}", "C", f"T{i}") for i in range(5)])
    packet = wsr.run_screening(
        root, http_get=_getter({f"T{i}": _payload() for i in range(5)}, []), universe_loader=universe,
        sleep=lambda s: None, monotonic=lambda: next(clock), expected_session=SESSION,
    )
    assert packet["run_status"] == "stopped"
    assert packet["stop_reason"] == "max_run_duration_seconds reached"
    assert packet["counts"]["screened"] < 5


def test_pacing_sleeps_between_requests(tmp_path):
    root = _root(tmp_path, _approval())
    slept: list[float] = []
    universe = _universe(("A1", "C", "A1"), ("A2", "C", "A2"), ("A3", "C", "A3"))
    wsr.run_screening(root, http_get=_getter({}, []), universe_loader=universe,
                      sleep=slept.append, expected_session=SESSION)
    assert slept == [0.5, 0.5]


# --- outputs and authority --------------------------------------------------------

def test_packet_authority_is_review_only(tmp_path):
    root = _root(tmp_path, _approval())
    packet = _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, [])
    auth = packet["authority"]
    assert auth["review_only"] is True
    assert all(v is False for k, v in auth.items() if k != "review_only")


def test_write_outputs_stay_under_tmp(tmp_path):
    root = _root(tmp_path, _approval())
    packet = _run(root, _universe(("AAA", "C", "AAA")), {"AAA": _payload()}, [])
    paths = wsr.write_outputs(root, packet)
    for p in paths:
        p.resolve().relative_to((root / "tmp").resolve())
        assert p.exists()
    assert (root / "tmp/weekly-screening" / f"{SESSION}.json").exists()
    md = (root / wsr.PACKET_MD_REL).read_text(encoding="utf-8")
    assert "Not decision-grade" in md or "not decision-grade" in md.lower()
    assert not (root / "state/finance/finance-canon.sqlite").exists()


def test_cli_refusal_exit_code(tmp_path, capsys):
    root = _root(tmp_path, _approval(active=False))
    rc = wsr.main(["--root", str(root), "--expected-session-date", SESSION])
    assert rc == 3
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "refused", "reason": "standing approval is not active", "provider_calls": 0}


def test_live_universe_read_does_not_change_canon():
    """Reads the live canon through the guarded read path; logical hash must not move."""
    import sqlite_snapshot

    db = LIVE_ROOT / wsr.DB_REL
    before = sqlite_snapshot.logical_sha256(db)
    universe = wsr.load_universe(LIVE_ROOT)
    after = sqlite_snapshot.logical_sha256(db)
    assert before == after
    assert len(universe) >= 32
    assert {m["tier"] for m in universe} <= {"A", "B", "C"}


def test_breakdowns_are_grouped_by_sector_in_digest(tmp_path):
    root = _root(tmp_path, _approval())
    universe = lambda r: [
        dict(ticker="U1", tier="C", yahoo_symbol="U1", name="U1", sector="Utilities"),
        dict(ticker="U2", tier="C", yahoo_symbol="U2", name="U2", sector="Utilities"),
        dict(ticker="X1", tier="A", yahoo_symbol="X1", name="X1", sector="Energy"),
    ]
    body = _payload(last_drop=40.0)
    packet = _run(root, universe, {"U1": body, "U2": body, "X1": body}, [])
    md = wsr.markdown_for(packet)
    assert "**Utilities** (2): U1" in md
    assert "**Energy** (1): X1 (Tier A" in md
    assert md.index("**Utilities**") < md.index("**Energy**")
