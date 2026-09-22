"""Tests for the hidden-bank runner slice."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKTREE / "scripts"
RUNNER = SCRIPTS / "arena_hidden_bank_runner.py"
BANK = WORKTREE / "data" / "evals" / "model-arena" / "arena-agentic-v1-20260920"
PROMPT_DIRECTIVE = "Return only the required JSON object. No prose."


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_gen = _load("arena_agentic_expansion", SCRIPTS / "arena_agentic_expansion.py")
_runner = _load("arena_hidden_bank_runner", RUNNER)


def _bank_docs():
    _, visible, hidden = _gen.build_bank()
    isolation = _gen.build_isolation()
    return visible, hidden, isolation


def _write_json(path, doc):
    path.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")


def _run_cli(*cli_args, timeout=480):
    return subprocess.run(
        [sys.executable, str(RUNNER), *cli_args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class RunnerTests(unittest.TestCase):
    def test_isolation_allowlist_enforced(self):
        visible, hidden, isolation = _bank_docs()
        bad = copy.deepcopy(isolation)
        bad["candidate_mount_allowlist"] = ["candidate-visible-bank.json", "hidden-bank.json"]
        with self.assertRaises(SystemExit):
            _runner.check_isolation(bad)
        bad2 = copy.deepcopy(isolation)
        bad2["candidate_mount_allowlist"] = ["something-else.json"]
        with self.assertRaises(SystemExit):
            _runner.check_isolation(bad2)
        _runner.check_isolation(isolation)

    def test_mount_contains_only_visible_bank(self):
        visible, hidden, isolation = _bank_docs()
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            v, h, iso = tmpd / "v.json", tmpd / "h.json", tmpd / "i.json"
            _write_json(v, visible)
            _write_json(h, hidden)
            _write_json(iso, isolation)
            out = tmpd / "out"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--isolation", str(iso), "--out", str(out), "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            mount = out / "candidate-mount"
            self.assertTrue(mount.is_dir())
            self.assertEqual(sorted(p.name for p in mount.iterdir()),
                             ["candidate-visible-bank.json"])
            mounted = json.loads((mount / "candidate-visible-bank.json").read_text())
            self.assertEqual(mounted, visible)
            contract = json.loads((out / "control" / "run-contract.json").read_text())
            self.assertIn("visible_sha256", contract)
            self.assertIn("hidden_sha256", contract)
            self.assertIn("model", contract)
            self.assertIn("timestamp_utc", contract)

    def test_hidden_key_not_in_dry_run(self):
        visible, hidden, isolation = _bank_docs()
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            v, h, iso = tmpd / "v.json", tmpd / "h.json", tmpd / "i.json"
            _write_json(v, visible)
            _write_json(h, hidden)
            _write_json(iso, isolation)
            out = tmpd / "out"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--isolation", str(iso), "--out", str(out), "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            dry = json.loads((out / "dry-run.json").read_text())
            self.assertEqual(len(dry), 12)
            blob = json.dumps(dry, sort_keys=True)
            for token in ('"key"', '"structure_id"', '"family_trap"', '"expected_trace"'):
                self.assertNotIn(token, blob)
            for entry in dry:
                self.assertEqual(sorted(entry), ["family", "instance_id", "prompt"])
            for case in hidden["cases"]:
                key_blob = json.dumps(case["key"], sort_keys=True)
                self.assertNotIn(key_blob, blob)

    def test_exact_key_passes_mutated_fails(self):
        visible, hidden, _ = _bank_docs()
        vmap = {c["instance_id"]: c for c in visible["cases"]}
        hmap = {c["instance_id"]: c for c in hidden["cases"]}
        iid = sorted(vmap)[0]
        exact_text = json.dumps(hmap[iid]["key"], sort_keys=True)
        ok = _runner.grade_text(vmap[iid], hmap[iid], exact_text)
        self.assertTrue(ok["strict_pass"])
        self.assertTrue(ok["factual"])
        wrong = _gen._mutate_first_leaf(hmap[iid]["key"])
        wrong_text = json.dumps(wrong, sort_keys=True)
        bad = _runner.grade_text(vmap[iid], hmap[iid], wrong_text)
        self.assertFalse(bad["strict_pass"])
        self.assertFalse(bad["factual"])

    def test_malformed_json_fails(self):
        visible, hidden, _ = _bank_docs()
        vmap = {c["instance_id"]: c for c in visible["cases"]}
        hmap = {c["instance_id"]: c for c in hidden["cases"]}
        iid = sorted(vmap)[0]
        for malformed in ["not json", '{"a":1, "a":2}', "```json\n{\"a\":1}\n```", '{"a": 1} ']:
            res = _runner.grade_text(vmap[iid], hmap[iid], malformed)
            self.assertFalse(res["strict_pass"], malformed)

    def test_grade_file_missing_and_extra_ids_fail_closed(self):
        visible, hidden, isolation = _bank_docs()
        vmap = {c["instance_id"]: c for c in visible["cases"]}
        hmap = {c["instance_id"]: c for c in hidden["cases"]}
        full = {iid: json.dumps(hmap[iid]["key"], sort_keys=True) for iid in vmap}
        missing = dict(full)
        missing.pop(sorted(missing)[0])
        with self.assertRaises(SystemExit):
            _runner.run_grade(vmap, hmap, missing, "m")
        extra = dict(full)
        extra["extra-id"] = "{}"
        with self.assertRaises(SystemExit):
            _runner.run_grade(vmap, hmap, extra, "m")
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            v, h, iso, gf = (tmpd / "v.json", tmpd / "h.json",
                             tmpd / "i.json", tmpd / "responses.json")
            _write_json(v, visible)
            _write_json(h, hidden)
            _write_json(iso, isolation)
            _write_json(gf, full)
            out = tmpd / "out"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--isolation", str(iso), "--out", str(out),
                            "--grade-file", str(gf))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            graded = json.loads((out / "graded-results.json").read_text())
            self.assertEqual(graded["total"], 12)
            self.assertEqual(graded["strict_pass_count"], 12)


class DispatchPlanTests(unittest.TestCase):
    def _stage(self, tmpd):
        visible, hidden, isolation = _bank_docs()
        isolation = copy.deepcopy(isolation)
        isolation["candidate_mount_allowlist"] = [
            "candidate-visible-bank.json", "fixtures/"
        ]
        isolation["candidate_mount_denylist"] = sorted(
            set(isolation["candidate_mount_denylist"]) | {"harness-fixtures.json"}
        )
        v = tmpd / "v.json"
        h = tmpd / "h.json"
        iso = tmpd / "i.json"
        _write_json(v, visible)
        _write_json(h, hidden)
        _write_json(iso, isolation)
        fixtures = tmpd / "fixtures.json"
        _write_json(fixtures, _gen.build_harness_fixtures())
        overlay = tmpd / "overlay.json"
        overlay_version = "test-overlay-r1"
        _write_json(overlay, {
            "envelope": _runner.ENVELOPE_ID,
            "overlay_version": overlay_version,
            "hidden_bank_sha256": hashlib.sha256(h.read_bytes()).hexdigest(),
            "families": {
                family: {"contract_text": "Return the documented JSON object."}
                for family in sorted({c["family"] for c in visible["cases"]})
            },
        })
        auth = tmpd / "auth.json"
        _write_json(auth, {
            "envelope": _runner.ENVELOPE_ID,
            "dispatch_ready": True,
            "overlay_version": overlay_version,
            "authorized_by": "owner-test",
            "authorized_at": "2026-09-20T14:30:00-07:00",
            "scope": {
                "models": ["m", "spark-candidate"],
                "cases": 12,
                "reps": 1,
            },
        })
        self._auth = auth
        self._fixtures = fixtures
        self._overlay = overlay
        return visible, hidden, v, h, iso

    def test_dispatch_plan_creates_prompts_manifest_mount_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            visible, hidden, v, h, iso = self._stage(tmpd)
            out = tmpd / "out"
            model = "spark-candidate"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--isolation", str(iso), "--out", str(out),
                            "--model", model, "--dispatch-plan",
                            "--fixtures", str(self._fixtures),
                            "--overlay", str(self._overlay),
                            "--authorization", str(self._auth))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            mount = out / "candidate-mount"
            self.assertTrue(mount.is_dir())
            self.assertEqual(sorted(p.name for p in mount.iterdir()),
                             ["candidate-visible-bank.json", "fixtures"])
            mounted = json.loads((mount / "candidate-visible-bank.json").read_text())
            self.assertEqual(mounted, visible)
            contract = json.loads((out / "control" / "run-contract.json").read_text())
            self.assertEqual(contract["model"], model)
            self.assertEqual(contract["timeout_s"], 600)
            self.assertEqual(contract["retries"], 0)
            self.assertEqual(contract["thinking"], "high")
            self.assertIn("deadline_utc", contract)
            import datetime as _dt
            issued = _dt.datetime.fromisoformat(
                contract["timestamp_utc"].replace("Z", "+00:00"))
            deadline = _dt.datetime.fromisoformat(
                contract["deadline_utc"].replace("Z", "+00:00"))
            self.assertEqual((deadline - issued).total_seconds(), 600)
            self.assertEqual(
                contract["mount_allowlist"],
                ["candidate-visible-bank.json", "fixtures/"],
            )
            self.assertIn("visible_sha256", contract)
            self.assertIn("hidden_sha256", contract)
            vmap = {c["instance_id"]: c for c in visible["cases"]}
            self.assertEqual(len(vmap), 12)
            prompts = out / "prompts"
            self.assertTrue(prompts.is_dir())
            for iid in sorted(vmap):
                pj = prompts / ("case-%s.json" % iid)
                pt = prompts / ("case-%s.txt" % iid)
                self.assertTrue(pj.is_file(), iid)
                self.assertTrue(pt.is_file(), iid)
                doc = json.loads(pj.read_text())
                self.assertEqual(
                    sorted(doc),
                    ["family", "instance_id", "prompt", "response_contract"],
                )
                self.assertEqual(doc["instance_id"], iid)
                self.assertEqual(doc["prompt"], vmap[iid]["prompt"])
                txt = pt.read_text()
                self.assertIn(iid, txt)
                self.assertIn(PROMPT_DIRECTIVE, txt)
            plan = json.loads((out / "dispatch-plan.json").read_text())
            self.assertEqual(plan["schema"], "veritas.arena_dispatch_plan.v1")
            self.assertEqual(plan["model"], model)
            self.assertEqual(plan["timeout_s"], 600)
            self.assertEqual(plan["retries"], 0)
            self.assertEqual(plan["thinking"], "high")
            self.assertEqual(len(plan["cases"]), 12)
            self.assertIn("deadline_utc", plan)
            self.assertIn("spawn_rule", plan)
            self.assertEqual(plan["spawn_rule"]["runTimeoutSeconds"], 600)
            self.assertEqual(plan["spawn_rule"]["retries"], 0)
            self.assertEqual(
                plan["spawn_rule"]["on_timeout"], "record_empty_fail_closed")
            import datetime as _dt2
            issued = _dt2.datetime.fromisoformat(
                plan["timestamp_utc"].replace("Z", "+00:00"))
            deadline = _dt2.datetime.fromisoformat(
                plan["deadline_utc"].replace("Z", "+00:00"))
            self.assertEqual((deadline - issued).total_seconds(), 600)
            for entry in plan["cases"]:
                self.assertEqual(sorted(entry),
                                 ["deadline_utc", "family", "instance_id",
                                  "prompt_path", "prompt_txt_path", "timeout_s"])
                self.assertEqual(entry["timeout_s"], 600)
                self.assertEqual(entry["deadline_utc"], plan["deadline_utc"])
                self.assertTrue((out / entry["prompt_path"]).is_file())
                self.assertTrue((out / entry["prompt_txt_path"]).is_file())
            blob = json.dumps(plan, sort_keys=True)
            blob += "".join((prompts / ("case-%s.json" % iid)).read_text()
                            for iid in sorted(vmap))
            for token in ('"key"', '"structure_id"', '"family_trap"', '"expected_trace"'):
                self.assertNotIn(token, blob)
            for case in hidden["cases"]:
                key_blob = json.dumps(case["key"], sort_keys=True)
                self.assertNotIn(key_blob, blob)

    def test_dispatch_plan_missing_isolation_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            _, _, v, h, _ = self._stage(tmpd)
            out = tmpd / "out"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--out", str(out), "--model", "m", "--dispatch-plan")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("runner_fail_closed", proc.stderr)

    def test_dispatch_plan_requires_explicit_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            _, _, v, h, iso = self._stage(tmpd)
            out = tmpd / "out"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--isolation", str(iso), "--out", str(out),
                            "--fixtures", str(self._fixtures),
                            "--overlay", str(self._overlay),
                            "--dispatch-plan", "--authorization", str(self._auth))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("runner_fail_closed", proc.stderr)

    def test_dispatch_plan_requires_overlay_and_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            _, _, v, h, iso = self._stage(tmpd)
            base = ["--visible", str(v), "--hidden", str(h),
                    "--isolation", str(iso), "--out", str(tmpd / "out"),
                    "--model", "m", "--dispatch-plan",
                    "--authorization", str(self._auth)]
            missing_overlay = _run_cli(*base, "--fixtures", str(self._fixtures))
            self.assertNotEqual(missing_overlay.returncode, 0)
            self.assertIn("dispatch_plan_requires_overlay", missing_overlay.stderr)
            missing_fixtures = _run_cli(*base, "--overlay", str(self._overlay))
            self.assertNotEqual(missing_fixtures.returncode, 0)
            self.assertIn("dispatch_plan_requires_fixtures", missing_fixtures.stderr)

    def test_collect_grades_exact_pass(self):
        visible, hidden, isolation = _bank_docs()
        vmap = {c["instance_id"]: c for c in visible["cases"]}
        hmap = {c["instance_id"]: c for c in hidden["cases"]}
        full = {iid: json.dumps(hmap[iid]["key"], sort_keys=True) for iid in vmap}
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            v, h, iso, resp = (tmpd / "v.json", tmpd / "h.json",
                              tmpd / "i.json", tmpd / "resp.json")
            _write_json(v, visible)
            _write_json(h, hidden)
            _write_json(iso, isolation)
            _write_json(resp, full)
            out = tmpd / "out"
            proc = _run_cli("--visible", str(v), "--hidden", str(h),
                            "--isolation", str(iso), "--out", str(out),
                            "--model", "m", "--collect", "--responses", str(resp))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            graded = json.loads((out / "graded-results.json").read_text())
            self.assertEqual(graded["model"], "m")
            self.assertEqual(graded["total"], 12)
            self.assertEqual(graded["strict_pass_count"], 12)
            self.assertEqual(len(graded["results"]), 12)

    def test_collect_mutated_and_malformed_fail(self):
        visible, hidden, isolation = _bank_docs()
        vmap = {c["instance_id"]: c for c in visible["cases"]}
        hmap = {c["instance_id"]: c for c in hidden["cases"]}
        full = {iid: json.dumps(hmap[iid]["key"], sort_keys=True) for iid in vmap}
        first = sorted(full)[0]
        mutated = dict(full)
        mutated[first] = json.dumps(_gen._mutate_first_leaf(hmap[first]["key"]),
                                    sort_keys=True)
        malformed = dict(full)
        malformed[first] = "not json"
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            v, h, iso = tmpd / "v.json", tmpd / "h.json", tmpd / "i.json"
            _write_json(v, visible)
            _write_json(h, hidden)
            _write_json(iso, isolation)
            for name, mapping, expect_json_valid in (
                ("mut.json", mutated, True),
                ("mal.json", malformed, False),
            ):
                resp = tmpd / name
                _write_json(resp, mapping)
                out = tmpd / ("out-" + name)
                proc = _run_cli("--visible", str(v), "--hidden", str(h),
                                "--out", str(out),
                                "--collect", "--responses", str(resp))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                graded = json.loads((out / "graded-results.json").read_text())
                self.assertEqual(graded["total"], 12)
                self.assertEqual(graded["strict_pass_count"], 11)
                row = [r for r in graded["results"] if r["instance_id"] == first][0]
                self.assertFalse(row["strict_pass"])
                self.assertFalse(row["factual"])
                self.assertEqual(row["json_valid"], expect_json_valid)


class AuthorizationGateTests(unittest.TestCase):
    def test_dispatch_plan_refused_without_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            out = tmpd / "o"
            proc = _run_cli(
                "--visible", str(BANK / "candidate-visible-bank.json"),
                "--hidden", str(BANK / "hidden-bank.json"),
                "--isolation", str(BANK / "overlay" / "candidate-isolation.json"),
                "--fixtures", str(BANK / "harness-fixtures.json"),
                "--overlay", str(BANK / "overlay" / "key-shapes.json"),
                "--out", str(out), "--model", "m", "--dispatch-plan",
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("dispatch_plan_requires_authorization", proc.stderr)
            self.assertFalse(out.exists())

    def test_authorization_must_be_dispatch_ready(self):
        with self.assertRaises(SystemExit):
            _runner.check_authorization(
                {"envelope": _runner.ENVELOPE_ID, "dispatch_ready": False,
                 "overlay_version": None}, None)

    def test_authorization_overlay_version_must_match_active_overlay(self):
        with self.assertRaises(SystemExit):
            _runner.check_authorization(
                {"envelope": _runner.ENVELOPE_ID, "dispatch_ready": True,
                 "overlay_version": "stale-r0"},
                {"overlay_version": "live-r1"})
        _runner.check_authorization(
            {"envelope": _runner.ENVELOPE_ID, "dispatch_ready": True,
             "overlay_version": "live-r1", "authorized_by": "owner",
             "authorized_at": "2026-09-20T14:30:00-07:00",
             "scope": {"models": ["m"], "cases": 12, "reps": 1}},
            {"overlay_version": "live-r1"}, model="m", expected_cases=12)

    def test_authorization_binds_identity_time_model_cases_and_reps(self):
        overlay = {"overlay_version": "live-r1"}
        base = {
            "envelope": _runner.ENVELOPE_ID,
            "dispatch_ready": True,
            "overlay_version": "live-r1",
            "authorized_by": "owner",
            "authorized_at": "2026-09-20T14:30:00-07:00",
            "scope": {"models": ["m"], "cases": 12, "reps": 1},
        }
        for mutation in (
            {"authorized_by": None},
            {"authorized_at": "2026-09-20T14:30:00"},
            {"scope": {"models": [], "cases": 12, "reps": 1}},
            {"scope": {"models": ["other"], "cases": 12, "reps": 1}},
            {"scope": {"models": ["m"], "cases": 11, "reps": 1}},
            {"scope": {"models": ["m"], "cases": 12, "reps": 2}},
        ):
            auth = copy.deepcopy(base)
            auth.update(mutation)
            with self.assertRaises(SystemExit, msg=mutation):
                _runner.check_authorization(
                    auth, overlay, model="m", expected_cases=12
                )

    def test_overlay_rejected_when_built_against_a_different_bank(self):
        with self.assertRaises(SystemExit):
            _runner.check_overlay(
                {"envelope": _runner.ENVELOPE_ID,
                 "hidden_bank_sha256": "0" * 64,
                 "families": {"T1": {"contract_text": "x"}}},
                b"not-the-same-bank")


class FixturePathSafetyTests(unittest.TestCase):
    def test_traversal_and_absolute_paths_rejected(self):
        for bad in ("../escape.json", "/etc/passwd", "C:\\win.json",
                    "a/../../b.json", "", "."):
            with self.assertRaises(SystemExit, msg=bad):
                _runner.safe_fixture_relpath(bad)

    def test_nested_relative_path_accepted(self):
        self.assertEqual(
            _runner.safe_fixture_relpath("recovery/replica/payload-b.json").as_posix(),
            "recovery/replica/payload-b.json",
        )


class ContaminationTests(unittest.TestCase):
    def test_strict_pass_on_unmounted_fixture_case_is_conclusive(self):
        out = _runner.detect_contamination("{}", [], unanswerable=True, strict_pass=True)
        self.assertTrue(out["contaminated"])
        self.assertEqual(out["contamination_severity"], "conclusive")
        self.assertIn("strict_pass_on_unmounted_fixture_case", out["contamination_reasons"])

    def test_guessable_field_name_is_only_suspect(self):
        out = _runner.detect_contamination('{"rows": 1}', ["rows"])
        self.assertTrue(out["contaminated"])
        self.assertEqual(out["contamination_severity"], "suspect")

    def test_hidden_only_value_is_conclusive(self):
        out = _runner.detect_contamination(
            '{"ts": "2026-08-02"}', ["2026-08-02"])
        self.assertEqual(out["contamination_severity"], "conclusive")

    def test_clean_response_is_not_flagged(self):
        out = _runner.detect_contamination('{"alloc": []}', ["2026-08-02", "rows"])
        self.assertFalse(out["contaminated"])
        self.assertEqual(out["contamination_severity"], "none")

    def test_mounted_fixtures_make_fixture_values_legitimate(self):
        visible = {"prompt": {"fixture_set_id": "fs-1"}}
        hidden = {"key": {}}
        fixture_set = {"files": {"recovery/a.json": '{"value":"a5"}'},
                       "expected_trace": ["recovery/a.json"]}
        leaked = _runner.hidden_only_tokens(visible, hidden, fixture_set, "visible-only")
        self.assertIn("a5", leaked)
        exposed = _runner.hidden_only_tokens(visible, hidden, fixture_set, "with-fixtures")
        self.assertNotIn("a5", exposed)


class OperationalAndInventedSignalTests(unittest.TestCase):
    def test_empty_response_is_operational_timeout_not_factual(self):
        visible = {"prompt": {"request": "x"}, "family": "T6"}
        hidden = {"instance_id": "i1", "family": "T6", "key": {"a": 1}}
        out = _runner.grade_text(visible, hidden, "")
        self.assertFalse(out["strict_pass"])
        self.assertTrue(out["operational_timeout"])
        self.assertEqual(out["operational_outcome"], "timeout_empty")

    def test_answered_response_is_not_timeout(self):
        visible = {"prompt": {"request": "x"}, "family": "T6"}
        hidden = {"instance_id": "i1", "family": "T6", "key": {"a": 1}}
        out = _runner.grade_text(visible, hidden, '{"a": 1}')
        self.assertFalse(out["operational_timeout"])
        self.assertEqual(out["operational_outcome"], "answered")

    def test_invented_signal_never_changes_strict(self):
        visible = {"prompt": {"fixture_set_id": "fs-1"}, "family": "T4"}
        hidden = {"instance_id": "i1", "family": "T4",
                  "key": {"rows": [{"id": "r2", "value": "b1"}]}}
        fixture_set = {"files": {"recovery/primary.json": '{"id":"r2","value":"b1"}'}}
        good = _runner.grade_text(
            visible, hidden,
            '{"rows": [{"id": "r2", "value": "b1"}]}',
            fixture_set=fixture_set, exposure="with-fixtures")
        bad = _runner.grade_text(
            visible, hidden,
            '{"rows": [{"id": "r2", "value": "b9-fabricated"}]}',
            fixture_set=fixture_set, exposure="with-fixtures")
        self.assertFalse(good["invented_content_suspect"])
        self.assertTrue(bad["invented_content_suspect"])
        # Additive only: strict already false for the fabricated answer.
        self.assertFalse(bad["strict_pass"])

    def test_invented_detector_error_is_surfaced_not_swallowed(self):
        """A detector crash must be reported so the rescorer can fail closed.

        Silently returning suspect=False made an unusable detector look like a
        clean signal, and the rescorer then awarded dimensional credit.
        """
        original = _runner.strings_in

        def broken_strings_in(_node):
            raise RuntimeError("seeded invented-detector failure")

        _runner.strings_in = broken_strings_in
        try:
            out = _runner.detect_invented_content(
                '{"rows": []}', {"rows": []}, None, {"rows": []}, "T4"
            )
        finally:
            _runner.strings_in = original
        self.assertEqual(out["invented_detector_error"], "RuntimeError")
        self.assertFalse(out["invented_content_suspect"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
