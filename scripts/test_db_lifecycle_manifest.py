from __future__ import annotations

import importlib.util
import gc
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "db_lifecycle_manifest.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("db_lifecycle_manifest", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def create_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE proof(id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO proof(value) VALUES ('ok')")


def test_manifest_surfaces_orphan_sidecars_without_delete_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        state = root / "state"
        archive = root / "09. Archive" / "DB Lifecycle - Archived"
        create_sqlite(tmp / "workspace-index.sqlite")
        orphan = state / "orphan.sqlite-wal"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("orphan-wal", encoding="utf-8")
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "STATE", state),
            mock.patch.object(module, "ARCHIVE_SCAN_ROOT", archive),
            mock.patch.object(module, "JSON_REPORT", tmp / "db-lifecycle-manifest.json"),
            mock.patch.object(module, "MD_REPORT", tmp / "db-lifecycle-manifest.md"),
            mock.patch.object(module, "ARCHIVE_APPROVAL_PACKET", tmp / "db-lifecycle-archive-approval-packet.json"),
        ):
            manifest = module.build_manifest()
            errors = module.validate_manifest(manifest)
            gc.collect()

    assert errors == []
    assert manifest["summary"]["database_count"] == 1
    assert manifest["summary"]["orphan_sidecar_count"] == 1
    sidecar = manifest["orphan_sidecars"][0]
    assert sidecar["path"] == "state/orphan.sqlite-wal"
    assert sidecar["parent_path"] == "state/orphan.sqlite"
    assert sidecar["parent_exists"] is False
    assert sidecar["delete_ready"] is False
    assert sidecar["apply_allowed"] is False
    assert sidecar["owner_approval_required"] is True


def test_vector_memory_and_workflow_checkpoint_dbs_are_protected() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        state = root / "state"
        archive = root / "09. Archive" / "DB Lifecycle - Archived"
        create_sqlite(tmp / "vector-memory.sqlite")
        create_sqlite(tmp / "vector-memory-hash-fallback.sqlite")
        create_sqlite(tmp / "vector-memory-ollama-primary.sqlite")
        create_sqlite(tmp / "vector-memory-ollama-full.sqlite")
        create_sqlite(tmp / "vector-memory-ollama-medium.sqlite")
        create_sqlite(tmp / "vector-memory-ollama-pilot.sqlite")
        create_sqlite(state / "workflow-checkpoints" / "generic-workflow-checkpoints.sqlite")
        create_sqlite(state / "workflow-checkpoints" / "wf74-wf88-checkpoints.sqlite")
        create_sqlite(state / "workflow-checkpoints" / "wf84-wf85-checkpoints.sqlite")
        create_sqlite(state / "workflow-checkpoints" / "implementation-closeout-checkpoints.sqlite")
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "STATE", state),
            mock.patch.object(module, "ARCHIVE_SCAN_ROOT", archive),
            mock.patch.object(module, "JSON_REPORT", tmp / "db-lifecycle-manifest.json"),
            mock.patch.object(module, "MD_REPORT", tmp / "db-lifecycle-manifest.md"),
            mock.patch.object(module, "ARCHIVE_APPROVAL_PACKET", tmp / "db-lifecycle-archive-approval-packet.json"),
        ):
            manifest = module.build_manifest()
            errors = module.validate_manifest(manifest)
            gc.collect()

    assert errors == []
    entries = {entry["basename"]: entry for entry in manifest["entries"]}
    for name in (
        "vector-memory.sqlite",
        "vector-memory-hash-fallback.sqlite",
        "vector-memory-ollama-primary.sqlite",
        "vector-memory-ollama-full.sqlite",
        "vector-memory-ollama-medium.sqlite",
        "vector-memory-ollama-pilot.sqlite",
        "generic-workflow-checkpoints.sqlite",
        "wf74-wf88-checkpoints.sqlite",
        "wf84-wf85-checkpoints.sqlite",
        "implementation-closeout-checkpoints.sqlite",
    ):
        assert entries[name]["lifecycle"] == "derived"
        assert entries[name]["status"] == "keep"
        assert entries[name]["archive_ready"] is False
        assert entries[name]["delete_ready"] is False

    assert "vector_memory_index.py build" not in entries["vector-memory.sqlite"]["rebuild_command"]
    assert "--db tmp\\vector-memory-hash-fallback.sqlite" in entries["vector-memory-hash-fallback.sqlite"]["rebuild_command"]


def test_retrieval_live_eval_dbs_are_derived_not_archive_ready() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        state = root / "state"
        archive = root / "09. Archive" / "DB Lifecycle - Archived"
        create_sqlite(tmp / "retrieval-live-eval-hash.sqlite")
        create_sqlite(tmp / "retrieval-live-eval-semantic.sqlite")
        create_sqlite(tmp / "retrieval-live-eval-mutation.sqlite")
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "STATE", state),
            mock.patch.object(module, "ARCHIVE_SCAN_ROOT", archive),
            mock.patch.object(module, "JSON_REPORT", tmp / "db-lifecycle-manifest.json"),
            mock.patch.object(module, "MD_REPORT", tmp / "db-lifecycle-manifest.md"),
            mock.patch.object(module, "ARCHIVE_APPROVAL_PACKET", tmp / "db-lifecycle-archive-approval-packet.json"),
        ):
            manifest = module.build_manifest()
            errors = module.validate_manifest(manifest)
            gc.collect()

    assert errors == []
    entries = {entry["basename"]: entry for entry in manifest["entries"]}
    for name in (
        "retrieval-live-eval-hash.sqlite",
        "retrieval-live-eval-semantic.sqlite",
        "retrieval-live-eval-mutation.sqlite",
    ):
        assert entries[name]["lifecycle"] == "derived"
        assert entries[name]["status"] == "keep"
        assert entries[name]["archive_ready"] is False
        assert entries[name]["delete_ready"] is False


def test_reference_corpus_uses_bounded_roots_and_skips_heavy_dirs() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        scripts = root / "scripts"
        tmp = root / "tmp"
        wiki = root / "wiki"
        heavy = root / "node_modules" / "pkg"
        nested_other = root / "other"
        scripts.mkdir(parents=True)
        wiki.mkdir(parents=True)
        heavy.mkdir(parents=True)
        nested_other.mkdir(parents=True)
        (scripts / "owner.py").write_text("workspace-index.sqlite", encoding="utf-8")
        (wiki / "page.md").write_text("workspace-index.sqlite", encoding="utf-8")
        (root / "README.md").write_text("workspace-index.sqlite", encoding="utf-8")
        (heavy / "ignored.json").write_text("workspace-index.sqlite", encoding="utf-8")
        (nested_other / "ignored.md").write_text("workspace-index.sqlite", encoding="utf-8")
        tmp.mkdir(parents=True)
        (tmp / "ignored-proof.json").write_text("workspace-index.sqlite", encoding="utf-8")
        (tmp / "oversized.json").write_text(
            "workspace-index.sqlite" + ("x" * module.MAX_REFERENCE_TEXT_BYTES),
            encoding="utf-8",
        )

        with mock.patch.object(module, "ROOT", root):
            paths = {path.relative_to(root).as_posix() for path in module.iter_text_files()}
            corpus_paths = {path.relative_to(root).as_posix() for path, _ in module.text_corpus()}

    assert "scripts/owner.py" in paths
    assert "wiki/page.md" in paths
    assert "README.md" in paths
    assert "tmp/ignored-proof.json" not in paths
    assert "node_modules/pkg/ignored.json" not in paths
    assert "other/ignored.md" not in paths
    assert "tmp/oversized.json" not in corpus_paths


def test_sqlite_probe_uses_bounded_large_db_checks() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "large.sqlite"
        create_sqlite(db)
        with (
            mock.patch.object(module, "FULL_INTEGRITY_MAX_BYTES", 1),
            mock.patch.object(module, "TABLE_ROW_COUNT_MAX_BYTES", 1),
        ):
            probe = module.sqlite_probe(db)
            gc.collect()

    assert probe["open_status"] == "ok"
    assert probe["integrity_check"] == "not_run"
    assert probe["integrity_check_mode"] == "skipped_large_db_guard"
    proof_table = next(row for row in probe["tables"] if row["name"] == "proof")
    assert proof_table["row_count"] is None
    assert proof_table["row_count_skipped_reason"] == "large_db_guard"
