from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "backup_rollback_delete_prep_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("backup_rollback_delete_prep_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_workspace(root: Path) -> None:
    backups = root / "backups" / "finance-sql-canon-migration"
    backups.mkdir(parents=True)
    db_path = backups / "finance-canon.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("create table proof(id integer primary key, value text)")
        connection.execute("insert into proof(value) values ('ok')")
        connection.commit()
    finally:
        connection.close()

    rollback = root / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-full-approved"
    rollback.mkdir(parents=True)
    (rollback / "cache.bin").write_bytes(b"rollback")

    tmp = root / "tmp"
    tmp.mkdir(parents=True)
    (tmp / "db-lifecycle-manifest.json").write_text(
        json.dumps(
            {
                "status": "validation_error",
                "generated_at_utc": "2026-07-05T00:00:00Z",
                "summary": {"delete_ready_count": 0, "archive_ready_count": 0, "unknown_count": 1},
                "validation_errors": ["example unknown"],
            }
        ),
        encoding="utf-8",
    )
    state = root / "state"
    (state / "tmp-lifecycle-deletion-tombstone.json").write_text(
        json.dumps({"schema_version": 1, "deleted_records": [], "runs": [], "events": []}),
        encoding="utf-8",
    )


def test_packet_marks_rollbacks_owner_ready_and_backups_blocked() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        seed_workspace(workspace)

        packet = module.build_packet(
            workspace_root=workspace,
            generated_at_utc="2026-07-05T23:00:00Z",
            include_sqlite_checks=True,
        )

        assert packet["validation"]["status"] == "ok"
        assert packet["status"] == "owner_approval_ready_for_rollback_only_backups_blocked"
        assert packet["summary"]["backup_owner_ready_delete_bytes"] == 0
        assert packet["summary"]["rollback_owner_ready_delete_bytes"] > 0
        assert packet["backup_retention_review"]["delete_ready_after_owner_approval"] is False
        assert packet["rollback_delete_microbatch"]["delete_ready_after_owner_approval"] is True
        assert packet["rollback_delete_microbatch"]["approval_phrase"].startswith(
            "Approve tmp lifecycle rollback delete microbatch "
        )


def test_packet_does_not_mutate_sources() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        seed_workspace(workspace)
        rollback_file = workspace / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-full-approved" / "cache.bin"
        before = rollback_file.read_bytes()

        packet = module.build_packet(
            workspace_root=workspace,
            generated_at_utc="2026-07-05T23:00:00Z",
            include_sqlite_checks=True,
        )

        assert rollback_file.exists()
        assert rollback_file.read_bytes() == before
        assert packet["authority_boundary"]["delete_performed"] is False
        assert packet["authority_boundary"]["archive_performed"] is False
        assert packet["authority_boundary"]["move_performed"] is False
        assert packet["authority_boundary"]["sqlite_write_performed"] is False


def test_backup_rows_are_never_owner_ready_in_this_packet() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        seed_workspace(workspace)

        packet = module.build_packet(
            workspace_root=workspace,
            generated_at_utc="2026-07-05T23:00:00Z",
            include_sqlite_checks=True,
        )

        rows = packet["backup_retention_review"]["rows"]
        assert rows
        assert all(row["delete_ready_after_owner_approval"] is False for row in rows)
        assert all(row["blocked_reason"] == "backup_retention_and_restore_proof_required" for row in rows)
        assert packet["backup_retention_review"]["approval_phrase"] is None


if __name__ == "__main__":
    test_packet_marks_rollbacks_owner_ready_and_backups_blocked()
    test_packet_does_not_mutate_sources()
    test_backup_rows_are_never_owner_ready_in_this_packet()
    print("backup rollback delete prep packet tests passed")
