"""Tests for the arena dispatch wall-clock enforcer."""
from __future__ import annotations

import datetime
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKTREE / "scripts"
ENFORCER = SCRIPTS / "arena_dispatch_enforcer.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_enf = _load("arena_dispatch_enforcer", ENFORCER)


def _plan(n=3, timeout_s=600, issued="2026-09-20T20:00:00+00:00"):
    base = datetime.datetime.fromisoformat(issued)
    deadline = (base + datetime.timedelta(seconds=timeout_s)).isoformat()
    return {
        "schema": "veritas.arena_dispatch_plan.v1",
        "model": "m",
        "timeout_s": timeout_s,
        "retries": 0,
        "thinking": "high",
        "timestamp_utc": issued,
        "deadline_utc": deadline,
        "cases": [
            {"instance_id": f"case-{i}", "family": "T6",
             "prompt_path": f"prompts/case-{i}.json",
             "prompt_txt_path": f"prompts/case-{i}.txt",
             "timeout_s": timeout_s, "deadline_utc": deadline}
            for i in range(n)
        ],
    }


def _run_cli(*cli_args, timeout=120):
    return subprocess.run(
        [sys.executable, str(ENFORCER), *cli_args],
        capture_output=True, text=True, timeout=timeout,
    )


class DeadlineTests(unittest.TestCase):
    def test_plan_deadline_matches_timestamp_plus_timeout(self):
        plan = _plan()
        deadline = _enf.effective_plan_deadline(plan)
        issued = datetime.datetime.fromisoformat(plan["timestamp_utc"])
        self.assertEqual((deadline - issued).total_seconds(), 600)

    def test_legacy_plan_without_deadline_derives_from_timestamp(self):
        plan = _plan()
        del plan["deadline_utc"]
        for case in plan["cases"]:
            del case["deadline_utc"]
        deadline = _enf.effective_plan_deadline(plan)
        issued = datetime.datetime.fromisoformat(plan["timestamp_utc"])
        self.assertEqual((deadline - issued).total_seconds(), 600)

    def test_nonzero_retries_refused(self):
        plan = _plan()
        plan["retries"] = 1
        with self.assertRaises(SystemExit):
            _enf.effective_plan_deadline(plan)

    def test_naive_timestamp_refused(self):
        plan = _plan(issued="2026-09-20T20:00:00")
        del plan["deadline_utc"]
        with self.assertRaises(SystemExit):
            _enf.effective_plan_deadline(plan)


class StuckDetectionTests(unittest.TestCase):
    def test_overdue_missing_is_stuck_before_finalize(self):
        plan = _plan(n=2)
        now = datetime.datetime.fromisoformat("2026-09-20T20:20:01+00:00")
        verdict = _enf.classify(plan, {"case-0": '{"a":1}'}, now)
        self.assertEqual(verdict["answered"], ["case-0"])
        self.assertEqual(verdict["overdue"], ["case-1"])
        self.assertEqual(verdict["pending"], [])

    def test_before_deadline_missing_is_pending_not_stuck(self):
        plan = _plan(n=2)
        now = datetime.datetime.fromisoformat("2026-09-20T20:05:00+00:00")
        verdict = _enf.classify(plan, {"case-0": '{"a":1}'}, now)
        self.assertEqual(verdict["pending"], ["case-1"])
        self.assertEqual(verdict["overdue"], [])

    def test_empty_string_counts_as_missing_not_answered(self):
        plan = _plan(n=1)
        now = datetime.datetime.fromisoformat("2026-09-20T20:05:00+00:00")
        verdict = _enf.classify(plan, {"case-0": ""}, now)
        self.assertEqual(verdict["pending"], ["case-0"])
        self.assertEqual(verdict["answered"], [])


class FinalizeTests(unittest.TestCase):
    def test_finalize_freezes_overdue_to_empty_fail_closed(self):
        plan = _plan(n=3)
        now = datetime.datetime.fromisoformat("2026-09-20T20:20:01+00:00")
        partial = {"case-0": '{"a":1}', "case-1": '{"b":2}'}
        final, audit = _enf.finalize(plan, partial, now)
        self.assertEqual(final["case-0"], '{"a":1}')
        self.assertEqual(final["case-1"], '{"b":2}')
        self.assertEqual(final["case-2"], "")
        self.assertEqual(audit["operational_timeout_count"], 1)
        self.assertEqual(audit["timed_out_ids"], ["case-2"])
        self.assertEqual(audit["schema"], "veritas.arena_dispatch_timeout_audit.v1")

    def test_finalize_keeps_answered_content_verbatim(self):
        plan = _plan(n=2)
        now = datetime.datetime.fromisoformat("2026-09-20T20:05:00+00:00")
        partial = {"case-0": '{"a":1}', "case-1": '{"b":2}'}
        final, audit = _enf.finalize(plan, partial, now)
        self.assertEqual(final, partial)
        self.assertEqual(audit["operational_timeout_count"], 0)

    def test_finalize_refuses_extra_ids(self):
        plan = _plan(n=1)
        now = datetime.datetime.fromisoformat("2026-09-20T20:05:00+00:00")
        with self.assertRaises(SystemExit):
            _enf.finalize(plan, {"case-0": "x", "rogue": "y"}, now)

    def test_cli_finalize_then_runner_grades_timeout(self):
        import importlib.util as ilu
        spec = ilu.spec_from_file_location(
            "arena_hidden_bank_runner_cli",
            str(SCRIPTS / "arena_hidden_bank_runner.py"))
        runner = ilu.module_from_spec(spec)
        spec.loader.exec_module(runner)
        plan = _plan(n=2)
        now = "2026-09-20T20:20:01+00:00"
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            plan_p = tmpd / "plan.json"
            resp_p = tmpd / "partial.json"
            out_p = tmpd / "final.json"
            audit_p = tmpd / "audit.json"
            plan_p.write_text(json.dumps(plan) + "\n", encoding="utf-8")
            resp_p.write_text(json.dumps({"case-0": '{"a": 1}'}) + "\n", encoding="utf-8")
            proc = _run_cli("--plan", str(plan_p), "--responses", str(resp_p),
                            "--out", str(out_p), "--audit", str(audit_p), "--now", now)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            final = json.loads(out_p.read_text(encoding="utf-8"))
            self.assertEqual(final["case-1"], "")
            # The frozen "" slot must grade as an operational timeout, never factual.
            visible = {"prompt": {}, "family": "T6"}
            hidden = {"instance_id": "case-1", "family": "T6", "key": {"a": 1}}
            graded = runner.grade_text(visible, hidden, final["case-1"])
            self.assertTrue(graded["operational_timeout"])
            self.assertFalse(graded["strict_pass"])
            self.assertFalse(graded["factual"])

    def test_cli_check_exit_2_on_stuck(self):
        plan = _plan(n=2)
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            plan_p = tmpd / "plan.json"
            resp_p = tmpd / "partial.json"
            plan_p.write_text(json.dumps(plan) + "\n", encoding="utf-8")
            resp_p.write_text(json.dumps({"case-0": "x"}) + "\n", encoding="utf-8")
            stuck = _run_cli("--plan", str(plan_p), "--check",
                             "--responses", str(resp_p),
                             "--now", "2026-09-20T20:20:01+00:00")
            self.assertEqual(stuck.returncode, 2)
            clean = _run_cli("--plan", str(plan_p), "--check",
                             "--responses", str(resp_p),
                             "--now", "2026-09-20T20:05:00+00:00")
            self.assertEqual(clean.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
