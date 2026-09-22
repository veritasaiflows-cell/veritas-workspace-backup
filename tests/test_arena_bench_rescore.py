"""Tests for the trap-gated dimensional rescorer."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKTREE / "scripts"
BANK = WORKTREE / "data" / "evals" / "model-arena" / "arena-agentic-v1-20260920"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_rescore = _load("arena_bench_rescore", SCRIPTS / "arena_bench_rescore.py")

_HIDDEN = json.loads((BANK / "hidden-bank.json").read_text(encoding="utf-8"))
_VISIBLE = json.loads((BANK / "candidate-visible-bank.json").read_text(encoding="utf-8"))
_HMAP = {c["instance_id"]: c for c in _HIDDEN["cases"]}
_VMAP = {c["instance_id"]: c for c in _VISIBLE["cases"]}


def _case(structure_id):
    for iid, case in _HMAP.items():
        if case["structure_id"] == structure_id:
            return _VMAP[iid], case
    raise AssertionError(f"no case with structure_id {structure_id}")


def _score(structure_id, response_text):
    visible, hidden = _case(structure_id)
    return _rescore.score_case(visible, hidden, response_text, None, "visible-only")


class TrapGatingTests(unittest.TestCase):
    def test_exact_answer_scores_one_and_passes_strict(self):
        _, hidden = _case("p4-release-cascade")
        result = _score("p4-release-cascade", json.dumps(hidden["key"]))
        self.assertTrue(result["strict_pass"])
        self.assertTrue(result["shape_match"])
        self.assertFalse(result["trap_triggered"])
        self.assertEqual(result["score"], 1.0)

    def test_triggered_trap_zeroes_an_otherwise_perfect_answer(self):
        """A trap gates rather than subtracts, so accuracy is irrelevant once set."""
        _, hidden = _case("verified-vs-claimed")
        key = json.loads(json.dumps(hidden["key"]))
        key["turn1"]["verified_complete"] = []
        result = _score("verified-vs-claimed", json.dumps(key))
        self.assertTrue(result["trap_triggered"])
        self.assertEqual(result["score"], 0.0)
        self.assertGreater(result["accuracy"], 0.0)

    def test_t1_forcing_feasibility_on_an_infeasible_case_triggers(self):
        payload = {"feasible": True, "alloc": [14.5, 14.5]}
        result = _score("infeasible-lower-bound", json.dumps(payload))
        self.assertTrue(result["trap_triggered"])
        self.assertEqual(result["score"], 0.0)

    def test_t6_guessing_an_abstention_triggers(self):
        _, hidden = _case("abstention-heavy")
        key = json.loads(json.dumps(hidden["key"]))
        for held_out in key["undetermined"]:
            key["induced"][held_out] = "zzzz"
        key["undetermined"] = []
        result = _score("abstention-heavy", json.dumps(key))
        self.assertTrue(result["trap_triggered"])
        self.assertEqual(result["score"], 0.0)

    def test_trap_detector_error_fails_closed(self):
        _, hidden = _case("p4-release-cascade")
        original = _rescore.TRAP_DETECTORS["p4-release-cascade"]

        def broken_detector(*_args):
            raise TypeError("seeded detector failure")

        _rescore.TRAP_DETECTORS["p4-release-cascade"] = broken_detector
        try:
            result = _score("p4-release-cascade", json.dumps(hidden["key"]))
        finally:
            _rescore.TRAP_DETECTORS["p4-release-cascade"] = original
        self.assertEqual(result["trap_evaluation_error"], "TypeError")
        self.assertEqual(result["score"], 0.0)


class DimensionalSeparationTests(unittest.TestCase):
    def test_right_values_under_wrong_key_names_score_zero_but_stay_json_valid(self):
        """The whole point of the rescorer: naming failure is not reasoning failure."""
        _, hidden = _case("p4-release-cascade")
        renamed = {"allocation": hidden["key"]["alloc"]}
        result = _score("p4-release-cascade", json.dumps(renamed))
        self.assertTrue(result["json_valid"])
        self.assertFalse(result["shape_match"])
        self.assertEqual(result["fields_correct"], 0)

    def test_partial_field_credit_is_reported(self):
        _, hidden = _case("resource-bottleneck")
        partial = {"makespan": hidden["key"]["makespan"]}
        result = _score("resource-bottleneck", json.dumps(partial))
        self.assertEqual(result["fields_correct_names"], ["makespan"])
        self.assertAlmostEqual(result["accuracy"], 0.25)

    def test_unparseable_response_scores_zero(self):
        result = _score("p4-release-cascade", "here is the allocation: 20, 20, 20, 20")
        self.assertFalse(result["json_valid"])
        self.assertEqual(result["score"], 0.0)
        self.assertIsNotNone(result["parse_error"])


class BankDriftTests(unittest.TestCase):
    def test_every_banked_structure_has_a_trap_detector(self):
        """Adding a case without a detector must fail loudly, not score silently."""
        missing = sorted(
            c["structure_id"]
            for c in _HIDDEN["cases"]
            if c["structure_id"] not in _rescore.TRAP_DETECTORS
        )
        self.assertEqual(missing, [])


class CliTests(unittest.TestCase):
    def test_missing_response_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            responses = Path(tmp) / "responses.json"
            responses.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _rescore.main(
                    [
                        "--bank-dir", str(BANK),
                        "--responses", str(responses),
                        "--model", "test",
                        "--out", str(out),
                    ]
                )
            self.assertIn("responses_missing_ids", str(ctx.exception))

    def test_full_run_over_exact_answers_scores_one(self):
        responses = {iid: json.dumps(c["key"]) for iid, c in _HMAP.items()}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            path = Path(tmp) / "responses.json"
            path.write_text(json.dumps(responses), encoding="utf-8")
            _rescore.main(
                [
                    "--bank-dir", str(BANK),
                    "--responses", str(path),
                    "--model", "oracle",
                    "--out", str(out),
                ]
            )
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["strict_pass_count"], len(_HMAP))
        self.assertEqual(report["strict_pass_count_clean"], len(_HMAP) - 2)
        self.assertEqual(report["contaminated_count"], 2)
        self.assertEqual(report["trap_evaluation_error_count"], 0)
        self.assertEqual(report["trap_triggered_count"], 0)
        self.assertEqual(report["dimensional_score"], 1.0)
        self.assertNotIn("T4", report["family_scores_clean"])


class EnhancementSignalTests(unittest.TestCase):
    def test_family_board_and_operational_counts_present(self):
        responses = {iid: json.dumps(c["key"]) for iid, c in _HMAP.items()}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            path = Path(tmp) / "responses.json"
            path.write_text(json.dumps(responses), encoding="utf-8")
            _rescore.main(
                [
                    "--bank-dir", str(BANK),
                    "--responses", str(path),
                    "--model", "oracle",
                    "--out", str(out),
                ]
            )
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("family_board", report)
        self.assertIn("operational_timeout_count", report)
        self.assertIn("answered_count", report)
        self.assertIn("invented_content_flag_count", report)
        self.assertEqual(report["operational_timeout_count"], 0)
        for fam, cell in report["family_board"].items():
            self.assertEqual(cell["cases"], cell["answered"] + cell["timeouts"])

    def test_empty_response_counts_as_timeout(self):
        first = sorted(_HMAP)[0]
        responses = {iid: json.dumps(c["key"]) for iid, c in _HMAP.items()}
        responses[first] = ""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            path = Path(tmp) / "responses.json"
            path.write_text(json.dumps(responses), encoding="utf-8")
            _rescore.main(
                [
                    "--bank-dir", str(BANK),
                    "--responses", str(path),
                    "--model", "oracle-timeout",
                    "--out", str(out),
                ]
            )
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["operational_timeout_count"], 1)
        row = next(r for r in report["results"] if r["instance_id"] == first)
        self.assertTrue(row["operational_timeout"])
        self.assertFalse(row["strict_pass"])


class FailClosedDetectorTests(unittest.TestCase):
    """An unusable detector must zero the case, not silently award credit."""

    def test_exotic_trap_detector_error_fails_closed_instead_of_escaping(self):
        """A detector raising outside the old narrow tuple must not escape."""
        _, hidden = _case("p4-release-cascade")
        original = _rescore.TRAP_DETECTORS["p4-release-cascade"]

        def exotic_detector(*_args):
            raise ZeroDivisionError("seeded exotic detector failure")

        _rescore.TRAP_DETECTORS["p4-release-cascade"] = exotic_detector
        try:
            result = _score("p4-release-cascade", json.dumps(hidden["key"]))
        finally:
            _rescore.TRAP_DETECTORS["p4-release-cascade"] = original
        self.assertEqual(result["trap_evaluation_error"], "ZeroDivisionError")
        self.assertEqual(result["score"], 0.0)

    def test_invented_detector_error_zeroes_the_case_and_is_reported(self):
        """A failing invented-content detector must not report a clean signal."""
        visible, hidden = _case("truncated-primary-mirror")
        original = _rescore._runner.detect_invented_content

        def broken_invented_detector(*_args, **_kwargs):
            # Mirrors the runner's real contract on failure.
            return {"invented_content_suspect": False, "invented_tokens": [],
                    "invented_detector_error": "RuntimeError"}

        _rescore._runner.detect_invented_content = broken_invented_detector
        try:
            result = _rescore.score_case(
                visible, hidden, json.dumps(hidden["key"]), None, "visible-only"
            )
        finally:
            _rescore._runner.detect_invented_content = original
        self.assertEqual(result["invented_detector_error"], "RuntimeError")
        self.assertTrue(result["invented_trap"])
        self.assertEqual(result["score"], 0.0)

    def test_clean_run_reports_no_detector_errors(self):
        """The additive signal must stay at zero for a well-formed run."""
        responses = {iid: json.dumps(c["key"]) for iid, c in _HMAP.items()}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            path = Path(tmp) / "responses.json"
            path.write_text(json.dumps(responses), encoding="utf-8")
            _rescore.main(
                [
                    "--bank-dir", str(BANK),
                    "--responses", str(path),
                    "--model", "oracle",
                    "--out", str(out),
                ]
            )
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["invented_detector_error_count"], 0)
        self.assertEqual(report["strict_pass_count"], len(_HMAP))
        self.assertEqual(report["dimensional_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
