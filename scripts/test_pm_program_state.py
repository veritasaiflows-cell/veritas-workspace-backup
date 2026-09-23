#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

import pm_program_state as pm


FUTURE_301_500_SUPPORT_KEYS = {
    "go_sql_500_expansion_gate",
    "python_go_sql_500_expansion_gate_parity",
    "wf78_500_reputation_gate",
}

CURRENT_PHASE2_SUPPORT_KEYS = {
    "go_wf78_sql_phase2_readiness_probe",
    "python_go_wf78_sql_phase2_readiness_parity",
}


def test_wf74_source_open_override_routes_to_finance_department() -> None:
    payload = {
        "summary": {
            "finance_response_quality_recommended_repair_route": "wf78_wf85_source_open_repair",
            "finance_response_quality_source_open_blocked_count": 42,
            "finance_response_quality_blocker_chain": [
                "wf74_model_quality_collection_cron_runner",
                "model_quality_scorecard",
                "finance_response_quality_slice",
                "source_open_blocked_count=42",
            ],
        }
    }

    override = pm.wf74_finance_source_open_action_override(
        "wf74_learning_runtime",
        "blocked",
        [payload],
    )

    assert override["department"] == "finance_wf78_wf84_wf85"
    assert override["department_owner"] == "main-session-veritas-finance"
    assert override["owner_workflow"] == "WF78/WF84/WF85"
    assert override["top_job_id"] == "pm-wf74-finance-source-open-quality-repair"
    assert "source_open_blocked_count=42" in override["description"]
    assert override["blocker_chain"][-1] == "source_open_blocked_count=42"


def test_wf74_source_open_override_is_narrow() -> None:
    assert pm.wf74_finance_source_open_action_override("wf74_learning_runtime", "ready", [{}]) == {}
    assert pm.wf74_finance_source_open_action_override("wf78_scaleout", "blocked", [{}]) == {}
    assert pm.wf74_finance_source_open_action_override("wf74_learning_runtime", "blocked", [{"summary": {}}]) == {}


def stale_artifact(key: str, **registry) -> dict:
    return {
        "key": key,
        "path": f"tmp/{key}.json",
        "required": True,
        "exists": True,
        "parseable_json": True,
        "json_expected": True,
        "age_hours": 48,
        "max_age_hours": 24,
        "source_registry": registry,
    }


def test_registry_suppressed_stale_rows_do_not_make_lane_stale() -> None:
    now = datetime(2026, 7, 5, 5, 0, tzinfo=timezone.utc)
    health = pm.artifact_health(
        [
            stale_artifact(
                "market",
                freshness_cadence="market_session",
                market_calendar_grace=True,
                stale_action="suppress_until_next_market_open",
                blocks_readiness=False,
            ),
            stale_artifact(
                "event",
                freshness_cadence="event_triggered",
                stale_action="event_triggered_waiting",
                blocks_readiness=False,
            ),
            stale_artifact(
                "monitor",
                freshness_cadence="weekly_or_on_demand",
                stale_action="monitor_only",
                blocks_readiness=False,
            ),
            stale_artifact(
                "legacy",
                required=False,
                lifecycle="demoted_legacy_wf78_surface_2026_06_25",
            ),
        ],
        now=now,
    )

    assert health["stale"] == []
    assert health["suppressed_stale_count"] == 4
    assert {row["stale_classification"]["bucket"] for row in health["suppressed_stale"]} == {
        "market_closed_grace",
        "event_triggered_waiting",
        "monitor_only_stale",
    }
    assert pm.lane_status(health, []) == "ready"


def test_refresh_now_stale_rows_still_limit_readiness() -> None:
    now = datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc)
    health = pm.artifact_health(
        [
            stale_artifact(
                "market_after_refresh",
                freshness_cadence="market_session",
                market_calendar_grace=True,
                stale_action="suppress_until_next_market_open",
                blocks_readiness=False,
            ),
            stale_artifact(
                "refresh",
                freshness_cadence="daily",
                stale_action="refresh_now",
                blocks_readiness=False,
            ),
        ],
        now=now,
    )

    assert [row["key"] for row in health["stale"]] == ["market_after_refresh", "refresh"]
    assert {row["stale_classification"]["bucket"] for row in health["stale"]} == {"refresh_now"}
    assert pm.lane_status(health, []) == "stale"


def test_registry_demoted_missing_source_is_not_required_for_readiness() -> None:
    health = pm.artifact_health(
        [
            {
                "key": "legacy",
                "path": "tmp/legacy.json",
                "required": True,
                "exists": False,
                "parseable_json": False,
                "json_expected": True,
                "source_registry": {
                    "required": False,
                    "lifecycle": "demoted_legacy_wf78_surface_2026_06_25",
                },
            }
        ],
        now=datetime(2026, 7, 5, 5, 0, tzinfo=timezone.utc),
    )

    assert health["missing_required"] == []
    assert health["required_count"] == 0
    assert pm.lane_status(health, []) == "ready"


def test_inactive_future_scaleout_status_and_staleness_are_non_blocking() -> None:
    item = stale_artifact(
        "future_scaleout_support",
        required=False,
        blocks_readiness=False,
        freshness_cadence="on_demand",
        stale_action="event_triggered_waiting",
        lifecycle="demoted_future_301_500_scaleout_support_2026_08_07",
        activation_condition="future_301_500_scaleout_lane_deliberately_active",
    )
    item["status"] = "blocked"
    item["validation_status"] = "error"

    health = pm.artifact_health(
        [item],
        now=datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc),
    )

    assert health["required_count"] == 0
    assert health["stale"] == []
    assert health["suppressed_stale_count"] == 1
    assert health["problem_statuses"] == []
    assert health["warning_statuses"] == []
    assert health["expected_gates"] == []
    assert health["suppressed_status_count"] == 2
    assert {row["field"] for row in health["suppressed_statuses"]} == {
        "status",
        "validation_status",
    }
    assert pm.lane_status(health, []) == "ready"


def test_deliberately_active_future_scaleout_support_blocks_again() -> None:
    item = stale_artifact(
        "active_future_scaleout_support",
        required=True,
        blocks_readiness=True,
        freshness_cadence="daily",
        stale_action="refresh_now",
        lifecycle="future_301_500_scaleout_support_active",
        activation_condition="future_301_500_scaleout_lane_deliberately_active",
    )
    item["status"] = "blocked"
    item["validation_status"] = "error"

    health = pm.artifact_health(
        [item],
        now=datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc),
    )

    assert health["required_count"] == 1
    assert len(health["stale"]) == 1
    assert health["suppressed_stale_count"] == 0
    assert {row["field"] for row in health["problem_statuses"]} == {
        "status",
        "validation_status",
    }
    assert health["suppressed_statuses"] == []
    assert pm.lane_status(health, []) == "blocked"


def test_required_current_blocker_is_not_suppressed_by_non_blocking_stale_cadence() -> None:
    item = {
        "key": "parallel_repeatable_work_orchestration",
        "path": "tmp/parallel-repeatable-work-orchestration.json",
        "required": True,
        "exists": True,
        "parseable_json": True,
        "json_expected": True,
        "status": "blocked",
        "validation_status": "blocked",
        "source_registry": {
            "required": True,
            "blocks_readiness": False,
            "freshness_cadence": "event_triggered",
            "stale_action": "event_triggered_waiting",
        },
    }

    health = pm.artifact_health([item])

    assert health["suppressed_statuses"] == []
    assert {row["field"] for row in health["problem_statuses"]} == {
        "status",
        "validation_status",
    }
    assert pm.lane_status(health, []) == "blocked"


def test_status_suppression_requires_both_false_flags_and_support_lifecycle() -> None:
    cases = {
        "required_flag_reactivated": {
            "required": True,
            "blocks_readiness": False,
            "lifecycle": "demoted_future_301_500_scaleout_support_2026_08_07",
        },
        "blocking_flag_reactivated": {
            "required": False,
            "blocks_readiness": True,
            "lifecycle": "demoted_future_301_500_scaleout_support_2026_08_07",
        },
        "support_lifecycle_missing": {
            "required": False,
            "blocks_readiness": False,
            "lifecycle": "current_active_operations",
        },
    }

    for key, registry in cases.items():
        item = {
            "key": key,
            "path": f"tmp/{key}.json",
            "required": registry["required"],
            "exists": True,
            "parseable_json": True,
            "json_expected": True,
            "status": "blocked",
            "validation_status": "error",
            "source_registry": registry,
        }

        health = pm.artifact_health([item])

        assert health["suppressed_statuses"] == [], key
        assert {row["field"] for row in health["problem_statuses"]} == {
            "status",
            "validation_status",
        }, key
        assert pm.lane_status(health, []) == "blocked", key


def test_negated_ready_statuses_fail_closed() -> None:
    for value in ("not_ready", "data_not_ready", "not-ready", "not ready", "unready", "data_unready"):
        assert pm.value_status(value) == "blocked", value
    assert pm.value_status("data_ready") == "ok"


def test_future_scaleout_registry_rows_are_explicitly_inactive() -> None:
    registry = pm.source_registry_index()

    for key in FUTURE_301_500_SUPPORT_KEYS:
        row = registry[f"key:{key}"]
        assert row["required"] is False
        assert row["blocks_readiness"] is False
        assert row["stale_action"] == "event_triggered_waiting"
        assert row["activation_condition"] == "future_301_500_scaleout_lane_deliberately_active"
        assert any(token in row["lifecycle"] for token in ("demoted", "future"))


def test_current_phase2_registry_rows_remain_required_and_blocking() -> None:
    registry = pm.source_registry_index()

    for key in CURRENT_PHASE2_SUPPORT_KEYS:
        row = registry[f"key:{key}"]
        assert row["required"] is True
        assert row["blocks_readiness"] is True
        assert row["stale_action"] == "refresh_now"
        assert row["lifecycle"] == "active_current_300_row_wf78_sql_phase2_support"


def test_new_direct_phase2_blocker_cannot_hide_behind_older_green_aggregate() -> None:
    direct = {
        "key": "go_wf78_sql_phase2_readiness_probe",
        "path": "tmp/go-wf78-sql-phase2-readiness-probe.json",
        "required": True,
        "exists": True,
        "parseable_json": True,
        "json_expected": True,
        "age_hours": 1,
        "max_age_hours": 168,
        "status": "blocked",
        "validation_status": "error",
        "source_registry": {
            "required": True,
            "blocks_readiness": True,
            "lifecycle": "active_current_300_row_wf78_sql_phase2_support",
        },
    }
    older_aggregate = {
        "key": "python_go_durable_output_parity_repeated_gate",
        "path": "tmp/python-go-durable-output-parity-repeated-gate.json",
        "required": True,
        "exists": True,
        "parseable_json": True,
        "json_expected": True,
        "age_hours": 100,
        "max_age_hours": 168,
        "status": "ok",
        "validation_status": "ok",
        "source_registry": {"required": True, "blocks_readiness": True},
    }

    health = pm.artifact_health([direct, older_aggregate])

    assert {row["path"] for row in health["problem_statuses"]} == {
        "tmp/go-wf78-sql-phase2-readiness-probe.json"
    }
    assert {row["field"] for row in health["problem_statuses"]} == {
        "status",
        "validation_status",
    }
    assert pm.lane_status(health, []) == "blocked"


if __name__ == "__main__":
    test_wf74_source_open_override_routes_to_finance_department()
    test_wf74_source_open_override_is_narrow()
    test_registry_suppressed_stale_rows_do_not_make_lane_stale()
    test_refresh_now_stale_rows_still_limit_readiness()
    test_registry_demoted_missing_source_is_not_required_for_readiness()
    test_inactive_future_scaleout_status_and_staleness_are_non_blocking()
    test_deliberately_active_future_scaleout_support_blocks_again()
    test_required_current_blocker_is_not_suppressed_by_non_blocking_stale_cadence()
    test_status_suppression_requires_both_false_flags_and_support_lifecycle()
    test_negated_ready_statuses_fail_closed()
    test_future_scaleout_registry_rows_are_explicitly_inactive()
    test_current_phase2_registry_rows_remain_required_and_blocking()
    test_new_direct_phase2_blocker_cannot_hide_behind_older_green_aggregate()
    print("pm_program_state tests passed")


def _missing_probe(key: str) -> dict:
    return pm.artifact_probe(key, pm.TMP / f"__absent_{key}__.json", True, 24)


def test_retired_lane_with_absent_proof_reports_retired_without_blockers() -> None:
    lane = pm.build_lane("ticker_card_refresh", "t", "p", [_missing_probe("x")], "ready", "stale", ["review-only"])
    assert lane["status"] == "retired"
    assert lane["blockers"] == []
    assert lane["next_action"]["action_type"] == "retired"


def test_non_retired_lane_with_absent_proof_still_blocks() -> None:
    lane = pm.build_lane("finance_os_data_model", "t", "p", [_missing_probe("x")], "ready", "stale", ["review-only"])
    assert lane["status"] == "blocked"
    assert lane["blockers"]


def test_finance_os_data_model_tracks_wf84_alert_evidence_plane() -> None:
    lane = next(l for l in pm.build_lanes(pm.source_artifacts()) if l["lane_id"] == "finance_os_data_model")
    paths = {a["path"] for a in lane["source_artifacts"]}
    assert "tmp/alert-level-freshness-controller.json" in paths
    assert not any("canonical-finance-data-plane" in p or "wf78" in p for p in paths)
