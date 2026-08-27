#!/usr/bin/env python3
"""Focused tests for the workspace-local turn circuit breaker."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import turn_circuit_breaker as breaker
except ModuleNotFoundError:
    from scripts import turn_circuit_breaker as breaker


class TurnCircuitBreakerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original_state_root = breaker.STATE_ROOT
        breaker.STATE_ROOT = Path(self.temp.name) / "turn-state"
        self.addCleanup(setattr, breaker, "STATE_ROOT", self.original_state_root)

    def start(self, job_id: str = "report-research") -> dict:
        state = breaker.new_state(
            job_id=job_id,
            turn_id="turn-1",
            owner_workflow="WF88",
            objective="Finish a long research report safely.",
            next_action="Continue with the next bounded research batch.",
        )
        return breaker.persist_state(state, "started")

    def test_policy_uses_requested_hard_limits(self) -> None:
        self.assertEqual(30, breaker.POLICY["hard_limits"]["tool_calls"])
        self.assertEqual(60_000, breaker.POLICY["hard_limits"]["context_tokens"])
        state = self.start()
        self.assertEqual({"tool_calls": 30, "context_tokens": 60_000}, state["limits"])
        self.assertTrue(state["tool_dispatch_allowed"])
        self.assertIn("--pretty resume", state["resume_command"])
        self.assertEqual("ok", breaker.validate_state(state)["status"])

    def test_warning_threshold_does_not_trip(self) -> None:
        state = breaker.update_progress(
            self.start(),
            turn_id="turn-1",
            tool_calls=24,
            context_tokens=48_000,
            last_successful_tool="memory_search",
        )
        self.assertEqual("running", state["status"])
        self.assertEqual("warning", state["guard"]["status"])
        self.assertTrue(state["tool_dispatch_allowed"])
        self.assertEqual("warning", breaker.validate_state(state)["status"])

    def test_thirtieth_tool_call_trips_and_atomically_checkpoints(self) -> None:
        state = breaker.update_progress(
            self.start(),
            turn_id="turn-1",
            tool_calls=30,
            context_tokens=32_000,
            completed_steps=["Evidence inventory complete."],
            last_successful_tool="read owner artifact",
            next_action="Start synthesis in a fresh turn.",
            validation_status="not_run",
        )
        self.assertEqual("checkpointed", state["status"])
        self.assertFalse(state["tool_dispatch_allowed"])
        self.assertTrue(state["resume_required"])
        self.assertEqual(["tool_calls_limit_reached"], state["checkpoint"]["reasons"])
        self.assertTrue(breaker.checkpoint_path("report-research").exists())
        self.assertEqual("veritas.turn_circuit_breaker_checkpoint.v1", state["checkpoint"]["payload"]["schema"])
        self.assertEqual("ok", breaker.validate_state(state)["status"])
        with self.assertRaisesRegex(breaker.GuardError, "dispatch is blocked"):
            breaker.preflight(state, turn_id="turn-1", tool_calls=30, context_tokens=32_000)

    def test_context_limit_trips_independently(self) -> None:
        state = breaker.update_progress(
            self.start("context-heavy"),
            turn_id="turn-1",
            tool_calls=8,
            context_tokens=60_000,
        )
        self.assertEqual(["context_tokens_limit_reached"], state["checkpoint"]["reasons"])
        self.assertEqual("checkpointed", state["status"])

    def test_resume_requires_a_fresh_turn_and_resets_per_turn_counters(self) -> None:
        tripped = breaker.update_progress(
            self.start(),
            turn_id="turn-1",
            tool_calls=30,
            context_tokens=10_000,
        )
        with self.assertRaisesRegex(breaker.GuardError, "different fresh turn_id"):
            breaker.resume_state(tripped, fresh_turn_id="turn-1")
        resumed = breaker.resume_state(tripped, fresh_turn_id="turn-2")
        self.assertEqual("running", resumed["status"])
        self.assertEqual(2, resumed["attempt_number"])
        self.assertEqual("turn-2", resumed["turn_id"])
        self.assertEqual({"tool_calls": 0, "context_tokens": 0}, resumed["observed"])
        self.assertEqual(1, len(resumed["attempt_history"]))
        self.assertIsNotNone(resumed["resumed_from_checkpoint"])
        self.assertTrue(resumed["tool_dispatch_allowed"])
        self.assertEqual("ok", breaker.validate_state(resumed)["status"])

    def test_embedded_checkpoint_remains_resumable_if_mirror_is_missing(self) -> None:
        tripped = breaker.update_progress(
            self.start("power-loss"),
            turn_id="turn-1",
            tool_calls=30,
            context_tokens=10_000,
        )
        breaker.checkpoint_path("power-loss").unlink()
        self.assertEqual("warning", breaker.validate_state(tripped)["status"])
        resumed = breaker.resume_state(tripped, fresh_turn_id="turn-2")
        self.assertEqual("running", resumed["status"])

    def test_stale_prior_mirror_cannot_block_later_embedded_checkpoint_resume(self) -> None:
        first = breaker.update_progress(
            self.start("repeat-crash"),
            turn_id="turn-1",
            tool_calls=30,
            context_tokens=10_000,
        )
        mirror_a = breaker.load_json(breaker.checkpoint_path("repeat-crash"))
        second_attempt = breaker.resume_state(first, fresh_turn_id="turn-2")
        second = breaker.update_progress(
            second_attempt,
            turn_id="turn-2",
            tool_calls=30,
            context_tokens=11_000,
        )
        breaker.atomic_write_json(breaker.checkpoint_path("repeat-crash"), mirror_a)
        validation = breaker.validate_state(second)
        self.assertEqual("warning", validation["status"])
        self.assertIn("checkpoint_mirror_stale_or_mismatched_embedded_checkpoint_authoritative", validation["warnings"])
        third_attempt = breaker.resume_state(second, fresh_turn_id="turn-3")
        self.assertEqual("running", third_attempt["status"])
        repaired_mirror = breaker.load_json(breaker.checkpoint_path("repeat-crash"))
        self.assertEqual(third_attempt["resumed_from_checkpoint"]["checkpoint_id"], repaired_mirror["checkpoint_id"])

    def test_observations_are_absolute_and_monotonic(self) -> None:
        state = breaker.update_progress(
            self.start(),
            turn_id="turn-1",
            tool_calls=5,
            context_tokens=12_000,
        )
        with self.assertRaisesRegex(breaker.GuardError, "tool_calls cannot decrease"):
            breaker.update_progress(state, turn_id="turn-1", tool_calls=4, context_tokens=12_000)
        with self.assertRaisesRegex(breaker.GuardError, "context_tokens cannot decrease"):
            breaker.update_progress(state, turn_id="turn-1", tool_calls=5, context_tokens=11_999)

    def test_stale_writer_cannot_reenable_dispatch(self) -> None:
        self.start("stale-writer")
        writer_one = breaker.load_state("stale-writer")
        writer_two = breaker.load_state("stale-writer")
        tripped = breaker.update_progress(
            writer_one,
            turn_id="turn-1",
            tool_calls=30,
            context_tokens=10_000,
        )
        self.assertEqual("checkpointed", tripped["status"])
        with self.assertRaisesRegex(breaker.GuardError, "stale state transition"):
            breaker.update_progress(
                writer_two,
                turn_id="turn-1",
                tool_calls=29,
                context_tokens=9_000,
            )
        persisted = breaker.load_state("stale-writer")
        self.assertEqual("checkpointed", persisted["status"])
        self.assertFalse(persisted["tool_dispatch_allowed"])

    def test_controlling_state_tampering_is_detected(self) -> None:
        self.start("tamper")
        path = breaker.state_path("tamper")
        tampered = breaker.load_json(path)
        tampered["tool_dispatch_allowed"] = False
        breaker.atomic_write_json(path, tampered)
        with self.assertRaisesRegex(breaker.GuardError, "state integrity failed"):
            breaker.load_state("tamper")

    def test_summary_fields_reject_multiline_payload_like_text(self) -> None:
        with self.assertRaisesRegex(breaker.GuardError, "one-line operator summary"):
            breaker.new_state(
                job_id="raw-text",
                turn_id="turn-1",
                owner_workflow="WF88",
                objective="line one\nline two",
                next_action="Continue safely.",
            )

    def test_manual_checkpoint_also_requires_resume(self) -> None:
        state = self.start("manual")
        checkpointed = breaker.checkpoint_state(state, ["manual_checkpoint"], event="manual_checkpointed")
        self.assertEqual("checkpointed", checkpointed["status"])
        self.assertEqual("checkpointed", checkpointed["guard"]["status"])
        self.assertEqual("ok", breaker.validate_state(checkpointed)["status"])

    def test_limits_can_narrow_but_cannot_widen(self) -> None:
        narrowed = breaker.limits_for(max_tool_calls=20, max_context_tokens=40_000)
        self.assertEqual({"tool_calls": 20, "context_tokens": 40_000}, narrowed)
        with self.assertRaisesRegex(breaker.GuardError, "max_tool_calls"):
            breaker.limits_for(max_tool_calls=31, max_context_tokens=60_000)
        with self.assertRaisesRegex(breaker.GuardError, "max_context_tokens"):
            breaker.limits_for(max_tool_calls=30, max_context_tokens=60_001)

    def test_completion_requires_clean_validation_and_active_turn(self) -> None:
        state = self.start("complete")
        with self.assertRaisesRegex(breaker.GuardError, "validation_status"):
            breaker.complete_state(state, turn_id="turn-1", validation_status="not_run")
        complete = breaker.complete_state(state, turn_id="turn-1", validation_status="ok")
        self.assertEqual("complete", complete["status"])
        self.assertFalse(complete["tool_dispatch_allowed"])
        self.assertEqual("ok", breaker.validate_state(complete)["status"])


if __name__ == "__main__":
    unittest.main()
