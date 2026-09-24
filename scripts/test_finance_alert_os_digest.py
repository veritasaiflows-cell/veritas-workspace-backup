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
            with mock.patch.object(digest, "LEVELS", path):
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
            with mock.patch.object(digest, "TMP", root):
                with mock.patch.object(digest, "deliver", return_value=result):
                    with mock.patch.object(
                        sys, "argv",
                        ["finance_alert_os_digest.py", "--mode", "midday", "--send", "--validate"],
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
