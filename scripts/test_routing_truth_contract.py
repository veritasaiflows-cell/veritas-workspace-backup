#!/usr/bin/env python3
"""Focused regressions for the workflow-routing truth contract."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import autonomous_routing_deployment_cards as cards
import concurrent_lane_manager as lanes
import workflow_routing_index as routing
import workflow_router as router


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def source(status: str = "ok") -> dict:
    return {
        "status": status,
        "validation": {"status": "ok" if status == "ok" else "blocked", "errors": [], "warnings": []},
        "authority_boundary": {
            "capital_deployment_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_allowed": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def test_route_contract_separates_state_from_priority() -> None:
    index = routing.build_index()
    by_id = {row["workflow_id"]: row for row in index["routes"]}

    wf75 = by_id["WF75"]
    assert wf75["priority"] == "P3"
    assert wf75["lifecycle"] == "paused"
    assert wf75["readiness"] == "paused"
    assert wf75["effective_status_override"] == "on_hold"
    assert wf75["safe_for_helper_lane"] is False

    wf67 = by_id["WF67"]
    assert wf67["authority_class"] == "paper_guard_fail_closed"
    assert wf67["readiness"] == "blocked"
    assert wf67["safe_for_helper_lane"] is False

    for row in index["routes"]:
        assert row["authoritative_next_action"] == row["next_action"]
        assert row["human_approval_owner"] == "Randall"
        assert row["freshness"]["material_context_score"] in routing.FRESHNESS_SCORES
        if row["tier"] in {"P0", "P1"}:
            assert row["primary_owner_lane"] == "main-session-veritas"
            assert row["proof_artifact"]
            assert row["effective_status_override"] != "ready"

    capsule = router.build_capsule(wf75, router.load_registry(), [], [])
    assert capsule["lifecycle"] == "paused"
    assert capsule["effective_status"] == "on_hold"
    assert capsule["helper_safe"] is False

    persisted = json.loads(routing.INDEX_OUT.read_text(encoding="utf-8"))
    assert router.route_index_staleness_reasons(persisted) == []
    stale = dict(persisted)
    stale["source_freshness"] = dict(persisted["source_freshness"])
    stale["source_freshness"]["active_workflows_mtime_ns"] = -1
    assert router.route_index_staleness_reasons(stale)


def test_live_lane_projection_excludes_terminal_history() -> None:
    register = lanes.empty_register()
    register["lanes"] = [
        {
            "lane_id": "WF73::done",
            "workflow_id": "WF73",
            "workstream_id": "done",
            "owner": "main-session-veritas",
            "status": "complete",
            "allowed_writes": ["tmp/done.json"],
            "proof_artifacts": ["tmp/done.json"],
        },
        {
            "lane_id": "WF73::live",
            "workflow_id": "WF73",
            "workstream_id": "live",
            "owner": "main-session-veritas",
            "status": "running",
            "lease_expires_at_utc": "2999-01-01T00:00:00Z",
            "allowed_writes": ["tmp/live.json"],
            "proof_artifacts": [],
            "runtime": {"deliverable": "Validate the focused routing repair."},
        },
    ]
    lanes.refresh_summary(register)
    summary = register["summary"]
    assert summary["historical_terminal_lane_count"] == 1
    assert summary["open_lane_count"] == 1
    assert [row["lane_id"] for row in summary["open_lanes"]] == ["WF73::live"]
    assert summary["open_lanes"][0]["owner"] == "main-session-veritas"
    assert summary["open_lanes"][0]["sla_status"] == "lease_current"


def test_candidate_docket_fails_closed_when_wf67_guard_is_not_clean() -> None:
    with TemporaryDirectory() as raw:
        root = Path(raw)
        paths = {key: root / f"{key}.json" for key in cards.SOURCES}
        for path in paths.values():
            write_json(path, source())

        router_source = source()
        router_source["rows"] = [{
            "ticker": "AAA", "auto_tier": "Tier A", "auto_state": "A-READY",
            "tier_a_confidence_status": "ready", "critical_data_conflict_count": 0,
        }]
        write_json(paths["wf78_auto_router"], router_source)

        manifest = source()
        manifest["authority_boundary"] = {"report_only": True, "ticker_import_allowed": False, "apply_allowed": False, "promotion_allowed": False}
        write_json(paths["wf78_batch_manifest"], manifest)

        timing = source()
        timing["rows"] = [{
            "ticker": "AAA", "tier_scope": "tier_a_b_decision_layer", "auto_tier": "Tier A",
            "auto_state": "A-READY", "final_timing_state": "review_ready_wait_approval",
        }]
        write_json(paths["wf85_timing_gate"], timing)

        morning = source()
        morning["cards"] = [{
            "ticker": "AAA", "clean_for_randall_approval_review": True,
            "owner_card_path": "tmp/aaa-card.json", "wf67_request_path": "tmp/aaa-request.json",
        }]
        write_json(paths["morning_cards"], morning)

        command = source()
        command["summary"] = {
            "shadow_threshold_met": True,
            "exact_order_preparation_allowed_now": True,
            "autonomous_execution_allowed_now": False,
        }
        write_json(paths["wf87_command_center"], command)
        rollup = source()
        rollup["shadow_threshold"] = {"threshold_met": True}
        rollup["reconciliation_maturity"] = {"mature_for_autonomy": True}
        write_json(paths["wf87_rollup"], rollup)

        payload = cards.build_payload(paths)
        row = payload["queue"][0]
        assert row["candidate_chain"]["Randall"]["approval_received"] is False
        assert row["candidate_chain"]["WF67"]["state"] == "ready"

        write_json(paths["wf67_guard"], source("blocked"))
        blocked = cards.build_payload(paths)["queue"][0]
        assert blocked["candidate_chain"]["WF67"]["state"] == "blocked"
        assert blocked["autonomous_routing_action"] == "owner_card_materialization_blocked"
        assert blocked["authority_boundary"]["paper_or_live_execution_allowed"] is False


def main() -> int:
    test_route_contract_separates_state_from_priority()
    test_live_lane_projection_excludes_terminal_history()
    test_candidate_docket_fails_closed_when_wf67_guard_is_not_clean()
    print("routing truth contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
