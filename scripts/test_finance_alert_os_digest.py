from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import finance_alert_os_digest as digest
from finance_alert_os_digest import build_message, controller_semantic_errors


class FinanceAlertOsDigestTests(unittest.TestCase):
    def test_message_is_alert_and_recommendation_only(self) -> None:
        levels = {
            "generated_at_utc": "2026-08-30T00:00:00Z",
            "summary": {
                "alert_state_counts": {"monitor_only": 1},
                "band_entry_signal_tickers": [],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": ["ETN"],
                "freshness_review_tickers": [],
                "quote_session_dates": ["2026-08-28"],
                "quote_as_of_utc_values": ["2026-08-28T19:59:44Z"],
            },
        }
        message = build_message("morning", levels)
        self.assertIn("Band-entry alerts: none", message)
        self.assertIn("Monitor-only: ETN", message)
        self.assertIn("Quote session date: 2026-08-28", message)
        self.assertIn("Quote evidence as of: 2026-08-28T19:59:44Z", message)
        self.assertIn("alert firing is suppressed", message)
        self.assertIn("no capital", message.lower())

    def test_alerts_without_intraday_eligibility_fail_closed(self) -> None:
        levels = {
            "summary": {
                "band_entry_signal_tickers": ["ETN"],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "fresh_intraday_signal_eligible_tickers": [],
            }
        }
        self.assertIn(
            "controller emits alerts without fresh-intraday eligibility proof",
            controller_semantic_errors(levels),
        )

    def test_intraday_eligible_alerts_are_allowed(self) -> None:
        levels = {
            "summary": {
                "band_entry_signal_tickers": ["ETN"],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "fresh_intraday_signal_eligible_tickers": ["ETN"],
            }
        }
        self.assertEqual(controller_semantic_errors(levels), [])


class ControllerStalenessTests(unittest.TestCase):
    def _levels(self, age_hours: float) -> dict:
        stamp = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        return {
            "generated_at_utc": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "alert_state_counts": {"monitor_only": 1},
                "band_entry_signal_tickers": [],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": ["ETN"],
                "freshness_review_tickers": [],
                "quote_session_dates": ["2026-09-04"],
                "quote_as_of_utc_values": ["2026-09-04T19:59:44Z"],
            },
        }

    def _payload(self, levels: dict, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert-level-freshness-controller.json"
            path.write_text(json.dumps(levels), encoding="utf-8")
            with mock.patch.object(digest, "LEVELS", path), mock.patch.object(digest, "THESIS_DIR", Path(tmp)):
                return digest.build_payload("morning", **kwargs)

    def test_fresh_controller_is_delivered(self) -> None:
        payload = self._payload(self._levels(0.5))

        self.assertEqual(payload["status"], "ok")
        self.assertIsNotNone(payload["message_preview"])

    def test_stale_controller_blocks_delivery(self) -> None:
        payload = self._payload(self._levels(20))

        self.assertEqual(payload["status"], "blocked")
        self.assertIsNone(payload["message_preview"])
        self.assertTrue(
            any("is stale" in error for error in payload["validation"]["errors"]),
            payload["validation"]["errors"],
        )

    def test_age_limit_is_configurable(self) -> None:
        payload = self._payload(self._levels(20), max_controller_age_hours=24.0)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source_artifacts"]["alert_levels"]["max_age_hours"], 24.0)

    def test_missing_stamp_fails_closed(self) -> None:
        levels = self._levels(0.5)
        levels.pop("generated_at_utc")
        payload = self._payload(levels)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn(
            "alert-level freshness proof has no usable generated_at_utc stamp",
            payload["validation"]["errors"],
        )

    def test_future_stamp_fails_closed(self) -> None:
        payload = self._payload(self._levels(-5))

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(
            any("in the future" in error for error in payload["validation"]["errors"]),
            payload["validation"]["errors"],
        )

    def test_small_negative_skew_is_tolerated(self) -> None:
        self.assertEqual(self._payload(self._levels(-0.05))["status"], "ok")

    def test_unparseable_stamp_fails_closed(self) -> None:
        levels = self._levels(0.5)
        levels["generated_at_utc"] = "not-a-timestamp"

        self.assertEqual(self._payload(levels)["status"], "blocked")


class TransportMultilineTests(unittest.TestCase):
    PAYLOAD = (
        "FINANCE ALERTS & RECOMMENDATIONS - MORNING\n"
        'Band-entry alerts: ETN "quoted" \'tick\'\n'
        "UTF-8: caf\u00e9 \u20ac\u00a5 \U0001f4c8 $HOME `back` & | ; < >\n"
        "Line3: a=b && c\n"
        "Line4: end"
    )

    def _levels(self) -> dict:
        return {
            "generated_at_utc": "2026-09-08T00:00:00Z",
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "alert_state_counts": {"monitor_only": 1},
                "band_entry_signal_tickers": [],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": ["ETN"],
                "freshness_review_tickers": [],
                "quote_session_dates": ["2026-09-04"],
                "quote_as_of_utc_values": ["2026-09-04T19:59:44Z"],
            },
        }

    def test_all_three_modes_forward_exact_multiline(self) -> None:
        import subprocess as sp
        for mode in ("recommendations", "morning", "midday"):
            msg = digest.build_message(mode, self._levels())
            self.assertGreaterEqual(msg.count("\n"), 3)
            captured: dict = {}
            def fake_run(argv, **kwargs):
                captured["argv"] = list(argv)
                self.assertIn("--message", argv)
                self.assertEqual(argv[argv.index("--message") + 1], msg)
                return mock.Mock(returncode=0, stderr="")
            with mock.patch.object(digest, "_is_windows", return_value=False):
                with mock.patch.object(digest, "resolve_openclaw", return_value="/usr/bin/openclaw"):
                    with mock.patch.object(sp, "run", side_effect=fake_run):
                        result = digest.deliver("t", msg, 5)
            self.assertTrue(result["ok"])
            self.assertNotIn(".cmd", " ".join(captured["argv"][:2]))
            self.assertEqual(result["transport"]["message_sha256"],
                             __import__("hashlib").sha256(msg.encode("utf-8")).hexdigest())

    def test_exact_metachar_message_preserved_posix(self) -> None:
        import subprocess as sp
        msg = self.PAYLOAD
        seen: dict = {}
        def fake_run(argv, **kwargs):
            seen["forwarded"] = argv[argv.index("--message") + 1]
            return mock.Mock(returncode=0, stderr="")
        with mock.patch.object(digest, "_is_windows", return_value=False):
            with mock.patch.object(digest, "resolve_openclaw", return_value="openclaw"):
                with mock.patch.object(sp, "run", side_effect=fake_run):
                    result = digest.deliver("t", msg, 5)
        self.assertTrue(result["ok"])
        self.assertEqual(seen["forwarded"], msg)
        self.assertEqual(result["transport"]["message_bytes"], len(msg.encode("utf-8")))
        self.assertEqual(result["transport"]["message_lines"], msg.count("\n") + 1)


class WindowsLaunchTests(unittest.TestCase):
    NPM_DIR = "C:/Users/x/AppData/Roaming/npm"

    def _which(self, mapping: dict) -> object:
        def fake(name: str):
            return mapping.get(name)
        return fake

    def _exact_is_file(self, expected_dir: str):
        """Make only the expected Node entry point exist in tests."""
        def side_effect(*args, **kwargs) -> bool:
            candidate = args[0] if args else None
            text = str(candidate).replace("\\", "/")
            return (
                text.endswith("/node_modules/openclaw/openclaw.mjs")
                and expected_dir.replace("\\", "/") in text
            )
        return side_effect

    def test_windows_npm_shim_resolves_node_direct(self) -> None:
        import subprocess as sp
        msg = "a\nb\nc"
        mapping = {
            "node": "C:/Program Files/nodejs/node.exe",
            "openclaw": self.NPM_DIR + "/openclaw.cmd",
            "openclaw.cmd": self.NPM_DIR + "/openclaw.cmd",
        }
        with mock.patch.object(digest, "_is_windows", return_value=True):
            with mock.patch.object(digest.shutil, "which", side_effect=self._which(mapping)):
                with mock.patch.object(Path, "is_file", autospec=True, side_effect=self._exact_is_file(self.NPM_DIR)):
                    with mock.patch.object(sp, "run", return_value=mock.Mock(returncode=0, stderr="")) as run:
                        result = digest.deliver("t", msg, 5)
        self.assertTrue(result["ok"])
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "C:/Program Files/nodejs/node.exe")
        self.assertTrue(argv[1].endswith("openclaw.mjs"))
        self.assertNotIn(".cmd", argv[0] + "|" + argv[1])
        self.assertIn(msg, argv)
        self.assertEqual(result["strategy"], "windows-node-direct")
        self.assertIn("shell", run.call_args[1])
        self.assertFalse(run.call_args[1]["shell"])

    def test_windows_agent_shim_resolves(self) -> None:
        import subprocess as sp
        mapping = {
            "node": "C:/Program Files/nodejs/node.exe",
            "openclaw": None,
            "openclaw.cmd": None,
            "agent-cli": self.NPM_DIR + "/agent-cli.cmd",
            "agent-cli.cmd": self.NPM_DIR + "/agent-cli.cmd",
        }
        with mock.patch.object(digest, "_is_windows", return_value=True):
            with mock.patch.object(digest.shutil, "which", side_effect=self._which(mapping)):
                with mock.patch.object(Path, "is_file", autospec=True, side_effect=self._exact_is_file(self.NPM_DIR)):
                    with mock.patch.object(sp, "run", return_value=mock.Mock(returncode=0, stderr="")) as run:
                        result = digest.deliver("t", "hello\nworld", 5)
        self.assertTrue(result["ok"])
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "C:/Program Files/nodejs/node.exe")
        self.assertTrue(argv[1].endswith("openclaw.mjs"))

    def test_windows_all_modes_exact_utf8_metachar(self) -> None:
        import subprocess as sp
        mapping = {
            "node": "C:/Program Files/nodejs/node.exe",
            "openclaw": self.NPM_DIR + "/openclaw.cmd",
            "openclaw.cmd": self.NPM_DIR + "/openclaw.cmd",
        }
        payload = "UTF-8: café €¥📈 $HOME `back` & | ; < >\nLine4: a=b && c"
        for mode in ("recommendations", "morning", "midday"):
            message = "FINANCE ALERTS & RECOMMENDATIONS\nBand-entry: ETN\n" + payload
            with mock.patch.object(digest, "_is_windows", return_value=True):
                with mock.patch.object(digest.shutil, "which", side_effect=self._which(mapping)):
                    with mock.patch.object(Path, "is_file", autospec=True, side_effect=self._exact_is_file(self.NPM_DIR)):
                        with mock.patch.object(sp, "run", return_value=mock.Mock(returncode=0, stderr="")) as run:
                            result = digest.deliver("t", message, 5)
            self.assertTrue(result["ok"], mode)
            argv = run.call_args[0][0]
            self.assertEqual(argv[argv.index("--message") + 1], message)
            self.assertEqual(result["transport"]["message_sha256"], __import__("hashlib").sha256(message.encode("utf-8")).hexdigest())
            self.assertNotIn(".cmd", argv[0] + "|" + argv[1])

    def test_windows_missing_node_fails_closed(self) -> None:
        import subprocess as sp
        with mock.patch.object(digest, "_is_windows", return_value=True):
            with mock.patch.object(digest.shutil, "which", return_value=None):
                with mock.patch.object(sp, "run") as run:
                    result = digest.deliver("t", "x\ny", 5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "safe-launch-unresolved")
        run.assert_not_called()

    def test_windows_missing_entrypoint_fails_closed(self) -> None:
        import subprocess as sp
        mapping = {"node": "C:/Program Files/nodejs/node.exe"}
        with mock.patch.object(digest, "_is_windows", return_value=True):
            with mock.patch.object(digest.shutil, "which", side_effect=self._which(mapping)):
                with mock.patch.object(Path, "is_file", autospec=True, return_value=False):
                    with mock.patch.object(sp, "run") as run:
                        result = digest.deliver("t", "x\ny", 5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["strategy"], "windows-node-entry-missing")
        run.assert_not_called()

    def test_windows_node_shims_fail_closed(self) -> None:
        import subprocess as sp
        for node in ("C:/Users/x/AppData/Roaming/npm/node.cmd", "C:/Tools/node.bat"):
            with mock.patch.object(digest, "_is_windows", return_value=True):
                with mock.patch.object(digest.shutil, "which", return_value=node):
                    with mock.patch.object(sp, "run") as run:
                        result = digest.deliver("t", "x\ny", 5)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "safe-launch-unresolved")
            run.assert_not_called()

    def test_windows_node_exe_passes_guard(self) -> None:
        self.assertTrue(digest._is_safe_node("C:/Program Files/nodejs/node.exe"))
        self.assertTrue(digest._is_safe_node("/usr/bin/node"))
        self.assertFalse(digest._is_safe_node("C:/x/node.cmd"))
        self.assertFalse(digest._is_safe_node("C:/x/node.bat"))
        self.assertFalse(digest._is_safe_node(None))


class DeliverFailureTests(unittest.TestCase):
    def test_nonzero_return_is_not_success(self) -> None:
        import subprocess as sp
        with mock.patch.object(digest, "_is_windows", return_value=False):
            with mock.patch.object(digest, "resolve_openclaw", return_value="openclaw"):
                with mock.patch.object(sp, "run", return_value=mock.Mock(returncode=1, stderr="boom")):
                    result = digest.deliver("t", "m\n2", 5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["returncode"], 1)

    def test_timeout_is_not_success(self) -> None:
        import subprocess as sp
        def boom(argv, **kwargs):
            raise sp.TimeoutExpired(cmd=argv, timeout=5, stderr="partial")
        with mock.patch.object(digest, "_is_windows", return_value=False):
            with mock.patch.object(digest, "resolve_openclaw", return_value="openclaw"):
                with mock.patch.object(sp, "run", side_effect=boom):
                    result = digest.deliver("t", "m\n2", 5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "timeout")

    def test_error_output_is_not_leaked(self) -> None:
        import subprocess as sp
        sentinel = "SENTINEL-PRIVATE-MESSAGE-CHECK"
        with mock.patch.object(digest, "_is_windows", return_value=False):
            with mock.patch.object(digest, "resolve_openclaw", return_value="openclaw"):
                with mock.patch.object(sp, "run", return_value=mock.Mock(returncode=1, stderr=sentinel)):
                    result = digest.deliver("t", "m\n2", 5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "nonzero-exit")
        self.assertEqual(result["stderr_tail"], "")
        self.assertNotIn(sentinel, json.dumps(result))

    def test_os_error_is_not_success_without_leak(self) -> None:
        import subprocess as sp
        secret = "SECRET-MESSAGE-BODY-123"
        with mock.patch.object(digest, "_is_windows", return_value=False):
            with mock.patch.object(digest, "resolve_openclaw", return_value="openclaw"):
                with mock.patch.object(sp, "run", side_effect=OSError("nope")):
                    result = digest.deliver("t", secret, 5)
        self.assertFalse(result["ok"])
        blob = json.dumps(result)
        self.assertNotIn(secret, blob)

    def test_failed_send_does_not_corrupt_dedupe_state(self) -> None:
        import subprocess as sp
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            with mock.patch.object(digest, "deliver", return_value={"ok": False, "returncode": 1}):
                fake_state = {"sent_keys": {}}
                state.write_text(json.dumps(fake_state), encoding="utf-8")
                loaded = json.loads(state.read_text(encoding="utf-8"))
                self.assertEqual(loaded["sent_keys"], {})

    def test_stale_and_duplicate_rules_retained(self) -> None:
        import subprocess as sp
        old = {
            "generated_at_utc": "2020-01-01T00:00:00Z",
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert-level-freshness-controller.json"
            path.write_text(json.dumps(old), encoding="utf-8")
            with mock.patch.object(digest, "LEVELS", path):
                payload = digest.build_payload("morning")
        self.assertEqual(payload["status"], "blocked")
        self.assertIsNone(payload["message_preview"])


class SendUnconfirmedTests(unittest.TestCase):
    def _fresh_levels(self) -> dict:
        stamp = datetime.now(timezone.utc) - timedelta(minutes=30)
        return {
            "generated_at_utc": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "alert_state_counts": {"monitor_only": 1},
                "band_entry_signal_tickers": [],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": ["ETN"],
                "freshness_review_tickers": [],
                "quote_session_dates": ["2026-09-11"],
                "quote_as_of_utc_values": ["2026-09-11T19:59:44Z"],
            },
        }

    def _run_send(self, tmp: str, result: dict):
        import contextlib
        import io
        import sys
        root = Path(tmp)
        (root / "alert-level-freshness-controller.json").write_text(
            json.dumps(self._fresh_levels()), encoding="utf-8"
        )
        out = io.StringIO()
        with mock.patch.object(digest, "LEVELS", root / "alert-level-freshness-controller.json"):
            with mock.patch.object(digest, "TMP", root), mock.patch.object(digest, "THESIS_DIR", root), \
                    mock.patch.object(digest, "ROOT", root):
                with mock.patch.object(digest, "deliver", return_value=result):
                    with mock.patch.object(
                        sys, "argv",
                        ["finance_alert_os_digest.py", "--mode", "midday", "--send", "--validate",
                         "--out", str(root / "digest.json")],
                    ):
                        with contextlib.redirect_stdout(out):
                            rc = digest.main()
        return rc, json.loads(out.getvalue()), root / "finance-alert-os-digest-state.json"

    def _sent_keys(self, state_path: Path) -> dict:
        if not state_path.exists():
            return {}
        return json.loads(state_path.read_text(encoding="utf-8")).get("sent_keys", {})

    def test_timeout_is_unconfirmed_and_records_dedupe_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, printed, state_path = self._run_send(
                tmp, {"ok": False, "error": "timeout", "stderr_tail": ""}
            )
            self.assertEqual(printed["status"], "send_unconfirmed")
            self.assertEqual(rc, 0)
            keys = self._sent_keys(state_path)
            self.assertEqual(len(keys), 1)
            entry = next(iter(keys.values()))
            self.assertFalse(entry["confirmed"])
            self.assertEqual(entry["mode"], "midday")
            self.assertIn(
                "delivery_unconfirmed_transport_timeout", printed["warnings"]
            )

    def test_nonzero_exit_stays_failed_without_dedupe_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, printed, state_path = self._run_send(
                tmp, {"ok": False, "error": "nonzero-exit", "returncode": 1, "stderr_tail": ""}
            )
            self.assertEqual(printed["status"], "send_failed")
            self.assertEqual(rc, 1)
            self.assertEqual(self._sent_keys(state_path), {})

    def test_safe_launch_unresolved_stays_failed_without_dedupe_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, printed, state_path = self._run_send(
                tmp, {"ok": False, "error": "safe-launch-unresolved"}
            )
            self.assertEqual(printed["status"], "send_failed")
            self.assertEqual(rc, 1)
            self.assertEqual(self._sent_keys(state_path), {})

    def test_success_records_confirmed_dedupe_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, printed, state_path = self._run_send(
                tmp, {"ok": True, "returncode": 0, "transport": {}}
            )
            self.assertEqual(printed["status"], "sent")
            self.assertEqual(rc, 0)
            keys = self._sent_keys(state_path)
            self.assertEqual(len(keys), 1)
            entry = next(iter(keys.values()))
            self.assertTrue(entry["confirmed"])
            self.assertEqual(entry["mode"], "midday")


class ThesisBlockTests(unittest.TestCase):
    TODAY = datetime(2026, 9, 30).date()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _record(self, ticker: str, **over) -> dict:
        rec = {
            "schema": "veritas.thesis_record.v1",
            "ticker": ticker,
            "status": "accepted",
            "thesis_statement": f"{ticker} statement.",
            "cases": {
                "base": {"summary": f"{ticker} base case"},
                "bull": {"summary": f"{ticker} bull case"},
                "bear": {"summary": f"{ticker} bear case"},
            },
            "catalysts": [
                {"event": "Past event", "expected_date": "2026-08-01", "date_confidence": "confirmed"},
                {"event": "Later event", "expected_date": "2026-11-05", "date_confidence": "provider_estimate"},
                {"event": "Soon event", "expected_date": "2026-10-10", "date_confidence": "company_confirmed"},
            ],
            "conviction": "high",
            "review_due": "2026-12-27",
            "owner_accepted_at": "2026-09-27T12:22:00-07:00",
        }
        rec.update(over)
        return rec

    def _write(self, ticker: str, **over) -> None:
        (self.dir / f"{ticker}.json").write_text(json.dumps(self._record(ticker, **over)), encoding="utf-8")

    def _levels(self, band=(), inval=(), rows=None) -> dict:
        return {
            "generated_at_utc": "2026-09-30T00:00:00Z",
            "rows": rows if rows is not None else [
                {"ticker": t, "latest_price": 101.234, "invalidation_threshold": 90.5,
                 "sql_reference": {"reference_invalidation_level": 91.25}}
                for t in (*band, *inval)
            ],
            "summary": {
                "alert_state_counts": {"band_entry": len(band), "invalidation": len(inval)},
                "band_entry_signal_tickers": list(band),
                "invalidation_signal_tickers": list(inval),
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": [],
                "freshness_review_tickers": [],
            },
        }

    def _msg(self, levels: dict, previous=None) -> str:
        with mock.patch.object(digest, "baseline_guard_line", return_value=None):
            return build_message(
                "midday", levels, previous_summary=previous, thesis_dir=self.dir, digest_date=self.TODAY,
                thesis_context=True,
            )

    def test_thesis_context_is_opt_in(self) -> None:
        # The recurring chain calls build_message(window, controller) for its
        # proof preview and alert-ledger message_text; that must not change.
        self._write("AAA")
        levels = self._levels(band=["AAA"])
        with mock.patch.object(digest, "baseline_guard_line", return_value=None):
            plain = build_message("midday", levels, thesis_dir=self.dir, digest_date=self.TODAY)
        self.assertNotIn("thesis context", plain)
        self.assertNotIn("AAA (band entry)", plain)
        self.assertEqual(plain, self._msg(levels, previous={"band_entry_signal_tickers": ["AAA"]}))

    def test_new_band_entry_gets_full_block(self) -> None:
        self._write("AAA")
        msg = self._msg(self._levels(band=["AAA"]), previous={})
        self.assertIn("New entries - thesis context:", msg)
        self.assertIn("AAA (band entry) - high conviction, thesis accepted 2026-09-27:", msg)
        self.assertIn("AAA statement.", msg)
        for case in ("Base: AAA base case", "Bull: AAA bull case", "Bear: AAA bear case"):
            self.assertIn("  " + case, msg)
        self.assertIn("  Next catalyst: Soon event 2026-10-10 (company_confirmed)", msg)
        self.assertIn("  Invalidation: 91.25 (guarded SQL); last price 101.23", msg)
        self.assertNotIn("overdue", msg)

    def test_name_in_previous_summary_gets_no_block(self) -> None:
        self._write("AAA")
        self._write("BBB")
        prev = {"band_entry_signal_tickers": ["AAA"], "invalidation_signal_tickers": []}
        msg = self._msg(self._levels(band=["AAA", "BBB"]), previous=prev)
        self.assertNotIn("AAA (band entry)", msg)
        self.assertIn("BBB (band entry)", msg)

    def test_no_previous_summary_all_new_capped_at_five(self) -> None:
        names = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
        for n in names:
            self._write(n)
        msg = self._msg(self._levels(band=names), previous=None)
        self.assertEqual(sum(1 for n in names if f"{n} (band entry)" in msg), 5)
        self.assertIn("Thesis blocks omitted for 2 more new entries: A6, A7", msg)

    def test_invalidation_ordered_first(self) -> None:
        for n in ("AAA", "BBB", "ZZZ"):
            self._write(n)
        msg = self._msg(self._levels(band=["AAA", "BBB"], inval=["ZZZ"]), previous={})
        self.assertLess(msg.index("ZZZ (invalidation)"), msg.index("AAA (band entry)"))
        self.assertLess(msg.index("AAA (band entry)"), msg.index("BBB (band entry)"))

    def test_band_entry_to_invalidation_counts_as_new(self) -> None:
        self._write("AAA")
        prev = {"band_entry_signal_tickers": ["AAA"], "invalidation_signal_tickers": []}
        msg = self._msg(self._levels(inval=["AAA"]), previous=prev)
        self.assertIn("AAA (invalidation) - high conviction", msg)

    def test_missing_and_non_accepted_thesis_give_no_accepted_line(self) -> None:
        self._write("DRAFT", status="draft")
        msg = self._msg(self._levels(band=["DRAFT", "GONE"]), previous={})
        self.assertIn("DRAFT (band entry) - no accepted thesis on file.", msg)
        self.assertIn("GONE (band entry) - no accepted thesis on file.", msg)

    def test_malformed_thesis_degrades_only_that_ticker(self) -> None:
        (self.dir / "BAD.json").write_text("{not json", encoding="utf-8")
        self._write("OKK")
        self._write("PART", cases={"base": {"summary": "only base"}})
        msg = self._msg(self._levels(band=["BAD", "OKK", "PART"]), previous={})
        self.assertIn("BAD (band entry) - thesis unavailable.", msg)
        self.assertIn("PART (band entry) - thesis unavailable.", msg)
        self.assertIn("OKK (band entry) - high conviction", msg)
        self.assertEqual(msg.splitlines()[-1], digest.BOUNDARY)

    def test_oversize_thesis_file_is_unavailable(self) -> None:
        (self.dir / "BIG.json").write_text(json.dumps(self._record("BIG", pad="x" * 300000)), encoding="utf-8")
        msg = self._msg(self._levels(band=["BIG"]), previous={})
        self.assertIn("BIG (band entry) - thesis unavailable.", msg)

    def test_dotted_ticker_maps_to_file(self) -> None:
        self._write("BRK.B")
        msg = self._msg(self._levels(band=["BRK.B"]), previous={})
        self.assertIn("BRK.B (band entry) - high conviction", msg)

    def test_overdue_review_shown_and_not_shown(self) -> None:
        self._write("OLD", review_due="2026-09-01")
        self._write("NEW", review_due="2026-09-30")
        msg = self._msg(self._levels(band=["OLD", "NEW"]), previous={})
        self.assertIn("  Thesis review overdue (due 2026-09-01)", msg)
        self.assertEqual(msg.count("Thesis review overdue"), 1)

    def test_catalyst_fallbacks(self) -> None:
        self._write("UND", catalysts=[{"event": "Someday", "expected_date": None, "date_confidence": "unknown"}])
        self._write("NOC", catalysts=[])
        msg = self._msg(self._levels(band=["UND", "NOC"]), previous={})
        self.assertIn("  Next catalyst: Someday date unknown (unknown)", msg)
        self.assertEqual(msg.count("Next catalyst"), 1)

    def test_price_omitted_when_absent(self) -> None:
        self._write("AAA")
        rows = [{"ticker": "AAA", "invalidation_threshold": 90.5}]
        msg = self._msg(self._levels(band=["AAA"], rows=rows), previous={})
        self.assertIn("  Invalidation: 90.50 (guarded SQL)", msg)
        self.assertNotIn("last price", msg)

    def test_truncation_lengths(self) -> None:
        self._write("LNG", thesis_statement="s" * 500,
                    cases={k: {"summary": "c" * 500} for k in ("base", "bull", "bear")})
        lines = self._msg(self._levels(band=["LNG"]), previous={}).splitlines()
        stmt = next(l for l in lines if l.startswith("sss"))
        self.assertEqual(len(stmt), 220)
        self.assertTrue(stmt.endswith("..."))
        base = next(l for l in lines if l.startswith("  Base:"))
        self.assertEqual(len(base), len("  Base: ") + 160)

    def test_char_cap_enforced_with_omitted_line(self) -> None:
        names = [f"T{i}" for i in range(5)]
        for n in names:
            self._write(n, thesis_statement="s" * 500,
                        cases={k: {"summary": "c" * 500} for k in ("base", "bull", "bear")})
        msg = self._msg(self._levels(band=names), previous={})
        self.assertLessEqual(len(msg), 3500)
        shown = [n for n in names if f"{n} (band entry)" in msg]
        self.assertLess(len(shown), 5)
        self.assertEqual(shown, names[: len(shown)])
        omitted = names[len(shown):]
        self.assertIn(
            f"Thesis blocks omitted for {len(omitted)} more new entries: {', '.join(omitted)}", msg
        )
        self.assertEqual(msg.splitlines()[-1], digest.BOUNDARY)

    def test_section_dropped_when_even_omitted_line_cannot_fit(self) -> None:
        levels = self._levels(band=["AAA"])
        with mock.patch.object(digest, "MESSAGE_MAX_CHARS", 10):
            msg = self._msg(levels, previous={})
        self.assertNotIn("thesis", msg)
        self.assertEqual(msg.splitlines()[-1], digest.BOUNDARY)

    def test_boundary_last_and_placement_before_confidence(self) -> None:
        self._write("AAA")
        levels = self._levels(band=["AAA"])
        levels["rows"][0]["sql_reference"]["reference_confidence"] = 40
        lines = self._msg(levels, previous={}).splitlines()
        self.assertEqual(lines[-1], digest.BOUNDARY)
        head = lines.index("New entries - thesis context:")
        conf = next(i for i, l in enumerate(lines) if l.startswith("Data confidence"))
        self.assertLess(lines.index(next(l for l in lines if l.startswith("Controller generated:"))), head)
        self.assertLess(head, conf)

    def test_no_new_entries_leaves_message_unchanged(self) -> None:
        self._write("AAA")
        levels = self._levels(band=["AAA"])
        prev = {"band_entry_signal_tickers": ["AAA"]}
        msg = self._msg(levels, previous=prev)
        self.assertNotIn("thesis context", msg)

    def test_semantic_key_unchanged_by_thesis_content(self) -> None:
        levels = self._levels(band=["AAA"])
        key = lambda: digest.semantic_digest_key("2026-09-30", "midday", {"summary": levels["summary"]}, "ok")
        before = key()
        self._write("AAA", thesis_statement="one")
        self._msg(levels, previous={})
        self._write("AAA", thesis_statement="two", status="draft")
        self._msg(levels, previous={})
        self.assertEqual(before, key())

    def test_read_previous_summary(self) -> None:
        path = self.dir / "prev.json"
        self.assertIsNone(digest.read_previous_summary(path))
        path.write_text("garbage", encoding="utf-8")
        self.assertIsNone(digest.read_previous_summary(path))
        path.write_text(json.dumps({"status": "sent", "summary": {"band_entry_signal_tickers": ["A"]}}), encoding="utf-8")
        self.assertEqual(digest.read_previous_summary(path), {"band_entry_signal_tickers": ["A"]})
        for undelivered in ("send_failed", "weekend_quiet", "blocked", "ok"):
            path.write_text(json.dumps({"status": undelivered, "summary": {"band_entry_signal_tickers": ["A"]}}), encoding="utf-8")
            self.assertIsNone(digest.read_previous_summary(path), undelivered)
        # the state file's last delivered summary wins over the artifact
        state = self.dir / "state.json"
        self.assertIsNone(digest.read_previous_summary(path, state))
        state.write_text(json.dumps({"sent_keys": {}, "last_delivered_summary": {"band_entry_signal_tickers": ["S"]}}), encoding="utf-8")
        self.assertEqual(digest.read_previous_summary(path, state), {"band_entry_signal_tickers": ["S"]})

    def test_main_reads_previous_before_overwrite(self) -> None:
        import contextlib
        import io
        import sys
        self._write("AAA")
        self._write("BBB")
        stamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        levels = self._levels(band=["AAA", "BBB"])
        levels.update({"generated_at_utc": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "ok",
                       "validation": {"status": "ok"}})
        levels["summary"]["fresh_intraday_signal_eligible_tickers"] = ["AAA", "BBB"]
        root = self.dir / "tmproot"
        root.mkdir()
        (root / "alert-level-freshness-controller.json").write_text(json.dumps(levels), encoding="utf-8")
        out = root / "digest.json"
        out.write_text(json.dumps({"status": "sent", "summary": {"band_entry_signal_tickers": ["AAA"]}}), encoding="utf-8")
        sends: list[str] = []

        def fake_deliver(target: str, message: str, timeout: float) -> dict:
            sends.append(message)
            return {"ok": True}

        def run(*extra: str) -> dict:
            buf = io.StringIO()
            argv = ["x", "--mode", "midday", "--write", "--out", str(out), *extra]
            with mock.patch.object(digest, "LEVELS", root / "alert-level-freshness-controller.json"), \
                    mock.patch.object(digest, "GUARD", root / "no-guard.json"), \
                    mock.patch.object(digest, "TMP", root), \
                    mock.patch.object(digest, "THESIS_DIR", self.dir), \
                    mock.patch.object(digest, "ROOT", root), \
                    mock.patch.object(digest, "deliver", fake_deliver), \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(buf):
                digest.main()
            return json.loads(out.read_text(encoding="utf-8"))

        first = run()["message_preview"]
        self.assertIn("BBB (band entry)", first)
        self.assertNotIn("AAA (band entry)", first)
        # an undelivered run (status ok, no --send) does not consume BBB's first appearance
        self.assertIn("BBB (band entry)", run()["message_preview"])
        sent = run("--send")
        self.assertEqual(sent["status"], "sent")
        self.assertIn("BBB (band entry)", sends[-1])
        state = json.loads((root / "finance-alert-os-digest-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_delivered_summary"]["band_entry_signal_tickers"], ["AAA", "BBB"])
        self.assertTrue(state["sent_keys"])
        # after delivery both names are "previous"; the next run has no new entries
        self.assertNotIn("thesis context", run()["message_preview"])


if __name__ == "__main__":
    unittest.main()


def test_suppressed_line_only_when_nothing_is_fire_eligible() -> None:
    import finance_alert_os_digest as digest
    base = {"monitor_only_tickers": ["AAA"], "band_entry_signal_tickers": ["BBB"]}
    mixed = digest.build_message("midday", {"summary": {**base, "fresh_intraday_signal_eligible_tickers": ["BBB"]}})
    assert "firing is suppressed" not in mixed
    assert "Review-only (last-completed-session evidence, not fire-eligible): AAA" in mixed
    closed = digest.build_message("midday", {"summary": {**base, "fresh_intraday_signal_eligible_tickers": []}})
    assert "firing is suppressed" in closed


def test_digest_key_ignores_timestamps_but_tracks_content() -> None:
    import finance_alert_os_digest as digest
    one = {"summary": {"band_entry_signal_tickers": ["B", "A"], "quote_as_of_utc_values": ["2026-09-23T14:00:00Z"]}}
    two = {"summary": {"band_entry_signal_tickers": ["A", "B"], "quote_as_of_utc_values": ["2026-09-23T15:00:00Z"]}}
    three = {"summary": {"band_entry_signal_tickers": ["A"]}}
    k = lambda levels: digest.semantic_digest_key("2026-09-23", "midday", levels, "ok")
    assert k(one) == k(two)
    assert k(one) != k(three)
    assert digest.semantic_digest_key("2026-09-24", "midday", one, "ok") != k(one)


def test_confidence_line_prints_median_lowest_and_missing() -> None:
    import finance_alert_os_digest as digest
    rows = [{"ticker": t, "sql_reference": {"reference_confidence": c}}
            for t, c in (("AAA", 50), ("BBB", 15), ("CCC", 30), ("DDD", None))]
    line = digest.confidence_line({"rows": rows})
    assert line.startswith("Data confidence (0-1, provisional, single-source cap 0.50):")
    assert "median 0.30 over 3" in line and "lowest BBB 0.15, CCC 0.30" in line
    assert "missing for 1: DDD" in line
    msg = digest.build_message("morning", {"rows": rows, "summary": {}})
    assert msg.splitlines()[-2] == line and msg.splitlines()[-1] == digest.BOUNDARY
    assert digest.confidence_line({"summary": {}}) is None
    assert "Data confidence" not in digest.build_message("morning", {"summary": {}})
