#!/usr/bin/env python3
"""Focused tests for implementation_builder_worktree_manager.py."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import implementation_builder_worktree_manager as manager


class PathContractTests(unittest.TestCase):
    def test_normalize_rejects_escape_absolute_and_control_paths(self) -> None:
        for value in (
            "../escape.txt",
            "/absolute.txt",
            "C:/absolute.txt",
            "nested/file.txt:stream",
            ".git/config",
            ".GIT/config",
            "nested/.git/config",
            "handoff-manifest.JSON",
            ".veritas-scoped-worktree.JSON",
            "NUL.txt",
            "NUL .txt",
            "trailing-dot.",
            "handoff-manifest.json",
        ):
            with self.subTest(value=value):
                with self.assertRaises(manager.WorktreeError):
                    manager.normalize_relative_path(value)

    def test_target_must_be_exact_scoped_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "handoff"
            expected, resolved_root = manager.assert_exact_target(root / "scoped-worktree", root)
            self.assertEqual(expected, resolved_root / "scoped-worktree")
            with self.assertRaises(manager.WorktreeError):
                manager.assert_exact_target(root / "other", root)

    def test_target_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "handoff"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            target = root / "scoped-worktree"
            try:
                os.symlink(outside, target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")
            with self.assertRaises(manager.WorktreeError):
                manager.assert_exact_target(target, root)

    def test_normalize_rejects_case_colliding_paths(self) -> None:
        with self.assertRaises(manager.WorktreeError):
            manager.normalize_path_list(
                ["nested/File.txt", "nested/file.txt"], label="test paths"
            )

    def test_inspection_rejects_non_utf8_and_too_many_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / "bad.bin").write_bytes(b"\xff")
            with self.assertRaises(manager.WorktreeError):
                manager.inspect_frozen_files(source, ["bad.bin"])
            names = []
            for index in range(manager.MAX_FILES + 1):
                name = f"f{index}.txt"
                names.append(name)
                (source / name).write_text("ok\n", encoding="utf-8")
            with self.assertRaises(manager.WorktreeError):
                manager.inspect_frozen_files(source, names)

    def test_inspection_rejects_oversize_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / "large.txt").write_text(
                "x" * (manager.MAX_FILE_BYTES + 1), encoding="utf-8"
            )
            with self.assertRaises(manager.WorktreeError):
                manager.inspect_frozen_files(source, ["large.txt"])

    def test_inspection_accepts_one_file_above_attachment_reader_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            payload = ("x" * 100 + "\n") * 500
            self.assertGreater(len(payload.encode("utf-8")), 40_000)
            (source / "large-source.py").write_text(payload, encoding="utf-8")

            frozen = manager.inspect_frozen_files(source, ["large-source.py"])

            self.assertEqual(len(frozen), 1)
            self.assertEqual(
                frozen[0].byte_count, (source / "large-source.py").stat().st_size
            )

    def test_status_only_identical_manifest_is_packaging_metadata_drift(self) -> None:
        status = b" M handoff-manifest.json\0"
        with patch.object(manager, "refresh_git_index") as refresh, patch.object(
            manager,
            "run_git_bytes",
            side_effect=[status, b"", b"", status],
        ), patch.object(
            manager, "git_path_matches_head_blob", return_value=True
        ) as identical:
            inventory = manager.capture_git_path_inventory(
                Path("C:/fixture"),
                allow_identical_status_only_paths=(manager.MANIFEST_FILENAME,),
            )

        refresh.assert_called_once()
        identical.assert_called_once_with(Path("C:/fixture"), manager.MANIFEST_FILENAME)
        self.assertEqual(inventory["paths"], [])
        self.assertEqual(inventory["status_paths"], [])
        self.assertEqual(
            inventory["packaging_metadata_drift_paths"],
            [manager.MANIFEST_FILENAME],
        )
        self.assertTrue(manager.git_inventory_matches_changed_paths(inventory, []))
        legacy_inventory = dict(inventory)
        legacy_inventory.pop("packaging_metadata_drift_paths")
        self.assertTrue(
            manager.git_inventory_matches_changed_paths(legacy_inventory, [])
        )

    def test_status_only_changed_manifest_still_fails_closed(self) -> None:
        status = b" M handoff-manifest.json\0"
        with patch.object(manager, "refresh_git_index"), patch.object(
            manager,
            "run_git_bytes",
            side_effect=[status, b"", b"", status],
        ), patch.object(manager, "git_path_matches_head_blob", return_value=False):
            with self.assertRaisesRegex(
                manager.WorktreeError,
                "Git status and tracked/untracked inventories differ",
            ):
                manager.capture_git_path_inventory(
                    Path("C:/fixture"),
                    allow_identical_status_only_paths=(manager.MANIFEST_FILENAME,),
                )


@unittest.skipUnless(shutil.which("git"), "git is required for integration tests")
class WorktreeLifecycleTests(unittest.TestCase):
    def test_prepare_preserves_crlf_bytes_when_global_autocrlf_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            global_config = base / "global.gitconfig"
            source.mkdir()
            (source / "a.txt").write_bytes(b"alpha\r\n")
            global_config.write_text(
                "[core]\n\tautocrlf = true\n", encoding="utf-8"
            )

            def write_json_with_windows_newlines(
                path: Path, payload: dict[str, object]
            ) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").replace(
                    "\n", "\r\n"
                )
                path.write_bytes(raw.encode("utf-8"))

            with patch.dict(
                os.environ,
                {
                    "GIT_CONFIG_GLOBAL": str(global_config),
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
            ), patch.object(
                manager, "write_json", side_effect=write_json_with_windows_newlines
            ):
                manager.prepare_worktree(
                    job_id="probe-crlf-baseline",
                    source_root=source,
                    source_base_label="tmp/probe-source",
                    relative_paths=["a.txt"],
                    target=target,
                    handoff_root=handoff,
                )

            self.assertEqual(
                manager.run_git(target, "config", "--local", "--get", "core.autocrlf").strip(),
                "false",
            )
            for relative in ("a.txt", manager.MANIFEST_FILENAME):
                with self.subTest(relative=relative):
                    committed_oid = manager.run_git(
                        target, "rev-parse", f"HEAD:{relative}"
                    ).strip()
                    working_oid = manager.run_git(
                        target, "hash-object", "--no-filters", relative
                    ).strip()
                    self.assertEqual(working_oid, committed_oid)
            self.assertEqual(
                manager.run_git(
                    target,
                    "-c",
                    "core.autocrlf=false",
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                ),
                "",
            )

    def test_prepare_verify_close_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / "nested").mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            (source / "nested" / "b.txt").write_text("beta\n", encoding="utf-8")

            prepared = manager.prepare_worktree(
                job_id="probe-1",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["nested/b.txt", "a.txt"],
                allowed_output_paths=["result.json"],
                target=target,
                handoff_root=handoff,
            )
            self.assertEqual(prepared["status"], "ok")
            self.assertEqual(prepared["file_count"], 2)
            self.assertEqual(
                manager.load_json(target / manager.MANIFEST_FILENAME)[
                    "execution_environment"
                ],
                manager.PYTHON_BYTECODE_ENV,
            )
            self.assertFalse((target / manager.SENTINEL_FILENAME).exists())
            sentinel_path = handoff / manager.SENTINEL_FILENAME
            self.assertTrue(sentinel_path.is_file())
            tracked_baseline = sorted(
                item
                for item in manager.run_git(target, "ls-files", "-z", "--").split("\0")
                if item
            )
            self.assertEqual(
                tracked_baseline,
                ["a.txt", manager.MANIFEST_FILENAME, "nested/b.txt"],
            )
            verified = manager.verify_worktree(target=target, handoff_root=handoff)
            self.assertTrue(verified["clean"])
            self.assertEqual(
                set(verified["git_path_inventory_checkpoints"]),
                {"before_binding_recheck", "after_binding_recheck"},
            )
            self.assertEqual(verified["packaging_metadata_drift_paths"], [])

            (target / "a.txt").write_text("alpha changed\n", encoding="utf-8")
            (target / "result.json").write_text('{"ok":true}\n', encoding="utf-8")
            patch_path = base / "proof" / "builder.patch"
            closed = manager.close_worktree(
                patch_path=patch_path,
                target=target,
                handoff_root=handoff,
            )
            self.assertEqual(closed["status"], "ok")
            self.assertEqual(closed["changed_file_count"], 2)
            self.assertEqual(closed["unexpected_changed_paths"], [])
            self.assertTrue(closed["patch_includes_declared_new_files"])
            self.assertTrue(patch_path.is_file())
            patch_text = patch_path.read_text(encoding="utf-8")
            self.assertIn("result.json", patch_text)
            self.assertIn('{"ok":true}', patch_text)
            self.assertEqual(closed["patch_sha256"], manager.sha256_file(patch_path))
            self.assertEqual(closed["tracked_diff_sha256"], closed["patch_sha256"])
            checkpoints = closed["git_path_inventory_checkpoints"]
            self.assertEqual(
                checkpoints["before_binding_recheck"],
                checkpoints["after_binding_recheck"],
            )
            self.assertEqual(
                checkpoints["before_binding_recheck"]["paths"],
                ["a.txt", "result.json"],
            )
            self.assertEqual(
                closed["git_path_inventory_sha256"],
                manager.git_inventory_checkpoints_sha256(
                    checkpoints, ["a.txt", "result.json"]
                ),
            )
            canonical_bytes = json.dumps(
                {
                    "schema": "veritas.git_path_inventory_checkpoints.v1",
                    "checkpoints": checkpoints,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            self.assertEqual(
                closed["git_path_inventory_sha256"],
                hashlib.sha256(canonical_bytes).hexdigest(),
            )
            apply_target = base / "apply-check"
            manager.run_git(
                base,
                "clone",
                "--quiet",
                "--no-hardlinks",
                str(target),
                str(apply_target),
            )
            manager.run_git(apply_target, "apply", "--check", str(patch_path))
            manager.run_git(apply_target, "apply", str(patch_path))
            for changed_file in closed["changed_files"]:
                changed_path = apply_target / changed_file["relative_path"]
                self.assertTrue(changed_path.is_file())
                self.assertEqual(
                    manager.sha256_file(changed_path), changed_file["sha256"]
                )
            self.assertEqual(manager._all_changed_paths(target), ["a.txt", "result.json"])
            sentinel = manager.load_json(sentinel_path)
            self.assertEqual(sentinel["state"], "closed")
            with self.assertRaises(manager.WorktreeError):
                manager.verify_worktree(target=target, handoff_root=handoff)

    def test_verify_requires_manifest_blob_and_clean_content_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-manifest-blob",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["a.txt"],
                target=target,
                handoff_root=handoff,
            )

            with patch.object(
                manager, "git_path_matches_head_blob", return_value=False
            ):
                with self.assertRaisesRegex(
                    manager.WorktreeError,
                    "manifest bytes or content diff differ",
                ):
                    manager.verify_worktree(target=target, handoff_root=handoff)

    def test_prepare_refuses_preexisting_sibling_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            handoff.mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            sentinel_path = handoff / manager.SENTINEL_FILENAME
            original = '{"preserve":true}\n'
            sentinel_path.write_text(original, encoding="utf-8")

            with self.assertRaises(manager.WorktreeError):
                manager.prepare_worktree(
                    job_id="probe-existing-sentinel",
                    source_root=source,
                    source_base_label="tmp/probe-source",
                    relative_paths=["a.txt"],
                    target=target,
                    handoff_root=handoff,
                )

            self.assertEqual(sentinel_path.read_text(encoding="utf-8"), original)
            self.assertFalse(target.exists())

    def test_python_execution_routes_bytecode_outside_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            cache_root = base / "ephemeral-python-cache"
            source.mkdir()
            (source / "sample_module.py").write_text(
                "VALUE = 42\n", encoding="utf-8"
            )
            manager.prepare_worktree(
                job_id="probe-bytecode-routing",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["sample_module.py"],
                target=target,
                handoff_root=handoff,
            )

            python_env = os.environ.copy()
            python_env.update(manager.PYTHON_BYTECODE_ENV)
            python_env["PYTHONPYCACHEPREFIX"] = str(cache_root)
            for command in (
                [sys.executable, "-c", "import sample_module; assert sample_module.VALUE == 42"],
                [sys.executable, "-m", "py_compile", "sample_module.py"],
            ):
                completed = subprocess.run(
                    command,
                    cwd=target,
                    env=python_env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=completed.stderr or completed.stdout,
                )

            residue = [
                path.relative_to(target).as_posix()
                for path in target.rglob("*")
                if path.name == "__pycache__" or path.suffix == ".pyc"
            ]
            self.assertEqual(residue, [])
            self.assertTrue(any(cache_root.rglob("*.pyc")))
            self.assertEqual(manager.run_git(target, "status", "--porcelain=v1"), "")

    def test_prepare_refuses_nonempty_existing_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            target.mkdir(parents=True)
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            (target / "unowned.txt").write_text("preserve\n", encoding="utf-8")
            with self.assertRaises(manager.WorktreeError):
                manager.prepare_worktree(
                    job_id="probe-2",
                    source_root=source,
                    source_base_label="tmp/probe-source",
                    relative_paths=["a.txt"],
                    target=target,
                    handoff_root=handoff,
                )

    def test_close_rejects_unlisted_new_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-3",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["a.txt"],
                allowed_output_paths=["result.json"],
                target=target,
                handoff_root=handoff,
            )
            (target / "unexpected.txt").write_text("nope\n", encoding="utf-8")
            with self.assertRaises(manager.WorktreeError):
                manager.close_worktree(
                    patch_path=base / "unexpected.patch",
                    target=target,
                    handoff_root=handoff,
                )

    def test_close_rejects_ignored_unlisted_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-ignored-unlisted",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=[".gitignore", "a.txt"],
                allowed_output_paths=["result.json"],
                target=target,
                handoff_root=handoff,
            )
            (target / "a.txt").write_text("alpha changed\n", encoding="utf-8")
            (target / "unexpected.ignored").write_text("hidden\n", encoding="utf-8")
            with self.assertRaises(manager.WorktreeError):
                manager.close_worktree(
                    patch_path=base / "ignored-unexpected.patch",
                    target=target,
                    handoff_root=handoff,
                )

    def test_close_includes_ignored_allowed_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-ignored-allowed",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=[".gitignore", "a.txt"],
                allowed_output_paths=["result.ignored"],
                target=target,
                handoff_root=handoff,
            )
            (target / "result.ignored").write_text("included\n", encoding="utf-8")
            patch_path = base / "ignored-allowed.patch"
            closed = manager.close_worktree(
                patch_path=patch_path,
                target=target,
                handoff_root=handoff,
            )
            self.assertEqual(closed["changed_files"][0]["relative_path"], "result.ignored")
            self.assertIn("result.ignored", patch_path.read_text(encoding="utf-8"))
            inventory = closed["git_path_inventory_checkpoints"][
                "after_binding_recheck"
            ]
            self.assertEqual(inventory["paths"], ["result.ignored"])
            self.assertEqual(inventory["tracked_diff_paths"], ["result.ignored"])
            self.assertEqual(inventory["untracked_paths"], [])

    def test_close_rejects_oversize_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-oversize-output",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["a.txt"],
                target=target,
                handoff_root=handoff,
            )
            (target / "a.txt").write_text(
                "x" * (manager.MAX_FILE_BYTES + 1), encoding="utf-8"
            )
            with self.assertRaises(manager.WorktreeError):
                manager.close_worktree(
                    patch_path=base / "oversize.patch",
                    target=target,
                    handoff_root=handoff,
                )

    def test_close_rejects_wrong_case_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-case-alias",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["a.txt"],
                allowed_output_paths=["Result.txt"],
                target=target,
                handoff_root=handoff,
            )
            (target / "result.txt").write_text("wrong case\n", encoding="utf-8")
            with self.assertRaises(manager.WorktreeError):
                manager.close_worktree(
                    patch_path=base / "wrong-case.patch",
                    target=target,
                    handoff_root=handoff,
                )

    def test_close_rejects_changed_control_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            handoff = base / "handoff"
            target = handoff / "scoped-worktree"
            source.mkdir()
            (source / "a.txt").write_text("alpha\n", encoding="utf-8")
            manager.prepare_worktree(
                job_id="probe-4",
                source_root=source,
                source_base_label="tmp/probe-source",
                relative_paths=["a.txt"],
                target=target,
                handoff_root=handoff,
            )
            manifest = target / "handoff-manifest.json"
            manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(manager.WorktreeError):
                manager.close_worktree(
                    patch_path=base / "control.patch",
                    target=target,
                    handoff_root=handoff,
                )


if __name__ == "__main__":
    unittest.main()
