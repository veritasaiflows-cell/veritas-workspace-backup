from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agi_harness_readiness_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("agi_harness_readiness_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgiHarnessReadinessPacketTests(unittest.TestCase):
    def paths_for(self, module, root: Path) -> dict[str, Path]:
        return {name: root / "tmp" / f"{name}.json" for name in module.default_inputs(root)}

    def write_ready_sources(self, paths: dict[str, Path]) -> None:
        write_json(paths["agi_os_eval_gate"], {"status": "ok", "validation": {"status": "ok", "warnings": [], "errors": []}})
        write_json(
            paths["implementation_token_attribution"],
            {
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "gap_resolution_status": "classified_unavailable_only",
                    "implementation_token_gap_count": 3,
                    "unclassified_supported_runtime_gap_count": 0,
                },
            },
        )
        write_json(paths["token_usage"], {"status": "ok", "validation": {"status": "ok"}, "summary": {}})
        write_json(paths["cron_control"], {"status": "ok", "summary": {"blocked_count": 0, "escalation_signal_count": 0}})
        write_json(paths["cron_freshness"], {"status": "ok", "summary": {"blocked_count": 0}})
        write_json(paths["otel_ops"], {"status": "ok", "collector_health": {"listening": True}})
        write_json(paths["vector_memory_graph"], {"status": "ok", "summary": {"node_count": 3, "edge_count": 2}})
        write_json(
            paths["agent_message_ledger"],
            {
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "event_count": 4,
                    "verified_helper_event_count": 4,
                    "telemetry_blocked_event_count": 0,
                    "unverified_receipt_event_count": 0,
                },
            },
        )
        write_json(paths["wf74_wf88_checkpoint"], {"status": "ok"})
        write_json(paths["wf84_wf85_checkpoint"], {"status": "ok"})
        write_json(paths["implementation_checkpoint"], {"status": "ok"})
        write_json(paths["wf88_os2_control"], {"status": "ok"})
        write_json(paths["wf88_wiki_synthesis"], {"status": "ok"})

    def test_ready_sources_produce_review_only_ok_packet(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self.paths_for(module, root)
            self.write_ready_sources(paths)

            payload = module.build_payload(root, paths)

            self.assertEqual(payload["validation"]["status"], "ok")
            self.assertEqual(payload["readiness_state"], "ready_review_only")
            self.assertFalse(payload["authority_boundary"]["autonomy_promotion_allowed"])
            self.assertFalse(payload["authority_boundary"]["paper_or_live_execution_allowed"])
            self.assertFalse(payload["authority_boundary"]["owner_approval_inferred"])

    def test_otel_and_token_gaps_are_warnings_not_authority_expansion(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self.paths_for(module, root)
            self.write_ready_sources(paths)
            write_json(paths["agi_os_eval_gate"], {"status": "eval_warning_review_only", "validation": {"status": "warning", "warnings": ["implementation_token_attribution_gate"], "errors": []}})
            write_json(
                paths["implementation_token_attribution"],
                {
                    "status": "warning",
                    "validation": {"status": "warning"},
                    "summary": {
                        "gap_resolution_status": "stamp_required",
                        "implementation_token_gap_count": 23,
                        "unclassified_supported_runtime_gap_count": 2,
                    },
                },
            )
            write_json(paths["cron_control"], {"status": "ok", "summary": {"blocked_count": 1, "escalation_signal_count": 1}})
            write_json(paths["otel_ops"], {"status": "blocked", "collector_health": {"listening": False, "error": "timed out"}})

            payload = module.build_payload(root, paths)

            self.assertEqual(payload["validation"]["status"], "warning")
            self.assertEqual(payload["readiness_state"], "partial_ready_review_only_with_warnings")
            self.assertIn("implementation_token_attribution_gate", payload["validation"]["warnings"])
            self.assertIn("cron_otel_operations_gate", payload["validation"]["warnings"])
            self.assertFalse(payload["authority_boundary"]["runtime_config_mutation_allowed"])

    def test_missing_eval_packet_blocks_readiness(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self.paths_for(module, root)
            self.write_ready_sources(paths)
            paths["agi_os_eval_gate"].unlink()

            payload = module.build_payload(root, paths)

            self.assertEqual(payload["validation"]["status"], "blocked")
            self.assertIn("agi_os_eval_gate", payload["validation"]["errors"])
            self.assertEqual(payload["readiness_state"], "not_ready_blocked")

    def test_unverified_or_telemetry_blocked_agent_events_cannot_pass_auditability(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self.paths_for(module, root)
            self.write_ready_sources(paths)
            write_json(
                paths["agent_message_ledger"],
                {
                    "status": "ok",
                    "validation": {"status": "ok"},
                    "summary": {
                        "event_count": 1,
                        "verified_helper_event_count": 0,
                        "telemetry_blocked_event_count": 1,
                        "unverified_receipt_event_count": 1,
                    },
                },
            )

            payload = module.build_payload(root, paths)
            gates = {item["name"]: item for item in payload["gates"]}

            self.assertEqual(gates["helper_auditability_gate"]["status"], "warning")
            self.assertEqual(gates["helper_auditability_gate"]["evidence"]["telemetry_blocked_event_count"], 1)
            self.assertIn("helper_auditability_gate", payload["validation"]["warnings"])


if __name__ == "__main__":
    unittest.main()
