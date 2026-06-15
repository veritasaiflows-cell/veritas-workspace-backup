#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import finance_recommendation_history_ledger as ledger


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class FinanceRecommendationHistoryLedgerTests(unittest.TestCase):
    def test_builds_normalized_history_rows_from_synthetic_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self._write_clean_sources(root)
            payload = ledger.build_ledger(paths, now="2026-06-13T00:00:00Z")

        self.assertEqual(payload["validation"]["status"], "ok")
        self.assertEqual(payload["summary"]["row_count"], 5)
        self.assertEqual(payload["summary"]["ticker_count"], 5)
        self.assertEqual(payload["authority_flags"]["capital_deployment_approved"], False)
        self.assertEqual(payload["authority_flags"]["owner_approval_inferred"], False)
        self.assertEqual(
            payload["summary"]["source_family_counts"],
            {
                "WF55_RECOMMENDATION_TRACKING": 1,
                "WF74_RECOMMENDATION_CORRECTNESS": 1,
                "WF78_DEPLOYMENT_READINESS_REVIEW": 1,
                "WF85_FINANCE_DECISION_FACTORY": 1,
                "WF85_TRADE_GRADE_DECISION_CARD": 1,
            },
        )

        vrt = next(row for row in payload["rows"] if row["ticker"] == "VRT" and row["source_family"] == "WF55_RECOMMENDATION_TRACKING")
        self.assertEqual(vrt["market_context"]["price"], 101.0)
        self.assertEqual(vrt["market_context"]["band_status"], "IN_BAND")
        self.assertEqual(vrt["feature_fields"]["checkpoint_status_counts"], {"pending_window": 1})
        self.assertTrue(vrt["row_id"].startswith("finhist_"))

        nvda = next(row for row in payload["rows"] if row["ticker"] == "NVDA")
        self.assertEqual(nvda["source_family"], "WF85_TRADE_GRADE_DECISION_CARD")
        self.assertEqual(nvda["feature_fields"]["decision_state"], "review_ready")
        self.assertFalse(nvda["authority_flags"]["paper_or_live_execution_allowed"])

    def test_authority_drift_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self._write_clean_sources(root)
            wf78 = json.loads(paths["wf78_human_review"].read_text(encoding="utf-8"))
            wf78["rows"][0]["capital_deployment_approved"] = True
            write_json(paths["wf78_human_review"], wf78)

            payload = ledger.build_ledger(paths, now="2026-06-13T00:00:00Z")

        self.assertEqual(payload["validation"]["status"], "critical")
        self.assertEqual(payload["status"], "blocked")
        issues = {finding["issue"] for finding in payload["validation"]["findings"]}
        self.assertIn("row_authority_drift", issues)

    def _write_clean_sources(self, root: Path) -> dict[str, Path]:
        wf55 = write_json(root / "wf55.json", {
            "schema_version": "wf55.recommendation_outcome_ledger_current.2",
            "generated_at_utc": "2026-06-12T20:00:00Z",
            "tracked_rows": [
                {
                    "ledger_event_id": "ledger_vrt",
                    "event_family": "recommendation_tracking",
                    "event_subtype": "owner_decision_pending",
                    "observed_at_utc": "2026-06-12T20:01:00Z",
                    "ticker": "VRT",
                    "payload": {
                        "recommendation_id": "rec-vrt",
                        "recommendation_source": "tmp/source-vrt.json",
                        "recommendation_type": "capital_review",
                        "current_status": "PROMOTION REVIEW",
                        "decision_status": "pending_owner_review",
                        "current_price": 101.0,
                        "entry_band_low": 95.0,
                        "entry_band_high": 105.0,
                        "stop_or_invalidation": 90.0,
                        "entry_band_status": "IN_BAND",
                        "quote_freshness_status": "fresh",
                        "base_case": "Synthetic base case",
                        "paper_or_live_execution_allowed": False,
                    },
                    "authority": {
                        "capital_action_allowed": False,
                        "owner_approval_granted": False,
                        "owner_approval_inference_allowed": False,
                        "paper_trade_allowed": False,
                        "portfolio_mutation_allowed": False,
                        "trade_execution_allowed": False,
                        "trade_or_account_action_allowed": False,
                    },
                    "provenance": {"source_artifacts": [{"path": "tmp/source-vrt.json"}]},
                    "forward_scorecard": {
                        "status": "pending",
                        "known_at_time": {"anchor_price": 101.0, "band_status": "IN_BAND"},
                        "checkpoints": [{"horizon_days": 1, "status": "pending_window"}],
                        "outcome_grade_assigned": False,
                    },
                }
            ],
        })
        wf74 = write_json(root / "wf74.json", {
            "schema": "wf74.finance_recommendation_correctness_ledger.v1",
            "generated_at_utc": "2026-06-12T20:02:00Z",
            "rows": [
                {
                    "recommendation_id": "rec-goog",
                    "ticker": "GOOG",
                    "generated_at_utc": "2026-06-12T20:02:00Z",
                    "source_artifact": "tmp/goog.json",
                    "status": "ok",
                    "recommendation_posture": "deploy_candidate",
                    "daily_review_state": "PROMOTION REVIEW",
                    "entry_band_status": "IN_BAND",
                    "close": 200.0,
                    "band_low": 190.0,
                    "band_high": 210.0,
                    "stop_or_invalidation": 180.0,
                    "source_freshness": {"overall_classification": "fresh", "trust_level": "review", "owner_review_required": True},
                    "failed_checks": [],
                    "wf55_exact_recommendation_id_present": True,
                    "authority_boundary": {
                        "owner_approval_inferred": False,
                        "capital_deployment_approved": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                    },
                }
            ],
        })
        wf78 = write_json(root / "wf78.json", {
            "schema": "veritas.wf78_deployment_readiness_human_review.v1",
            "generated_at_utc": "2026-06-12T20:03:00Z",
            "rows": [
                {
                    "ticker": "PH",
                    "packet_id": "packet-ph",
                    "auto_tier": "Tier A",
                    "route_state": "A-WATCH",
                    "priority_score": 70,
                    "readiness_impact": "synthetic impact",
                    "review_status": "ready_for_non_executing_deployment_readiness_row",
                    "band_status": "ABOVE_BAND",
                    "latest_known_price": 120.0,
                    "entry_band_low": 100.0,
                    "entry_band_high": 110.0,
                    "stop_or_invalidation": 95.0,
                    "owner_source_path": "03. Portfolio/Execution Board.md",
                    "owner_source_timestamp": "2026-06-12",
                    "deployment_surface_existing_row_present": False,
                    "proposed_non_executing_review_action": "Review only",
                    "review_only": True,
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "paper_or_live_execution_allowed": False,
                    "owner_approval_inferred": False,
                    "band_context_group": "ABOVE_BAND_NO_CHASE",
                    "no_chase": True,
                    "human_review_posture": "no_chase_above_band_review_only",
                }
            ],
        })
        wf85_cards = write_json(root / "wf85-cards.json", {
            "schema": "veritas.trade_grade_decision_cards.v1",
            "generated_at_utc": "2026-06-12T20:04:00Z",
            "cards": [
                {
                    "ticker": "NVDA",
                    "auto_tier": "Tier A",
                    "auto_state": "A-READY",
                    "primary_state": "review_ready",
                    "queue_state": "A-DEPLOY-CANDIDATE-REVIEW-READY",
                    "decision_state": "review_ready",
                    "thesis_snapshot": {"summary": "Synthetic thesis"},
                    "current_price": {"latest_known_price": 50.0, "market_date": "2026-06-12", "source": "tmp/quote.json"},
                    "entry_band": {"low": 45.0, "high": 55.0, "band_status": "IN_BAND"},
                    "stop_or_invalidation": {"level": 40.0},
                    "source_freshness": {"status": "fresh", "quote_freshness_status": "fresh", "fresh_quote_required": False},
                    "evidence_family_status": [{"status": "ok"}],
                    "owner_action_required": True,
                    "authority_boundary": {
                        "capital_deployment_approved": False,
                        "trade_or_execution_approved": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "money_movement_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ],
        })
        wf85_factory = write_json(root / "wf85-factory.json", {
            "schema": "veritas.finance_decision_factory.v1",
            "generated_at_utc": "2026-06-12T20:05:00Z",
            "decision_ledger": [
                {
                    "ticker": "ETN",
                    "auto_tier": "Tier A",
                    "queue_state": "A-DEPLOY-CANDIDATE-REVIEW-READY",
                    "gate_verdict": "defer_until_veto_clears",
                    "gate_vetoes": ["synthetic"],
                    "card_preparable": True,
                    "current_price": 80.0,
                    "current_band_status": "BELOW_BAND",
                    "entry_band_low": 82.0,
                    "entry_band_high": 90.0,
                    "stop_or_invalidation": 76.0,
                    "quote_freshness_status": "fresh",
                    "disposition": "gate_deferred",
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "paper_or_live_execution_allowed": False,
                    "owner_approval_inferred": False,
                }
            ],
        })
        wf77 = write_json(root / "wf77.json", {
            "schema_version": "wf77_price_freshness_bridge.v1",
            "generated_at_utc": "2026-06-12T20:06:00Z",
            "rows": [
                {
                    "ticker": "VRT",
                    "tier": "A",
                    "coverage_lane": "execution",
                    "monitoring_role": "decision_queue_or_near_action",
                    "price_state": {"latest_close": 101.0, "data_date": "2026-06-12", "source": "tmp/technical-refresh.json", "ma_posture": "above 200d"},
                    "card_price_context": {"fresh_price_band_status": "IN_BAND", "entry_band_low": 95.0, "entry_band_high": 105.0, "stop_or_invalidation": 90.0},
                }
            ],
        })
        return {
            "wf55_current": wf55,
            "wf74_correctness": wf74,
            "wf78_human_review": wf78,
            "wf85_decision_cards": wf85_cards,
            "wf85_decision_factory": wf85_factory,
            "wf77_price_state": wf77,
        }


if __name__ == "__main__":
    unittest.main()
