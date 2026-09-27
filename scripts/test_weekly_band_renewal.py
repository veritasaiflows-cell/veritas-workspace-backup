from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import weekly_band_renewal as w

WORKSPACE = Path(__file__).resolve().parents[1]


def row(old_low=100.0, new_low=101.0, *, blocked=False, warn=False, widened=False):
    if blocked:
        return {"classification": "blocked", "old_to_proposed": {"old": None, "proposed": None}}
    old = {"reference_price_low": old_low, "reference_price_high": 110.0, "reference_invalidation_level": 95.0}
    new = {"reference_price_low": new_low, "reference_price_high": 110.0, "reference_invalidation_level": 95.0,
           "band_floor_applied": widened}
    return {"classification": "trend_qualified", "invalidation_ordering_warning": warn,
            "old_to_proposed": {"old": old, "proposed": new}}


CLEAN_DRY = {"drift": 0, "no_mutation": True}


def test_gate_passes_small_clean_moves() -> None:
    g = w.evaluate_gate({"tickers": {"A": row(), "B": row(widened=True)}}, CLEAN_DRY)
    assert g["passed"] and g["floor_widened"] == ["B"]


def test_gate_stops_on_each_condition() -> None:
    assert not w.evaluate_gate({"tickers": {"A": row(blocked=True)}}, CLEAN_DRY)["passed"]
    assert not w.evaluate_gate({"tickers": {"A": row(warn=True)}}, CLEAN_DRY)["passed"]
    over = w.evaluate_gate({"tickers": {"A": row(new_low=106.0)}}, CLEAN_DRY)
    assert not over["passed"] and over["moved_over_limit"] == ["A"]
    assert w.evaluate_gate({"tickers": {"A": row(new_low=105.0)}}, CLEAN_DRY)["passed"]  # exactly 5% is allowed
    assert not w.evaluate_gate({"tickers": {"A": row()}}, {"drift": 1, "no_mutation": True})["passed"]
    assert not w.evaluate_gate({"tickers": {"A": row()}}, None)["passed"]
    assert not w.evaluate_gate({"tickers": {}}, CLEAN_DRY)["passed"]


def test_gate_boundary_uses_unrounded_fraction() -> None:
    assert w.evaluate_gate({"tickers": {"A": row(new_low=105.0)}}, CLEAN_DRY)["passed"]  # exactly 5.000% allowed
    over = w.evaluate_gate({"tickers": {"A": row(new_low=105.004)}}, CLEAN_DRY)
    assert not over["passed"] and over["moved_over_limit"] == ["A"]  # raw 5.004% rejects


def _root(tmp: Path, active: bool = True, prior=True) -> Path:
    (tmp / "state/finance/standing-approvals").mkdir(parents=True)
    (tmp / w.GATE_REL).write_text(json.dumps({"active": active}), encoding="utf-8")
    if prior:
        applied(tmp, "2026-09-24", ["A"])
    return tmp


def applied(root: Path, session: str, names: list[str], legacy=False):
    audit = root / w.AUDIT_DIR_REL / f"{session}-applied.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    packet = {"session": session, "status": "applied", "applied": True,
              "gate": {"edge_moves": {t: {} for t in names}}}
    if not legacy:
        packet["scope"] = {"tickers": names}
    audit.write_text(json.dumps(packet), encoding="utf-8")


def live_scope(path, *, workspace_root):
    return {"scope": {"fingerprint": "fixture-fingerprint"}}


def fake_runner(matrix: dict, calls: list):
    def run(argv, cwd):
        calls.append(argv)
        script = argv[1]
        if "yahoo_reference_level_matrix" in script:
            out = cwd / argv[argv.index("--json-output") + 1]
            out.parent.mkdir(parents=True, exist_ok=True)
            names = sorted(matrix.get("tickers", {}))
            data = {**matrix, "scope": matrix.get("scope", {"tickers": names, "count": len(names),
                                                         "fingerprint": "fixture-fingerprint",
                                                         "tier_breakdown": {"A": len(names)}})}
            out.write_text(json.dumps(data), encoding="utf-8")
        if "--dry-run" in argv:
            (cwd / argv[argv.index("--dryrun-path") + 1]).write_text(json.dumps(
                {"old_drift_tickers": [], "missing_tickers": [], "mutation_performed": False}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
    return run


def test_run_applies_only_when_gate_passes_and_flag_set(tmp_path: Path) -> None:
    root = _root(tmp_path)
    calls: list = []
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, calls), scope_resolver=live_scope)
    assert p["status"] == "applied" and any("--apply" in c for c in calls)
    assert (root / w.AUDIT_DIR_REL / "2026-09-25-applied.json").is_file()
    calls.clear()
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-26",
              runner=fake_runner({"tickers": {"A": row(new_low=120.0)}}, calls), scope_resolver=live_scope)
    assert p["status"] == "needs_owner_review" and not any("--apply" in c for c in calls)


def test_revoked_gate_never_applies(tmp_path: Path) -> None:
    root = _root(tmp_path, active=False)
    calls: list = []
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, calls), scope_resolver=live_scope)
    assert p["status"] == "needs_owner_review" and not any("--apply" in c for c in calls)


def test_name_list_changes_and_legacy_prior(tmp_path: Path) -> None:
    root = _root(tmp_path)
    for names, expected in ((["A"], None), (["A", "B"], "added ['B']"),
                            (["B"], "removed ['A']")):
        calls = []
        packet = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
                       runner=fake_runner({"tickers": {t: row() for t in names}}, calls),
                       scope_resolver=live_scope)
        if expected:
            assert packet["status"] == "needs_owner_review"
            assert expected in str(packet["gate"]["reasons"])
            assert not any("--apply" in call for call in calls)
        else:
            assert packet["status"] == "applied"
            assert packet["scope"]["prior_applied_session"] == "2026-09-24"
            for flag in ("--dry-run", "--apply"):
                argv = next(call for call in calls if flag in call)
                assert argv[argv.index("--expected-scope-fingerprint") + 1] == "fixture-fingerprint"
                assert argv[argv.index("--expected-matrix-sha256") + 1] == packet["matrix_sha256"]
                assert "--verify-live-scope" in argv
            assert packet["matrix_sha256"] == hashlib.sha256((root / packet["matrix"]).read_bytes()).hexdigest()
            assert "fingerprint: fixture-fin" in (root / w.PACKET_MD_REL).read_text()
        # Ensure comparisons are always against the prior fixture, not this test run.
        (root / w.AUDIT_DIR_REL / "2026-09-25-applied.json").unlink(missing_ok=True)
    applied(root, "2026-09-24", ["A"], legacy=True)
    p = w.run(root, python="py", apply_if_gated=False, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, []), scope_resolver=live_scope)
    assert p["gate"]["passed"] and p["scope"]["prior_applied_session"] == "2026-09-24"


def test_no_prior_and_missing_scope_fail_closed(tmp_path: Path) -> None:
    root = _root(tmp_path, prior=False)
    calls = []
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, calls), scope_resolver=live_scope)
    assert p["status"] == "needs_owner_review"
    assert "no readable prior applied renewal to compare the name list" in p["gate"]["reasons"]
    assert not any("--apply" in c for c in calls)
    applied(root, "2026-09-24", ["A"])
    calls.clear()
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}, "scope": {}}, calls), scope_resolver=live_scope)
    assert "matrix carries no scope block" in p["gate"]["reasons"]
    assert not any("--apply" in c for c in calls)
    def invalid_matrix(argv, cwd):
        if "yahoo_reference_level_matrix" in argv[1]:
            path = cwd / argv[argv.index("--json-output") + 1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{invalid", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=invalid_matrix, scope_resolver=live_scope)
    assert p["status"] == "needs_owner_review"
    assert "matrix carries no scope block" in p["gate"]["reasons"]


def test_fingerprint_drift_and_resolver_exception(tmp_path: Path) -> None:
    root = _root(tmp_path)
    for resolver, fragment in ((lambda path, *, workspace_root: {"scope": {"fingerprint": "drift"}},
                                "scope changed between matrix generation and apply"),
                               (lambda path, *, workspace_root: (_ for _ in ()).throw(ValueError("SQL refused")),
                                "SQL refused")):
        calls = []
        p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
                  runner=fake_runner({"tickers": {"A": row()}}, calls), scope_resolver=resolver)
        assert p["status"] == "needs_owner_review"
        assert fragment in str(p["gate"]["reasons"])
        assert not any("--apply" in c for c in calls)
    counter = iter(["fixture-fingerprint", "drift"])
    calls = []
    p = w.run(root, python="py", apply_if_gated=True, session="2026-09-25",
              runner=fake_runner({"tickers": {"A": row()}}, calls),
              scope_resolver=lambda path, *, workspace_root: {"scope": {"fingerprint": next(counter)}})
    assert p["status"] == "needs_owner_review"
    assert "scope changed between matrix generation and apply" in p["gate"]["reasons"]
    assert any("--dry-run" in c for c in calls) and not any("--apply" in c for c in calls)


def test_last_completed_session_skips_open_day() -> None:
    def ts(d):
        return int(datetime.fromisoformat(d + "T09:30:00-04:00").timestamp())
    payload = json.dumps({"chart": {"result": [{"timestamp": [ts("2026-09-24"), ts("2026-09-25")],
                                                 "indicators": {"quote": [{"close": [1.0, 2.0]}]}}]}}).encode()
    during = datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc)   # 11:00 ET, session open
    after = datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc)    # Saturday
    assert w.last_completed_session(lambda u: payload, during) == "2026-09-24"
    assert w.last_completed_session(lambda u: payload, after) == "2026-09-25"


def test_redirected_root_never_touches_production(tmp_path: Path) -> None:
    prod = [WORKSPACE / w.PACKET_REL, WORKSPACE / w.AUDIT_DIR_REL]
    before = [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in prod]
    w.run(_root(tmp_path), python="py", apply_if_gated=False, session="2026-09-25",
          runner=fake_runner({"tickers": {"A": row()}}, []), scope_resolver=live_scope)
    assert before == [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in prod]


class PriorAuditRefusalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = _root(Path(self.temp.name))
        self.audit = self.root / w.AUDIT_DIR_REL

    def check_refusal(self, filename, fragment):
        calls = []
        packet = w.run(self.root, python="py", apply_if_gated=True, session="2026-09-27",
                       runner=fake_runner({"tickers": {"A": row()}}, calls), scope_resolver=live_scope)
        self.assertEqual(packet["status"], "needs_owner_review")
        self.assertTrue(any(f"newest applied audit record is invalid: {filename}: {fragment}" in reason
                            for reason in packet["gate"]["reasons"]))
        self.assertFalse(any("--dry-run" in call or "--apply" in call for call in calls))

    def test_conflicting_status_and_applied_halts(self):
        path = self.audit / "2026-09-26-applied.json"
        path.write_text(json.dumps({"session": "2026-09-26", "applied": False, "status": "applied",
                                    "scope": {"tickers": ["A"]}}))
        self.check_refusal(path.name, "applied/status")
        path.write_text(json.dumps({"session": "2026-09-26", "applied": True, "status": "review",
                                    "scope": {"tickers": ["A"]}}))
        self.check_refusal(path.name, "applied/status")

    def test_session_mismatch_halts(self):
        path = self.audit / "2026-09-26-applied.json"
        path.write_text(json.dumps({"session": "2026-09-25", "applied": True, "status": "applied",
                                    "scope": {"tickers": ["A"]}}))
        self.check_refusal(path.name, "session differs")

    def test_symlink_not_considered(self):
        path = self.audit / "2026-09-26-applied.json"
        try:
            path.symlink_to(self.audit / "2026-09-24-applied.json")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        self.assertEqual(w._prior_applied_names(self.root, "2026-09-27"), ("2026-09-24", ["A"], None))

    def test_directory_not_considered(self):
        (self.audit / "2026-09-26-applied.json").mkdir()
        self.assertEqual(w._prior_applied_names(self.root, "2026-09-27"), ("2026-09-24", ["A"], None))

    def test_malformed_newest_never_falls_back(self):
        path = self.audit / "2026-09-26-applied.json"
        path.write_text("{broken", encoding="utf-8")
        self.check_refusal(path.name, "Expecting property name")

    def test_newest_valid_record_wins(self):
        applied(self.root, "2026-09-25", ["A", "B"])
        applied(self.root, "2026-09-26", ["B", "A"])
        self.assertEqual(w._prior_applied_names(self.root, "2026-09-27"),
                         ("2026-09-26", ["A", "B"], None))

    def test_legacy_gate_edge_moves(self):
        applied(self.root, "2026-09-26", ["B", "A"], legacy=True)
        self.assertEqual(w._prior_applied_names(self.root, "2026-09-27"),
                         ("2026-09-26", ["A", "B"], None))

    def test_future_record_halts(self):
        applied(self.root, "2026-09-28", ["A"])
        self.check_refusal("2026-09-28-applied.json", "future-dated")

    def test_bad_names_halt_not_fallback(self):
        path = self.audit / "2026-09-26-applied.json"
        applied(self.root, "2026-09-26", ["A", "A"])
        self.check_refusal(path.name, "names must be unique non-empty")

    def test_wrapper_passes_explicit_root_and_matrix_hash(self):
        seen = []

        def resolver(db, *, workspace_root):
            seen.append((db, workspace_root))
            return live_scope(db, workspace_root=workspace_root)

        calls = []
        packet = w.run(self.root, python="py", apply_if_gated=True, session="2026-09-25",
                       runner=fake_runner({"tickers": {"A": row()}}, calls), scope_resolver=resolver)
        self.assertEqual(packet["status"], "applied")
        self.assertEqual(seen, [(self.root / w.DB_REL, self.root.resolve())] * 2)
        digest = hashlib.sha256((self.root / packet["matrix"]).read_bytes()).hexdigest()
        self.assertEqual(packet["matrix_sha256"], digest)
        for flag in ("--dry-run", "--apply"):
            argv = next(call for call in calls if flag in call)
            self.assertEqual(argv[argv.index("--expected-matrix-sha256") + 1], digest)
            self.assertIn("--verify-live-scope", argv)
