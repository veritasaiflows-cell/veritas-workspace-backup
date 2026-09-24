#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm_implementation_job_queue.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pm_implementation_job_queue", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def args() -> SimpleNamespace:
    return SimpleNamespace(
        pm_state=None,
        pm_actions=None,
        cron_candidates=None,
        helper_packets=None,
        wf74_router=None,
        max_pm_jobs=10,
        max_cron_jobs=0,
        max_wf74_jobs=8,
    )


def next_actions() -> dict:
    return {
        "status": "ok",
        "next_actions": [
            {
                "action_id": "trade_grade_decision_os-execute_safe_next_step",
                "action_type": "execute_safe_next_step",
                "lane_id": "trade_grade_decision_os",
                "lane_status": "ready",
                "readiness_score": 90,
                "description": "Advance WF85 proof surface.",
                "stop_lines": [
                    "internal personal decision support only",
                    "no capital deployment or execution authority",
                ],
            }
        ],
    }


def test_capabilities_and_completion_ledger_skip() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        first_args = args()
        first_args.pm_state_payload = {"status": "ok"}
        first_args.pm_actions_payload = next_actions()
        first_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        first_args.helper_packets_payload = {"status": "ok"}
        first_args.wf74_router_payload = {"status": "ok", "validation": {"status": "ok"}, "pm_job_candidates": []}

        payload = module.build_payload(first_args)
        assert payload["validation"]["status"] == "ok"
        job = payload["jobs"][0]
        caps = job["automation_capabilities"]
        assert job["job_id"] == "pm-trade-grade-decision-os-execute-safe-next-step"
        assert caps["auto_main_may_execute"] is True
        assert caps["auto_cron_may_execute"] is False
        assert caps["cron_proof_refresh_candidate"] is True
        assert caps["cron_graduation_required"] is True
        assert caps["cron_graduation_satisfied"] is False
        assert caps["auto_heartbeat_may_execute"] is False
        assert caps["helper_lane_allowed"] is True
        assert payload["summary"]["auto_main_executable_job_count"] == 1
        assert payload["summary"]["auto_cron_executable_job_count"] == 0
        assert payload["summary"]["cron_proof_refresh_candidate_count"] == 1
        assert payload["summary"]["cron_graduation_required_job_count"] == 1
        assert job["department"] == "finance_wf78_wf84_wf85"
        assert job["department_owner"]
        assert job["owner_workflow"] == "WF78/WF84/WF85"
        assert job["accountable_integrator"] == "main_session_veritas"
        assert job["allowed_execution_mode"] == "main_review_only_proof_refresh"
        assert payload["summary"]["department_counts"]["finance_wf78_wf84_wf85"] == 1

        module.DEFAULT_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.DEFAULT_COMPLETION_LEDGER.write_text(
            json.dumps({"job": {"job_id": job["job_id"]}}) + "\n",
            encoding="utf-8",
        )
        second_args = args()
        second_args.pm_state_payload = {"status": "ok"}
        second_args.pm_actions_payload = next_actions()
        second_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        second_args.helper_packets_payload = {"status": "ok"}
        second_args.wf74_router_payload = {"status": "ok", "validation": {"status": "ok"}, "pm_job_candidates": []}
        completed_payload = module.build_payload(second_args)
        completed_job = completed_payload["jobs"][0]
        assert completed_job["status"] == "completed_by_ledger"
        assert completed_job["automation_capabilities"]["auto_main_may_execute"] is False
        assert completed_job["allowed_execution_mode"] == "completed_by_ledger_resolved"
        assert completed_payload["summary"]["completed_by_ledger_job_count"] == 1
        assert completed_payload["summary"]["active_job_count"] == 0
        assert completed_payload["summary"]["top_job_id"] is None
        assert completed_payload["summary"]["top_completed_job_id"] == job["job_id"]


def test_ready_for_review_jobs_can_complete_from_ledger() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        job_id = "pm-wf74-followup-wf55-measurement-only"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {"status": "ok", "next_actions": []}
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [
                {
                    "job_id": job_id,
                    "status": "ready_for_review",
                    "priority": "P2",
                    "title": "WF55 measurement-only followup",
                    "implementation_class": "wf74_workflow_measurement_followup",
                    "proof_commands": [
                        "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate"
                    ],
                }
            ],
        }

        module.DEFAULT_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.DEFAULT_COMPLETION_LEDGER.write_text(
            json.dumps({"job": {"job_id": job_id}}) + "\n",
            encoding="utf-8",
        )

        payload = module.build_payload(test_args)
        completed_job = payload["jobs"][0]
        assert completed_job["status"] == "completed_by_ledger"
        assert completed_job["completed_by_ledger"] is True
        assert completed_job["automation_capabilities"]["auto_main_may_execute"] is False
    assert payload["summary"]["ready_job_count"] == 0
    assert payload["summary"]["completed_by_ledger_job_count"] == 1
    assert payload["summary"]["active_job_count"] == 0
    assert payload["summary"]["top_job_id"] is None
    assert payload["summary"]["top_completed_job_id"] == job_id


def test_regressed_wf74_job_is_not_suppressed_by_prior_completion() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        job_id = "pm-wf74-planning-followthrough-gap-regression"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {"status": "ok", "next_actions": []}
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [
                {
                    "job_id": job_id,
                    "status": "ready_for_main_or_helper",
                    "priority": "P1",
                    "source_key": "planning_quality-abc",
                    "source_category": "planning_quality",
                    "completion_status": "current_regression_after_completion",
                    "title": "Continue planning follow-through gap reduction after completed pass",
                    "implementation_class": "wf74_planning_followthrough",
                    "proof_commands": [
                        "python scripts\\coding_outcome_ledger.py --write --validate"
                    ],
                }
            ],
        }

        module.DEFAULT_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.DEFAULT_COMPLETION_LEDGER.write_text(
            json.dumps({"job": {"job_id": job_id}}) + "\n",
            encoding="utf-8",
        )

        payload = module.build_payload(test_args)
        job = payload["jobs"][0]
        assert job["status"] == "ready_for_main_or_helper"
        assert job.get("completed_by_ledger") is not True
        assert payload["summary"]["ready_job_count"] == 1
        assert payload["summary"]["completed_by_ledger_job_count"] == 0
        assert payload["summary"]["top_job_id"] == job_id


def test_regressed_wf74_job_resolves_after_new_exact_completion() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        job_id = "pm-wf74-cron-migration-regression-repair"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {"status": "ok", "next_actions": []}
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [
                {
                    "job_id": job_id,
                    "status": "ready_for_main_or_helper",
                    "priority": "P1",
                    "source_key": "cron-migration-regression",
                    "source_category": "cron_migration",
                    "completion_status": "current_regression_after_completion",
                    "prior_completion": {
                        "latest_completed_at_utc": "2026-06-21T03:32:18Z"
                    },
                    "title": "Repair regressed cron signals after completed migration plan",
                    "implementation_class": "wf74_cron_migration_repair_plan",
                    "proof_commands": [
                        "python scripts\\cron_control_packet.py --write --validate"
                    ],
                }
            ],
        }

        module.DEFAULT_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.DEFAULT_COMPLETION_LEDGER.write_text(
            json.dumps({
                # Recent exact completion: the fix just landed.
                "completed_at_utc": (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "job": {"job_id": job_id},
            }) + "\n",
            encoding="utf-8",
        )

        payload = module.build_payload(test_args)
        job = payload["jobs"][0]
        assert job["status"] == "completed_by_ledger"
        assert job["completed_by_ledger"] is True
        assert job["completion_match"] == "exact_job_id_after_regression"
        assert payload["summary"]["ready_job_count"] == 0
        assert payload["summary"]["completed_by_ledger_job_count"] == 1
        assert payload["summary"]["top_job_id"] is None
        assert payload["summary"]["top_completed_job_id"] == job_id


def test_completed_lane_can_absorb_inspect_blocker_alias() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {
            "status": "ok",
            "next_actions": [
                {
                    "action_id": "parallel_lane_orchestration-inspect_blocker",
                    "action_type": "inspect_blocker",
                    "lane_id": "parallel_lane_orchestration",
                    "lane_status": "blocked",
                    "readiness_score": 15,
                    "description": "Refresh the parallel lane recommendation.",
                    "stop_lines": ["recommendation only"],
                }
            ],
        }
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {"status": "ok", "validation": {"status": "ok"}, "pm_job_candidates": []}

        blocked_payload = module.build_payload(test_args)
        blocked_job = blocked_payload["jobs"][0]
        assert blocked_job["status"] == "blocked"
        assert blocked_payload["summary"]["blocked_job_count"] == 1

        module.DEFAULT_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.DEFAULT_COMPLETION_LEDGER.write_text(
            json.dumps({
                "job": {
                    "job_id": "pm-parallel-lane-orchestration-execute-safe-next-step",
                    "title": blocked_job["title"],
                    "collision_group": blocked_job["collision_group"],
                }
            }) + "\n",
            encoding="utf-8",
        )

        completed_payload = module.build_payload(test_args)
        completed_job = completed_payload["jobs"][0]
        assert completed_job["status"] == "completed_by_ledger"
        assert completed_job["completion_match"] == "inspect_blocker_collision_title_alias"
        assert completed_payload["summary"]["blocked_job_count"] == 0
        assert completed_payload["summary"]["active_job_count"] == 0
        assert completed_payload["summary"]["top_job_id"] is None


def test_retail_truth_routing_job_refreshes_customer_output_decision() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {
            "status": "ok",
            "next_actions": [
                {
                    "action_id": "retail_truth_routing-refresh_artifact",
                    "action_type": "refresh_artifact",
                    "lane_id": "retail_truth_routing",
                    "lane_status": "stale",
                    "readiness_score": 45,
                    "description": "Refresh retail truth routing proof.",
                    "stop_lines": ["no customer output"],
                }
            ],
        }
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {"status": "ok", "validation": {"status": "ok"}, "pm_job_candidates": []}

        payload = module.build_payload(test_args)
        commands = payload["jobs"][0]["proof_commands"]
        assert "python scripts\\retail_customer_output_decision_packet.py --write --validate" in commands


def test_wf74_finance_source_open_candidate_keeps_finance_department() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {"status": "ok", "next_actions": []}
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [
                {
                    "job_id": "pm-wf74-finance-source-open-quality-repair",
                    "rank": 1,
                    "priority": "P1",
                    "status": "ready_for_main_or_helper",
                    "source_key": "finance_source_open-test",
                    "source_category": "finance_mutation",
                    "lane_id": "finance_source_open_quality_repair",
                    "lane_status": "ready",
                    "title": "Clear finance response quality source-open blockers so WF74 scorecard can pass",
                    "objective": "Run WF78 source-open repair proof and rerun finance response quality.",
                    "implementation_class": "finance_response_quality_source_open_repair",
                    "owner_surface": "Finance response quality slice + WF78/WF85 source-open repair conveyor",
                    "target_files": ["tmp/finance-response-quality-slice.json"],
                    "collision_group": "wf74_finance_source_open_quality_repair",
                    "proof_commands": [
                        "python scripts\\wf78_source_open_repair_executor.py --tier all --write --validate",
                        "python scripts\\wf78_source_open_work_packet.py --write --validate",
                        "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
                    ],
                    "acceptance_criteria": ["source-open blockers are repaired or exactly reclassified"],
                    "stop_lines": ["no capital deployment"],
                    "authority_boundary": module.AUTHORITY_BOUNDARY,
                }
            ],
        }

        payload = module.build_payload(test_args)
        job = payload["jobs"][0]
        assert payload["validation"]["status"] == "ok", payload["validation"]
        assert job["job_id"] == "pm-wf74-finance-source-open-quality-repair"
        assert job["department"] == "finance_wf78_wf84_wf85"
        assert job["department_owner"] == "main-session-veritas-finance"
        assert job["owner_workflow"] == "WF78/WF84/WF85"
        assert job["allowed_execution_mode"] == "main_review_only_proof_refresh"


def test_finance_engine_rebuilds_artifact_index_after_generators() -> None:
    module = load_module()
    commands = module.LANE_TEMPLATES["finance_engine"]["proof_commands"]
    assembler = "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate"
    incremental = "python scripts\\artifact_index.py incremental"
    validate = "python scripts\\artifact_index.py validate"
    assert assembler in commands
    assert incremental in commands
    assert validate in commands
    assert commands.index(assembler) < commands.index(incremental) < commands.index(validate)


def test_cron_execution_requires_explicit_graduation_flag() -> None:
    module = load_module()
    base_job = {
        "status": "ready_for_main_or_helper",
        "implementation_class": "trade_grade_decision_os",
        "validation_budget": {"budget": "narrow"},
        "closeout_mode": "pm_state",
        "proof_commands": ["python scripts\\pm_control_packet.py --write --write-db --validate"],
        "target_files": ["tmp/pm-control-packet.json"],
    }

    candidate = module.automation_capabilities(dict(base_job))
    assert candidate["auto_main_may_execute"] is True
    assert candidate["cron_proof_refresh_candidate"] is True
    assert candidate["cron_graduation_required"] is True
    assert candidate["auto_cron_may_execute"] is False

    graduated = module.automation_capabilities({**base_job, "rsi_cron_graduation_approved": True})
    assert graduated["auto_main_may_execute"] is True
    assert graduated["cron_proof_refresh_candidate"] is True
    assert graduated["cron_graduation_satisfied"] is True
    assert graduated["auto_cron_may_execute"] is True


def test_main_proof_worker_rejects_shared_handoff_work() -> None:
    module = load_module()
    caps = module.automation_capabilities({
        "status": "ready_for_main_or_helper",
        "implementation_class": "canonical_finance_data_plane",
        "validation_budget": {"budget": "shared"},
        "closeout_mode": "handoff",
        "proof_commands": ["python scripts\\canonical_finance_data_plane.py --write --write-db --validate"],
        "target_files": ["tmp/canonical-finance-data-plane.json"],
    })

    assert caps["proof_only"] is True
    assert caps["main_proof_refresh_candidate"] is False
    assert caps["auto_main_may_execute"] is False
    assert caps["auto_cron_may_execute"] is False


def main() -> int:
    test_capabilities_and_completion_ledger_skip()
    test_ready_for_review_jobs_can_complete_from_ledger()
    test_regressed_wf74_job_is_not_suppressed_by_prior_completion()
    test_regressed_wf74_job_resolves_after_new_exact_completion()
    test_completed_lane_can_absorb_inspect_blocker_alias()
    test_retail_truth_routing_job_refreshes_customer_output_decision()
    test_wf74_finance_source_open_candidate_keeps_finance_department()
    test_finance_engine_rebuilds_artifact_index_after_generators()
    test_cron_execution_requires_explicit_graduation_flag()
    test_main_proof_worker_rejects_shared_handoff_work()
    print("pm_implementation_job_queue capability tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def test_stale_exact_completion_does_not_hide_current_regression() -> None:
    # 2026-09-24: 06-24 completions of the regression job id hid a live
    # September cron regression; an old exact completion must not resolve it.
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.DEFAULT_COMPLETION_LEDGER = root / "state" / "implementation-completion-ledger.jsonl"
        job_id = "pm-wf74-cron-migration-regression-repair"
        test_args = args()
        test_args.pm_state_payload = {"status": "ok"}
        test_args.pm_actions_payload = {"status": "ok", "next_actions": []}
        test_args.cron_candidates_payload = {"status": "ok", "candidates": []}
        test_args.helper_packets_payload = {"status": "ok"}
        test_args.wf74_router_payload = {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [{
                "job_id": job_id, "status": "ready_for_main_or_helper", "priority": "P1",
                "source_key": "cron-migration-regression", "source_category": "cron_migration",
                "completion_status": "current_regression_after_completion",
                "prior_completion": {"latest_completed_at_utc": "2026-06-21T03:32:18Z"},
                "title": "Repair regressed cron signals after completed migration plan",
                "implementation_class": "wf74_cron_migration_repair_plan",
                "proof_commands": ["python scripts\cron_control_packet.py --write --validate"],
            }],
        }
        module.DEFAULT_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.DEFAULT_COMPLETION_LEDGER.write_text(
            json.dumps({"completed_at_utc": "2026-06-24T00:08:22Z", "job": {"job_id": job_id}}) + "\n",
            encoding="utf-8",
        )
        job = module.build_payload(test_args)["jobs"][0]
        assert job["status"] == "ready_for_main_or_helper"
        assert job.get("completed_by_ledger") is not True
