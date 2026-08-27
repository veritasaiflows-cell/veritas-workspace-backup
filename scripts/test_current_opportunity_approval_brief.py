#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import current_opportunity_approval_brief as brief


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class CurrentOpportunityApprovalBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        tmp = self.root / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)

        _write_json(
            tmp / "pm-control-packet.json",
            {
                "status": "ok",
                "generated_at_utc": "2026-07-07T20:00:00Z",
                "validation": {"status": "ok"},
                "summary": {
                    "pm_cockpit_source_health": {
                        "stale_required": [
                            {
                                "key": "python_go_source_truth_parity_validator_parity",
                                "path": "tmp/python-go-source-truth-parity.json",
                                "age_hours": 172.2,
                                "max_age_hours": 168,
                                "blocks_readiness": True,
                            }
                        ]
                    },
                    "stale_lane_digest": {
                        "lanes": [
                            {
                                "lane_id": "wf75_service_state",
                                "title": "WF75 service-state handoff",
                                "readiness_score": 72.0,
                                "next_action": "execute safe next step",
                                "validation_budget": "focused",
                            }
                        ]
                    },
                },
            },
        )
        _write_json(
            tmp / "cron-control-packet.json",
            {
                "status": "ok",
                "generated_at_utc": "2026-07-07T20:01:00Z",
                "validation": {"status": "ok"},
                "summary": {
                    "blocked_count": 0,
                    "escalation_signal_count": 0,
                    "handoff_first_proof_needs_repair_count": 1,
                    "handoff_first_proof_status": "warning",
                },
            },
        )
        _write_json(
            tmp / "trade-grade-decision-cards.json",
            {
                "status": "ok",
                "generated_at_utc": "2026-07-07T20:02:00Z",
                "validation": {"status": "ok"},
                "cards": [
                    {"ticker": "NVDA", "decision_state": "review_ready"},
                    {"ticker": "ADP", "decision_state": "monitor_only"},
                ],
            },
        )
        _write_json(
            tmp / "trade-grade-approval-card-gate.json",
            {
                "status": "ok",
                "generated_at_utc": "2026-07-07T20:03:00Z",
                "validation": {"status": "ok"},
                "summary": {"approval_card_draft_count": 0},
            },
        )
        _write_json(
            tmp / "wf85-paper-deployment-notification-digest.json",
            {
                "status": "ok",
                "generated_at_utc": "2026-07-07T20:04:00Z",
                "validation": {"status": "ok"},
                "summary": {
                    "deployment_ready_tickers": [],
                    "near_deployment_tickers": [],
                    "watch_tickers": ["ADP", "ETN"],
                    "blocked_or_repair_tickers": ["APP"],
                    "execution_ready_count": 0,
                    "wf67_guard_status": "blocked",
                },
                "categories": {
                    "watch": [
                        {
                            "ticker": "ADP",
                            "auto_state": "A-WATCH",
                            "decision_state": "monitor_only",
                            "primary_state": "blocked_missing_freshness",
                            "latest_known_price": 245.60,
                            "market_date": "2026-07-07",
                            "band_status": "IN_BAND",
                            "entry_band_low": 239.15,
                            "entry_band_high": 246.69,
                            "stop_or_invalidation": 231.0,
                        },
                        {
                            "ticker": "ETN",
                            "auto_state": "A-WATCH",
                            "decision_state": "monitor_only",
                            "primary_state": "monitor_only",
                            "latest_known_price": 395.68,
                            "market_date": "2026-07-07",
                            "band_status": "IN_BAND",
                            "entry_band_low": 360.73,
                            "entry_band_high": 412.18,
                        },
                    ],
                    "blocked_or_repair": [
                        {
                            "ticker": "APP",
                            "decision_state": "monitor_only",
                            "primary_state": "below_band_wait",
                            "band_status": "BELOW_BAND",
                        }
                    ],
                },
            },
        )
        _write_json(
            tmp / "owner-gated-action-review-queue.json",
            {
                "status": "ok",
                "generated_at_utc": "2026-07-07T20:05:00Z",
                "validation": {"status": "ok"},
                "review_items": [
                    {
                        "gate": "paper_execution",
                        "title": "Approve exact paper order",
                        "priority": "high",
                        "decision_state": "owner_required",
                        "required_owner_decision": "approve_or_decline",
                        "required_before_apply": ["fresh WF67 guard", "exact order terms"],
                        "source": "tmp/paper-order-request.json",
                    },
                    {
                        "gate": "monitor_only",
                        "title": "No action",
                        "required_owner_decision": "none_now",
                    },
                ],
            },
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_builds_fixed_packet_brief(self) -> None:
        packet = brief.build_brief(self.root)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertEqual(packet["summary"]["recommended_tool_call_budget"], 6)
        self.assertEqual(packet["summary"]["watch_count"], 2)
        self.assertEqual(packet["summary"]["owner_approval_required_count"], 1)
        self.assertEqual(packet["summary"]["overdue_item_count"], 3)
        self.assertEqual(packet["current_opportunities"]["finance"]["review_ready_tickers"], ["NVDA"])
        self.assertEqual(packet["current_opportunities"]["finance"]["watch_by_band_status"]["IN_BAND"], ["ADP", "ETN"])

    def test_preserves_review_only_authority_boundary(self) -> None:
        packet = brief.build_brief(self.root)
        boundary = packet["authority_boundary"]

        self.assertTrue(boundary["review_only"])
        self.assertTrue(boundary["deterministic_packet_route"])
        self.assertFalse(boundary["broad_search_allowed_by_default"])
        self.assertFalse(boundary["status_card_fallback_allowed_by_default"])
        self.assertFalse(boundary["paper_position_check_allowed_by_default"])
        self.assertFalse(boundary["capital_deployment_allowed"])
        self.assertFalse(boundary["trade_or_execution_allowed"])
        self.assertFalse(boundary["paper_or_live_execution_allowed"])
        self.assertFalse(boundary["owner_approval_inferred"])

    def test_refresh_contract_is_narrow_and_deterministic(self) -> None:
        commands = ["python " + " ".join(command) for command in brief.REFRESH_COMMANDS]

        self.assertEqual(len(commands), 5)
        self.assertIn("python scripts/pm_control_packet.py --write --write-db --validate", commands)
        self.assertIn("python scripts/cron_control_packet.py --write --validate", commands)
        self.assertIn("python scripts/trade_grade_decision_cards.py --write --validate", commands)
        self.assertIn("python scripts/wf85_paper_deployment_notification_digest.py --write --validate", commands)
        self.assertIn("python scripts/owner_gated_action_review_queue.py --write --validate", commands)
        self.assertFalse(any("status_card_packet" in command for command in commands))
        self.assertFalse(any("paper_position" in command for command in commands))
        self.assertFalse(any("workspace_index" in command for command in commands))

    def test_validation_blocks_missing_required_source(self) -> None:
        (self.root / "tmp" / "owner-gated-action-review-queue.json").unlink()
        packet = brief.build_brief(self.root)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertTrue(any(error == "missing_source:owner_gated_action_queue" for error in packet["validation"]["errors"]))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
