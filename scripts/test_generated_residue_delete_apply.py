#!/usr/bin/env python3
"""Fail-closed regression tests for the manifest-bound generated-residue delete tool."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("generated_residue_delete_apply.py")
SPEC = importlib.util.spec_from_file_location("generated_residue_delete_apply", MODULE_PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)

ELIGIBLE = tool.parse_iso("2026-09-23T05:01:23Z")
AFTER = ELIGIBLE + timedelta(minutes=5)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class GeneratedResidueDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.real_before = {p: tool.sha256_file(p) for p in (tool.ROOT / tool.ARCHIVE_ROOT_REL).glob("*") if p.is_file()}
        self.archive = self.root / tool.ARCHIVE_ROOT_REL
        self.archive.mkdir(parents=True)
        self.evidence = self.root / tool.EVIDENCE_REL
        self.evidence.mkdir(parents=True)
        (self.root / "scripts").mkdir()
        self.files = {"_alpha.log": b"alpha residue\n", "beta-run.out": b"beta residue output\n"}
        rows = []
        for name, data in self.files.items():
            (self.archive / name).write_bytes(data)
            rows.append({"path": f"tmp/{name}", "sha256": digest(data), "bytes": len(data),
                         "proposed_destination": tool.ARCHIVE_ROOT_REL})
        self.bystander = self.archive / "not-in-scope.log"
        self.bystander.write_bytes(b"keep me\n")
        frozen = self.evidence / tool.FROZEN_NAME
        frozen.write_text(json.dumps({"suggestions": rows}), encoding="utf-8")
        approval = {
            "scope": {"frozen_manifest_sha256": tool.sha256_file(frozen), "row_count": len(rows),
                      "total_bytes": sum(len(d) for d in self.files.values())},
            "retention_rule": {"eligible_at_utc": "2026-09-23T05:01:23Z"},
            "authority_boundary": {"other_archive_family_covered": False},
        }
        (self.evidence / tool.APPROVAL_NAME).write_text(json.dumps(approval), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()
        real_after = {p: tool.sha256_file(p) for p in (tool.ROOT / tool.ARCHIVE_ROOT_REL).glob("*") if p.is_file()}
        self.assertEqual(self.real_before, real_after, "test touched the real pilot archive")

    def freeze(self, now=AFTER) -> tuple[Path, str]:
        manifest = tool.build_manifest(self.root, now)
        path = self.evidence / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path, tool.sha256_file(path)

    def all_present(self) -> bool:
        return all((self.archive / n).exists() for n in self.files) and self.bystander.exists()

    def test_build_refuses_before_retention_elapses(self) -> None:
        with self.assertRaisesRegex(tool.GateError, "retention not elapsed"):
            tool.build_manifest(self.root, ELIGIBLE - timedelta(seconds=1))

    def test_build_freezes_rows_with_24h_expiry_and_deletes_nothing(self) -> None:
        manifest = tool.build_manifest(self.root, AFTER)
        self.assertEqual(manifest["row_count"], 2)
        self.assertEqual(tool.parse_iso(manifest["expires_at_utc"]) - AFTER, timedelta(hours=24))
        self.assertFalse(manifest["authority_boundary"]["permanent_deletion_authorized"])
        self.assertTrue(self.all_present())

    def test_build_blocks_when_frozen_list_was_edited(self) -> None:
        frozen = self.evidence / tool.FROZEN_NAME
        frozen.write_text(frozen.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(tool.GateError, "frozen list sha256"):
            tool.build_manifest(self.root, AFTER)

    def test_build_blocks_on_live_reference(self) -> None:
        (self.root / "scripts" / "uses_it.py").write_text("open('tmp/_alpha.log')\n", encoding="utf-8")
        with self.assertRaisesRegex(tool.GateError, "live references"):
            tool.build_manifest(self.root, AFTER)

    def test_reference_scan_is_exact_basename(self) -> None:
        (self.root / "scripts" / "near.py").write_text("x = 'tier_alpha.log' + 'beta-run.out.bak'\n", encoding="utf-8")
        tool.build_manifest(self.root, AFTER)

    def test_build_blocks_on_hash_drift(self) -> None:
        (self.archive / "_alpha.log").write_bytes(b"alpha residuE\n")
        with self.assertRaisesRegex(tool.GateError, "sha256"):
            tool.build_manifest(self.root, AFTER)

    def test_preflight_without_apply_deletes_nothing(self) -> None:
        path, sha = self.freeze()
        receipt = tool.apply_manifest(self.root, path, sha, "", apply=False, now=AFTER)
        self.assertEqual(receipt["status"], "preflight_ok_nothing_deleted")
        self.assertTrue(self.all_present())

    def test_apply_requires_approval_reference(self) -> None:
        path, sha = self.freeze()
        receipt = tool.apply_manifest(self.root, path, sha, "  ", apply=True, now=AFTER)
        self.assertEqual(receipt["status"], "blocked")
        self.assertTrue(self.all_present())

    def test_apply_blocks_on_wrong_manifest_sha(self) -> None:
        path, _ = self.freeze()
        receipt = tool.apply_manifest(self.root, path, "0" * 64, "msg 1", apply=True, now=AFTER)
        self.assertIn("manifest sha256", receipt["reason"])
        self.assertTrue(self.all_present())

    def test_apply_blocks_after_manifest_expires(self) -> None:
        path, sha = self.freeze()
        receipt = tool.apply_manifest(self.root, path, sha, "msg 1", apply=True, now=AFTER + timedelta(hours=24, seconds=1))
        self.assertIn("validity window", receipt["reason"])
        self.assertTrue(self.all_present())

    def test_apply_blocks_row_outside_frozen_scope_even_if_sha_matches(self) -> None:
        path, _ = self.freeze()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        data = self.bystander.read_bytes()
        manifest["rows"].append({"archive_path": self.bystander.relative_to(self.root).as_posix(),
                                 "original_path": "tmp/not-in-scope.log", "sha256": digest(data), "bytes": len(data)})
        path.write_text(json.dumps(manifest), encoding="utf-8")
        receipt = tool.apply_manifest(self.root, path, tool.sha256_file(path), "msg 1", apply=True, now=AFTER)
        self.assertIn("differ from the approved frozen list", receipt["reason"])
        self.assertTrue(self.all_present())

    def test_apply_redirected_archive_path_is_blocked(self) -> None:
        path, _ = self.freeze()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["rows"][0]["archive_path"] = "scripts/_alpha.log"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        receipt = tool.apply_manifest(self.root, path, tool.sha256_file(path), "msg 1", apply=True, now=AFTER)
        self.assertEqual(receipt["status"], "blocked")
        self.assertTrue(self.all_present())

    def test_drift_in_any_row_blocks_all_deletes(self) -> None:
        path, sha = self.freeze()
        (self.archive / "beta-run.out").write_bytes(b"changed after freeze\n")
        receipt = tool.apply_manifest(self.root, path, sha, "msg 1", apply=True, now=AFTER)
        self.assertEqual(receipt["status"], "blocked")
        self.assertEqual(receipt["deleted"], [])
        self.assertTrue((self.archive / "_alpha.log").exists())

    def test_new_reference_after_freeze_blocks_apply(self) -> None:
        path, sha = self.freeze()
        (self.root / "scripts" / "late.py").write_text("p = 'beta-run.out'\n", encoding="utf-8")
        receipt = tool.apply_manifest(self.root, path, sha, "msg 1", apply=True, now=AFTER)
        self.assertIn("live references", receipt["reason"])
        self.assertTrue(self.all_present())

    def test_apply_deletes_exactly_the_frozen_rows(self) -> None:
        path, sha = self.freeze()
        receipt = tool.apply_manifest(self.root, path, sha, "Randall msg 1", apply=True, now=AFTER)
        self.assertEqual(receipt["status"], "deleted_all")
        self.assertEqual(len(receipt["deleted"]), 2)
        self.assertFalse(any((self.archive / n).exists() for n in self.files))
        self.assertTrue(self.bystander.exists())
        self.assertTrue((self.evidence / tool.APPROVAL_NAME).exists())

    def test_evidence_writes_never_overwrite(self) -> None:
        target = self.evidence / "once.json"
        tool.write_json_new(target, {"a": 1})
        with self.assertRaises(FileExistsError):
            tool.write_json_new(target, {"a": 2})


if __name__ == "__main__":
    unittest.main()
