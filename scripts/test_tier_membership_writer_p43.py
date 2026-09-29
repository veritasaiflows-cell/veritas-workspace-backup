#!/usr/bin/env python3
"""P4-3 integration tests: journal lease/timeout/recovery, owner-decision
binding, live-safe inverse rollback and the cutover gate, driven through
scripts/tier_membership_writer.py on copies of the staged fixture root.

Never touches the live canon except one read-only gate check.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

os.environ["VERITAS_P42_TEST_ONLY_ACTIVATION"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_tier_membership_writer as base  # noqa: E402
import tier_membership_writer as wmod  # noqa: E402
import tier_owner_decision as tod  # noqa: E402
import tier_transaction_journal as ttj  # noqa: E402

LIVE_ROOT = Path(__file__).resolve().parent.parent


def journal(root: Path, clock=None) -> ttj.TierTransactionJournal:
    return wmod.journal_for(root, clock)


def swap_setup(tmpdir: str):
    root = Path(tmpdir) / "root"
    b = base.pick_b_ticker(root)
    c = base.pick_c_with_band(root)
    base.inject_onboarding(root, c)
    dec = base.write_decision(tmpdir, [
        base.approved(b, "B", "C", card="card_b"),
        base.approved(c, "C", "B", card="card_c")])
    return root, b, c, dec


def _unrelated_commit(root: Path) -> None:
    """Another job (e.g. freshness) commits an unrelated row."""
    con = sqlite3.connect(str(base.db_path(root)))
    try:
        con.execute("INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                    " VALUES ('between-backup-and-lock','2026-09-29T06:00:00Z',"
                    "'unrelated_test_commit','{}')")
        con.commit()
    finally:
        con.close()


def _backup_then_unrelated_commit(root: Path):
    """wal_safe_backup, then another job commits before our write lock."""
    original = wmod.snap.wal_safe_backup

    def wrapped(db, backup_path):
        info = original(db, backup_path)
        _unrelated_commit(root)
        return info
    return wrapped


def _unrelated_count(root: Path) -> int:
    con = sqlite3.connect(str(base.db_path(root)))
    try:
        return con.execute("SELECT COUNT(*) FROM audit_events "
                           "WHERE event_id='between-backup-and-lock'").fetchone()[0]
    finally:
        con.close()


class _CommitRaises:
    """Connection stand-in whose COMMIT raises: after the commit is durable
    (``durable=True``) or instead of committing (``durable=False``)."""

    def __init__(self, con, durable: bool, after=None):
        self.con, self.durable, self.after = con, durable, after

    def commit(self):
        if self.durable:
            self.con.commit()
        if self.after is not None:
            self.after()  # e.g. another job commits before the probe
        raise sqlite3.OperationalError("commit raised (test)")

    def rollback(self):
        self.con.rollback()


def _commit_raising(durable: bool, after=None):
    """Patch for wmod._commit_or_prove_aborted: the real helper, fed a COMMIT
    that raises."""
    real = wmod._commit_or_prove_aborted

    def patched(con, landed):
        return real(_CommitRaises(con, durable, after), landed)
    return patched


def _commit_then(hook):
    """Patch for wmod._commit_or_prove_aborted: a normal COMMIT, then ``hook``."""
    real = wmod._commit_or_prove_aborted

    def patched(con, landed):
        real(con, landed)
        hook()
    return patched


def _canon_connect_fails_when(root: Path, armed: list):
    """sqlite3.connect that refuses read-write canon opens once ``armed``."""
    real = sqlite3.connect
    target = str(base.db_path(root))

    def connect(*a, **k):
        if armed and a and a[0] == target and not k.get("uri"):
            raise sqlite3.OperationalError("unable to open database file (test)")
        return real(*a, **k)
    return connect


def apply_swap(root: Path, dec: Path, out_name: str = "p43-out"):
    out = root / "tmp" / out_name
    return base.run_writer(root, "--decision-file", str(dec), "--apply", "--write",
                           "--output-dir", str(out)), out


class TestOwnerDecisionBinding(unittest.TestCase):
    def test_missing_owner_decision_id_refused(self):
        tmp = base.copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = base.pick_b_ticker(root)
            c = base.pick_c_with_band(root)
            base.inject_onboarding(root, c)
            entries = [base.approved(b, "B", "C"), base.approved(c, "C", "B")]
            entries[0]["owner_decision_id"] = None
            dec = base.write_decision(tmp.name, entries)
            before = base.logical(root)
            proc, _ = apply_swap(root, dec)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("missing_owner_decision_id", proc.stdout)
            self.assertEqual(base.logical(root), before)
        finally:
            tmp.cleanup()

    def test_record_for_a_different_change_refused_even_in_dry_run(self):
        tmp = base.copy_staged()
        try:
            root, b, c, dec = swap_setup(tmp.name)
            doc = json.loads(dec.read_text(encoding="utf-8"))
            did = doc["decisions"][1]["owner_decision_id"]
            path = tod.decision_path(root, did)
            rec = json.loads(path.read_text(encoding="utf-8"))
            rec["card_id"] = "card_someone_else"
            path.write_text(json.dumps(rec), encoding="utf-8")
            before = base.logical(root)
            proc = base.run_writer(root, "--decision-file", str(dec))
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("decision_binding_mismatch", proc.stdout)
            self.assertIn(":card_id", proc.stdout)
            self.assertEqual(base.logical(root), before)
        finally:
            tmp.cleanup()

    def test_expired_record_refused(self):
        tmp = base.copy_staged()
        try:
            root, b, c, dec = swap_setup(tmp.name)
            doc = json.loads(dec.read_text(encoding="utf-8"))
            did = doc["decisions"][0]["owner_decision_id"]
            path = tod.decision_path(root, did)
            rec = json.loads(path.read_text(encoding="utf-8"))
            now = dt.datetime.now(dt.timezone.utc)
            rec["granted_at"] = (now - dt.timedelta(days=8)).isoformat()
            rec["expires_at"] = (now - dt.timedelta(days=1)).isoformat()
            path.write_text(json.dumps(rec), encoding="utf-8")
            proc, _ = apply_swap(root, dec)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("decision_expired", proc.stdout)
        finally:
            tmp.cleanup()


class TestJournalledApply(unittest.TestCase):
    def test_apply_records_effective_journal_and_consumes_decisions(self):
        tmp = base.copy_staged()
        try:
            root, b, c, dec = swap_setup(tmp.name)
            proc, out = apply_swap(root, dec)
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])
            audit = json.loads(proc.stdout)["audit"]
            ids = audit["journal_txn_ids"]
            self.assertEqual(set(ids), {b, c})
            self.assertEqual(audit["authority"]["activation_context"], "hermetic_test")
            j = journal(root)
            for ticker, jtxn in ids.items():
                txn = j.get(jtxn)
                self.assertEqual(txn["state"], ttj.EFFECTIVE)
                self.assertIsNone(j.lease(ticker))
                self.assertEqual(txn["commit"]["canon_transaction_id"], audit["transaction_id"])
            con = sqlite3.connect(str(base.db_path(root)))
            try:
                details = [json.loads(r[0]) for r in con.execute(
                    "SELECT detail_json FROM audit_events WHERE event_type=?",
                    (wmod.EVENT_TYPE,))]
            finally:
                con.close()
            self.assertEqual({d["journal_txn_id"] for d in details}, set(ids.values()))
            self.assertTrue(all(len(d["owner_decision_sha256"]) == 64 for d in details))
            # Re-running the same decision set cannot apply twice.
            again, _ = apply_swap(root, dec, "p43-again")
            self.assertEqual(again.returncode, 2)
            self.assertIn("prior_tier_mismatch", again.stdout)
        finally:
            tmp.cleanup()

    def test_lease_held_by_live_transaction_refuses_and_changes_nothing(self):
        tmp = base.copy_staged()
        try:
            root, b, c, dec = swap_setup(tmp.name)
            fam = wmod.snapshot_rows(base.db_path(root), [c])["families"][c]
            other = journal(root).open(
                ticker=c, from_tier="C", to_tier="B", prior_family=fam,
                forward_family={**fam, "tier": "B"}, decision_id="other-writer-decision",
                decision_sha256="x", holder="other-writer")
            before = base.logical(root)
            proc, _ = apply_swap(root, dec)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("lease_held:%s" % c, proc.stdout)
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual(j.lease(c)["txn_id"], other["txn_id"])
            self.assertIsNone(j.lease(b), "sibling lease must be released")
            self.assertEqual([t["txn_id"] for t in j.open_transactions()], [other["txn_id"]])
        finally:
            tmp.cleanup()

    def test_crash_after_commit_is_finalized_by_recovery(self):
        tmp = base.copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = base.TestConcurrencyAndRestore._prep(None, root, tmp.name)
            wmod.bind_owner_decisions(root, bundle)
            out = root / "tmp" / "crash"
            with self.assertRaises(wmod._SimulatedCrash):
                wmod.do_apply(root, base.db_path(root), bundle, ctx, mods,
                              out / "backup.sqlite", out / "a.json", out / "r.json", out,
                              _crash_after_commit=True)
            self.assertEqual(base.sql_tier_of(root, c), "B")  # canon committed
            j = journal(root)
            pending = j.open_transactions()
            self.assertEqual({t["ticker"] for t in pending}, {b, c})
            proc = base.run_writer(root, "--recover", "--after-crash")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            settled = json.loads(proc.stdout)["settled"]
            self.assertEqual({s["state"] for s in settled}, {ttj.EFFECTIVE})
            self.assertEqual(j.open_transactions(), [])
            self.assertIsNone(j.lease(c))
        finally:
            tmp.cleanup()

    def test_crash_before_commit_is_blocked_by_recovery(self):
        tmp = base.copy_staged()
        try:
            root, b, c, dec = swap_setup(tmp.name)
            fam = wmod.snapshot_rows(base.db_path(root), [c])["families"][c]
            txn = journal(root).open(
                ticker=c, from_tier="C", to_tier="B", prior_family=fam,
                forward_family={**fam, "tier": "B"}, decision_id="dead-writer-decision",
                decision_sha256="x", holder="dead-writer")
            proc = base.run_writer(root, "--recover")
            self.assertEqual(json.loads(proc.stdout)["settled"], [])  # still in its window
            proc = base.run_writer(root, "--recover", "--after-crash")
            settled = json.loads(proc.stdout)["settled"]
            self.assertEqual([(s["txn_id"], s["state"]) for s in settled],
                             [(txn["txn_id"], ttj.BLOCKED)])
            self.assertEqual(base.sql_tier_of(root, c), "C")
            # The lease is free again: the real decision set now applies.
            ok, _ = apply_swap(root, dec)
            self.assertEqual(ok.returncode, 0, ok.stdout[-2000:])
        finally:
            tmp.cleanup()

    def test_timed_out_transaction_expires_on_next_apply(self):
        tmp = base.copy_staged()
        try:
            root, b, c, dec = swap_setup(tmp.name)
            fam = wmod.snapshot_rows(base.db_path(root), [c])["families"][c]
            past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5)
            stale = journal(root, clock=lambda: past).open(
                ticker=c, from_tier="C", to_tier="B", prior_family=fam,
                forward_family={**fam, "tier": "B"}, decision_id="stale-decision",
                decision_sha256="x", holder="old-writer")
            ok, _ = apply_swap(root, dec)  # do_apply runs recovery first
            self.assertEqual(ok.returncode, 0, ok.stdout[-2000:])
            expired = journal(root).get(stale["txn_id"])
            self.assertEqual(expired["state"], ttj.EXPIRED)
            self.assertEqual(expired["reasons"], ["timeout_end_of_next_market_session"])
        finally:
            tmp.cleanup()

    def _in_process(self, tmpdir):
        root = Path(tmpdir) / "root"
        b, c, mods, bundle, ctx = base.TestConcurrencyAndRestore._prep(None, root, tmpdir)
        return root, b, c, mods, bundle, ctx

    def _do_apply(self, root, mods, bundle, ctx, name, **kw):
        out = root / "tmp" / name
        return wmod.do_apply(root, base.db_path(root), bundle, ctx, mods,
                             out / "backup.sqlite", out / "a.json", out / "r.json", out, **kw)

    def _assert_undone_keeping_unrelated(self, root, b, c, bundle, exc):
        self.assertIn("post_apply_failed_restored", str(exc))
        self.assertEqual(_unrelated_count(root), 1, "another job's commit was destroyed")
        self.assertEqual(base.sql_tier_of(root, b), "B")
        self.assertEqual(base.sql_tier_of(root, c), "C")
        for d in bundle["decisions"]:  # our audit events are compensated away
            self.assertIsNone(wmod.canon_decision_consumed(base.db_path(root),
                                                           d["owner_decision_id"]))
        j = journal(root)
        self.assertEqual(j.open_transactions(), [])
        self.assertIsNone(j.lease(c))

    def test_commit_between_backup_and_lock_survives_failed_apply(self):
        # QA F4 / re-review N1: a commit landing after the backup survives a
        # verify failure, because failures are undone by compare-and-swap.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            with mock.patch.object(wmod.snap, "wal_safe_backup",
                                   _backup_then_unrelated_commit(root)):
                with self.assertRaises(RuntimeError) as cm:
                    self._do_apply(root, mods, bundle, ctx, "race", _force_verify_fail=True)
            self._assert_undone_keeping_unrelated(root, b, c, bundle, cm.exception)
        finally:
            tmp.cleanup()

    def test_commit_after_our_commit_survives_failed_apply(self):
        # Re-review N1: the window between our COMMIT and the undo.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)

            def commit_then_fail(*_a, **_k):
                _unrelated_commit(root)
                raise RuntimeError("verify failed (test)")
            with mock.patch.object(wmod, "verify_post_state", commit_then_fail):
                with self.assertRaises(RuntimeError) as cm:
                    self._do_apply(root, mods, bundle, ctx, "post-commit")
            self._assert_undone_keeping_unrelated(root, b, c, bundle, cm.exception)
        finally:
            tmp.cleanup()

    def test_backup_matching_lock_state_is_recorded(self):
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "clean")
            self.assertTrue(audit["backup_matches_lock_state"])
            self.assertEqual(audit["db_logical_sha256_after"], base.logical(root))
        finally:
            tmp.cleanup()

    def test_unverifiable_commit_that_cannot_be_undone_exits_committed_unsettled(self):
        # Re-review N5: canon holds our change, so this must not be reported
        # as "nothing applied"; the journal stays pending for recovery.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)

            def other_job_touches_row_then_fail(*_a, **_k):
                con = sqlite3.connect(str(base.db_path(root)))
                try:
                    con.execute("UPDATE universe_membership SET tier_decision_scope='touched'"
                                " WHERE ticker=?", (c,))
                    con.commit()
                finally:
                    con.close()
                raise RuntimeError("verify failed (test)")
            with mock.patch.object(wmod, "verify_post_state", other_job_touches_row_then_fail):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    self._do_apply(root, mods, bundle, ctx, "unsettled")
            self.assertIn("compensation_refused_row_changed_after_commit:%s" % c, str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "C")  # left as committed
            self.assertEqual({t["ticker"] for t in journal(root).open_transactions()}, {b, c})
        finally:
            tmp.cleanup()

    def test_recovery_marking_effective_blocks_apply_compensation(self):
        # Round-3 NEW-3: a concurrent --recover marks our commit effective
        # between COMMIT and the undo. Compensation must not reverse canon
        # underneath an effective journal; canon and journal stay forward.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)

            def recover_then_fail(*_a, **_k):
                wmod.recover_journal(journal(root), base.db_path(root))
                raise RuntimeError("verify failed (test)")
            with mock.patch.object(wmod, "verify_post_state", recover_then_fail):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    self._do_apply(root, mods, bundle, ctx, "recovered")
            self.assertIn("compensation_skipped_journal_already_settled", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "C")
            self.assertEqual(base.sql_tier_of(root, c), "B")
            j = journal(root)
            self.assertEqual({t["ticker"] for t in j.effective_transactions()}, {b, c})
            self.assertEqual(j.open_transactions(), [])
        finally:
            tmp.cleanup()

    def test_failure_building_post_commit_proof_is_compensated(self):
        # Round-3 NEW-4: any exception after COMMIT (here, a malformed verify
        # result) is undone, not reported as a bare "nothing applied" error.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            before = base.logical(root)
            with mock.patch.object(wmod, "verify_post_state", lambda *_a, **_k: {}):
                with self.assertRaises(RuntimeError) as cm:
                    self._do_apply(root, mods, bundle, ctx, "malformed")
            self.assertNotIsInstance(cm.exception, wmod._CommittedUnsettled)
            self.assertIn("post_commit_failed_restored", str(cm.exception))
            self.assertEqual(base.logical(root), before)
            for d in bundle["decisions"]:
                self.assertIsNone(wmod.canon_decision_consumed(base.db_path(root),
                                                               d["owner_decision_id"]))
            j = journal(root)
            self.assertEqual(j.open_transactions(), [])
            self.assertEqual(j.effective_transactions(), [])
        finally:
            tmp.cleanup()

    def test_mark_effective_failure_is_settled_by_recovery(self):
        # Round-3 missing test: canon holds the verified commit, the journal
        # write fails, and recovery settles it from the commit evidence.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            with mock.patch.object(ttj.TierTransactionJournal, "mark_effective",
                                   side_effect=RuntimeError("journal write failed (test)")):
                audit = self._do_apply(root, mods, bundle, ctx, "mark-eff")
            self.assertEqual(base.sql_tier_of(root, b), "C")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def test_recovery_marks_committed_txn_effective_even_when_row_changed(self):
        # Round-4 R4-1: a committed apply whose forward row a later job
        # changed must NOT be read as "no commit". The audit event is atomic
        # with the row, so it alone proves the apply. Expiring one leg of a
        # paired swap while its sibling goes effective splits the pair.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            with self.assertRaises(wmod._SimulatedCrash):
                self._do_apply(root, mods, bundle, ctx, "crash-r41",
                               _crash_after_commit=True)
            ids = [t["txn_id"] for t in journal(root).open_transactions()]
            self.assertEqual(len(ids), 2)
            # a later job changes b's committed row (e.g. an evidence repair)
            con = sqlite3.connect(str(base.db_path(root)))
            try:
                con.execute(
                    "UPDATE universe_membership SET tier='B', "
                    "coverage_obligation_tier='B', sql_tier='Tier B', "
                    "tier_decision_scope='tier_b_sql_first_review_scope' "
                    "WHERE ticker=?", (b,))
                con.commit()
            finally:
                con.close()
            # timeout has passed; the commit evidence must still win
            future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
            settled = wmod.recover_journal(journal(root, clock=lambda: future),
                                            base.db_path(root))
            self.assertEqual(len(settled), 2, settled)
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids}, {ttj.EFFECTIVE})
            self.assertEqual(j.open_transactions(), [])
            self.assertIsNone(j.lease(b))
            self.assertIsNone(j.lease(c))
        finally:
            tmp.cleanup()

    def test_failure_reading_post_commit_result_keys_is_compensated(self):
        # Round-4 NEW-4 residual: even reading the post-COMMIT result keys
        # stays guarded; a KeyError there is compensated (exit 4 with canon
        # restored and the journal blocked), never a bare escape that leaves
        # canon and journal split.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            real_apply = wmod.apply_transaction

            def apply_then_drop_result(*a, **k):
                n = real_apply(*a, **k)
                result = k.get("result")
                if result is not None:
                    result.pop("logical_after", None)
                return n

            before = base.logical(root)
            with mock.patch.object(wmod, "apply_transaction",
                                   apply_then_drop_result):
                with self.assertRaises(RuntimeError) as cm:
                    self._do_apply(root, mods, bundle, ctx, "no-after")
            self.assertIn("post_commit_failed_restored", str(cm.exception))
            self.assertEqual(base.logical(root), before)
            self.assertEqual(base.sql_tier_of(root, b), "B")
            self.assertEqual(base.sql_tier_of(root, c), "C")
            for d in bundle["decisions"]:
                self.assertIsNone(wmod.canon_decision_consumed(
                    base.db_path(root), d["owner_decision_id"]))
            j = journal(root)
            self.assertEqual(j.open_transactions(), [])
            self.assertEqual(j.effective_transactions(), [])
        finally:
            tmp.cleanup()

    def test_whole_db_rollback_holds_the_canon_write_lock(self):
        # Round-4 R4-3: the hash check, journal check and restore run under
        # ONE canon BEGIN IMMEDIATE; no other job can commit in the gap.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "lockhold")
            real_restore = wmod._locked_logical_restore
            observed = {}

            def restore_under_writer_lock(con, backup, expected):
                other = sqlite3.connect(str(base.db_path(root)), timeout=0.5)
                try:
                    other.execute("BEGIN IMMEDIATE")
                    observed["concurrent_write"] = "acquired"
                    other.rollback()
                except sqlite3.OperationalError:
                    observed["concurrent_write"] = "blocked"
                finally:
                    other.close()
                return real_restore(con, backup, expected)

            with mock.patch.object(wmod, "_locked_logical_restore",
                                   restore_under_writer_lock):
                result = wmod.do_rollback(base.db_path(root),
                                          Path(audit["rollback_path"]),
                                          wmod.staged_modules(root))
            self.assertEqual(observed["concurrent_write"], "blocked")
            self.assertEqual(result["status"], "rolled_back")
            self.assertEqual(base.sql_tier_of(root, b), "B")
            self.assertEqual(base.sql_tier_of(root, c), "C")
        finally:
            tmp.cleanup()

    def test_commit_attempted_after_rollback_hash_check_survives_restore(self):
        # Round-5 on R4-3: another job tries to commit right after the
        # current-state hash check. Under the one lock it must wait and land
        # AFTER the restore; in the old check-then-restore gap the restore
        # overwrote it.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "gapcommit")
            real_hash = wmod._logical_sha256_conn
            threads, observed = [], {}

            def hash_then_competing_commit(con):
                h = real_hash(con)
                if not threads:  # the first call is the pre-restore check
                    # a write attempted in the gap must be refused right now...
                    other = sqlite3.connect(str(base.db_path(root)), timeout=0.2)
                    try:
                        other.execute("BEGIN IMMEDIATE")
                        observed["gap_write"] = "acquired"
                        other.rollback()
                    except sqlite3.OperationalError:
                        observed["gap_write"] = "blocked"
                    finally:
                        other.close()
                    # ...and a competitor whose INSERT has started (trace
                    # callback fires as the statement begins, before it can
                    # take the write lock) must land after the restore
                    started = threading.Event()

                    def compete():
                        c2 = sqlite3.connect(str(base.db_path(root)), timeout=10)
                        c2.set_trace_callback(
                            lambda sql: started.set()
                            if sql.lstrip().upper().startswith("INSERT") else None)
                        try:
                            c2.execute(
                                "INSERT INTO audit_events(event_id,event_time_utc,"
                                "event_type,detail_json) VALUES ('between-backup-and-lock',"
                                "'2026-09-29T06:00:00Z','unrelated_test_commit','{}')")
                            c2.commit()
                        finally:
                            c2.close()
                    t = threading.Thread(target=compete)
                    t.start()
                    threads.append(t)
                    self.assertTrue(started.wait(5))
                return h

            with mock.patch.object(wmod, "_logical_sha256_conn",
                                   hash_then_competing_commit):
                result = wmod.do_rollback(base.db_path(root),
                                          Path(audit["rollback_path"]),
                                          wmod.staged_modules(root))
            threads[0].join(30)
            self.assertFalse(threads[0].is_alive())
            self.assertEqual(observed["gap_write"], "blocked")
            self.assertEqual(result["status"], "rolled_back")
            self.assertEqual(_unrelated_count(root), 1)  # not overwritten
            self.assertEqual(base.sql_tier_of(root, b), "B")
            self.assertEqual(base.sql_tier_of(root, c), "C")
        finally:
            tmp.cleanup()

    def test_whole_db_restore_replays_autoincrement_sequence(self):
        # Round-5 R5-2: iterdump already carries sqlite_sequence; replaying it
        # twice duplicated rows, so every restore of such a DB failed its hash.
        tmp = tempfile.TemporaryDirectory()
        try:
            backup = Path(tmp.name) / "backup.sqlite"
            live = Path(tmp.name) / "live.sqlite"
            for path, rows in ((backup, 2), (live, 3)):
                con = sqlite3.connect(str(path))
                con.execute("CREATE TABLE t(id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
                con.executemany("INSERT INTO t(v) VALUES (?)", [(str(i),) for i in range(rows)])
                con.commit()
                con.close()
            expected = wmod.snap.logical_sha256(backup)
            con = sqlite3.connect(str(live))
            try:
                con.execute("BEGIN IMMEDIATE")
                self.assertEqual(wmod._locked_logical_restore(con, backup, expected), expected)
                con.commit()
                self.assertEqual(con.execute("SELECT name, seq FROM sqlite_sequence").fetchall(),
                                 [("t", 2)])
            finally:
                con.close()
            self.assertEqual(wmod.snap.logical_sha256(live), expected)
            # documented fail-closed limit: a backup WITHOUT sqlite_sequence
            # cannot be matched by a live DB that has one -> refuse, no change
            plain = Path(tmp.name) / "plain.sqlite"
            con = sqlite3.connect(str(plain))
            con.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
            con.commit()
            con.close()
            live_before = wmod.snap.logical_sha256(live)
            con = sqlite3.connect(str(live))
            try:
                con.execute("BEGIN IMMEDIATE")
                with self.assertRaises(ValueError):
                    wmod._locked_logical_restore(con, plain, wmod.snap.logical_sha256(plain))
                con.rollback()
            finally:
                con.close()
            self.assertEqual(wmod.snap.logical_sha256(live), live_before)
        finally:
            tmp.cleanup()

    def test_audit_probes_require_the_exact_journal_txn_id(self):
        # Round-5 R5-1: LIKE treats '_' as a wildcard and folds case, so an
        # event for a different id matched. Only the exact id (and ticker) may.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            db = base.db_path(root)
            real_id = "tt_20260929T000000000000Z_%s_abcd1234" % b
            lookalike = real_id.replace("_", "X").upper()
            con = sqlite3.connect(str(db))
            try:
                for event_id, event_type, jid in (
                        ("r51-fwd", wmod.EVENT_TYPE, lookalike),
                        ("r51-inv:%s" % b, wmod.ROLLBACK_EVENT_TYPE, lookalike),
                        ("r51-other-ticker", wmod.EVENT_TYPE, real_id + "-other")):
                    con.execute(
                        "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                        " VALUES (?,?,?,?)",
                        (event_id, "2026-09-29T06:00:00Z", event_type,
                         json.dumps({"ticker": b, "journal_txn_id": jid,
                                     "owner_decision_id": "ODXR5XX"}, sort_keys=True)))
                con.commit()
            finally:
                con.close()
            txn = {"txn_id": real_id, "ticker": b}
            self.assertIsNone(wmod.canon_commit_probe(db)(txn))
            self.assertIsNone(wmod.canon_rollback_probe(db)(txn))
            self.assertIsNone(wmod.canon_decision_consumed(db, "OD_R5_X"))
            con = sqlite3.connect(str(db))
            try:
                con.execute(
                    "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                    " VALUES ('r51-exact-wrong-ticker','2026-09-29T06:00:00Z',?,?)",
                    (wmod.EVENT_TYPE, json.dumps({"ticker": c, "journal_txn_id": real_id,
                                                  "owner_decision_id": "OD_R5_X"},
                                                 sort_keys=True)))
                con.commit()
            finally:
                con.close()
            self.assertIsNone(wmod.canon_commit_probe(db)(txn))  # ticker must match too
            self.assertEqual(wmod.canon_decision_consumed(db, "OD_R5_X"),
                             "r51-exact-wrong-ticker")
            # round-6: type-exact (JSON true never equals 1) and bad JSON skipped
            con = sqlite3.connect(str(db))
            try:
                con.execute(
                    "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                    " VALUES ('r51-bool','2026-09-29T06:00:00Z',?,?)",
                    (wmod.EVENT_TYPE, json.dumps({"flag": True, "n": "1"})))
                con.execute(
                    "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                    " VALUES ('r51-badjson','2026-09-29T06:00:00Z',?,?)",
                    (wmod.EVENT_TYPE, '{"journal_txn_id": "%s", broken' % real_id))
                con.commit()
                self.assertEqual(wmod._audit_events_matching(con, wmod.EVENT_TYPE, "flag", 1), [])
                self.assertEqual([e for e, _ in wmod._audit_events_matching(
                    con, wmod.EVENT_TYPE, "journal_txn_id", real_id)],
                    ["r51-exact-wrong-ticker"])
            finally:
                con.close()
        finally:
            tmp.cleanup()

    def test_unreadable_journal_after_commit_exits_committed_unsettled(self):
        # Round-5 R5-3: the journal write fails AND the state read-back fails;
        # canon is committed, so that is exit 5, never a bare exit-4 escape.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            real_get = ttj.TierTransactionJournal.get
            armed = []

            def get_fails_once_armed(self_, *a, **k):
                if armed:
                    raise RuntimeError("journal read failed (test)")
                return real_get(self_, *a, **k)

            def mark_fails_and_arms(self_, *a, **k):
                armed.append(1)
                raise RuntimeError("journal write failed (test)")

            with mock.patch.object(ttj.TierTransactionJournal, "mark_effective",
                                   mark_fails_and_arms), \
                    mock.patch.object(ttj.TierTransactionJournal, "get",
                                      get_fails_once_armed):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    self._do_apply(root, mods, bundle, ctx, "unreadable")
            self.assertIn("committed_journal_unsettled", str(cm.exception))
            self.assertIn("unreadable", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "C")  # the commit held
        finally:
            tmp.cleanup()

    def test_whole_db_rollback_failure_after_restore_exits_committed_unsettled(self):
        # Round-5 R5-4: once the restore has committed, a guard failure is
        # exit 5 with the journal already settled; a journal failure is exit 5
        # too. Neither may read as "nothing changed" (exit 4).
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "r54-guard")
            staged = wmod.staged_modules(root)
            with mock.patch.object(staged["fsca"].FinanceSqlCanonAccess, "validate",
                                   return_value={"status": "error", "errors": ["test"]}):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_rollback(base.db_path(root), Path(audit["rollback_path"]), staged)
            self.assertIn("whole_db_restored_post_check_failed", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")  # restore held
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "r54-journal")
            with mock.patch.object(ttj.TierTransactionJournal, "mark_rolled_back",
                                   side_effect=RuntimeError("journal write failed (test)")):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_rollback(base.db_path(root), Path(audit["rollback_path"]),
                                     wmod.staged_modules(root))
            self.assertIn("whole_db_restored_journal_unsettled", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")
        finally:
            tmp.cleanup()

    def test_raised_commit_that_landed_is_treated_as_committed(self):
        # Round-6 R6-1: a raised COMMIT is not proof of abort. When canon
        # shows the commit, the apply carries on as committed (verified,
        # journal effective) instead of "canon unchanged" + blocked journal.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            with mock.patch.object(wmod, "_commit_or_prove_aborted", _commit_raising(True)):
                audit = self._do_apply(root, mods, bundle, ctx, "r61-landed")
            self.assertEqual(base.sql_tier_of(root, b), "C")
            self.assertEqual(base.sql_tier_of(root, c), "B")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def test_raised_commit_that_aborted_leaves_canon_unchanged(self):
        # Round-6 R6-1: when canon proves the abort, "canon unchanged" is true.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            before = base.logical(root)
            with mock.patch.object(wmod, "_commit_or_prove_aborted", _commit_raising(False)):
                with self.assertRaises(RuntimeError) as cm:
                    self._do_apply(root, mods, bundle, ctx, "r61-aborted")
            self.assertNotIsInstance(cm.exception, wmod._CommittedUnsettled)
            self.assertIn("commit raised (test)", str(cm.exception))
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual(j.open_transactions(), [])
            self.assertEqual(j.effective_transactions(), [])
        finally:
            tmp.cleanup()

    def test_commit_outcome_unknown_is_committed_unsettled(self):
        # Round-6 R6-1: if canon cannot be read after a raised COMMIT, the
        # outcome is unknown -> exit 5, never "our change absent".
        class _Con:
            def commit(self):
                raise sqlite3.OperationalError("commit raised (test)")

            def rollback(self):
                pass

        def probe_fails():
            raise sqlite3.OperationalError("canon unreadable (test)")
        with self.assertRaises(wmod._CommittedUnsettled) as cm:
            wmod._commit_or_prove_aborted(_Con(), probe_fails)
        self.assertIn("commit_outcome_unknown", str(cm.exception))
        with self.assertRaises(sqlite3.OperationalError):
            wmod._commit_or_prove_aborted(_Con(), lambda: False)
        wmod._commit_or_prove_aborted(_Con(), lambda: True)  # landed: no error

    def test_whole_db_rollback_raised_commit_that_landed_is_rolled_back(self):
        # Round-6 R6-1, whole-DB restore: the restore landed despite a raised
        # COMMIT, so the journal settles to canon. Round 8: a restore cannot be
        # attributed to THIS attempt from canon, so it is exit 5, not exit 0.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "r61-wholedb")
            with mock.patch.object(wmod, "_commit_or_prove_aborted", _commit_raising(True)):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_rollback(base.db_path(root), Path(audit["rollback_path"]),
                                     wmod.staged_modules(root))
            self.assertIn("canon_restored_unattributed", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_whole_db_landed_restore_survives_a_commit_before_the_probe(self):
        # Round-7 R7-1: after a durable but raised restore COMMIT another job
        # commits before the probe. A whole-DB hash probe then read "not
        # landed" (exit 4); the apply-events-absent probe is unaffected.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "r71-race")
            with mock.patch.object(wmod, "_commit_or_prove_aborted",
                                   _commit_raising(True, after=lambda: _unrelated_commit(root))):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_rollback(base.db_path(root), Path(audit["rollback_path"]),
                                     wmod.staged_modules(root))
            # never exit 4 ("nothing changed"): canon restored, journal settled
            self.assertIn("canon_restored_unattributed", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")
            self.assertEqual(_unrelated_count(root), 1)
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_whole_db_raised_commit_that_aborted_changes_nothing(self):
        # Round-8: apply events still present = no restore of this apply
        # committed (ours included) -> proven abort, exit 4 is the truth.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "r8-wholedb-abort")
            before = base.logical(root)
            with mock.patch.object(wmod, "_commit_or_prove_aborted", _commit_raising(False)):
                with self.assertRaises(sqlite3.OperationalError):
                    wmod.do_rollback(base.db_path(root), Path(audit["rollback_path"]),
                                     wmod.staged_modules(root))
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def test_whole_db_rollback_refuses_a_file_that_omits_a_sibling(self):
        # Round-8 R8-1: a rollback file trimmed to one leg of a two-ticker apply
        # keeps valid hashes, but would restore both tickers and settle one
        # journal txn. Canon's own events define the complete apply -> refuse
        # before any change.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            audit = self._do_apply(root, mods, bundle, ctx, "r81")
            doc = json.loads(Path(audit["rollback_path"]).read_text(encoding="utf-8"))
            staged = wmod.staged_modules(root)
            before = base.logical(root)
            # round 10: a substitute backup, internally consistent in the file
            other = root / "tmp" / "r10-substitute-backup.sqlite"
            con = sqlite3.connect(str(other))
            con.execute("CREATE TABLE t(v TEXT)")
            con.commit()
            con.close()
            other_hash = wmod.snap.logical_sha256(other)

            def substitute_backup(d):
                d["backup_path"] = str(other)
                d["backup_logical_sha256"] = d["db_logical_sha256_before"] = other_hash

            incomplete = "not_the_complete_apply"
            variants = {
                "decision_and_journal_trimmed": (incomplete, lambda d: (
                    d.__setitem__("decisions", [x for x in d["decisions"] if x["ticker"] == b]),
                    d.__setitem__("journal_txn_ids", {b: d["journal_txn_ids"][b]}))),
                "journal_trimmed_only": (incomplete, lambda d: d.__setitem__(
                    "journal_txn_ids", {b: d["journal_txn_ids"][b]})),
                "foreign_journal_id": (incomplete, lambda d: d["journal_txn_ids"].__setitem__(
                    c, "tt_not_ours")),
                # round 9: decision records themselves must be canon's own
                "duplicate_decision": (incomplete, lambda d: d["decisions"].append(
                    dict(d["decisions"][0]))),
                "same_ticker_other_owner_decision": (incomplete, lambda d: d["decisions"][0]
                                                     .__setitem__("owner_decision_id", "OD_X")),
                "same_ticker_other_transition": (incomplete, lambda d: d["decisions"][1]
                                                 .__setitem__("to_tier", "A")),
                # round 10: ANY decision difference, and the backup itself
                "decision_key_changed": (incomplete, lambda d: d["decisions"][0]
                                         .__setitem__("decision", "rejected")),
                "decision_key_removed": (incomplete, lambda d: d["decisions"][0].pop("decision")),
                "substituted_backup": ("rollback_backup_not_canon_attested", substitute_backup),
            }
            for name, (expected, trim) in variants.items():
                bad = json.loads(json.dumps(doc))
                trim(bad)
                path = root / "tmp" / ("r81-%s.json" % name)
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(wmod.Refusal, msg=name) as cm:
                    wmod.do_rollback(base.db_path(root), path, staged)
                self.assertIn(expected, str(cm.exception), name)
                self.assertEqual(base.logical(root), before, name)
            # round 10: another job commits after the apply; a file whose
            # after-hash is moved to cover it would erase that commit
            _unrelated_commit(root)
            moved = json.loads(json.dumps(doc))
            moved["db_logical_sha256_after"] = wmod.snap.logical_sha256(base.db_path(root))
            path = root / "tmp" / "r10-moved-after.json"
            path.write_text(json.dumps(moved), encoding="utf-8")
            with self.assertRaises(wmod.Refusal) as cm:
                wmod.do_rollback(base.db_path(root), path, staged)
            self.assertIn("rollback_after_state_unattested", str(cm.exception))
            self.assertEqual(_unrelated_count(root), 1)
            # the genuine file still restores? no: canon moved on, so it is
            # refused as a state mismatch -- never a silent overwrite
            with self.assertRaises(wmod.Refusal) as cm:
                wmod.do_rollback(base.db_path(root), Path(audit["rollback_path"]), staged)
            self.assertIn("rollback_current_state_mismatch", str(cm.exception))
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in audit["journal_txn_ids"].values()},
                             {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def test_landed_probe_is_bound_to_exact_events(self):
        # Round-7 R7-1: only THIS attempt's exact event ids with their journal
        # ids count; a prefix-colliding event never does; a partial set or a
        # foreign journal id is impossible for one COMMIT and raises.
        tmp = base.copy_staged()
        try:
            root = Path(tmp.name) / "root"
            db = base.db_path(root)
            con = sqlite3.connect(str(db))
            try:
                for event_id, jid in (("txn_R7:AAA", "tt_a"), ("txn_R7:AAAX", "tt_a"),
                                      ("txn_R7:ZZZ", "tt_z"), ("txn_R7:FOREIGN", "tt_other")):
                    con.execute(
                        "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                        " VALUES (?,?,?,?)", (event_id, "2026-09-29T06:00:00Z", wmod.EVENT_TYPE,
                                              json.dumps({"journal_txn_id": jid})))
                con.commit()
            finally:
                con.close()
            present = wmod._exact_events_present
            self.assertTrue(present(db, wmod.EVENT_TYPE, {"txn_R7:AAA": "tt_a"}))
            self.assertFalse(present(db, wmod.EVENT_TYPE, {"txn_R7:BBB": "tt_b"}))  # prefix ignored
            self.assertFalse(present(db, wmod.ROLLBACK_EVENT_TYPE, {"txn_R7:AAA": "tt_a"}))
            self.assertFalse(present(db, wmod.EVENT_TYPE, {}))
            with self.assertRaises(RuntimeError):
                present(db, wmod.EVENT_TYPE, {"txn_R7:AAA": "tt_a", "txn_R7:BBB": "tt_b"})
            with self.assertRaises(RuntimeError):
                present(db, wmod.EVENT_TYPE, {"txn_R7:FOREIGN": "tt_mine"})
        finally:
            tmp.cleanup()

    def test_compensation_connect_failure_after_commit_exits_committed_unsettled(self):
        # Round-7 R7-2: verification fails after COMMIT and the compensation
        # cannot even open canon -> exit 5 with the apply still present.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            armed = []
            with mock.patch.object(wmod, "_commit_or_prove_aborted",
                                   _commit_then(lambda: armed.append(1))), \
                    mock.patch.object(wmod.sqlite3, "connect",
                                      _canon_connect_fails_when(root, armed)):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    self._do_apply(root, mods, bundle, ctx, "r72",
                                   _force_verify_fail=True)
            self.assertIn("compensation_connect_failed", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "C")  # apply still present
        finally:
            tmp.cleanup()

    def test_whole_db_rollback_refused_when_backup_missed_commits_before_lock(self):
        # Round-3 missing test: restoring a backup older than the lock state
        # would destroy another job's commit, so --rollback refuses.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            with mock.patch.object(wmod.snap, "wal_safe_backup",
                                   _backup_then_unrelated_commit(root)):
                audit = self._do_apply(root, mods, bundle, ctx, "missed")
            self.assertFalse(audit["backup_matches_lock_state"])
            before = base.logical(root)
            proc = base.run_writer(root, "--rollback", audit["rollback_path"],
                                   "--backup-path", str(root / "tmp" / "missed-rb" / "b.sqlite"))
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("rollback_backup_missed_commits_before_lock", proc.stdout)
            self.assertEqual(base.logical(root), before)
            self.assertEqual(_unrelated_count(root), 1)
        finally:
            tmp.cleanup()

    def test_preflight_refusal_does_not_consume_decisions(self):
        # Re-review N3: an operator path error must not burn owner decisions.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            out = root / "tmp" / "typo"
            out.mkdir(parents=True)
            (out / "a.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(wmod.Refusal) as cm:
                wmod.do_apply(root, base.db_path(root), bundle, ctx, mods,
                              out / "backup.sqlite", out / "a.json", out / "r.json", out)
            self.assertIn("proof_path_already_exists", str(cm.exception))
            con = sqlite3.connect(str(journal(root).path))
            try:
                for d in bundle["decisions"]:
                    self.assertEqual(con.execute(
                        "SELECT COUNT(*) FROM transactions WHERE decision_id=?",
                        (d["owner_decision_id"],)).fetchone()[0], 0)
            finally:
                con.close()
            audit = self._do_apply(root, mods, bundle, ctx, "retry")
            self.assertEqual(set(audit["journal_txn_ids"]), {b, c})
        finally:
            tmp.cleanup()

    def test_recovery_waits_for_the_canon_write_lock(self):
        # Re-review N2: expiry cannot interleave with a writer's check-to-commit.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            fam = wmod.snapshot_rows(base.db_path(root), [c])["families"][c]
            past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5)
            stale = journal(root, clock=lambda: past).open(
                ticker=c, from_tier="C", to_tier="B", prior_family=fam,
                forward_family={**fam, "tier": "B"}, decision_id="stale-lock-decision",
                decision_sha256="x", holder="old-writer")
            writer = sqlite3.connect(str(base.db_path(root)))
            writer.execute("BEGIN IMMEDIATE")  # a writer between check and commit
            done = []
            worker = threading.Thread(
                target=lambda: done.append(wmod.recover_journal(journal(root), base.db_path(root))))
            worker.start()
            worker.join(1.5)
            self.assertTrue(worker.is_alive(), "recovery must wait for the canon lock")
            self.assertEqual(journal(root).get(stale["txn_id"])["state"], ttj.PENDING)
            writer.rollback()
            writer.close()
            worker.join(30)
            self.assertFalse(worker.is_alive())
            self.assertEqual(journal(root).get(stale["txn_id"])["state"], ttj.EXPIRED)
        finally:
            tmp.cleanup()

    def test_non_refusal_preflight_failure_settles_journal(self):
        # QA F5: an OSError before the canon transaction must not strand
        # pending txns, held leases and burned decisions.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            before = base.logical(root)

            def boom(*_a, **_k):
                raise OSError("disk full (test)")
            with mock.patch.object(wmod.snap, "wal_safe_backup", boom):
                with self.assertRaises(RuntimeError) as cm:
                    self._do_apply(root, mods, bundle, ctx, "oserr")
            self.assertIn("disk full", str(cm.exception))
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual(j.open_transactions(), [])
            self.assertIsNone(j.lease(b))
            self.assertIsNone(j.lease(c))
        finally:
            tmp.cleanup()

    def test_do_apply_enforces_owner_decision_binding(self):
        # QA F9: binding is enforced inside do_apply, not only in main().
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            bundle["decisions"][1]["card_id"] = "card_tampered"
            before = base.logical(root)
            with self.assertRaises(wmod.Refusal) as cm:
                self._do_apply(root, mods, bundle, ctx, "unbound")
            self.assertIn("owner_decision_refused", str(cm.exception))
            self.assertEqual(base.logical(root), before)
            self.assertFalse((root / ttj.JOURNAL_REL).exists())
        finally:
            tmp.cleanup()

    def test_decision_stays_single_use_if_journal_is_lost(self):
        # QA F10: canon audit events are a second consumption record.
        tmp = base.copy_staged()
        try:
            root, b, c, mods, bundle, ctx = self._in_process(tmp.name)
            self._do_apply(root, mods, bundle, ctx, "first")
            did = bundle["decisions"][0]["owner_decision_id"]
            self.assertIsNotNone(wmod.canon_decision_consumed(base.db_path(root), did))
            (root / ttj.JOURNAL_REL).unlink()
            before = base.logical(root)
            with self.assertRaises(wmod.Refusal) as cm:
                self._do_apply(root, mods, bundle, ctx, "replay")
            self.assertIn("decision_already_consumed_in_canon:%s" % did, str(cm.exception))
            self.assertEqual(base.logical(root), before)
        finally:
            tmp.cleanup()

    def test_verify_failure_restores_and_blocks_journal(self):
        tmp = base.copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = base.TestConcurrencyAndRestore._prep(None, root, tmp.name)
            before = base.logical(root)
            out = root / "tmp" / "vf"
            with self.assertRaises(RuntimeError) as cm:
                wmod.do_apply(root, base.db_path(root), bundle, ctx, mods,
                              out / "backup.sqlite", out / "a.json", out / "r.json", out,
                              _force_verify_fail=True)
            self.assertIn("post_apply_failed_restored", str(cm.exception))
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual(j.open_transactions(), [])
            self.assertIsNone(j.lease(b))
        finally:
            tmp.cleanup()


class TestInverseRollback(unittest.TestCase):
    def _applied(self, tmpdir):
        root, b, c, dec = swap_setup(tmpdir)
        proc, out = apply_swap(root, dec)
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])
        return root, b, c, json.loads(proc.stdout)["audit"]["journal_txn_ids"], out

    def test_inverse_rollback_preserves_unrelated_later_writes(self):
        tmp = base.copy_staged()
        try:
            root, b, c, ids, out = self._applied(tmp.name)
            # A later, unrelated commit (e.g. the freshness job) that a
            # whole-file restore would destroy.
            con = sqlite3.connect(str(base.db_path(root)))
            try:
                con.execute("INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json)"
                            " VALUES ('later-unrelated','2026-09-28T20:00:00Z','unrelated_test_commit','{}')")
                con.commit()
            finally:
                con.close()
            whole = base.run_writer(root, "--rollback", str(out / "tier_rollback.json"))
            self.assertEqual(whole.returncode, 2)
            self.assertIn("rollback_current_state_mismatch", whole.stdout)
            proc = base.run_writer(root, "--rollback-txn", ids[b], "--rollback-txn", ids[c],
                                   "--backup-path", str(root / "tmp" / "inv" / "backup.sqlite"))
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])
            body = json.loads(proc.stdout)
            self.assertEqual(body["status"], "rolled_back_inverse")
            self.assertEqual(body["tier_breakdown"], {"A": 15, "B": 17})
            self.assertEqual(base.sql_tier_of(root, b), "B")
            self.assertEqual(base.sql_tier_of(root, c), "C")
            con = sqlite3.connect(str(base.db_path(root)))
            try:
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE event_id='later-unrelated'").fetchone()[0], 1)
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE event_type=?",
                    (wmod.ROLLBACK_EVENT_TYPE,)).fetchone()[0], 2)
            finally:
                con.close()
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.ROLLED_BACK})
            mods = wmod.staged_modules(root)
            self.assertEqual(mods["fsca"].FinanceSqlCanonAccess(base.db_path(root)).validate()["status"], "ok")
            # Rolled back once; a second attempt refuses.
            again = base.run_writer(root, "--rollback-txn", ids[b], "--rollback-txn", ids[c])
            self.assertEqual(again.returncode, 2)
            self.assertIn("not_effective", again.stdout)
        finally:
            tmp.cleanup()

    def test_half_of_a_swap_cannot_be_rolled_back_alone(self):
        # QA F2: BOTH legs, including the one that would not breach a cap.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            before = base.logical(root)
            for leg, other in ((b, c), (c, b)):
                proc = base.run_writer(root, "--rollback-txn", ids[leg], "--backup-path",
                                       str(root / "tmp" / ("half-" + leg) / "backup.sqlite"))
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertIn("inverse_rollback_incomplete_canon_transaction", proc.stdout)
                self.assertIn(ids[other], proc.stdout)
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def test_cap_is_checked_on_counts_read_under_the_lock(self):
        # QA F8: an unrelated C->B write after the swap leaves B=18 once the
        # swap is undone; the count read inside the write lock catches it.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            other_c = base.pick_c_with_band(root)
            con = sqlite3.connect(str(base.db_path(root)))
            try:
                con.execute("UPDATE universe_membership SET tier='B' WHERE ticker=?", (other_c,))
                con.commit()
            finally:
                con.close()
            before = base.logical(root)
            proc = base.run_writer(root, "--rollback-txn", ids[b], "--rollback-txn", ids[c])
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("inverse_rollback_cap_breach:A=15 B=18", proc.stdout)
            self.assertEqual(base.logical(root), before)
        finally:
            tmp.cleanup()

    def test_later_transaction_on_ticker_blocks_rollback(self):
        # QA F3: an A-B-A history must not let an old txn clobber a newer one.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            fam = wmod.snapshot_rows(base.db_path(root), [c])["families"][c]
            j = journal(root)
            later = j.open(
                ticker=c, from_tier="B", to_tier="C", prior_family=fam,
                forward_family={**fam, "tier": "C"}, decision_id="later-decision",
                decision_sha256="x", holder=wmod.writer_holder())
            before = base.logical(root)
            for state in ("pending", "effective"):
                proc = base.run_writer(root, "--rollback-txn", ids[b], "--rollback-txn", ids[c],
                                       "--backup-path", str(root / "tmp" / state / "backup.sqlite"))
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertIn("inverse_rollback_later_transaction_on_ticker:%s" % c, proc.stdout)
                self.assertIn(later["txn_id"], proc.stdout)
                j.mark_effective(later["txn_id"], {"canon_transaction_id": "test"})
            self.assertEqual(base.logical(root), before)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def _assert_inverse_undone_keeping_unrelated(self, root, b, c, ids, exc):
        self.assertIn("inverse_rollback_failed_restored", str(exc))
        self.assertEqual(_unrelated_count(root), 1, "another job's commit was destroyed")
        self.assertEqual(base.sql_tier_of(root, b), "C")  # forward values back
        self.assertEqual(base.sql_tier_of(root, c), "B")
        con = sqlite3.connect(str(base.db_path(root)))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM audit_events WHERE event_type=?",
                                         (wmod.ROLLBACK_EVENT_TYPE,)).fetchone()[0], 0)
        finally:
            con.close()
        self.assertEqual({journal(root).get(t)["state"] for t in ids.values()}, {ttj.EFFECTIVE})

    def test_commit_between_backup_and_lock_survives_failed_inverse(self):
        # QA F4 / re-review N1 (inverse path, backup-to-lock window).
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            with mock.patch.object(wmod.snap, "wal_safe_backup",
                                   _backup_then_unrelated_commit(root)):
                with self.assertRaises(RuntimeError) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                             wmod.staged_modules(root),
                                             root / "tmp" / "inv-race" / "backup.sqlite",
                                             _force_verify_fail=True)
            self._assert_inverse_undone_keeping_unrelated(root, b, c, ids, cm.exception)
        finally:
            tmp.cleanup()

    def test_commit_after_inverse_commit_survives_failed_inverse(self):
        # Re-review N1 (inverse path, after-COMMIT window).
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            mods = wmod.staged_modules(root)
            cls = mods["fsca"].FinanceSqlCanonAccess
            real_validate = cls.validate
            calls = []

            def validate(self_):
                calls.append(1)
                if len(calls) == 1:  # the pre-lock guard check
                    return real_validate(self_)
                _unrelated_commit(root)
                return {"status": "error", "errors": ["test"]}
            with mock.patch.object(cls, "validate", validate):
                with self.assertRaises(RuntimeError) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]], mods,
                                             root / "tmp" / "inv-post" / "backup.sqlite")
            self._assert_inverse_undone_keeping_unrelated(root, b, c, ids, cm.exception)
        finally:
            tmp.cleanup()

    def test_crash_after_inverse_commit_is_settled_by_recovery(self):
        # QA F7.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            with self.assertRaises(wmod._SimulatedCrash):
                wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                         wmod.staged_modules(root),
                                         root / "tmp" / "inv-crash" / "backup.sqlite",
                                         _crash_after_commit=True)
            self.assertEqual(base.sql_tier_of(root, c), "C")  # inverse committed
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.EFFECTIVE})
            proc = base.run_writer(root, "--recover")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            settled = json.loads(proc.stdout)["settled"]
            self.assertEqual({(s["txn_id"], s["state"]) for s in settled},
                             {(t, ttj.ROLLED_BACK) for t in ids.values()})
        finally:
            tmp.cleanup()

    def test_recovery_marking_rolled_back_blocks_inverse_compensation(self):
        # Round-3 NEW-1: a concurrent --recover marks the txns rolled_back from
        # the inverse event before the undo. Compensation must not restore the
        # forward values underneath a rolled_back journal.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            mods = wmod.staged_modules(root)
            cls = mods["fsca"].FinanceSqlCanonAccess
            real_validate = cls.validate
            calls = []

            def validate(self_):
                calls.append(1)
                if len(calls) == 1:  # the pre-lock guard check
                    return real_validate(self_)
                wmod.recover_journal(journal(root), base.db_path(root))
                return {"status": "error", "errors": ["test"]}
            with mock.patch.object(cls, "validate", validate):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]], mods,
                                             root / "tmp" / "inv-recovered" / "backup.sqlite")
            self.assertIn("inverse_committed_unverified_journal", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")  # inverse kept
            self.assertEqual(base.sql_tier_of(root, c), "C")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_mark_rolled_back_failure_exits_committed_unsettled(self):
        # Round-3 NEW-2: the inverse is committed and verified but the journal
        # cannot record it; that is exit 5, never "our change absent" (exit 4).
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            with mock.patch.object(ttj.TierTransactionJournal, "mark_rolled_back",
                                   side_effect=RuntimeError("journal write failed (test)")):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                             wmod.staged_modules(root),
                                             root / "tmp" / "inv-jfail" / "backup.sqlite")
            self.assertIn("inverse_committed_journal_unsettled", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")
            proc = base.run_writer(root, "--recover")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_transient_mark_rolled_back_failure_is_settled_by_recovery(self):
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            real = ttj.TierTransactionJournal.mark_rolled_back
            calls = []

            def flaky(self_, *a, **k):
                calls.append(1)
                if len(calls) == 1:
                    raise RuntimeError("journal write failed once (test)")
                return real(self_, *a, **k)
            with mock.patch.object(ttj.TierTransactionJournal, "mark_rolled_back", flaky):
                result = wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                                  wmod.staged_modules(root),
                                                  root / "tmp" / "inv-flaky" / "backup.sqlite")
            self.assertEqual(result["status"], "rolled_back_inverse")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_inverse_proof_build_failure_exits_committed_unsettled(self):
        # Round-4 R4-2: the inverse is committed and the journal settled; a
        # failure building the success proof is committed-unsettled (exit 5),
        # never a plain failure that reads as "our change absent" (exit 4).
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            real_backup = wmod.snap.wal_safe_backup

            class _ProofFailure(dict):
                def __getitem__(self, key):
                    if key == "backup_path":
                        raise KeyError("proof build failed (test)")
                    return super().__getitem__(key)

            def exploding_backup(db, path):
                return _ProofFailure(real_backup(db, path))

            with mock.patch.object(wmod.snap, "wal_safe_backup", exploding_backup):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root),
                                              [ids[b], ids[c]],
                                              wmod.staged_modules(root),
                                              root / "tmp" / "inv-proof" / "backup.sqlite")
            self.assertIn("inverse_committed_proof_failed", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")  # inverse held
            self.assertEqual(base.sql_tier_of(root, c), "C")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()},
                             {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_unreadable_journal_after_inverse_commit_exits_committed_unsettled(self):
        # Round-5 R5-3, inverse path: journal write and read-back both fail
        # after the inverse COMMIT -> exit 5, not a bare exit-4 escape.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            real_get = ttj.TierTransactionJournal.get
            armed = []

            def get_fails_once_armed(self_, *a, **k):
                if armed:
                    raise RuntimeError("journal read failed (test)")
                return real_get(self_, *a, **k)

            def mark_fails_and_arms(self_, *a, **k):
                armed.append(1)
                raise RuntimeError("journal write failed (test)")

            with mock.patch.object(ttj.TierTransactionJournal, "mark_rolled_back",
                                   mark_fails_and_arms), \
                    mock.patch.object(ttj.TierTransactionJournal, "get",
                                      get_fails_once_armed):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                             wmod.staged_modules(root),
                                             root / "tmp" / "inv-unread" / "backup.sqlite")
            self.assertIn("inverse_committed_journal_unsettled", str(cm.exception))
            self.assertIn("unreadable", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")  # inverse held
        finally:
            tmp.cleanup()

    def test_inverse_raised_commit_that_landed_is_rolled_back(self):
        # Round-6 R6-1, inverse path: canon holds the inverse despite a
        # raised COMMIT -> verified and settled, not exit 4.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            with mock.patch.object(wmod, "_commit_or_prove_aborted", _commit_raising(True)):
                result = wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                                  wmod.staged_modules(root),
                                                  root / "tmp" / "inv-r61" / "backup.sqlite")
            self.assertEqual(result["status"], "rolled_back_inverse")
            self.assertEqual(base.sql_tier_of(root, b), "B")
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.ROLLED_BACK})
        finally:
            tmp.cleanup()

    def test_inverse_compensation_connect_failure_exits_committed_unsettled(self):
        # Round-7 R7-2, inverse path.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            armed = []
            with mock.patch.object(wmod, "_commit_or_prove_aborted",
                                   _commit_then(lambda: armed.append(1))), \
                    mock.patch.object(wmod.sqlite3, "connect",
                                      _canon_connect_fails_when(root, armed)):
                with self.assertRaises(wmod._CommittedUnsettled) as cm:
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                             wmod.staged_modules(root),
                                             root / "tmp" / "inv-r72" / "backup.sqlite",
                                             _force_verify_fail=True)
            self.assertIn("inverse_compensation_connect_failed", str(cm.exception))
            self.assertEqual(base.sql_tier_of(root, b), "B")  # inverse still present
        finally:
            tmp.cleanup()

    def test_inverse_raised_commit_that_aborted_changes_nothing(self):
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            before = base.logical(root)
            with mock.patch.object(wmod, "_commit_or_prove_aborted", _commit_raising(False)):
                with self.assertRaises(sqlite3.OperationalError):
                    wmod.do_inverse_rollback(root, base.db_path(root), [ids[b], ids[c]],
                                             wmod.staged_modules(root),
                                             root / "tmp" / "inv-r61a" / "backup.sqlite")
            self.assertEqual(base.logical(root), before)
            j = journal(root)
            self.assertEqual({j.get(t)["state"] for t in ids.values()}, {ttj.EFFECTIVE})
        finally:
            tmp.cleanup()

    def test_whole_db_rollback_checks_journal_before_restoring(self):
        # QA F12: a journal refusal must come before the restore, not after.
        tmp = base.copy_staged()
        try:
            root, b, c, ids, out = self._applied(tmp.name)
            journal(root).mark_rolled_back(ids[b], {"reason": "test_inconsistent_journal"})
            before = base.logical(root)
            proc = base.run_writer(root, "--rollback", str(out / "tier_rollback.json"))
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("rollback_journal_txn_not_effective:%s" % ids[b], proc.stdout)
            self.assertEqual(base.logical(root), before)
        finally:
            tmp.cleanup()

    def test_row_changed_since_commit_refuses(self):
        tmp = base.copy_staged()
        try:
            root, b, c, ids, _ = self._applied(tmp.name)
            con = sqlite3.connect(str(base.db_path(root)))
            try:
                con.execute("UPDATE universe_membership SET decision_grade_eligible=0 WHERE ticker=?", (c,))
                con.commit()
            finally:
                con.close()
            before = base.logical(root)
            proc = base.run_writer(root, "--rollback-txn", ids[b], "--rollback-txn", ids[c])
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("row_changed_since_commit:%s" % c, proc.stdout)
            self.assertEqual(base.logical(root), before)
            self.assertEqual(base.sql_tier_of(root, b), "C")
        finally:
            tmp.cleanup()


class TestCutoverGate(unittest.TestCase):
    def _production_copy(self):
        """A temp root WITHOUT the hermetic marker: it is treated as production."""
        tmp = base.copy_staged()
        root = Path(tmp.name) / "root"
        (root / ".p42-hermetic-test-root").unlink()
        return tmp, root

    def test_production_apply_blocked_without_cutover(self):
        tmp, root = self._production_copy()
        try:
            b = base.pick_b_ticker(root)
            c = base.pick_c_with_band(root)
            base.inject_onboarding(root, c)
            dec = base.write_decision(tmp.name, [base.approved(b, "B", "C"), base.approved(c, "C", "B")])
            before = base.logical(root)
            dry = base.run_writer(root, "--decision-file", str(dec))
            plan = json.loads(dry.stdout)
            self.assertEqual(plan["authority"]["activation_status"], "blocked")
            self.assertIn("cutover_not_approved", plan["authority"]["activation_context_or_block_reason"])
            proc, _ = apply_swap(root, dec)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("activation_blocked:cutover_not_approved", proc.stdout)
            rec = base.run_writer(root, "--rollback-txn", "tt_anything")
            self.assertIn("cutover_not_approved", rec.stdout)
            # QA F1: recovery writes the journal, so it is gated too.
            for extra in ((), ("--after-crash",)):
                recovered = base.run_writer(root, "--recover", *extra)
                self.assertEqual(recovered.returncode, 2, recovered.stdout)
                self.assertIn("cutover_not_approved", recovered.stdout)
            self.assertEqual(base.logical(root), before)
            self.assertFalse((root / ttj.JOURNAL_REL).exists())
        finally:
            tmp.cleanup()

    def test_production_apply_runs_once_cutover_is_approved(self):
        tmp, root = self._production_copy()
        try:
            b = base.pick_b_ticker(root)
            c = base.pick_c_with_band(root)
            base.inject_onboarding(root, c)
            dec = base.write_decision(tmp.name, [base.approved(b, "B", "C"), base.approved(c, "C", "B")])
            gate = root / tod.CUTOVER_REL
            gate.parent.mkdir(parents=True, exist_ok=True)
            gate.write_text(json.dumps({
                "id": tod.CUTOVER_ID, "active": True, "covers": ["tier_membership_writer"],
                "granted_by": "Randall", "granted_at": "2026-10-16T09:00:00-07:00",
                "grant_text": "test fixture cutover"}), encoding="utf-8")
            proc, _ = apply_swap(root, dec)
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])
            audit = json.loads(proc.stdout)["audit"]
            self.assertEqual(audit["authority"]["activation_context"], "production_cutover")
            self.assertEqual(base.sql_tier_of(root, c), "B")
            # Re-review N4: no whole-DB restore on a live canon.
            rb = base.run_writer(root, "--rollback", audit["rollback_path"])
            self.assertEqual(rb.returncode, 2, rb.stdout)
            self.assertIn("whole_db_rollback_hermetic_only", rb.stdout)
            self.assertEqual(base.sql_tier_of(root, c), "B")
        finally:
            tmp.cleanup()

    def test_live_canon_mutation_is_not_allowed(self):
        db = LIVE_ROOT / "state" / "finance" / "finance-canon.sqlite"
        allowed, why = wmod.mutation_allowed(LIVE_ROOT, db)
        self.assertFalse(allowed)
        self.assertIn("cutover_not_approved", why)
        self.assertFalse((LIVE_ROOT / tod.CUTOVER_REL).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
