from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf74_wf88_loop_trace_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf74_wf88_loop_trace_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module, *, duplicate_job: bool = False) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.MEMORY = root / "memory"
    module.OUT = module.TMP / "wf74-wf88-loop-trace.json"
    module.MD_OUT = module.TMP / "wf74-wf88-loop-trace.md"
    module.SOURCE_PATHS = {name: module.TMP / path.name for name, path in module.SOURCE_PATHS.items()}
    module.SOURCE_PATHS.update({
        "wf74_improvement_opportunity_queue": module.TMP / "wf74-improvement-opportunity-queue.json",
        "wf74_autonomy_work_router": module.TMP / "wf74-autonomy-work-router.json",
        "wf74_decision_docket": module.TMP / "wf74-decision-docket.json",
        "pm_implementation_job_queue": module.TMP / "pm-implementation-job-queue.json",
        "concurrent_lane_register": module.TMP / "concurrent-lane-register.json",
    })
    module.TMP.mkdir(parents=True, exist_ok=True)
    module.MEMORY.mkdir(parents=True, exist_ok=True)
    generated = module.utc_now()
    opportunity_id = "code_mutation-test123456"
    job_id = "pm-wf74-code-mutation-test"
    lane_id = "wf74-code-mutation-test"

    write_json(module.SOURCE_PATHS["otel_ops_control"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"event_count": 12},
        "validation": {"status": "ok"},
    })
    write_json(module.SOURCE_PATHS["model_learning_metadata_ledger"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"row_count": 4, "failure_rows": 1, "runtime_otel_rows": 2},
        "validation": {"status": "ok"},
    })
    write_json(module.SOURCE_PATHS["token_efficiency_scorecard"], {
        "status": "warning",
        "generated_at_utc": generated,
        "summary": {
            "token_event_count": 10,
            "api_call_reduction_candidate_count": 1,
            "prompt_compression_candidate_count": 1,
            "failure_cost_candidate_count": 0,
        },
        "validation": {"status": "warning"},
    })
    write_json(module.SOURCE_PATHS["implementation_token_attribution_bridge"], {
        "status": "warning",
        "generated_at_utc": generated,
        "summary": {"implementation_token_gap_count": 0},
        "validation": {"status": "warning"},
    })
    write_json(module.SOURCE_PATHS["wf74_improvement_opportunity_queue"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"opportunity_count": 1},
        "opportunities": [
            {
                "opportunity_id": opportunity_id,
                "origin_opportunity_id": opportunity_id,
                "lifecycle_id": "lifecycle-test-route",
                "category": "code_mutation",
                "title": "Repair test route",
                "priority": 90,
                "signal": "test_failure",
                "completion_status": "open",
                "review_event_ref": {
                    "schema": module.REVIEW_EVENT_REF_SCHEMA,
                    "metadata_only": True,
                    "link_status": "linked_exact",
                    "event_kind": "coding_outcome_event",
                    "lifecycle_id": "lifecycle-test-route",
                    "source_path": "data/state-history/coding-outcome-ledger.jsonl",
                    "record_id": "coding-test-event",
                    "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
                },
            }
        ],
        "validation": {"status": "ok"},
    })
    candidates = [
        {
            "job_id": job_id,
            "source_key": opportunity_id,
            "lane_id": lane_id,
            "status": "ready",
        }
    ]
    if duplicate_job:
        candidates.append({
            "job_id": job_id,
            "source_key": "another-source",
            "lane_id": "another-lane",
            "status": "ready",
        })
    write_json(module.SOURCE_PATHS["wf74_autonomy_work_router"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"routed_opportunity_count": 1, "pm_job_candidate_count": len(candidates)},
        "opportunity_routes": [
            {
                "source_key": opportunity_id,
                "recommendation_id": opportunity_id,
                "origin_opportunity_id": opportunity_id,
                "lifecycle_id": "lifecycle-test-route",
                "route_status": "pm_job_candidate",
                "route": "test_route",
                "pm_job_id": job_id,
                "implementation_class": "wf74_test_repair",
                "next_action": "Run the test repair.",
                "review_event_ref": {
                    "schema": module.REVIEW_EVENT_REF_SCHEMA,
                    "metadata_only": True,
                    "link_status": "linked_exact",
                    "event_kind": "coding_outcome_event",
                    "lifecycle_id": "lifecycle-test-route",
                    "source_path": "data/state-history/coding-outcome-ledger.jsonl",
                    "record_id": "coding-test-event",
                    "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
                },
            }
        ],
        "pm_job_candidates": candidates,
        "validation": {"status": "ok"},
    })
    write_json(module.SOURCE_PATHS["wf74_decision_docket"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"row_count": 1},
        "rows": [
            {
                "docket_id": "docket-test",
                "source_id": opportunity_id,
                "action_state": "fix_now",
                "next_action": "Patch the test surface.",
            }
        ],
        "validation": {"status": "ok"},
    })
    write_json(module.SOURCE_PATHS["pm_implementation_job_queue"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"job_count": 1},
        "jobs": [
            {
                "job_id": job_id,
                "status": "ready_for_main_or_helper",
                "source_opportunity_id": opportunity_id,
                "lane_id": lane_id,
                "readiness_score": 85,
                "collision_group": "wf74_test_repair",
            }
        ],
        "validation": {"status": "ok"},
    })
    write_json(module.SOURCE_PATHS["concurrent_lane_register"], {
        "status": "ok",
        "generated_at_utc": generated,
        "summary": {"active_lane_count": 0},
        "lanes": [
            {
                "lane_id": f"WF74::{lane_id}",
                "workflow_id": "WF74",
                "workstream_id": lane_id,
                "status": "complete",
                "updated_at_utc": generated,
                "completed_at_utc": generated,
                "proof_artifacts": ["python scripts\\test_wf74_wf88_loop_trace_packet.py"],
            }
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    for name in ("control_closeout_bundle", "implementation_release_contract", "wf88_wiki_synthesis_packet", "wf88_os2_control_packet"):
        write_json(module.SOURCE_PATHS[name], {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"stale_input_count": 0, "missing_required_input_count": 0},
            "validation": {"status": "ok"},
        })
    (module.MEMORY / "2026-07-04.md").write_text(
        f"- Completed closeout for {opportunity_id} using {job_id}.\n",
        encoding="utf-8",
    )


def test_loop_trace_stitches_opportunity_to_lane_closeout_and_memory() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["trace_row_count"] == 1
        assert packet["summary"]["pm_job_link_count"] == 1
        assert packet["summary"]["lane_link_count"] == 1
        assert packet["summary"]["completed_lane_missing_closeout_count"] == 0
        assert packet["summary"]["completed_lane_missing_memory_ref_count"] == 0
        row = packet["trace_rows"][0]
        assert row["pm_job_id"] == "pm-wf74-code-mutation-test"
        assert row["lane_status"] == "complete"
        assert row["memory_refs"]
        assert row["lifecycle_id"] == "lifecycle-test-route"
        assert row["review_event_ref"]["metadata_only"] is True
        assert row["review_event_provenance"] == [{
            "event_kind": "coding_outcome_event",
            "link_status": "linked_exact",
            "source_path": "data/state-history/coding-outcome-ledger.jsonl",
            "record_id": "coding-test-event",
            "record_hash": None,
        }]
        assert packet["authority_boundary"]["auto_apply_allowed"] is False


def test_loop_trace_blocks_duplicate_pm_job_ids() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module, duplicate_job=True)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert "duplicate_pm_job_id_count:1" in packet["validation"]["errors"]


def test_completed_by_ledger_job_without_live_lane_is_not_missing_lane_link() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        pm_queue_path = module.SOURCE_PATHS["pm_implementation_job_queue"]
        pm_queue = json.loads(pm_queue_path.read_text(encoding="utf-8"))
        pm_queue["jobs"][0]["status"] = "completed_by_ledger"
        pm_queue_path.write_text(json.dumps(pm_queue), encoding="utf-8")
        lane_register_path = module.SOURCE_PATHS["concurrent_lane_register"]
        lane_register = json.loads(lane_register_path.read_text(encoding="utf-8"))
        lane_register["lanes"] = []
        lane_register_path.write_text(json.dumps(lane_register), encoding="utf-8")

        packet = module.build_packet()

        assert packet["summary"]["lane_link_missing_count"] == 0
        row = packet["trace_rows"][0]
        assert "missing_lane_link" not in row["missing_links"]
        assert row["lane_resolution"] == "completed_by_ledger_no_live_lane_required"


def test_lifecycle_id_survives_pm_lane_change() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        first = module.build_packet()["trace_rows"][0]
        pm_queue_path = module.SOURCE_PATHS["pm_implementation_job_queue"]
        pm_queue = json.loads(pm_queue_path.read_text(encoding="utf-8"))
        pm_queue["jobs"][0]["lane_id"] = "wf74-code-mutation-test-next"
        pm_queue_path.write_text(json.dumps(pm_queue), encoding="utf-8")
        second = module.build_packet()["trace_rows"][0]

        assert first["trace_id"] != second["trace_id"]
        assert first["lifecycle_id"] == second["lifecycle_id"] == "lifecycle-test-route"


def test_review_event_ref_rejects_prose_capability_and_noncanonical_paths() -> None:
    module = load_module()
    valid_ref = {
        "schema": module.REVIEW_EVENT_REF_SCHEMA,
        "metadata_only": True,
        "link_status": "linked_exact",
        "event_kind": "coding_outcome_event",
        "lifecycle_id": "lifecycle-test-route",
        "source_path": "data/state-history/coding-outcome-ledger.jsonl",
        "record_id": "coding-test-event",
        "source_freshness": {"status": "fresh"},
        "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
    }
    assert module.metadata_only_review_event_ref(
        valid_ref,
        lifecycle_id="lifecycle-test-route",
        recommendation_id="code_mutation-test123456",
    ) is not None
    for prohibited_key, prohibited_value in {
        "raw_response": "must-not-propagate",
        "tool_payload": {"secret": "must-not-propagate"},
        "review_note": "free-form prose is not metadata",
        "execution_allowed": False,
    }.items():
        invalid_ref = dict(valid_ref)
        invalid_ref[prohibited_key] = prohibited_value
        assert module.metadata_only_review_event_ref(
            invalid_ref,
            lifecycle_id="lifecycle-test-route",
            recommendation_id="code_mutation-test123456",
        ) is None, prohibited_key
    invalid_boundary_ref = dict(valid_ref)
    invalid_boundary_ref["authority_boundary"] = {
        "review_only": True,
        "owner_approval_inferred": False,
        "approval_granted": False,
    }
    assert module.metadata_only_review_event_ref(
        invalid_boundary_ref,
        lifecycle_id="lifecycle-test-route",
        recommendation_id="code_mutation-test123456",
    ) is None
    invalid_freshness_ref = dict(valid_ref)
    invalid_freshness_ref["source_freshness"] = {
        "status": "fresh",
        "raw_tool_payload": "must-not-propagate",
    }
    assert module.metadata_only_review_event_ref(
        invalid_freshness_ref,
        lifecycle_id="lifecycle-test-route",
        recommendation_id="code_mutation-test123456",
    ) is None
    for invalid_path in (
        "tmp/wf74-autonomy-work-router.json",
        "tmp/wf74-wf88-loop-trace.json",
        "tmp/rsi-outcome-scorecard.json",
        "wiki/Decision Compiler.md",
        "data/state-history/recommendation-outcome-grades.jsonl",
    ):
        invalid_ref = dict(valid_ref)
        invalid_ref["source_path"] = invalid_path
        assert module.metadata_only_review_event_ref(
            invalid_ref,
            lifecycle_id="lifecycle-test-route",
            recommendation_id="code_mutation-test123456",
        ) is None, invalid_path


def test_legacy_lifecycle_fallback_matches_queue_router_and_trace() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        queue_path = module.SOURCE_PATHS["wf74_improvement_opportunity_queue"]
        queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))
        legacy_opportunity = queue_payload["opportunities"][0]
        legacy_opportunity.pop("origin_opportunity_id")
        legacy_opportunity.pop("lifecycle_id")
        legacy_opportunity.pop("review_event_ref")
        queue_path.write_text(json.dumps(queue_payload), encoding="utf-8")
        router_path = module.SOURCE_PATHS["wf74_autonomy_work_router"]
        router_payload = json.loads(router_path.read_text(encoding="utf-8"))
        legacy_route = router_payload["opportunity_routes"][0]
        legacy_route.pop("origin_opportunity_id")
        legacy_route.pop("lifecycle_id")
        legacy_route.pop("review_event_ref")
        router_path.write_text(json.dumps(router_payload), encoding="utf-8")

        import wf74_autonomy_work_router as router
        import wf74_improvement_opportunity_queue as queue

        origin = "code_mutation-test123456"
        expected = queue.ensure_lifecycle_identity({"opportunity_id": origin})["lifecycle_id"]
        routed = router.opportunity_route({
            "opportunity_id": origin,
            "category": "code_mutation",
            "title": "Legacy lifecycle fallback",
        }, {"classification": "active_repair_plan_required"})
        trace_row = module.build_packet()["trace_rows"][0]

        assert expected == routed["lifecycle_id"] == trace_row["lifecycle_id"]


if __name__ == "__main__":
    test_loop_trace_stitches_opportunity_to_lane_closeout_and_memory()
    test_loop_trace_blocks_duplicate_pm_job_ids()
    test_completed_by_ledger_job_without_live_lane_is_not_missing_lane_link()
    test_lifecycle_id_survives_pm_lane_change()
    test_review_event_ref_rejects_prose_capability_and_noncanonical_paths()
    test_legacy_lifecycle_fallback_matches_queue_router_and_trace()
    print("ok")
