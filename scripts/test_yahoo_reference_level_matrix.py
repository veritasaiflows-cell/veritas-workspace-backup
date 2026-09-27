"""Network-free tests for the Yahoo-only G6 review matrix."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[0] / "yahoo_reference_level_matrix.py"
matrix = SourceFileLoader("yahoo_reference_level_matrix", str(MODULE_PATH)).load_module()
REAL_RESOLVE = matrix.resolve_band_scope
AS_OF = "2026-09-10"
EXPECTED = "2026-09-09"
FIXED_NOW = datetime(2026, 9, 10, 1, 2, 3, tzinfo=timezone.utc)
TICKERS = tuple(sorted(("AMD", "AMZN", "BKNG", "BRK.B", "CAT", "CME", "CVX", "ECL",
                        "ETN", "GE", "GOOG", "GS", "ITA", "JPM", "KTOS", "LIN",
                        "LLY", "LMT", "LNG", "META", "MSFT", "NFLX", "NVDA", "PH",
                        "PLTR", "RTX", "SMCI", "TMUS", "VMC", "VRT", "WMB", "XOM")))


def fake_scope(tickers=TICKERS):
    names = tuple(sorted(tickers))
    return {"tickers": names, "symbols": {t: t.replace(".", "-") for t in names},
            "scope": {"tickers": list(names), "count": len(names), "fingerprint": "fixture-fingerprint",
                      "tier_breakdown": {"A": len(names)}, "resolved_at_utc": "2026-09-10T00:00:00Z"}}


def fixed_now():
    return FIXED_NOW


def chart_raw(count=260, final_date=EXPECTED, with_adjclose=True, invalid=None, timezone_name="America/New_York"):
    end = datetime.fromisoformat(final_date + "T20:00:00+00:00")
    timestamps = [int(end.timestamp()) - (count - 1 - index) * 86400 for index in range(count)]
    opens = [100.0 + index * 0.2 for index in range(count)]
    highs = [value + 1.5 for value in opens]
    lows = [value - 1.0 for value in opens]
    closes = [value + 0.5 for value in opens]
    volumes = [1000000 + index for index in range(count)]
    adjusted = [value * 0.98 for value in closes]
    if invalid == "null":
        closes[-2] = None
    if invalid == "ohlc":
        lows[-2] = highs[-2] + 1.0
    indicators = {"quote": [{"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}]}
    if with_adjclose:
        indicators["adjclose"] = [{"adjclose": adjusted}]
    payload = {"chart": {"result": [{"meta": {"exchangeTimezoneName": timezone_name}, "timestamp": timestamps, "indicators": indicators, "events": {"dividends": {}, "splits": {}}}], "error": None}}
    return json.dumps(payload).encode("utf-8")


def mock_http(raw, status=200):
    return lambda url, timeout=25: (status, raw)


def make_canon_db(root: str | Path):
    db = Path(root) / "state" / "finance" / "finance-canon.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE reference_levels (ticker TEXT PRIMARY KEY, reference_price_low REAL, reference_price_high REAL, reference_invalidation_level REAL, source_artifact_path TEXT, source_artifact_sha256 TEXT, source_generated_at_utc TEXT, raw_json TEXT)")
    for index, ticker in enumerate(TICKERS):
        connection.execute(
            "INSERT INTO reference_levels VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticker, 10.0 + index, 11.0 + index, 9.0 + index,
                f"old/{ticker}.json", f"old-{ticker}-hash", "2026-08-20T00:00:00Z",
                json.dumps({"level_as_of_utc": "2026-08-20T00:00:00Z"}),
            ),
        )
    connection.commit()
    connection.close()
    return db


class YahooReferenceLevelMatrixTests(unittest.TestCase):
    def setUp(self):
        self.resolver_patch = patch.object(matrix, "resolve_band_scope", return_value=fake_scope())
        self.resolver_patch.start()
        self.addCleanup(self.resolver_patch.stop)

    def test_scope_and_provider_mapping_are_exact(self):
        self.assertEqual(len(fake_scope()["tickers"]), 32)
        self.assertEqual(tuple(sorted(TICKERS)), TICKERS)
        self.assertEqual(matrix.provider_symbol("BRK.B"), "BRK-B")
        with self.assertRaises(ValueError):
            matrix.build_document(AS_OF, EXPECTED, ("AAPL",), http_get=mock_http(chart_raw()), now_fn=fixed_now)
        with self.assertRaises(ValueError):
            matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw()), now_fn=fixed_now)

    def test_default_scope_root_is_real_path(self):
        seen = []

        class Access:
            def __init__(self, db):
                self.db = db

            def dynamic_entitlement_scope(self, *, envelope_name, envelope_count):
                self.outer = (envelope_name, envelope_count)
                return SimpleNamespace(
                    memberships={"NVDA": SimpleNamespace(yfinance_symbol="NVDA")},
                    overflow_tickers=(), integrity_breaches=(),
                    payload=lambda: {"fingerprint": "fixture", "count": 1, "tier_breakdown": {"A": 1}})

        def policy_loader(root):
            seen.append(root)
            return SimpleNamespace(max_scope_count=1)

        resolved = REAL_RESOLVE("fixture.sqlite", access_factory=Access, policy_loader=policy_loader)
        self.assertEqual(resolved["tickers"], ("NVDA",))
        self.assertEqual(seen, [MODULE_PATH.resolve().parents[1]])
        self.assertIsInstance(seen[0], Path)
        self.assertIsNotNone(seen[0])

    def test_document_and_main_supply_explicit_scope_root(self):
        with tempfile.TemporaryDirectory() as folder:
            db = make_canon_db(folder)
            with patch.object(matrix, "resolve_band_scope", return_value=fake_scope()) as resolver:
                matrix.build_document(AS_OF, EXPECTED, ("NVDA",), db_path=db,
                                      http_get=mock_http(chart_raw()), now_fn=fixed_now, diagnostic=True)
                self.assertEqual(resolver.call_args.kwargs["workspace_root"], MODULE_PATH.resolve().parents[1])
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED,
                                                  "--ticker", "NVDA", "--db", str(db)],
                                                 http_get=mock_http(chart_raw()), now_fn=fixed_now), 0)
                self.assertEqual(resolver.call_args.kwargs["workspace_root"], MODULE_PATH.resolve().parents[1])

    def test_guarded_scope_resolution_and_refusals(self):
        def resolve(names=("BRK.B", "NVDA"), cap=3, overflow=(), breaches=(), blank=False, error=None):
            memberships = {t: SimpleNamespace(ticker=t, tier="A", decision_grade_eligible=True,
                                              yfinance_symbol=" " if blank else t.replace(".", "-")) for t in names}
            class Access:
                def __init__(self, db):
                    assert db == "fixture.sqlite"
                def dynamic_entitlement_scope(self, *, envelope_name, envelope_count):
                    assert (envelope_name, envelope_count) == ("band_renewal", cap)
                    if error:
                        raise error()
                    return SimpleNamespace(memberships=memberships, overflow_tickers=overflow,
                                           integrity_breaches=breaches,
                                           payload=lambda: {"fingerprint": "abc", "count": len(names),
                                                            "tier_breakdown": {"A": len(names)}})
            return REAL_RESOLVE("fixture.sqlite", access_factory=Access,
                                             policy_loader=lambda root: SimpleNamespace(max_scope_count=cap))
        happy = resolve()
        self.assertEqual(happy["tickers"], ("BRK.B", "NVDA"))
        self.assertEqual(happy["symbols"]["BRK.B"], "BRK-B")
        self.assertEqual(happy["scope"]["tickers"], ["BRK.B", "NVDA"])
        class DynamicEntitlementScopeError(Exception):
            pass
        for code, kw in (("band_scope_error", {"error": DynamicEntitlementScopeError}),
                         ("band_scope_empty", {"names": ()}),
                         ("band_scope_overflow", {"overflow": ("X",)}),
                         ("band_scope_over_cap", {"cap": 1}),
                         ("band_scope_integrity_breach", {"breaches": ("bad",)}),
                         ("band_scope_blank_yfinance_symbol", {"blank": True})):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                resolve(**kw)

    def test_contract_scope_sizes_and_outside_diagnostic(self):
        for names in (TICKERS[:-1], TICKERS, tuple(sorted((*TICKERS, "ZZZ")))):
            with self.subTest(count=len(names)), tempfile.TemporaryDirectory() as folder:
                db = make_canon_db(folder)
                if "ZZZ" in names:
                    con = sqlite3.connect(db)
                    con.execute("INSERT INTO reference_levels VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                ("ZZZ", 1, 2, 0.5, "old/ZZZ", "hash", "oldtime", '{"level_as_of_utc":"oldtime"}'))
                    con.commit()
                    con.close()
                scope = fake_scope(names)
                doc = matrix.build_document(AS_OF, EXPECTED, db_path=db, http_get=mock_http(chart_raw()),
                                            now_fn=fixed_now, resolved_scope=scope)
                self.assertTrue(doc["artifact_write_eligible"])
                self.assertEqual(len(doc["tickers"]), len(names))
                self.assertIn(f"Scope: {len(names)} names; fingerprint: fixture-fingerprint", matrix.markdown_for(doc))
                with self.assertRaisesRegex(ValueError, "exact full resolved scope"):
                    matrix.build_document(AS_OF, EXPECTED, names[:-1], db_path=db,
                                          resolved_scope=scope, http_get=mock_http(chart_raw()))
                previous = os.getcwd()
                os.chdir(folder)
                try:
                    code = matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED,
                                        "--ticker", "OUTSIDE", "--db", str(db)],
                                       scope_resolver=lambda path, *, workspace_root: scope, http_get=mock_http(chart_raw()))
                    self.assertNotEqual(code, 0)
                    self.assertFalse(Path("tmp").exists())
                finally:
                    os.chdir(previous)

    def test_resolver_refusal_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = os.getcwd()
            os.chdir(folder)
            try:
                def refuse(path, *, workspace_root):
                    raise ValueError("band_scope_integrity_breach")
                code = matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED, "--write"],
                                   scope_resolver=refuse, http_get=mock_http(chart_raw()))
                self.assertNotEqual(code, 0)
                self.assertFalse(Path("tmp").exists())
            finally:
                os.chdir(previous)

    def test_valid_row_has_252_bars_and_all_authority_flags_false(self):
        document = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw()), now_fn=fixed_now, diagnostic=True)
        row = document["tickers"]["NVDA"]
        self.assertEqual(row["classification"], "trend_qualified")
        self.assertEqual(len(row["normalized_bars"]), 252)
        self.assertFalse(row["canonical_write_allowed"])
        self.assertFalse(row["controller_clear_allowed"])
        self.assertFalse(row["account_or_execution_action_allowed"])
        self.assertFalse(row["delivery_action_allowed"])
        self.assertTrue(row["review_required"])
        self.assertEqual(row["raw_sha256"], hashlib.sha256(chart_raw()).hexdigest())

    def test_document_level_full_apply_gates_are_review_only(self):
        document = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw()), now_fn=fixed_now, diagnostic=True)
        self.assertFalse(document["apply_ready"])
        self.assertFalse(document["full_apply_ready"])
        self.assertFalse(document["canonical_write_allowed"])
        self.assertFalse(document["controller_clear_allowed"])
        self.assertFalse(document["delivery_action_allowed"])
        self.assertFalse(document["account_or_execution_action_allowed"])
        self.assertFalse(document["scheduler_change_allowed"])
        self.assertTrue(document["review_required"])
        self.assertTrue(document["review_only"])
        self.assertFalse(document["owner_numeric_approval_received"])
        self.assertTrue(document["requires_exact_owner_approval"])
        self.assertEqual(document["full_apply_blockers"], [])

    def test_absent_adjclose_and_wrong_final_date_block(self):
        no_adj = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw(with_adjclose=False)), now_fn=fixed_now, diagnostic=True)
        self.assertEqual(no_adj["tickers"]["NVDA"]["classification"], "blocked")
        wrong_date = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw(final_date="2026-09-08")), now_fn=fixed_now, diagnostic=True)
        self.assertEqual(wrong_date["tickers"]["NVDA"]["blocked_reason"], "date_mismatch")

    def test_invalid_bar_blocks(self):
        document = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw(invalid="ohlc")), now_fn=fixed_now, diagnostic=True)
        row = document["tickers"]["NVDA"]
        self.assertEqual(row["blocked_reason"], "invalid_ohlc_order")
        self.assertTrue(row["normalized_bars"])
        self.assertEqual(row["invalid_bar_evidence"]["session_date"], "2026-09-08")

    def test_blocked_document_lists_full_apply_blocker(self):
        document = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw(invalid="ohlc")), now_fn=fixed_now, diagnostic=True)
        self.assertEqual(document["full_apply_blockers"], [{"ticker": "NVDA", "blocked_reason": "invalid_ohlc_order"}])
        self.assertFalse(document["full_apply_ready"])

    def test_formula_matches_simple_known_series(self):
        bars = [{"open": 10 + index, "high": 12 + index, "low": 9 + index, "close": 11 + index, "volume": 1, "adjustment_factor": 1} for index in range(252)]
        metrics = matrix.calculate_metrics(bars)
        self.assertAlmostEqual(metrics["sma50"], sum(11 + index for index in range(202, 252)) / 50)
        self.assertAlmostEqual(metrics["support20"], 9 + 232)
        self.assertAlmostEqual(metrics["atr20"], 3.0)
        # D9 option A: invalidation anchors on the band low, so support20 >
        # SMA50 (this series) can no longer put invalidation inside the band.
        self.assertAlmostEqual(
            metrics["proposed_reference_invalidation_level"],
            min(metrics["support20"], metrics["sma50"]) - 4.5,
        )
        self.assertTrue(metrics["invalidation_below_range"])

    def test_safe_output_path_rejects_unsafe_values(self):
        for unsafe in ("../bad.json", "/tmp/bad.json", "tmp", "tmp/../bad.json", "tmp/x:ads", "C:\\bad.json"):
            with self.assertRaises(ValueError, msg=unsafe):
                matrix.validate_output_path(unsafe)

    def test_no_file_write_without_write_flag(self):
        raw = chart_raw()
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                output = io.StringIO()
                with redirect_stdout(output):
                    code = matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED, "--ticker", "NVDA"], http_get=mock_http(raw), now_fn=fixed_now)
                self.assertEqual(code, 0)
                self.assertFalse(Path("tmp/yahoo_reference_level_matrix.json").exists())
                self.assertEqual(json.loads(output.getvalue())["tickers"]["NVDA"]["classification"], "trend_qualified")
            finally:
                os.chdir(previous)

    def test_single_ticker_diagnostic_write_is_rejected(self):
        with self.assertRaises(SystemExit):
            matrix.parse_args(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED, "--ticker", "NVDA", "--write"])

    def test_write_creates_only_full_scope_tmp_artifacts(self):
        raw = chart_raw()
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                make_canon_db(folder)
                code = matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED, "--write"], http_get=mock_http(raw), now_fn=fixed_now)
                self.assertEqual(code, 0)
                self.assertTrue(Path("tmp/yahoo_reference_level_matrix.json").is_file())
                self.assertTrue(Path("tmp/yahoo_reference_level_matrix.md").is_file())
                written = json.loads(Path("tmp/yahoo_reference_level_matrix.json").read_text(encoding="utf-8"))
                self.assertTrue(written["artifact_write_eligible"])
                self.assertEqual(tuple(written["tickers"]), TICKERS)
                self.assertEqual(written["scope"]["tickers"], list(TICKERS))
                self.assertEqual(written["scope"]["fingerprint"], "fixture-fingerprint")
                markdown = Path("tmp/yahoo_reference_level_matrix.md").read_text(encoding="utf-8")
                self.assertIn("## Yahoo source lineage", markdown)
                self.assertIn("## Current canonical lineage", markdown)
            finally:
                os.chdir(previous)

    def test_markdown_decision_authority_flags_session_and_identities(self):
        raw = chart_raw()
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                make_canon_db(folder)
                code = matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED, "--write"], http_get=mock_http(raw), now_fn=fixed_now)
                self.assertEqual(code, 0)
                markdown = Path("tmp/yahoo_reference_level_matrix.md").read_text(encoding="utf-8")
                self.assertIn("## Decision", markdown)
                self.assertIn("NO APPLY NOW", markdown)
                self.assertIn("not an apply set", markdown)
                self.assertIn("no owner has approved", markdown)
                for flag in (
                    "canonical_write_allowed=false",
                    "controller_clear_allowed=false",
                    "apply_ready=false",
                    "review_required=true",
                    "scheduler_change_allowed=false",
                    "delivery_action_allowed=false",
                    "account_or_execution_action_allowed=false",
                ):
                    self.assertIn(flag, markdown)
                self.assertIn("Valid final session", markdown)
                self.assertIn("review_required", markdown)
                self.assertIn("BRK.B", markdown)
                self.assertIn("BRK-B", markdown)
                written = json.loads(Path("tmp/yahoo_reference_level_matrix.json").read_text(encoding="utf-8"))
                self.assertFalse(written["full_apply_ready"])
                self.assertFalse(written["owner_numeric_approval_received"])
                self.assertTrue(written["requires_exact_owner_approval"])
            finally:
                os.chdir(previous)

    def test_markdown_decision_dynamic_blocked_lists_all_blockers(self):
        raw_blocked = chart_raw(invalid="ohlc")
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                make_canon_db(folder)
                code = matrix.main(["--as-of-date", AS_OF, "--expected-session-date", EXPECTED, "--write"], http_get=mock_http(raw_blocked), now_fn=fixed_now)
                self.assertEqual(code, 0)
                written = json.loads(Path("tmp/yahoo_reference_level_matrix.json").read_text(encoding="utf-8"))
                markdown = Path("tmp/yahoo_reference_level_matrix.md").read_text(encoding="utf-8")
                self.assertGreater(written["row_counts"]["blocked"], 0)
                self.assertTrue(written["full_apply_blockers"])
                for entry in written["full_apply_blockers"]:
                    self.assertIn(f"{entry['ticker']}={entry['blocked_reason']}", markdown)
                self.assertIn("blocks any full 32-row apply", markdown)
                self.assertIn("not an apply set", markdown)
                self.assertIn("incomplete", markdown)
                self.assertIn("NO APPLY NOW", markdown)
            finally:
                os.chdir(previous)

    def test_markdown_decision_dynamic_no_blocker_withholds_ita_and_incomplete(self):
        document = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw()), now_fn=fixed_now, diagnostic=True)
        document["artifact_write_eligible"] = True
        document["tickers"] = {ticker: dict(document["tickers"]["NVDA"], ticker=ticker, yahoo_symbol=matrix.provider_symbol(ticker)) for ticker in TICKERS}
        document["row_counts"] = {"trend_qualified": 32, "monitor_only": 0, "blocked": 0}
        document["full_apply_blockers"] = []
        markdown = matrix.markdown_for(document)
        self.assertIn("NO APPLY NOW", markdown)
        self.assertIn("exact owner approval absent", markdown)
        self.assertIn("not an apply set", markdown)
        decision_section = markdown.split("## Decision")[1].split("## Authority flags")[0]
        self.assertNotIn("ITA", decision_section)
        self.assertNotIn("invalid_ohlc_order", decision_section)
        self.assertNotIn("incomplete", decision_section)
        self.assertFalse(document["full_apply_ready"])
        self.assertFalse(document["apply_ready"])

    def test_same_json_and_markdown_output_path_is_rejected(self):
        raw = chart_raw()
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                make_canon_db(folder)
                code = matrix.main([
                    "--as-of-date", AS_OF,
                    "--expected-session-date", EXPECTED,
                    "--json-output", "tmp/same.out",
                    "--markdown-output", "tmp/same.out",
                    "--write",
                ], http_get=mock_http(raw), now_fn=fixed_now)
                self.assertEqual(code, 2)
                self.assertFalse(Path("tmp/same.out").exists())
            finally:
                os.chdir(previous)

    def test_old_side_requires_finite_prices_and_nonempty_lineage(self):
        complete = {
            "lookup_status": "found",
            "old": {
                "reference_price_low": 1.0,
                "reference_price_high": 2.0,
                "reference_invalidation_level": 0.5,
                "level_as_of": "2026-01-01T00:00:00Z",
                "source_artifact_path": "old.json",
                "source_artifact_sha256": "hash",
                "source_generated_at_utc": "2026-01-01T00:00:00Z",
            },
        }
        self.assertTrue(matrix.has_complete_old_record(complete))
        complete["old"]["reference_price_high"] = float("nan")
        self.assertFalse(matrix.has_complete_old_record(complete))

    def test_raw_utc_cutoff_precedes_timezone_derivation(self):
        payload = json.loads(chart_raw())
        first = payload["chart"]["result"][0]
        cutoff_side_timestamp = int(datetime(2026, 9, 10, 1, 0, tzinfo=timezone.utc).timestamp())
        first["timestamp"].append(cutoff_side_timestamp)
        quote = first["indicators"]["quote"][0]
        for field, value in (("open", 200.0), ("high", 201.0), ("low", 199.0), ("close", 200.5), ("volume", 1000000)):
            quote[field].append(value)
        first["indicators"]["adjclose"][0]["adjclose"].append(200.5)
        bars, metadata = matrix.extract_normalized_bars(payload, date(2026, 9, 10))
        self.assertIsNotNone(bars)
        self.assertEqual(len(bars), 260)
        self.assertEqual(bars[-1]["session_date"], EXPECTED)
        self.assertEqual(metadata["exchange_timezone_source"], "yahoo_metadata")

    def test_markdown_refuses_incomplete_contract_document(self):
        document = matrix.build_document(AS_OF, EXPECTED, ("NVDA",), http_get=mock_http(chart_raw()), now_fn=fixed_now, diagnostic=True)
        with self.assertRaises(ValueError):
            matrix.markdown_for(document)

    def test_read_old_levels_is_read_only_and_captures_lineage(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "canon.sqlite"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE reference_levels (ticker TEXT PRIMARY KEY, reference_price_low REAL, reference_price_high REAL, reference_invalidation_level REAL, source_artifact_path TEXT, source_artifact_sha256 TEXT, source_generated_at_utc TEXT, raw_json TEXT)")
            connection.execute("INSERT INTO reference_levels VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("NVDA", 1, 2, 0.5, "old.md", "oldhash", "oldtime", json.dumps({"level_as_of_utc": "2026-01-01T00:00:00Z"})))
            connection.commit()
            connection.close()
            rows, status = matrix.read_old_levels(db, ("NVDA",))
            self.assertEqual(status, "ok")
            self.assertEqual(rows["NVDA"]["old"]["level_as_of"], "2026-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
