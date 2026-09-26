#!/usr/bin/env python3
"""Focused tests for wf89_credit_reader (synthetic temp fixtures only).

Never touches live stores: builds tiny throwaway global + executor SQLite
DBs under a temp dir and points the reader at them via --global-db /
--agent-root. Covers contract v0.2: fully-bound creditable run,
PARTIAL/missing-usage, task_runs-only uncreditable, unreadable executor
store, window/entry MISMATCH, multi-window session_key keying, and
per-attempt/no-aggregation generation handling.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from wf89_credit_reader import read_task, task_text_hash  # noqa: E402


def completed_event(run_id: str, session_id: str, usage: dict | None, seq: int = 1) -> str:
    data: dict = {"aborted": False}
    if usage is not None:
        data["usage"] = usage
    return json.dumps({"type": "model.completed", "sessionId": session_id,
                       "runId": run_id, "seq": seq, "data": data})


FULL_USAGE = {"input": 100, "output": 50, "total": 150, "cost": {"total": 0.01},
              "cacheRead": 10, "reasoningTokens": 20}
MIN_USAGE = {"input": 200, "output": 60, "total": 260, "cost": {"total": 0.02}}


def mk_global(path: Path, tasks: list[dict], subs: list[dict]) -> None:
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE task_runs (task_id TEXT PRIMARY KEY, runtime TEXT,
      task_kind TEXT, requester_session_key TEXT, owner_key TEXT, scope_kind TEXT,
      child_session_key TEXT, agent_id TEXT, requester_agent_id TEXT, run_id TEXT,
      label TEXT, task TEXT, status TEXT, created_at INTEGER, started_at INTEGER,
      ended_at INTEGER, tool_use_count INTEGER, detail_json TEXT)""")
    con.execute("""CREATE TABLE subagent_runs (run_id TEXT, child_session_key TEXT,
      controller_session_key TEXT, requester_session_key TEXT, created_at INTEGER,
      payload_json TEXT)""")
    for t in tasks:
        con.execute("""INSERT INTO task_runs VALUES
          (:task_id,:runtime,:task_kind,:requester_session_key,:owner_key,:scope_kind,
           :child_session_key,:agent_id,:requester_agent_id,:run_id,:label,:task,
           :status,:created_at,:started_at,:ended_at,:tool_use_count,:detail_json)""", t)
    for s in subs:
        con.execute("""INSERT INTO subagent_runs VALUES
          (:run_id,:child_session_key,:controller_session_key,:requester_session_key,
           :created_at,:payload_json)""", s)
    con.commit()
    con.close()


def mk_executor(path: Path, nodes: list[dict], windows: list[dict],
                events: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE session_nodes (session_key TEXT, current_session_id TEXT,
      entry_json TEXT, entry_valid INTEGER, status TEXT)""")
    con.execute("""CREATE TABLE session_windows (session_id TEXT, session_key TEXT,
      previous_session_id TEXT, status TEXT, model TEXT, model_provider TEXT)""")
    con.execute("""CREATE TABLE trajectory_runtime_events (session_id TEXT, seq INTEGER,
      run_id TEXT, event_json TEXT, created_at INTEGER)""")
    for n in nodes:
        con.execute("INSERT INTO session_nodes VALUES (?,?,?,?,?)",
                    (n["session_key"], n["current_session_id"], n["entry_json"],
                     n["entry_valid"], n["status"]))
    for w in windows:
        con.execute("INSERT INTO session_windows VALUES (?,?,?,?,?,?)",
                    (w["session_id"], w["session_key"], w.get("previous_session_id"),
                     w["status"], w.get("model"), w.get("model_provider")))
    for i, (sid, rid, ej) in enumerate(events):
        con.execute("INSERT INTO trajectory_runtime_events VALUES (?,?,?,?,?)",
                    (sid, i + 1, rid, ej, 1700000000000 + i))
    con.commit()
    con.close()


def base_task(**kw: object) -> dict:
    d: dict = {"task_id": "t1", "runtime": "subagent", "task_kind": "exec",
               "requester_session_key": "req1", "owner_key": "o1", "scope_kind": "s1",
               "child_session_key": "child1", "agent_id": "ag1",
               "requester_agent_id": "rag1", "run_id": "r1", "label": "L1",
               "task": "do work", "status": "succeeded", "created_at": 1,
               "started_at": 2, "ended_at": 3, "tool_use_count": 5,
               "detail_json": json.dumps({"kind": "task_backing_instance",
                                          "runtime": "subagent", "generation": 1})}
    d.update(kw)
    return d


def base_sub(**kw: object) -> dict:
    d: dict = {"run_id": "r1", "child_session_key": "child1",
               "controller_session_key": "ctrl1", "requester_session_key": "req1",
               "created_at": 1, "payload_json": json.dumps(
                   {"runId": "r1", "taskRunId": "r1", "childSessionKey": "child1",
                    "controllerSessionKey": "ctrl1", "requesterSessionKey": "req1",
                    "requesterOrigin": "webchat", "requesterDisplayKey": "d",
                    "requesterAgentId": "rag1", "task": "do work"})}
    d.update(kw)
    return d


def entry_json(session_id: str, status: str = "done") -> str:
    return json.dumps({"sessionId": session_id, "status": status, "model": "m1",
                       "modelProvider": "p1", "inputTokens": 1, "outputTokens": 2,
                       "totalTokens": 999, "totalTokensFresh": True})


class Ctx:
    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wf89test_"))
        self.gdb = self.tmp / "global.sqlite"
        self.aroot = self.tmp / "agents"

    def run(self) -> dict:
        return read_task(global_db=self.gdb, agent_root=self.aroot)


class CreditReaderTests(unittest.TestCase):
    def test_creditable_full_binding(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "CREDITABLE")
        self.assertTrue(rec["verified"] and rec["creditable"])
        self.assertEqual(rec["usage"],
                         {"input": 100, "output": 50, "total": 150,
                          "cost_total": 0.01, "cacheRead": 10, "reasoningTokens": 20})

    def test_partial_missing_usage(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", None))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "PARTIAL")
        self.assertFalse(rec["creditable"])
        self.assertIsNone(rec["usage"])

    def test_task_runs_only_uncreditable(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "INCOMPLETE")
        self.assertFalse(rec["verified"] and rec["creditable"])

    def test_rekeyed_registry_run_id_joins_on_task_run_id(self) -> None:
        # Live 2026-09-24: re-announced runs carry a new subagent_runs.run_id;
        # payload.taskRunId still names the task run and must be the join key.
        c = Ctx()
        mk_global(c.gdb, [base_task()],
                  [base_sub(run_id="announce:requester-settle:child1:yield-1")])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", MIN_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "CREDITABLE")

    def test_duplicate_task_run_id_fails_closed(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()],
                  [base_sub(), base_sub(run_id="announce:dup")])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "MISMATCH")
        self.assertFalse(rec["creditable"])

    def test_unreadable_executor_store(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        # No executor DB created at all -> absent store.
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "UNREADABLE")

    def test_entry_valid_zero_unreadable(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 0, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "UNREADABLE")

    def test_window_entry_mismatch_blocks_credit(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1", status="failed"),
                      "entry_valid": 1, "status": "failed"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "MISMATCH")
        self.assertFalse(rec["creditable"])

    def test_multi_window_session_key_keying(self) -> None:
        """Same session_key, two windows; node points at w2; w1 usage must NOT leak in."""
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w2",
                      "entry_json": entry_json("w2"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"},
                     {"session_id": "w2", "session_key": "child1",
                      "previous_session_id": "w1", "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", FULL_USAGE)),
                     ("w2", "r1", completed_event("r1", "w2", MIN_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "CREDITABLE")
        self.assertEqual(rec["window_session_id"], "w2")
        self.assertEqual(rec["usage"],
                         {"input": 200, "output": 60, "total": 260, "cost_total": 0.02})
        self.assertEqual(rec["usage_events_outside_bound_window"], 1)

    def test_generations_reported_per_attempt_no_aggregation(self) -> None:
        """Two generations of the same logical task => two rows, each credited
        only from its own run_id/window; totals must NOT be merged."""
        c = Ctx()
        t1 = base_task(task_id="t1", run_id="r1", child_session_key="child1",
                       detail_json=json.dumps({"generation": 1}))
        t2 = base_task(task_id="t2", run_id="r2", child_session_key="child2",
                       detail_json=json.dumps({"generation": 2}))
        s1 = base_sub(run_id="r1", child_session_key="child1",
                      payload_json=json.dumps({"runId": "r1", "taskRunId": "r1",
                                               "childSessionKey": "child1",
                                               "requesterAgentId": "rag1"}))
        s2 = base_sub(run_id="r2", child_session_key="child2",
                      payload_json=json.dumps({"runId": "r2", "taskRunId": "r2",
                                               "childSessionKey": "child2",
                                               "requesterAgentId": "rag1"}))
        mk_global(c.gdb, [t1, t2], [s1, s2])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"},
                     {"session_key": "child2", "current_session_id": "w2",
                      "entry_json": entry_json("w2"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"},
                     {"session_id": "w2", "session_key": "child2",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", FULL_USAGE)),
                     ("w2", "r2", completed_event("r2", "w2", MIN_USAGE))])
        recs = {r["task_id"]: r for r in c.run()["records"]}
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs["t1"]["generation"], 1)
        self.assertEqual(recs["t2"]["generation"], 2)
        self.assertEqual(recs["t1"]["usage"]["input"], 100)
        self.assertEqual(recs["t2"]["usage"]["input"], 200)

    def test_unlabeled_observable_only(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task(label=None)], [base_sub()])
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "OBSERVABLE_ONLY")
        self.assertFalse(rec["creditable"])

    def full_executor(self, c: Ctx, events: list[tuple]) -> None:
        mk_executor(c.aroot / "ag1" / "agent" / "openclaw-agent.sqlite",
                    [{"session_key": "child1", "current_session_id": "w1",
                      "entry_json": entry_json("w1"), "entry_valid": 1, "status": "done"}],
                    [{"session_id": "w1", "session_key": "child1",
                      "previous_session_id": None, "status": "done",
                      "model": "m1", "model_provider": "p1"}],
                    events)

    def test_requester_agent_id_mismatch_blocks_credit(self) -> None:
        c = Ctx()
        payload = json.loads(base_sub()["payload_json"])
        payload["requesterAgentId"] = "someone-else"
        mk_global(c.gdb, [base_task()], [base_sub(payload_json=json.dumps(payload))])
        self.full_executor(c, [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "MISMATCH")
        self.assertIn("requester_agent_id", rec["reason"])

    def test_one_unusable_completed_event_makes_run_partial(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        self.full_executor(c, [("w1", "r1", completed_event("r1", "w1", FULL_USAGE, seq=1)),
                               ("w1", "r1", completed_event("r1", "w1", None, seq=2))])
        rec = c.run()["records"][0]
        self.assertEqual(rec["state"], "PARTIAL")
        self.assertFalse(rec["creditable"])
        self.assertIn("1 of 2", rec["reason"])

    def test_state_event_witness(self) -> None:
        cases = {
            "match": ([("r1", "CHILD1", "ag1", "run_completed")], "CREDITABLE"),
            "disagree": ([("r1", "child-other", "ag1", "run_completed")], "MISMATCH"),
            "absent": ([("r9", "child1", "ag1", "run_completed")], "CREDITABLE"),
        }
        for expected, (rows, state) in cases.items():
            c = Ctx()
            mk_global(c.gdb, [base_task()], [base_sub()])
            con = sqlite3.connect(c.gdb)
            con.execute("""CREATE TABLE session_state_events (run_id TEXT, session_key TEXT,
              agent_id TEXT, kind TEXT)""")
            con.executemany("INSERT INTO session_state_events VALUES (?,?,?,?)", rows)
            con.commit()
            con.close()
            self.full_executor(c, [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
            rec = c.run()["records"][0]
            self.assertEqual(rec["state_event_witness"], expected)
            self.assertEqual(rec["state"], state)
        c = Ctx()
        mk_global(c.gdb, [base_task()], [base_sub()])
        self.full_executor(c, [("w1", "r1", completed_event("r1", "w1", FULL_USAGE))])
        self.assertEqual(c.run()["records"][0]["state_event_witness"], "unavailable")

    def test_task_text_hash_known_answer_vector(self) -> None:
        self.assertEqual(task_text_hash("wf89 d2b known-answer vector"),
                         "ca72eff42b7768aa78afe86affe878953a0596756aa165f7ba97c978a0e2e6fe")

    def test_task_text_hash_stable(self) -> None:
        s = "do work"
        self.assertEqual(task_text_hash(s), task_text_hash(s))

    def test_task_text_hash_single_byte_differs(self) -> None:
        self.assertNotEqual(task_text_hash("do work"), task_text_hash("do worx"))

    def test_task_null_and_empty_yield_hash_uncomputable(self) -> None:
        c = Ctx()
        mk_global(c.gdb, [base_task(task_id="t_null", run_id="r_null", task=None),
                          base_task(task_id="t_empty", run_id="r_empty", task="")], [])
        recs = {r["task_id"]: r for r in c.run()["records"]}
        self.assertEqual(recs["t_null"]["task_text_sha256"], "hash_uncomputable")
        self.assertEqual(recs["t_empty"]["task_text_sha256"], "hash_uncomputable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
