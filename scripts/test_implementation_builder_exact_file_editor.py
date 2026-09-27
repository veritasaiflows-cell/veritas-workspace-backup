#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import implementation_builder_exact_file_editor as editor


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


class ExactFileEditorTests(unittest.TestCase):
    def fixture(self, base: Path, *, job_id: str = "job-1") -> tuple[Path, Path]:
        root = base / "worktree"
        root.mkdir()
        (root / "nested").mkdir()
        (root / "a.txt").write_bytes(b"alpha\nbeta\n")
        (root / "nested" / "new.txt").write_bytes(b"")
        manifest = {
            "schema": editor.MANIFEST_SCHEMA,
            "generated_at_utc": "2026-09-26T00:00:00Z",
            "job_id": job_id,
            "source_base_label": "fixture",
            "limits": {},
            "file_count": 1,
            "total_bytes": 11,
            "estimated_context_tokens": 3,
            "files": [],
            "allowed_write_paths": ["a.txt", "nested/new.txt"],
            "output_placeholders": [
                {
                    "relative_path": "nested/new.txt",
                    "bytes": 0,
                    "sha256": editor.EMPTY_SHA256,
                }
            ],
            "execution_environment": {},
            "authority": {
                "writable_root": "/worktree",
                "main_acceptance_required": True,
                "runtime_config_mutation_allowed": False,
                "network_allowed": False,
                "external_delivery_allowed": False,
            },
        }
        manifest_path = root / "handoff-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return root, manifest_path

    def apply(self, root: Path, manifest: Path, request: dict[str, object]) -> dict[str, object]:
        raw = json.dumps(request, separators=(",", ":")).encode("utf-8")
        return editor.apply_request(
            request,
            request_sha256=digest(raw),
            root=root,
            manifest_path=manifest,
        )

    def test_exact_replacement_and_placeholder_full_content_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            request = {
                "schema": editor.REQUEST_SCHEMA,
                "job_id": "job-1",
                "operations": [
                    {
                        "path": "a.txt",
                        "expected_sha256": digest(b"alpha\nbeta\n"),
                        "edits": [{"old": "beta", "new": "gamma"}],
                    },
                    {
                        "path": "nested/new.txt",
                        "expected_sha256": editor.EMPTY_SHA256,
                        "content_b64": b64(b"created through exact bind\n"),
                    },
                ],
            }
            result = self.apply(root, manifest, request)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["changed_file_count"], 2)
            self.assertFalse(result["files_created"])
            self.assertEqual((root / "a.txt").read_text(), "alpha\ngamma\n")
            self.assertEqual((root / "nested" / "new.txt").read_text(), "created through exact bind\n")

    def test_write_failure_restores_already_written_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            request = {
                "schema": editor.REQUEST_SCHEMA,
                "job_id": "job-1",
                "operations": [
                    {
                        "path": "a.txt",
                        "expected_sha256": digest(b"alpha\nbeta\n"),
                        "edits": [{"old": "beta", "new": "gamma"}],
                    },
                    {
                        "path": "nested/new.txt",
                        "expected_sha256": editor.EMPTY_SHA256,
                        "content_b64": b64(b"new\n"),
                    },
                ],
            }
            job_id, prepared = editor.prepare_edits(
                request,
                root=root,
                manifest_path=manifest,
            )
            original_write = editor._write_fd
            calls = 0

            def fail_second_write(fd: int, payload: bytes) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated write failure")
                original_write(fd, payload)

            with patch.object(editor, "_write_fd", side_effect=fail_second_write):
                with self.assertRaisesRegex(editor.ExactFileEditError, "written files restored"):
                    editor.commit_edits(job_id, prepared, "f" * 64)
            self.assertEqual((root / "a.txt").read_bytes(), b"alpha\nbeta\n")
            self.assertEqual((root / "nested" / "new.txt").read_bytes(), b"")

    def test_prevalidates_every_operation_before_first_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            request = {
                "schema": editor.REQUEST_SCHEMA,
                "job_id": "job-1",
                "operations": [
                    {
                        "path": "a.txt",
                        "expected_sha256": digest(b"alpha\nbeta\n"),
                        "edits": [{"old": "beta", "new": "gamma"}],
                    },
                    {
                        "path": "nested/new.txt",
                        "expected_sha256": "0" * 64,
                        "content_b64": b64(b"must not land\n"),
                    },
                ],
            }
            with self.assertRaisesRegex(editor.ExactFileEditError, "preimage hash mismatch"):
                self.apply(root, manifest, request)
            self.assertEqual((root / "a.txt").read_bytes(), b"alpha\nbeta\n")
            self.assertEqual((root / "nested" / "new.txt").read_bytes(), b"")

    def test_out_of_allowlist_path_is_rejected_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            request = {
                "schema": editor.REQUEST_SCHEMA,
                "job_id": "job-1",
                "operations": [
                    {
                        "path": "unlisted.txt",
                        "expected_sha256": editor.EMPTY_SHA256,
                        "content_b64": b64(b"no\n"),
                    }
                ],
            }
            with self.assertRaisesRegex(editor.ExactFileEditError, "outside the manifest allowlist"):
                self.apply(root, manifest, request)
            self.assertFalse((root / "unlisted.txt").exists())

    def test_missing_allowlisted_file_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            (root / "nested" / "new.txt").unlink()
            request = {
                "schema": editor.REQUEST_SCHEMA,
                "job_id": "job-1",
                "operations": [
                    {
                        "path": "nested/new.txt",
                        "expected_sha256": editor.EMPTY_SHA256,
                        "content_b64": b64(b"no\n"),
                    }
                ],
            }
            with self.assertRaises(OSError):
                self.apply(root, manifest, request)
            self.assertFalse((root / "nested" / "new.txt").exists())

    def test_job_mismatch_duplicate_and_control_paths_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            base_operation = {
                "path": "a.txt",
                "expected_sha256": digest(b"alpha\nbeta\n"),
                "edits": [{"old": "beta", "new": "gamma"}],
            }
            with self.assertRaisesRegex(editor.ExactFileEditError, "job_id"):
                self.apply(
                    root,
                    manifest,
                    {"schema": editor.REQUEST_SCHEMA, "job_id": "wrong", "operations": [base_operation]},
                )
            with self.assertRaisesRegex(editor.ExactFileEditError, "duplicate"):
                self.apply(
                    root,
                    manifest,
                    {"schema": editor.REQUEST_SCHEMA, "job_id": "job-1", "operations": [base_operation, base_operation]},
                )
            for path in ("handoff-manifest.json", ".git/config", "../escape.txt", "/absolute.txt"):
                with self.subTest(path=path), self.assertRaises(editor.ExactFileEditError):
                    editor.normalize_relative_path(path)

    def test_edit_must_match_exactly_once_and_must_change_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            for old, new, message in (
                ("missing", "x", "exactly once"),
                ("a", "x", "exactly once"),
                ("beta", "beta", "no-op"),
            ):
                request = {
                    "schema": editor.REQUEST_SCHEMA,
                    "job_id": "job-1",
                    "operations": [
                        {
                            "path": "a.txt",
                            "expected_sha256": digest(b"alpha\nbeta\n"),
                            "edits": [{"old": old, "new": new}],
                        }
                    ],
                }
                with self.subTest(old=old, new=new), self.assertRaisesRegex(editor.ExactFileEditError, message):
                    self.apply(root, manifest, request)
            self.assertEqual((root / "a.txt").read_bytes(), b"alpha\nbeta\n")

    def test_strict_request_shape_and_base64_decoder(self) -> None:
        request = {"schema": editor.REQUEST_SCHEMA, "job_id": "job-1", "operations": [], "extra": True}
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            with self.assertRaisesRegex(editor.ExactFileEditError, "fields"):
                self.apply(root, manifest, request)
        encoded = b64(json.dumps({"ok": True}).encode())
        decoded, observed = editor.decode_request_b64(encoded)
        self.assertEqual(decoded, {"ok": True})
        self.assertEqual(observed, digest(json.dumps({"ok": True}).encode()))
        with self.assertRaisesRegex(editor.ExactFileEditError, "canonical base64"):
            editor.decode_request_b64("%%%")

    def test_symlink_target_is_rejected_when_supported(self) -> None:
        if os.name == "nt":
            self.skipTest("Windows symlink creation is privilege-dependent")
        with tempfile.TemporaryDirectory() as temp:
            root, manifest = self.fixture(Path(temp))
            (root / "a.txt").unlink()
            (root / "a.txt").symlink_to(root / "nested" / "new.txt")
            request = {
                "schema": editor.REQUEST_SCHEMA,
                "job_id": "job-1",
                "operations": [
                    {
                        "path": "a.txt",
                        "expected_sha256": editor.EMPTY_SHA256,
                        "content_b64": b64(b"no\n"),
                    }
                ],
            }
            with self.assertRaises(OSError):
                self.apply(root, manifest, request)


if __name__ == "__main__":
    unittest.main()
