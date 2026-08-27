from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "orphan_transcript_inventory_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("orphan_transcript_inventory_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_openclaw_home(root: Path) -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    sessions_root = root / "agents" / "main" / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    (sessions_root / "active-session.jsonl").write_text('{"active": true}\n', encoding="utf-8")
    (sessions_root / "orphan-session.jsonl").write_text('{"orphan": true}\n', encoding="utf-8")
    (sessions_root / "orphan-session.trajectory.jsonl").write_text('{"trajectory": true}\n', encoding="utf-8")
    (sessions_root / "old-session.jsonl.deleted.20260705T000000Z").write_text('{"deleted": true}\n', encoding="utf-8")
    sessions_index = sessions_root / "sessions.json"
    sessions_index.write_text(
        json.dumps({"agent:main:dashboard:active-session": {"path": "active-session.jsonl"}}),
        encoding="utf-8",
    )
    return workspace, root, sessions_root


def test_packet_inventories_only_unreferenced_bare_transcripts() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace, openclaw_home, sessions_root = seed_openclaw_home(Path(tmpdir))

        packet = module.build_packet(
            workspace_root=workspace,
            openclaw_home=openclaw_home,
            sessions_root=sessions_root,
            security_ledger=None,
            generated_at_utc="2026-07-05T22:00:00Z",
            archive_stamp="20260705T220000Z",
        )

        assert packet["validation"]["status"] == "ok"
        assert packet["status"] == "owner_approval_ready_no_archive_performed"
        assert packet["summary"]["orphan_transcript_count"] == 1
        row = packet["microbatch"]["rows"][0]
        assert row["path"] == "agents/main/sessions/orphan-session.jsonl"
        assert row["proposed_archive_path"].endswith(".jsonl.deleted.20260705T220000Z")
        assert row["sha256"] == module.file_sha256(sessions_root / "orphan-session.jsonl")
        assert "active-session" not in json.dumps(packet["microbatch"]["rows"])


def test_packet_contains_no_content_preview_keys_and_does_not_mutate_sources() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace, openclaw_home, sessions_root = seed_openclaw_home(Path(tmpdir))
        source = sessions_root / "orphan-session.jsonl"
        before = source.read_bytes()

        packet = module.build_packet(
            workspace_root=workspace,
            openclaw_home=openclaw_home,
            sessions_root=sessions_root,
            security_ledger=None,
            generated_at_utc="2026-07-05T22:00:00Z",
            archive_stamp="20260705T220000Z",
        )

        assert module.has_forbidden_content_key(packet) == []
        assert source.exists()
        assert source.read_bytes() == before
        assert packet["authority_boundary"]["archive_performed"] is False
        assert packet["authority_boundary"]["rename_performed"] is False
        assert packet["authority_boundary"]["delete_performed"] is False


def test_security_ledger_count_drift_is_warning_not_blocker() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        workspace, openclaw_home, sessions_root = seed_openclaw_home(root)
        ledger = workspace / "tmp" / "security-warning-ledger.json"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(
            json.dumps(
                {
                    "generated_at_utc": "2026-07-05T21:00:00Z",
                    "status": "warning",
                    "warnings": [{"message": "Doctor found 214 orphan transcript files."}],
                }
            ),
            encoding="utf-8",
        )

        packet = module.build_packet(
            workspace_root=workspace,
            openclaw_home=openclaw_home,
            sessions_root=sessions_root,
            security_ledger=ledger,
            generated_at_utc="2026-07-05T22:00:00Z",
            archive_stamp="20260705T220000Z",
        )

        assert packet["validation"]["status"] == "ok"
        assert packet["validation"]["warnings"] == ["security_ledger_count_drift:214!=1"]


def test_incidental_uuid_string_does_not_mark_transcript_referenced() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        workspace, openclaw_home, sessions_root = seed_openclaw_home(root)
        sessions_index = sessions_root / "sessions.json"
        sessions_index.write_text(
            json.dumps(
                {
                    "agent:main:dashboard:active-session": {
                        "sessionId": "active-session",
                        "sessionFile": str(sessions_root / "active-session.jsonl"),
                        "childIds": ["orphan-session"],
                    }
                }
            ),
            encoding="utf-8",
        )

        packet = module.build_packet(
            workspace_root=workspace,
            openclaw_home=openclaw_home,
            sessions_root=sessions_root,
            security_ledger=None,
            generated_at_utc="2026-07-05T22:00:00Z",
            archive_stamp="20260705T220000Z",
        )

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["orphan_transcript_count"] == 1
        assert packet["microbatch"]["rows"][0]["path"] == "agents/main/sessions/orphan-session.jsonl"


if __name__ == "__main__":
    test_packet_inventories_only_unreferenced_bare_transcripts()
    test_packet_contains_no_content_preview_keys_and_does_not_mutate_sources()
    test_security_ledger_count_drift_is_warning_not_blocker()
    test_incidental_uuid_string_does_not_mark_transcript_referenced()
    print("orphan transcript inventory packet tests passed")
