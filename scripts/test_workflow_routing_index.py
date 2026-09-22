#!/usr/bin/env python3
"""Targeted regressions for workflow routing freshness owners."""
from __future__ import annotations

import gc
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta, timezone
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

WF89_CONTINUITY_SUFFIX = (
    "Workflow 89 - Isolated Agent Specialization and Fleet Efficiency Contract.md"
)
WF89_PRIMARY_ARTIFACT = "tmp/wf89-fleet-20260909/wf89-refresh-20260918.json"
WF89_RESUME_COMMAND = "python scripts\\workflow_router.py WF89 --answer all"
WF89_REQUIRED_ALIAS_KEYS = {
    "wf89",
    "workflow89",
    "isolatedagentspecializationandfleetefficiencycontract",
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
    # LOOP-REPAIR-20260912: WF88 blockers/limits are computed from live proof, not literals.
    # Retired literals and stale counts must not resurface anywhere actionable.
    for row in (wf74, wf88):
        joined = " ".join(row["blockers"]) + " " + " ".join(row.get("claim_limits") or [])
        assert "WF67 paper manager remains the execution guardrail" not in joined
        assert "19-case isolated live pilot" not in joined
        assert "zero semantic lift on six paraphrases" not in joined
    # Fixture-isolated retrieval discrimination: bad evidence yields a claim limit
    # (never an operational blocker); good evidence later passes clean.
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=_bad_retrieval_loader
    ):
        limits = routing.compute_wf88_claim_limits()
        folded = " ".join(limits).casefold()
        assert "human gold review incomplete" in folded
        assert "provider promotion blocked" in folded
        assert not any("retrieval" in blocker.casefold() for blocker in routing.compute_wf88_blockers())
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=_clean_loop_loader
    ):
        assert routing.compute_wf88_claim_limits() == []
        assert routing.compute_wf88_blockers() == []


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


def test_wf89_registered_as_p1_with_canonical_owner() -> None:
    routes = routes_by_id()
    wf89 = routes["WF89"]
    assert wf89["tier"] == "P1"
    assert wf89["display_name"] == "Isolated Agent Specialization and Fleet Efficiency Contract"
    assert (wf89["continuity_note"] or "").endswith(WF89_CONTINUITY_SUFFIX)
    assert "Supplementary" not in (wf89["continuity_note"] or "")
    assert wf89["primary_route_artifact"] == WF89_PRIMARY_ARTIFACT
    assert "tmp/wf89-fleet-20260909/current-handoff.json" in wf89["secondary_artifacts"]
    assert wf89["default_resume_command"] == WF89_RESUME_COMMAND
    assert WF89_RESUME_COMMAND in wf89["validator_commands"]
    assert wf89["owner_action_required"] is True
    assert wf89["safe_for_helper_lane"] is True
    assert len(wf89["stop_lines"]) >= 1
    assert wf89["validator_commands"]


def test_wf89_aliases_resolve_and_reject_fragments() -> None:
    routes = routes_by_id()
    wf89 = routes["WF89"]
    records = routing.route_alias_records(wf89)
    keys = {record["alias_key"] for record in records}
    assert WF89_REQUIRED_ALIAS_KEYS <= keys
    assert "fleet" not in keys
    assert "isolated" not in keys
    assert routing.normalize_lookup_key("Workflow89") == "workflow89"
    assert routing.normalize_lookup_key("WF-89") == "wf89"


def test_wf89_readonly_no_completion_inference() -> None:
    routes = routes_by_id()
    wf89 = routes["WF89"]
    assert "review-only" in wf89["authority_boundary"]
    joined_stops = " ".join(wf89["stop_lines"]).casefold()
    assert "no owner-approval inference" in joined_stops
    assert "no whole-workflow-complete inference from a1 acceptance" in joined_stops
    for token in ("capital", "execution"):
        assert token in joined_stops
    state = wf89["current_state"].casefold()
    assert "a1" in state and "explicit limits" in state
    assert "no whole-fleet readiness" in state
    assert "no successful live credited attribution" in state
    assert "complet" not in state or "no accounting/activation completion" in state
    assert wf89.get("effective_status_override") is None


def test_wf89_expected_counts_bump_and_guard() -> None:
    assert routing.EXPECTED_ROUTE_COUNT == 44
    assert routing.EXPECTED_TIER_COUNTS == {"P0": 2, "P1": 12, "P2": 8, "P3": 15, "P4": 7}
    # Raw build_routes() holds pre-reconciliation historical definitions; the
    # canonical invariant applies to reconciled build_index()["routes"].
    routes = routing.build_index()["routes"]
    assert len(routes) == routing.EXPECTED_ROUTE_COUNT
    for tier, expected in routing.EXPECTED_TIER_COUNTS.items():
        assert sum(1 for route in routes if route["tier"] == tier) == expected
    assert any(route["workflow_id"] == "WF89" and route["tier"] == "P1" for route in routes)
    # Negative guard: the pre-registration P1/total counts must no longer match.
    assert routing.EXPECTED_ROUTE_COUNT != 43
    assert routing.EXPECTED_TIER_COUNTS["P1"] != 11


def test_existing_routes_unchanged_after_wf89() -> None:
    routes = routes_by_id()
    assert routes["WF75"]["primary_route_artifact"] == "tmp/wf75-service-state-current.json"
    assert routes["WF79-SMB"]["primary_route_artifact"] == "tmp/wf79-smb-phase-closeout.json"
    assert routes["WF-WORKSPACE-GOVERNOR"]["tier"] == "P2"
    assert routes["WF-WORKSPACE-GOVERNOR"]["default_resume_command"] is None
    workflow_ids = [route["workflow_id"] for route in routing.build_routes()]
    assert len(workflow_ids) == len(set(workflow_ids))
    seen: set[str] = set()
    for route in routing.build_routes():
        for record in routing.route_alias_records(route):
            key = record["alias_key"]
            assert key not in seen, f"duplicate alias key {key!r}"
            seen.add(key)


def test_monitor_handoff_uses_explicit_owner_not_generated_or_retired() -> None:
    explicit = {"WF-CHIEF-GATE", "WF-FINANCE-CHAINS", "WF-BOARD-CANON-GUARDRAILS", "WF-SQL-INDEXES", "WF-WORKSPACE-GOVERNOR"}
    assert not hasattr(routing, "ROUTE_SOURCE_OVERRIDES")
    assert not hasattr(routing, "route_source_authority")
    routes = routes_by_id()
    for workflow_id in explicit:
        packet = routing.build_handoff(routes[workflow_id])
        assert packet["source_authority"] == "scripts/workflow_routing_index.py"
        assert packet["workflow_id"] == workflow_id
    assert routing.build_handoff(routes["WF75"])["source_authority"] == "06. Playbooks/Active Workflows.md"


def test_wf89_windows_junction_blocker_dated_proof() -> None:
    routes = routes_by_id()
    blockers = routes["WF89"]["blockers"]
    joined = " ".join(blockers).casefold()
    assert "no native windows denial fixture" not in joined
    assert "proof skipped" not in joined
    assert "2026-09-10" in joined
    assert "windows-junction-proof.json" in joined
    assert "junction" in joined
    assert "four" in joined
    assert "file-symlink" in joined
    assert "no universal" in joined or "no claim" in joined or "reparse" in joined
    assert any("dispatch_binding_missing_or_ambiguous" in b for b in blockers)
    assert any("isolated_source_reverification_mismatch" in b for b in blockers)


# LOOP-REPAIR-20260912: computed live-proof blockers for WF74/WF88.
# Fixtures carry producer-declared generated_at_utc; filesystem mtime is never
# consulted by the loop helpers, so these tests isolate proof content from checkout/copy times.


def _fresh_generated_at(hours_ago: float = 1.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _clean_loop_payload(status="ok", summary=None, validation_status="ok", hours_ago=1.0):
    return {
        "status": status,
        "generated_at_utc": _fresh_generated_at(hours_ago),
        "summary": summary if summary is not None else {},
        "validation": {"status": validation_status, "errors": [], "warnings": []},
    }


_CLEAN_WF88_SUMMARY = {
    "stale_input_count": 0,
    "stale_inputs": [],
    "blocked_or_followup_action_count": 0,
    "route_contraction_validation_status": "ok",
    "model_performance_claim_allowed_now": True,
    "wiki_frontier_result_row_count": 12,
    "wiki_advanced_pilot_executed_count": 2,
    "wiki_rsi_outcome_mature": True,
    "improvement_open_count": 0,
}

_CLEAN_RETRIEVAL_SUMMARY = {}


def _clean_retrieval_payload():
    return {
        "status": "ok",
        "generated_at_utc": _fresh_generated_at(),
        "human_review": {"sole_relevance_review_complete": True},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def _bad_retrieval_payload():
    return {
        "status": "draft_review_required",
        "generated_at_utc": _fresh_generated_at(),
        "human_review": {"sole_relevance_review_complete": False},
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": ["semantic_hash_paraphrase_discrimination_not_observed"],
        },
    }


def _clean_loop_loader(rel):
    if rel == routing.WF88_PRIMARY_PROOF:
        return _clean_loop_payload(summary=dict(_CLEAN_WF88_SUMMARY))
    if rel == "tmp/retrieval-live-eval.json":
        return _clean_retrieval_payload()
    return _clean_loop_payload()


def _bad_retrieval_loader(rel):
    if rel == routing.WF88_PRIMARY_PROOF:
        return _clean_loop_payload(summary=dict(_CLEAN_WF88_SUMMARY))
    if rel == "tmp/retrieval-live-eval.json":
        return _bad_retrieval_payload()
    return _clean_loop_payload()


def test_wf74_primary_is_current_owner_proof_not_retired_spine() -> None:
    routes = routes_by_id()
    wf74 = routes["WF74"]
    assert wf74["primary_route_artifact"] == "tmp/wf74-improvement-opportunity-queue.json"
    assert wf74["primary_route_artifact"] == routing.WF74_PRIMARY_PROOF
    assert "tmp/autonomy-spine-readiness-rollup.json" not in wf74["secondary_artifacts"]
    for proof in (
        "tmp/wf74-decision-docket.json",
        "tmp/wf74-autonomy-work-router.json",
        "tmp/improvement-ledger-current.json",
        "tmp/otel-ops-control.json",
        "tmp/otel-ops-window-summary.json",
    ):
        assert proof in wf74["secondary_artifacts"]
    joined_validators = " ".join(wf74["validator_commands"])
    assert "autonomy_spine_readiness_rollup" not in joined_validators
    assert "otel_ops_control" in joined_validators
    assert "improvement-opportunity queue" in wf74["next_action"]


def test_loop_missing_stale_failed_proof_blocks() -> None:
    with patch.object(routing, "exists_on_disk", return_value=False), patch.object(
        routing, "_loop_load_json", return_value=None
    ):
        assert any("missing" in blocker.casefold() for blocker in routing.compute_wf74_blockers())
        assert any("missing" in blocker.casefold() for blocker in routing.compute_wf88_blockers())

    def stale_loader(rel):
        return _clean_loop_payload(hours_ago=routing.LOOP_PROOF_SLA_HOURS + 1.0)

    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=stale_loader
    ):
        # Producer-clock staleness blocks even when the filesystem looks brand new:
        # touching or copying evidence must never green it.
        with patch.object(routing, "_age_hours", return_value=0.0):
            assert any(
                "stale by producer clock" in blocker for blocker in routing.compute_wf74_blockers()
            )
        assert any("stale by producer clock" in blocker for blocker in routing.compute_wf74_blockers())

    def future_loader(rel):
        payload = _clean_loop_payload()
        payload["generated_at_utc"] = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        return payload

    def unusable_loader(kind):
        def load(rel):
            payload = _clean_loop_payload()
            if kind == "absent":
                payload.pop("generated_at_utc")
            elif kind == "garbage":
                payload["generated_at_utc"] = "not-a-timestamp"
            elif kind == "critical":
                payload["status"] = "critical"
            elif kind == "validation-errors":
                payload["validation"] = {"status": "ok", "errors": ["stale_input:x", "stale_input:y"]}
            elif kind == "declared":
                payload["summary"] = {"blockers": ["owner hold: wait for X"]}
            elif kind == "no-validation":
                payload.pop("validation")
            return payload
        return load

    expectations = {
        "absent": "no usable generated_at_utc",
        "garbage": "no usable generated_at_utc",
        "critical": "failure",
        "validation-errors": "producer validation error",
        "declared": "proof declares blocker",
        "no-validation": "no validation section",
    }
    for kind, needle in expectations.items():
        with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
            routing, "_loop_load_json", side_effect=unusable_loader(kind)
        ):
            assert any(needle in blocker for blocker in routing.compute_wf74_blockers()), kind
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=unusable_loader("validation-errors")
    ):
        errors = [
            blocker for blocker in routing.compute_wf74_blockers()
            if "producer validation error" in blocker
        ]
        assert len(errors) >= 2
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=future_loader
    ):
        assert any("in the future" in blocker for blocker in routing.compute_wf74_blockers())


def test_loop_summary_blockers_propagate_and_clear() -> None:
    def regressed_loader(rel):
        if rel == routing.WF74_PRIMARY_PROOF:
            return _clean_loop_payload(
                summary={"regressed_after_completion_count": 2, "high_priority_count": 0}
            )
        return _clean_loop_payload()

    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=regressed_loader
    ):
        blockers = routing.compute_wf74_blockers()
        assert any("regressed-after-completion" in blocker for blocker in blockers)
        assert routing.compute_wf74_claim_limits() == []

    def queue_depth_loader(rel):
        if rel == routing.WF74_PRIMARY_PROOF:
            return _clean_loop_payload(summary={"high_priority_count": 1})
        return _clean_loop_payload()

    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=queue_depth_loader
    ):
        # Queue depth is a claim limit, never an operational blocker.
        assert routing.compute_wf74_blockers() == []
        assert any("queue depth" in limit for limit in routing.compute_wf74_claim_limits())

    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", return_value=_clean_loop_payload()
    ):
        assert routing.compute_wf74_blockers() == []
        assert routing.compute_wf74_claim_limits() == []


def test_loop_upstream_wf74_blocks_propagate_to_wf88_and_owner_gates_persist() -> None:
    routes = routes_by_id()
    for workflow_id in ("WF74", "WF88"):
        route = routes[workflow_id]
        assert route["tier"] == "P1"
        assert "review-only" in route["authority_boundary"]
        assert len(route["stop_lines"]) >= 1
        assert "approval inference" in " ".join(route["stop_lines"]).casefold()
        assert isinstance(route.get("claim_limits"), list)
    assert "No base-model self-modification" in " ".join(routes["WF74"]["stop_lines"])

    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=_clean_loop_loader
    ):
        assert routing.compute_wf74_blockers() == []
        assert routing.compute_wf74_claim_limits() == []
        assert routing.compute_wf88_blockers() == []
        assert routing.compute_wf88_claim_limits() == []

    def upstream_blocked_loader(rel):
        if rel == routing.WF74_PRIMARY_PROOF:
            return _clean_loop_payload(summary={"regressed_after_completion_count": 1})
        if rel == routing.WF88_PRIMARY_PROOF:
            return _clean_loop_payload(summary=dict(_CLEAN_WF88_SUMMARY))
        if rel == "tmp/retrieval-live-eval.json":
            return _clean_retrieval_payload()
        return _clean_loop_payload()

    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=upstream_blocked_loader
    ):
        assert routing.compute_wf74_blockers() != []
        wf88_blockers = routing.compute_wf88_blockers()
        assert any("WF88 upstream" in blocker for blocker in wf88_blockers)
        # Claim-limit vocabulary never leaks into operational blockers.
        folded = " ".join(wf88_blockers).casefold()
        for token in ("frontier", "pilot", "model-performance", "recursive-improvement", "promotion"):
            assert token not in folded

    # Recompute reflects dependency change: no stale cache retention.
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=upstream_blocked_loader
    ):
        assert routing.compute_wf74_blockers() != []
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=_clean_loop_loader
    ):
        assert routing.compute_wf74_blockers() == []


def test_wf88_pivot_branch_retains_contraction_visibility() -> None:
    row = {
        "workflow_id": "WF88",
        "display_name": "WF88 - Veritas OS 2.0",
        "tier": "P1",
        "primary_route_artifact": "tmp/wf88-os2-control-packet.json",
        "secondary_artifacts": [],
        "validator_commands": [],
        "stop_lines": [],
        "blockers": [],
    }
    out = routing.apply_alert_os_pivot_contract(row)
    assert out["primary_route_artifact"] == "tmp/wf88-os2-control-packet.json"
    assert "tmp/wf88-route-contraction-packet.json" in list(out.get("secondary_artifacts") or [])
    assert "python scripts\\wf88_route_contraction_packet.py --write --write-md --validate" in list(out.get("validator_commands") or [])
    stop = " ".join(out.get("stop_lines") or []).casefold()
    assert "no retired finance producer" in stop
    assert "execution" in stop


def test_wf87_pivot_branch_stays_retired_without_primary() -> None:
    row = {"workflow_id": "WF87", "display_name": "WF87 - Paper Autonomy Runtime Governor", "aliases": []}
    out = routing.apply_alert_os_pivot_contract(row)
    assert out["primary_route_artifact"] is None
    assert list(out.get("secondary_artifacts") or []) == []
    assert "Retired" in str(out.get("current_state") or "")
    assert out.get("owner_action_required") is True


def main() -> int:
    test_operational_packets_are_primary_freshness_owners()
    test_stable_script_mtime_is_not_used_for_current_state_freshness()
    test_wf74_wf88_route_live_retrieval_discrimination_separately()
    test_canonical_pause_reconciles_route_and_control_registry()
    test_exact_alias_lookup_is_indexed_and_rejects_fragments()
    test_sql_lookup_fails_closed_when_selected_freshness_source_moves()
    test_wf89_registered_as_p1_with_canonical_owner()
    test_wf89_aliases_resolve_and_reject_fragments()
    test_wf89_readonly_no_completion_inference()
    test_wf89_expected_counts_bump_and_guard()
    test_existing_routes_unchanged_after_wf89()
    test_monitor_handoff_uses_explicit_owner_not_generated_or_retired()
    test_wf89_windows_junction_blocker_dated_proof()
    test_wf74_primary_is_current_owner_proof_not_retired_spine()
    test_loop_missing_stale_failed_proof_blocks()
    test_loop_summary_blockers_propagate_and_clear()
    test_loop_upstream_wf74_blocks_propagate_to_wf88_and_owner_gates_persist()
    test_wf88_pivot_branch_retains_contraction_visibility()
    test_wf87_pivot_branch_stays_retired_without_primary()
    test_loop_fa1_unknown_status_fails_closed()
    test_loop_fa1_validation_vocab_fails_closed()
    test_loop_fa1_review_only_statuses_stay_green()
    test_loop_fa1_producer_warning_stays_green()
    print("workflow_routing_index targeted tests passed")
    return 0

# F-A1 allowlist hardening: explicit producer/validation vocabularies, fail closed.
# Legitimate values come from the frozen producer descriptors (finding.json
# current_producer_descriptors): producer {ok, control_packet_ready_no_apply_authority,
# draft_review_required}, validation {ok, warning}. Everything else blocks.


def test_loop_fa1_unknown_status_fails_closed() -> None:
    for bad in (None, 123, 4.5, True, "", "   ", "unknown", "UNKNOWN", "UnKnOwN",
                "fail-closed", "FAIL-CLOSED", "fail_closed", "failed", "critical",
                "error", "blocked", "ok-bogus", " draft ", "none", "null", "n/a"):
        assert routing._loop_status_failed(bad) is True, repr(bad)
    assert not hasattr(routing, "_LOOP_FAIL_TOKENS")


def test_loop_fa1_validation_vocab_fails_closed() -> None:
    for bad in (None, 123, "", "unknown", "UNKNOWN", "fail-closed", "fail_closed",
                "failed", "error", "critical", "blocked", "draft_review_required", "ok-bogus"):
        assert routing._loop_validation_failed(bad) is True, repr(bad)
    for good in ("ok", "OK", " ok ", "warning", "WARNING", " Warning "):
        assert routing._loop_validation_failed(good) is False, repr(good)


def test_loop_fa1_review_only_statuses_stay_green() -> None:
    for good in ("ok", "OK", " ok ", "control_packet_ready_no_apply_authority",
                 "CONTROL_PACKET_READY_NO_APPLY_AUTHORITY",
                 "draft_review_required", "Draft_Review_Required"):
        assert routing._loop_status_failed(good) is False, repr(good)
    # QA probe replays: fresh proof with present-but-unknown/None/missing status,
    # or unknown validation status, must block (blockers != []).
    def loader_for(status, validation_status, drop_status=False, drop_validation=False):
        def load(rel):
            payload = _clean_loop_payload()
            if drop_status:
                payload.pop("status")
            else:
                payload["status"] = status
            if drop_validation:
                payload.pop("validation", None)
            elif validation_status is not None:
                payload["validation"] = {"status": validation_status, "errors": [], "warnings": []}
            else:
                payload["validation"] = {"status": None, "errors": [], "warnings": []}
            return payload
        return load
    probes = [
        loader_for(None, "unknown"),
        loader_for("unknown", None),
        loader_for("PLACEHOLDER", "ok", drop_status=True),
        loader_for("ok", "unknown"),
        loader_for("fail-closed", "ok"),
        loader_for("ok", "fail-closed"),
    ]
    for loader in probes:
        with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
            routing, "_loop_load_json", side_effect=loader
        ):
            assert routing.compute_wf74_blockers() != []
    # Positive: legitimate review-only producer + warning validation stays green.
    def review_only_loader(rel):
        return {
            "status": "draft_review_required",
            "generated_at_utc": _fresh_generated_at(),
            "summary": {},
            "validation": {"status": "warning", "errors": [], "warnings": []},
        }
    with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
        routing, "_loop_load_json", side_effect=review_only_loader
    ):
        assert routing.compute_wf74_blockers() == []



def test_loop_fa1_producer_warning_stays_green() -> None:
    for good in ("warning", "WARNING", " warning "):
        assert routing._loop_status_failed(good) is False, repr(good)
    # End to end: legitimate producer warning with ok/warning validation stays green.
    for validation_status in ("ok", "warning"):
        def warning_loader(rel, _vs=validation_status):
            return {
                "status": "warning",
                "generated_at_utc": _fresh_generated_at(),
                "summary": {},
                "validation": {"status": _vs, "errors": [], "warnings": []},
            }
        with patch.object(routing, "exists_on_disk", return_value=True), patch.object(
            routing, "_loop_load_json", side_effect=warning_loader
        ):
            assert routing.compute_wf74_blockers() == []


if __name__ == "__main__":
    raise SystemExit(main())
