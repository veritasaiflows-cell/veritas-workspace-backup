#!/usr/bin/env python3
"""Hermetic tests for weekly_tier_proposal_job v2 (P4-2 slice A r2).

Every test copies staged-root to a fresh tempdir and runs the job with
cwd = that copy and --root = that copy; staged-root itself is never
modified. No live-DB writes, no network.

Covers: real-shape run (32 incumbents, 0 demotions, caps full, C
candidates thesis_required/needs_candidate_band), 10 verbatim proofs,
deterministic screening rank, demotion-on-impairment, staleness-is-not-
demotion, headroom, swap pairing, authority block, markdown refusal, and
the read-only guarantee (input bytes unchanged; no writes outside the
output dir).
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
from unittest import mock

V2_DIR = Path(__file__).resolve().parent
ROOT = V2_DIR.parent
JOB = V2_DIR / "weekly_tier_proposal_job.py"
STAGED = ROOT / "tmp" / "p4-2-writer-lane-20260927" / "staged-root"
AS_OF = "2026-09-27"

sys.path.insert(0, str(V2_DIR))
import weekly_tier_proposal_job as jobmod  # noqa: E402


def copy_staged() -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory(prefix="p42-a1-")
    dst = Path(tmp.name) / "root"
    shutil.copytree(STAGED, dst)
    return tmp


def run_job(root: Path, *extra) -> subprocess.CompletedProcess:
    outdir = root / "tmp" / "p42-out"
    cmd = [sys.executable, str(JOB), "--root", str(root),
           "--as-of", AS_OF, "--output-dir", str(outdir), *extra]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          cwd=str(root))


def load_packet(root: Path) -> dict:
    with open(root / "tmp" / "p42-out"
              / ("weekly_tier_proposal_%s.json" % AS_OF),
              encoding="utf-8") as fh:
        return json.load(fh)


def snapshot_tree(root: Path, skip_prefixes=()) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(rel == s or rel.startswith(s) for s in skip_prefixes):
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


EXPECTED_PROOFS = [
    "identity_listing_resolution",
    "prior_tier_version",
    "thesis_lineage_risks_macro_catalysts",
    "destination_enrollments",
    "evidence_recency",
    "capacity_or_displacement",
    "quote_session_eligibility",
    "card_queue_enrollment",
    "duplicate_surface_census",
    "rollback_crashrecovery_validation_audit",
]
ALLOWED_STATUSES = {"satisfied", "missing", "blocked",
                    "enumerated_exception"}


class TestRealShape(unittest.TestCase):
    def test_real_shape_counts_caps_and_candidates(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            packet = load_packet(root)
            self.assertEqual(packet["schema"],
                             "veritas.weekly_tier_proposal.v1")
            self.assertEqual(packet["counts"]["tier_a"], 15)
            self.assertEqual(packet["counts"]["tier_b"], 17)
            self.assertEqual(packet["counts"]["tier_c"], 268)
            self.assertEqual(len(packet["incumbents"]), 32)
            self.assertEqual(packet["demotions"], [])
            self.assertEqual(packet["cap_flags"]["tier_a"]["state"],
                             "full")
            self.assertEqual(packet["cap_flags"]["tier_b"]["state"],
                             "full")
            self.assertEqual(
                packet["cap_flags"]["evaluated_scope"]["cap"], 128)
            self.assertEqual(
                packet["cap_flags"]["evaluated_scope"]["count"], 32)
            self.assertEqual(len(packet["candidates"]), 10)
            for cand in packet["candidates"]:
                self.assertIn(cand["status"],
                              ("promotion_candidate:thesis_required",
                               "needs_candidate_band",
                               "promotion_candidate:capacity_check"))
                self.assertIn("capacity_blocked", cand["capacity"])
                self.assertTrue(cand["screen_reason"])
            auth = packet["authority"]
            self.assertFalse(auth["tier_write"])
            self.assertFalse(auth["canon_write"])
            self.assertFalse(auth["owner_approval_inferred"])
            self.assertFalse(auth["apply_mode_exists"])
        finally:
            tmp.cleanup()

    def check_10_proofs(self, card):
        self.assertEqual(sorted(card["proofs"].keys()),
                         sorted(EXPECTED_PROOFS))
        for key, proof in card["proofs"].items():
            self.assertIn(proof["status"], ALLOWED_STATUSES,
                          (card["ticker"], key))
            self.assertNotEqual(proof["status"], "not_applicable")
            self.assertTrue(proof["detail"])

    def test_incumbent_cards_carry_10_verbatim_proofs(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            self.assertEqual(run_job(root).returncode, 0)
            packet = load_packet(root)
            self.assertEqual(packet["proof_keys"], EXPECTED_PROOFS)
            for card in packet["incumbents"]:
                self.check_10_proofs(card)
        finally:
            tmp.cleanup()

    def test_challenger_cards_carry_10_verbatim_proofs(self):
        # P2: challengers use the same 10-proof builder.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            self.assertEqual(run_job(root).returncode, 0)
            packet = load_packet(root)
            self.assertEqual(len(packet["candidates"]), 10)
            for card in packet["candidates"]:
                self.check_10_proofs(card)
                self.assertEqual(card["role"], "challenger")
                self.assertTrue(card["screen_reason"])
                self.assertIn("screen_rank", card)
        finally:
            tmp.cleanup()

    def test_quote_session_current_when_market_closed(self):
        # P1: last-completed-session quote with market closed is current,
        # even though quote_freshness_status says stale; the frozen SQL
        # label is reported only.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            self.assertEqual(run_job(root).returncode, 0)
            packet = load_packet(root)
            for card in packet["incumbents"]:
                quote = card["proofs"]["quote_session_eligibility"]
                self.assertEqual(quote["status"], "satisfied",
                                 card["ticker"])
                rec = card["proofs"]["evidence_recency"]
                self.assertEqual(
                    sorted(rec["classes"].keys()),
                    sorted(jobmod.RECENCY_CLASSES))
                self.assertEqual(
                    rec["classes"]["quote_session"]["status"],
                    "satisfied")
                self.assertIn("sql_stale_label", rec["detail"])
            for line in packet["repair_debt"]:
                self.assertNotIn("stale_families", line)
        finally:
            tmp.cleanup()

    def test_incumbent_band_labels_weekly_renewal(self):
        # P5: incumbents show weekly_renewal + level pin age.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            self.assertEqual(run_job(root).returncode, 0)
            packet = load_packet(root)
            for card in packet["incumbents"]:
                band = card["band"]
                self.assertEqual(band["band_owner"], "weekly_renewal")
                self.assertTrue(band["level_as_of_utc"])
        finally:
            tmp.cleanup()

    def test_default_as_of_is_phoenix_date(self):
        # P4: no --as-of flag -> America/Phoenix date (UTC-7).
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            outdir = root / "tmp" / "p42-out"
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                [sys.executable, str(JOB), "--root", str(root),
                 "--output-dir", str(outdir)],
                capture_output=True, text=True, env=env, cwd=str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            expect = jobmod._phoenix_today()
            self.assertTrue(
                (outdir / ("weekly_tier_proposal_%s.json" % expect)
                 ).exists())
        finally:
            tmp.cleanup()

    def test_screening_rank_is_deterministic(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            self.assertEqual(run_job(root).returncode, 0)
            first = [(c["ticker"], c["screen_rank"], c["screen_reason"])
                     for c in load_packet(root)["candidates"]]
            shutil.rmtree(root / "tmp" / "p42-out")
            self.assertEqual(run_job(root).returncode, 0)
            second = [(c["ticker"], c["screen_rank"], c["screen_reason"])
                      for c in load_packet(root)["candidates"]]
            self.assertEqual(first, second)
            self.assertEqual(len(first), 10)
            ranks = [r for _, r, _ in first]
            self.assertEqual(ranks, sorted(ranks))
        finally:
            tmp.cleanup()


class TestSyntheticFixtures(unittest.TestCase):
    def _b_incumbent(self, root: Path) -> str:
        db = root / "state" / "finance" / "finance-canon.sqlite"
        con = sqlite3.connect(str(db))
        try:
            row = con.execute(
                "SELECT ticker FROM universe_membership WHERE tier='B' "
                "ORDER BY ticker LIMIT 1").fetchone()
        finally:
            con.close()
        return row[0]

    def _a_incumbent(self, root: Path) -> str:
        db = root / "state" / "finance" / "finance-canon.sqlite"
        con = sqlite3.connect(str(db))
        try:
            row = con.execute(
                "SELECT ticker FROM universe_membership WHERE tier='A' "
                "ORDER BY ticker LIMIT 1").fetchone()
        finally:
            con.close()
        return row[0]

    def test_demotion_on_sourced_impairment(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            ticker = self._b_incumbent(root)
            theses = sorted((root / "state" / "finance" / "thesis").glob(
                "*.json"))
            victim = None
            for fp in theses:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if data.get("ticker") == ticker:
                    victim = fp
                    break
            self.assertIsNotNone(victim, "B incumbent needs a thesis file")
            data = json.loads(victim.read_text(encoding="utf-8"))
            data["status"] = "retired"
            data["demotion_proponent"] = "main-review"
            data["impairment_evidence_source"] = "q2-filing-review"
            victim.write_text(json.dumps(data, indent=2),
                              encoding="utf-8")
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            packet = load_packet(root)
            got = [c for c in packet["demotions"]
                   if c["ticker"] == ticker]
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0]["proposed_tier"], "C")
            self.assertEqual(got[0]["demotion_evidence"]["basis"],
                             "retired_thesis_with_proponent")
        finally:
            tmp.cleanup()

    def test_staleness_is_repair_debt_not_demotion(self):
        # P1: a controller row that is NOT last-completed-session current
        # (delayed feed) makes the quote class missing -> repair debt via
        # controller values, never the frozen SQL label, never demotion.
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            ticker = self._a_incumbent(root)
            ctl_path = (root / "tmp"
                        / "alert-level-freshness-controller.json")
            doc = json.loads(ctl_path.read_text(encoding="utf-8"))
            for row in doc["rows"]:
                if row.get("ticker") == ticker:
                    row["quote_calendar_status"] = "delayed_feed"
                    row["quote_freshness_status"] = "stale"
            ctl_path.write_text(json.dumps(doc), encoding="utf-8")
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            packet = load_packet(root)
            self.assertEqual(
                [c for c in packet["demotions"]
                 if c["ticker"] == ticker], [])
            card = [c for c in packet["incumbents"]
                    if c["ticker"] == ticker][0]
            self.assertEqual(
                card["proofs"]["quote_session_eligibility"]["status"],
                "missing")
            for line in packet["repair_debt"]:
                self.assertNotIn("stale_families", line)
        finally:
            tmp.cleanup()

    def test_headroom_shows_on_b_to_a_case(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            ticker = self._a_incumbent(root)
            db = root / "state" / "finance" / "finance-canon.sqlite"
            con = sqlite3.connect(str(db))
            try:
                con.execute(
                    "UPDATE universe_membership SET tier='C', "
                    "coverage_obligation_tier='C', sql_tier='Tier C', "
                    "tier_decision_scope='tier_c_sql_first_review_scope', "
                    "decision_grade_eligible=0 WHERE ticker=?", (ticker,))
                con.commit()
            finally:
                con.close()
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            packet = load_packet(root)
            self.assertEqual(packet["counts"]["tier_a"], 14)
            self.assertEqual(packet["cap_flags"]["tier_a"]["headroom"], 1)
            b_cards = [c for c in packet["incumbents"]
                       if c["prior_tier"] == "B"]
            self.assertTrue(b_cards)
            for card in b_cards:
                self.assertIn("headroom 1",
                              card["b_to_a_case"]["capacity"])
        finally:
            tmp.cleanup()

    def test_candidate_capacity_respects_evaluated_cap(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            ticker = self._b_incumbent(root)
            db = root / "state" / "finance" / "finance-canon.sqlite"
            con = sqlite3.connect(str(db))
            try:
                con.execute(
                    "UPDATE universe_membership SET tier='C', "
                    "coverage_obligation_tier='C', sql_tier='Tier C', "
                    "tier_decision_scope='tier_c_sql_first_review_scope', "
                    "decision_grade_eligible=0 WHERE ticker=?", (ticker,))
                con.commit()
            finally:
                con.close()
            policy_path = root / "state" / "dynamic-entitlement-provider-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["envelope"]["max_scope_count"] = 31
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            packet = load_packet(root)
            self.assertEqual(packet["counts"]["tier_b"], 16)
            self.assertEqual(packet["counts"]["evaluated"], 31)
            self.assertEqual(packet["cap_flags"]["evaluated_scope"]["state"],
                             "full")
            for card in packet["candidates"]:
                self.assertIn("evaluated scope full/over-cap",
                              card["capacity"])
                self.assertEqual(
                    card["proofs"]["capacity_or_displacement"]["status"],
                    "blocked")
        finally:
            tmp.cleanup()

    def test_demotion_does_not_create_swap_without_complete_proof(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            a_ticker = self._a_incumbent(root)
            # Sourced impairment on an A incumbent -> demotion frees A.
            theses = {json.loads(fp.read_text(encoding="utf-8")).get(
                "ticker"): fp for fp in
                (root / "state" / "finance" / "thesis").glob("*.json")}
            self.assertIn(a_ticker, theses)
            data = json.loads(theses[a_ticker].read_text(
                encoding="utf-8"))
            data["status"] = "retired"
            data["demotion_proponent"] = "main-review"
            data["impairment_evidence_source"] = "q2-filing-review"
            theses[a_ticker].write_text(json.dumps(data, indent=2),
                                        encoding="utf-8")
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            packet = load_packet(root)
            dem = [c for c in packet["demotions"]
                   if c["ticker"] == a_ticker]
            self.assertEqual(len(dem), 1)
            self.assertEqual(dem[0]["proposed_tier"], "B")
            # Presence-only thesis/evidence cannot create a B->A swap.
            self.assertEqual(packet.get("swap_pairs", []), [])
            for card in packet["incumbents"]:
                if card["prior_tier"] == "B":
                    self.assertFalse(card["b_to_a_case"]["credible"])
        finally:
            tmp.cleanup()


class TestUnitGuards(unittest.TestCase):
    def test_screen_score_orders_completeness_first(self):
        full = {"ticker": "F", "data_quality": "clean",
                "revenue_yoy_pct": 1.0, "operating_margin_pct": 1.0,
                "fcf_yield_pct": 1.0}
        thin = {"ticker": "T", "data_quality": "clean",
                "revenue_yoy_pct": 999.0, "operating_margin_pct": 999.0,
                "fcf_yield_pct": None}
        s_full = jobmod.screen_score("F", full)
        s_thin = jobmod.screen_score("T", thin)
        self.assertGreater(s_full["completeness"],
                           s_thin["completeness"])

    def test_percentile_composite_outlier_does_not_dominate(self):
        # P3: an outlier huge on 1 of 3 fields must not outrank a name
        # better on 2 of 3 fields.
        mk = lambda t, r, o, f: {"ticker": t, "data_quality": "clean",
                                 "revenue_yoy_pct": r,
                                 "operating_margin_pct": o,
                                 "fcf_yield_pct": f}
        names = [jobmod.screen_score(*a) for a in [
            ("OUT", mk("OUT", 345.0, 1.0, 1.0)),
            ("BAL", mk("BAL", 10.0, 20.0, 5.0)),
            ("MID", mk("MID", 12.0, 15.0, 4.0)),
        ]]
        ranked = jobmod.rank_screened(names)
        order = [s["ticker"] for s in ranked]
        self.assertEqual(order[0], "BAL")
        self.assertEqual(order[-1], "OUT")
        bal = [s for s in ranked if s["ticker"] == "BAL"][0]
        self.assertIn("revenue_yoy_pct=10.0", bal["reason"])
        self.assertIn("composite=", bal["reason"])

    def test_recency_breakdown_six_classes(self):
        # P1 unit: frozen SQL label never decides; closed-market last
        # completed session is current.
        ctl = {"quote_calendar_status": "current_last_completed_session",
               "quote_freshness_status": "stale",
               "market_session_window": "market_closed_weekend_or_holiday",
               "quote_data_date": "2026-09-25"}
        rec = jobmod.recency_breakdown(
            "X", ctl, None, None, ["fresh_price_quote"], AS_OF)
        self.assertEqual(rec["classes"]["quote_session"]["status"],
                         "satisfied")
        self.assertEqual(sorted(rec["classes"].keys()),
                         sorted(jobmod.RECENCY_CLASSES))
        self.assertEqual(rec["sql_stale_label"], ["fresh_price_quote"])
        # delayed feed with no current marker -> missing
        ctl2 = dict(ctl, quote_calendar_status="delayed_feed")
        rec2 = jobmod.recency_breakdown(
            "X", ctl2, None, None, [], AS_OF)
        self.assertEqual(rec2["classes"]["quote_session"]["status"],
                         "missing")

    def test_nonfinite_metrics_are_missing(self):
        row = {"data_quality": "clean", "revenue_yoy_pct": float("nan"),
               "operating_margin_pct": float("inf"),
               "fcf_yield_pct": 2.0}
        score = jobmod.screen_score("X", row)
        self.assertIsNone(score["raws"]["revenue_yoy_pct"])
        self.assertIsNone(score["raws"]["operating_margin_pct"])
        self.assertEqual(score["raws"]["fcf_yield_pct"], 2.0)
        self.assertEqual(score["completeness"], 3)

    def test_output_dir_must_resolve_under_root_tmp(self):
        with tempfile.TemporaryDirectory(prefix="p42-output-") as td:
            root = Path(td) / "root"
            (root / "tmp").mkdir(parents=True)
            inside = jobmod.resolve_output_dir(root, "tmp/ok")
            self.assertEqual(inside, (root / "tmp" / "ok").resolve())
            with self.assertRaises(ValueError):
                jobmod.resolve_output_dir(root, root.parent / "outside")
            with self.assertRaises(ValueError):
                jobmod.resolve_output_dir(root, "../outside")
            with mock.patch.object(
                    jobmod, "_is_reparse_point", return_value=True):
                with self.assertRaises(ValueError):
                    jobmod.resolve_output_dir(root, "tmp/linked")

    def test_as_of_cannot_escape_output_filename(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            target = root / "tmp" / "alert-level-freshness-controller.json"
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            proc = run_job(
                root, "--as-of",
                "2026-09-27/../../alert-level-freshness-controller")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                             before)
        finally:
            tmp.cleanup()

    def test_refuse_forbidden_markdown(self):
        out = V2_DIR / "output"
        jobmod.refuse_forbidden_markdown(
            out / "weekly_tier_proposal_2026-09-27.md", "digest")
        with self.assertRaises(ValueError):
            jobmod.refuse_forbidden_markdown(
                Path("03. Alerts and Recommendations/x.md"), "digest")
        with self.assertRaises(ValueError):
            jobmod.refuse_forbidden_markdown(
                out / "Alert Bands digest.md", "digest")

    def test_no_apply_mode(self):
        proc = run_job(Path(tempfile.mkdtemp()), "--apply")
        self.assertNotEqual(proc.returncode, 0)

    def test_guard_blocked_packet_and_exit_code(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            (root / "state" / "finance" / "finance-canon.sqlite").unlink()
            proc = run_job(root)
            self.assertEqual(proc.returncode, 3)
            packet = load_packet(root)
            self.assertEqual(packet["status"], "blocked")
            self.assertFalse(
                packet["authority"]["owner_approval_inferred"])
        finally:
            tmp.cleanup()


class TestReadOnlyGuarantee(unittest.TestCase):
    def test_inputs_unchanged_no_stray_writes(self):
        tmp = copy_staged()
        try:
            root = Path(tmp.name) / "root"
            before = snapshot_tree(root, skip_prefixes=("tmp/p42-out",))
            proc = run_job(root)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            after = snapshot_tree(root, skip_prefixes=("tmp/p42-out",))
            self.assertEqual(before, after)
            out_files = sorted(
                (root / "tmp" / "p42-out").rglob("*"))
            self.assertTrue(out_files)
            names = sorted(p.name for p in out_files if p.is_file())
            self.assertEqual(names, [
                "weekly_tier_proposal_2026-09-27.json",
                "weekly_tier_proposal_2026-09-27.md"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
