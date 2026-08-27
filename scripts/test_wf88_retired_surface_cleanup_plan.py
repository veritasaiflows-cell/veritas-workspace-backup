from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_retired_surface_cleanup_plan.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_retired_surface_cleanup_plan", SCRIPT)
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
    module.TMP_LIFECYCLE = module.TMP / "tmp-lifecycle-guard.json"
    module.HUMAN_RETIREMENT = module.TMP / "human-canon-thinning-retirement-inventory.json"
    module.DB_LIFECYCLE = module.TMP / "db-lifecycle-manifest.json"
    module.WORKFLOW_ROUTING = module.TMP / "workflow-routing-index.json"
    module.ARTIFACT_INDEX_DB = module.TMP / "veritas-artifact-index.sqlite"
    module.OUT = module.TMP / "wf88-retired-surface-cleanup-plan.json"
    module.MD_OUT = module.TMP / "wf88-retired-surface-cleanup-plan.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    write_json(module.TMP_LIFECYCLE, {
        "schema": "veritas.tmp_lifecycle_guard.v1",
        "generated_at_utc": "2026-06-27T00:00:00Z",
        "status": "warning",
        "summary": {"cleanup_preview_eligible_count": 2},
        "cleanup_preview_samples": [
            {
                "path": "tmp/research-automation/old-sample.json",
                "suffix": ".json",
                "size_bytes": 120,
                "last_write_utc": "2026-05-01T00:00:00Z",
                "age_days": 50,
                "cleanup_preview_eligible": True,
                "protected_reasons": [],
            },
            {
                "path": "tmp/wf85-decision-os-review-packet.json",
                "suffix": ".json",
                "size_bytes": 120,
                "last_write_utc": "2026-05-01T00:00:00Z",
                "age_days": 50,
                "cleanup_preview_eligible": True,
                "protected_reasons": [],
            },
        ],
    })
    (module.TMP / "research-automation").mkdir()
    (module.TMP / "research-automation" / "old-sample.json").write_text("{}", encoding="utf-8")
    (module.TMP / "wf85-decision-os-review-packet.json").write_text("{}", encoding="utf-8")

    write_json(module.HUMAN_RETIREMENT, {
        "schema": "veritas.human_canon_thinning_retirement_inventory.v1",
        "generated_at_utc": "2026-06-27T00:00:00Z",
        "status": "ok",
        "summary": {"archive_or_delete_candidates_ready_now": 0, "cron_schedule_mutation_ready_now": 0},
        "categories": {
            "keep": [],
            "narrow_on_demand": [
                {
                    "path": "scripts/ticker_answer_packet.py",
                    "classification": "legacy_compatibility_wrapper",
                    "reason": "Keep compatibility-only.",
                }
            ],
            "retire_candidate": [
                {
                    "path": "runtime_performance_scorecard.py:default_human_note_parity_commands",
                    "classification": "broad_runtime_cost",
                    "reason": "Move out of default scoring.",
                }
            ],
            "do_not_retire": [],
        },
    })
    scripts_dir = root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "ticker_answer_packet.py").write_text("# compatibility\n", encoding="utf-8")
    (scripts_dir / "runtime_performance_scorecard.py").write_text("# scorecard\n", encoding="utf-8")

    write_json(module.DB_LIFECYCLE, {
        "generated_at_utc": "2026-06-27T00:00:00Z",
        "status": "ready_for_owner_decision",
        "summary": {"archive_candidate_count": 1, "archive_approval_packet": "tmp/db-lifecycle-archive-approval-packet.json"},
        "recommended_owner_decision": {"archive_now_after_approval": ["tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite"]},
        "entries": [
            {
                "path": "tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite",
                "owner": "WF72 rollback drill proof",
                "status": "archive_ready",
                "archive_ready": True,
                "delete_ready": False,
                "size_bytes": 10,
                "sha256": "abc",
            }
        ],
    })
    write_json(module.WORKFLOW_ROUTING, {
        "schema_version": "workflow_routing_index.v1",
        "generated_at_utc": "2026-06-27T00:00:00Z",
        "routes": [{"workflow_id": "WF88", "next_action": "cleanup plan"}],
    })


def test_plan_has_four_lanes_and_no_cleanup_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        plan = module.build_plan()
        validation = plan["validation"]

        assert validation["status"] == "ok"
        assert set(plan["lanes"]) == {
            "tmp_delete_proposal",
            "script_route_contraction",
            "db_lifecycle_microbatch",
            "cron_retired_job_packet",
        }
        assert plan["authority_boundary"]["delete_allowed"] is False
        assert plan["authority_boundary"]["archive_allowed"] is False
        assert plan["authority_boundary"]["apply_allowed"] is False
        assert plan["summary"]["delete_allowed_now_count"] == 0
        assert plan["summary"]["archive_allowed_now_count"] == 0


def test_plan_surfaces_first_tmp_batch_and_route_contraction_files() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        plan = module.build_plan()

        first_batch = plan["lanes"]["tmp_delete_proposal"]["first_small_safe_proposal_batch"]
        assert first_batch["candidate_count"] == 1
        assert first_batch["rows"][0]["path"] == "tmp/research-automation/old-sample.json"
        assert first_batch["rows"][0]["delete_allowed_now"] is False

        script_lane = plan["lanes"]["script_route_contraction"]
        files = set(script_lane["exact_files_for_next_route_contraction"])
        assert "scripts/ticker_answer_packet.py" in files
        assert "scripts/runtime_performance_scorecard.py" in files
        assert script_lane["delete_allowed_now"] is False


def test_rebuildable_research_sample_inputs_can_enter_tmp_batch() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        root = Path(tmpdir)
        raw = root / "tmp" / "research-automation" / "raw-events.json"
        raw.write_text("[]", encoding="utf-8")
        scripts_dir = root / "scripts"
        (scripts_dir / "research_intake_packet.py").write_text(
            'parser.add_argument("--input", default="tmp/research-automation/raw-events.json")\n'
            'parser.add_argument("--init-sample", action="store_true")\n',
            encoding="utf-8",
        )
        readme = scripts_dir / "README.md"
        readme.write_text("python scripts/research_intake_packet.py --input tmp/research-automation/raw-events.json\n", encoding="utf-8")
        payload = json.loads(module.TMP_LIFECYCLE.read_text(encoding="utf-8"))
        payload["cleanup_preview_samples"].append(
            {
                "path": "tmp/research-automation/raw-events.json",
                "suffix": ".json",
                "size_bytes": 2,
                "last_write_utc": "2026-05-01T00:00:00Z",
                "age_days": 50,
                "cleanup_preview_eligible": True,
                "protected_reasons": [],
            }
        )
        write_json(module.TMP_LIFECYCLE, payload)

        plan = module.build_plan()

        first_batch = plan["lanes"]["tmp_delete_proposal"]["first_small_safe_proposal_batch"]
        rows = {row["path"]: row for row in first_batch["rows"]}
        assert "tmp/research-automation/raw-events.json" in rows
        row = rows["tmp/research-automation/raw-events.json"]
        assert row["active_reference_count"] == 0
        assert row["rebuildable_sample_input_proof"]["is_rebuildable_sample_input"] is True
        assert row["delete_allowed_now"] is False


def test_closed_history_and_cache_rows_can_enter_first_microbatch() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        root = Path(tmpdir)
        audio_path = "tmp/audio-tools/node_modules/sharp/vendor/8.14.5/win32-x64/" + "platform.json"
        wf38_path = "tmp/wf38-fixtures/" + "passing_packet.json"
        wf59_path = "tmp/wf59-backups/" + "openclaw.before-disable-telegram-and-compaction.json"
        payload = json.loads(module.TMP_LIFECYCLE.read_text(encoding="utf-8"))
        payload["cleanup_preview_samples"] = [
            {
                "path": audio_path,
                "suffix": ".json",
                "size_bytes": 11,
                "last_write_utc": "2023-09-01T00:00:00Z",
                "age_days": 1000,
                "cleanup_preview_eligible": True,
                "protected_reasons": [],
            },
            {
                "path": wf38_path,
                "suffix": ".json",
                "size_bytes": 1623,
                "last_write_utc": "2026-05-06T00:00:00Z",
                "age_days": 52,
                "cleanup_preview_eligible": True,
                "protected_reasons": [],
            },
            {
                "path": wf59_path,
                "suffix": ".json",
                "size_bytes": 4458,
                "last_write_utc": "2026-05-09T00:00:00Z",
                "age_days": 49,
                "cleanup_preview_eligible": True,
                "protected_reasons": [],
            },
        ]
        write_json(module.TMP_LIFECYCLE, payload)
        for rel_path in [audio_path, wf38_path, wf59_path]:
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        (root / "scripts" / "README.md").write_text(
            f"fixture: {wf38_path}\n",
            encoding="utf-8",
        )
        continuity = root / "06. Playbooks" / "Project Continuity" / "Workflow 59 - Continuity and Compaction Hardening.md"
        continuity.parent.mkdir(parents=True, exist_ok=True)
        continuity.write_text(
            f"historical backup: {wf59_path}\n",
            encoding="utf-8",
        )

        plan = module.build_plan()

        first_batch = plan["lanes"]["tmp_delete_proposal"]["first_small_safe_proposal_batch"]
        rows = {row["path"]: row for row in first_batch["rows"]}
        assert set(rows) == set(payload["cleanup_preview_samples"][i]["path"] for i in range(3))
        assert first_batch["name"] == "tmp_closed_history_and_cache_microbatch"
        assert all(row["active_reference_count"] == 0 for row in rows.values())
        assert rows[wf38_path]["nonblocking_reference_sample"] == ["scripts/README.md"]
        assert rows[wf59_path]["proof_history_reference_sample"] == [
            "06. Playbooks/Project Continuity/Workflow 59 - Continuity and Compaction Hardening.md"
        ]
        assert all(row["delete_allowed_now"] is False for row in rows.values())


if __name__ == "__main__":
    test_plan_has_four_lanes_and_no_cleanup_authority()
    test_plan_surfaces_first_tmp_batch_and_route_contraction_files()
    test_rebuildable_research_sample_inputs_can_enter_tmp_batch()
    test_closed_history_and_cache_rows_can_enter_first_microbatch()
    print("wf88 retired surface cleanup plan tests passed")
