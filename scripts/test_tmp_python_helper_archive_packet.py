from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tmp_python_helper_archive_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("tmp_python_helper_archive_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_workspace(root: Path, module):
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "tmp-python-helper-archive-packet.json"
    module.TMP.mkdir(parents=True, exist_ok=True)
    helper = module.TMP / "_scratch.py"
    helper.write_text("print('scratch')\n", encoding="utf-8")
    return helper


def test_packet_marks_unreferenced_tmp_helper_owner_ready() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        helper = seed_workspace(Path(tmpdir), module)

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["status"] == "owner_approval_ready_no_archive_performed"
        assert packet["summary"]["tmp_python_helper_count"] == 1
        assert packet["summary"]["archive_ready_after_owner_approval_count"] == 1
        row = packet["microbatch"]["rows"][0]
        assert row["path"] == "tmp/_scratch.py"
        assert row["sha256"] == module.file_sha256(helper)
        assert row["archive_ready_after_owner_approval"] is True
        assert "Approve tmp Python helper archive microbatch" in packet["summary"]["approval_phrase"]


def test_packet_blocks_helper_with_active_reference() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        scripts = root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "consumer.py").write_text("TARGET = 'tmp/_scratch.py'\n", encoding="utf-8")

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["status"] == "promotion_or_reference_review_required"
        assert packet["summary"]["archive_ready_after_owner_approval_count"] == 0
        assert packet["summary"]["promotion_or_reference_review_count"] == 1
        blocked = packet["blocked_or_promote_first_rows"][0]
        assert blocked["durable_promotion_recommended"] is True
        assert blocked["active_reference_count"] == 1


if __name__ == "__main__":
    test_packet_marks_unreferenced_tmp_helper_owner_ready()
    test_packet_blocks_helper_with_active_reference()
    print("tmp python helper archive packet tests passed")
