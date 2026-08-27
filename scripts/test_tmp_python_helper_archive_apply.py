from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET_SCRIPT = ROOT / "scripts" / "tmp_python_helper_archive_packet.py"
APPLY_SCRIPT = ROOT / "scripts" / "tmp_python_helper_archive_apply.py"


def load_module(name: str, path: Path):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path):
    packet_module = load_module("tmp_python_helper_archive_packet", PACKET_SCRIPT)
    apply_module = load_module("tmp_python_helper_archive_apply", APPLY_SCRIPT)
    packet_module.ROOT = root
    packet_module.TMP = root / "tmp"
    packet_module.OUT = packet_module.TMP / "tmp-python-helper-archive-packet.json"
    apply_module.ROOT = root
    apply_module.TMP = root / "tmp"
    apply_module.PACKET = apply_module.TMP / "tmp-python-helper-archive-packet.json"
    apply_module.APPLY_REPORT = apply_module.TMP / "tmp-python-helper-archive-apply-report.json"
    apply_module.ARCHIVE_ROOT = root / "09. Archive" / "tmp-python-helpers - Archived"
    apply_module.TMP.mkdir(parents=True, exist_ok=True)
    helper = apply_module.TMP / "_scratch.py"
    helper.write_text("print('scratch')\n", encoding="utf-8")
    packet = packet_module.build_packet()
    write_json(apply_module.PACKET, packet)
    return packet_module, apply_module, helper, packet


def test_dry_run_does_not_archive() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        _packet_module, apply_module, helper, _packet = seed_workspace(Path(tmpdir))

        report = apply_module.build_report(apply=False, approval_phrase=None)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert report["summary"]["candidate_count"] == 1
        assert helper.exists()
        assert not apply_module.ARCHIVE_ROOT.exists()


def test_apply_requires_exact_phrase() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        _packet_module, apply_module, helper, _packet = seed_workspace(Path(tmpdir))

        report = apply_module.build_report(apply=True, approval_phrase="wrong")

        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert helper.exists()


def test_apply_archives_after_hash_verified() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _packet_module, apply_module, helper, packet = seed_workspace(root)

        report = apply_module.build_report(apply=True, approval_phrase=packet["summary"]["approval_phrase"])

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "applied_tmp_python_helper_archive"
        assert report["summary"]["archived_count"] == 1
        assert not helper.exists()
        archived = root / report["archived_records"][0]["archive_copy"]
        assert archived.exists()
        assert apply_module.file_sha256(archived) == report["archived_records"][0]["sha256"]


def test_hash_mismatch_blocks_apply() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        _packet_module, apply_module, helper, packet = seed_workspace(Path(tmpdir))
        payload = json.loads(apply_module.PACKET.read_text(encoding="utf-8"))
        payload["microbatch"]["rows"][0]["sha256"] = "bad"
        payload["microbatch"]["digest"] = apply_module.microbatch_digest(payload["microbatch"]["rows"])
        payload["summary"]["microbatch_digest"] = payload["microbatch"]["digest"]
        write_json(apply_module.PACKET, payload)

        report = apply_module.build_report(apply=True, approval_phrase=packet["summary"]["approval_phrase"])

        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("sha256_mismatch:") for error in report["validation"]["errors"])
        assert helper.exists()


def test_non_root_tmp_path_blocks_apply() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        _packet_module, apply_module, helper, packet = seed_workspace(Path(tmpdir))
        payload = json.loads(apply_module.PACKET.read_text(encoding="utf-8"))
        payload["microbatch"]["rows"][0]["path"] = "tmp/nested/_scratch.py"
        payload["microbatch"]["digest"] = apply_module.microbatch_digest(payload["microbatch"]["rows"])
        payload["summary"]["microbatch_digest"] = payload["microbatch"]["digest"]
        write_json(apply_module.PACKET, payload)

        report = apply_module.build_report(apply=True, approval_phrase=packet["summary"]["approval_phrase"])

        assert report["validation"]["status"] == "blocked"
        assert "path_not_root_tmp_python_helper:tmp/nested/_scratch.py" in report["validation"]["errors"]
        assert helper.exists()


if __name__ == "__main__":
    test_dry_run_does_not_archive()
    test_apply_requires_exact_phrase()
    test_apply_archives_after_hash_verified()
    test_hash_mismatch_blocks_apply()
    test_non_root_tmp_path_blocks_apply()
    print("tmp python helper archive apply tests passed")
