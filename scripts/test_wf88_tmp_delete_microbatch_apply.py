from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_tmp_delete_microbatch_apply.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_tmp_delete_microbatch_apply", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> tuple[Path, Path]:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.STATE = root / "state"
    module.READINESS_PACKET = module.TMP / "wf88-delete-readiness-packet.json"
    module.APPLY_REPORT = module.TMP / "wf88-delete-microbatch-apply-report.json"
    module.ROLLBACK_ROOT = module.STATE / "tmp-lifecycle-rollback" / "wf88-tmp-delete-microbatch"
    first = module.TMP / "wf38-fixtures" / "passing_packet.json"
    second = module.TMP / "audio-tools" / "node_modules" / "sharp" / "vendor" / "8.14.5" / "win32-x64" / "platform.json"
    first.parent.mkdir(parents=True, exist_ok=True)
    second.parent.mkdir(parents=True, exist_ok=True)
    first.write_text('{"event": true}', encoding="utf-8")
    second.write_text('{"fresh": true}', encoding="utf-8")
    write_json(
        module.READINESS_PACKET,
        {
            "schema": "veritas.wf88_delete_readiness_packet.v1",
            "status": "owner_ready_microbatches_no_apply",
            "tmp_delete_microbatch": {
                "rows": [
                    {
                        "path": "tmp/wf38-fixtures/passing_packet.json",
                        "exists": True,
                        "size_bytes": first.stat().st_size,
                        "sha256": module.file_sha256(first),
                        "active_reference_count": 0,
                        "protected_reasons": [],
                        "delete_ready_after_owner_approval": True,
                    },
                    {
                        "path": "tmp/audio-tools/node_modules/sharp/vendor/8.14.5/win32-x64/platform.json",
                        "exists": True,
                        "size_bytes": second.stat().st_size,
                        "sha256": module.file_sha256(second),
                        "active_reference_count": 0,
                        "protected_reasons": [],
                        "delete_ready_after_owner_approval": True,
                    },
                ],
            },
        },
    )
    return first, second


def test_dry_run_does_not_delete() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        first, second = seed_workspace(Path(tmpdir), module)

        report = module.build_report(apply=False, approval_phrase=None)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert report["summary"]["candidate_count"] == 2
        assert first.exists()
        assert second.exists()


def test_apply_requires_exact_phrase() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        first, second = seed_workspace(Path(tmpdir), module)

        report = module.build_report(apply=True, approval_phrase="wrong")

        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert first.exists()
        assert second.exists()


def test_apply_deletes_only_after_rollback_copy() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        first, second = seed_workspace(root, module)

        report = module.build_report(apply=True, approval_phrase=module.APPROVAL_PHRASE)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "applied_wf88_tmp_delete_microbatch"
        assert report["summary"]["deleted_count"] == 2
        assert not first.exists()
        assert not second.exists()
        for record in report["deleted_records"]:
            rollback = root / record["rollback_copy"]
            assert rollback.exists()
            assert module.file_sha256(rollback) == record["sha256"]


def test_hash_mismatch_blocks_apply() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        first, second = seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.READINESS_PACKET.read_text(encoding="utf-8"))
        payload["tmp_delete_microbatch"]["rows"][0]["sha256"] = "bad"
        write_json(module.READINESS_PACKET, payload)

        report = module.build_report(apply=True, approval_phrase=module.APPROVAL_PHRASE)

        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("sha256_mismatch:") for error in report["validation"]["errors"])
        assert first.exists()
        assert second.exists()


def test_non_tmp_path_blocks_apply() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        first, second = seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.READINESS_PACKET.read_text(encoding="utf-8"))
        payload["tmp_delete_microbatch"]["rows"][0]["path"] = "state/not-tmp.json"
        write_json(module.READINESS_PACKET, payload)

        report = module.build_report(apply=True, approval_phrase=module.APPROVAL_PHRASE)

        assert report["validation"]["status"] == "blocked"
        assert "path_not_in_approved_tmp_scope:state/not-tmp.json" in report["validation"]["errors"]
        assert first.exists()
        assert second.exists()


if __name__ == "__main__":
    test_dry_run_does_not_delete()
    test_apply_requires_exact_phrase()
    test_apply_deletes_only_after_rollback_copy()
    test_hash_mismatch_blocks_apply()
    test_non_tmp_path_blocks_apply()
    print("wf88 tmp delete microbatch apply tests passed")
