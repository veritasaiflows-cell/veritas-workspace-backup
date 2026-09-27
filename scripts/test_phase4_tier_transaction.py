"""Tests for phase4_tier_transaction (stdlib unittest; Main runs under pytest)."""

from __future__ import annotations

import ast
import copy
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase4_tier_transaction as txn

NOW = "2026-09-26T16:00:00Z"
LATER = "2026-09-26T17:00:00Z"
EXPIRED_NOW = "2026-09-30T16:00:00Z"
UNIVERSE = "universe-test-01"
SNAPSHOT = "snapshot-test-01"
RHASH = "0123456789abcdef" * 4
TOK = "token-abc"
WRONG_TOK = "wrong-token"


def machine() -> dict:
    return txn.new_machine([{"ticker": "CME", "tier": "B", "version": 3}],
                           universe_id=UNIVERSE, snapshot_id=SNAPSHOT)


def proposal(lease: str = "lease-001", token: str = TOK) -> dict:
    return {
        "ticker": "CME", "expected_prior_tier": "B", "expected_prior_version": 3,
        "expected_prior_gen": 0, "destination_tier": "A",
        "readiness_hash": RHASH, "universe_id": UNIVERSE,
        "snapshot_id": SNAPSHOT, "lease_id": lease, "token": token,
        "created_at_utc": NOW, "expires_at_utc": "2026-09-27T16:00:00Z",
        "enrollment_proof": {"enrolled": True, "tier": "A"},
        "coverage_proof": {"covered": True, "universe_id": UNIVERSE},
    }


def approval(lease: str = "lease-001", token: str = TOK) -> dict:
    return {"approver": "randall", "approved_at_utc": LATER,
            "method": "human_review_commit", "lease_id": lease,
            "token": token, "readiness_hash": RHASH}


def proposed_line(lease: str, ticker: str = "CME", phash: str = "h1") -> dict:
    return {"kind": "proposed", "lease_id": lease, "ticker": ticker,
            "proposal_hash": phash}


def committed_line(lease: str, ticker: str = "CME", phash: str = "h1",
                   prior: tuple = ("B", 3, 0),
                   next_: tuple = ("A", 4, 1)) -> dict:
    return {"kind": "committed", "lease_id": lease, "ticker": ticker,
            "proposal_hash": phash,
            "prior_tier": prior[0], "prior_version": prior[1], "prior_gen": prior[2],
            "next_tier": next_[0], "next_version": next_[1], "next_gen": next_[2]}


class HappyPathTests(unittest.TestCase):
    def test_propose_commit_rollback(self) -> None:
        m0: dict = machine()
        snapshot0: dict = copy.deepcopy(m0)
        m1, r1 = txn.propose(m0, proposal(), now_utc=NOW)
        self.assertTrue(r1["ok"])
        self.assertEqual(m0, snapshot0, msg="propose mutated input")
        m2, r2 = txn.commit(m1, lease_id="lease-001", token=TOK,
                            approval=approval(), now_utc=LATER)
        self.assertTrue(r2["ok"])
        self.assertEqual(m2["slots"]["CME"]["tier"], "A")
        self.assertEqual(m2["slots"]["CME"]["version"], 4)
        m3, r3 = txn.rollback(m2, lease_id="lease-001", token=TOK,
                              now_utc=LATER)
        self.assertTrue(r3["ok"])
        self.assertEqual(m3["slots"]["CME"]["tier"], "B")
        self.assertEqual(m3["slots"]["CME"]["version"], 3)
        self.assertGreater(m3["slots"]["CME"]["gen"], m2["slots"]["CME"]["gen"])

    def test_followup_propose_after_commit(self) -> None:
        m1, _ = txn.propose(machine(), proposal("L1", "tok-L1"), now_utc=NOW)
        m2, r2 = txn.commit(m1, lease_id="L1", token="tok-L1",
                            approval=approval("L1", "tok-L1"), now_utc=LATER)
        self.assertTrue(r2["ok"])
        follow: dict = proposal("L2", "tok-L2")
        follow.update({"expected_prior_tier": "A", "expected_prior_version": 4,
                       "expected_prior_gen": 1, "destination_tier": "C",
                       "enrollment_proof": {"enrolled": True, "tier": "C"}})
        m3, r3 = txn.propose(m2, follow, now_utc=LATER)
        self.assertTrue(r3["ok"], msg=f"follow-up after commit blocked: {r3}")
        m4, r4 = txn.commit(m3, lease_id="L2", token="tok-L2",
                            approval=approval("L2", "tok-L2"), now_utc=LATER)
        self.assertTrue(r4["ok"])
        self.assertEqual(m4["slots"]["CME"]["tier"], "C")

    def test_expire_leaves_prior_unchanged(self) -> None:
        m0: dict = machine()
        m1, r1 = txn.propose(m0, proposal(), now_utc=NOW)
        self.assertTrue(r1["ok"])
        m2, r2 = txn.expire(m1, now_utc=EXPIRED_NOW)
        self.assertTrue(r2["ok"])
        self.assertIn("lease-001", r2["expired"])
        self.assertEqual(m2["slots"]["CME"]["tier"], "B")
        self.assertEqual(m2["slots"]["CME"]["version"], 3)
        self.assertIn("lease-001", m2["expired"])

    def test_commit_idempotent_exact_replay(self) -> None:
        m0: dict = machine()
        m1, _ = txn.propose(m0, proposal(), now_utc=NOW)
        m2, r2 = txn.commit(m1, lease_id="lease-001", token=TOK,
                            approval=approval(), now_utc=LATER)
        self.assertTrue(r2["ok"])
        m3, r3 = txn.commit(m2, lease_id="lease-001", token=TOK,
                            approval=approval(), now_utc=LATER)
        self.assertTrue(r3["ok"])
        self.assertTrue(r3.get("replay"))
        self.assertEqual(m3["slots"]["CME"]["tier"], "A")

    def test_recover_classifies(self) -> None:
        journal: list = [
            proposed_line("l1"), committed_line("l1"),
            {"kind": "rolled_back", "lease_id": "l1", "ticker": "CME",
             "proposal_hash": "h1",
             "prior_tier": "B", "prior_version": 3, "prior_gen": 0,
             "next_tier": "A", "next_version": 4, "next_gen": 1},
            proposed_line("l4", phash="h4"),
            {"kind": "expired", "lease_id": "l4", "ticker": "CME",
             "proposal_hash": "h4"},
        ]
        result: dict = txn.recover(journal)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["proposed"], 2)
        self.assertEqual(result["counts"]["committed"], 1)
        self.assertEqual(result["leases"]["l1"], "rolled_back")
        self.assertEqual(result["leases"]["l4"], "expired")
        bad: dict = txn.recover(journal + [{"kind": "bogus", "lease_id": ""}])
        self.assertEqual(bad["status"], "error")
        self.assertEqual(bad["counts"]["malformed"], 1)
        bad2: dict = txn.recover("not-a-journal")
        self.assertEqual(bad2["status"], "error")

    def test_recover_rejects_orphans_and_duplicates(self) -> None:
        orphan: dict = txn.recover([committed_line("x")])
        self.assertEqual(orphan["status"], "error")
        self.assertEqual(orphan["leases"]["x"], "blocked")
        no_commit: dict = txn.recover(
            [proposed_line("y"),
             {"kind": "rolled_back", "lease_id": "y", "ticker": "CME"}])
        self.assertEqual(no_commit["status"], "error")
        self.assertEqual(no_commit["leases"]["y"], "blocked")
        dup: dict = txn.recover(
            [proposed_line("z"), committed_line("z"), committed_line("z")])
        self.assertEqual(dup["status"], "error")
        self.assertEqual(dup["leases"]["z"], "blocked")

    def test_recover_flags_ticker_hash_and_concurrent(self) -> None:
        changed: dict = txn.recover(
            [proposed_line("a", "CME", "h1"), committed_line("a", "ITA", "h2")])
        self.assertEqual(changed["status"], "error")
        self.assertEqual(changed["leases"]["a"], "blocked")
        sequential: dict = txn.recover(
            [proposed_line("a", "CME", "h1"), committed_line("a", "CME", "h1"),
             proposed_line("b", "CME", "h9"),
             committed_line("b", "CME", "h9", prior=("A", 4, 1),
                            next_=("C", 5, 2))])
        self.assertEqual(sequential["status"], "ok")
        self.assertEqual(sequential["leases"]["a"], "committed")
        self.assertEqual(sequential["leases"]["b"], "committed")
        concurrent: dict = txn.recover(
            [proposed_line("a", "CME", "h1"), committed_line("a", "CME", "h1"),
             proposed_line("b", "CME", "h9"),
             committed_line("b", "CME", "h9", prior=("B", 3, 0),
                            next_=("C", 4, 1))])
        self.assertEqual(concurrent["status"], "error")
        self.assertEqual(concurrent["leases"]["b"], "blocked")
        incomplete: dict = txn.recover(
            [proposed_line("c"), {"kind": "committed", "lease_id": "c",
                                  "ticker": "CME"}])
        self.assertEqual(incomplete["status"], "error")
        self.assertEqual(incomplete["leases"]["c"], "blocked")


class ImmutabilityTests(unittest.TestCase):
    def test_returned_proposal_aliasing_cannot_rewrite(self) -> None:
        m1, r1 = txn.propose(machine(), proposal(), now_utc=NOW)
        r1["proposal"]["destination_tier"] = "Z"
        r1["proposal"]["enrollment_proof"] = False
        self.assertEqual(m1["proposed"]["lease-001"]["destination_tier"], "A")
        m2, r2 = txn.commit(m1, lease_id="lease-001", token=TOK,
                            approval=approval(), now_utc=LATER)
        self.assertTrue(r2["ok"])
        self.assertEqual(m2["slots"]["CME"]["tier"], "A")

    def test_mutated_machine_reused_fails_closed(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        m1["proposed"]["lease-001"]["destination_tier"] = "C"
        m1["proposed"]["lease-001"]["enrollment_proof"] = {"enrolled": True,
                                                           "tier": "C"}
        _, r_tampered = txn.commit(m1, lease_id="lease-001", token=TOK,
                                   approval=approval(), now_utc=LATER)
        self.assertFalse(r_tampered["ok"])
        m1b, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        m1b["slots"]["CME"] = {"tier": "Z", "version": 99, "gen": 99}
        _, r_slot = txn.commit(m1b, lease_id="lease-001", token=TOK,
                               approval=approval(), now_utc=LATER)
        self.assertFalse(r_slot["ok"])
        fresh: dict = machine()
        m3, _ = txn.propose(fresh, proposal(), now_utc=NOW)
        m4, r4 = txn.commit(m3, lease_id="lease-001", token=TOK,
                            approval=approval(), now_utc=LATER)
        self.assertTrue(r4["ok"])
        self.assertEqual(m4["slots"]["CME"]["tier"], "A")


class JournalBindingTests(unittest.TestCase):
    def test_forged_proposal_without_journal_rejected(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        forged: dict = copy.deepcopy(m1)
        forged["proposed"]["forged"] = {
            "ticker": "CME", "expected_prior_tier": "B",
            "expected_prior_version": 3, "expected_prior_gen": 0,
            "destination_tier": "A", "readiness_hash": RHASH,
            "universe_id": UNIVERSE, "snapshot_id": SNAPSHOT,
            "lease_id": "forged", "token": "tok-forged",
            "created_at_utc": NOW, "expires_at_utc": "2026-09-27T16:00:00Z",
            "enrollment_proof": {"enrolled": True, "tier": "A"},
            "coverage_proof": {"covered": True},
        }
        _, r = txn.commit(forged, lease_id="forged", token="tok-forged",
                          approval=approval("forged", "tok-forged"), now_utc=LATER)
        self.assertFalse(r["ok"])

    def test_tampered_destination_rejected_at_commit(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        tampered: dict = copy.deepcopy(m1)
        tampered["proposed"]["lease-001"]["destination_tier"] = "Z"
        tampered["proposed"]["lease-001"]["enrollment_proof"] = {"enrolled": True,
                                                                 "tier": "Z"}
        _, r = txn.commit(tampered, lease_id="lease-001", token=TOK,
                          approval=approval(), now_utc=LATER)
        self.assertFalse(r["ok"])

    def test_fake_committed_plus_plain_journal_line_rejected(self) -> None:
        m0: dict = machine()
        forged: dict = copy.deepcopy(m0)
        forged["committed"]["x"] = {
            "lease_id": "x", "ticker": "CME", "token": "tok-x",
            "proposal": dict(proposal("x", "tok-x")),
            "approval": dict(approval("x", "tok-x")),
            "prior_tier": "C", "prior_version": 0, "prior_gen": 0,
            "next_tier": "B", "next_version": 3, "next_gen": 0,
        }
        forged["journal"] = [{"kind": "committed", "lease_id": "x",
                              "ticker": "CME"}]
        _, r = txn.rollback(forged, lease_id="x", token="tok-x", now_utc=LATER)
        self.assertFalse(r["ok"])

    def test_edited_prior_rejected_at_rollback(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        m2, _ = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=approval(), now_utc=LATER)
        edited: dict = copy.deepcopy(m2)
        edited["committed"]["lease-001"]["prior_tier"] = "C"
        edited["committed"]["lease-001"]["prior_version"] = 0
        _, r = txn.rollback(edited, lease_id="lease-001",
                            token=TOK, now_utc=LATER)
        self.assertFalse(r["ok"])
        rec: dict = txn.recover(edited["journal"])
        self.assertEqual(rec["status"], "ok")


class NegativeTests(unittest.TestCase):
    def test_duplicate_lease_rejected(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        _, r2 = txn.propose(m1, proposal(), now_utc=NOW)
        self.assertFalse(r2["ok"])
        self.assertIn("duplicate_active_lease", r2["reasons"])

    def test_ticker_exclusivity_and_token_reuse(self) -> None:
        m1, _ = txn.propose(machine(), proposal("lease-001", "tok-1"),
                            now_utc=NOW)
        second: dict = proposal("lease-002", "tok-2")
        _, r = txn.propose(m1, second, now_utc=NOW)
        self.assertFalse(r["ok"])
        self.assertIn("ticker_lease_active", r["reasons"])
        m_exp, _ = txn.propose(machine(), proposal("lease-9", "tok-reuse"),
                               now_utc=NOW)
        m_exp2, _ = txn.expire(m_exp, now_utc=EXPIRED_NOW)
        _, r_reuse = txn.propose(m_exp2, proposal("lease-10", "tok-reuse"),
                                 now_utc=EXPIRED_NOW)
        self.assertFalse(r_reuse["ok"])
        self.assertIn("token_reuse_rejected", r_reuse["reasons"])
        _, r_lease = txn.propose(m_exp2, proposal("lease-9", "tok-fresh"),
                                 now_utc=EXPIRED_NOW)
        self.assertFalse(r_lease["ok"])
        self.assertIn("lease_id_reuse_rejected", r_lease["reasons"])

    def test_stale_version_tier_rejected(self) -> None:
        stale_v: dict = proposal()
        stale_v["expected_prior_version"] = 2
        _, r = txn.propose(machine(), stale_v, now_utc=NOW)
        self.assertFalse(r["ok"])
        self.assertIn("stale_expected_version", r["reasons"])
        stale_t: dict = proposal()
        stale_t["expected_prior_tier"] = "A"
        _, r2 = txn.propose(machine(), stale_t, now_utc=NOW)
        self.assertFalse(r2["ok"])
        self.assertIn("stale_expected_tier", r2["reasons"])

    def test_aba_stale_gen_rejected(self) -> None:
        m1, _ = txn.propose(machine(), proposal("L1", "tok-L1"), now_utc=NOW)
        other_machine: dict = machine()
        l2_prop: dict = proposal("L2", "tok-L2")
        l2_prop["destination_tier"] = "C"
        l2_prop["enrollment_proof"] = {"enrolled": True, "tier": "C"}
        m2, r2 = txn.commit(m1, lease_id="L1", token="tok-L1",
                            approval=approval("L1", "tok-L1"), now_utc=LATER)
        self.assertTrue(r2["ok"])
        m3, r3 = txn.rollback(m2, lease_id="L1", token="tok-L1", now_utc=LATER)
        self.assertTrue(r3["ok"])
        m4, _ = txn.propose(other_machine, l2_prop, now_utc=NOW)
        tampered: dict = copy.deepcopy(m3)
        tampered["proposed"]["L2"] = m4["proposed"]["L2"]
        tampered["used_tokens"] = dict(m3.get("used_tokens", {}))
        tampered["used_tokens"]["tok-L2"] = "L2"
        tampered["used_leases"] = dict(m3.get("used_leases", {}))
        tampered["used_leases"]["L2"] = "CME"
        tampered["journal"] = list(m3.get("journal", [])) + [
            e for e in m4.get("journal", []) if e.get("lease_id") == "L2"]
        _, r_commit = txn.commit(tampered, lease_id="L2", token="tok-L2",
                                 approval=approval("L2", "tok-L2"), now_utc=LATER)
        self.assertFalse(r_commit["ok"])
        self.assertIn("stale_expected_gen", r_commit["reasons"])

    def test_invalid_destination(self) -> None:
        bad: dict = proposal()
        bad["destination_tier"] = "Z"
        bad["enrollment_proof"] = {"enrolled": True, "tier": "Z"}
        _, r = txn.propose(machine(), bad, now_utc=NOW)
        self.assertFalse(r["ok"])
        self.assertIn("destination_invalid", r["reasons"])
        same: dict = proposal()
        same["destination_tier"] = "B"
        same["enrollment_proof"] = {"enrolled": True, "tier": "B"}
        _, r2 = txn.propose(machine(), same, now_utc=NOW)
        self.assertFalse(r2["ok"])
        self.assertIn("destination_same_as_prior", r2["reasons"])

    def test_coverage_enrollment_required(self) -> None:
        no_cov: dict = proposal()
        no_cov["coverage_proof"] = False
        _, r = txn.propose(machine(), no_cov, now_utc=NOW)
        self.assertFalse(r["ok"])
        self.assertIn("coverage_missing", r["reasons"])
        no_enr: dict = proposal()
        no_enr["enrollment_proof"] = {"enrolled": False, "tier": "A"}
        _, r2 = txn.propose(machine(), no_enr, now_utc=NOW)
        self.assertFalse(r2["ok"])
        self.assertIn("enrollment_missing", r2["reasons"])
        bare_hash: dict = proposal()
        bare_hash["readiness_hash"] = "x"
        _, r3 = txn.propose(machine(), bare_hash, now_utc=NOW)
        self.assertFalse(r3["ok"])
        self.assertIn("readiness_hash_invalid", r3["reasons"])

    def test_expired_lease_proposal_rejected(self) -> None:
        old: dict = proposal()
        old["expires_at_utc"] = "2026-09-20T00:00:00Z"
        _, r = txn.propose(machine(), old, now_utc=NOW)
        self.assertFalse(r["ok"])
        self.assertIn("lease_expired", r["reasons"])

    def test_direct_commit_without_proposal(self) -> None:
        _, r = txn.commit(machine(), lease_id="ghost", token="t",
                          approval=approval("ghost", "t"), now_utc=LATER)
        self.assertFalse(r["ok"])
        self.assertIn("no_valid_proposal", r["reasons"])

    def test_commit_token_mismatch_and_expiry(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        _, r = txn.commit(m1, lease_id="lease-001", token=WRONG_TOK,
                          approval=approval(), now_utc=LATER)
        self.assertFalse(r["ok"])
        self.assertIn("lease_token_mismatch", r["reasons"])
        _, r2 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=approval(), now_utc=EXPIRED_NOW)
        self.assertFalse(r2["ok"])
        self.assertIn("lease_expired", r2["reasons"])

    def test_commit_requires_bound_human_approval(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        auto: dict = approval()
        auto["automatic"] = True
        _, r = txn.commit(m1, lease_id="lease-001", token=TOK,
                          approval=auto, now_utc=LATER)
        self.assertFalse(r["ok"])
        self.assertIn("approval_automatic_rejected", r["reasons"])
        missing: dict = approval()
        missing["approver"] = ""
        _, r2 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=missing, now_utc=LATER)
        self.assertFalse(r2["ok"])
        self.assertIn("approval_approver_missing", r2["reasons"])
        wrong_method: dict = approval()
        wrong_method["method"] = "auto"
        _, r3 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=wrong_method, now_utc=LATER)
        self.assertFalse(r3["ok"])
        self.assertIn("approval_method_invalid", r3["reasons"])
        other_lease: dict = approval("other-lease", TOK)
        _, r4 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=other_lease, now_utc=LATER)
        self.assertFalse(r4["ok"])
        self.assertIn("approval_lease_mismatch", r4["reasons"])
        early: dict = approval()
        early["approved_at_utc"] = "2020-01-01T00:00:00Z"
        _, r5 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=early, now_utc=LATER)
        self.assertFalse(r5["ok"])
        self.assertIn("approval_before_proposal", r5["reasons"])
        future: dict = approval()
        future["approved_at_utc"] = "2099-01-01T00:00:00Z"
        _, r6 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=future, now_utc=LATER)
        self.assertFalse(r6["ok"])
        self.assertIn("approval_in_future", r6["reasons"])
        bot: dict = approval()
        bot["approver"] = "auto-bot"
        _, r7 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=bot, now_utc=LATER)
        self.assertFalse(r7["ok"])
        self.assertIn("approval_machine_approver_rejected", r7["reasons"])
        underscore_bot: dict = approval()
        underscore_bot["approver"] = "auto_bot"
        _, r8 = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=underscore_bot, now_utc=LATER)
        self.assertFalse(r8["ok"])
        self.assertIn("approval_machine_approver_rejected", r8["reasons"])
        for actor in ("system monitor", "auto-bot", "auto\u200bbot", "ＡＵＴＯ－ＢＯＴ",
                      "auto.bot", "veritas-os-freshness-monitor"):
            variant: dict = approval()
            variant["approver"] = actor
            _, rejected = txn.commit(m1, lease_id="lease-001", token=TOK,
                                     approval=variant, now_utc=LATER)
            self.assertFalse(rejected["ok"], msg=f"approver={actor!r} must fail")
            self.assertIn("approval_machine_approver_rejected", rejected["reasons"])

    def test_conflicting_replay_rejected(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        m2, _ = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=approval(), now_utc=LATER)
        other: dict = approval()
        other["approver"] = "someone-else"
        _, r = txn.commit(m2, lease_id="lease-001", token=TOK,
                          approval=other, now_utc=LATER)
        self.assertFalse(r["ok"])
        self.assertIn("conflicting_replay", r["reasons"])

    def test_rollback_cross_guards(self) -> None:
        m1, _ = txn.propose(machine(), proposal(), now_utc=NOW)
        _, r = txn.rollback(m1, lease_id="lease-001", token=TOK,
                            now_utc=LATER)
        self.assertFalse(r["ok"])
        self.assertIn("no_committed_transaction", r["reasons"])
        m2, _ = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=approval(), now_utc=LATER)
        _, r2 = txn.rollback(m2, lease_id="lease-001", token=WRONG_TOK,
                             now_utc=LATER)
        self.assertFalse(r2["ok"])
        self.assertIn("lease_token_mismatch", r2["reasons"])
        tampered: dict = copy.deepcopy(m2)
        tampered["slots"]["CME"] = {"tier": "C", "version": 9, "gen": 9}
        _, r3 = txn.rollback(tampered, lease_id="lease-001",
                             token=TOK, now_utc=LATER)
        self.assertFalse(r3["ok"])
        self.assertIn("rollback_cross_version_rejected", r3["reasons"])

    def test_unhashable_and_unknown_never_crash(self) -> None:
        bad_ticker: dict = proposal()
        bad_ticker["ticker"] = ["CME"]
        _, r = txn.propose(machine(), bad_ticker, now_utc=NOW)
        self.assertFalse(r["ok"])
        self.assertIn("ticker_invalid", r["reasons"])
        bad_lease: dict = proposal()
        bad_lease["lease_id"] = {"a": 1}
        _, r2 = txn.propose(machine(), bad_lease, now_utc=NOW)
        self.assertFalse(r2["ok"])
        unknown: dict = proposal()
        unknown["ticker"] = "ZZZ"
        _, r3 = txn.propose(machine(), unknown, now_utc=NOW)
        self.assertFalse(r3["ok"])
        self.assertIn("ticker_unknown", r3["reasons"])
        _, r4 = txn.propose(machine(), proposal(), now_utc="2026-09-26T16:00:00")
        self.assertFalse(r4["ok"])
        self.assertIn("now_malformed", r4["reasons"])

    def test_uncopyable_proof_and_broken_state_never_crash(self) -> None:
        import threading
        locked: dict = proposal()
        locked["coverage_proof"] = {"covered": True, "lock": threading.Lock()}
        _, r = txn.propose(machine(), locked, now_utc=NOW)
        self.assertFalse(r["ok"])
        m0: dict = machine()
        m0["slots"]["CME"] = threading.Lock()
        _, r2 = txn.propose(m0, proposal(), now_utc=NOW)
        self.assertFalse(r2["ok"])
        self.assertNotEqual(r2, {"ok": True})
        _, r3 = txn.expire({"proposed": []}, now_utc=NOW)
        self.assertFalse(r3["ok"])
        m_nokey: dict = machine()
        del m_nokey["expired"]
        m_p, r_p = txn.propose(m_nokey, proposal(), now_utc=NOW)
        self.assertTrue(r_p["ok"])
        _, r_e = txn.expire(m_p, now_utc=EXPIRED_NOW)
        self.assertTrue(r_e["ok"])


class RecoveryChainTests(unittest.TestCase):
    def test_sequential_chain_hands_off_holder(self) -> None:
        journal: list = [
            proposed_line("a", "CME", "h1"), committed_line("a", "CME", "h1"),
            proposed_line("b", "CME", "h9"),
            committed_line("b", "CME", "h9", prior=("A", 4, 1),
                           next_=("B", 5, 2)),
        ]
        result: dict = txn.recover(journal)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["leases"]["b"], "committed")

    def test_chain_after_rollback_uses_restored_values(self) -> None:
        journal: list = [
            proposed_line("a", "CME", "h1"), committed_line("a", "CME", "h1"),
            {"kind": "rolled_back", "lease_id": "a", "ticker": "CME",
             "proposal_hash": "h1",
             "prior_tier": "B", "prior_version": 3, "prior_gen": 0,
             "next_tier": "A", "next_version": 4, "next_gen": 1},
            proposed_line("b", "CME", "h9"),
            committed_line("b", "CME", "h9", prior=("B", 3, 2),
                           next_=("C", 4, 3)),
        ]
        result: dict = txn.recover(journal)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["leases"]["b"], "committed")
        stale: list = list(journal)
        stale[-1] = committed_line("b", "CME", "h9", prior=("B", 3, 0),
                                   next_=("C", 4, 1))
        bad: dict = txn.recover(stale)
        self.assertEqual(bad["status"], "error")

    def test_earlier_commit_cannot_rollback_after_chained_commit(self) -> None:
        journal: list = [
            proposed_line("L1", "CME", "h1"), committed_line("L1", "CME", "h1"),
            proposed_line("L2", "CME", "h2"),
            committed_line("L2", "CME", "h2", prior=("A", 4, 1),
                           next_=("C", 5, 2)),
            {"kind": "rolled_back", "lease_id": "L1", "ticker": "CME",
             "proposal_hash": "h1", "prior_tier": "B", "prior_version": 3,
             "prior_gen": 0, "next_tier": "A", "next_version": 4, "next_gen": 1},
        ]
        result: dict = txn.recover(journal)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["leases"]["L1"], "blocked")
        self.assertIn("entry_4_rollback_not_current_holder_blocked", result["reasons"])

    def test_true_concurrent_same_prior_rejected(self) -> None:
        journal: list = [
            proposed_line("a", "CME", "h1"), committed_line("a", "CME", "h1"),
            proposed_line("b", "CME", "h9"),
            committed_line("b", "CME", "h9", prior=("B", 3, 0),
                           next_=("C", 4, 1)),
        ]
        result: dict = txn.recover(journal)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["leases"]["b"], "blocked")

    def test_rolled_back_ticker_hash_mismatch_blocked(self) -> None:
        base: list = [
            proposed_line("a", "CME", "h1"), committed_line("a", "CME", "h1"),
        ]
        bad_ticker: list = base + [{"kind": "rolled_back", "lease_id": "a",
                                    "ticker": "ITA", "proposal_hash": "h1"}]
        self.assertEqual(txn.recover(bad_ticker)["status"], "error")
        bad_hash: list = base + [{"kind": "rolled_back", "lease_id": "a",
                                  "ticker": "CME", "proposal_hash": "other"}]
        self.assertEqual(txn.recover(bad_hash)["status"], "error")
        missing_hash: list = base + [{"kind": "rolled_back", "lease_id": "a",
                                      "ticker": "CME"}]
        self.assertEqual(txn.recover(missing_hash)["status"], "error")
        bad_prior: list = base + [{"kind": "rolled_back", "lease_id": "a",
                                   "ticker": "CME", "proposal_hash": "h1",
                                   "prior_tier": "C", "prior_version": 9,
                                   "prior_gen": 9,
                                   "next_tier": "A", "next_version": 4,
                                   "next_gen": 1}]
        self.assertEqual(txn.recover(bad_prior)["status"], "error")

    def test_inflight_proposed_needs_reversal(self) -> None:
        result: dict = txn.recover([proposed_line("solo", "CME", "h1")])
        self.assertEqual(result["leases"]["solo"], "needs_reversal")
        self.assertNotEqual(result["status"], "ok")
        self.assertIn("journal_has_problems", result["reasons"])

    def test_committed_requires_proposal_hash(self) -> None:
        journal: list = [proposed_line("c"),
                         {"kind": "committed", "lease_id": "c",
                          "ticker": "CME",
                          "prior_tier": "B", "prior_version": 3,
                          "prior_gen": 0, "next_tier": "A",
                          "next_version": 4, "next_gen": 1}]
        result: dict = txn.recover(journal)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["leases"]["c"], "blocked")

    def test_proposed_and_expired_require_matching_hashes(self) -> None:
        missing_proposed: dict = txn.recover([
            {"kind": "proposed", "lease_id": "p", "ticker": "CME"},
        ])
        self.assertEqual(missing_proposed["status"], "error")
        self.assertEqual(missing_proposed["leases"]["p"], "blocked")
        missing_expired: dict = txn.recover([
            proposed_line("e", "CME", "h1"),
            {"kind": "expired", "lease_id": "e", "ticker": "CME"},
        ])
        self.assertEqual(missing_expired["status"], "error")
        mismatched_expired: dict = txn.recover([
            proposed_line("m", "CME", "h1"),
            {"kind": "expired", "lease_id": "m", "ticker": "CME",
             "proposal_hash": "other"},
        ])
        self.assertEqual(mismatched_expired["status"], "error")

    def test_expired_lock_released_without_expire_call(self) -> None:
        m0: dict = machine()
        m1, r1 = txn.propose(m0, proposal("lease-001", "tok-1"), now_utc=NOW)
        self.assertTrue(r1["ok"])
        second: dict = proposal("lease-002", "tok-2")
        second.update({"created_at_utc": EXPIRED_NOW,
                       "expires_at_utc": "2026-10-01T16:00:00Z"})
        m2, r2 = txn.propose(m1, second, now_utc=EXPIRED_NOW)
        self.assertTrue(r2["ok"], msg=f"expired staged lock not released: {r2}")

    def test_duplicate_case_variant_rows_reported(self) -> None:
        m: dict = txn.new_machine([
            {"ticker": "CME", "tier": "B", "version": 3},
            {"ticker": "CME", "tier": "A", "version": 4},
            {"ticker": " cme ", "tier": "A", "version": 5},
        ], universe_id=UNIVERSE, snapshot_id=SNAPSHOT)
        self.assertEqual(len(m["slots"]), 1)
        self.assertEqual(m["slots"]["CME"]["tier"], "B")
        self.assertTrue(len(m.get("row_issues", [])) >= 2)
        reasons: list = [r.get("reason") for r in m["row_issues"]]
        self.assertIn("duplicate_ticker_row", reasons)
        self.assertIn("case_variant_duplicate_ticker_row", reasons)

    def test_invalid_row_precedes_duplicate_classification(self) -> None:
        m: dict = txn.new_machine([
            {"ticker": "CME", "tier": "B", "version": 3},
            {"ticker": "cme", "tier": "Z", "version": 4},
        ], universe_id=UNIVERSE, snapshot_id=SNAPSHOT)
        self.assertEqual(m["slots"]["CME"]["tier"], "B")
        self.assertEqual(m["row_issues"], [
            {"ticker": "cme", "reason": "invalid_ticker_row"},
        ])


class ImmutabilitySurfaceTests(unittest.TestCase):
    PATH = Path(__file__).resolve().parent / "phase4_tier_transaction.py"

    def test_inputs_not_mutated(self) -> None:
        m0: dict = machine()
        snap: dict = copy.deepcopy(m0)
        prop: dict = proposal()
        prop_snap: dict = copy.deepcopy(prop)
        m1, _ = txn.propose(m0, prop, now_utc=NOW)
        self.assertEqual(m0, snap)
        self.assertEqual(prop, prop_snap)
        self.assertIsNot(m1, m0)
        snap1: dict = copy.deepcopy(m1)
        m2, _ = txn.commit(m1, lease_id="lease-001", token=TOK,
                           approval=approval(), now_utc=LATER)
        self.assertEqual(m1, snap1)
        self.assertEqual(m2["slots"]["CME"]["tier"], "A")

    def test_no_sqlite_filesystem_network_cli(self) -> None:
        tree: ast.AST = ast.parse(self.PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotEqual(alias.name.split(".")[0], "sqlite3")
                    self.assertNotIn(alias.name.split(".")[0], {"socket", "urllib", "http", "subprocess", "argparse"})
            if isinstance(node, ast.ImportFrom):
                module: str = (node.module or "").split(".")[0]
                self.assertNotEqual(module, "sqlite3")
                self.assertNotIn(module, {"socket", "urllib", "http", "subprocess", "argparse"})
            if isinstance(node, ast.Call):
                func: ast.AST = node.func
                if isinstance(func, ast.Name):
                    self.assertNotIn(func.id, {"open", "exec", "eval"})
                if isinstance(func, ast.Attribute):
                    self.assertNotIn(func.attr, {"connect", "urlopen", "request", "popen", "system"})
        text: str = self.PATH.read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", text)
        self.assertNotIn("sys.argv", text)

    def test_no_finance_portfolio_fields(self) -> None:
        text: str = self.PATH.read_text(encoding="utf-8").lower()
        for term in ("holding", "holdings", "sizing", "capital", "execution",
                     "account", "money", "allocation", "weight", "cash",
                     "shares", "quantity", "tranche", "rebalance", "portfolio"):
            self.assertIsNone(re.search(r"\b" + re.escape(term) + r"\b", text),
                              msg=f"forbidden term {term}")
        hits: list[str] = re.findall(r"\border\b", text)
        self.assertEqual(hits, [], msg="forbidden term order")


if __name__ == "__main__":
    unittest.main()
