"""Scratch/host-portable dynamic scope checks for the historical Yahoo32 writer."""
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import g6_yahoo32_sql_apply as writer

SCRIPT = Path(__file__).with_name("g6_yahoo32_sql_apply.py")
# Test-only stand-in for guarded SQL: runs the real script with a fake live
# scope resolver. Live scope equals the matrix scope unless
# G6_TEST_LIVE_FINGERPRINT simulates drift.
LIVE_SHIM = (
    "import json, os, runpy, sys, types\n"
    "script, args = sys.argv[1], sys.argv[2:]\n"
    "def resolve_band_scope(db_path, **_):\n"
    "    fp = os.environ.get('G6_TEST_LIVE_FINGERPRINT')\n"
    "    if fp is None:\n"
    "        with open(args[args.index('--matrix') + 1], encoding='utf-8') as f:\n"
    "            fp = json.load(f)['scope']['fingerprint']\n"
    "    return {'scope': {'fingerprint': fp}}\n"
    "fake = types.ModuleType('yahoo_reference_level_matrix')\n"
    "fake.resolve_band_scope = resolve_band_scope\n"
    "sys.modules['yahoo_reference_level_matrix'] = fake\n"
    "sys.argv = [script] + args\n"
    "runpy.run_path(script, run_name='__main__')\n"
)
OLD = {"reference_price_low": 10, "reference_price_high": 20,
       "reference_invalidation_level": 5}
NEW = {"reference_price_low": 11, "reference_price_high": 21,
       "reference_invalidation_level": 6}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(root, n=32, scoped=True):
    db = root / "levels.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE reference_levels (ticker TEXT PRIMARY KEY, "
                "reference_price_low REAL, reference_price_high REAL, "
                "reference_invalidation_level REAL, reference_confidence INTEGER, "
                "reference_band_status TEXT, authority_class TEXT, "
                "source_artifact_path TEXT, source_artifact_sha256 TEXT, "
                "source_generated_at_utc TEXT)")
    con.executemany("INSERT INTO reference_levels VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(f"T{i:02d}", 10, 20, 5, 70, "above_band", "owner_review",
                      "old-pin.json", "a" * 64, "2026-01-01T00:00:00Z")
                     for i in range(40)])
    con.commit()
    con.close()
    tickers = [f"T{i:02d}" for i in range(n)]
    matrix = {"tickers": {t: {"old": OLD, "proposed": NEW} for t in tickers}}
    if scoped:
        members = [{"ticker": t, "tier": "core", "decision_grade_eligible": True}
                   for t in tickers]
        matrix["scope"] = {
            "source": "guarded-sql-dynamic-entitlement",
            "members": members, "tickers": tickers, "count": n,
            "fingerprint": writer._dynamic_scope_fingerprint(
                [(m["ticker"], m["tier"], m["decision_grade_eligible"])
                 for m in members]),
        }
    return db, matrix


def run(root, mode, db, matrix=None, *extra, live_fingerprint=None):
    mp = root / "matrix.json"
    if matrix is not None:
        mp.write_text(json.dumps(matrix), encoding="utf-8")
    cmd = [sys.executable, "-B", "-c", LIVE_SHIM, str(SCRIPT), mode, "--db", str(db)]
    if mode != "--rollback":
        cmd += ["--matrix", str(mp), "--baseline-dir", str(root / "pins")]
    cmd += list(extra)
    env = dict(os.environ)
    env.pop("G6_TEST_LIVE_FINGERPRINT", None)
    if live_fingerprint is not None:
        env["G6_TEST_LIVE_FINGERPRINT"] = live_fingerprint
    return subprocess.run(cmd, text=True, capture_output=True, check=False, env=env)


def verified(matrix):
    return ("--expected-scope-fingerprint", matrix["scope"]["fingerprint"], "--verify-live-scope")


class DynamicScopeTests(unittest.TestCase):
    def test_known_fingerprint_vector(self):
        triples = [("AAA", "core", True), ("BÉ", "watch", False),
                   ("ZZZ", "other", True)]
        self.assertEqual(writer._dynamic_scope_fingerprint(triples),
                         "336bb2c7eacb8d5602fab2c4b84e4e5f70b4282d1401ac3255f306ebaf1d5b2e")

    def test_scoped_apply_counts_and_byte_exact_rollback(self):
        for n in (31, 32, 33):
            with self.subTest(n=n), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                db, matrix = fixture(root, n)
                original = digest(db)
                backup, rb = root / "backup.sqlite", root / "rollback.json"
                result = run(root, "--apply", db, matrix, "--write", "--validate",
                             "--backup-path", str(backup), "--rollback-path", str(rb),
                             *verified(matrix))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"apply_ok: rows={n}", result.stdout)
                artifact = json.loads(rb.read_text())
                self.assertEqual((artifact["scope_consistent"], artifact["scope_verified"],
                                  artifact["scope_count"], artifact["scope_fingerprint"]),
                                 (True, True, n, matrix["scope"]["fingerprint"]))
                self.assertFalse(artifact["matrix_sha256_verified"])
                self.assertTrue(artifact["live_scope_verified"])
                self.assertEqual(digest(backup), original)
                con = sqlite3.connect(db)
                try:
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0], 40)
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM reference_levels "
                                                 "WHERE reference_band_status IS NULL").fetchone()[0], n)
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM reference_levels "
                                                 "WHERE authority_class = 'owner_review'").fetchone()[0], 40)
                finally:
                    con.close()
                restored = run(root, "--rollback", db, None, "--rollback-path", str(rb))
                self.assertEqual(restored.returncode, 0, restored.stderr)
                self.assertEqual(digest(db), original)

    def test_correct_flag_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, matrix = fixture(root, 31)
            flag = matrix["scope"]["fingerprint"]
            original = digest(db)
            dry_path, rb = root / "dry.json", root / "rollback.json"
            result = run(root, "--dry-run", db, matrix, "--write", "--validate",
                         "--expected-scope-fingerprint", flag, "--dryrun-path", str(dry_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(digest(db), original)
            dry = json.loads(dry_path.read_text())
            self.assertEqual((dry["scope_consistent"], dry["scope_verified"],
                              dry["scope_fingerprint"], dry["scope_count"]),
                             (True, True, flag, 31))
            result = run(root, "--apply", db, matrix, "--write", "--validate",
                         "--expected-scope-fingerprint", flag, "--verify-live-scope", "--backup-path",
                         str(root / "backup.sqlite"), "--rollback-path", str(rb))
            self.assertEqual(result.returncode, 0, result.stderr)
            applied = json.loads(rb.read_text())
            self.assertEqual((applied["scope_consistent"], applied["scope_verified"],
                              applied["scope_fingerprint"], applied["scope_count"],
                              applied["live_scope_verified"]),
                             (True, True, flag, 31, True))

    def test_scope_refusals_before_backup(self):
        cases = ("wrong flag", "flag without scope", "tampered tier", "extra matrix ticker",
                 "missing matrix ticker", "count mismatch", "unsorted members", "malformed flag")
        for case in cases:
            for mode in ("--dry-run", "--apply"):
                with self.subTest(case=case, mode=mode), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    db, original_matrix = fixture(root, 31)
                    matrix = copy.deepcopy(original_matrix)
                    flag = matrix["scope"]["fingerprint"]
                    if case == "wrong flag":
                        flag = "0" * 64 if flag != "0" * 64 else "1" * 64
                    elif case == "flag without scope":
                        del matrix["scope"]
                    elif case == "tampered tier":
                        matrix["scope"]["members"][0]["tier"] = "tampered"
                    elif case == "extra matrix ticker":
                        matrix["tickers"]["T31"] = {"old": OLD, "proposed": NEW}
                    elif case == "missing matrix ticker":
                        del matrix["tickers"]["T00"]
                    elif case == "count mismatch":
                        matrix["scope"]["count"] += 1
                    elif case == "unsorted members":
                        members = matrix["scope"]["members"]
                        members[0], members[1] = members[1], members[0]
                    elif case == "malformed flag":
                        flag = "G" * 64
                    backup = root / "backup.sqlite"
                    before = digest(db)
                    result = run(root, mode, db, matrix, "--write", "--validate",
                                 "--expected-scope-fingerprint", flag, "--verify-live-scope",
                                 "--backup-path", str(backup))
                    self.assertEqual(result.returncode, 2, (case, mode, result.stderr))
                    self.assertIn("refused", result.stderr)
                    self.assertEqual(digest(db), before)
                    self.assertFalse(backup.exists())
                    self.assertFalse((root / "pins").exists())

    def test_empty_matrix_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, _ = fixture(root, 32, scoped=False)
            before = digest(db)
            backup = root / "backup.sqlite"
            result = run(root, "--apply", db, {"tickers": {}}, "--write",
                         "--backup-path", str(backup))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("at least one ticker", result.stderr)
            self.assertEqual(digest(db), before)
            self.assertFalse(backup.exists())

    def test_unscoped_dry_run_allowed_but_apply_refused(self):
        for n in (31, 32):
            with self.subTest(n=n), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                db, matrix = fixture(root, n, scoped=False)
                before = digest(db)
                dry = root / "dry.json"
                result = run(root, "--dry-run", db, matrix, "--write", "--validate",
                             "--dryrun-path", str(dry))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(digest(db), before)
                summary = json.loads(dry.read_text())
                self.assertEqual((summary["scope_consistent"], summary["scope_verified"],
                                  summary["scope_fingerprint"], summary["scope_count"]),
                                 (False, False, None, None))
                backup = root / "backup.sqlite"
                result = run(root, "--apply", db, matrix, "--write", "--validate",
                             "--backup-path", str(backup), "--rollback-path", str(root / "rb.json"))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("apply refused", result.stderr)
                self.assertEqual(digest(db), before)
                self.assertFalse(backup.exists())
                self.assertFalse((root / "pins").exists())

    def test_scoped_apply_requires_fingerprint_and_live_scope(self):
        cases = {
            "no flags": ((), None, "apply refused"),
            "fingerprint only": (("--expected-scope-fingerprint", None), None, "apply refused"),
            "live only": (("--verify-live-scope",), None, "requires --expected-scope-fingerprint"),
            "live drift": (("--expected-scope-fingerprint", None, "--verify-live-scope"), "0" * 64,
                           "live scope fingerprint mismatch"),
        }
        for case, (flags, live, fragment) in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                db, matrix = fixture(root, 33)
                fp = matrix["scope"]["fingerprint"]
                flags = tuple(fp if f is None else f for f in flags)
                before = digest(db)
                backup = root / "backup.sqlite"
                result = run(root, "--apply", db, matrix, "--write", "--validate",
                             "--backup-path", str(backup), "--rollback-path", str(root / "rb.json"),
                             *flags, live_fingerprint=live)
                self.assertEqual(result.returncode, 2, (case, result.stderr))
                self.assertIn(fragment, result.stderr)
                self.assertEqual(digest(db), before)
                self.assertFalse(backup.exists())
                self.assertFalse((root / "pins").exists())

    def test_run_apply_function_refuses_unverified_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, matrix = fixture(root, 31)
            mp = root / "matrix.json"
            mp.write_text(json.dumps(matrix), encoding="utf-8")
            data, sha = writer.load_matrix(mp)
            flag = matrix["scope"]["fingerprint"]
            triples = writer.extract_triples(data)
            verified_info = writer.verify_scope(data, flag)
            resolver = lambda path: {"scope": {"fingerprint": flag}}
            fewer = dict(list(triples.items())[:30])
            cases = {
                "no scope info": (None, flag, True, triples),
                "unverified scope": (writer.verify_scope(data), flag, True, triples),
                "no expected flag": (verified_info, None, False, triples),
                "no live check": (verified_info, flag, False, triples),
                "count mismatch": (verified_info, flag, True, fewer),
            }
            before = digest(db)
            for case, (info, expected, live, batch) in cases.items():
                with self.subTest(case=case):
                    backup = root / f"backup-{case}.sqlite"
                    with self.assertRaisesRegex(ValueError, "apply refused"):
                        writer.run_apply(db, batch, mp, sha, backup, root / "rb.json", True,
                                         baseline_dir=root / "pins", scope_info=info,
                                         expected_scope_fingerprint=expected,
                                         verify_live_scope=live, live_scope_resolver=resolver)
                    self.assertFalse(backup.exists())
            self.assertEqual(digest(db), before)
            self.assertFalse((root / "pins").exists())

    def test_validator_variable_count_and_mismatched_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, matrix = fixture(root, 31)
            mp = root / "matrix.json"
            rb = root / "rollback.json"
            result = run(root, "--apply", db, matrix, "--write", "--validate",
                         "--backup-path", str(root / "backup.sqlite"),
                         "--rollback-path", str(rb), *verified(matrix))
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = json.loads(rb.read_text())
            artifact["rollback_path"] = str(rb)
            self.assertEqual(writer.validate_apply_artifact(artifact, db, digest(mp)), [])
            for field in ("scope_verified", "live_scope_verified"):
                unverified = copy.deepcopy(artifact)
                unverified[field] = False
                self.assertIn("apply must be scope-verified and live-scope-verified",
                              writer.validate_apply_artifact(unverified, db, digest(mp)))
            broken = copy.deepcopy(artifact)
            broken["triple_count"] = 30
            self.assertTrue(any("triple_count" in e for e in
                                writer.validate_apply_artifact(broken, db, digest(mp))))
            broken = copy.deepcopy(artifact)
            broken["scope_count"] = 30
            self.assertTrue(any("scope_count" in e for e in
                                writer.validate_apply_artifact(broken, db, digest(mp))))
            broken["scope_verified"] = False
            self.assertTrue(any("scope_count" in e for e in
                                writer.validate_apply_artifact(broken, db, digest(mp))))

    def test_matrix_sha_guards_and_proofs(self):
        for mode in ("--dry-run", "--apply"):
            for case in ("wrong", "changed bytes", "malformed", "correct"):
                with self.subTest(mode=mode, case=case), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    db, matrix = fixture(root, 32)
                    mp = root / "matrix.json"
                    raw = json.dumps(matrix).encode("utf-8")
                    mp.write_bytes(raw)
                    expected = hashlib.sha256(raw).hexdigest()
                    if case == "wrong":
                        expected = "0" * 64 if expected != "0" * 64 else "1" * 64
                    elif case == "changed bytes":
                        # Hash the original, then change the matrix bytes on disk.
                        mp.write_bytes(raw + b" ")
                    elif case == "malformed":
                        expected = "A" * 64
                    before = digest(db)
                    backup = root / "backup.sqlite"
                    artifact = root / "artifact.json"
                    cmd = [sys.executable, "-B", "-c", LIVE_SHIM, str(SCRIPT), mode, "--db", str(db),
                           "--matrix", str(mp), "--baseline-dir", str(root / "pins"),
                           "--expected-matrix-sha256", expected, "--write",
                           "--backup-path", str(backup)]
                    if mode == "--apply":
                        cmd += ["--rollback-path", str(artifact), *verified(matrix)]
                    else:
                        cmd += ["--dryrun-path", str(artifact)]
                    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
                    if case != "correct":
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertEqual(digest(db), before)
                        self.assertFalse(backup.exists())
                        self.assertFalse(artifact.exists())
                        self.assertFalse((root / "pins").exists())
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertTrue(json.loads(artifact.read_text())["matrix_sha256_verified"])

    def test_live_scope_requires_expected_flag(self):
        for mode in ("--dry-run", "--apply"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                db, matrix = fixture(root, 31)
                before = digest(db)
                backup = root / "backup.sqlite"
                result = run(root, mode, db, matrix, "--write", "--verify-live-scope",
                             "--backup-path", str(backup))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(digest(db), before)
                self.assertFalse(backup.exists())
                self.assertFalse((root / "pins").exists())

    def test_injected_live_scope_resolver(self):
        for mode in ("dry", "apply"):
            for case in ("mismatch", "exception", "match"):
                with self.subTest(mode=mode, case=case), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    db, matrix = fixture(root, 31)
                    mp = root / "matrix.json"
                    mp.write_text(json.dumps(matrix), encoding="utf-8")
                    matrix_data, sha = writer.load_matrix(mp)
                    flag = matrix["scope"]["fingerprint"]
                    scope_info = writer.verify_scope(matrix_data, flag)
                    triples = writer.extract_triples(matrix_data)
                    calls = []
                    def resolver(path):
                        calls.append(path)
                        if case == "exception":
                            raise RuntimeError("offline resolver")
                        return {"scope": {"fingerprint": flag if case == "match" else "0" * 64}}
                    before = digest(db)
                    backup = root / "backup.sqlite"
                    opts = dict(scope_info=scope_info, expected_scope_fingerprint=flag,
                                verify_live_scope=True, live_scope_resolver=resolver)
                    if mode == "dry":
                        operation = lambda: writer.build_dry_run(db, triples, mp, sha, **opts)
                    else:
                        operation = lambda: writer.run_apply(
                            db, triples, mp, sha, backup, root / "rollback.json", True,
                            baseline_dir=root / "pins", **opts)
                    if case == "match":
                        artifact = operation()
                        self.assertTrue(artifact["live_scope_verified"])
                        self.assertTrue(artifact["scope_verified"])
                        if mode == "apply":
                            self.assertTrue(backup.exists())
                    else:
                        with self.assertRaisesRegex(ValueError, "live scope"):
                            operation()
                        self.assertEqual(digest(db), before)
                        self.assertFalse(backup.exists())
                        self.assertFalse((root / "pins").exists())
                    self.assertEqual(calls, [db])


if __name__ == "__main__":
    unittest.main()
