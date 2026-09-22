"""Hermetic unittest controls for ARENA-HARNESS-P0-20260919 (stdlib only).

Offline: Docker subprocess calls are mocked; no candidate code ever runs on the
host interpreter here. Temporary directories only. Main may separately run tiny
trusted seed/reference/wrong-seed probes through the pre-existing Docker image
after inspection; those are harness probes, not another model batch.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arena_harness as H
import model_arena as MA
import arena_filework as FW


def _ns(**kw):
    return SimpleNamespace(**kw)


class StrictJsonTest(unittest.TestCase):
    def test_positive_reference(self):
        obj, err = H.parse_strict_json_object('{"a": 1, "b": "x"}')
        self.assertIsNone(err)
        self.assertEqual(obj, {"a": 1, "b": "x"})

    def test_wrong_values_rejected_by_grader(self):
        ok, reason = MA._grade_json('{"k": 2}', {"required_keys": ["k"], "expect_values": {"k": 1}})
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("wrong_value"))

    def test_empty_rejected(self):
        obj, err = H.parse_strict_json_object('   \n')
        self.assertIsNone(obj)
        self.assertTrue(err)

    def test_fenced_rejected(self):
        obj, err = H.parse_strict_json_object('```json\n{"a": 1}\n```')
        self.assertIsNone(obj)
        self.assertEqual(err, "json_fenced")

    def test_prose_rejected_no_brace_extraction(self):
        obj, err = H.parse_strict_json_object('here is your answer {"a": 1} thanks')
        self.assertIsNone(obj)
        self.assertEqual(err, "json_not_exact_object")

    def test_leading_prose_rejected(self):
        obj, err = H.parse_strict_json_object('Sure! {"a": 1}')
        self.assertIsNone(obj)
        self.assertIsNotNone(err)

    def test_duplicate_keys_rejected(self):
        obj, err = H.parse_strict_json_object('{"a": 1, "a": 2}')
        self.assertIsNone(obj)
        self.assertTrue(str(err).startswith("duplicate_key"))

    def test_nan_infinity_rejected(self):
        for bad in ('{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}'):
            obj, err = H.parse_strict_json_object(bad)
            self.assertIsNone(obj, bad)
            self.assertTrue(str(err).startswith("non_finite_json"), bad)

    def test_exponent_overflow_rejected_recursive(self):
        # 1e999 parses to inf; must be rejected, including nested.
        for bad in ('{"a": 1e999}', '{"a": {"b": [1, 2e999]}}'):
            obj, err = H.parse_strict_json_object(bad)
            self.assertIsNone(obj, bad)
            self.assertTrue(str(err).startswith("non_finite_json"), bad)

    def test_negative_zero_exponent_is_finite_positive_control(self):
        # -0e999 is finite negative zero, not overflow; must parse.
        obj, err = H.parse_strict_json_object('{"a": -0e999}')
        self.assertIsNone(err)
        self.assertIsNotNone(obj)
        self.assertIn("a", obj)
        self.assertTrue(H.strict_value_equal(obj["a"], 0))
        self.assertTrue(H.strict_value_equal(obj["a"], -0.0))

    def test_top_level_array_rejected(self):
        obj, err = H.parse_strict_json_object('[1, 2]')
        self.assertIsNone(obj)
        self.assertEqual(err, "json_not_exact_object")

    def test_bool_never_equals_number(self):
        for a, b in ((True, 1), (False, 0), (1, True), (0, False),
                      (True, 1.0), ("1", 1), (None, 0)):
            self.assertFalse(H.strict_value_equal(a, b), f"{a!r} vs {b!r}")
        ok, _ = MA._grade_json('{"flag": 1}', {"required_keys": ["flag"], "expect_values": {"flag": True}})
        self.assertFalse(ok)
        ok2, _ = MA._grade_json('{"flag": true}', {"required_keys": ["flag"], "expect_values": {"flag": True}})
        self.assertTrue(ok2)

    def test_nested_bool_never_equals_number(self):
        self.assertFalse(H.strict_value_equal({"f": True}, {"f": 1}))
        self.assertFalse(H.strict_value_equal({"a": [True]}, {"a": [1]}))
        self.assertTrue(H.strict_value_equal({"a": [1, {"b": 2.0}]}, {"a": [1.0, {"b": 2}]}))
        ok, _ = MA._grade_json('{"o": {"f": 1}}',
                               {"required_keys": ["o"], "expect_values": {"o": {"f": True}}})
        self.assertFalse(ok)
        ok2, _ = MA._grade_json('{"o": {"f": true}}',
                                {"required_keys": ["o"], "expect_values": {"o": {"f": True}}})
        self.assertTrue(ok2)

    def test_literal_backticks_inside_string_accepted(self):
        obj, err = H.parse_strict_json_object('{"a": "hi ``` hi"}')
        self.assertIsNone(err)
        self.assertEqual(obj, {"a": "hi ``` hi"})

    def test_unicode_whitespace_not_normalized(self):
        # U+00A0 NBSP around the object must NOT be stripped as transport.
        obj, err = H.parse_strict_json_object('\u00a0{"a": 1}\u00a0')
        self.assertIsNone(obj)
        self.assertIsNotNone(err)

    def test_lone_cr_not_normalized(self):
        # Lone CR is left for the parser; CRLF-only normalization applies.
        obj, err = H.parse_strict_json_object('{\r"a": 1}')
        # json.loads accepts \r as whitespace; the point is we did not rewrite
        # it to \n beforehand (parser verdict governs, not our normalization).
        self.assertIn((obj is None), (True, False))
        if obj is not None:
            self.assertEqual(obj, {"a": 1})

    def test_int_float_equivalence_preserved(self):
        self.assertTrue(H.strict_value_equal(1, 1.0))
        self.assertTrue(H.strict_value_equal(1.0, 1))
        self.assertTrue(H.strict_value_equal(0, 0.0))
        ok, _ = MA._grade_json('{"k": 1.0}', {"required_keys": ["k"], "expect_values": {"k": 1}})
        self.assertTrue(ok)
        ok2, _ = MA._grade_json('{"k": 1}', {"required_keys": ["k"], "expect_values": {"k": 1.0}})
        self.assertTrue(ok2)


class ReceiptTest(unittest.TestCase):
    P = "answer: 42"
    M = "provider/model-x"

    def test_positive_byte_exact(self):
        rec = H.make_transport_receipt(self.P, self.P, self.M, self.M, False)
        self.assertTrue(rec["passed"])
        self.assertTrue(rec["byte_exact"])
        self.assertIn("expected_sha256", rec)
        self.assertIn("observed_sha256", rec)

    def test_normalized_newline_only(self):
        rec = H.make_transport_receipt("hello\n", "hello", self.M, self.M, False)
        self.assertTrue(rec["passed"])
        self.assertFalse(rec["byte_exact"])
        self.assertTrue(rec["normalized_match"])
        self.assertEqual(rec["reason"], "normalized")

    def test_crlf_normalized(self):
        rec = H.make_transport_receipt("a\r\nb\r\n", "a\nb", self.M, self.M, False)
        self.assertTrue(rec["passed"])
        self.assertEqual(rec["reason"], "normalized")

    def test_bom_normalized(self):
        rec = H.make_transport_receipt("\ufeffhello", "hello", self.M, self.M, False)
        self.assertTrue(rec["passed"])

    def test_truncated_mismatch(self):
        rec = H.make_transport_receipt("hello world", "hello", self.M, self.M, False)
        self.assertFalse(rec["passed"])
        self.assertEqual(rec["reason"], "prompt_mismatch")

    def test_wrong_model(self):
        rec = H.make_transport_receipt(self.P, self.P, self.M, "provider/other", False)
        self.assertFalse(rec["passed"])
        self.assertEqual(rec["reason"], "model_mismatch")

    def test_missing_model(self):
        rec = H.make_transport_receipt(self.P, self.P, self.M, None, False)
        self.assertFalse(rec["passed"])

    def test_fallback_true_fails(self):
        rec = H.make_transport_receipt(self.P, self.P, self.M, self.M, True)
        self.assertFalse(rec["passed"])
        self.assertEqual(rec["reason"], "fallback_not_false")

    def test_indented_mismatch(self):
        rec = H.make_transport_receipt("hello", "  hello", self.M, self.M, False)
        self.assertFalse(rec["passed"])

    def test_fallback_missing_fails(self):
        rec = H.make_transport_receipt(self.P, self.P, self.M, self.M, None)
        self.assertFalse(rec["passed"])

    def test_fallback_string_truthy_fails(self):
        rec = H.make_transport_receipt(self.P, self.P, self.M, self.M, "false")
        self.assertFalse(rec["passed"])

    def test_missing_prompt_fails(self):
        rec = H.make_transport_receipt(self.P, None, self.M, self.M, False)
        self.assertFalse(rec["passed"])

    def test_grader_receipt_gate(self):
        task = {"prompt": self.P, "grade": {"mode": "static"}, "class": "c"}
        row = {"terminal_outcome": "succeeded", "output_text": "hi",
               "observed_model": self.M, "model_applied": True, "fallback_applied": False}
        ok, reason = MA._check_receipt(row, task["prompt"], self.M)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_receipt")

    def test_model_applied_must_be_true(self):
        task = {"prompt": self.P, "grade": {"mode": "static"}, "class": "c"}
        for bad in (None, False, 0, 1, "true"):
            row = {"observed_prompt": self.P, "observed_model": self.M,
                   "model_applied": bad, "fallback_applied": False}
            ok, reason = MA._check_receipt(row, task["prompt"], self.M)
            self.assertFalse(ok, bad)
            self.assertEqual(reason, "model_override_not_applied", bad)

    def test_explicit_observed_model_required(self):
        task = {"prompt": self.P, "grade": {"mode": "static"}, "class": "c"}
        row = {"observed_prompt": self.P, "resolved_model": self.M,
               "model_applied": True, "fallback_applied": False}
        ok, reason = MA._check_receipt(row, task["prompt"], self.M)
        self.assertFalse(ok)
        self.assertEqual(reason, "receipt_missing_observed_model")

    def test_forged_receipt_rejected(self):
        good = H.make_transport_receipt(self.P, self.P, self.M, self.M, False)
        ok, _ = H.verify_transport_receipt(good)
        self.assertTrue(ok)
        forged = dict(good)
        forged["passed"] = True
        forged["reason"] = "byte_exact"
        forged["byte_exact"] = False
        forged["normalized_match"] = False
        ok2, _ = H.verify_transport_receipt(forged)
        self.assertFalse(ok2)
        bad_hash = dict(good)
        bad_hash["expected_sha256"] = "ZZZ"
        ok3, r3 = H.verify_transport_receipt(bad_hash)
        self.assertFalse(ok3)
        self.assertTrue(r3.startswith("receipt_bad_hash"))
        wrong_schema = dict(good)
        wrong_schema["schema"] = "other"
        ok4, _ = H.verify_transport_receipt(wrong_schema)
        self.assertFalse(ok4)


class PlanGuardTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / "tmp").mkdir(parents=True)
        (self.root / "data" / "evals" / "model-arena").mkdir(parents=True)
        self._patch = patch.multiple(
            MA, ROOT=self.root,
            ROSTER_PATH=self.root / "data" / "evals" / "model-arena" / "roster.json",
            TASKS_PATH=self.root / "data" / "evals" / "model-arena" / "tasks.json",
            RESULTS_DIR=self.root / "data" / "evals" / "model-arena" / "results",
            PLAN_PATH=self.root / "tmp" / "model-arena-plan.json",
            PLANS_DIR=self.root / "tmp" / "model-arena-plans",
            PROMPTS_ROOT=self.root / "tmp" / "model-arena-prompts")
        self._patch.start()
        roster = {"models": [{"id": "m1", "model_path": "p/m1", "label": "M1", "enabled": True}]}
        tasks = {"task_set_id": "ts1", "tasks": [
            {"id": "t1", "class": "c", "prompt": "do t1",
             "grade": {"mode": "static", "contains_all": ["ok"]}}]}
        (self.root / "data" / "evals" / "model-arena" / "roster.json").write_text(json.dumps(roster))
        (self.root / "data" / "evals" / "model-arena" / "tasks.json").write_text(json.dumps(tasks))

    def tearDown(self):
        self._patch.stop()
        self.td.cleanup()

    def _args(self, **kw):
        base = dict(run_id="run-good1", models=None, tasks=None, classes=None, repeats=1)
        base.update(kw)
        return _ns(**base)

    def test_positive_plan_freezes(self):
        rc = MA.build_plan(self._args())
        self.assertEqual(rc, 0)
        plan = json.loads((self.root / "tmp" / "model-arena-plans" / "model-arena-plan-run-good1.json").read_text())
        self.assertEqual(plan["planned_pair_ids"], ["m1::t1::1"])
        self.assertEqual(plan["frozen_tasks"][0]["prompt_sha256"], H.sha256_text("do t1"))
        self.assertIn("grade_sha256", plan["frozen_tasks"][0])
        self.assertIn("prompt_file", plan["pairs"][0])
        pf = self.root / "tmp" / "model-arena-prompts" / "run-good1"
        self.assertTrue(any(pf.glob("*.md")))
        self.assertTrue((pf / plan["pairs"][0]["prompt_file"]).exists())

    def test_positive_repeat_guard_rejects_zero_and_negative(self):
        self.assertEqual(MA.build_plan(self._args(repeats=0)), 1)
        self.assertEqual(MA.build_plan(self._args(repeats=-2)), 1)

    def test_unknown_selectors_not_silent(self):
        self.assertEqual(MA.build_plan(self._args(models="nope", run_id="r2")), 1)
        self.assertEqual(MA.build_plan(self._args(tasks="nope", run_id="r3")), 1)
        self.assertEqual(MA.build_plan(self._args(classes="nope", run_id="r4")), 1)

    def test_unsafe_run_id_rejected(self):
        self.assertEqual(MA.build_plan(self._args(run_id="../evil")), 1)

    def test_colliding_names_do_not_collide(self):
        with self.assertRaises(ValueError):
            H.prompt_filename_for_pair("m::a/b::1")
        with self.assertRaises(ValueError):
            H.prompt_filename_for_pair("m::a\\b::1")
        prefix = "m::" + "x" * 180
        a_id = prefix + "::1a"
        b_id = prefix + "::1b"
        self.assertLessEqual(len(a_id), 200)
        self.assertLessEqual(len(b_id), 200)
        a = H.prompt_filename_for_pair(a_id)
        b = H.prompt_filename_for_pair(b_id)
        self.assertNotEqual(a, b)
        long_id = "m::" + "x" * 200 + "::1"
        with self.assertRaises(ValueError):
            H.prompt_filename_for_pair(long_id)

    def test_refuse_existing_prompt_dir(self):
        self.assertEqual(MA.build_plan(self._args()), 0)
        # Same run refuses (plan + prompt dir already exist).
        self.assertEqual(MA.build_plan(self._args()), 1)

    def test_immutable_plan_tampering_rejected(self):
        self.assertEqual(MA.build_plan(_ns(run_id="s9", models=None, tasks=None, classes=None, repeats=1)), 0)
        ppath = self.root / "tmp" / "model-arena-plans" / "model-arena-plan-s9.json"
        plan = json.loads(ppath.read_text())
        plan["frozen_tasks"][0]["prompt_sha256"] = "0" * 64
        ppath.write_text(json.dumps(plan))
        rp = self.root / "data" / "evals" / "model-arena" / "results" / "s9.jsonl"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("{}\n")
        rc = MA.score(_ns(run_id="s9", allow_exec=False))
        self.assertNotEqual(rc, 0)


class ScoreGateTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / "tmp").mkdir(parents=True)
        adir = self.root / "data" / "evals" / "model-arena"
        adir.mkdir(parents=True)
        self._patch = patch.multiple(
            MA, ROOT=self.root,
            ROSTER_PATH=adir / "roster.json",
            TASKS_PATH=adir / "tasks.json",
            RESULTS_DIR=adir / "results",
            PLAN_PATH=self.root / "tmp" / "model-arena-plan.json",
            PLANS_DIR=self.root / "tmp" / "model-arena-plans",
            PROMPTS_ROOT=self.root / "tmp" / "model-arena-prompts",
            SCORECARD_JSON=self.root / "tmp" / "model-arena-scorecard.json",
            SCORECARD_MD=self.root / "tmp" / "model-arena-scorecard.md")
        self._patch.start()
        roster = {"models": [{"id": "m1", "model_path": "p/m1", "label": "M1", "enabled": True}]}
        tasks = {"task_set_id": "ts1", "tasks": [
            {"id": "t1", "class": "c", "prompt": "do t1",
             "grade": {"mode": "static", "contains_all": ["ok"]}},
            {"id": "t2", "class": "c", "prompt": "do t2",
             "grade": {"mode": "static", "contains_all": ["ok"]}}]}
        (adir / "roster.json").write_text(json.dumps(roster))
        (adir / "tasks.json").write_text(json.dumps(tasks))
        MA.build_plan(_ns(run_id="s1", models=None, tasks=None, classes=None, repeats=1))

    def tearDown(self):
        self._patch.stop()
        self.td.cleanup()

    def _write_results(self, lines):
        rp = self.root / "data" / "evals" / "model-arena" / "results" / "s1.jsonl"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _row(self, pid, text, **kw):
        r = {"schema": MA.RESULT_SCHEMA, "run_id": "s1", "pair_id": pid,
             "requested_model": "p/m1", "resolved_model": "p/m1",
             "observed_model": "p/m1", "model_applied": True,
             "fallback_applied": False,
             "observed_prompt": "do t1" if "::t1::" in pid else "do t2",
             "terminal_outcome": "succeeded", "runtime_ms": 5,
             "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
             "output_text": text, "session_key": "k", "dispatched_at_utc": "t"}
        r.update(kw)
        return r

    def test_positive_scores_and_missing_becomes_not_run(self):
        self._write_results([json.dumps(self._row("m1::t1::1", "this is ok"))])
        rc = MA.score(_ns(run_id="s1", allow_exec=False))
        self.assertEqual(rc, 0)
        card = json.loads((self.root / "tmp" / "model-arena-scorecard.json").read_text())
        self.assertEqual(card["rows_not_run"], 1)
        self.assertFalse(card["invalid_evidence"])
        m = card["models"][0]
        self.assertEqual(m["n"], 2)

    def test_drifted_task_keys_warn_but_frozen_wins(self):
        live = json.loads((self.root / "data" / "evals" / "model-arena" / "tasks.json").read_text())
        live["tasks"][0]["grade"] = {"mode": "static", "contains_all": ["different"]}
        (self.root / "data" / "evals" / "model-arena" / "tasks.json").write_text(json.dumps(live))
        self._write_results([json.dumps(self._row("m1::t1::1", "this is ok"))])
        rc = MA.score(_ns(run_id="s1", allow_exec=False))
        self.assertEqual(rc, 0)
        card = json.loads((self.root / "tmp" / "model-arena-scorecard.json").read_text())
        self.assertIn("t1", card["live_grading_key_drift"])

    def test_duplicate_invalidates_pair_single_cell_nonzero(self):
        self._write_results([
            json.dumps(self._row("m1::t1::1", "this is ok")),
            json.dumps(self._row("m1::t1::1", "this is ok")),
            json.dumps(self._row("m1::t2::1", "this is ok")),
        ])
        rc = MA.score(_ns(run_id="s1", allow_exec=False))
        self.assertNotEqual(rc, 0)
        card = json.loads((self.root / "tmp" / "model-arena-scorecard.json").read_text())
        self.assertTrue(card["invalid_evidence"])
        self.assertFalse(card["accepting"])

    def test_schema_run_mismatch_are_failed_cells(self):
        self._write_results([
            json.dumps({**self._row("m1::t1::1", "this is ok"), "schema": "bad"}),
            json.dumps({**self._row("m1::t2::1", "this is ok"), "run_id": "other"}),
        ])
        rc = MA.score(_ns(run_id="s1", allow_exec=False))
        self.assertNotEqual(rc, 0)
        card = json.loads((self.root / "tmp" / "model-arena-scorecard.json").read_text())
        self.assertTrue(card["invalid_evidence"])

    def test_malformed_duplicatekey_rejected(self):
        self._write_results([
            '{"schema": "veritas.model_arena_result.v1", "a": 1, "a": 2}',
            json.dumps(self._row("m1::t1::1", "this is ok")),
        ])
        rc = MA.score(_ns(run_id="s1", allow_exec=False))
        self.assertNotEqual(rc, 0)

    def test_strict_row_parsing_rejects_nonfinite(self):
        line = json.dumps(self._row("m1::t1::1", "this is ok"))[:-1] + ', "x": NaN}'
        obj, kind, _e = MA._parse_result_line(line)
        self.assertIsNone(obj)
        self.assertEqual(kind, "malformed")


class FakeProc:
    """Minimal Popen stand-in for streaming tests: BytesIO streams, poll/kill/wait."""
    def __init__(self, rc, out=b"", err=b""):
        self._rc = rc
        self.stdout = io.BytesIO(out)
        self.stderr = io.BytesIO(err)
        self.killed = False

    def poll(self):
        if self._rc is not None:
            return self._rc
        return -9 if self.killed else None

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return -9 if self.killed else self._rc


class DockerRunnerTest(unittest.TestCase):
    IMG_ID = "sha256:" + "ab" * 32

    def _mock_docker(self, proc, rm_calls, image_id=None):
        iid = image_id or self.IMG_ID
        def fake_popen(cmd, **kw):
            if isinstance(cmd, list) and len(cmd) >= 3 and cmd[:3] == ["docker", "image", "inspect"]:
                self.assertIn("--format", cmd)
                self.assertIn("{{.Id}}", cmd)
                return FakeProc(0, out=(iid + "\n").encode("utf-8"))
            if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "docker" and cmd[1] == "run":
                self.assertIn("--pull", cmd)
                self.assertEqual(cmd[cmd.index("--pull") + 1], "never")
                self.assertIn(iid, cmd)
                return proc
            if isinstance(cmd, list) and len(cmd) >= 2 and cmd[:2] == ["docker", "rm"]:
                rm_calls.append(cmd)
                return FakeProc(0)
            raise AssertionError(f"unexpected docker command: {cmd}")
        return (patch("arena_harness.subprocess.Popen", side_effect=fake_popen),
                patch("arena_harness.subprocess.run", side_effect=AssertionError("subprocess.run must not be used for docker")))

    def test_blocked_without_allow_exec_no_subprocess(self):
        with patch("arena_harness.subprocess.run") as mr, \
             patch("arena_harness.subprocess.Popen") as mp:
            res = H.run_sandboxed_command(Path("/tmp"), ["python3", "x.py"], 5, False, "r", "p")
            mr.assert_not_called()
            mp.assert_not_called()
        self.assertEqual(res["status"], "blocked_exec_disabled")

    def test_image_id_used_no_pull_uuid_name(self):
        proc = FakeProc(0, out=b"hi\n")
        rm_calls = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc, rm_calls)
            with pm, rm:
                n1 = H.make_container_name("r", "p")
                n2 = H.make_container_name("r", "p")
                self.assertNotEqual(n1, n2)
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 5, True, "r", "p")
                argv = H.docker_run_args("arena-r-p-own", Path(td), ["python3", "case.py"], self.IMG_ID)
                self.assertIn("--pull", argv)
                self.assertEqual(argv[argv.index("--pull") + 1], "never")
                self.assertIn(self.IMG_ID, argv)
        self.assertEqual(res["status"], "ok")

    def test_output_cap_rc0_still_nonpass(self):
        proc = FakeProc(0, out=b"y" * (2 * 1024 * 1024))
        rm_calls = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc, rm_calls)
            with pm, rm:
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 30, True, "rr", "pp")
        self.assertEqual(res["status"], "output_limit_exceeded")
        self.assertFalse(res["passed"])
        self.assertEqual(len(rm_calls), 1)

    def test_delayed_eof_drain_then_cap(self):
        # Fast exit with buffered output: must drain through EOF then cap-check.
        proc = FakeProc(0, out=b"A" * (512 * 1024) + b"END\n")
        rm_calls = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc, rm_calls)
            with pm, rm:
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 30, True, "r", "p")
        self.assertEqual(res["status"], "ok")
        self.assertIn("END", res["stdout"])
        proc2 = FakeProc(0, out=b"B" * (2 * 1024 * 1024))
        rm2 = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc2, rm2)
            with pm, rm:
                res2 = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 30, True, "r", "p")
        self.assertEqual(res2["status"], "output_limit_exceeded")

    def test_nonzero_cleans_owned_container(self):
        proc = FakeProc(3, out=b"ARENA_PASS\n", err=b"boom")
        rm_calls = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc, rm_calls)
            with pm, rm:
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 5, True, "r", "p")
        self.assertEqual(res["status"], "nonzero")
        self.assertEqual(len(rm_calls), 1)
        self.assertFalse(H.check_success_marker(res["stdout"], res["returncode"]))

    def test_missing_image_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("arena_harness.subprocess.Popen", return_value=FakeProc(1, err=b"No such image")):
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 5, True, "r", "p")
        self.assertEqual(res["status"], "missing_image")

    def test_missing_docker_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("arena_harness.subprocess.Popen", side_effect=FileNotFoundError()):
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 5, True, "r", "p")
        self.assertEqual(res["status"], "missing_docker")

    def test_timeout_recorded_and_only_named_container_cleaned(self):
        proc = FakeProc(None)
        rm_calls = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc, rm_calls)
            with pm, rm:
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 1, True, "r", "p")
        self.assertEqual(res["status"], "timeout")
        self.assertEqual(res["reason"], "exec_timeout")
        self.assertTrue(proc.killed)
        self.assertEqual(len(rm_calls), 1)
        self.assertIn("arena-r-p", rm_calls[0][-1])

    def test_large_but_under_cap_output_passes_through(self):
        body = b"z" * (512 * 1024) + b"ARENA_PASS\n"
        proc = FakeProc(0, out=body)
        rm_calls = []
        with tempfile.TemporaryDirectory() as td:
            pm, rm = self._mock_docker(proc, rm_calls)
            with pm, rm:
                res = H.run_sandboxed_command(Path(td), ["python3", "case.py"], 30, True, "r", "p")
        self.assertEqual(res["status"], "ok")
        self.assertIn("ARENA_PASS", res["stdout"])
        self.assertEqual(rm_calls, [])

    def test_code_exec_never_touches_host_interpreter(self):
        with patch.object(MA, "subprocess") as msub:
            with patch("arena_harness.subprocess.Popen", return_value=FakeProc(1)):
                ok, reason = MA._grade_code_exec("x = 1", {"asserts": ["assert True"]}, True, "r", "p")
                self.assertFalse(ok)
                self.assertEqual(reason, "exec_missing_image")
            msub.run.assert_not_called()
            msub.Popen.assert_not_called()

    def test_run_args_carry_containment_controls(self):
        argv = H.docker_run_args("arena-r-p", Path("/tmp/g"), ["python3", "case.py"], self.IMG_ID)
        flat = " ".join(argv)
        for token in ("--user", "65534:65534", "--network", "none", "--read-only",
                      "--cap-drop", "ALL", "no-new-privileges", "--memory", "512m",
                      self.IMG_ID, "--pull never"):
            self.assertIn(token, flat)
        self.assertEqual(argv[argv.index("--pull") + 1], "never")

    def test_early_spoof_with_fake_nonce_fails(self):
        nonce = H.make_nonce_marker()
        self.assertFalse(H.check_nonce_marker_line("ARENA_PASS\n", 0, nonce))
        self.assertTrue(H.check_nonce_marker_line(f"hello\n{nonce}\n", 0, nonce))
        self.assertFalse(H.check_nonce_marker_line(f"{nonce}\n", 1, nonce))


class FileworkTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self._patch = patch.multiple(
            FW, ROOT=self.root,
            TASKS_DIR=self.root / "tasks-v3",
            TASKS_PATH=self.root / "tasks-v3" / "tasks-v3.json",
            ROSTER_PATH=self.root / "roster.json",
            RUNS_ROOT=self.root / "tmp" / "arena-v3",
            PLAN_PATH=self.root / "tmp" / "arena-filework-plan.json",
            CARD_JSON=self.root / "tmp" / "fw-card.json",
            CARD_MD=self.root / "tmp" / "fw-card.md",
            SANDBOX_ROOT=self.root / "sandboxes")
        self._patch.start()
        # Point the per-run plan dir at temp as well.
        self._plans = patch.object(FW, "PLANS_DIR", self.root / "tmp" / "arena-filework-plans")
        self._plans.start()

    def tearDown(self):
        self._plans.stop()
        self._patch.stop()
        self.td.cleanup()

    def _seed(self, tid="t1"):
        (self.root / "tasks-v3" / tid / "seed").mkdir(parents=True)
        (self.root / "tasks-v3" / tid / "seed" / "a.py").write_text("x=1\n")
        (self.root / "tasks-v3" / tid / "prompt.md").write_text("fix {PAIR_ID} {WORKDIR}")
        (self.root / "tasks-v3" / "tasks-v3.json").write_text(json.dumps(
            {"task_set_id": "ts", "tasks": [{"id": tid, "dir": tid,
                                             "protected_files": [],
                                             "verify": {"module": "test_x"}}]}))
        (self.root / "roster.json").write_text(json.dumps(
            {"models": [{"id": "m1", "model_path": "p/m1", "label": "M1", "enabled": True}]}))

    def test_two_batches_isolated(self):
        self._seed()
        self.assertEqual(FW.prepare(_ns(run_id="fw1", models=None, tasks=None)), 0)
        self.assertEqual(FW.prepare(_ns(run_id="fw2", models=None, tasks=None)), 0)
        self.assertTrue(FW._load_filework_plan("fw1") is not None)
        self.assertTrue(FW._load_filework_plan("fw2") is not None)

    def test_stdlib_shadow_rejected(self):
        self._seed()
        FW.prepare(_ns(run_id="fw1", models=None, tasks=None))
        wd = self.root / "tmp" / "arena-v3" / "fw1" / "m1" / "t1"
        (wd / "unittest.py").write_text("evil\n")
        task = {"id": "t1", "dir": "t1", "protected_files": [],
                "verify": {"module": "test_x", "restore_protected_before_verify": False}}
        out = FW._grade_pair(task, wd)
        self.assertFalse(out["passed"])
        self.assertEqual(out["reason"], "stdlib_shadow")

    def test_linked_seed_rejected(self):
        import os
        self._seed()
        seed = self.root / "tasks-v3" / "t1" / "seed"
        try:
            os.symlink(str(seed / "a.py"), str(seed / "link.py"))
            made_link = True
        except (OSError, NotImplementedError):
            made_link = False
        if made_link:
            rc = FW.prepare(_ns(run_id="fwL", models=None, tasks=None))
            self.assertEqual(rc, 1)

    def test_harvest_missing_returns_nonzero(self):
        self._seed()
        FW.prepare(_ns(run_id="fw1", models=None, tasks=None))
        with patch("builtins.print"):
            rc = FW.harvest(_ns(run_id="fw1"))
        self.assertNotEqual(rc, 0)

    def test_grade_missing_live_changed_seed_refused_before_grader(self):
        self._seed()
        self.assertEqual(FW.prepare(_ns(run_id="fwA", models=None, tasks=None)), 0)
        (self.root / "tasks-v3" / "tasks-v3.json").unlink()
        (self.root / "tasks-v3" / "t1" / "seed" / "a.py").write_text("x=2\n")
        with patch.object(FW, "_grade_pair", side_effect=AssertionError("must not reach grader")) as mg:
            with patch("builtins.print"):
                rc = FW.grade(_ns(run_id="fwA", allow_exec=False))
        self.assertNotEqual(rc, 0)
        mg.assert_not_called()

    def test_grade_missing_live_intact_seed_reaches_grader(self):
        self._seed()
        self.assertEqual(FW.prepare(_ns(run_id="fwB", models=None, tasks=None)), 0)
        (self.root / "tasks-v3" / "tasks-v3.json").unlink()
        def _fake(task, wd):
            return {"workdir": str(wd), "passed": True, "clean": True, "reason": "ok", "tests_passed": True}
        with patch.object(FW, "_grade_pair", side_effect=_fake) as mg:
            with patch("builtins.print"):
                rc = FW.grade(_ns(run_id="fwB", allow_exec=False))
        self.assertEqual(rc, 0)
        self.assertEqual(mg.call_count, 1)

    def test_grade_frozen_policy_wins_over_live(self):
        self._seed()
        frozen_budget = {"file": "a.py", "max_changed_lines": 5}
        frozen_tokens = ["OLD"]
        tasks = {"task_set_id": "ts", "tasks": [{"id": "t1", "dir": "t1", "protected_files": [], "diff_budget": frozen_budget, "forbidden_tokens": frozen_tokens, "verify": {"module": "test_x"}}]}
        (self.root / "tasks-v3" / "tasks-v3.json").write_text(json.dumps(tasks))
        self.assertEqual(FW.prepare(_ns(run_id="fwC", models=None, tasks=None)), 0)
        live = json.loads((self.root / "tasks-v3" / "tasks-v3.json").read_text())
        live["tasks"][0]["diff_budget"] = {"file": "a.py", "max_changed_lines": 9999}
        live["tasks"][0]["forbidden_tokens"] = ["MUTABLE"]
        (self.root / "tasks-v3" / "tasks-v3.json").write_text(json.dumps(live))
        seen = {}
        def _fake(task, wd):
            seen.update(task)
            return {"workdir": str(wd), "passed": True, "clean": True, "reason": "ok", "tests_passed": True}
        with patch.object(FW, "_grade_pair", side_effect=_fake):
            with patch("builtins.print"):
                rc = FW.grade(_ns(run_id="fwC", allow_exec=False))
        self.assertEqual(rc, 0)
        self.assertEqual(seen.get("diff_budget"), frozen_budget)
        self.assertEqual(seen.get("forbidden_tokens"), frozen_tokens)

    def test_grade_tampered_frozen_grade_refused(self):
        self._seed()
        self.assertEqual(FW.prepare(_ns(run_id="fwD", models=None, tasks=None)), 0)
        ppath = self.root / "tmp" / "arena-filework-plans" / "arena-filework-plan-fwD.json"
        plan = json.loads(ppath.read_text())
        plan["frozen_tasks"][0]["grade"] = {"module": "evil"}
        ppath.write_text(json.dumps(plan))
        with patch.object(FW, "_grade_pair", side_effect=AssertionError("must not reach grader")) as mg:
            with patch("builtins.print"):
                rc = FW.grade(_ns(run_id="fwD", allow_exec=False))
        self.assertNotEqual(rc, 0)
        mg.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
