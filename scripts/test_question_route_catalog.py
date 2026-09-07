#!/usr/bin/env python3
from __future__ import annotations

import unittest

import question_route_catalog as catalog


class QuestionRouteCatalogTests(unittest.TestCase):
    def test_catalog_is_valid_and_budgeted(self) -> None:
        packet = catalog.build_catalog()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertEqual(packet["summary"]["route_count"], 9)
        self.assertEqual(packet["summary"]["pm_followup_candidate_count"], 0)
        self.assertTrue(packet["summary"]["raw_capture_blocked"])
        self.assertFalse(packet["summary"]["prompt_text_stored"])
        for route in packet["routes"]:
            self.assertLessEqual(route["max_tool_calls"], 8)
            self.assertGreaterEqual(route["max_tool_calls"], 1)
            self.assertTrue(route["first_hop_sources"])

    def test_route_selection_for_common_questions(self) -> None:
        cases = {
            "What are my current finance alerts and recommendations?": "finance_alerts_and_recommendations",
            "Last 10 skill proposals and patches?": "skill_proposals_and_patches",
            "What skills were modified or created?": "skills_modified_or_created",
            "What improvements and opportunities do we have today?": "daily_improvements_and_opportunities",
            "ASI/harness readiness?": "prompt_book_asi_harness_readiness",
            "What are my current opportunities and what needs approval?": "current_opportunities_and_approvals",
            "How can we start using isolated agents for implementation work?": "implementation_agent_orchestration",
            "What is the 5h and 24h isolated agent usage?": "isolated_agent_fleet_usage",
            "Give me the weekly isolated agent fleet report": "isolated_agent_fleet_weekly_report",
        }

        for question, route_id in cases.items():
            selected = catalog.select_route(question)
            self.assertIsNotNone(selected, question)
            self.assertEqual(selected["route_id"], route_id)

    def test_skill_proposal_route_uses_lifecycle_wide_recent_list(self) -> None:
        packet = catalog.build_catalog()
        route = next(
            route for route in packet["routes"] if route["route_id"] == "skill_proposals_and_patches"
        )

        self.assertIn("skill_workshop list --limit 10", route["first_hop_sources"])
        self.assertIn("skill_workshop list --status pending", route["first_hop_sources"])
        self.assertNotIn("skill_workshop list --status applied", route["first_hop_sources"])

    def test_implementation_agent_route_uses_agent_inventory_and_linter(self) -> None:
        packet = catalog.build_catalog()
        route = next(
            route for route in packet["routes"] if route["route_id"] == "implementation_agent_orchestration"
        )

        self.assertEqual(route["max_tool_calls"], 8)
        self.assertIn("openclaw agents list --json", route["first_hop_sources"])
        self.assertIn(
            "python scripts\\agent_bootstrap_linter.py --agents all --write --validate",
            route["first_hop_sources"],
        )
        self.assertIn("agent config/model/binding mutation without exact approval", route["forbidden_tools"])

    def test_fleet_usage_routes_are_metadata_only_and_cost_truthful(self) -> None:
        packet = catalog.build_catalog()
        usage = next(route for route in packet["routes"] if route["route_id"] == "isolated_agent_fleet_usage")
        weekly = next(route for route in packet["routes"] if route["route_id"] == "isolated_agent_fleet_weekly_report")

        self.assertIn("tmp/token-usage-ledger-current.json", usage["first_hop_sources"])
        self.assertIn("5h and 24h fleet usage", usage["response_shape"])
        self.assertTrue(any("not an invoice" in value for value in usage["trust_limits"]))
        self.assertIn("parent-job completion and Main acceptance", weekly["response_shape"])
        self.assertTrue(any("never inferred" in value for value in weekly["trust_limits"]))
        self.assertTrue(any("partial current week" in value for value in weekly["forbidden_tools"]))

    def test_authority_boundaries_preserved(self) -> None:
        packet = catalog.build_catalog()

        for route in packet["routes"]:
            boundary = route["authority_boundary"]
            self.assertTrue(boundary["review_only"])
            self.assertTrue(boundary["metadata_only"])
            self.assertFalse(boundary["raw_prompt_capture"])
            self.assertFalse(boundary["raw_response_capture"])
            self.assertFalse(boundary["tool_payload_capture"])
            self.assertFalse(boundary["cron_schedule_mutation"])
            self.assertFalse(boundary["runtime_config_mutation"])
            self.assertFalse(boundary["finance_canon_portfolio_mutation"])
            self.assertFalse(boundary["capital_deployment"])
            self.assertFalse(boundary["paper_live_account_action"])
            self.assertFalse(boundary["external_delivery"])
            self.assertFalse(boundary["owner_approval_inference"])

    def test_validation_blocks_over_budget_route(self) -> None:
        packet = catalog.build_catalog()
        packet["routes"][0]["max_tool_calls"] = 9

        result = catalog.validate_catalog(packet)

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("max_tool_calls_out_of_bounds" in error for error in result["errors"]))

    def test_validation_blocks_broad_first_hop_source(self) -> None:
        packet = catalog.build_catalog()
        packet["routes"][0]["first_hop_sources"].insert(0, "python scripts\\workspace_index.py")

        result = catalog.validate_catalog(packet)

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("broad_first_hop_source" in error for error in result["errors"]))

    def test_finance_alert_route_requires_guarded_current_proof(self) -> None:
        packet = catalog.build_catalog()
        route = next(
            route for route in packet["routes"] if route["route_id"] == "finance_alerts_and_recommendations"
        )

        joined_sources = "\n".join(route["first_hop_sources"]).lower()
        joined_forbidden = "\n".join(route["forbidden_tools"]).lower()
        joined_limits = "\n".join(route["trust_limits"]).lower()
        joined_proof = "\n".join(route["proof"]).lower()

        self.assertIn("run_alerts_recommendations_chain.py midday", joined_sources)
        self.assertIn("stale evidence presented as current", joined_forbidden)
        self.assertIn("lowers confidence or suppresses", joined_limits)
        self.assertIn("quote-snapshot-proof.json", joined_proof)
        self.assertIn("no owner-approval inference", "\n".join(route["stop_lines"]))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
