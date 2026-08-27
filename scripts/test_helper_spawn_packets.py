#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

import helper_spawn_packets as packets


class HelperSpawnPacketTests(unittest.TestCase):
    def payload_for(self, rows: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema": packets.SCHEMA,
            "authority_boundary": copy.deepcopy(packets.AUTHORITY_BOUNDARY),
            "packets": rows,
        }

    def test_standard_packets_carry_complete_main_routed_assignment_contract(self) -> None:
        rows = packets.standard_packets()
        payload = self.payload_for(rows)
        validation = packets.validate_payload(payload)
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["errors"], [])
        self.assertEqual(validation["warnings"], [])
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(row["assignment_contract_revision"], packets.ASSIGNMENT_CONTRACT_REVISION)
            self.assertTrue(row["agent_id"])
            self.assertTrue(row["parent_job_id"])
            self.assertTrue(row["phase"])
            self.assertTrue(row["owner_workflow"])
            self.assertTrue(row["authority_class"])
            self.assertEqual(row["model_route"]["model"], "openai/gpt-5.6-terra")
            self.assertEqual(row["context_budget"]["max_files"], 6)
            self.assertEqual(row["context_budget"]["max_total_bytes"], 120_000)
            self.assertTrue(row["handoff_contract"]["closeout_revalidation_before_synthesis_required"])
            self.assertEqual(row["retry_contract"]["provisional_incident_update_sla_seconds"], 90)
            self.assertTrue(row["effort_policy"]["escalation_triggers"])
            self.assertEqual(row["read_boundary"], row["files_to_read_first"])
            self.assertEqual(row["write_boundary"]["allowed"], row["allowed_writes"])
            self.assertEqual(row["write_boundary"]["forbidden"], row["forbidden_writes"])
            self.assertEqual(row["stop_lines"], row["forbidden_actions_or_stop_lines"])
            self.assertTrue(row["deliverable"])
            self.assertTrue(row["acceptance_proof"])
            self.assertTrue(row["timeout_or_partial_output_expectation"])
            self.assertEqual(row["closeout_destination"], "Veritas main")
            self.assertFalse(row["authority_boundary"]["direct_agent_to_agent_delegation_allowed"])
            self.assertFalse(row["authority_boundary"]["helper_user_facing_final_authority_allowed"])
        by_id = {row["packet_id"]: row for row in rows}
        self.assertEqual(by_id["implementation-helper"]["model_route"]["reasoning"], "medium")
        self.assertEqual(by_id["independent-qa-helper"]["model_route"]["reasoning"], "high")
        self.assertEqual(by_id["artifact-audit-helper"]["model_route"]["reasoning"], "low")
        self.assertEqual(by_id["finance-evidence-helper"]["model_route"]["reasoning"], "low")
        self.assertEqual(by_id["pm-service-packet-helper"]["model_route"]["reasoning"], "low")

    def test_current_assignment_contract_rejects_missing_fields_and_authority_widening(self) -> None:
        row = packets.standard_packets()[0]
        del row["agent_id"]
        row["authority_boundary"]["direct_agent_to_agent_delegation_allowed"] = True
        payload = self.payload_for([row])
        payload["authority_boundary"]["helper_user_facing_final_authority_allowed"] = True
        validation = packets.validate_payload(payload)
        error_text = "\n".join(validation["errors"])
        self.assertEqual(validation["status"], "error")
        self.assertIn("assignment_missing:agent_id", error_text)
        self.assertIn("direct_agent_to_agent_delegation_allowed_not_false", error_text)
        self.assertIn("helper_user_facing_final_authority_allowed_not_false", error_text)

    def test_current_assignment_contract_requires_named_receiver_and_actual_post_apply_qa_flags(self) -> None:
        row = packets.standard_packets()[0]
        del row["handoff_contract"]["actual_receiver_readback_before_dispatch_required"]
        del row["handoff_contract"]["actual_post_apply_file_hashes_required"]
        validation = packets.validate_payload(self.payload_for([row]))
        error_text = "\n".join(validation["errors"])
        self.assertIn("actual_receiver_readback_before_dispatch_required", error_text)
        self.assertIn("actual_post_apply_file_hashes_required", error_text)
        self.assertIn("handoff_contract_not_fail_closed", error_text)

    def test_legacy_packet_remains_valid_with_warning(self) -> None:
        legacy_boundary = {
            key: value
            for key, value in packets.AUTHORITY_BOUNDARY.items()
            if key
            not in {
                "direct_agent_to_agent_delegation_allowed",
                "helper_user_facing_final_authority_allowed",
            }
        }
        legacy = {
            "packet_id": "legacy-helper",
            "staff_lane_or_role": "Legacy Desk",
            "objective": "Review a bounded artifact.",
            "files_to_read_first": ["artifact"],
            "allowed_actions": ["read-only review"],
            "forbidden_actions_or_stop_lines": ["no mutation"],
            "output_contract": ["status"],
            "acceptance_proof": ["direct inspection"],
            "timeout_or_partial_output_expectation": "10 minutes",
            "merge_expectation": "read_only_report",
            "authority_boundary": legacy_boundary,
        }
        payload = {
            "schema": packets.SCHEMA,
            "authority_boundary": legacy_boundary,
            "packets": [legacy],
        }
        validation = packets.validate_payload(payload)
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["errors"], [])
        self.assertIn("legacy-helper:legacy_packet_without_assignment_contract_revision", validation["warnings"])

    def test_selected_action_preserves_supplied_assignment_metadata(self) -> None:
        handoff = {
            "selected_action": {
                "lane_id": "lane-7",
                "workflow_id": "WF74",
                "phase": "implementation",
                "description": "Patch the named validator.",
            },
            "helper_lane_contract": {
                "primary_lane": "implementation",
                "staff_lane": "Implementation Builder",
                "agent_id": "implementation-builder",
                "authority_class": "workspace_scoped_distinct_output",
                "model_route": copy.deepcopy(packets.DEFAULT_MODEL_ROUTE),
                "files_to_read_first": ["validator.py"],
                "allowed_writes": ["patches/validator.py"],
                "forbidden_writes": ["openclaw.json"],
                "tool_boundaries": ["no process execution"],
                "acceptance_proof": ["Main-run unit test"],
                "allowed_merge_mode": "patch_proposal",
                "closeout_destination": "Veritas main",
            },
        }
        row = packets.selected_action_packet(handoff)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["agent_id"], "implementation-builder")
        self.assertEqual(row["parent_job_id"], "lane-7")
        self.assertEqual(row["owner_workflow"], "WF74")
        self.assertEqual(row["allowed_writes"], ["patches/validator.py"])
        self.assertEqual(row["tool_boundaries"], ["no process execution"])
        validation = packets.validate_payload(self.payload_for([row]))
        self.assertEqual(validation["status"], "ok")

    def test_selected_material_qa_infers_high_effort_when_route_is_not_supplied(self) -> None:
        handoff = {
            "selected_action": {"lane_id": "qa-9", "workflow_id": "WF85", "phase": "independent_qa"},
            "helper_lane_contract": {
                "primary_lane": "independent_qa",
                "staff_lane": "Independent QA Desk",
                "files_to_read_first": ["handoff/review.json"],
                "acceptance_proof": ["findings-first report"],
            },
        }
        row = packets.selected_action_packet(handoff)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["model_route"]["reasoning"], "high")
        self.assertEqual(row["effort_policy"]["default_reasoning"], "high")

    def test_effort_and_all_context_ceilings_are_enforced(self) -> None:
        qa = packets.standard_packets()[1]
        qa["model_route"] = copy.deepcopy(packets.DEFAULT_MODEL_ROUTE)
        qa["effort_policy"]["default_reasoning"] = "medium"
        validation = packets.validate_payload(self.payload_for([qa]))
        self.assertIn("independent-qa-helper:high_effort_required", validation["errors"])
        self.assertIn("independent-qa-helper:medium_effort_only_for_bounded_implementation", validation["errors"])

        implementation = packets.standard_packets()[0]
        implementation["scope_class"] = "cross_contract"
        validation = packets.validate_payload(self.payload_for([implementation]))
        self.assertIn("implementation-helper:high_effort_required", validation["errors"])

        implementation = packets.standard_packets()[0]
        implementation["context_budget"]["max_total_bytes"] = packets.DEFAULT_CONTEXT_BUDGET["max_total_bytes"] + 1
        implementation["context_budget"]["max_context_tokens"] = packets.DEFAULT_CONTEXT_BUDGET["max_context_tokens"] + 1
        validation = packets.validate_payload(self.payload_for([implementation]))
        self.assertIn("implementation-helper:context_byte_budget_above_hard_ceiling", validation["errors"])
        self.assertIn("implementation-helper:context_token_budget_above_hard_ceiling", validation["errors"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
