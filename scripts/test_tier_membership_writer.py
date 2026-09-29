#!/usr/bin/env python3
"""Hermetic tests for tier_membership_writer r3 (P4-2 slice C).

Every test copies staged-root to a fresh tempdir (quiesced fixture DB)
and runs the writer with cwd = that copy and --root = that copy;
staged-root itself is never modified. Decision files live outside the
copied root. No live-DB writes, no network. The writer is never run
against the live canon here.

Backup/restore go only through the shared scripts/sqlite_snapshot.py
WAL-safe owner; proofs are logical (WAL-inclusive) hashes, never file copies
or file shas.

Covers: dry-run writes nothing; valid swap applies with exact witnesses,
guard ok, breakdown 15/17; all refusal classes with the logical DB
unchanged; T1 reader-held restore; T2 concurrent-change refusal; T5
per-statement rowcount; T7 accepted_at + proposal-packet binding;
rollback restores the exact logical content.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["VERITAS_P42_TEST_ONLY_ACTIVATION"] = "1"

V2_DIR = Path(__file__).resolve().parent
ROOT = V2_DIR.parent
WRITER = V2_DIR / "tier_membership_writer.py"
STAGED = ROOT / "tmp" / "p4-2-writer-lane-20260927" / "staged-root"
AS_OF = "2026-09-27"

sys.path.insert(0, str(V2_DIR))
import tier_membership_writer as wmod  # noqa: E402
import sqlite_snapshot as snap  # noqa: E402


def copy_staged() -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory(prefix="p42-c1-")
    dst = Path(tmp.name) / "root"
    shutil.copytree(STAGED, dst)
    (dst / ".p42-hermetic-test-root").write_text(
        "temporary fixture only\n", encoding="utf-8")
    fin = dst / "state" / "finance"
    for sidecar in ("finance-canon.sqlite-shm", "finance-canon.sqlite-wal"):
        p = fin / sidecar
        if p.exists():
            p.unlink()
    return tmp


def db_path(root: Path) -> Path:
    return root / "state" / "finance" / "finance-canon.sqlite"


def logical(root: Path) -> str:
    return snap.logical_sha256(db_path(root))


def snapshot_tree(root: Path) -> dict:
    # *-shm / *-wal excluded: the guarded read-only path materializes
    # empty sidecars on any WAL open; they carry no canon content. The
    # main db file is compared logically (WAL-inclusive), and callers
    # additionally assert the -wal carries no frames.
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.endswith(("-shm", "-wal")):
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            out[p.relative_to(root).as_posix()] = h.hexdigest()
    return out


def assert_no_wal_frames(root: Path) -> None:
    wal = db_path(root).parent / (db_path(root).name + "-wal")
    if wal.exists():
        assert wal.stat().st_size == 0, wal.stat().st_size


def run_writer(root: Path, *extra) -> subprocess.CompletedProcess:
    argv = list(extra)
    if "--decision-file" in argv and "--proposal-packet" not in argv:
        decision_path = Path(argv[argv.index("--decision-file") + 1])
        doc = json.loads(decision_path.read_text(encoding="utf-8"))
        packet_path = root / "tmp" / "test-proposal-packet.json"
        if packet_path.is_file():
            sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            if all(d.get("proposal_packet_sha256") == sha
                   for d in doc["decisions"]):
                argv.extend(["--proposal-packet", str(packet_path)])
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["VERITAS_P42_TEST_ONLY_ACTIVATION"] = "1"
    return subprocess.run(
        [sys.executable, str(WRITER), "--root", str(root),
         "--db", str(db_path(root)), *argv],
        capture_output=True, text=True, env=env, cwd=str(root))


def write_owner_decisions(root: Path, decisions: list[dict]) -> None:
    """P4-3 fixture: record an owner decision matching each entry exactly.

    Entries that already carry an ``owner_decision_id`` key (including None,
    for negative tests) are left alone.
    """
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    base = root / "state" / "finance" / "tier-decisions"
    base.mkdir(parents=True, exist_ok=True)
    for d in decisions:
        if "owner_decision_id" in d:
            continue
        did = "test-%s-%s%s-%s" % (str(d.get("ticker", "x")).lower(),
                                   str(d.get("from_tier", "")).lower(),
                                   str(d.get("to_tier", "")).lower(),
                                   str(d.get("card_id", "card")).lower()[:24])
        did = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in did)
        d["owner_decision_id"] = did
        (base / ("%s.json" % did)).write_text(json.dumps({
            "schema": "veritas.tier_owner_decision.v1",
            "decision_id": did, "decision": "approved",
            "ticker": str(d.get("ticker", "")).upper(),
            "from_tier": str(d.get("from_tier", "")).upper(),
            "to_tier": str(d.get("to_tier", "")).upper(),
            "card_id": d.get("card_id") or "missing",
            "proposal_packet_sha256": d.get("proposal_packet_sha256") or "0" * 64,
            "granted_by": "Randall", "channel": "test fixture",
            "message_ref": "fixture", "grant_text": "fixture approval",
            "granted_at": (now - dt.timedelta(hours=1)).isoformat(),
            "expires_at": (now + dt.timedelta(days=6)).isoformat(),
            "recorded_by": "Main", "recorded_at": now.isoformat(),
        }, indent=2), encoding="utf-8")


def write_decision(tmpdir: str, decisions: list[dict],
                   as_of: str = AS_OF) -> Path:
    root = Path(tmpdir) / "root"
    path = root / "tmp" / "decision.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if all(not d.get("proposal_packet_sha256") for d in decisions):
        required = {
            name: {"status": "satisfied", "detail": "test fixture"}
            for name in (
                "identity_listing_resolution",
                "thesis_lineage_risks_macro_catalysts",
                "evidence_recency",
                "quote_session_eligibility",
                "duplicate_surface_census",
            )
        }
        cards = []
        for d in decisions:
            from_tier, to_tier = d["from_tier"], d["to_tier"]
            card = {
                "card_id": d["card_id"], "ticker": d["ticker"],
                "prior_tier": from_tier, "proposed_tier": to_tier,
                "proofs": required,
                "role": ("demotion_proposed"
                         if from_tier in ("A", "B")
                         and to_tier in ("B", "C")
                         else "challenger"),
            }
            if from_tier == "C":
                card["status"] = "promotion_candidate:capacity_check"
            if to_tier == "A":
                card["b_to_a_case"] = {"to_tier": "A", "credible": True}
            cards.append(card)
        packet = root / "tmp" / "test-proposal-packet.json"
        packet.write_text(json.dumps({"cards": cards}, sort_keys=True),
                          encoding="utf-8")
        sha = hashlib.sha256(packet.read_bytes()).hexdigest()
        for d in decisions:
            d["proposal_packet_sha256"] = sha
    write_owner_decisions(root, decisions)
    path.write_text(json.dumps(
        {"schema": "veritas.tier_decision_set.v1", "as_of": as_of,
         "decisions": decisions}, indent=2), encoding="utf-8")
    return path


def sql_tier_of(root: Path, ticker: str) -> str:
    con = sqlite3.connect(str(db_path(root)))
    try:
        row = con.execute("SELECT tier FROM universe_membership WHERE "
                          "ticker=?", (ticker,)).fetchone()
        return row[0] if row else ""
    finally:
        con.close()


def pick_b_ticker(root: Path) -> str:
    con = sqlite3.connect(str(db_path(root)))
    try:
        return con.execute("SELECT ticker FROM universe_membership WHERE "
                           "tier='B' ORDER BY ticker LIMIT 1").fetchone()[0]
    finally:
        con.close()


def pick_c_with_band(root: Path) -> str:
    con = sqlite3.connect(str(db_path(root)))
    try:
        row = con.execute(
            "SELECT u.ticker FROM universe_membership u "
            "JOIN reference_levels r ON r.ticker=u.ticker "
            "JOIN evidence_freshness e ON e.ticker=u.ticker "
            "WHERE u.tier='C' ORDER BY u.ticker LIMIT 1").fetchone()
        return row[0]
    finally:
        con.close()


def pick_c_without_band(root: Path) -> str:
    con = sqlite3.connect(str(db_path(root)))
    try:
        row = con.execute(
            "SELECT ticker FROM universe_membership WHERE tier='C' "
            "AND ticker NOT IN (SELECT ticker FROM reference_levels) "
            "ORDER BY ticker LIMIT 1").fetchone()
        return row[0]
    finally:
        con.close()


def onboard_fixture_band(root: Path, ticker: str,
                         packet_date: str = AS_OF) -> None:
    """Fixture setup simulating the D3 onboarding writer's output plus a
    fixture-side baseline renewal mirroring an owner-approved weekly
    renewal (new content-hash filename, lineage + meta repointed).
    Fixture copies only; never the live canon. Required because the
    carried-over C rows have provenance-gapped lineage (records read as
    None), NULL confidence, and an immutable baseline pinning both."""
    con = sqlite3.connect(str(db_path(root)))
    try:
        con.execute("UPDATE source_lineage SET source_status='ok', "
                    "validator_status='ok' WHERE scope_key=? AND "
                    "field_family='reference_levels'", (ticker,))
        con.execute("UPDATE reference_levels SET "
                    "reference_confidence=70 WHERE ticker=?", (ticker,))
        raw = con.execute("SELECT raw_json FROM reference_levels WHERE "
                          "ticker=?", (ticker,)).fetchone()[0]
        doc = json.loads(raw)
        doc["phase4_onboarding"] = {
            "band_packet_as_of_date": packet_date,
            "onboarded_by": "test-fixture-simulated-D3"}
        con.execute("UPDATE reference_levels SET raw_json=? WHERE "
                    "ticker=?", (json.dumps(doc, sort_keys=True), ticker))
        con.commit()
    finally:
        con.close()
    renew_fixture_baseline(root, ticker, 70)


def renew_fixture_baseline(root: Path, ticker: str,
                           confidence: int) -> None:
    import datetime as _dt_mod
    basedir = root / "state" / "finance" / "baselines"
    olds = sorted(basedir.glob("alert-reference-levels-v1-*.json"))
    assert len(olds) == 1, olds
    old = olds[0]
    doc = json.loads(old.read_text(encoding="utf-8"))
    rows = doc["rows"]
    hit = [r for r in rows if r.get("ticker") == ticker]
    assert len(hit) == 1, ticker
    hit[0]["reference_confidence"] = confidence
    for key, val in doc.items():
        if key == "rows" or not isinstance(val, list):
            continue
        for r in val:
            if isinstance(r, dict) and r.get("ticker") == ticker \
                    and "reference_confidence" in r:
                r["reference_confidence"] = confidence
    projection = [{"ticker": r["ticker"],
                   "reference_price_low": r["reference_price_low"],
                   "reference_price_high": r["reference_price_high"],
                   "reference_invalidation_level":
                       r["reference_invalidation_level"],
                   "reference_confidence": r["reference_confidence"]}
                  for r in rows]
    new_proj = hashlib.sha256(json.dumps(
        projection, separators=(",", ":"),
        sort_keys=True).encode("utf-8")).hexdigest()
    doc["numeric_projection_sha256"] = new_proj
    raw_bytes = json.dumps(doc, indent=2, sort_keys=True).encode("utf-8")
    new_sha = hashlib.sha256(raw_bytes).hexdigest()
    new_rel = ("state/finance/baselines/alert-reference-levels-v1-%s.json"
               % new_sha)
    (root / new_rel).write_bytes(raw_bytes)
    con = sqlite3.connect(str(db_path(root)))
    try:
        con.execute("UPDATE reference_levels SET source_artifact_path=?, "
                    "source_artifact_sha256=?", (new_rel, new_sha))
        con.execute("UPDATE source_lineage SET source_artifact_path=?, "
                    "source_artifact_sha256=? WHERE "
                    "field_family='reference_levels'", (new_rel, new_sha))
        meta_row = con.execute("SELECT value FROM finance_state_meta "
                               "WHERE key='alerts_os_reference_baseline_v1'"
                               ).fetchone()[0]
        meta = json.loads(meta_row)
        for key in ("path", "baseline_path"):
            if key in meta:
                meta[key] = new_rel
        for key in ("sha256", "baseline_sha256"):
            if key in meta:
                meta[key] = new_sha
        meta["numeric_projection_sha256"] = new_proj
        meta["generated_at_utc"] = _dt_mod.datetime.now(
            _dt_mod.timezone.utc).isoformat()
        con.execute("UPDATE finance_state_meta SET value=? WHERE "
                    "key='alerts_os_reference_baseline_v1'",
                    (json.dumps(meta, indent=2, sort_keys=True),))
        con.commit()
    finally:
        con.close()
    old.unlink()
    assert not old.exists()


def inject_onboarding(root: Path, ticker: str,
                      packet_date: str = AS_OF) -> None:
    onboard_fixture_band(root, ticker, packet_date)


def quiesce_db(root: Path) -> None:
    con = sqlite3.connect(str(db_path(root)))
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.commit()
    finally:
        con.close()
    for sidecar in ("finance-canon.sqlite-shm",
                    "finance-canon.sqlite-wal"):
        p = db_path(root).parent / sidecar
        if p.exists():
            p.unlink()


def approved(ticker, frm, to, ref="OWNER-2026-09-27-001",
             card=None, sha="",
             accepted="2026-09-27T12:00:00-07:00") -> dict:
    return {"ticker": ticker, "from_tier": frm, "to_tier": to,
            "decision": "approved", "approval_reference": ref,
            "accepted_at": accepted,
            "card_id": card or f"card_{ticker}",
            "proposal_packet_sha256": sha}


class TestDryRun(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            quiesce_db(root)
            pre_logical = logical(root)
            dec = write_decision(tmp.name, [
                approved(b, "B", "C"), approved(c, "C", "B")])
            before = snapshot_tree(root)
            proc = run_writer(root, "--decision-file", str(dec))
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            plan = json.loads(proc.stdout)
            self.assertEqual(plan["status"], "dry_run_plan")
            self.assertEqual(plan["post_counts"], {"A": 15, "B": 17,
                                                   "C": 268})
            self.assertEqual(snapshot_tree(root), before)
            self.assertEqual(logical(root), pre_logical)
            assert_no_wal_frames(root)
            proc2 = run_writer(root, "--decision-file", str(dec),
                               "--apply")
            plan2 = json.loads(proc2.stdout)
            self.assertIn("BOTH --apply and --write", plan2["note"])
            self.assertEqual(logical(root), pre_logical)
        finally:
            tmp.cleanup()


    def test_production_activation_is_blocked(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            dec = write_decision(tmp.name, [
                approved(b, "B", "C"), approved(c, "C", "B")])
            packet = root / "tmp" / "test-proposal-packet.json"
            before = logical(root)
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env.pop("VERITAS_P42_TEST_ONLY_ACTIVATION", None)
            proc = subprocess.run(
                [sys.executable, str(WRITER), "--root", str(root),
                 "--db", str(db_path(root)), "--decision-file", str(dec),
                 "--proposal-packet", str(packet), "--apply", "--write"],
                capture_output=True, text=True, env=env, cwd=str(root))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("activation_blocked", proc.stdout)
            self.assertEqual(logical(root), before)
        finally:
            tmp.cleanup()


class TestValidSwap(unittest.TestCase):
    def test_swap_applies_with_exact_witnesses(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            pre_logical = logical(root)
            con0 = sqlite3.connect(str(db_path(root)))
            try:
                before_raw = dict(con0.execute(
                    "SELECT ticker, raw_json FROM universe_membership "
                    "WHERE ticker IN (?, ?)", (b, c)).fetchall())
            finally:
                con0.close()
            out = root / "tmp" / "p42-wout"
            dec = write_decision(tmp.name, [
                approved(b, "B", "C", card="card_b"),
                approved(c, "C", "B", card="card_c")])
            proc = run_writer(
                root, "--decision-file", str(dec), "--apply", "--write",
                "--output-dir", str(out),
                "--backup-path", str(out / "backup.sqlite"),
                "--audit-path", str(out / "audit.json"),
                "--rollback-path", str(out / "rollback.json"))
            self.assertEqual(proc.returncode, 0,
                             proc.stdout[-2000:] + proc.stderr[-2000:])
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "applied")
            audit = result["audit"]
            self.assertEqual(sql_tier_of(root, b), "C")
            self.assertEqual(sql_tier_of(root, c), "B")
            con = sqlite3.connect(str(db_path(root)))
            try:
                con.row_factory = sqlite3.Row
                rb = dict(con.execute("SELECT * FROM universe_membership "
                                      "WHERE ticker=?", (b,)).fetchone())
                rc = dict(con.execute("SELECT * FROM universe_membership "
                                      "WHERE ticker=?", (c,)).fetchone())
                self.assertEqual(
                    (rb["coverage_obligation_tier"], rb["sql_tier"],
                     rb["tier_decision_scope"],
                     rb["decision_grade_eligible"]),
                    ("C", "Tier C", "tier_c_sql_first_review_scope", 0))
                self.assertEqual(
                    (rc["coverage_obligation_tier"], rc["sql_tier"],
                     rc["tier_decision_scope"],
                     rc["decision_grade_eligible"]),
                    ("B", "Tier B", "tier_b_sql_first_review_scope", 1))
                # raw_json and all non-tier columns untouched
                self.assertEqual(rb["raw_json"], before_raw[b])
                self.assertEqual(rc["raw_json"], before_raw[c])
                rows = con.execute(
                    "SELECT event_id, event_type, detail_json FROM "
                    "audit_events WHERE event_type=? "
                    "ORDER BY event_id",
                    (wmod.EVENT_TYPE,)).fetchall()
                self.assertEqual(len(rows), 2)
                for _, _, detail in rows:
                    d = json.loads(detail)
                    self.assertIn(d["ticker"], (b, c))
                    self.assertTrue(d["approval_reference"])
                    self.assertTrue(d["accepted_at"])
                    self.assertTrue(d["transaction_id"])
            finally:
                con.close()
            self.assertEqual(audit["tier_breakdown_after"],
                             {"A": 15, "B": 17})
            self.assertTrue(audit["renewal_stop_for_owner_review"])
            # T1: logical (WAL-inclusive) proofs, not file shas.
            self.assertEqual(audit["db_logical_sha256_before"], pre_logical)
            self.assertEqual(audit["backup_logical_sha256"], pre_logical)
            self.assertEqual(audit["db_logical_sha256_after"],
                             logical(root))
            rb_doc = json.loads((out / "rollback.json").read_text(
                encoding="utf-8"))
            self.assertEqual(rb_doc["db_logical_sha256_before"],
                             pre_logical)
            self.assertIn(b, rb_doc["before_snapshot"]["families"])
            mods = wmod.staged_modules(root)
            access = mods["fsca"].FinanceSqlCanonAccess(db_path(root))
            self.assertEqual(access.validate()["status"], "ok")
        finally:
            tmp.cleanup()


class TestRefusals(unittest.TestCase):
    def _refused(self, root, decisions, reason_sub, tmpdir,
                 as_of=AS_OF, extra=()):
        pre_logical = logical(root)
        dec = write_decision(tmpdir, decisions, as_of=as_of)
        out = root / "tmp" / "wout"
        proc = run_writer(
            root, "--decision-file", str(dec), "--apply", "--write",
            "--output-dir", str(out), *extra)
        self.assertEqual(proc.returncode, 2,
                         proc.stdout[-2000:] + proc.stderr[-2000:])
        body = json.loads(proc.stdout)
        self.assertEqual(body["status"], "refused")
        self.assertIn(reason_sub, body["reason"])
        self.assertEqual(logical(root), pre_logical)
        return body

    def test_prior_tier_mismatch(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            self._refused(root, [approved(b, "C", "B")],
                          "prior_tier_mismatch", tmp.name)
        finally:
            tmp.cleanup()

    def test_cap_breach_without_paired_demotion(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            self._refused(root, [approved(c, "C", "B")],
                          "cap_breach", tmp.name)
        finally:
            tmp.cleanup()

    def test_c_to_a_jump_refused(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            c = pick_c_with_band(root)
            self._refused(root, [approved(c, "C", "A")],
                          "transition_not_allowed", tmp.name)
        finally:
            tmp.cleanup()

    def test_bandless_promotion_refused(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_without_band(root)
            self.assertIsNotNone(c)
            self._refused(root, [approved(b, "B", "C"),
                                 approved(c, "C", "B")],
                          "bandless_destination", tmp.name)
        finally:
            tmp.cleanup()

    def test_stale_band_promotion_refused(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c, packet_date="2026-08-01")
            self._refused(root, [approved(b, "B", "C"),
                                 approved(c, "C", "B")],
                          "stale_band_promotion_refused", tmp.name)
        finally:
            tmp.cleanup()

    def test_unapproved_entry_refused(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            d = approved(b, "B", "C")
            d["decision"] = "proposed"
            self._refused(root, [d], "unapproved_entry", tmp.name)
        finally:
            tmp.cleanup()

    def test_missing_approval_ref_refused(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            d = approved(b, "B", "C", ref="  ")
            self._refused(root, [d], "missing_approval_reference",
                          tmp.name)
        finally:
            tmp.cleanup()

    def test_missing_accepted_at_refused(self):
        # T7: accepted_at is mandatory.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            d = approved(b, "B", "C")
            del d["accepted_at"]
            self._refused(root, [d], "missing_or_invalid_accepted_at",
                          tmp.name)
            d2 = approved(b, "B", "C", accepted="not-a-date")
            self._refused(root, [d2], "missing_or_invalid_accepted_at",
                          tmp.name)
        finally:
            tmp.cleanup()

    def test_packet_sha_requires_packet_file(self):
        # T7: named packet sha without --proposal-packet refuses.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            d = approved(b, "B", "C", card="card_b", sha="0" * 64)
            self._refused(root, [d], "proposal_packet_required", tmp.name)
        finally:
            tmp.cleanup()

    def test_packet_sha_mismatch_refused(self):
        # T7: packet file whose sha differs from the named sha refuses.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            pkt = root / "tmp" / "packet.json"
            pkt.write_text(json.dumps({"cards": [{"card_id": "card_b"}]}),
                           encoding="utf-8")
            d = approved(b, "B", "C", card="card_b", sha="1" * 64)
            self._refused(root, [d], "proposal_packet_sha_mismatch",
                          tmp.name, extra=("--proposal-packet", str(pkt)))
        finally:
            tmp.cleanup()

    def test_packet_card_binding_applies(self):
        # T7: matching sha + card_id present in the packet applies.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            pkt = root / "tmp" / "packet.json"
            ready_proofs = {
                name: {"status": "satisfied", "detail": "test fixture"}
                for name in (
                    "identity_listing_resolution",
                    "thesis_lineage_risks_macro_catalysts",
                    "evidence_recency",
                    "quote_session_eligibility",
                    "duplicate_surface_census",
                )
            }
            raw = json.dumps({
                "incumbents": [{
                    "card_id": "card_b", "ticker": b,
                    "prior_tier": "B", "proposed_tier": "C",
                    "role": "demotion_proposed", "proofs": ready_proofs,
                }],
                "candidates": [{
                    "card_id": "card_c", "ticker": c,
                    "prior_tier": "C", "proposed_tier": "B",
                    "role": "challenger",
                    "status": "promotion_candidate:capacity_check",
                    "proofs": ready_proofs,
                }],
            }, sort_keys=True).encode()
            pkt.write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            out = root / "tmp" / "p42-wout"
            dec = write_decision(tmp.name, [
                approved(b, "B", "C", card="card_b", sha=sha),
                approved(c, "C", "B", card="card_c", sha=sha)])
            proc = run_writer(
                root, "--decision-file", str(dec), "--apply", "--write",
                "--output-dir", str(out),
                "--proposal-packet", str(pkt))
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:])
            body = json.loads(proc.stdout)
            self.assertEqual(body["status"], "applied")
            self.assertEqual(sql_tier_of(root, b), "C")
            self.assertEqual(sql_tier_of(root, c), "B")
        finally:
            tmp.cleanup()


class TestConcurrencyAndRestore(unittest.TestCase):
    def _prep(self, root, tmpdir):
        b = pick_b_ticker(root)
        c = pick_c_with_band(root)
        inject_onboarding(root, c)
        mods = wmod.staged_modules(root)
        bundle = wmod.load_decisions(write_decision(tmpdir, [
            approved(b, "B", "C"), approved(c, "C", "B")]))
        ctx = wmod.check_preconditions(root, db_path(root), bundle, mods)
        return b, c, mods, bundle, ctx

    def test_mid_transaction_failure_leaves_db_logically_identical(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = self._prep(root, tmp.name)
            pre_logical = logical(root)
            pre_snapshot = wmod.snapshot_rows(db_path(root), [b, c])
            with self.assertRaises(RuntimeError):
                wmod.apply_transaction(
                    db_path(root), bundle, ctx, "txn_test",
                    pre_snapshot, _fault_after_first=True)
            self.assertEqual(logical(root), pre_logical)
        finally:
            tmp.cleanup()

    def test_concurrent_change_refuses_and_applies_nothing(self):
        # T2: a concurrent tier change between snapshot and transaction
        # (injected hook on a separate connection) -> ROLLBACK + refuse,
        # writer applies nothing.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = self._prep(root, tmp.name)

            def hook():
                con = sqlite3.connect(str(db_path(root)))
                try:
                    con.execute("UPDATE universe_membership SET tier='C', "
                                "coverage_obligation_tier='C', "
                                "sql_tier='Tier C', tier_decision_scope="
                                "'tier_c_sql_first_review_scope', "
                                "decision_grade_eligible=0 WHERE ticker=?",
                                (b,))
                    con.commit()
                finally:
                    con.close()

            pre_snapshot = wmod.snapshot_rows(db_path(root), [b, c])
            hook()
            post_hook_logical = logical(root)
            with self.assertRaises(wmod.Refusal) as cm:
                wmod.apply_transaction(db_path(root), bundle, ctx,
                                       "txn_test", pre_snapshot)
            self.assertIn("concurrent_canon_change_detected",
                          str(cm.exception))
            self.assertEqual(logical(root), post_hook_logical)
            self.assertEqual(sql_tier_of(root, c), "C")
        finally:
            tmp.cleanup()

    def test_unrelated_balanced_tier_swap_refuses(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = self._prep(root, tmp.name)
            pre_snapshot = wmod.snapshot_rows(db_path(root), [b, c])
            con = sqlite3.connect(str(db_path(root)))
            try:
                b2 = con.execute(
                    "SELECT ticker FROM universe_membership WHERE tier='B' "
                    "AND ticker<>? ORDER BY ticker LIMIT 1", (b,)
                ).fetchone()[0]
                c2 = con.execute(
                    "SELECT ticker FROM universe_membership WHERE tier='C' "
                    "AND ticker<>? ORDER BY ticker LIMIT 1", (c,)
                ).fetchone()[0]
                con.execute(
                    "UPDATE universe_membership SET tier='C', "
                    "coverage_obligation_tier='C', sql_tier='Tier C', "
                    "tier_decision_scope='tier_c_sql_first_review_scope', "
                    "decision_grade_eligible=0 WHERE ticker=?", (b2,))
                con.execute(
                    "UPDATE universe_membership SET tier='B', "
                    "coverage_obligation_tier='B', sql_tier='Tier B', "
                    "tier_decision_scope='tier_b_sql_first_review_scope', "
                    "decision_grade_eligible=1 WHERE ticker=?", (c2,))
                con.commit()
            finally:
                con.close()
            changed = logical(root)
            with self.assertRaises(wmod.Refusal) as cm:
                wmod.apply_transaction(
                    db_path(root), bundle, ctx, "txn_test", pre_snapshot)
            self.assertIn("concurrent_canon_change_detected", str(cm.exception))
            self.assertEqual(logical(root), changed)
            self.assertEqual(sql_tier_of(root, b), "B")
            self.assertEqual(sql_tier_of(root, c), "C")
        finally:
            tmp.cleanup()

    def test_rowcount_check_fires_on_vanished_row(self):
        # T5: with the T2 re-read skipped (test hook), a row deleted
        # between snapshot and transaction must fail cur.rowcount == 1.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = self._prep(root, tmp.name)
            pre_snapshot = wmod.snapshot_rows(db_path(root), [b, c])
            con = sqlite3.connect(str(db_path(root)))
            try:
                con.execute("DELETE FROM universe_membership WHERE "
                            "ticker=?", (c,))
                con.commit()
            finally:
                con.close()
            with self.assertRaises(RuntimeError) as cm:
                wmod.apply_transaction(
                    db_path(root), bundle, ctx, "txn_test", pre_snapshot,
                    _skip_concurrency_check=True)
            self.assertIn("update_affected_0_rows", str(cm.exception))
        finally:
            tmp.cleanup()

    def test_reader_held_restore_is_logically_exact(self):
        # T1: reader held open across apply + forced post-commit verify
        # failure -> live DB logically equals the backup while the reader
        # is still open (copyfile/file-sha proofs cannot show this).
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b, c, mods, bundle, ctx = self._prep(root, tmp.name)
            out = root / "tmp" / "wout"
            out.mkdir(parents=True, exist_ok=True)
            backup = out / "backup.sqlite"
            info = snap.wal_safe_backup(db_path(root), backup)
            pre_logical = info["logical_sha256_before"]
            reader = sqlite3.connect(str(db_path(root)))
            try:
                reader.execute("SELECT COUNT(*) FROM universe_membership"
                               ).fetchone()
                pre_snapshot = wmod.snapshot_rows(db_path(root), [b, c])
                with self.assertRaises(RuntimeError):
                    wmod.do_apply(
                        root, db_path(root), bundle, ctx, mods,
                        out / "backup2.sqlite", out / "a.json",
                        out / "r.json", out,
                        _force_verify_fail=True)
                # reader still open: live content must equal the backup.
                self.assertEqual(logical(root), pre_logical)
                self.assertEqual(sql_tier_of(root, b), "B")
                self.assertEqual(sql_tier_of(root, c), "C")
            finally:
                reader.close()
        finally:
            tmp.cleanup()

    def test_rollback_refuses_after_unrelated_commit(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            out = root / "tmp" / "p42-drift"
            dec = write_decision(tmp.name, [
                approved(b, "B", "C"), approved(c, "C", "B")])
            proc = run_writer(
                root, "--decision-file", str(dec), "--apply", "--write",
                "--output-dir", str(out))
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:])
            con = sqlite3.connect(str(db_path(root)))
            try:
                con.execute(
                    "INSERT INTO audit_events(event_id,event_time_utc,"
                    "event_type,detail_json) VALUES (?,?,?,?)",
                    ("unrelated-after-tier", "2026-09-27T23:59:00Z",
                     "unrelated_test_commit", "{}"))
                con.commit()
            finally:
                con.close()
            after_unrelated = logical(root)
            rb = run_writer(root, "--rollback",
                            str(out / "tier_rollback.json"))
            self.assertEqual(rb.returncode, 2)
            self.assertIn("rollback_current_state_mismatch", rb.stdout)
            self.assertEqual(logical(root), after_unrelated)
        finally:
            tmp.cleanup()

    def test_rollback_restores_exact_logical_content(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            b = pick_b_ticker(root)
            c = pick_c_with_band(root)
            inject_onboarding(root, c)
            pre_logical = logical(root)
            out = root / "tmp" / "p42-wout"
            dec = write_decision(tmp.name, [
                approved(b, "B", "C"), approved(c, "C", "B")])
            proc = run_writer(
                root, "--decision-file", str(dec), "--apply", "--write",
                "--output-dir", str(out))
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:])
            self.assertNotEqual(logical(root), pre_logical)
            rb = run_writer(root, "--rollback",
                            str(out / "tier_rollback.json"))
            self.assertEqual(rb.returncode, 0,
                             rb.stdout[-2000:] + rb.stderr[-2000:])
            body = json.loads(rb.stdout)
            self.assertEqual(body["status"], "rolled_back")
            self.assertEqual(body["db_logical_sha256"], pre_logical)
            self.assertEqual(logical(root), pre_logical)
            self.assertEqual(body["tier_breakdown"], {"A": 15, "B": 17})
            self.assertEqual(sql_tier_of(root, b), "B")
            self.assertEqual(sql_tier_of(root, c), "C")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
