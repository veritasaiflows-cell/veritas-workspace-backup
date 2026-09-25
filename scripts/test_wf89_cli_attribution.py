#!/usr/bin/env python3
"""Contract v0.3 tests: CLI dispatch records bound by wf89_credit_reader.read_cli.

Synthetic temp fixtures only; never touches live stores or the real
state/wf89-dispatch-records directory.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_wf89_credit_reader import (  # noqa: E402
    MIN_USAGE, Ctx, base_task, completed_event, entry_json, mk_executor, mk_global)
from wf89_credit_reader import read_cli  # noqa: E402
from wf89_dispatch_record import full_session_key, write_record  # noqa: E402

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

    def test_two_matching_rows_fail_closed(self) -> None:
        self.record()
        mk_global(self.c.gdb, [cli_task(), cli_task(task_id="t2", run_id="r2", created_at=3000)], [])
        executor(self.c)
        rec = self.run_cli()["records"][0]
        self.assertEqual(rec["state"], "MISMATCH")
        self.assertFalse(rec["creditable"])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
