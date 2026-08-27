from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_script_cleanup_inventory.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_script_cleanup_inventory", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.ROUTE_CONTRACTION = module.TMP / "wf88-route-contraction-packet.json"
    module.GPT55_REVIEW = module.TMP / "wf88-script-cleanup-reference-graph-gpt55.md"
    module.GPT54_REVIEW = module.TMP / "wf88-deprecated-script-risk-gpt54.md"
    module.OUT = module.TMP / "wf88-script-cleanup-inventory.json"
    module.MD_OUT = module.TMP / "wf88-script-cleanup-inventory.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    for file_path in sorted(module.KEEP_CORE | module.MIGRATION_MODE):
        path = root / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# placeholder\n", encoding="utf-8")

    write_json(module.ROUTE_CONTRACTION, {
        "schema": "veritas.wf88_route_contraction_packet.v1",
        "status": "route_contraction_dry_run_ready_no_delete_authority",
        "generated_at_utc": module.utc_now(),
        "route_contraction_files": [
            {
                "path": "scripts/ticker_answer_packet.py",
                "exists": True,
                "sha256": "abc",
                "status": "contracted_or_already_narrowed",
                "active_reference_count": 2,
                "active_reference_sample": [
                    "scripts/ticker_answer_packet_retirement_plan.py",
                    "tmp/validator-bundle-router.json",
                ],
            },
            {
                "path": "scripts/workflow_router.py",
                "exists": True,
                "sha256": "def",
                "status": "contracted_or_already_narrowed",
                "active_reference_count": 1,
                "active_reference_sample": ["scripts/wf88_route_contraction_packet.py"],
            },
        ],
    })
    module.GPT55_REVIEW.write_text("Script deletion is not safe now.\n", encoding="utf-8")
    module.GPT54_REVIEW.write_text("Deprecated script deletion is not safe now.\n", encoding="utf-8")


def test_script_cleanup_inventory_blocks_script_deletion() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["candidate_script_count"] == 2
        assert packet["summary"]["delete_candidate_count"] == 0
        assert packet["summary"]["script_deletion_ready_now_count"] == 0
        assert packet["summary"]["helper_consensus_script_deletion_not_safe_now"] is True
        rows = {row["path"]: row for row in packet["script_cleanup_inventory"]}
        assert rows["scripts/ticker_answer_packet.py"]["cleanup_category"] == "migration_mode"
        assert rows["scripts/workflow_router.py"]["cleanup_category"] == "keep"
        assert all(row["delete_allowed_now"] is False for row in rows.values())
        assert all(row["archive_allowed_now"] is False for row in rows.values())


if __name__ == "__main__":
    test_script_cleanup_inventory_blocks_script_deletion()
    print("wf88 script cleanup inventory tests passed")
