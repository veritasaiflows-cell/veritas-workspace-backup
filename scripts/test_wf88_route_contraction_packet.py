from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_route_contraction_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_route_contraction_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.CLEANUP_PLAN = module.TMP / "wf88-retired-surface-cleanup-plan.json"
    module.OS2_CONTROL_PACKET = module.TMP / "wf88-os2-control-packet.json"
    module.ROUTING_INDEX = module.TMP / "workflow-routing-index.json"
    module.OUT = module.TMP / "wf88-route-contraction-packet.json"
    module.MD_OUT = module.TMP / "wf88-route-contraction-packet.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    exact_files = sorted(module.EXPECTED_MARKERS)
    rows = []
    for file_path in exact_files:
        write_text(root / file_path, "\n".join(module.EXPECTED_MARKERS[file_path]))
        rows.append({
            "item": file_path,
            "classification": "test_contraction",
            "route_or_script_files": [file_path],
            "target_reference_proof": {
                file_path: {
                    "active_reference_count": 1,
                    "active_reference_sample": ["scripts/test_reference.py"],
                },
            },
            "post_contraction_validators": ["python -m py_compile <touched script files>"],
            "delete_allowed_now": False,
            "archive_allowed_now": False,
        })
    cleanup_authority = {
        "review_only": True,
        "proposal_only": True,
        "delete_allowed": False,
        "archive_allowed": False,
        "move_allowed": False,
        "apply_allowed": False,
        "cron_schedule_mutation_allowed": False,
    }
    write_json(module.CLEANUP_PLAN, {
        "status": "proposal_ready_no_apply_authority",
        "authority_boundary": cleanup_authority,
        "summary": {
            "delete_allowed_now_count": 0,
            "archive_allowed_now_count": 0,
            "tmp_cleanup_preview_eligible_count": 9,
            "first_tmp_microbatch_candidate_count": 2,
            "db_archive_candidate_count": 1,
            "cron_packet_status": "packet_needed_no_cron_mutation",
        },
        "lanes": {
            "tmp_delete_proposal": {"status": "proposal_ready"},
            "script_route_contraction": {
                "status": "route_contraction_preflight_ready",
                "delete_allowed_now": False,
                "archive_allowed_now": False,
                "exact_files_for_next_route_contraction": exact_files,
                "rows": rows,
            },
            "db_lifecycle_microbatch": {"status": "owner_packet_needed"},
            "cron_retired_job_packet": {"status": "packet_needed"},
        },
    })
    write_json(module.OS2_CONTROL_PACKET, {"status": "control_packet_ready_no_apply_authority"})
    write_json(module.ROUTING_INDEX, {
        "status": "ok",
        "routes": [
            {
                "workflow_id": "WF87",
                "primary_route_artifact": "tmp/wf87-paper-autonomy-runtime-governor.json",
                "secondary_artifacts": [],
            },
            {
                "workflow_id": "WF88",
                "primary_route_artifact": "tmp/wf88-os2-control-packet.json",
                "secondary_artifacts": ["tmp/wf88-route-contraction-packet.json"],
            },
        ],
    })


def test_route_contraction_packet_never_grants_destructive_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["contracted_or_already_narrowed_count"] == len(module.EXPECTED_MARKERS)
        assert packet["summary"]["script_deletion_ready_now_count"] == 0
        assert packet["authority_boundary"]["delete_allowed"] is False
        assert packet["authority_boundary"]["archive_allowed"] is False
        assert packet["authority_boundary"]["apply_allowed"] is False
        assert packet["retirement_readiness"]["ready_for_destructive_apply"] is False


if __name__ == "__main__":
    test_route_contraction_packet_never_grants_destructive_authority()
    print("wf88 route contraction packet tests passed")
