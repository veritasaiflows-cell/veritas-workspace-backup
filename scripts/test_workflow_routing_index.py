#!/usr/bin/env python3
"""Targeted regressions for workflow routing freshness owners."""
from __future__ import annotations

import gc
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import workflow_routing_index as routing
import workflow_router as workflow_router


EXPECTED_FRESHNESS_OWNERS = {
    "WF75": (
        "tmp/wf75-service-state-current.json",
        "scripts/wf75_training_desk.py",
    ),
    "WF79-SMB": (
        "tmp/wf79-smb-phase-closeout.json",
        "scripts/generic_intelligence_saas_pivot.py",
    ),
}


def routes_by_id() -> dict[str, dict]:
    return {route["workflow_id"]: route for route in routing.build_routes()}


def test_operational_packets_are_primary_freshness_owners() -> None:
    routes = routes_by_id()

    for workflow_id, (primary_owner, stable_script) in EXPECTED_FRESHNESS_OWNERS.items():
        route = routes[workflow_id]
        assert route["primary_route_artifact"] == primary_owner
        assert stable_script in route["secondary_artifacts"]
        assert primary_owner not in route["secondary_artifacts"]


def test_stable_script_mtime_is_not_used_for_current_state_freshness() -> None:
    routes = routes_by_id()

    for workflow_id, (primary_owner, stable_script) in EXPECTED_FRESHNESS_OWNERS.items():
        age_calls: list[str | None] = []

        def fake_age(path: str | None) -> float:
            age_calls.append(path)
            if path == stable_script:
                return routing.AGING_HOURS + 1.0
            if path == primary_owner:
                return 1.0
            return 2.0

        with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
            routing, "_age_hours", side_effect=fake_age
        ):
            freshness = routing.score_route_freshness(routes[workflow_id])

        assert freshness["score"] == "fresh"
        assert freshness["primary_artifact_age_hours"] == 1.0
        assert primary_owner in age_calls
        assert stable_script not in age_calls


def test_wf74_wf88_route_live_retrieval_discrimination_separately() -> None:
    routes = routes_by_id()
    wf74 = routes["WF74"]
    wf88 = routes["WF88"]

    for route in (wf74, wf88):
        assert "tmp/retrieval-live-eval.json" in route["secondary_artifacts"]
        assert "data/state-history/retrieval-live-eval.jsonl" in route["secondary_artifacts"]
        assert "python scripts\\retrieval_live_eval.py --write --write-md --validate" in route["validator_commands"]
        assert "python scripts\\test_retrieval_live_eval.py" in route["validator_commands"]

    assert "not the compatibility scorecard" in wf74["next_action"]
    assert "human gold review" in wf88["next_action"]
    assert any("zero semantic lift on six paraphrases" in blocker for blocker in wf88["blockers"])


def test_canonical_pause_reconciles_route_and_control_registry() -> None:
    index = routing.build_index()
    wf75 = {route["workflow_id"]: route for route in index["routes"]}["WF75"]

    assert wf75["tier"] == "P3"
    assert wf75["current_state"].startswith("Paused by Randall 2026-06-09")
    assert wf75["next_action"] == "Do not advance unless Randall resumes WF75."
    assert wf75["safe_for_helper_lane"] is False
    assert wf75["effective_status_override"] == "on_hold"
    assert wf75["state_reconciliation"]["status"] == "aligned"
    assert wf75["state_reconciliation"]["control_override_status"] == "on_hold"

    capsule = workflow_router.build_capsule(wf75, workflow_router.load_registry(), [], [])
    assert capsule["tier"] == "P3"
    assert capsule["effective_status"] == "on_hold"
    assert capsule["next_action"] == "Do not advance unless Randall resumes WF75."
    assert capsule["helper_safe"] is False

    for workflow_id in ("WF80", "WF81", "WF82", "WF83"):
        paused_route = {route["workflow_id"]: route for route in index["routes"]}[workflow_id]
        assert paused_route["tier"] == "P3"
        assert paused_route["safe_for_helper_lane"] is False
        assert paused_route["effective_status_override"] == "on_hold"
        assert paused_route["state_reconciliation"]["status"] == "aligned"


def test_exact_alias_lookup_is_indexed_and_rejects_fragments() -> None:
    index = routing.build_index()
    with TemporaryDirectory() as directory:
        db_path = Path(directory) / "workflow-routing-index.sqlite"
        report = routing.write_sqlite_index(index, db_path)
        assert report["status"] == "ok"

        for selector in ("WF75", "wf-75", "Workflow 75", "75", "Retail Investor Finance Intelligence SaaS"):
            resolved = routing.sql_route_lookup(db_path, selector)
            assert resolved is not None
            assert resolved["workflow_id"] == "WF75"
        assert routing.sql_route_lookup(db_path, "retail") is None
        assert routing.find_route(index, "retail") is None

        con = sqlite3.connect(db_path)
        try:
            plan = con.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT r.workflow_id
                FROM workflow_route_aliases AS a
                JOIN workflow_routes AS r ON r.workflow_id = a.workflow_id
                WHERE a.alias_key = ?
                """,
                ("wf75",),
            ).fetchall()
        finally:
            con.close()
        assert any("SEARCH a" in detail for _, _, _, detail in plan)
        # sqlite3 connection context managers commit/roll back but do not close
        # a connection. Collect function-local readers before Windows removes the
        # temporary WAL database directory.
        gc.collect()


def test_sql_lookup_fails_closed_when_selected_freshness_source_moves() -> None:
    index = routing.build_index()
    wf75 = {route["workflow_id"]: route for route in index["routes"]}["WF75"]
    original_mtime = routing._mtime_ns

    with TemporaryDirectory() as directory:
        db_path = Path(directory) / "workflow-routing-index.sqlite"
        routing.write_sqlite_index(index, db_path)

        def changed_mtime(path: str | None) -> int | None:
            value = original_mtime(path)
            if path == wf75["primary_route_artifact"]:
                return (value or 0) + 1
            return value

        with patch.object(routing, "_mtime_ns", side_effect=changed_mtime):
            try:
                routing.sql_route_lookup(db_path, "WF75")
            except routing.SqlIndexStaleError as exc:
                assert any(
                    item.get("check") == "route_freshness_source"
                    and item.get("workflow_id") == "WF75"
                    for item in exc.reasons
                )
            else:
                raise AssertionError("stale selected-route freshness was served")
        gc.collect()


def main() -> int:
    test_operational_packets_are_primary_freshness_owners()
    test_stable_script_mtime_is_not_used_for_current_state_freshness()
    test_wf74_wf88_route_live_retrieval_discrimination_separately()
    test_canonical_pause_reconciles_route_and_control_registry()
    test_exact_alias_lookup_is_indexed_and_rejects_fragments()
    test_sql_lookup_fails_closed_when_selected_freshness_source_moves()
    print("workflow_routing_index targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
