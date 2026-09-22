#!/usr/bin/env python3
"""Focused regression tests for the archive-only manifest binding gate."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("bounded_auto_archive.py")
SPEC = importlib.util.spec_from_file_location("bounded_auto_archive", MODULE_PATH)
assert SPEC and SPEC.loader
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


class BoundedAutoArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "tmp").mkdir()
        archive.ROOT = self.root
        archive.TMP = self.root / "tmp"
        archive.GENERATED_ROOT = self.root / "09. Archive" / "Auto Archive - Generated Residue"
        archive.DEPRECATED_ROOT = self.root / "09. Archive" / "Deprecated Files - Auto Archived"
        archive.LOG_ROOT = self.root / "09. Archive" / "Archive Logs"
        archive.TMP_REPORT = archive.TMP / "bounded-auto-archive-last-report.json"
        archive.TMP_MD = archive.TMP / "bounded-auto-archive-last-report.md"
        self.source = archive.TMP / "proof.log"
        self.source.write_bytes(b"frozen generated residue\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def item(self) -> dict[str, object]:
        return {
            "path": "tmp/proof.log", "kind": "generated_residue", "apply_allowed": True,
            "owner_approval_required": False, "reference_count": 0,
            "sha256": archive.sha256_file(self.source), "bytes": self.source.stat().st_size,
            "proposed_destination": "09. Archive/Auto Archive - Generated Residue/test",
        }

    def execute_manifest(self, item: dict[str, object], apply: bool) -> dict[str, object]:
        manifest = archive.TMP / "input.json"
        manifest.write_text(json.dumps({"suggestions": [item]}), encoding="utf-8")
        return archive.build_report(manifest, apply=apply)

    def test_apply_binds_hash_and_bytes_and_reports_manifest_identity(self) -> None:
        report = self.execute_manifest(self.item(), apply=True)
        self.assertEqual(report["counts"]["moved"], 1)
        row = report["moved"][0]
        self.assertEqual(row["sha256_manifest"], row["sha256_before"])
        self.assertEqual(row["bytes_manifest"], len(b"frozen generated residue\n"))
        self.assertFalse(self.source.exists())

    def test_hash_drift_blocks_without_moving(self) -> None:
        item = self.item()
        item["sha256"] = "0" * 64
        report = self.execute_manifest(item, apply=True)
        self.assertEqual(report["counts"]["moved"], 0)
        self.assertIn("manifest sha256 mismatch", report["blocked"][0]["reason"])
        self.assertTrue(self.source.exists())

    def test_byte_drift_blocks_without_moving(self) -> None:
        item = self.item()
        item["bytes"] = 0
        report = self.execute_manifest(item, apply=True)
        self.assertEqual(report["counts"]["moved"], 0)
        self.assertIn("manifest byte count mismatch", report["blocked"][0]["reason"])
        self.assertTrue(self.source.exists())

    def test_existing_destination_fails_closed(self) -> None:
        item = self.item()
        destination = archive.GENERATED_ROOT / "test" / self.source.name
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"unrelated archive file")
        report = self.execute_manifest(item, apply=True)
        self.assertEqual(report["counts"]["moved"], 0)
        self.assertIn("destination already exists", report["blocked"][0]["reason"])
        self.assertTrue(self.source.exists())


if __name__ == "__main__":
    unittest.main()
