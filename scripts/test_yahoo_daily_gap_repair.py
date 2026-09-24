from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yahoo_daily_gap_repair as repair

WORKSPACE = Path(__file__).resolve().parents[1]
NY = repair.EXCHANGE_TZ
DAYS = ["2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22"]


def ts(day: str, hh: int = 9, mm: int = 30) -> int:
    y, m, d = map(int, day.split("-"))
    return int(datetime(y, m, d, hh, mm, tzinfo=NY).timestamp())


def daily_payload(missing: set[str], events: dict | None = None) -> bytes:
    stamps, q = [], {k: [] for k in ("open", "high", "low", "close", "volume")}
    for i, day in enumerate(DAYS):
        stamps.append(ts(day))
        for k in q:
            q[k].append(None if day in missing else (1000 if k == "volume" else 100.0 + i))
    return json.dumps({"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [q]},
                                             "events": events or {}}]}}).encode()


def intraday_payload(close_offset: float = 0.0, bars_per_day: int = 13) -> bytes:
    stamps, q = [], {k: [] for k in ("open", "high", "low", "close", "volume")}
    for i, day in enumerate(DAYS):
        for b in range(bars_per_day):
            minutes = 9 * 60 + 30 + 30 * b
            stamps.append(ts(day, minutes // 60, minutes % 60))
            last = b == bars_per_day - 1
            q["open"].append(99.5 + i); q["high"].append(101.0 + i); q["low"].append(99.0 + i)
            q["close"].append((100.0 + i + close_offset) if last else 100.2 + i); q["volume"].append(80)
    return json.dumps({"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [q]}}]}}).encode()


def fake_http(daily: bytes, intraday: bytes):
    def get(url: str):
        return 200, (intraday if "interval=30m" in url else daily)
    return get


def test_clean_ticker_writes_nothing(tmp_path: Path) -> None:
    report = repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload(set()), intraday_payload()),
                        completed_through="2026-09-22", write=True)
    assert report["gaps_found"] == 0 and report["repairs_added"] == 0 and report["status"] == "ok"
    assert not (tmp_path / repair.OVERLAY_REL).exists()


def test_gap_repaired_from_calibrated_intraday(tmp_path: Path) -> None:
    report = repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload({"2026-09-21"}), intraday_payload()),
                        completed_through="2026-09-22", write=True)
    assert report["repairs_added"] == 1 and report["status"] == "ok"
    overlay = json.loads((tmp_path / repair.OVERLAY_REL).read_text(encoding="utf-8"))
    bar = overlay["repairs"]["AAA"]["2026-09-21"]
    assert bar["close"] == 103.0 and bar["high"] == 104.0 and bar["method"] == repair.METHOD


def test_uncalibrated_method_blocks(tmp_path: Path) -> None:
    report = repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload({"2026-09-21"}), intraday_payload(close_offset=1.0)),
                        completed_through="2026-09-22", write=True)
    assert report["repairs_added"] == 0 and report["status"] == "warning"
    assert report["blocked"]["AAA"]["2026-09-21"] == "method_not_calibrated_for_ticker"


def test_corporate_action_on_gap_date_blocks(tmp_path: Path) -> None:
    events = {"dividends": {"x": {"date": ts("2026-09-21"), "amount": 1.0}}}
    report = repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload({"2026-09-21"}, events), intraday_payload()),
                        completed_through="2026-09-22", write=True)
    assert report["blocked"]["AAA"]["2026-09-21"] == "corporate_action_on_gap_date"


def test_thin_intraday_coverage_blocks(tmp_path: Path) -> None:
    report = repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload({"2026-09-21"}), intraday_payload(bars_per_day=5)),
                        completed_through="2026-09-22", write=True)
    assert report["repairs_added"] == 0 and report["status"] == "warning"


def test_existing_repair_never_rewritten(tmp_path: Path) -> None:
    http = fake_http(daily_payload({"2026-09-21"}), intraday_payload())
    repair.run(tmp_path, tickers=["AAA"], http_get=http, completed_through="2026-09-22", write=True)
    first = (tmp_path / repair.OVERLAY_REL).read_bytes()
    again = repair.run(tmp_path, tickers=["AAA"], http_get=http, completed_through="2026-09-22", write=True)
    assert again["repairs_added"] == 0 and (tmp_path / repair.OVERLAY_REL).read_bytes() == first


def test_scope_follows_controller(tmp_path: Path) -> None:
    (tmp_path / "tmp").mkdir()
    (tmp_path / repair.CONTROLLER_REL).write_text(json.dumps({"rows": [{"ticker": "ZZZ"}, {"ticker": "AAA"}]}), encoding="utf-8")
    report = repair.run(tmp_path, http_get=fake_http(daily_payload(set()), intraday_payload()), completed_through="2026-09-22")
    assert report["scope_count"] == 2 and [r["ticker"] for r in report["results"]] == ["AAA", "ZZZ"]
    empty = repair.run(tmp_path / "none", http_get=fake_http(b"", b""), completed_through="2026-09-22")
    assert empty["status"] == "error"


def test_redirected_root_never_touches_production(tmp_path: Path) -> None:
    production = [WORKSPACE / repair.OVERLAY_REL, WORKSPACE / repair.REPORT_REL]
    before = [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in production]
    repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload({"2026-09-21"}), intraday_payload()),
               completed_through="2026-09-22", write=True)
    assert before == [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in production]


def test_generator_uses_repair_only_where_yahoo_is_null() -> None:
    from datetime import date as _date
    import yahoo_reference_level_matrix as matrix
    stamps = [ts(d, 13, 30) for d in DAYS[:3]]
    quote = {"open": [100.0, None, 102.0], "high": [101.0, None, 103.0], "low": [99.0, None, 101.0],
             "close": [100.5, None, 102.5], "volume": [10, None, 12]}
    payload = {"chart": {"result": [{"meta": {"exchangeTimezoneName": "America/New_York"}, "timestamp": stamps,
                                      "indicators": {"quote": [quote], "adjclose": [{"adjclose": [50.25, None, 102.5]}]}}]}}
    blocked, meta = matrix.extract_normalized_bars(payload, _date(2026, 9, 30))
    assert blocked is None and meta["reason"] == "nonfinite_ohlcv_or_adjclose"
    fix = {"2026-09-17": {"open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 11}}
    bars, meta = matrix.extract_normalized_bars(payload, _date(2026, 9, 30), fix)
    assert meta["repaired_session_dates"] == ["2026-09-17"]
    assert bars[1]["adjustment_factor"] == bars[0]["adjustment_factor"] == 0.5
    assert bars[1]["close"] == 101.5 * 0.5
    # An official bar is never replaced by an overlay entry.
    bars2, meta2 = matrix.extract_normalized_bars(payload, _date(2026, 9, 30), {**fix, "2026-09-16": {"close": 1.0}})
    assert bars2[0]["close"] == 50.25 and meta2["repaired_session_dates"] == ["2026-09-17"]


def test_newest_session_gets_grace(tmp_path: Path) -> None:
    report = repair.run(tmp_path, tickers=["AAA"], http_get=fake_http(daily_payload({"2026-09-22"}), intraday_payload()),
                        completed_through="2026-09-22", write=True)
    assert report["gaps_found"] == 0 and report["repairs_added"] == 0
    assert report["results"][0]["pending_latest"] == ["2026-09-22"]
