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
        self.assertGreater(len(promoted), 0, "expected at least one owner-review promotion candidate")
        for item in promoted:
            self.assertEqual(item["vetoes"], [], item)
            self.assertEqual(item["band_status"], "IN_BAND", item)

    def test_config_backed_band_status_blocks_ph_and_watch_only_monitors(self) -> None:
        payload = gate.build_gate()
        by_ticker = {item["ticker"]: item for item in payload["candidates"]}
        if by_ticker["PH"]["chief_intelligence_verdict"] == "promote_for_owner_review":
            self.assertEqual(by_ticker["PH"]["band_status"], "IN_BAND")
            self.assertEqual(by_ticker["PH"]["vetoes"], [])
        else:
            self.assertNotEqual(by_ticker["PH"]["band_status"], "IN_BAND")
        self.assertNotEqual(by_ticker["VAW"]["chief_intelligence_verdict"], "promote_for_owner_review")

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


if __name__ == "__main__":
    unittest.main()
