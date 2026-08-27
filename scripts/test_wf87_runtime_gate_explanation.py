#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf87_runtime_gate_explanation as explain


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def base_source(status: str = "blocked") -> dict:
    return {
        "status": status,
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "live_endpoint_allowed": False,
            "money_movement_allowed": False,
        },
    }


def rollup_payload(root: Path, blockers: list[str]) -> dict:
    source_artifacts = {
        "ttl": str(root / "ttl.json"),
        "intraday": str(root / "intraday.json"),
        "paper_reconciliation": str(root / "paper-reconciliation.json"),
        "position_sizing": str(root / "position-sizing.json"),
        "circuit_breakers": str(root / "circuit-breakers.json"),
        "wf86_shadow": str(root / "shadow.json"),
        "order_history": str(root / "order-history.json"),
    }
    for path in source_artifacts.values():
        write_json(Path(path), base_source())
    write_json(
        root / "shadow.json",
        {
            **base_source("ok"),
            "summary": {
                "decision_count": 36,
                "scoreable_decision_count": 16,
                "pending_regular_session_followup_count": 2,
            },
        },
    )
    write_json(
        root / "position-sizing.json",
        {
            **base_source("blocked"),
            "summary": {"critical_finding_count": 3, "blocked_candidate_count": 0},
            "findings": [{"severity": "critical", "code": "no_order_candidates"}],
        },
    )
    return {
        "schema": "veritas.wf87_v2_readiness_rollup.v1",
        "generated_at_utc": "2026-06-20T06:00:00Z",
        "status": "phase_a_hardening_implemented_runtime_blocked",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "market_session": {"regular_market_hours": False},
        "shadow_threshold": {
            "clean_shadow_decision_count": 15,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 5,
            "required_clean_market_sessions": 5,
        },
        "reconciliation_maturity": {
            "status": "blocked",
            "submitted_source_count": 1,
            "unresolved_count": 0,
            "current_reconciliation_clean": False,
            "mature_for_autonomy": False,
        },
        "blockers": blockers,
        "blocker_taxonomy": {
            "maturity_blockers": [
                "shadow_threshold_not_met",
                "reconciliation_maturity_not_met",
            ],
            "fail_closed_at_rest": [
                "approval_freshness_ttl_status_not_allowed:blocked",
                "intraday_monitor_status_not_allowed:wake_recommended",
                "paper_reconciliation_freshness_status_not_allowed:blocked",
                "portfolio_circuit_breakers_status_not_allowed:blocked",
            ],
            "runtime_blockers": [
                "position_sizing_runtime_status_not_allowed:blocked",
            ],
        },
        "gates": [
            {
                "name": "position_sizing_runtime",
                "source_status": "blocked",
                "validation_status": "ok",
                "runtime_status": "blocked",
            }
        ],
        "source_artifacts": source_artifacts,
    }


def test_all_known_blockers_are_explained() -> None:
    blockers = [
        "approval_freshness_ttl_status_not_allowed:blocked",
        "intraday_monitor_status_not_allowed:wake_recommended",
        "paper_reconciliation_freshness_status_not_allowed:blocked",
        "portfolio_circuit_breakers_status_not_allowed:blocked",
        "position_sizing_runtime_status_not_allowed:blocked",
        "reconciliation_maturity_not_met",
        "shadow_threshold_not_met",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rollup = write_json(root / "rollup.json", rollup_payload(root, blockers))
        payload = explain.build_explanation(rollup)
        assert payload["status"] == "runtime_blocked_explained"
        assert payload["validation"]["status"] == "ok"
        assert payload["summary"]["explained_blocker_count"] == len(blockers)
        assert payload["summary"]["unexplained_blocker_count"] == 0
        by_blocker = {row["blocker"]: row for row in payload["explanations"]}
        for blocker in blockers:
            row = by_blocker[blocker]
            assert row["source_artifact"]
            assert row["reason"]
            assert row["owner_action"]
            assert row["validator"].startswith("python scripts\\")
            assert row["authority_boundary"]["paper_or_live_execution_allowed"] is False
        assert by_blocker["position_sizing_runtime_status_not_allowed:blocked"]["blocker_class"] == "runtime_blocker"
        assert by_blocker["shadow_threshold_not_met"]["maturity_context"]["gap"] == 5


def test_unknown_blocker_is_validation_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rollup = write_json(root / "rollup.json", rollup_payload(root, ["unknown_gate_blocked"]))
        payload = explain.build_explanation(rollup)
        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "error"
        assert payload["unexplained_blockers"] == ["unknown_gate_blocked"]
        assert "unexplained_blockers_present" in payload["validation"]["errors"]


def test_source_authority_drift_is_validation_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rollup_payload_value = rollup_payload(root, ["position_sizing_runtime_status_not_allowed:blocked"])
        position_path = Path(rollup_payload_value["source_artifacts"]["position_sizing"])
        source = json.loads(position_path.read_text(encoding="utf-8"))
        source["authority_boundary"]["paper_or_live_execution_allowed"] = True
        write_json(position_path, source)
        rollup = write_json(root / "rollup.json", rollup_payload_value)
        payload = explain.build_explanation(rollup)
        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "error"
        assert "authority_drift_detected" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_all_known_blockers_are_explained()
    test_unknown_blocker_is_validation_error()
    test_source_authority_drift_is_validation_error()
    print("ok")
