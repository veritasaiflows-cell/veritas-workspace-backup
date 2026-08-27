#!/usr/bin/env python3
"""Regression tests for the deterministic WF88 decision compiler."""
from __future__ import annotations

import copy
import unittest
from datetime import timedelta

import wf88_decision_compiler as compiler


class Wf88DecisionCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payloads, errors = compiler.load_sources()
        cls.payloads = payloads
        cls.errors = errors
        generated = [
            compiler.parse_utc(payload.get("generated_at_utc"))
            for payload in payloads.values()
            if isinstance(payload, dict)
        ]
        generated = [value for value in generated if value is not None]
        cls.fixed_now = max(generated) + timedelta(minutes=1)
        cls.packet = compiler.build_packet(
            source_payloads=copy.deepcopy(payloads),
            source_load_errors=errors,
            now=cls.fixed_now,
        )

    def test_runtime_contract_is_one_way_and_cycle_free(self) -> None:
        input_paths = {row["path"] for row in self.packet["inputs"].values()}
        self.assertFalse(input_paths & compiler.FORBIDDEN_RUNTIME_INPUTS)
        self.assertEqual(
            self.packet["runtime_dependency_contract"]["direction"],
            "upstream_action_surfaces_to_decision_compiler_to_wiki",
        )
        self.assertFalse(self.packet["runtime_dependency_contract"]["model_or_api_call"])
        self.assertEqual(self.packet["leak_guard"]["runtime_cycle_input_count"], 0)

    def test_live_sources_compile_all_deduplicated_action_rows(self) -> None:
        queue_count = len(self.payloads["actionable_improvement_queue"]["action_items"])
        self.assertEqual(self.packet["summary"]["decision_object_count"], queue_count)
        self.assertEqual(len(self.packet["decisions"]), queue_count)
        self.assertGreater(queue_count, 0)
        self.assertEqual(self.packet["validation"]["errors"], [])
        self.assertNotEqual(self.packet["validation"]["status"], "blocked")
        self.assertTrue(self.packet["leak_guard"]["pass"])

    def test_decision_objects_have_strict_required_shape(self) -> None:
        nested_keys = {
            "source_selection": {
                "stable_key",
                "primary_source_pointer",
                "candidate_source_pointers",
                "field_precedence",
                "selection_reason",
                "generated_review_only",
                "source_open_required_for_material_claim",
            },
            "freshness": {
                "status",
                "generated_at_utc",
                "age_hours",
                "max_age_hours",
                "expires_at_utc",
                "source_statuses",
                "expiry_behavior",
            },
            "conflict_uncertainty": {
                "conflict",
                "recommendation_conflict",
                "state_conflict",
                "uncertainties",
                "conflicting_source_pointers",
                "resolution_rule",
            },
            "expiry_reopen": {
                "expires_at_utc",
                "review_by_utc",
                "reopen_trigger",
                "expiry_behavior",
            },
            "later_outcome_pointer": {
                "path",
                "json_pointer",
                "exact_pointer",
                "match_key",
                "status",
                "outcome_state",
                "current_tracking_pointer",
                "closed_outcome_pointer",
                "future_collection_pointer",
            },
        }
        ids: set[str] = set()
        for decision in self.packet["decisions"]:
            with self.subTest(decision_id=decision["decision_id"]):
                self.assertTrue(compiler.REQUIRED_DECISION_FIELDS <= set(decision))
                self.assertEqual(
                    compiler.strict_schema_instance_errors(decision, compiler.DECISION_OBJECT_SCHEMA),
                    [],
                )
                self.assertRegex(decision["decision_id"], r"^wf88dec-[a-f0-9]{16}$")
                self.assertNotIn(decision["decision_id"], ids)
                ids.add(decision["decision_id"])
                self.assertGreaterEqual(len(decision["alternatives"]), 2)
                self.assertTrue(decision["authority_class"].startswith("review_only"))
                self.assertGreaterEqual(len(decision["stop_lines"]), len(compiler.GLOBAL_STOP_LINES))
                for field, expected_keys in nested_keys.items():
                    self.assertEqual(set(decision[field]), expected_keys)
                primary = decision["source_pointers"][0]
                self.assertTrue(primary["selected"])
                self.assertTrue(primary["json_pointer"].startswith("/action_items/"))
                self.assertEqual(
                    compiler.stable_decision_id(decision["source_selection"]["stable_key"]),
                    decision["decision_id"],
                )

    def test_sparse_routes_and_command_use_nonempty_review_only_sentinels(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        payloads["actionable_improvement_queue"]["action_items"] = [
            {
                "item_id": "sparse-route-regression",
                "source_key": "sparse-route-regression",
                "title": "Sparse route regression fixture",
                "action_state": "monitor_only",
                "next_action": "Keep this sparse row fail-closed and review-only.",
                "destination": "   ",
                "destination_id": "\t",
                "proof_command": " \t ",
                "secondary_routes": [{}, {"destination_id": " ", "title": "\t", "action_state": "  "}],
            }
        ]
        packet = compiler.build_packet(
            source_payloads=payloads,
            source_load_errors=self.errors,
            now=self.fixed_now,
        )
        decision = packet["decisions"][0]
        owner_route = decision["owner_route"]
        self.assertEqual(owner_route["route"], compiler.MISSING_ROUTE_SENTINEL)
        self.assertEqual(owner_route["route_id"], compiler.MISSING_ROUTE_ID_SENTINEL)
        self.assertEqual(decision["next_command"]["command"], compiler.MISSING_COMMAND_SENTINEL)
        self.assertTrue(all(isinstance(value, str) and value for value in owner_route.values() if isinstance(value, str)))
        for secondary in owner_route["secondary_routes"]:
            self.assertTrue(all(isinstance(value, str) and value for value in secondary.values()))
        self.assertEqual(
            compiler.strict_schema_instance_errors(decision, compiler.DECISION_OBJECT_SCHEMA),
            [],
        )
        self.assertFalse(
            any(error.startswith("decision_schema_violation:") for error in packet["validation"]["errors"])
        )

    def test_recursive_strict_schema_blocks_nested_type_tampering(self) -> None:
        mutations = [
            (
                "route_null",
                lambda decision: decision["owner_route"].__setitem__("route", None),
                "$.owner_route.route",
            ),
            (
                "route_whitespace",
                lambda decision: decision["owner_route"].__setitem__("route", " \t "),
                "$.owner_route.route",
            ),
            (
                "route_id_null",
                lambda decision: decision["owner_route"].__setitem__("route_id", None),
                "$.owner_route.route_id",
            ),
            (
                "route_id_whitespace",
                lambda decision: decision["owner_route"].__setitem__("route_id", "\r\n"),
                "$.owner_route.route_id",
            ),
            (
                "secondary_title_number",
                lambda decision: decision["owner_route"].__setitem__(
                    "secondary_routes",
                    [{"route_id": "review-route", "state": "review_only", "title": 7}],
                ),
                "$.owner_route.secondary_routes[0].title",
            ),
            (
                "command_null",
                lambda decision: decision["next_command"].__setitem__("command", None),
                "$.next_command.command",
            ),
            (
                "command_whitespace",
                lambda decision: decision["next_command"].__setitem__("command", "   "),
                "$.next_command.command",
            ),
            (
                "nested_additional_property",
                lambda decision: decision["owner_route"].__setitem__("uncontracted_hint", "not allowed"),
                "$.owner_route.uncontracted_hint",
            ),
        ]
        for label, mutate, expected_path in mutations:
            with self.subTest(label=label):
                tampered = copy.deepcopy(self.packet)
                decision = tampered["decisions"][0]
                mutate(decision)
                validation = compiler.validate_packet(tampered)
                self.assertEqual(validation["status"], "blocked")
                schema_errors = [
                    error for error in validation["errors"] if error.startswith("decision_schema_violation:")
                ]
                self.assertTrue(schema_errors)
                self.assertTrue(any(expected_path in error for error in schema_errors))
                if "whitespace" in label:
                    self.assertTrue(any("strict_schema_blank_string:" in error for error in schema_errors))

    def test_same_sources_and_clock_produce_identical_decisions(self) -> None:
        second = compiler.build_packet(
            source_payloads=copy.deepcopy(self.payloads),
            source_load_errors=self.errors,
            now=self.fixed_now,
        )
        self.assertEqual(self.packet["decisions"], second["decisions"])
        self.assertEqual(self.packet["summary"], second["summary"])

    def test_stale_primary_source_blocks_every_current_action(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        stale_at = self.fixed_now - timedelta(hours=48)
        payloads["actionable_improvement_queue"]["generated_at_utc"] = compiler.utc_text(stale_at)
        packet = compiler.build_packet(
            source_payloads=payloads,
            source_load_errors=self.errors,
            now=self.fixed_now,
        )
        self.assertEqual(packet["summary"]["blocked_count"], len(packet["decisions"]))
        self.assertTrue(all(row["state"] == "blocked_source_not_current" for row in packet["decisions"]))
        self.assertIn(
            "required_source_not_current:actionable_improvement_queue:stale",
            packet["validation"]["warnings"],
        )

    def test_route_contradiction_is_preserved_not_silently_overwritten(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        first_item = payloads["actionable_improvement_queue"]["action_items"][0]
        destination_id = first_item["destination_id"]
        docket_row = next(
            row
            for row in payloads["wf74_decision_docket"]["rows"]
            if row.get("docket_id") == destination_id
        )
        docket_row["next_action"] = "Contradictory route-context recommendation for regression proof."
        packet = compiler.build_packet(
            source_payloads=payloads,
            source_load_errors=self.errors,
            now=self.fixed_now,
        )
        decision = packet["decisions"][0]
        self.assertTrue(decision["conflict_uncertainty"]["conflict"])
        self.assertTrue(decision["conflict_uncertainty"]["recommendation_conflict"])
        self.assertEqual(decision["recommendation"], first_item["next_action"])
        self.assertGreater(len(decision["conflict_uncertainty"]["conflicting_source_pointers"]), 0)
        self.assertIn(f"decision_conflict:{decision['decision_id']}", packet["validation"]["warnings"])

    def test_missing_required_action_surface_fails_closed(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        payloads["actionable_improvement_queue"] = None
        errors = dict(self.errors)
        errors["actionable_improvement_queue"] = "missing_source"
        packet = compiler.build_packet(
            source_payloads=payloads,
            source_load_errors=errors,
            now=self.fixed_now,
        )
        self.assertEqual(packet["decisions"], [])
        self.assertEqual(packet["status"], "decision_compiler_blocked_fail_closed")
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertIn(
            "missing_required_source:actionable_improvement_queue:tmp/actionable-improvement-queue.json",
            packet["validation"]["errors"],
        )

    def test_authority_and_command_leaks_are_blocking(self) -> None:
        widened = copy.deepcopy(self.packet)
        widened["decisions"][0]["authority_class"] = "approved_execute"
        validation = compiler.validate_packet(widened)
        self.assertEqual(validation["status"], "blocked")
        self.assertTrue(any(value.startswith("authority_class_not_review_only:") for value in validation["errors"]))

        command_leak = copy.deepcopy(self.packet)
        command_leak["decisions"][0]["next_command"]["command"] = "python dangerous.py --apply"
        validation = compiler.validate_packet(command_leak)
        self.assertEqual(validation["status"], "blocked")
        self.assertTrue(any(value.startswith("forbidden_next_command:") for value in validation["errors"]))

    def test_later_outcome_pointer_distinguishes_reopen_from_closure(self) -> None:
        statuses = {
            row["later_outcome_pointer"]["status"]
            for row in self.packet["decisions"]
        }
        self.assertTrue(
            statuses
            <= {
                "linked_closed_outcome",
                "tracking_open_no_later_outcome",
                "reopened_after_prior_close",
                "linked_recommendation_outcome",
                "pending_future_match",
            }
        )
        for decision in self.packet["decisions"]:
            pointer = decision["later_outcome_pointer"]
            self.assertTrue(pointer["json_pointer"].startswith("/"))
            self.assertIn("#", pointer["exact_pointer"])
            if pointer["status"] == "reopened_after_prior_close":
                self.assertIsNotNone(pointer["current_tracking_pointer"])
                self.assertIsNotNone(pointer["closed_outcome_pointer"])

    def test_markdown_renders_decision_and_dependency_contract(self) -> None:
        markdown = compiler.render_markdown(self.packet)
        self.assertIn("# WF88 Decision Compiler", markdown)
        self.assertIn(self.packet["decisions"][0]["decision_id"], markdown)
        self.assertIn("does not read the WF88 wiki synthesis", markdown)


if __name__ == "__main__":
    unittest.main()
