#!/usr/bin/env python3
"""Hermetic tests for promotion_candidate_band (P4-2 slice B r3).

Every test copies staged-root to a tempdir and runs with cwd = that copy, so
the candidate tier check reads the temp guard DB. Quote bars are fixtures only
(http_get stub); no network. Never touches the live workspace.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
V2 = HERE.parent
ROOT = V2.parent
STAGED_ROOT = ROOT / "tmp" / "p4-2-writer-lane-20260927" / "staged-root"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"PASS {name}")
    else:
        FAIL.append(name)
        print(f"FAIL {name} {detail}")


def load_band():
    if str(V2) not in sys.path:
        sys.path.insert(0, str(V2))
    spec = importlib.util.spec_from_file_location(
        "promotion_candidate_band_v2", str(V2 / "promotion_candidate_band.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


BAND = load_band()


def fresh_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="pcb-"))
    shutil.copytree(STAGED_ROOT, tmp / "root", symlinks=False)
    return tmp / "root"


def fixture_payload(n: int, last: date) -> bytes:
    """Fake Yahoo chart payload: n monotonic daily sessions ending on `last`."""
    start = last - timedelta(days=n - 1)
    ts, opens, highs, lows, closes, vols, adj = [], [], [], [], [], [], []
    for i in range(n):
        day = start + timedelta(days=i)
        noon = datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)
        close = 100.0 + i * 0.5
        ts.append(int(noon.timestamp()))
        opens.append(round(close - 0.1, 4))
        highs.append(round(close * 1.01, 4))
        lows.append(round(close * 0.99, 4))
        closes.append(round(close, 4))
        vols.append(1_000_000)
        adj.append(round(close, 4))
    return json.dumps({
        "chart": {"result": [{
            "meta": {"exchangeTimezoneName": "America/New_York"},
            "timestamp": ts,
            "indicators": {
                "quote": [{"open": opens, "high": highs, "low": lows,
                           "close": closes, "volume": vols}],
                "adjclose": [{"adjclose": adj}],
            },
        }]},
    }).encode("utf-8")


def stub_get(payload: bytes):
    def get(url: str, timeout: int = 25):
        return 200, payload
    return get


class Cwd:
    def __init__(self, path: Path):
        self.path, self.prev = path, Path.cwd()

    def __enter__(self):
        os.chdir(self.path)
        return self.path

    def __exit__(self, *exc):
        os.chdir(self.prev)
        return False


LAST = date(2026, 9, 25)
AS_OF = "2026-09-26"


def test_happy_bandless_tier_c() -> None:
    root = fresh_root()
    with Cwd(root):
        packet = BAND.build_band("BAC", AS_OF, "2026-09-25",
                                 http_get=stub_get(fixture_payload(260, LAST)))
    check("happy_keys", packet.get("schema") == "veritas.promotion_candidate_band.v1"
          and packet.get("ticker") == "BAC" and packet.get("yahoo_symbol") == "BAC"
          and packet.get("scope_role") == "promotion_candidate"
          and packet.get("bar_count") == 252 and packet.get("method") == "mech-v3-floor-atr20",
          json.dumps(packet)[:300])
    check("happy_no_scope_block", "scope" not in packet, str(sorted(packet)))
    check("happy_triple_sane",
          packet["reference_invalidation_level"] < packet["reference_price_low"]
          < packet["reference_price_high"]
          and packet["reference_confidence"] is not None
          and packet["width_atr_multiple"] >= 1.0, json.dumps(packet)[:300])
    check("happy_review_only",
          packet["authority"].get("review_only") is True
          and packet["authority"].get("canon_write_allowed") is False
          and packet["authority"].get("tier_assignment_allowed") is False)


def test_write_only_with_flag() -> None:
    root = fresh_root()
    with Cwd(root):
        packet = BAND.build_band("BAC", AS_OF, "2026-09-25",
                                 http_get=stub_get(fixture_payload(260, LAST)))
        try:
            BAND.write_packet(packet, "tmp/bac-band.json", False)
            check("write_requires_flag", False, "wrote without --write")
        except ValueError:
            check("write_requires_flag", True)
        path = BAND.write_packet(packet, "tmp/bac-band.json", True)
    check("write_packet_file", path.is_file() and json.loads(path.read_text())["ticker"] == "BAC")
    with Cwd(root):
        try:
            BAND.write_packet(packet, "../escape.json", True)
            check("write_path_containment", False, "outside path accepted")
        except ValueError:
            check("write_path_containment", True)


def test_refuse_tier_ab_and_inactive() -> None:
    root = fresh_root()
    with Cwd(root):
        for ticker, label in (("NVDA", "tier_a"), ("MSFT", "tier_b"), ("ZZZZ", "inactive")):
            try:
                BAND.build_band(ticker, AS_OF, "2026-09-25",
                                http_get=stub_get(fixture_payload(260, LAST)))
                check(f"refuse_{label}", False, "no refusal")
            except ValueError as e:
                check(f"refuse_{label}", True, str(e)[:100])


def test_refuse_bars_and_dates() -> None:
    root = fresh_root()
    with Cwd(root):
        try:
            BAND.build_band("BAC", AS_OF, "2026-09-25",
                            http_get=stub_get(fixture_payload(100, LAST)))
            check("refuse_few_bars", False, "no refusal")
        except ValueError:
            check("refuse_few_bars", True)
        try:
            BAND.build_band("BAC", AS_OF, "2026-09-24",
                            http_get=stub_get(fixture_payload(260, LAST)))
            check("refuse_date_mismatch", False, "no refusal")
        except ValueError:
            check("refuse_date_mismatch", True)


def fixture_flat_payload(n: int, last: date) -> bytes:
    """Flat market with epsilon wobble: forces the ATR20 floor in float dust."""
    start = last - timedelta(days=n - 1)
    ts, opens, highs, lows, closes, vols, adj = [], [], [], [], [], [], []
    for i in range(n):
        day = start + timedelta(days=i)
        noon = datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)
        close = 100.0 + ((-1) ** i) * 1e-7
        ts.append(int(noon.timestamp()))
        opens.append(close)
        highs.append(close + 1e-7)
        lows.append(close - 1e-7)
        closes.append(close)
        vols.append(1_000_000)
        adj.append(close)
    return json.dumps({
        "chart": {"result": [{
            "meta": {"exchangeTimezoneName": "America/New_York"},
            "timestamp": ts,
            "indicators": {
                "quote": [{"open": opens, "high": highs, "low": lows,
                           "close": closes, "volume": vols}],
                "adjclose": [{"adjclose": adj}],
            },
        }]},
    }).encode("utf-8")


def test_floor_width_tolerance() -> None:
    root = fresh_root()
    with Cwd(root):
        packet = BAND.build_band("BAC", AS_OF, "2026-09-25",
                                 http_get=stub_get(fixture_flat_payload(260, LAST)))
    check("floor_applied", packet.get("band_floor_applied") is True, json.dumps(packet)[:200])
    width = packet["reference_price_high"] - packet["reference_price_low"]
    atr = packet["atr20"]
    check("floor_within_tolerance", width + 1e-9 * max(1.0, abs(atr)) >= atr,
          f"width={width} atr={atr}")


class _FakeRec:
    def __init__(self, tier: str, symbol: str):
        self.tier, self.yfinance_symbol = tier, symbol


class _FakeAccess:
    def __init__(self, rec):
        self._rec = rec

    def universe_memberships(self, tickers):
        name = list(tickers)[0]
        return {name: self._rec}


def test_sql_symbol_mapping() -> None:
    import hashlib as _hl
    root = fresh_root()
    seen: dict = {}

    def spy_get(url: str, timeout: int = 25):
        seen["url"] = url
        return 200, fixture_payload(260, LAST)

    with Cwd(root):
        access_mod = BAND._load_scripts_module("finance_sql_canon_access")
        real = access_mod.FinanceSqlCanonAccess
        access_mod.FinanceSqlCanonAccess = lambda *a, **k: _FakeAccess(_FakeRec("C", "BRK-B"))
        try:
            packet = BAND.build_band("BRK.B", AS_OF, "2026-09-25", http_get=spy_get)
        finally:
            access_mod.FinanceSqlCanonAccess = real
    check("sql_symbol_used", packet.get("yahoo_symbol") == "BRK-B"
          and "BRK-B" in seen.get("url", ""), str(seen)[:200])
    with Cwd(root):
        access_mod = BAND._load_scripts_module("finance_sql_canon_access")
        real = access_mod.FinanceSqlCanonAccess
        access_mod.FinanceSqlCanonAccess = lambda *a, **k: _FakeAccess(_FakeRec("C", ""))
        try:
            BAND.build_band("BRK.B", AS_OF, "2026-09-25", http_get=spy_get)
            check("blank_symbol_refused", False, "no refusal")
        except ValueError:
            check("blank_symbol_refused", True)
        finally:
            access_mod.FinanceSqlCanonAccess = real


def test_provenance_fields() -> None:
    import hashlib as _hl
    root = fresh_root()
    raw = fixture_payload(260, LAST)
    with Cwd(root):
        packet = BAND.build_band("BAC", AS_OF, "2026-09-25", http_get=stub_get(raw))
    check("provenance_fields",
          packet.get("raw_sha256") == _hl.sha256(raw).hexdigest()
          and bool(packet.get("retrieved_at_utc"))
          and packet.get("observed_final_session_date") == "2026-09-25"
          and packet.get("repairs_applied") is False, json.dumps(packet)[:300])


def test_clean_refusals() -> None:
    from statistics import StatisticsError
    root = fresh_root()
    with Cwd(root):
        def boom(url: str, timeout: int = 25):
            raise RuntimeError("net down")
        try:
            BAND.build_band("BAC", AS_OF, "2026-09-25", http_get=boom)
            check("http_error_clean", False, "no refusal")
        except ValueError:
            check("http_error_clean", True)
        except RuntimeError:
            check("http_error_clean", False, "traceback leaked")
        matrix = BAND._load_scripts_module("yahoo_reference_level_matrix")
        real_calc = matrix.calculate_metrics
        matrix.calculate_metrics = lambda bars: (_ for _ in ()).throw(StatisticsError("x"))
        try:
            BAND.build_band("BAC", AS_OF, "2026-09-25",
                            http_get=stub_get(fixture_payload(260, LAST)))
            check("calc_error_clean", False, "no refusal")
        except ValueError:
            check("calc_error_clean", True)
        except StatisticsError:
            check("calc_error_clean", False, "traceback leaked")
        finally:
            matrix.calculate_metrics = real_calc
    check("docstring_no_repairs", "no repair list" in (BAND.__doc__ or "").lower())


def run_cli(root: Path, *args: str):
    return subprocess.run(
        [sys.executable, "-B", str(V2 / "promotion_candidate_band.py"), *args],
        cwd=str(root), capture_output=True, text=True, timeout=300,
    )


def test_cli_refusals_before_network() -> None:
    root = fresh_root()
    r = run_cli(root, "--ticker", "NVDA", "--as-of", AS_OF,
                "--expected-session-date", "2026-09-25",
                "--json-output", "tmp/nvda.json", "--write")
    check("cli_refuses_tier_a", r.returncode != 0 and not (root / "tmp" / "nvda.json").exists(),
          r.stderr[-200:])
    r = run_cli(root, "--ticker", "BAC", "--as-of", AS_OF,
                "--expected-session-date", "2026-09-25",
                "--json-output", "tmp/bac.md", "--write")
    check("cli_refuses_markdown", r.returncode != 0 and not (root / "tmp" / "bac.md").exists(),
          r.stderr[-200:])
    r = run_cli(root, "--ticker", "BAC", "--as-of", AS_OF,
                "--expected-session-date", "2026-09-25",
                "--json-output", "tmp/bac.json")
    check("cli_requires_write", r.returncode != 0 and not (root / "tmp" / "bac.json").exists(),
          r.stderr[-200:])


def main() -> int:
    for fn in (test_happy_bandless_tier_c, test_write_only_with_flag,
               test_refuse_tier_ab_and_inactive, test_refuse_bars_and_dates,
               test_floor_width_tolerance, test_sql_symbol_mapping,
               test_provenance_fields, test_clean_refusals,
               test_cli_refusals_before_network):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"{type(e).__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
