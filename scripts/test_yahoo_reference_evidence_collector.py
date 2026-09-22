"""Unit tests for the Yahoo-only reference evidence collector (no network)."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


COLLECTOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "yahoo_reference_evidence_collector.py"
COLLECTOR_SPEC = spec_from_file_location("yahoo_reference_evidence_collector", str(COLLECTOR_PATH))
collector = module_from_spec(COLLECTOR_SPEC)
COLLECTOR_SPEC.loader.exec_module(collector)

AS_OF_DATE = "2025-01-03"
CUTOFF_EPOCH = int(datetime(2025, 1, 3, tzinfo=timezone.utc).timestamp())
FIXED_NOW = datetime(2025, 1, 3, 1, 2, 3, tzinfo=timezone.utc)


def fixed_now():
    return FIXED_NOW


def make_chart_raw(
    count, cutoff_epoch=CUTOFF_EPOCH, invalid_index=None, with_adjclose=True,
    with_events=True, include_cutoff=False,
):
    timestamps = [int(cutoff_epoch) - (count - index) * 86400 for index in range(count)]
    if include_cutoff:
        timestamps.append(int(cutoff_epoch))
    opens = [100.0 + index * 0.1 for index in range(len(timestamps))]
    highs = [value + 1.0 for value in opens]
    lows = [value - 1.0 for value in opens]
    closes = [value + 0.5 for value in opens]
    volumes = [1_000_000 + index for index in range(len(timestamps))]
    if invalid_index is not None:
        highs[invalid_index] = -5.0
    quote = {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}
    indicators = {"quote": [quote]}
    if with_adjclose:
        indicators["adjclose"] = [{"adjclose": list(closes)}]
    first = {"meta": {"symbol": "TEST"}, "timestamp": timestamps, "indicators": indicators}
    if with_events:
        first["events"] = {"dividends": {"1700000000": {"amount": 0.5}}, "splits": {}}
    return json.dumps({"chart": {"result": [first], "error": None}}).encode("utf-8")


def mock_http_for(raw, status=200, record=None):
    def _get(url, timeout=20):
        if record is not None:
            record.append(url)
        return status, raw
    return _get


def raising_http(url, timeout=20):
    raise ConnectionError("simulated network failure")


class YahooCollectorTests(unittest.TestCase):
    def test_default_scope_is_exactly_required_32_symbols(self):
        expected = (
            "AMD", "AMZN", "BKNG", "BRK.B", "CAT", "CME", "CVX", "ECL",
            "ETN", "GE", "GOOG", "GS", "ITA", "JPM", "KTOS", "LIN",
            "LLY", "LMT", "LNG", "META", "MSFT", "NFLX", "NVDA", "PH",
            "PLTR", "RTX", "SMCI", "TMUS", "VMC", "VRT", "WMB", "XOM",
        )
        self.assertEqual(tuple(collector.SCOPED_TICKERS), expected)
        self.assertEqual(len(collector.SCOPED_TICKERS), 32)
        self.assertEqual(tuple(sorted(collector.SCOPED_TICKERS)), expected)
        self.assertEqual(collector.to_yahoo_symbol("BRK.B"), "BRK-B")
        with self.assertRaises(ValueError):
            collector.build_document(
                AS_OF_DATE, ["AAPL"], http_get=mock_http_for(make_chart_raw(252)), now_fn=fixed_now
            )

    def test_normal_yahoo_payload_is_observed_unverified_with_safety_flags(self):
        raw = make_chart_raw(252)
        urls = []
        document = collector.build_document(
            AS_OF_DATE, ["NVDA"], http_get=mock_http_for(raw, record=urls), now_fn=fixed_now
        )
        self.assertEqual(document["source_mode"], "single_source_yahoo_personal_use")
        self.assertTrue(document["review_only"])
        self.assertFalse(document["independent_reconciliation"])
        self.assertFalse(document["canonical_write_allowed"])
        self.assertFalse(document["scheduler_change_allowed"])
        self.assertFalse(document["account_or_execution_action_allowed"])
        entry = document["tickers"]["NVDA"]
        self.assertEqual(entry["status"], "observed_unverified")
        self.assertEqual(entry["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(entry["adjustment_basis"], "yahoo_chart_unverified")
        self.assertEqual(entry["corporate_action_evidence"], "unverified")
        self.assertTrue(entry["adjustment_fields_present"]["adjclose"])
        self.assertTrue(entry["adjustment_fields_present"]["dividends"])
        self.assertIn("query1.finance.yahoo.com", urls[0])
        self.assertIn("events=div%2Csplits", urls[0])

    def test_brkb_maps_to_brk_dash_b(self):
        urls = []
        document = collector.build_document(
            AS_OF_DATE, ["BRK.B"], http_get=mock_http_for(make_chart_raw(252), record=urls), now_fn=fixed_now
        )
        entry = document["tickers"]["BRK.B"]
        self.assertEqual(entry["yahoo_symbol"], "BRK-B")
        self.assertEqual(entry["canonical_ticker"], "BRK.B")
        self.assertIn("BRK-B", urls[0])
        self.assertEqual(entry["status"], "observed_unverified")

    def test_short_history_and_invalid_ohlc_stay_blocked(self):
        short = collector.build_document(
            AS_OF_DATE, ["MSFT"], http_get=mock_http_for(make_chart_raw(251)), now_fn=fixed_now
        )
        self.assertEqual(short["tickers"]["MSFT"]["blocked_reason"], "insufficient_completed_sessions")
        invalid = collector.build_document(
            AS_OF_DATE, ["MSFT"], http_get=mock_http_for(make_chart_raw(252, invalid_index=10)), now_fn=fixed_now
        )
        self.assertEqual(invalid["tickers"]["MSFT"]["status"], "blocked")

    def test_cutoff_session_is_excluded(self):
        document = collector.build_document(
            AS_OF_DATE, ["MSFT"], http_get=mock_http_for(make_chart_raw(252, include_cutoff=True)), now_fn=fixed_now
        )
        self.assertEqual(document["tickers"]["MSFT"]["sessions_observed"], 252)

    def test_malformed_and_http_failures_stay_blocked(self):
        malformed = collector.build_document(
            AS_OF_DATE, ["MSFT"], http_get=mock_http_for(b"not-json{{{"), now_fn=fixed_now
        )
        self.assertEqual(malformed["tickers"]["MSFT"]["blocked_reason"], "malformed_payload")
        failed = collector.build_document(AS_OF_DATE, ["MSFT"], http_get=raising_http, now_fn=fixed_now)
        self.assertTrue(failed["tickers"]["MSFT"]["blocked_reason"].startswith("http_error"))
        non_200 = collector.build_document(
            AS_OF_DATE, ["MSFT"], http_get=mock_http_for(make_chart_raw(252), status=503), now_fn=fixed_now
        )
        self.assertEqual(non_200["tickers"]["MSFT"]["blocked_reason"], "http_non_200_or_empty")
        missing = collector.build_document(
            AS_OF_DATE, ["MSFT"],
            http_get=mock_http_for(json.dumps({"chart": {"result": [], "error": None}}).encode("utf-8")),
            now_fn=fixed_now,
        )
        self.assertEqual(missing["tickers"]["MSFT"]["blocked_reason"], "missing_result")

    def test_unscoped_ticker_and_unsafe_output_are_rejected(self):
        with self.assertRaises(SystemExit):
            collector.parse_args(["--as-of-date", AS_OF_DATE, "--ticker", "AAPL"])
        for unsafe in ("../evil.json", "/tmp/evil.json", "outside/evil.json", "tmp", "tmp/", "tmp/../evil.json", "tmp/evil:ads", "tmp/CON.json", "tmp/aux.txt", "tmp/COM1.json", "tmp/LPT9.json", "tmp/evil.", "tmp/evil ", "C:\\evil.json"):
            with self.assertRaises(ValueError, msg=unsafe):
                collector.validate_output_path(unsafe)
        with self.assertRaises(ValueError):
            collector.build_document(AS_OF_DATE, ["AAPL"], http_get=mock_http_for(make_chart_raw(252)), now_fn=fixed_now)

    def test_no_file_write_without_flag_and_safe_write_with_flag(self):
        raw = make_chart_raw(252)
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                printed = io.StringIO()
                with redirect_stdout(printed):
                    exit_code = collector.main(
                        ["--as-of-date", AS_OF_DATE, "--ticker", "NVDA"],
                        http_get=mock_http_for(raw), now_fn=fixed_now,
                    )
                self.assertEqual(exit_code, 0)
                self.assertFalse(Path("tmp/yahoo_reference_evidence.json").exists())
                self.assertEqual(json.loads(printed.getvalue())["tickers"]["NVDA"]["status"], "observed_unverified")
                with redirect_stdout(io.StringIO()):
                    exit_code = collector.main(
                        ["--as-of-date", AS_OF_DATE, "--ticker", "NVDA", "--write"],
                        http_get=mock_http_for(raw), now_fn=fixed_now,
                    )
                self.assertEqual(exit_code, 0)
                self.assertTrue(Path("tmp/yahoo_reference_evidence.json").is_file())
                self.assertEqual(Path("tmp/yahoo_reference_evidence.json").read_text(encoding="utf-8"), printed.getvalue())
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
