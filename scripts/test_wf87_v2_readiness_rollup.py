#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf87_v2_readiness_rollup as rollup


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "authority_boundary": {
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "live_endpoint_allowed": False,
            "money_movement_allowed": False,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in rollup.DEFAULT_SOURCES}


def write_phase_b_artifacts(paths: dict[str, Path]) -> None:
    write_json(
        paths["assisted_cadence"],
        {
            "status": "attempted_cadence_satisfied_maturity_blocked",
            "owner_policy_approval": {
                "approved": True,
                "exact_wf67_order_approval_required_each_time": True,
            },
            "assisted_maturity_reps": {
                "current_week_wf86_assisted_attempt_count": 1,
                "current_week_assisted_terminal_attempt_count": 1,
                "current_week_assisted_maturity_rep_count": 0,
                "all_time_wf86_assisted_attempt_count": 1,
                "all_time_assisted_terminal_attempt_count": 1,
                "all_time_assisted_maturity_rep_count": 0,
                "all_time_assisted_filled_round_trip_count": 0,
            },
            "authority_boundary": {
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
                "live_endpoint_allowed": False,
                "money_movement_allowed": False,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    )
    write_json(
        paths["shadow_outcomes"],
        {
            "status": "pending_regular_session_followup",
            "summary": {
                "scoreable_decision_count": 0,
                "pending_regular_session_followup_count": 3,
                "decision_quality_claim_allowed_now": False,
                "model_performance_claim_allowed_now": False,
            },
            "authority_boundary": {
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
                "live_endpoint_allowed": False,
                "money_movement_allowed": False,
                "decision_quality_claim_allowed_now": False,
                "model_performance_claim_allowed_now": False,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    )


def test_all_phase_a_gates_clean_but_autonomy_still_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        shadow = base_payload()
        shadow["summary"] = {
            "clean_shadow_decision_count": 3,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 1,
            "required_clean_market_sessions": 5,
            "shadow_threshold_met": False,
        }
        write_json(paths["wf86_shadow"], shadow)
        write_json(paths["wf86_autotrader"], base_payload("shadow_ready"))
        write_json(paths["wf86_guard"], base_payload("blocked"))
        write_json(paths["trade_grade_rollup"], base_payload("warning"))
        paper_reconciliation = base_payload()
        paper_reconciliation["freshness"] = {"status": "ok"}
        write_json(paths["paper_reconciliation"], paper_reconciliation)
        order_history = base_payload()
        order_history["summary"] = {"submitted_source_count": 1, "unresolved_count": 0}
        write_json(paths["order_history"], order_history)
        for key in ("position_sizing", "circuit_breakers", "ttl", "intraday"):
            write_json(paths[key], base_payload())
        paths["journal"].write_text(
            json.dumps({"decision_key": "2026-06-11:VRT", "authority": {"paper_or_live_execution_allowed": False}}) + "\n",
            encoding="utf-8",
        )
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths)
        assert payload["status"] == "phase_a_hardened_not_autonomous"
        assert payload["phase_readiness"]["phase_a_hardening_components_installed"] is True
        assert payload["phase_readiness"]["phase_a_runtime_gates_clean"] is True
        assert payload["phase_readiness"]["phase_a_hardening_gates_clean"] is True
        assert payload["phase_readiness"]["phase_c_autonomous_paper_buy_ready"] is False
        assert payload["phase_readiness"]["phase_b_assisted_cadence_policy_approved"] is True
        assert payload["phase_readiness"]["phase_b_assisted_attempts_current_week"] == 1
        assert payload["phase_readiness"]["phase_b_assisted_maturity_reps_current_week"] == 0
        assert payload["phase_readiness"]["shadow_outcome_scoring_installed"] is True
        assert "shadow_threshold_not_met" in payload["blockers"]
        assert payload["validation"]["status"] == "ok"


def test_missing_phase_a_artifact_blocks_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        for key, path in paths.items():
            if key == "position_sizing":
                continue
            if key == "journal":
                path.write_text(json.dumps({"decision_key": "a"}) + "\n", encoding="utf-8")
            elif key in {"assisted_cadence", "shadow_outcomes"}:
                continue
            else:
                write_json(path, base_payload("ok"))
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths)
        assert payload["status"] == "blocked"
        assert "position_sizing_runtime_artifact_missing" in payload["blockers"]
        assert payload["phase_readiness"]["phase_a_hardening_components_installed"] is False
        assert payload["validation"]["status"] == "ok"


def test_authority_drift_is_validation_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        for key, path in paths.items():
            if key == "journal":
                path.write_text(json.dumps({"decision_key": "a"}) + "\n", encoding="utf-8")
            elif key in {"assisted_cadence", "shadow_outcomes"}:
                continue
            else:
                payload = base_payload("ok")
                if key == "ttl":
                    payload["authority_boundary"]["paper_or_live_execution_allowed"] = True
                write_json(path, payload)
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths)
        assert payload["validation"]["status"] == "error"
        assert "authority_drift_detected" in payload["validation"]["errors"]


def test_fail_closed_phase_a_artifacts_count_as_installed_but_runtime_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        shadow = base_payload()
        shadow["summary"] = {
            "clean_shadow_decision_count": 3,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 1,
            "required_clean_market_sessions": 5,
            "shadow_threshold_met": False,
        }
        write_json(paths["wf86_shadow"], shadow)
        write_json(paths["wf86_autotrader"], base_payload("shadow_ready"))
        write_json(paths["wf86_guard"], base_payload("blocked"))
        write_json(paths["trade_grade_rollup"], base_payload("warning"))
        paper_reconciliation = base_payload()
        paper_reconciliation["freshness"] = {"status": "ok"}
        write_json(paths["paper_reconciliation"], paper_reconciliation)
        order_history = base_payload()
        order_history["summary"] = {"submitted_source_count": 1, "unresolved_count": 0}
        write_json(paths["order_history"], order_history)
        write_json(paths["position_sizing"], base_payload("ok"))
        for key in ("circuit_breakers", "ttl", "intraday"):
            write_json(paths[key], base_payload("blocked"))
        paths["journal"].write_text(
            json.dumps({"decision_key": "2026-06-11:VRT", "authority": {"paper_or_live_execution_allowed": False}}) + "\n",
            encoding="utf-8",
        )
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths, now_utc="2026-06-12T04:00:00Z")
        assert payload["status"] == "phase_a_hardening_implemented_runtime_blocked"
        assert payload["phase_readiness"]["phase_a_hardening_components_installed"] is True
        assert payload["phase_readiness"]["phase_a_runtime_gates_clean"] is False
        assert "approval_freshness_ttl_status_not_allowed:blocked" in payload["blocker_taxonomy"]["fail_closed_at_rest"]
        assert "shadow_threshold_not_met" in payload["blocker_taxonomy"]["maturity_blockers"]
        assert payload["validation"]["status"] == "ok"


def test_reconciliation_maturity_accepts_classifier_submitted_order_count() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        shadow = base_payload()
        shadow["summary"] = {
            "clean_shadow_decision_count": 20,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 5,
            "required_clean_market_sessions": 5,
            "shadow_threshold_met": True,
        }
        write_json(paths["wf86_shadow"], shadow)
        write_json(paths["wf86_autotrader"], base_payload("shadow_ready"))
        write_json(paths["wf86_guard"], base_payload("blocked"))
        write_json(paths["trade_grade_rollup"], base_payload("warning"))
        paper_reconciliation = base_payload()
        paper_reconciliation["freshness"] = {"status": "ok"}
        write_json(paths["paper_reconciliation"], paper_reconciliation)
        order_history = base_payload()
        order_history["summary"] = {"submitted_order_count": 1, "unresolved_count": 0}
        write_json(paths["order_history"], order_history)
        for key in ("position_sizing", "circuit_breakers", "ttl", "intraday"):
            write_json(paths[key], base_payload())
        paths["journal"].write_text(
            json.dumps({"decision_key": "2026-06-11:VRT", "authority": {"paper_or_live_execution_allowed": False}}) + "\n",
            encoding="utf-8",
        )
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths)
        assert payload["reconciliation_maturity"]["submitted_source_count"] == 1
        assert payload["reconciliation_maturity"]["mature_for_autonomy"] is True
        assert "reconciliation_maturity_not_met" not in payload["blockers"]


def test_reconciliation_maturity_accepts_fresh_reconciliation_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        shadow = base_payload()
        shadow["summary"] = {
            "clean_shadow_decision_count": 20,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 5,
            "required_clean_market_sessions": 5,
            "shadow_threshold_met": True,
        }
        write_json(paths["wf86_shadow"], shadow)
        write_json(paths["wf86_autotrader"], base_payload("shadow_ready"))
        write_json(paths["wf86_guard"], base_payload("blocked"))
        write_json(paths["trade_grade_rollup"], base_payload("warning"))
        paper_reconciliation = base_payload()
        paper_reconciliation["freshness"] = {"status": "fresh"}
        write_json(paths["paper_reconciliation"], paper_reconciliation)
        order_history = base_payload()
        order_history["summary"] = {"submitted_order_count": 1, "unresolved_count": 0}
        write_json(paths["order_history"], order_history)
        for key in ("circuit_breakers", "ttl", "intraday"):
            write_json(paths[key], base_payload())
        write_json(paths["position_sizing"], base_payload("idle_no_candidates"))
        paths["journal"].write_text(
            json.dumps({"decision_key": "2026-06-11:VRT", "authority": {"paper_or_live_execution_allowed": False}}) + "\n",
            encoding="utf-8",
        )
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths)
        assert payload["reconciliation_maturity"]["current_reconciliation_freshness_status"] == "fresh"
        assert payload["reconciliation_maturity"]["mature_for_autonomy"] is True
        assert "reconciliation_maturity_not_met" not in payload["blockers"]
        assert payload["phase_readiness"]["phase_a_runtime_gates_clean"] is True


def test_blocked_current_reconciliation_blocks_maturity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        shadow = base_payload()
        shadow["summary"] = {
            "clean_shadow_decision_count": 20,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 5,
            "required_clean_market_sessions": 5,
            "shadow_threshold_met": True,
        }
        write_json(paths["wf86_shadow"], shadow)
        write_json(paths["wf86_autotrader"], base_payload("shadow_ready"))
        write_json(paths["wf86_guard"], base_payload("blocked"))
        write_json(paths["trade_grade_rollup"], base_payload("warning"))
        paper_reconciliation = base_payload("blocked")
        paper_reconciliation["freshness"] = {"status": "blocked"}
        write_json(paths["paper_reconciliation"], paper_reconciliation)
        order_history = base_payload()
        order_history["summary"] = {"submitted_order_count": 1, "unresolved_count": 0}
        write_json(paths["order_history"], order_history)
        for key in ("position_sizing", "circuit_breakers", "ttl", "intraday"):
            write_json(paths[key], base_payload())
        paths["journal"].write_text(json.dumps({"decision_key": "a"}) + "\n", encoding="utf-8")
        write_phase_b_artifacts(paths)
        payload = rollup.build_rollup(paths)
        assert payload["reconciliation_maturity"]["order_history_mature"] is True
        assert payload["reconciliation_maturity"]["current_reconciliation_clean"] is False
        assert payload["reconciliation_maturity"]["mature_for_autonomy"] is False
        assert "reconciliation_maturity_not_met" in payload["blockers"]


if __name__ == "__main__":
    test_all_phase_a_gates_clean_but_autonomy_still_blocked()
    test_missing_phase_a_artifact_blocks_fail_closed()
    test_authority_drift_is_validation_error()
    test_fail_closed_phase_a_artifacts_count_as_installed_but_runtime_blocked()
    test_reconciliation_maturity_accepts_classifier_submitted_order_count()
    test_reconciliation_maturity_accepts_fresh_reconciliation_status()
    test_blocked_current_reconciliation_blocks_maturity()
    print("ok")
