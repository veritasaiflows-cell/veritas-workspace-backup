from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agent_message_ledger_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("agent_message_ledger_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentMessageLedgerPacketTests(unittest.TestCase):
    def test_agent_message_ledger_is_metadata_only_and_idempotent(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            register = root / "concurrent-lane-register.json"
            ledger = root / "agent-message-ledger.jsonl"
            register.write_text(
                json.dumps(
                    {
                        "generated_at_utc": "2026-07-05T00:00:00Z",
                        "validation": {"status": "ok"},
                        "lanes": [
                            {
                                "lane_id": "RUNTIME::test",
                                "workflow_id": "RUNTIME",
                                "workstream_id": "test",
                                "owner": "main",
                                "status": "complete",
                                "created_at_utc": "2026-07-05T00:00:00Z",
                                "updated_at_utc": "2026-07-05T00:01:00Z",
                                "completed_at_utc": "2026-07-05T00:01:00Z",
                                "runtime": {
                                    "model_path": "openai/gpt-5.5",
                                    "token_closeout_status": "provider_usage_unavailable",
                                    "session_key": "agent:private:session-key",
                                    "session_id": "private-session-id",
                                    "parent_job_id": "job-1",
                                    "phase": "implementation",
                                    "retry_count": 0,
                                    "attempt_number": 1,
                                    "is_first_attempt": True,
                                    "attempt_id": "attempt-private-1",
                                    "outcome_event_kind": "terminal_closeout",
                                    "outcome_event_sequence": 1,
                                    "outcome_recorded_at_utc": "2026-07-05T00:01:00Z",
                                    "outcome_status": "passed",
                                    "main_acceptance_status": "accepted",
                                    "main_acceptance_evidence": "private acceptance narrative",
                                },
                                "allowed_writes": ["tmp/test.json"],
                                "acceptance_commands": ["python scripts/test.py"],
                                "proof_artifacts": ["tmp/test.json"],
                                "notes": ["raw prompt: private content must never escape"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            first = module.build_packet(register, ledger, append_ledger=True)
            second = module.build_packet(register, ledger, append_ledger=True)

            self.assertEqual(first["summary"]["event_count"], 1)
            self.assertEqual(first["summary"]["new_event_count"], 1)
            self.assertEqual(second["summary"]["new_event_count"], 0)
            self.assertEqual(len(ledger.read_text(encoding="utf-8").splitlines()), 1)
            self.assertFalse(first["authority_boundary"]["raw_prompt_capture_allowed"])
            self.assertFalse(first["authority_boundary"]["executes_work"])
            event = first["recent_events"][0]
            self.assertTrue(str(event["outcome_event_id"]).startswith("sha256:"))
            self.assertTrue(str(event["session_ref_hash"]).startswith("sha256:"))
            self.assertEqual(event["attempt_number"], 1)
            self.assertTrue(event["is_first_attempt"])
            serialized = json.dumps(first)
            for forbidden in (
                "agent:private:session-key",
                "private-session-id",
                "attempt-private-1",
                "private acceptance narrative",
                "raw prompt: private content must never escape",
            ):
                self.assertNotIn(forbidden, serialized)
            for forbidden_key in ("session_key", "session_id", "notes", "acceptance_commands"):
                self.assertNotIn(forbidden_key, event)

            mutated = json.loads(register.read_text(encoding="utf-8"))
            mutated["lanes"][0]["proof_artifacts"] = ["tmp/changed-proof.json"]
            register.write_text(json.dumps(mutated), encoding="utf-8")
            conflict = module.build_packet(register, ledger, append_ledger=True)
            self.assertEqual(conflict["validation"]["status"], "error")
            self.assertEqual(conflict["summary"]["identity_conflict_count"], 1)
            self.assertEqual(len(ledger.read_text(encoding="utf-8").splitlines()), 1)

            retry = json.loads(register.read_text(encoding="utf-8"))
            retry_runtime = retry["lanes"][0]["runtime"]
            retry_runtime.update({
                "retry_count": 1,
                "attempt_number": 2,
                "is_first_attempt": False,
                "attempt_id": "attempt-private-2",
                "outcome_event_sequence": 2,
                "outcome_recorded_at_utc": "2026-07-05T00:02:00Z",
            })
            retry["lanes"][0]["completed_at_utc"] = "2026-07-05T00:02:00Z"
            register.write_text(json.dumps(retry), encoding="utf-8")
            retry_packet = module.build_packet(register, ledger, append_ledger=True)
            self.assertEqual(retry_packet["validation"]["status"], "ok")
            self.assertEqual(retry_packet["summary"]["new_event_count"], 1)
            self.assertEqual(len(ledger.read_text(encoding="utf-8").splitlines()), 2)

    def test_prefilled_runtime_reference_hashes_cannot_escape_raw_text(self) -> None:
        module = load_module()
        raw_reference = "raw-prefilled-session-reference:must-not-escape"
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "agent-message-ledger.jsonl"
            for field_name in ("session_ref_hash", "session_id_hash", "session_key_hash"):
                with self.subTest(field_name=field_name):
                    event = module.event_for_lane(
                        {
                            "lane_id": f"RUNTIME::{field_name}",
                            "workflow_id": "RUNTIME",
                            "workstream_id": field_name,
                            "owner": "main",
                            "status": "complete",
                            "completed_at_utc": "2026-07-05T00:01:00Z",
                            "runtime": {
                                field_name: raw_reference,
                                "attempt_number": 1,
                                "retry_count": 0,
                                "outcome_event_kind": "terminal_closeout",
                                "outcome_event_sequence": 1,
                            },
                        }
                    )
                    self.assertIsNotNone(event)
                    self.assertEqual(event["session_ref_hash"], module.hash_reference(raw_reference))
                    self.assertNotIn(raw_reference, json.dumps(event))
                    result = module.write_ledger(ledger, [event], write=True)
                    self.assertFalse(result["conflicts"])
                    self.assertNotIn(raw_reference, ledger.read_text(encoding="utf-8"))

        for supplied, expected in (
            ("ABCDEF0123456789ABCDEF01", "abcdef0123456789abcdef01"),
            ("A" * 64, "a" * 64),
            ("SHA256:" + ("B" * 64), "sha256:" + ("b" * 64)),
        ):
            with self.subTest(supplied=supplied):
                self.assertEqual(module.normalize_reference_hash(supplied), expected)

    def test_post_cutover_self_declared_usage_is_an_incident_without_a_source_receipt(self) -> None:
        module = load_module()
        lane = {
            "lane_id": "RUNTIME::forged-usage",
            "workflow_id": "RUNTIME",
            "workstream_id": "forged-usage",
            "status": "complete",
            "created_at_utc": "2026-08-13T21:00:00Z",
            "completed_at_utc": "2026-08-13T21:01:00Z",
            "runtime": {
                "model_path": "openai/gpt-5.6-terra",
                "parent_job_id": "job-1",
                "phase": "implementation",
                "run_id": "run-1",
                "session_ref_hash": "session-ref-1",
                "source_snapshot_fingerprint": "snapshot-1",
                "attempt_correlation": {"key_hash": "attempt-1"},
                "token_attribution_source": "codex_native_rollout_jsonl",
                "input_token_semantics": "exclusive_cached",
                "input_tokens": 10,
                "cached_input_tokens": 20,
                "cache_write_tokens": 0,
                "output_tokens": 5,
                "total_tokens": 35,
                "source_input_total_tokens": 30,
                "source_total_tokens_fresh": True,
                "usage_creditable": True,
                "usage_credit_status": "creditable",
                "usage_source_receipt_id": "forged",
            },
        }
        event = module.event_for_lane(lane, [])
        self.assertIsNotNone(event)
        self.assertEqual(event["outcome_event_kind"], "incident")
        self.assertEqual(event["incident_code"], "telemetry_attribution_unavailable")
        self.assertFalse(event["usage_source_receipt_verified"])
        self.assertFalse(event["usage_creditable"])
        self.assertEqual(event["usage_credit_status"], "blocked")
        self.assertTrue(event["runtime_usage_creditable_claim"])
        self.assertEqual(event["runtime_usage_credit_status_claim"], "creditable")

    def test_default_raw_usage_claims_do_not_rewrite_a_legacy_v2_event(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            register = root / "concurrent-lane-register.json"
            ledger = root / "agent-message-ledger.jsonl"
            lane = {
                "lane_id": "RUNTIME::legacy-default-claims",
                "workflow_id": "RUNTIME",
                "workstream_id": "legacy-default-claims",
                "owner": "main",
                "status": "complete",
                "created_at_utc": "2026-07-05T00:00:00Z",
                "completed_at_utc": "2026-07-05T00:01:00Z",
                "runtime": {
                    "session_ref_hash": "B" * 64,
                    "attempt_number": 1,
                    "retry_count": 0,
                    "outcome_event_kind": "terminal_closeout",
                    "outcome_event_sequence": 1,
                },
            }
            register.write_text(
                json.dumps({"validation": {"status": "ok"}, "lanes": [lane]}),
                encoding="utf-8",
            )
            legacy_event = module.event_for_lane(lane)
            self.assertIsNotNone(legacy_event)
            self.assertNotIn("runtime_usage_creditable_claim", legacy_event)
            self.assertNotIn("runtime_usage_credit_status_claim", legacy_event)
            ledger.write_text(
                json.dumps(legacy_event, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            packet = module.build_packet(register, ledger, append_ledger=True)

            self.assertEqual(packet["validation"]["status"], "ok")
            self.assertEqual(packet["summary"]["identity_conflict_count"], 0)
            self.assertEqual(packet["summary"]["new_event_count"], 0)

    def test_parent_job_metadata_supplement_is_warning_not_identity_conflict(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            register = root / "concurrent-lane-register.json"
            ledger = root / "agent-message-ledger.jsonl"
            lane = {
                "lane_id": "RUNTIME::metadata-supplement",
                "workflow_id": "RUNTIME",
                "workstream_id": "metadata-supplement",
                "owner": "main",
                "status": "blocked",
                "created_at_utc": "2026-08-13T21:00:00Z",
                "ended_at_utc": "2026-08-13T21:01:00Z",
                "runtime": {
                    "session_ref_hash": "C" * 64,
                    "attempt_number": 1,
                    "retry_count": 0,
                    "outcome_event_kind": "incident",
                    "outcome_event_sequence": 1,
                    "outcome_recorded_at_utc": "2026-08-13T21:01:00Z",
                    "incident_code": "elapsed_budget_exceeded",
                },
            }
            register.write_text(
                json.dumps({"validation": {"status": "ok"}, "lanes": [lane]}),
                encoding="utf-8",
            )
            first = module.build_packet(register, ledger, append_ledger=True)
            self.assertEqual(first["validation"]["status"], "ok")
            self.assertEqual(first["summary"]["new_event_count"], 1)
            ledger_before = ledger.read_bytes()

            supplemented = json.loads(register.read_text(encoding="utf-8"))
            supplemented["lanes"][0]["runtime"]["parent_job_id"] = "parent-job-after-closeout"
            register.write_text(json.dumps(supplemented), encoding="utf-8")
            packet = module.build_packet(register, ledger, append_ledger=True)

            self.assertEqual(packet["validation"]["status"], "warning")
            self.assertFalse(packet["validation"]["errors"])
            self.assertEqual(packet["summary"]["identity_conflict_count"], 0)
            self.assertEqual(packet["summary"]["metadata_supplement_conflict_count"], 1)
            self.assertEqual(packet["summary"]["new_event_count"], 0)
            self.assertFalse(packet["source_artifacts"]["agent_message_ledger"]["write_blocked"])
            self.assertEqual(ledger.read_bytes(), ledger_before)

    def test_tampered_existing_event_fingerprint_fails_closed_without_rewrite(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            register = root / "concurrent-lane-register.json"
            ledger = root / "agent-message-ledger.jsonl"
            lane = {
                "lane_id": "RUNTIME::tamper-test",
                "workflow_id": "RUNTIME",
                "workstream_id": "tamper-test",
                "owner": "main",
                "status": "complete",
                "created_at_utc": "2026-07-05T00:00:00Z",
                "completed_at_utc": "2026-07-05T00:01:00Z",
                "runtime": {
                    "session_ref_hash": "A" * 64,
                    "attempt_number": 1,
                    "retry_count": 0,
                    "outcome_event_kind": "terminal_closeout",
                    "outcome_event_sequence": 1,
                },
            }
            register.write_text(
                json.dumps({"validation": {"status": "ok"}, "lanes": [lane]}),
                encoding="utf-8",
            )
            original_event = module.event_for_lane(lane)
            self.assertIsNotNone(original_event)
            tampered_event = dict(original_event)
            tampered_event["status"] = "blocked"
            self.assertEqual(tampered_event["outcome_event_id"], original_event["outcome_event_id"])
            self.assertEqual(tampered_event["event_fingerprint"], original_event["event_fingerprint"])
            ledger.write_text(
                json.dumps(tampered_event, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            ledger_before = ledger.read_bytes()

            packet = module.build_packet(register, ledger, append_ledger=True)

            self.assertEqual(packet["validation"]["status"], "error")
            self.assertEqual(packet["summary"]["integrity_conflict_count"], 1)
            self.assertEqual(packet["summary"]["new_event_count"], 0)
            self.assertTrue(packet["source_artifacts"]["agent_message_ledger"]["write_blocked"])
            self.assertIn(
                f"existing_ledger_integrity_conflict:{original_event['outcome_event_id']}",
                packet["validation"]["errors"],
            )
            self.assertEqual(ledger.read_bytes(), ledger_before)


if __name__ == "__main__":
    unittest.main()
