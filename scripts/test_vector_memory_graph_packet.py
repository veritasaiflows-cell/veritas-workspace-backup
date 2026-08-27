from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vector_memory_graph_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("vector_memory_graph_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VectorMemoryGraphPacketTests(unittest.TestCase):
    def test_graph_links_sources_to_workflows_tickers_actions_and_boundaries(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tmp").mkdir()
            packet = root / "tmp" / "wf78-route.json"
            packet.write_text(
                json.dumps(
                    {
                        "status": "warning",
                        "workflow_id": "WF78",
                        "ticker": "NVDA",
                        "summary": {
                            "next_action": "Source-open material claims before WF85 review.",
                            "blocked_reason": "earnings claim still needs review",
                        },
                    }
                ),
                encoding="utf-8",
            )
            db = root / "tmp" / "vector-memory.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE sources(source_path TEXT, source_family TEXT, authority_class TEXT, chunk_count INTEGER)"
            )
            conn.execute(
                "INSERT INTO sources VALUES(?, ?, ?, ?)",
                ("tmp/wf78-route.json", "wf78_finance_routing_packet", "derived_proof_packet", 1),
            )
            conn.commit()
            conn.close()

            payload = module.build_packet(root, db)

            self.assertIn(payload["status"], {"ok", "warning"})
            self.assertFalse(payload["authority_boundary"]["approval_authority"])
            self.assertGreater(payload["summary"]["node_count"], 0)
            node_ids = {node["id"] for node in payload["nodes"]}
            self.assertIn("workflow:WF78", node_ids)
            self.assertIn("ticker:NVDA", node_ids)
            edge_types = {edge["type"] for edge in payload["edges"]}
            self.assertIn("mentions_workflow", edge_types)
            self.assertIn("reports_action", edge_types)


if __name__ == "__main__":
    unittest.main()
