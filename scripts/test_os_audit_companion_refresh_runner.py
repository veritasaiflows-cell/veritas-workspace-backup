"""Focused tests for os_audit_companion_refresh_runner.

Deterministic, no network, no model. Uses a temp copy layout for proof/state paths
by monkeypatching module-level paths.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "os_audit_companion_refresh_runner.py"

spec = importlib.util.spec_from_file_location("os_audit_companion_refresh_runner", MODULE_PATH)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_commands_match_cron_payload_exactly(self):
        expected = [
            ["python", "scripts/tmp_lifecycle_guard.py", "--write", "--validate"],
            ["python", "scripts/token_budget_status.py", "--write", "--validate"],
            ["python", "scripts/security_warning_ledger.py", "--write", "--validate"],
            ["python", "scripts/wf78_promotion_visibility_top10.py", "--write", "--validate"],
            ["python", "scripts/pm_autonomy_verifier.py", "--health-check", "--validate"],
            ["python", "scripts/status_card_packet.py", "--write", "--validate"],
        ]
        self.assertEqual(runner.COMMANDS, expected)

    def test_dry_run_writes_proof_without_executing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            proof = Path(td) / "proof.json"
            with mock.patch.object(runner, "PROOF_PATH", proof), mock.patch.object(
                runner, "STATE_PATH", Path(td) / "state.json"
            ), mock.patch.object(
                runner, "_inventory_fingerprint", return_value={"sha256": "dry", "file_count": 0}
            ), mock.patch.object(runner, "run_commands") as run_mock:
                argv = sys.argv
                sys.argv = ["runner", "--dry-run"]
                try:
                    rc = runner.main()
                finally:
                    sys.argv = argv
                self.assertEqual(rc, 0)
                run_mock.assert_not_called()
                loaded = json.loads(proof.read_text(encoding="utf-8"))
                self.assertEqual(loaded["status"], "dry_run")
                self.assertTrue(loaded["dry_run"])
                self.assertEqual(len(loaded["commands_planned"]), 6)

    def test_run_commands_stops_on_first_failure(self):
        calls = []

        def fake_run(argv, cwd, capture_output, text, timeout):
            calls.append(argv)

            class Proc:
                returncode = 0 if len(calls) < 3 else 1
                stdout = "ok"
                stderr = ""

            return Proc()

        with mock.patch.object(runner.subprocess, "run", side_effect=fake_run):
            results, failed_at = runner.run_commands()
        self.assertEqual(failed_at, 3)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[-1]["exit_code"], 1)

    def test_skip_gate_evidence_flags_identical_inputs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            proof = Path(td) / "proof.json"
            state = Path(td) / "state.json"
            fp = {"sha256": "abc", "file_count": 10}
            state.write_text(
                json.dumps(
                    {
                        "generated_at_utc": "2026-08-26T00:00:00+00:00",
                        "input_fingerprint_after": fp,
                        "output_fingerprint": {"sha256": "out1"},
                    }
                ),
                encoding="utf-8",
            )

            class Proc:
                returncode = 0
                stdout = "ok"
                stderr = ""

            with mock.patch.object(runner, "PROOF_PATH", proof), mock.patch.object(
                runner, "STATE_PATH", state
            ), mock.patch.object(runner, "_inventory_fingerprint", return_value=fp), mock.patch.object(
                runner, "_output_fingerprint", return_value={"sha256": "out1"}
            ), mock.patch.object(
                runner.subprocess, "run", return_value=Proc()
            ):
                argv = sys.argv
                sys.argv = ["runner", "--write", "--validate"]
                try:
                    rc = runner.main()
                finally:
                    sys.argv = argv
            self.assertEqual(rc, 0)
            loaded = json.loads(proof.read_text(encoding="utf-8"))
            self.assertEqual(loaded["status"], "ok")
            self.assertTrue(loaded["skip_gate_evidence"]["would_have_skipped_this_run"])
            self.assertFalse(loaded["skip_gate_evidence"]["outputs_changed_vs_previous_run"])

    def test_state_not_updated_on_failure(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            proof = Path(td) / "proof.json"
            state = Path(td) / "state.json"

            class Proc:
                returncode = 1
                stdout = ""
                stderr = "boom"

            fp = {"sha256": "fp", "file_count": 0}
            with mock.patch.object(runner, "PROOF_PATH", proof), mock.patch.object(
                runner, "STATE_PATH", state
            ), mock.patch.object(runner, "_inventory_fingerprint", return_value=fp), mock.patch.object(
                runner, "_output_fingerprint", return_value={"sha256": "out"}
            ), mock.patch.object(runner.subprocess, "run", return_value=Proc()):
                argv = sys.argv
                sys.argv = ["runner", "--write"]
                try:
                    rc = runner.main()
                finally:
                    sys.argv = argv
            self.assertEqual(rc, 1)
            self.assertFalse(state.exists(), "state must not update when a command fails")


if __name__ == "__main__":
    unittest.main()
