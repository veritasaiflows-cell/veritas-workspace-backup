#!/usr/bin/env python3
"""Offline unit tests for the review-only reference-evidence validator."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "alert_reference_evidence_packet.py"
SCOPE = [
    "AMD", "AMZN", "BRK.B", "CAT", "CVX", "ETN", "GOOG", "GS",
    "JPM", "LLY", "LMT", "LNG", "MSFT", "NVDA", "PLTR", "RTX",
    "VRT", "XOM",
]

AS_OF = "2026-09-08"
HEX64 = "a" * 64

IDENTITY_OK = {
    "AMD": ("AMD Inc", "Advanced Micro Devices common stock evidence"),
    "AMZN": ("AMZN Inc", "Amazon.com common stock evidence"),
    "BRK.B": ("BRK-B Inc", "Berkshire Hathaway Class B common stock evidence"),
    "CAT": ("CAT Inc", "Caterpillar common stock evidence"),
    "CVX": ("CVX Inc", "Chevron common stock evidence"),
    "ETN": ("ETN Inc", "Eaton common stock evidence"),
    "GOOG": ("GOOG Inc", "Alphabet Class C common stock evidence"),
    "GS": ("GS Inc", "Goldman Sachs common stock evidence"),
    "JPM": ("JPM Inc", "JPMorgan Chase common stock evidence"),
    "LLY": ("LLY Inc", "Eli Lilly common stock evidence"),
    "LMT": ("LMT Inc", "Lockheed Martin common stock evidence"),
    "LNG": ("LNG Inc", "Cheniere Energy common stock evidence"),
    "MSFT": ("MSFT Inc", "Microsoft common stock evidence"),
    "NVDA": ("NVDA Inc", "NVIDIA common stock evidence"),
    "PLTR": ("PLTR Inc", "Palantir common stock evidence"),
    "RTX": ("RTX Inc", "RTX common stock evidence"),
    "VRT": ("VRT Inc", "Vertiv Holdings common stock evidence"),
    "XOM": ("XOM Inc", "Exxon Mobil common stock evidence"),
}

PROVIDER_OK = {
    "BRK.B": "BRK-B",
}


def provider_for(ticker: str) -> str:
    return PROVIDER_OK.get(ticker, ticker)


def make_calendar(n: int = 252, end: str = "2026-09-04") -> list:
    end_day = date.fromisoformat(end)
    days = []
    cursor = end_day
    while len(days) < n:
        if cursor.weekday() < 5:
            days.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    days.reverse()
    return days


def make_sessions(calendar, base: float = 100.0):
    rows = []
    price = base
    for i, day in enumerate(calendar):
        open_p = round(price, 2)
        close_p = round(price * 1.001 + 0.01, 2)
        high_p = round(max(open_p, close_p) + 0.05, 2)
        low_p = round(min(open_p, close_p) - 0.05, 2)
        rows.append({
            "date": day,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "adjusted_close": close_p,
            "volume": 1000000 + i,
            "split_coefficient": 1,
            "completed": True,
        })
        price = close_p
    return rows


def make_ticker(ticker: str, calendar, policy: str = "split_only") -> dict:
    issuer, evidence = IDENTITY_OK[ticker]
    return {
        "ticker": ticker,
        "provider_symbol": provider_for(ticker),
        "issuer_name": issuer,
        "exchange": "XNYS" if ticker != "ETN" else "XNYS",
        "identity_evidence": evidence,
        "price_source": {
            "publisher": "Example Publisher",
            "url": "https://example.com/prices/%s" % ticker.replace(".", "-"),
            "retrieved_at_utc": "2026-09-08T20:00:00+00:00",
            "payload_sha256": HEX64,
            "adjustment_disclosure_url": "https://example.com/disclosures/adjustments",
            "adjustment_policy": policy,
        },
        "sessions": make_sessions(calendar, base=100.0 + SCOPE.index(ticker)),
        "corporate_actions": [],
        "gap_reviews": [],
        "earnings_evidence": {
            "status": "unannounced",
            "source_url": "https://example.com/earnings/%s" % ticker.replace(".", "-"),
            "publisher": "Example Publisher",
            "retrieved_at_utc": "2026-09-08T20:00:00+00:00",
            "event_date": None,
            "timing": "unknown",
            "sec_url": "https://example.com/sec/%s" % ticker.replace(".", "-"),
        },
    }


def make_input(calendar=None, policy: str = "split_only") -> dict:
    calendar = calendar if calendar is not None else make_calendar()
    return {
        "schema": "veritas.alert_reference_evidence_input.v2",
        "status": "ok",
        "adjustment_policy": policy,
        "as_of_date": AS_OF,
        "expected_completed_session_dates": list(calendar),
        "tickers": [make_ticker(t, calendar, policy=policy) for t in SCOPE],
    }


def run_cli(args, cwd: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class ValidatorTests(unittest.TestCase):
    def test_valid_fixture_ok_and_sma_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_input()
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            out = "tmp/package.json"
            proc = run_cli(
                ["--input", str(src), "--output", out, "--as-of-date", AS_OF,
                 "--write", "--validate", "--json"],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            printed = json.loads(proc.stdout)
            self.assertEqual(printed["schema"], "veritas.alert_reference_evidence_package.v2")
            self.assertEqual(printed["status"], "ok")
            self.assertTrue(printed["independent_source_reconciliation_required"])
            self.assertIn("Independent source reconciliation", printed["adjustment_policy_note"])
            self.assertTrue(all(ord(c) < 128 for c in proc.stdout))
            self.assertTrue(printed["review_only"])
            self.assertFalse(printed["canonical_write_allowed"])
            self.assertFalse(printed["scheduler_change_allowed"])
            self.assertFalse(printed["account_or_execution_action_allowed"])
            self.assertEqual([t["ticker"] for t in printed["tickers"]], SCOPE)
            for row in printed["tickers"]:
                self.assertEqual(row["status"], "review_only_eligible")
                self.assertEqual(row["errors"], [])
                self.assertIsNotNone(row["sma_50"])
                self.assertIsNotNone(row["sma_200"])
                self.assertTrue(isinstance(row["evidence_sha256"], str) and len(row["evidence_sha256"]) == 64)
                self.assertEqual(row["session_count"], 252)
            written = json.loads((Path(tmp) / out).read_text(encoding="utf-8"))
            self.assertEqual(written, printed)

    def test_rejects_251_row_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            calendar = make_calendar(n=251)
            payload = make_input(calendar=calendar)
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json",
                 "--as-of-date", AS_OF, "--validate", "--json"],
                cwd=tmp,
            )
            # Either malformed (exit 2) or blocked (exit 1) is a rejection; never ok.
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            if proc.stdout.strip():
                printed = json.loads(proc.stdout)
                self.assertNotEqual(printed.get("status"), "ok")

    def test_rejects_asof_session_and_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Session on the as-of date.
            payload = make_input()
            payload["tickers"][0]["sessions"][-1]["date"] = AS_OF
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json",
                 "--as-of-date", AS_OF, "--validate"],
                cwd=tmp,
            )
            self.assertNotEqual(proc.returncode, 0)
            printed = json.loads(proc.stdout)
            self.assertEqual(printed["status"], "blocked")
            amd = [t for t in printed["tickers"] if t["ticker"] == "AMD"][0]
            self.assertEqual(amd["status"], "insufficient_evidence")

            # completed=false.
            payload2 = make_input()
            payload2["tickers"][1]["sessions"][10]["completed"] = False
            src2 = Path(tmp) / "in2.json"
            src2.write_text(json.dumps(payload2), encoding="utf-8")
            proc2 = run_cli(
                ["--input", str(src2), "--output", "tmp/package2.json",
                 "--as-of-date", AS_OF, "--validate"],
                cwd=tmp,
            )
            self.assertNotEqual(proc2.returncode, 0)
            printed2 = json.loads(proc2.stdout)
            self.assertEqual(printed2["status"], "blocked")

    def test_rejects_identity_mismatches(self):
        variants = {
            "BRK.B": {"provider_symbol": "BRK.B"},
            "GOOG": {"identity_evidence": "Alphabet Class A common stock evidence"},
            "VRT": {"identity_evidence": "Some other company common stock evidence"},
            "LNG": {"identity_evidence": "Some generic gas company evidence"},
        }
        for ticker, patch in variants.items():
            with self.subTest(ticker=ticker):
                with tempfile.TemporaryDirectory() as tmp:
                    payload = make_input()
                    idx = SCOPE.index(ticker)
                    payload["tickers"][idx].update(copy.deepcopy(patch))
                    src = Path(tmp) / "in.json"
                    src.write_text(json.dumps(payload), encoding="utf-8")
                    proc = run_cli(
                        ["--input", str(src), "--output", "tmp/package.json",
                         "--as-of-date", AS_OF, "--validate"],
                        cwd=tmp,
                    )
                    self.assertNotEqual(proc.returncode, 0, msg=ticker + proc.stderr)
                    printed = json.loads(proc.stdout)
                    self.assertEqual(printed["status"], "blocked")
                    row = [t for t in printed["tickers"] if t["ticker"] == ticker][0]
                    self.assertEqual(row["status"], "insufficient_evidence")
                    self.assertTrue(row["errors"])

    def test_rejects_gap_and_split_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Unexplained >=10% gap: force open far above prior close.
            payload = make_input()
            sessions = payload["tickers"][0]["sessions"]
            prev_close = sessions[50]["close"]
            sessions[51]["open"] = round(prev_close * 1.25, 2)
            sessions[51]["high"] = round(sessions[51]["open"] + 1.0, 2)
            sessions[51]["low"] = round(min(sessions[51]["open"], sessions[51]["close"]) - 0.05, 2)
            if sessions[51]["high"] < max(sessions[51]["open"], sessions[51]["close"]):
                sessions[51]["high"] = round(max(sessions[51]["open"], sessions[51]["close"]) + 0.05, 2)
            src = Path(tmp) / "gap.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json",
                 "--as-of-date", AS_OF, "--validate"],
                cwd=tmp,
            )
            self.assertNotEqual(proc.returncode, 0)
            printed = json.loads(proc.stdout)
            amd = [t for t in printed["tickers"] if t["ticker"] == "AMD"][0]
            self.assertEqual(amd["status"], "insufficient_evidence")

            # Uncovered split coefficient.
            payload2 = make_input()
            payload2["tickers"][2]["sessions"][100]["split_coefficient"] = 2
            src2 = Path(tmp) / "split.json"
            src2.write_text(json.dumps(payload2), encoding="utf-8")
            proc2 = run_cli(
                ["--input", str(src2), "--output", "tmp/package2.json",
                 "--as-of-date", AS_OF, "--validate"],
                cwd=tmp,
            )
            self.assertNotEqual(proc2.returncode, 0)
            printed2 = json.loads(proc2.stdout)
            cat = [t for t in printed2["tickers"] if t["ticker"] == "BRK.B"][0]
            self.assertEqual(cat["status"], "insufficient_evidence")

    def test_validate_nonzero_and_no_write_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_input()
            payload["tickers"][3]["sessions"][5]["completed"] = False
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            out_rel = "tmp/package.json"
            proc = run_cli(
                ["--input", str(src), "--output", out_rel,
                 "--as-of-date", AS_OF, "--validate"],
                cwd=tmp,
            )
            self.assertNotEqual(proc.returncode, 0)
            printed = json.loads(proc.stdout)
            self.assertEqual(printed["status"], "blocked")
            self.assertFalse((Path(tmp) / out_rel).exists())

    def test_rejects_hash_and_date_with_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_input()
            payload["tickers"][0]["price_source"]["payload_sha256"] = HEX64 + "\n"
            src = Path(tmp) / "bad-hash.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 1)
            amd = json.loads(proc.stdout)["tickers"][0]
            self.assertEqual(amd["status"], "insufficient_evidence")
            self.assertTrue(any("payload_sha256" in item for item in amd["errors"]))

            payload = make_input()
            payload["expected_completed_session_dates"][-1] += "\n"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 2)

    def test_requires_price_source_adjustment_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mutation in ("missing", "mismatch"):
                with self.subTest(mutation=mutation):
                    payload = make_input()
                    source = payload["tickers"][0]["price_source"]
                    if mutation == "missing":
                        del source["adjustment_policy"]
                    else:
                        source["adjustment_policy"] = "split_and_dividend_adjusted_close"
                    src = Path(tmp) / (mutation + ".json")
                    src.write_text(json.dumps(payload), encoding="utf-8")
                    proc = run_cli(
                        ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                        cwd=tmp,
                    )
                    self.assertEqual(proc.returncode, 1)
                    amd = json.loads(proc.stdout)["tickers"][0]
                    self.assertEqual(amd["status"], "insufficient_evidence")

    def test_blocked_exits_nonzero_without_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_input()
            payload["tickers"][0]["sessions"][5]["completed"] = False
            src = Path(tmp) / "blocked.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["status"], "blocked")

    def test_accepts_utf8_bom_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bom.json"
            src.write_text(json.dumps(make_input()), encoding="utf-8-sig")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["status"], "ok")

    def test_rejects_bare_tmp_output_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "valid.json"
            src.write_text(json.dumps(make_input()), encoding="utf-8")
            for output in ("tmp", "tmp/", "../tmp/package.json", "C:\\tmp\\package.json", "tmp/a:b.json"):
                with self.subTest(output=output):
                    proc = run_cli(
                        ["--input", str(src), "--output", output, "--as-of-date", AS_OF],
                        cwd=tmp,
                    )
                    self.assertEqual(proc.returncode, 2)

    def test_rejects_opposite_sign_gap_percent(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_input()
            sessions = payload["tickers"][0]["sessions"]
            prior = sessions[50]["close"]
            sessions[51]["open"] = round(prior * 1.25, 2)
            sessions[51]["high"] = round(sessions[51]["open"] + 1.0, 2)
            sessions[51]["low"] = round(min(sessions[51]["open"], sessions[51]["close"]) - 0.05, 2)
            day = sessions[51]["date"]
            payload["tickers"][0]["gap_reviews"] = [{
                "date": day,
                "source_url": "https://example.com/gaps/amd",
                "source_hash": HEX64,
                "gap_percent": -25.0,
                "disposition": "reviewed",
            }]
            src = Path(tmp) / "signed-gap.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 1)
            amd = json.loads(proc.stdout)["tickers"][0]
            self.assertTrue(any("gap_percent" in item for item in amd["errors"]))

    def test_rejects_v1_contract_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_input()
            payload["schema"] = "veritas.alert_reference_evidence_input.v1"
            src = Path(tmp) / "old-schema.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", AS_OF],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("input schema", proc.stderr)

    def test_accepts_future_parameterized_completed_session_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            future_as_of = "2026-09-09"
            payload = make_input()
            payload["as_of_date"] = future_as_of
            src = Path(tmp) / "future-cutoff.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            proc = run_cli(
                ["--input", str(src), "--output", "tmp/package.json", "--as-of-date", future_as_of],
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
