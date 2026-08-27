from __future__ import annotations

import tempfile
from pathlib import Path

import wf88_cleanup_common as common


def test_reference_category_shared_for_inventory_and_typed_graph() -> None:
    assert common.wf88_reference_category("scripts/consumer.py") == "active_code_or_control_consumer"
    assert common.wf88_reference_category("scripts/wf88_script_cleanup_inventory.py", typed_graph=True) == "cleanup_or_migration_control"
    assert common.wf88_reference_category("tmp/wf88-proof.json", typed_graph=True) == "generated_tmp_proof"
    assert common.wf88_reference_need("active_code_or_control_consumer") == "must_replace_before_delete"


def test_file_sha256_and_input_record() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        path = root / "tmp" / "packet.json"
        path.parent.mkdir(parents=True)
        path.write_text("{}", encoding="utf-8")
        record = common.input_record(path, {"schema": "example", "status": "ok"}, root=root, required=True)

    assert record["path"] == "tmp/packet.json"
    assert record["present"] is True
    assert record["required"] is True
    assert record["schema"] == "example"
    assert len(str(record["sha256"])) == 64


def test_sqlite_sidecar_helpers_find_orphans() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        state = root / "state"
        tmp.mkdir()
        state.mkdir()
        db = tmp / "live.sqlite"
        db.write_text("", encoding="utf-8")
        attached = tmp / "live.sqlite-wal"
        attached.write_text("wal", encoding="utf-8")
        orphan = state / "orphan.db-shm"
        orphan.write_text("shm", encoding="utf-8")

        dbs = common.iter_sqlite_db_files([tmp, state], root=root)
        orphans = common.iter_orphan_sqlite_sidecars([tmp, state], db_files=dbs, root=root)

    assert common.is_sqlite_sidecar(attached)
    assert common.sqlite_sidecar_kind(orphan) == "shm"
    assert common.rel(common.sqlite_parent_for_sidecar(orphan), root) == "state/orphan.db"
    assert [common.rel(path, root) for path in dbs] == ["tmp/live.sqlite"]
    assert [common.rel(path, root) for path in orphans] == ["state/orphan.db-shm"]
