"""Tests for phase4_tier_readiness (stdlib unittest; Main runs under pytest)."""

from __future__ import annotations

import ast
import copy
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase4_tier_readiness as readiness

NOW = "2026-09-26T16:00:00Z"
UNIVERSE = "universe-test-01"
SNAPSHOT = "snapshot-test-01"


def base_evidence() -> dict:
    return {
        "ticker": "CME",
        "thesis": {"status": "accepted", "review_due": "2026-10-26", "ticker": "CME"},
        "band": {
            "ticker": "CME", "low": 258.87, "high": 267.8765,
            "invalidation": 249.9238, "atr20": 2.0, "confidence": 0.72,
            "methodology": "mech-v3-floor-atr20",
            "generated_at_utc": "2026-09-26T15:00:00Z",
            "pinned": True, "pin_id": "pin-001",
        },
        "bars": {"valid_bars": 252, "repaired_bars": 2},
        "earnings": {"present": True, "updated_at_utc": "2026-09-20T12:00:00Z"},
        "macro": {"present": True, "updated_at_utc": "2026-09-25T12:00:00Z"},
        "benchmark": {"sector_etf": "XLI"},
        "ledger": {"has_state_snapshot": True},
    }


def evaluate(ev: dict, **kwargs: object) -> dict:
    params: dict = {"now_utc": NOW, "universe_id": UNIVERSE,
                    "snapshot_id": SNAPSHOT, "prior_tier": "B",
                    "prior_version": 3, "expected_ticker": "CME",
                    "expected_pin_id": "pin-001"}
    params.update(kwargs)
    return readiness.evaluate_readiness(ev, **params)


def eligible(res: dict, ev: dict, **kwargs: object) -> dict:
    params: dict = {"now_utc": NOW, "expected_ticker": "CME",
                    "universe_id": UNIVERSE, "snapshot_id": SNAPSHOT,
                    "expected_pin_id": "pin-001"}
    params.update(kwargs)
    return readiness.recommendation_eligibility(res, ev, **params)


def promote(res: dict, ev: dict, qual: dict, **kwargs: object) -> dict:
    params: dict = {"now_utc": NOW, "expected_ticker": "CME",
                    "universe_id": UNIVERSE, "snapshot_id": SNAPSHOT,
                    "expected_pin_id": "pin-001"}
    params.update(kwargs)
    return readiness.evaluate_promotion(res, ev, qual, **params)


class PassFailTest(unittest.TestCase):
    def test_happy_path_ready(self) -> None:
        result: dict = evaluate(base_evidence())
        self.assertTrue(result["ready"])
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["recommendation_eligible"])
        self.assertEqual(result["provenance"]["universe_id"], UNIVERSE)
        self.assertEqual(result["ticker"], "CME")

    def test_universe_not_hardcoded(self) -> None:
        result: dict = readiness.evaluate_readiness(
            base_evidence(), now_utc=NOW,
            universe_id="custom-universe-99", snapshot_id="snap-77",
            expected_ticker="CME", expected_pin_id="pin-001",
        )
        self.assertTrue(result["ready"])
        self.assertEqual(result["provenance"]["universe_id"], "custom-universe-99")

    def test_missing_universe_fails(self) -> None:
        result: dict = readiness.evaluate_readiness(
            base_evidence(), now_utc=NOW, universe_id="", snapshot_id=SNAPSHOT,
            expected_ticker="CME", expected_pin_id="pin-001",
        )
        self.assertFalse(result["ready"])
        self.assertIn("universe_identity_missing", result["reasons"])

    def test_returns_are_isolated_copies(self) -> None:
        first: dict = evaluate(base_evidence())
        first["reasons"].append("forged")
        first["provenance"]["universe_id"] = "forged"
        second: dict = evaluate(base_evidence())
        self.assertEqual(second["reasons"], [])
        self.assertEqual(second["provenance"]["universe_id"], UNIVERSE)


class GateTests(unittest.TestCase):
    def check_fail(self, mutate: object, code: str) -> None:
        ev: dict = base_evidence()
        if callable(mutate):
            mutate(ev)
        result: dict = evaluate(ev)
        self.assertFalse(result["ready"], msg=f"expected fail for {code}")
        self.assertIn(code, result["reasons"])

    def test_thesis_gates(self) -> None:
        self.check_fail(lambda e: e["thesis"].update({"status": "draft"}), "thesis_not_accepted")
        self.check_fail(lambda e: e["thesis"].update({"review_due": "2026-09-01"}), "thesis_overdue")
        self.check_fail(lambda e: e["thesis"].update({"review_due": "not-a-date"}), "thesis_review_due_malformed")
        self.check_fail(lambda e: e.pop("thesis"), "thesis_missing")

    def test_band_freshness_pin_confidence(self) -> None:
        self.check_fail(lambda e: e["band"].update({"generated_at_utc": "2026-09-01T00:00:00Z"}), "band_stale")
        self.check_fail(lambda e: e["band"].update({"pinned": False}), "band_not_pin_bound")
        self.check_fail(lambda e: e["band"].update({"pin_id": ""}), "band_not_pin_bound")
        self.check_fail(lambda e: e["band"].update({"confidence": None}), "band_confidence_missing")
        self.check_fail(lambda e: e["band"].update({"confidence": True}), "band_confidence_missing")
        self.check_fail(lambda e: e["band"].update({"methodology": "mech-v1-old"}), "band_methodology_unsupported")
        self.check_fail(lambda e: e.pop("band"), "band_missing")
        self.check_fail(lambda e: e["band"].update({"generated_at_utc": "bad-ts"}), "band_timestamp_malformed")
        self.check_fail(lambda e: e["band"].update({"generated_at_utc": "2026-09-26T16:00:00"}), "band_timestamp_malformed")

    def test_confidence_nan_inf_range(self) -> None:
        self.check_fail(lambda e: e["band"].update({"confidence": float("nan")}), "band_confidence_malformed")
        self.check_fail(lambda e: e["band"].update({"confidence": float("inf")}), "band_confidence_malformed")
        self.check_fail(lambda e: e["band"].update({"confidence": -5}), "band_confidence_out_of_range")
        self.check_fail(lambda e: e["band"].update({"confidence": 1.5}), "band_confidence_out_of_range")
        self.check_fail(lambda e: e["band"].update({"confidence": "high"}), "band_confidence_malformed")

    def test_band_levels_finite(self) -> None:
        self.check_fail(lambda e: e["band"].update({"high": float("inf")}), "band_levels_malformed")
        self.check_fail(lambda e: e["band"].update({"low": float("nan")}), "band_levels_malformed")
        self.check_fail(lambda e: e["band"].update({"low": -1.0}), "band_levels_malformed")
        self.check_fail(lambda e: e["band"].update({"atr20": True}), "band_levels_malformed")

    def test_pin_and_ticker_binding(self) -> None:
        result: dict = evaluate(base_evidence(), expected_pin_id="other-pin")
        self.assertFalse(result["ready"])
        self.assertIn("band_pin_mismatch", result["reasons"])
        ev2: dict = base_evidence()
        ev2["band"]["ticker"] = "ITA"
        result2: dict = evaluate(ev2)
        self.assertFalse(result2["ready"])
        self.assertIn("ticker_mismatch", result2["reasons"])
        ev3: dict = base_evidence()
        del ev3["ticker"]
        result3: dict = evaluate(ev3)
        self.assertFalse(result3["ready"])
        self.assertIn("ticker_missing", result3["reasons"])
        result4: dict = evaluate(base_evidence(), expected_ticker="ITA")
        self.assertFalse(result4["ready"])
        self.assertIn("ticker_mismatch", result4["reasons"])

    def test_subobject_ticker_required(self) -> None:
        ev: dict = base_evidence()
        del ev["thesis"]["ticker"]
        result: dict = evaluate(ev)
        self.assertFalse(result["ready"])
        self.assertIn("ticker_mismatch", result["reasons"])
        ev2: dict = base_evidence()
        del ev2["band"]["ticker"]
        result2: dict = evaluate(ev2)
        self.assertFalse(result2["ready"])
        self.assertIn("ticker_mismatch", result2["reasons"])

    def test_nonstring_pin_expectation_never_crashes(self) -> None:
        result: dict = evaluate(base_evidence(), expected_pin_id=5)
        self.assertFalse(result["ready"])
        self.assertIn("band_pin_mismatch", result["reasons"])

    def test_band_geometry_atr(self) -> None:
        self.check_fail(lambda e: e["band"].update({"invalidation": 260.0}), "invalidation_geometry_invalid")
        self.check_fail(lambda e: e["band"].update({"low": 270.0, "high": 260.0}), "invalidation_geometry_invalid")
        self.check_fail(lambda e: e["band"].update({"low": 260.0, "high": 260.5, "atr20": 2.0}), "band_width_below_atr20")
        self.check_fail(lambda e: e["band"].update({"atr20": 0}), "atr20_malformed")
        ev: dict = base_evidence()
        ev["band"].update({"low": 260.0, "high": 262.0, "invalidation": 259.0, "atr20": 2.0})
        self.assertTrue(evaluate(ev)["ready"])
        ev2: dict = base_evidence()
        ev2["band"].update({"invalidation": ev2["band"]["low"]})
        result: dict = evaluate(ev2)
        self.assertFalse(result["ready"])
        self.assertIn("invalidation_geometry_invalid", result["reasons"])
        self.check_fail(lambda e: e["band"].update({"low": "x"}), "band_levels_malformed")

    def test_bar_repair_boundaries(self) -> None:
        self.check_fail(lambda e: e["bars"].update({"valid_bars": 251}), "bars_insufficient")
        self.check_fail(lambda e: e["bars"].update({"repaired_bars": 3}), "repairs_exceeded")
        self.check_fail(lambda e: e["bars"].update({"valid_bars": "many"}), "bars_malformed")
        self.check_fail(lambda e: e["bars"].update({"valid_bars": True}), "bars_malformed")
        ev: dict = base_evidence()
        self.assertTrue(evaluate(ev)["ready"])
        ev["bars"].update({"valid_bars": 300, "repaired_bars": 0})
        self.assertTrue(evaluate(ev)["ready"])

    def test_context_benchmark_snapshot(self) -> None:
        self.check_fail(lambda e: e["earnings"].update({"present": False}), "earnings_missing")
        self.check_fail(lambda e: e["macro"].update({"present": False}), "macro_missing")
        self.check_fail(lambda e: e["earnings"].update({"updated_at_utc": "2026-01-01T00:00:00Z"}), "earnings_stale")
        self.check_fail(lambda e: e["macro"].update({"updated_at_utc": "2026-01-01T00:00:00Z"}), "macro_stale")
        self.check_fail(lambda e: e["macro"].update({"updated_at_utc": "2026-09-26T16:00:00"}), "macro_timestamp_malformed")
        self.check_fail(lambda e: e["benchmark"].update({"sector_etf": ""}), "benchmark_missing")
        self.check_fail(lambda e: e.pop("benchmark"), "benchmark_missing")
        self.check_fail(lambda e: e["ledger"].update({"has_state_snapshot": False}), "ledger_snapshot_missing")
        self.check_fail(lambda e: e.pop("ledger"), "ledger_snapshot_missing")

    def test_malformed_unknown_fail_closed(self) -> None:
        result: dict = readiness.evaluate_readiness(
            "not-a-mapping", now_utc=NOW, universe_id=UNIVERSE, snapshot_id=SNAPSHOT,
            expected_ticker="CME", expected_pin_id="pin-001",
        )
        self.assertFalse(result["ready"])
        self.assertIn("evidence_malformed", result["reasons"])
        result2: dict = readiness.evaluate_readiness(
            {}, now_utc="bad-now", universe_id=UNIVERSE, snapshot_id=SNAPSHOT,
            expected_ticker="CME", expected_pin_id="pin-001",
        )
        self.assertFalse(result2["ready"])
        self.assertIn("now_malformed", result2["reasons"])
        result3: dict = readiness.evaluate_readiness(
            {"ticker": "CME"}, now_utc="2026-09-26T16:00:00",
            universe_id=UNIVERSE, snapshot_id=SNAPSHOT,
            expected_ticker="CME", expected_pin_id="pin-001",
        )
        self.assertFalse(result3["ready"])
        self.assertIn("now_malformed", result3["reasons"])

    def test_prior_invalid(self) -> None:
        result: dict = evaluate(base_evidence(), prior_tier="Z", prior_version=3)
        self.assertFalse(result["ready"])
        self.assertIn("prior_tier_invalid", result["reasons"])
        result2: dict = evaluate(base_evidence(), prior_tier="B", prior_version="x")
        self.assertFalse(result2["ready"])
        self.assertIn("prior_version_invalid", result2["reasons"])


class AuthorityTests(unittest.TestCase):
    def test_prior_tier_authoritative(self) -> None:
        auth: dict = readiness.prior_tier_authority("B", 3)
        self.assertEqual(auth["tier"], "B")
        self.assertTrue(auth["authoritative"])
        result: dict = evaluate(base_evidence())
        self.assertEqual(result["prior_effective_tier"], "B")
        self.assertEqual(result["prior_effective_version"], 3)

    def test_prior_authority_rejects_invalid(self) -> None:
        auth: dict = readiness.prior_tier_authority("Z", "x")
        self.assertFalse(auth["authoritative"])
        self.assertIn("prior_tier_invalid", auth["reasons"])
        self.assertIn("prior_version_invalid", auth["reasons"])

    def test_recommendation_ineligible_when_not_ready(self) -> None:
        ev: dict = base_evidence()
        ev["bars"].update({"valid_bars": 10})
        result: dict = evaluate(ev)
        out: dict = eligible(result, ev)
        self.assertFalse(out["eligible"])
        self.assertFalse(result["recommendation_eligible"])
        out2: dict = eligible("bad", ev)
        self.assertFalse(out2["eligible"])
        self.assertIn("readiness_missing", out2["reasons"])

    def test_recommendation_rejects_bare_and_stale(self) -> None:
        ev: dict = base_evidence()
        bare: dict = eligible({"ready": True}, ev)
        self.assertFalse(bare["eligible"])
        fresh: dict = evaluate(ev)
        ok: dict = eligible(fresh, ev)
        self.assertTrue(ok["eligible"])
        stale: dict = eligible(fresh, ev, now_utc="2026-10-10T16:00:00Z")
        self.assertFalse(stale["eligible"])
        self.assertIn("readiness_stale", stale["reasons"])
        forged: dict = copy.deepcopy(fresh)
        forged["evidence_hash"] = "0" * 64
        out: dict = eligible(forged, ev)
        self.assertFalse(out["eligible"])
        self.assertIn("readiness_inconsistent", out["reasons"])

    def test_eligibility_and_promotion_require_explicit_pin_identity(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        with self.assertRaises(TypeError):
            readiness.recommendation_eligibility(fresh, ev, now_utc=NOW)
        with self.assertRaises(TypeError):
            readiness.evaluate_promotion(
                fresh, ev, {"evidence_strength": "strong", "review": "explicit"},
                now_utc=NOW)
        blank: dict = eligible(fresh, ev, expected_pin_id="")
        self.assertFalse(blank["eligible"])
        self.assertIn("readiness_expected_pin_missing", blank["reasons"])
        blank_promotion: dict = promote(
            fresh, ev, {"evidence_strength": "strong", "review": "explicit"},
            expected_pin_id="")
        self.assertFalse(blank_promotion["allowed"])
        self.assertIn("readiness_expected_pin_missing", blank_promotion["reasons"])

    def test_handbuilt_consistent_result_rejected(self) -> None:
        ev: dict = base_evidence()
        hand: dict = {"ready": True, "reasons": [], "evidence_hash": "x",
                      "ticker": "CME",
                      "provenance": {"universe_id": UNIVERSE, "snapshot_id": SNAPSHOT,
                                     "now_utc": NOW, "evidence_hash": "x"}}
        out: dict = eligible(hand, ev)
        self.assertFalse(out["eligible"])
        hand_hex: dict = copy.deepcopy(hand)
        hand_hex["evidence_hash"] = "ab" * 32
        hand_hex["provenance"]["evidence_hash"] = "ab" * 32
        out2: dict = eligible(hand_hex, ev)
        self.assertFalse(out2["eligible"])
        self.assertIn("readiness_inconsistent", out2["reasons"])

    def test_identity_binding_enforced(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        out: dict = eligible(fresh, ev, expected_ticker="ITA")
        self.assertFalse(out["eligible"])
        self.assertIn("readiness_ticker_mismatch", out["reasons"])
        out2: dict = eligible(fresh, ev, universe_id="other-universe")
        self.assertFalse(out2["eligible"])
        self.assertIn("readiness_universe_mismatch", out2["reasons"])
        out3: dict = eligible(fresh, ev, snapshot_id="other-snap")
        self.assertFalse(out3["eligible"])
        self.assertIn("readiness_snapshot_mismatch", out3["reasons"])

    def test_max_age_validated(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        for bad_age in (float("nan"), float("inf"), 36500, True, 0, -1, "7"):
            out: dict = eligible(fresh, ev, now_utc="2027-09-26T16:00:00Z",
                                 max_age_days=bad_age)
            self.assertFalse(out["eligible"], msg=f"max_age={bad_age!r} must fail")
            self.assertIn("readiness_max_age_malformed", out["reasons"])
        tight: dict = eligible(fresh, ev, max_age_days=1)
        self.assertTrue(tight["eligible"])


class PromotionDemotionTests(unittest.TestCase):
    def test_promotion_strong(self) -> None:
        ev: dict = base_evidence()
        ok: dict = promote(evaluate(ev), ev,
                           {"evidence_strength": "strong", "review": "explicit"})
        self.assertTrue(ok["allowed"])

    def test_promotion_rejects_forged_and_stale(self) -> None:
        ev: dict = base_evidence()
        forged: dict = promote({"ready": True}, ev,
                               {"evidence_strength": "strong", "review": "explicit"})
        self.assertFalse(forged["allowed"])
        fresh: dict = evaluate(ev)
        stale: dict = promote(fresh, ev,
                              {"evidence_strength": "strong", "review": "explicit"},
                              now_utc="2026-10-10T16:00:00Z")
        self.assertFalse(stale["allowed"])
        nan_age: dict = promote(fresh, ev,
                                {"evidence_strength": "strong", "review": "explicit"},
                                now_utc="2027-09-26T16:00:00Z",
                                max_age_days=float("nan"))
        self.assertFalse(nan_age["allowed"])

    def test_promotion_weak_rejected(self) -> None:
        ev: dict = base_evidence()
        bad: dict = promote(evaluate(ev), ev,
                            {"evidence_strength": "weak", "review": "explicit"})
        self.assertFalse(bad["allowed"])
        self.assertIn("promotion_requires_strong_evidence", bad["reasons"])
        ev2: dict = base_evidence()
        ev2["bars"].update({"valid_bars": 10})
        not_ready: dict = promote(evaluate(ev2), ev2,
                                  {"evidence_strength": "strong", "review": "explicit"})
        self.assertFalse(not_ready["allowed"])

    def valid_claim(self) -> dict:
        return {
            "basis": ["thesis_impairment"],
            "impairment": {"source": "independent-review", "proponent": "sector-desk",
                           "beneficiary": False, "observation_days": 30,
                           "observations": 8, "reason_code": "IMPAIR-1",
                           "sustained": True},
        }

    def test_demotion_staleness_only_rejected(self) -> None:
        claim: dict = {
            "basis": ["staleness", "freshness_decay"],
            "impairment": {"source": "independent-review", "proponent": "sector-desk",
                           "beneficiary": False, "observation_days": 30,
                           "observations": 10, "reason_code": "IMPAIR-1",
                           "sustained": True},
        }
        result: dict = readiness.evaluate_demotion(claim)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_staleness_insufficient", result["reasons"])

    def test_demotion_variant_unknown_nonstring_bases(self) -> None:
        for basis in (["Staleness"], ["stale"], ["something-new"], [[1]]):
            claim: dict = {
                "basis": basis,
                "impairment": {"source": "independent-review", "proponent": "sector-desk",
                               "beneficiary": False, "observation_days": 30,
                               "observations": 10, "reason_code": "IMPAIR-1",
                               "sustained": True},
            }
            result: dict = readiness.evaluate_demotion(claim)
            self.assertFalse(result["allowed"], msg=f"basis must fail closed: {basis}")
        padded: dict = {
            "basis": [" thesis_impairment "],
            "impairment": {"source": "independent-review", "proponent": "sector-desk",
                           "beneficiary": False, "observation_days": 30,
                           "observations": 10, "reason_code": "IMPAIR-1",
                           "sustained": True},
        }
        self.assertTrue(readiness.evaluate_demotion(padded)["allowed"])

    def test_demotion_mixed_basis_rejected(self) -> None:
        claim: dict = self.valid_claim()
        claim["basis"] = ["thesis_impairment", "garbage"]
        result: dict = readiness.evaluate_demotion(claim)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_basis_unknown", result["reasons"])

    def test_demotion_beneficiary_attestation(self) -> None:
        for beneficiary in (True, None, "yes", 1):
            claim: dict = self.valid_claim()
            claim["impairment"]["beneficiary"] = beneficiary
            result: dict = readiness.evaluate_demotion(claim)
            self.assertFalse(result["allowed"], msg=f"beneficiary={beneficiary!r} must fail")
            self.assertIn("demotion_beneficiary_attestation_missing", result["reasons"])
        missing: dict = self.valid_claim()
        del missing["impairment"]["beneficiary"]
        result: dict = readiness.evaluate_demotion(missing)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_beneficiary_attestation_missing", result["reasons"])

    def test_demotion_system_source_variants(self) -> None:
        for source in ("veritas-os-freshness-monitor", "Veritas OS Freshness Monitor",
                       "cron", "scheduler", "monitor", "freshness_monitor"):
            claim: dict = self.valid_claim()
            claim["impairment"]["source"] = source
            result: dict = readiness.evaluate_demotion(claim)
            self.assertFalse(result["allowed"], msg=f"source={source!r} must fail")
            self.assertIn("demotion_system_source_rejected", result["reasons"])
        prop: dict = self.valid_claim()
        prop["impairment"]["proponent"] = "freshness-monitor"
        result: dict = readiness.evaluate_demotion(prop)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_system_proponent_rejected", result["reasons"])
        code: dict = self.valid_claim()
        code["impairment"]["reason_code"] = "staleness"
        result2: dict = readiness.evaluate_demotion(code)
        self.assertFalse(result2["allowed"])
        self.assertIn("demotion_reason_code_invalid", result2["reasons"])

    def test_demotion_system_source_qa_variants(self) -> None:
        qa_sources: tuple[str, ...] = (
            "CRON", "Scheduler", "AUTO", "System", "MACHINE",
            "auto bot", "AutoBot", "auto_bot", "AUTO-BOT",
            "veritasosfreshnessmonitor", "VeritasOSFreshnessMonitor",
            "freshness monitor", "FRESHNESS-MONITOR", "os monitor",
            "os-monitor", "system monitor", "machine bot",
            "cron\u200bscheduler",
        )
        for source in qa_sources:
            claim: dict = self.valid_claim()
            claim["impairment"]["source"] = source
            result: dict = readiness.evaluate_demotion(claim)
            self.assertFalse(result["allowed"], msg=f"source={source!r} must fail")
            self.assertIn("demotion_system_source_rejected", result["reasons"])
            prop: dict = self.valid_claim()
            prop["impairment"]["proponent"] = source
            result2: dict = readiness.evaluate_demotion(prop)
            self.assertFalse(result2["allowed"], msg=f"proponent={source!r} must fail")
            self.assertIn("demotion_system_proponent_rejected", result2["reasons"])

    def test_demotion_reason_code_decay_variants(self) -> None:
        for code in ("stale-data", "STALE", "freshness-decay", "data-gap",
                      "missing-bars", "needs-update", "UPDATE_REQUIRED",
                      "gap_detected", "staleness"):
            claim: dict = self.valid_claim()
            claim["impairment"]["reason_code"] = code
            result: dict = readiness.evaluate_demotion(claim)
            self.assertFalse(result["allowed"], msg=f"code={code!r} must fail")
            self.assertIn("demotion_reason_code_invalid", result["reasons"])

    def test_demotion_proponent_required(self) -> None:
        no_prop: dict = self.valid_claim()
        del no_prop["impairment"]["proponent"]
        result: dict = readiness.evaluate_demotion(no_prop)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_proponent_missing", result["reasons"])

    def test_demotion_thresholds_not_claimant_set(self) -> None:
        claim: dict = self.valid_claim()
        claim["min_days"] = 0
        claim["min_observations"] = 0
        claim["impairment"]["observation_days"] = 0
        claim["impairment"]["observations"] = 0
        result: dict = readiness.evaluate_demotion(claim)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_insufficient_duration", result["reasons"])
        self.assertIn("demotion_insufficient_observations", result["reasons"])
        crashy: dict = self.valid_claim()
        crashy["min_days"] = "abc"
        crashy["min_observations"] = None
        result2: dict = readiness.evaluate_demotion(crashy)
        self.assertTrue(result2["allowed"])

    def test_demotion_malformed_never_raises(self) -> None:
        for bad in (None, "x", {"basis": "not-a-list"},
                    {"basis": [], "impairment": {}}, {"basis": ["thesis_impairment"]}):
            result: dict = readiness.evaluate_demotion(bad)
            self.assertFalse(result["allowed"])

    def test_demotion_duration_observations(self) -> None:
        short: dict = self.valid_claim()
        short["impairment"]["observation_days"] = 5
        short["impairment"]["observations"] = 1
        result: dict = readiness.evaluate_demotion(short)
        self.assertFalse(result["allowed"])
        self.assertIn("demotion_insufficient_duration", result["reasons"])
        self.assertIn("demotion_insufficient_observations", result["reasons"])

    def test_demotion_valid_allowed(self) -> None:
        result: dict = readiness.evaluate_demotion(self.valid_claim())
        self.assertTrue(result["allowed"])


class ReadinessBindingTests(unittest.TestCase):
    def test_ready_flip_rejected(self) -> None:
        ev: dict = base_evidence()
        ev["bars"].update({"valid_bars": 10})
        bad_hash: str = readiness.canonical_evidence_hash(ev)
        forged: dict = {"ready": True, "reasons": [], "evidence_hash": bad_hash,
                        "ticker": "CME",
                        "prior_effective_tier": "B", "prior_effective_version": 3,
                        "provenance": {"universe_id": UNIVERSE,
                                       "snapshot_id": SNAPSHOT, "now_utc": NOW,
                                       "evidence_hash": bad_hash}}
        out: dict = eligible(forged, ev)
        self.assertFalse(out["eligible"])
        self.assertIn("readiness_reevaluation_failed", out["reasons"])
        out2: dict = promote(forged, ev,
                             {"evidence_strength": "strong", "review": "explicit"})
        self.assertFalse(out2["allowed"])

    def test_reasons_flip_rejected(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        tampered: dict = copy.deepcopy(fresh)
        tampered["reasons"] = []
        tampered["ready"] = True
        # evidence mutated so re-evaluation disagrees on reasons content
        ev2: dict = copy.deepcopy(ev)
        ev2["bars"].update({"valid_bars": 10})
        real: dict = readiness.evaluate_readiness(
            ev2, now_utc=NOW, universe_id=UNIVERSE, snapshot_id=SNAPSHOT,
            expected_ticker="CME", expected_pin_id="pin-001",
            prior_tier="B", prior_version=3)
        forged2: dict = copy.deepcopy(real)
        forged2["ready"] = True
        forged2["reasons"] = []
        out: dict = eligible(forged2, ev2)
        self.assertFalse(out["eligible"])

    def test_ticker_relabel_rejected(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        relabeled: dict = copy.deepcopy(fresh)
        relabeled["ticker"] = "ITA"
        out: dict = eligible(relabeled, ev)
        self.assertFalse(out["eligible"])
        out2: dict = eligible(relabeled, ev, expected_ticker="ITA")
        self.assertFalse(out2["eligible"])

    def test_universe_snapshot_relabel_rejected(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        forged_u: dict = copy.deepcopy(fresh)
        forged_u["provenance"]["universe_id"] = "other-universe"
        out: dict = eligible(forged_u, ev)
        self.assertFalse(out["eligible"])
        forged_s: dict = copy.deepcopy(fresh)
        forged_s["provenance"]["snapshot_id"] = "other-snap"
        out2: dict = eligible(forged_s, ev)
        self.assertFalse(out2["eligible"])

    def test_time_shift_rejected(self) -> None:
        ev: dict = base_evidence()
        ev["band"].update({"generated_at_utc": "2026-09-20T16:00:01Z"})
        ev["earnings"].update({"updated_at_utc": "2026-09-20T16:00:01Z"})
        ev["macro"].update({"updated_at_utc": "2026-09-26T15:00:00Z"})
        fresh: dict = evaluate(ev)
        self.assertTrue(fresh["ready"])
        out: dict = eligible(fresh, ev, now_utc="2026-09-27T16:01:00Z")
        self.assertFalse(out["eligible"])

    def test_handbuilt_hash_valid_garbage_rejected(self) -> None:
        garbage: dict = {"ticker": "CME", "band": {"ticker": "CME"}}
        ghash: str = readiness.canonical_evidence_hash(garbage)
        hand: dict = {"ready": True, "reasons": [], "evidence_hash": ghash,
                      "ticker": "CME",
                      "prior_effective_tier": "B", "prior_effective_version": 3,
                      "provenance": {"universe_id": UNIVERSE,
                                     "snapshot_id": SNAPSHOT, "now_utc": NOW,
                                     "evidence_hash": ghash}}
        out: dict = eligible(hand, garbage)
        self.assertFalse(out["eligible"])
        self.assertIn("readiness_reevaluation_failed", out["reasons"])

    def test_pin_mismatch_rejected_via_reeval(self) -> None:
        ev: dict = base_evidence()
        fresh: dict = evaluate(ev)
        out: dict = eligible(fresh, ev, expected_pin_id="other-pin")
        self.assertFalse(out["eligible"])


class StaticSurfaceTests(unittest.TestCase):
    READINESS_PATH = Path(__file__).resolve().parent / "phase4_tier_readiness.py"
    TXN_PATH = Path(__file__).resolve().parent / "phase4_tier_transaction.py"

    def check_surface(self, path: Path) -> None:
        tree: ast.AST = ast.parse(path.read_text(encoding="utf-8"))
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
        text: str = path.read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", text)
        self.assertNotIn("sys.argv", text)

    def check_vocabulary(self, path: Path) -> None:
        text: str = path.read_text(encoding="utf-8").lower()
        for term in ("holding", "holdings", "sizing", "capital", "execution",
                     "account", "money", "allocation", "weight", "cash",
                     "shares", "quantity", "tranche", "rebalance", "portfolio"):
            self.assertIsNone(re.search(r"\b" + re.escape(term) + r"\b", text),
                              msg=f"forbidden term {term} in {path.name}")

    def test_no_sqlite_filesystem_network_cli(self) -> None:
        self.check_surface(self.READINESS_PATH)
        self.check_surface(self.TXN_PATH)

    def test_no_finance_vocabulary(self) -> None:
        self.check_vocabulary(self.READINESS_PATH)
        self.check_vocabulary(self.TXN_PATH)

    def test_import_has_no_side_effects(self) -> None:
        import importlib
        parent: Path = Path(__file__).resolve().parent
        before_files: set[str] = {p.name for p in parent.iterdir()}
        importlib.reload(readiness)
        after_files: set[str] = {p.name for p in parent.iterdir()}
        self.assertEqual(before_files, after_files)
        self.assertTrue(evaluate(base_evidence())["ready"])
        self.assertEqual({p.name for p in parent.iterdir()}, before_files)


if __name__ == "__main__":
    unittest.main()
