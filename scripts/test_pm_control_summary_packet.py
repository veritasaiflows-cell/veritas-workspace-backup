from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm_control_summary_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("pm_control_summary_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PMControlSummaryPacketTests(unittest.TestCase):
    def test_summary_packet_omits_raw_sections_and_preserves_boundary(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pm_control = root / "pm-control-packet.json"
            pm_control.write_text(json.dumps({
                "status": "ok",
                "generated_at_utc": "2026-07-05T00:00:00Z",
                "summary": {
                    "pm_status": "ok",
                    "pm_readiness": "green",
                    "next_action_count": 3,
                    "top_next_action": {
                        "rank": 1,
                        "lane_id": "finance_os_data_model",
                        "action_id": "finance-refresh",
                        "description": "Refresh data plane.",
                        "inline_execution_allowed": False,
                        "heartbeat_may_execute": False,
                    },
                    "implementation_queue": {
                        "job_count": 5,
                        "ready_job_count": 2,
                        "active_job_count": 1,
                        "blocked_job_count": 0,
                        "helper_lane_allowed_job_count": 2,
                    },
                    "heartbeat": {"candidate_count": 4, "blocked_count": 1, "handoff_ready_count": 2},
                    "main_session_handoff": {
                        "status": "ready_for_main_session",
                        "selected_action": "finance-refresh",
                        "selected_lane": "finance_os_data_model",
                    },
                    "main_session_greenkeeper": {
                        "status": "warning",
                        "validation_warnings": ["main_handoff_action_present"],
                    },
                    "main_session_escalation_consumer": {"cron_escalation_signal_count": 0},
                    "control_plane_signal_freshness": {"stale_count": 0},
                    "stale_lane_digest": {
                        "stale_lane_count": 1,
                        "next_safe_action": "Refresh top lane.",
                        "lanes": [{"lane_id": "finance_os_data_model", "title": "Finance OS", "readiness_score": 45}],
                    },
                },
                "sections": {"large_raw_section": ["do not copy"]},
                "validation": {"status": "ok"},
            }), encoding="utf-8")

            packet = module.build_packet(pm_control)

            self.assertEqual(packet["summary"]["implementation_ready_job_count"], 2)
            self.assertEqual(packet["top_next_action"]["lane_id"], "finance_os_data_model")
            self.assertNotIn("sections", packet)
            self.assertFalse(packet["authority_boundary"]["executes_work"])
            self.assertFalse(packet["authority_boundary"]["spawns_helpers"])
            self.assertIn("main_session_handoff_ready", packet["validation"]["warnings"])


if __name__ == "__main__":
    unittest.main()
