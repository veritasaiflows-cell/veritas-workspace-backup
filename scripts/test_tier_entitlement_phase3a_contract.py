"""Regression guards for the Phase 3A dynamic-routing contract amendment."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "06. Playbooks" / "Project Continuity" / "Tier Entitlement and Atomic Promotion Review Contract.md"
PLAN = ROOT / "tmp" / "tier-entitlement-v091-phase3a-plan.json"
PACKET = ROOT / "tmp" / "tier-entitlement-v091-phase3-external-cutover-approval-packet.json"


class Phase3ADynamicContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = CONTRACT.read_text(encoding="utf-8")
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.packet = json.loads(PACKET.read_text(encoding="utf-8"))

    def test_canonical_scope_has_no_eligibility_or_capacity_filter(self) -> None:
        scope = self.plan["canonical_scope_contract"]
        self.assertEqual(
            scope["membership_predicate"],
            "securities.active=1 AND universe_membership.tier IN ('A','B')",
        )
        self.assertEqual(
            scope["decision_grade_eligible_behavior"],
            "returned_with_entitlement_integrity_breach_not_filtered",
        )
        self.assertIn("There is no code-level ticker ceiling", self.contract)
        self.assertIn("scope_over_envelope", self.contract)

    def test_scope_integrity_and_external_gate_are_explicit(self) -> None:
        scope = self.plan["canonical_scope_contract"]
        self.assertEqual(scope["provider_gate_failure"], "external_scope_gate_not_enabled")
        self.assertIn("guarded_sql_scope_tier_conflict", self.contract)
        self.assertIn("guarded_sql_scope_payload_fingerprint_mismatch", self.contract)
        self.assertIn("SHA-256 digest", self.contract)

    def test_static_external_cutover_packet_is_not_an_approval_surface(self) -> None:
        self.assertEqual(self.packet["status"], "superseded_by_phase3a_dynamic_contract")
        self.assertIsNone(self.packet["decision_requested"])
        self.assertIn("historical_proposal_not_authorized", self.packet)
        self.assertIn("requirements_for_any_replacement_packet", self.packet)

    def test_supersession_binds_the_amended_contract_and_plan(self) -> None:
        binding = self.packet["supersession_source_binding"]
        for path in (CONTRACT, PLAN):
            relative = path.relative_to(ROOT).as_posix()
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(binding[relative], actual)


if __name__ == "__main__":
    unittest.main()
