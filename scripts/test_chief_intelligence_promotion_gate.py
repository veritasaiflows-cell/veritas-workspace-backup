from __future__ import annotations

import unittest

import chief_intelligence_promotion_gate as gate


class ChiefIntelligencePromotionGateTests(unittest.TestCase):
    def test_gate_builds_review_only_ranked_candidates(self) -> None:
        payload = gate.build_gate()
        validation = gate.validate_gate(payload)
        self.assertEqual(validation["status"], "ok", validation)
        self.assertGreater(payload["summary"]["candidate_count"], 0)
        self.assertTrue(payload["authority"]["review_only"])
        for key in gate.FALSE_AUTHORITY_KEYS:
            self.assertIs(payload["authority"][key], False, key)

    def test_no_promoted_candidate_has_veto_or_out_of_band_state(self) -> None:
        payload = gate.build_gate()
        promoted = [
            item for item in payload["candidates"]
            if item["chief_intelligence_verdict"] == "promote_for_owner_review"
        ]
        for item in promoted:
            self.assertEqual(item["vetoes"], [], item)
            self.assertEqual(item["band_status"], "IN_BAND", item)
        if not promoted:
            self.assertIn("no candidate reached promote_for_owner_review", gate.validate_gate(payload)["warnings"])

    def test_config_backed_band_status_blocks_ph_and_watch_only_monitors(self) -> None:
        payload = gate.build_gate()
        by_ticker = {item["ticker"]: item for item in payload["candidates"]}
        if by_ticker["PH"]["chief_intelligence_verdict"] == "promote_for_owner_review":
            self.assertEqual(by_ticker["PH"]["band_status"], "IN_BAND")
            self.assertEqual(by_ticker["PH"]["vetoes"], [])
        else:
            self.assertNotEqual(by_ticker["PH"]["band_status"], "IN_BAND")
        self.assertNotEqual(by_ticker["VAW"]["chief_intelligence_verdict"], "promote_for_owner_review")

    def test_sql_first_band_proposal_supersedes_legacy_portfolio_band(self) -> None:
        bands = gate.entry_bands_from_band_proposals({
            "generated_at_utc": "2026-06-30T15:00:00Z",
            "proposals": [{
                "ticker": "ETN",
                "canonical_apply_eligible": True,
                "current_band_low": 392.15,
                "current_band_high": 411.45,
                "current_stop": 372.54,
                "suggested_band_low": 401.10,
                "suggested_band_high": 421.25,
                "suggested_stop": 380.50,
                "close": 407.50,
                "band_status": "IN_BAND",
            }],
        })
        etn = bands["ETN"]
        self.assertEqual(etn["source_priority"], "sql_first_band_proposal")
        self.assertTrue(etn["supersedes_portfolio_config_band"])
        legacy_band = etn.get("legacy_current_band")
        self.assertIsInstance(legacy_band, dict)
        self.assertNotEqual(etn["low"], legacy_band.get("low"))
        self.assertNotEqual(etn["high"], legacy_band.get("high"))

    def test_in_band_no_veto_candidate_is_not_labeled_reclaim_or_pullback(self) -> None:
        verdict = gate.verdict_from(
            42.59,
            [],
            "IN_BAND",
            "ALMOST / NEAR-EARNINGS CAUTION",
            "ALMOST",
            "NVDA",
        )
        self.assertEqual(verdict, "in_band_review_hold")

        payload = gate.build_gate()
        by_ticker = {item["ticker"]: item for item in payload["candidates"]}
        nvda = by_ticker["NVDA"]
        if nvda["band_status"] == "IN_BAND" and not nvda["vetoes"]:
            self.assertNotEqual(nvda["chief_intelligence_verdict"], "watch_for_reclaim_or_pullback")

    def test_current_band_status_used_when_suggested_band_not_applyable(self) -> None:
        bands = gate.entry_bands_from_band_proposals({
            "generated_at_utc": "2026-06-30T15:00:00Z",
            "proposals": [{
                "ticker": "BRK.B",
                "canonical_apply_eligible": False,
                "current_band_low": 489.78,
                "current_band_high": 498.19,
                "current_stop": 483.05,
                "suggested_band_low": 478.96,
                "suggested_band_high": 491.62,
                "suggested_stop": 469.93,
                "close": 497.04,
                "band_status": "NEAR_BAND",
            }],
        })
        self.assertEqual(bands["BRK.B"]["band_status"], "IN_BAND")
        self.assertEqual(bands["BRK.B"]["low"], 489.78)
        self.assertEqual(bands["BRK.B"]["high"], 498.19)

    def test_probability_readiness_stays_non_model_authority(self) -> None:
        payload = gate.build_gate()
        self.assertNotEqual(payload["summary"]["probability_readiness"], "READY")
        self.assertFalse(payload["authority"]["probability_or_modeling_authority"])
        self.assertFalse(payload["authority"]["model_ranked_deployment_allowed"])
        joined_cautions = " ".join(
            caution
            for candidate in payload["candidates"]
            for caution in candidate.get("cautions", [])
        )
        self.assertIn("no win-rate/model claim allowed", joined_cautions)

    def test_in_band_soft_opportunity_review_debt_holds_without_veto(self) -> None:
        opportunity = {
            "blocked_or_deferred": ["GS"],
            "candidate_reviews": {
                "GS": {
                    "band_status": "IN_BAND",
                    "below_stop_or_repair": False,
                    "blocked_reasons": ["band_review_debt", "near_catalyst_window"],
                    "blocking_gate": "risk/sizing / peer priority",
                    "deployment_status": "PROMOTION REVIEW",
                    "monitoring_flags": ["band_review_required", "near_catalyst_window"],
                    "next_action": "Keep secondary to JPM unless explicit review says otherwise",
                    "queue_judgment": "hold in promotion review",
                    "workflow_state": "ALMOST",
                },
            },
        }
        score, positives, vetoes, cautions = gate.score_candidate(
            "GS",
            {"close": 1011.37},
            {"surface_state": "PROMOTION REVIEW"},
            {},
            {},
            {},
            {"low": 971.53, "high": 1048.14, "stop": 928.97},
            {},
            opportunity,
            True,
        )
        self.assertEqual(vetoes, [])
        self.assertIn("current opportunity digest review debt", cautions)
        self.assertIn("inside written band", positives)
        self.assertEqual(
            gate.verdict_from(score, vetoes, "IN_BAND", "PROMOTION REVIEW", "ALMOST", "GS"),
            "in_band_review_hold",
        )

    def test_in_band_hard_opportunity_blocker_still_vetoes(self) -> None:
        opportunity = {
            "blocked_or_deferred": ["GS"],
            "candidate_reviews": {
                "GS": {
                    "band_status": "IN_BAND",
                    "below_stop_or_repair": False,
                    "blocked_reasons": ["missing_source_open"],
                    "blocking_gate": "source-open missing",
                    "deployment_status": "PROMOTION REVIEW",
                    "monitoring_flags": ["source_open_missing"],
                    "workflow_state": "ALMOST",
                },
            },
        }
        _, _, vetoes, cautions = gate.score_candidate(
            "GS",
            {"close": 1011.37},
            {"surface_state": "PROMOTION REVIEW"},
            {},
            {},
            {},
            {"low": 971.53, "high": 1048.14, "stop": 928.97},
            {},
            opportunity,
            True,
        )
        self.assertEqual(vetoes, ["current opportunity digest blocked/deferred"])
        self.assertNotIn("current opportunity digest review debt", cautions)

    def test_vetoed_candidates_explain_root_cause_in_plain_english(self) -> None:
        payload = gate.build_gate()
        vetoed = [item for item in payload["candidates"] if item.get("vetoes")]
        self.assertGreater(len(vetoed), 0, "expected at least one vetoed candidate")
        for item in vetoed:
            self.assertTrue(item.get("veto_details"), item)
            self.assertTrue(item.get("root_cause_blockers"), item)
            self.assertTrue(item.get("plain_english_blockers"), item)
            for detail in item["veto_details"]:
                self.assertIn("plain_english", detail)
                self.assertIn("source_artifact", detail)
        by_ticker = {item["ticker"]: item for item in payload["candidates"]}
        if "NVDA" in by_ticker and by_ticker["NVDA"].get("vetoes"):
            joined = " ".join(by_ticker["NVDA"].get("plain_english_blockers") or [])
            self.assertIn("NVDA was in band", joined)
            self.assertIn("promotion-review debt", joined)


if __name__ == "__main__":
    unittest.main()
