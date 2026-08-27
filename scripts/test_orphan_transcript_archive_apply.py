from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPLY_SCRIPT = ROOT / "scripts" / "orphan_transcript_archive_apply.py"
INVENTORY_SCRIPT = ROOT / "scripts" / "orphan_transcript_inventory_packet.py"


def load_module(path: Path, name: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_packet(root: Path) -> tuple[Path, Path, str]:
    inventory = load_module(INVENTORY_SCRIPT, "orphan_transcript_inventory_packet_for_apply_tests")
    workspace = root / "workspace"
    sessions_root = root / "agents" / "main" / "sessions"
    workspace.mkdir(parents=True, exist_ok=True)
    sessions_root.mkdir(parents=True, exist_ok=True)
    source = sessions_root / "orphan-session.jsonl"
    source.write_bytes(b'{"orphan": true}\n')
    (sessions_root / "active-session.jsonl").write_bytes(b'{"active": true}\n')
    (sessions_root / "sessions.json").write_text(
        json.dumps({"agent:main:active": {"sessionFile": "active-session.jsonl"}}),
        encoding="utf-8",
    )
    packet = inventory.build_packet(
        workspace_root=workspace,
        openclaw_home=root,
        sessions_root=sessions_root,
        security_ledger=None,
        generated_at_utc="2026-07-05T22:00:00Z",
        archive_stamp="20260705T220000Z",
    )
    packet_path = workspace / "tmp" / "orphan-transcript-inventory-packet.json"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    return packet_path, source, packet["summary"]["approval_phrase"]


def test_dry_run_does_not_rename_source() -> None:
    apply_module = load_module(APPLY_SCRIPT, "orphan_transcript_archive_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        packet_path, source, phrase = seed_packet(Path(tmpdir))
        report = apply_module.build_report(packet_path=packet_path, approval_phrase=phrase, apply=False)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert source.exists()
        assert not Path(report["dry_run_rows"][0]["proposed_archive_path"]).is_absolute()
        assert report["authority_boundary"]["content_preview_performed"] is False
        assert report["authority_boundary"]["delete_performed"] is False


def test_apply_exact_phrase_renames_without_delete_or_content_preview() -> None:
    apply_module = load_module(APPLY_SCRIPT, "orphan_transcript_archive_apply_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        packet_path, source, phrase = seed_packet(Path(tmpdir))
        report = apply_module.build_report(packet_path=packet_path, approval_phrase=phrase, apply=True)

        archived = report["archived_rows"][0]
        archive = Path(tmpdir) / archived["archive_path"]
        assert report["validation"]["status"] == "ok"
        assert report["status"] == "applied_orphan_transcript_archive"
        assert not source.exists()
        assert archive.exists()
        assert apply_module.file_sha256(archive) == archived["sha256"]
        assert report["authority_boundary"]["rename_performed"] is True
        assert report["authority_boundary"]["delete_performed"] is False
        assert report["authority_boundary"]["content_preview_performed"] is False
        assert report["authority_boundary"]["sessions_index_mutation_performed"] is False


def test_wrong_approval_phrase_blocks_apply() -> None:
    apply_module = load_module(APPLY_SCRIPT, "orphan_transcript_archive_apply_wrong_phrase")
    with tempfile.TemporaryDirectory() as tmpdir:
        packet_path, source, _phrase = seed_packet(Path(tmpdir))
        report = apply_module.build_report(packet_path=packet_path, approval_phrase="wrong", apply=True)

        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert source.exists()


def test_existing_archive_target_blocks_apply() -> None:
    apply_module = load_module(APPLY_SCRIPT, "orphan_transcript_archive_apply_existing_target")
    with tempfile.TemporaryDirectory() as tmpdir:
        packet_path, source, phrase = seed_packet(Path(tmpdir))
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        archive = Path(tmpdir) / packet["microbatch"]["rows"][0]["proposed_archive_path"]
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"already here")

        report = apply_module.build_report(packet_path=packet_path, approval_phrase=phrase, apply=True)

        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("archive_target_exists:") for error in report["validation"]["errors"])
        assert source.exists()


if __name__ == "__main__":
    test_dry_run_does_not_rename_source()
    test_apply_exact_phrase_renames_without_delete_or_content_preview()
    test_wrong_approval_phrase_blocks_apply()
    test_existing_archive_target_blocks_apply()
    print("orphan transcript archive apply tests passed")
