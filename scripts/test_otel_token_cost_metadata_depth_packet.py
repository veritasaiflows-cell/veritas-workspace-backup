#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import otel_token_cost_metadata_depth_packet as packet_module


def span(name: str, start: datetime, attributes: dict[str, object]) -> dict[str, object]:
    def value(item: object) -> dict[str, object]:
        return {"intValue": str(item)} if isinstance(item, int) else {"stringValue": str(item)}

    return {
        "spanId": "abc",
        "name": name,
        "startTimeUnixNano": str(int(start.timestamp() * 1e9)),
        "attributes": [{"key": key, "value": value(item)} for key, item in attributes.items()],
    }


class CollectorEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    def write_traces(self, spans: list[dict[str, object]]) -> Path:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "traces.jsonl"
        path.write_text(
            "\n".join(json.dumps({"resourceSpans": [{"scopeSpans": [{"spans": [row]}]}]}) for row in spans),
            encoding="utf-8",
        )
        return path

    def test_token_attributes_are_detected_as_already_captured(self) -> None:
        recent = datetime(2026, 9, 12, 11, 0, 0, tzinfo=timezone.utc)
        path = self.write_traces([
            span("openclaw.model.call", recent, {
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 20,
                "openclaw.model_call.usage.total_tokens": 120,
            }),
        ])
        evidence = packet_module.collector_evidence(path, self.now)
        self.assertEqual(evidence["token_bearing_span_count"], 1)
        self.assertIn("gen_ai.usage.input_tokens", evidence["token_attributes_already_captured"])
        self.assertEqual(evidence["rolling_5h_model_call_spans_only"]["total_tokens"], 120)

    def test_model_usage_spans_excluded_from_the_non_double_counted_view(self) -> None:
        recent = datetime(2026, 9, 12, 11, 0, 0, tzinfo=timezone.utc)
        path = self.write_traces([
            span("openclaw.model.call", recent, {"openclaw.model_call.usage.total_tokens": 100}),
            span("openclaw.model.usage", recent, {"openclaw.tokens.total": 100}),
        ])
        evidence = packet_module.collector_evidence(path, self.now)
        self.assertEqual(evidence["rolling_5h_all_token_spans"]["total_tokens"], 200)
        self.assertEqual(evidence["rolling_5h_model_call_spans_only"]["total_tokens"], 100)

    def test_absent_join_keys_block_per_run_attribution(self) -> None:
        recent = datetime(2026, 9, 12, 11, 0, 0, tzinfo=timezone.utc)
        path = self.write_traces([
            span("openclaw.model.call", recent, {"openclaw.provider": "openai", "openclaw.tokens.total": 10}),
        ])
        evidence = packet_module.collector_evidence(path, self.now)
        self.assertEqual(evidence["lane_or_run_join_keys_found"], [])
        self.assertFalse(evidence["per_run_attribution_possible_from_otel"])

    def test_present_join_key_would_enable_per_run_attribution(self) -> None:
        recent = datetime(2026, 9, 12, 11, 0, 0, tzinfo=timezone.utc)
        path = self.write_traces([
            span("openclaw.model.call", recent, {"openclaw.session.id": "s1", "openclaw.tokens.total": 10}),
        ])
        evidence = packet_module.collector_evidence(path, self.now)
        self.assertTrue(evidence["per_run_attribution_possible_from_otel"])

    def test_stale_spans_fall_outside_the_rolling_window(self) -> None:
        old = datetime(2026, 9, 1, 11, 0, 0, tzinfo=timezone.utc)
        path = self.write_traces([span("openclaw.model.call", old, {"openclaw.tokens.total": 999})])
        evidence = packet_module.collector_evidence(path, self.now)
        self.assertEqual(evidence["rolling_5h_model_call_spans_only"]["span_count"], 0)
        self.assertEqual(evidence["rolling_7d_model_call_spans_only"]["span_count"], 0)


class PacketContractTests(unittest.TestCase):
    def test_packet_is_review_only_and_never_infers_approval(self) -> None:
        payload = packet_module.build_packet(packet_module.ROOT)
        boundary = payload["authority_boundary"]
        self.assertTrue(boundary["review_only"])
        self.assertFalse(boundary["collector_config_mutation_allowed"])
        self.assertFalse(boundary["runtime_config_mutation_allowed"])
        self.assertFalse(boundary["owner_approval_inferred"])
        self.assertEqual(payload["status"], "owner_decision_pending")
        self.assertEqual(payload["validation"]["errors"], [])

    def test_live_evidence_refutes_the_metadata_depth_premise(self) -> None:
        payload = packet_module.build_packet(packet_module.ROOT)
        self.assertFalse(payload["patch_would_change_token_or_cost_coverage"])
        self.assertEqual(
            payload["recommendation"]["recommended_owner_decision"],
            "decline_metadata_depth_patch_as_framed",
        )
        self.assertTrue(payload["proposed_patch_if_approved"]["rollback"]["reversible"])
        self.assertEqual(payload["proposed_patch_if_approved"]["expected_effect_on_token_coverage"], "none")

    def test_alternative_states_what_it_cannot_deliver(self) -> None:
        payload = packet_module.build_packet(packet_module.ROOT)
        alternative = payload["alternative_that_addresses_the_real_gap"]
        self.assertFalse(alternative["collector_config_change_required"])
        self.assertTrue(alternative["would_not_deliver"])
        self.assertFalse(payload["ledger_side_comparison"]["counting_basis_comparable_with_otel"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
