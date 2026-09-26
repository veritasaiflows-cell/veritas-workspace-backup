#!/usr/bin/env python3
"""Contract v0.3 tests: CLI dispatch records bound by wf89_credit_reader.read_cli.

Synthetic temp fixtures only; never touches live stores or the real
state/wf89-dispatch-records directory.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_wf89_credit_reader import (  # noqa: E402
    MIN_USAGE, Ctx, base_task, completed_event, entry_json, mk_executor, mk_global)
import wf89_credit_reader  # noqa: E402
import wf89_dispatch_record  # noqa: E402
from wf89_credit_reader import read_cli  # noqa: E402
from wf89_dispatch_record import full_session_key, launch, write_record  # noqa: E402

KEY = "agent:ag1:job1"
TEXT = "Scoped job: add farewell()."


def cli_task(**kw: object) -> dict:
    d = base_task(runtime="cli", task_kind=None, label=None, child_session_key=KEY,
                  requester_session_key=KEY, requester_agent_id="ag1", task=TEXT,
                  created_at=2000, detail_json=None)
    d.update(kw)
    return d


def executor(c: Ctx) -> None:
    mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                [{"session_key": KEY, "current_session_id": "w1",
                  "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"}],
                [{"session_id": "w1", "session_key": KEY, "previous_session_id": None,
                  "status": "done", "model": "m1", "model_provider": "p1"}],
                [("w1", "r1", completed_event("r1", "w1", MIN_USAGE))])


class CliAttributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Ctx()
        self.ddir = self.c.tmp / "dispatch"
        self.msg = self.c.tmp / "task.md"
        self.msg.write_text(TEXT + "\n", encoding="utf-8")  # store keeps it stripped

    def record(self, now_ms: int = 1000, label: str = "wf89 cli proof") -> dict:
        return write_record("ag1", "job1", label, self.msg, self.ddir, now_ms=now_ms)

    def run_cli(self) -> dict:
        return read_cli(self.ddir, global_db=self.c.gdb, agent_root=self.c.aroot)

    def test_recorded_cli_run_is_creditable_with_record_label(self) -> None:
        self.record()
        mk_global(self.c.gdb, [cli_task()], [])
        executor(self.c)
        out = self.run_cli()
        rec = out["records"][0]
        self.assertEqual(rec["state"], "CREDITABLE")
        self.assertEqual(rec["label"], "wf89 cli proof")
        self.assertEqual(rec["usage"]["total"], 260)
        self.assertEqual(out["cli_rows_without_dispatch_record_by_agent"], {})

    def test_cli_row_without_record_is_never_credited(self) -> None:
        mk_global(self.c.gdb, [cli_task()], [])
        executor(self.c)
        out = self.run_cli()
        self.assertEqual(out["records"], [])
        self.assertEqual(out["cli_rows_without_dispatch_record_by_agent"], {"ag1": 1})

    def test_task_text_mismatch_stays_pending(self) -> None:
        self.record()
        mk_global(self.c.gdb, [cli_task(task="a different task")], [])
        executor(self.c)
        self.assertEqual(self.run_cli()["records"][0]["state"], "PENDING")

    def test_row_older_than_record_cannot_be_claimed(self) -> None:
        self.record(now_ms=5000)
        mk_global(self.c.gdb, [cli_task(created_at=2000)], [])
        executor(self.c)
        self.assertEqual(self.run_cli()["records"][0]["state"], "PENDING")

    def test_mixed_case_record_binds_lowercased_store_key(self) -> None:
        write_record("ag1", "JOB1", "case proof", self.msg, self.ddir, now_ms=1000)
        mk_global(self.c.gdb, [cli_task()], [])
        executor(self.c)
        rec = self.run_cli()["records"][0]
        self.assertEqual(rec["state"], "CREDITABLE")
        self.assertEqual(full_session_key("ag1", "Job-20260926T0627Z"), "agent:ag1:job-20260926t0627z")

    def test_two_matching_rows_fail_closed(self) -> None:
        self.record()
        mk_global(self.c.gdb, [cli_task(), cli_task(task_id="t2", run_id="r2", created_at=3000)], [])
        executor(self.c)
        rec = self.run_cli()["records"][0]
        self.assertEqual(rec["state"], "MISMATCH")
        self.assertFalse(rec["creditable"])

    def test_two_records_claiming_one_row_fail_closed(self) -> None:
        self.record(now_ms=1000)
        self.record(now_ms=1500)
        mk_global(self.c.gdb, [cli_task()], [])
        executor(self.c)
        out = self.run_cli()
        self.assertEqual([r["state"] for r in out["records"]], ["MISMATCH", "MISMATCH"])
        self.assertFalse(any(r["creditable"] for r in out["records"]))
        self.assertEqual(out["cli_rows_without_dispatch_record_by_agent"], {})

    def test_missing_executor_witness_is_unreadable(self) -> None:
        self.record()
        mk_global(self.c.gdb, [cli_task()], [])
        self.assertEqual(self.run_cli()["records"][0]["state"], "UNREADABLE")

    def test_invalid_record_is_reported_not_used(self) -> None:
        self.ddir.mkdir()
        (self.ddir / "bad.json").write_text('{"schema": "x"}', encoding="utf-8")
        mk_global(self.c.gdb, [cli_task()], [])
        out = self.run_cli()
        self.assertEqual(out["records"], [])
        self.assertEqual(len(out["dispatch_record_errors"]), 1)

    def test_writer_rejects_foreign_session_key_and_empty_label(self) -> None:
        with self.assertRaises(ValueError):
            full_session_key("ag1", "agent:other:job1")
        with self.assertRaises(ValueError):
            self.record(label="  ")
        self.assertEqual(full_session_key("ag1", "job1"), KEY)


class LauncherTests(unittest.TestCase):
    """One-command dispatch: record and launch cannot drift apart."""

    def setUp(self) -> None:
        self.c = Ctx()
        self.ddir = self.c.tmp / "dispatch"
        self.msg = self.c.tmp / "task.md"
        self.msg.write_text(TEXT + "\n", encoding="utf-8")
        self.calls: list[list[str]] = []

    def runner(self, command: list[str], **kw: object) -> SimpleNamespace:
        # The record must already exist when the agent starts.
        self.assertEqual(len(list(self.ddir.glob("*.json"))), 1)
        self.calls.append(command)
        return SimpleNamespace(returncode=0, kw=kw)

    def test_launch_writes_record_first_then_runs_bound_command(self) -> None:
        rec, proc = launch("ag1", "job1", "wf89 launcher proof", message_file=self.msg,
                           extra_args=["--model", "p/m", "--json"], binary="openclaw",
                           dispatch_dir=self.ddir, runner=self.runner, check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.kw, {"check": False})
        self.assertEqual(self.calls, [["openclaw", "agent", "--agent", "ag1", "--session-key", KEY,
                                       "--message-file", str(self.msg), "--model", "p/m", "--json"]])
        stored = json.loads(Path(rec["_written"]).read_text(encoding="utf-8"))
        self.assertEqual(stored["session_key"], KEY)
        self.assertEqual(stored["launched_by"], "wf89_dispatch_record.launch")

    def test_launched_run_is_creditable_end_to_end(self) -> None:
        launch("ag1", "job1", "wf89 launcher proof", message_file=self.msg, binary="openclaw",
               dispatch_dir=self.ddir, runner=self.runner)
        mk_global(self.c.gdb, [cli_task(created_at=9_999_999_999_999)], [])
        executor(self.c)
        out = read_cli(self.ddir, global_db=self.c.gdb, agent_root=self.c.aroot)
        self.assertEqual(out["records"][0]["state"], "CREDITABLE")
        self.assertEqual(out["cli_rows_without_dispatch_record_by_agent"], {})

    def test_inline_message_text_binds_like_a_file(self) -> None:
        rec, _ = launch("ag1", "job1", "inline", message_text=TEXT, binary=["node", "oc.mjs"],
                        dispatch_dir=self.ddir, runner=self.runner)
        self.assertEqual(self.calls[0][:3], ["node", "oc.mjs", "agent"])
        self.assertIn("--message", self.calls[0])
        self.assertIsNone(rec["message_file"])
        self.assertEqual(rec["task_text_sha256"], wf89_credit_reader.normalized_text_hash(TEXT))

    def test_reserved_or_invalid_launches_write_no_record_and_never_run(self) -> None:
        for kwargs in ({"extra_args": ["--session-id", "x"]}, {"extra_args": ["--message=x"]},
                       {"extra_args": ["--to", "+1"]}, {"label": " "},
                       {"session_key": "agent:other:job1"}, {"message_text": "   "}):
            args = {"agent_id": "ag1", "session_key": "job1", "label": "ok", "message_file": self.msg}
            args.update(kwargs)
            if "message_text" in kwargs:
                args.pop("message_file")
            with self.assertRaises(ValueError, msg=kwargs):
                launch(**args, binary="openclaw", dispatch_dir=self.ddir, runner=self.runner)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.ddir.exists() and any(self.ddir.iterdir()))

    def test_cli_run_mode_passes_extra_args_and_returns_child_exit_code(self) -> None:
        seen = {}

        def fake_launch(*a: object, **kw: object) -> tuple:
            seen.update(args=a, kw=kw)
            return {"dispatch_id": "d"}, SimpleNamespace(returncode=3)

        with mock.patch.object(wf89_dispatch_record, "launch", fake_launch),                 mock.patch("sys.stderr"):
            code = wf89_dispatch_record.main(["--agent", "ag1", "--session-key", "job1", "--label", "L",
                                              "--message-file", str(self.msg), "--run", "--",
                                              "--model", "p/m", "--json"])
        self.assertEqual(code, 3)
        self.assertEqual(seen["kw"]["extra_args"], ["--model", "p/m", "--json"])

    def test_cli_extra_args_without_run_are_refused(self) -> None:
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            wf89_dispatch_record.main(["--agent", "ag1", "--session-key", "job1", "--label", "L",
                                       "--message-file", str(self.msg), "--", "--json"])


class BypassAlarmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Ctx()
        self.ddir = self.c.tmp / "dispatch"

    def test_exec_background_rows_are_not_agent_runs(self) -> None:
        mk_global(self.c.gdb, [cli_task(task_id="x1", run_id="exec:x1", task_kind="exec",
                                        child_session_key=None, task="Background CLI command")], [])
        out = read_cli(self.ddir, global_db=self.c.gdb, agent_root=self.c.aroot)
        self.assertEqual(out["cli_rows_without_dispatch_record_by_agent"], {})
        self.assertEqual(out["cli_exec_background_rows"], 1)

    def test_only_unrecorded_runs_after_go_live_count_as_bypass(self) -> None:
        mk_global(self.c.gdb, [cli_task(created_at=4000),
                               cli_task(task_id="t2", run_id="r2", created_at=6000)], [])
        with mock.patch.object(wf89_credit_reader, "WRAPPER_GO_LIVE_MS", 5000):
            out = read_cli(self.ddir, global_db=self.c.gdb, agent_root=self.c.aroot)
        self.assertEqual(out["cli_rows_without_dispatch_record_by_agent"], {"ag1": 2})
        self.assertEqual(out["cli_rows_bypassing_dispatch_wrapper_by_agent"], {"ag1": 1})
        self.assertEqual([r["task_id"] for r in out["cli_bypass_rows"]], ["t2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
