#!/usr/bin/env python3
"""Tests for the WF88 DB duplicate-source delete packet."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_db_duplicate_source_delete_packet.py"

spec = importlib.util.spec_from_file_location("wf88_db_duplicate_source_delete_packet", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class Wf88DbDuplicateSourceDeletePacketTests(unittest.TestCase):
    def test_packet_ready_requires_matching_archive_copy_and_neutralized_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "tmp" / mod.TARGET_BASENAME
            archive = root / "09. Archive" / "DB Lifecycle - Archived" / "2026-05-30" / "wf72-drill" / mod.TARGET_BASENAME
            source.parent.mkdir(parents=True)
            archive.parent.mkdir(parents=True)
            source.write_bytes(b"same")
            archive.write_bytes(b"same")
            digest = mod.sha256_file(source)
            manifest = {
                "entries": [
                    {
                        "path": f"tmp/{mod.TARGET_BASENAME}",
                        "basename": mod.TARGET_BASENAME,
                        "status": "archive_destination_already_present",
                        "recommendation": "duplicate",
                        "proposed_destination": "09. Archive/DB Lifecycle - Archived/2026-05-30/wf72-drill/" + mod.TARGET_BASENAME,
                        "sha256": digest,
                        "size_bytes": source.stat().st_size,
                        "sqlite": {"open_status": "ok", "integrity_check": "ok"},
                        "sidecars": [],
                        "reference_classification": {
                            "active_operational_consumer_references": [
                                "06. Playbooks/Project Continuity/Workflow 88 - Veritas OS 2.0.md",
                                "scripts/test_wf88_retired_surface_cleanup_plan.py",
                            ]
                        },
                    }
                ]
            }
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "MANIFEST", root / "manifest.json"):
                (root / "manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
                packet = mod.build_packet()
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertTrue(packet["summary"]["source_delete_allowed_after_owner_approval"])

    def test_packet_blocks_unknown_operational_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "tmp" / mod.TARGET_BASENAME
            archive = root / "09. Archive" / "DB Lifecycle - Archived" / "2026-05-30" / "wf72-drill" / mod.TARGET_BASENAME
            source.parent.mkdir(parents=True)
            archive.parent.mkdir(parents=True)
            source.write_bytes(b"same")
            archive.write_bytes(b"same")
            digest = mod.sha256_file(source)
            manifest = {
                "entries": [
                    {
                        "path": f"tmp/{mod.TARGET_BASENAME}",
                        "basename": mod.TARGET_BASENAME,
                        "status": "archive_destination_already_present",
                        "proposed_destination": "09. Archive/DB Lifecycle - Archived/2026-05-30/wf72-drill/" + mod.TARGET_BASENAME,
                        "sha256": digest,
                        "size_bytes": source.stat().st_size,
                        "sqlite": {"open_status": "ok", "integrity_check": "ok"},
                        "sidecars": [],
                        "reference_classification": {
                            "active_operational_consumer_references": ["scripts/active_consumer.py"]
                        },
                    }
                ]
            }
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "MANIFEST", root / "manifest.json"):
                (root / "manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
                packet = mod.build_packet()
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertIn("unneutralized_operational_references_remain", packet["validation"]["errors"])


if __name__ == "__main__":
    unittest.main()
