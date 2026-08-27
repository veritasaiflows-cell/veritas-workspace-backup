#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import finance_vector_retrieval_summary as summary


class FinanceVectorRetrievalSummaryTests(unittest.TestCase):
    def test_compact_summary_routes_without_raw_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tmp_dir = root / "tmp"
            tmp_dir.mkdir()
            wf84_path = tmp_dir / "canonical-finance-data-plane.json"
            wf85_path = tmp_dir / "trade-grade-decision-cards.json"
            out_path = tmp_dir / "finance-vector-retrieval-summary.json"
            wf84 = {
                "schema": "veritas.canonical_finance_data_plane.v1",
                "generated_at_utc": "2026-08-08T00:00:00Z",
                "status": "ok",
                "validation": {"status": "ok"},
                "tables": {
                    "security_master": [
                        {"ticker": "B", "name": "Beta", "instrument_type": "ETF", "sector": "Utilities"},
                        {"ticker": "A", "name": "Alpha", "instrument_type": "Operating Company", "sector": "Technology"},
                    ],
                    "routing_state_current": [
                        {"ticker": "A", "auto_tier": "Tier A", "auto_state": "A-WATCH", "route_priority": 1, "route_reason": "fresh"},
                        {"ticker": "B", "auto_tier": "Tier C", "auto_state": "C-CANDIDATE", "route_priority": 20, "route_reason": "monitor"},
                    ],
                    "decision_queue_state": [
                        {"ticker": "A", "primary_state": "review", "queue_state": "ready", "gate_verdict": "review_only", "rank_score": 9, "owner_action_required": True},
                        {"ticker": "B", "primary_state": "monitor", "queue_state": "queued", "gate_verdict": "wait", "rank_score": 3, "owner_action_required": False},
                    ],
                    "price_technical_current": [
                        {"ticker": "A", "latest_known_price": 100.0, "market_date": "2026-08-08", "quote_freshness_status": "fresh", "band_status": "IN_BAND", "technical_status": "ok", "technical_summary": "compact technical note", "raw_json": "must not copy"},
                        {"ticker": "B", "latest_known_price": 50.0, "market_date": "2026-08-08", "quote_freshness_status": "fresh", "band_status": "NO_CHASE", "technical_status": "ok", "raw_json": "must not copy"},
                    ],
                    "entry_stop_reference": [
                        {"ticker": "A", "entry_band_low": 95.0, "entry_band_high": 101.0, "stop_or_invalidation": 90.0, "freshness_status": "fresh", "validation_status": "ok", "source_artifact_path": "03. Portfolio/Execution Board.md", "source_artifact_hash": "abc", "raw_json": "must not copy"},
                        {"ticker": "B", "entry_band_low": 45.0, "entry_band_high": 51.0, "stop_or_invalidation": 42.0, "freshness_status": "fresh", "validation_status": "ok", "raw_json": "must not copy"},
                    ],
                    "fundamental_snapshot": [
                        {"ticker": "A", "data_quality": "ok", "key_metrics_status": "available", "latest_earnings_status": "available", "raw_json": "must not copy"},
                        {"ticker": "B", "data_quality": "ok", "key_metrics_status": "available", "latest_earnings_status": "available", "raw_json": "must not copy"},
                    ],
                    "earnings_catalyst": [
                        {"ticker": "A", "catalyst_status": "available", "latest_earnings_status": "available", "raw_json": "must not copy"},
                        {"ticker": "B", "catalyst_status": "available", "latest_earnings_status": "available", "raw_json": "must not copy"},
                    ],
                    "analyst_snapshot": [
                        {"ticker": "A", "status": "available", "consensus_rating": "Buy", "average_target": 120.0, "raw_json": "must not copy"},
                        {"ticker": "B", "status": "available", "consensus_rating": "Hold", "average_target": 52.0, "raw_json": "must not copy"},
                    ],
                    "evidence_family_status": [
                        {"ticker": "A", "family_id": "analyst_consensus", "status": "covered"},
                        {"ticker": "A", "family_id": "analyst_price_targets", "status": "covered_but_source_stale"},
                        {"ticker": "A", "family_id": "analyst_ratings", "status": "resolved_thin_monitor_current"},
                        {"ticker": "B", "family_id": "technical_posture", "status": "missing", "missing_count": 1, "stale_count": 0},
                    ],
                    "source_artifact": [
                        {"artifact_id": "src_a", "path": "data/a.json", "role": "test", "status": "ok", "sha256": "abc", "raw_summary_json": "must not copy"}
                    ],
                },
            }
            wf85 = {
                "schema": "veritas.trade_grade_decision_cards.v1",
                "generated_at_utc": "2026-08-08T00:00:01Z",
                "status": "ok",
                "validation": {"status": "ok"},
                "cards": [
                    {"ticker": "A", "decision_state": "review_ready", "auto_tier": "Tier A", "promotion_gate": {"verdict": "review", "vetoes": []}, "source_freshness": {"status": "fresh"}, "source_drillback": {"raw": "must not copy"}, "scenario_context": {"raw": "must not copy"}, "authority_boundary": {"trade_or_execution_approved": False}},
                    {"ticker": "B", "decision_state": "monitor_only", "auto_tier": "Tier C", "promotion_gate": {"verdict": "wait", "vetoes": ["not ready"]}, "source_freshness": {"status": "fresh"}, "source_drillback": {"raw": "must not copy"}, "scenario_context": {"raw": "must not copy"}, "authority_boundary": {"trade_or_execution_approved": False}},
                ],
            }
            wf84_path.write_text(json.dumps(wf84), encoding="utf-8")
            wf85_path.write_text(json.dumps(wf85), encoding="utf-8")

            payload = summary.build_summary(root=root, wf84_path=wf84_path, wf85_path=wf85_path, out_path=out_path)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["route_count"], 2)
            self.assertEqual([route["ticker"] for route in payload["ticker_routes"]], ["A", "B"])
            self.assertEqual(payload["ticker_routes"][0]["evidence_exceptions"], [])
            self.assertEqual(payload["ticker_routes"][1]["evidence_exceptions"][0]["family_id"], "technical_posture")
            self.assertEqual(payload["validation"]["status"], "ok")
            self.assertNotIn("raw_json", json.dumps(payload))
            self.assertNotIn("source_drillback", json.dumps(payload))
            self.assertNotIn("scenario_context", json.dumps(payload))
            self.assertEqual(summary.nested_forbidden_keys(payload), [])

            wf84_path.write_text(json.dumps({**wf84, "status": "changed"}), encoding="utf-8")
            validation = summary.validate_summary(payload, root=root)
            self.assertEqual(validation["status"], "error")
            self.assertTrue(any(error.startswith("source_packet_hash_drift") for error in validation["errors"]))


if __name__ == "__main__":
    unittest.main()
