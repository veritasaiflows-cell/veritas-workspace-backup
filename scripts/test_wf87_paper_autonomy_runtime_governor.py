from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf87_paper_autonomy_runtime_governor.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf87_paper_autonomy_runtime_governor", SCRIPT)
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
    module.ROLLUP = module.TMP / "wf87-v2-readiness-rollup.json"
    module.GATE_EXPLANATION = module.TMP / "wf87-runtime-gate-explanation.json"
    module.WF85_PACKET = module.TMP / "wf85-decision-os-review-packet.json"
    module.WF67_GUARD = module.TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
    module.OUT = module.TMP / "wf87-paper-autonomy-runtime-governor.json"
    module.MD_OUT = module.TMP / "wf87-paper-autonomy-runtime-governor.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    write_json(module.ROLLUP, {
        "status": "phase_a_hardening_implemented_runtime_blocked",
        "phase_readiness": {
            "phase_c_autonomous_paper_buy_ready": False,
            "phase_e_live_ready": False,
        },
        "shadow_threshold": {
            "clean_shadow_decision_count": 21,
            "required_clean_decisions": 20,
            "unique_clean_market_sessions": 7,
            "required_clean_market_sessions": 5,
            "threshold_met": True,
        },
        "shadow_outcome_calibration": {
            "status": "ok",
            "scoreable_decision_count": 22,
            "pending_regular_session_followup_count": 0,
            "decision_quality_claim_allowed_now": False,
            "model_performance_claim_allowed_now": False,
        },
        "assisted_paper_cadence": {
            "status": "outside_fresh_gate_window",
            "owner_policy_approved": True,
            "exact_order_approval_required_each_time": True,
            "all_time_assisted_attempt_count": 2,
            "all_time_assisted_terminal_attempt_count": 2,
            "all_time_assisted_maturity_rep_count": 0,
            "all_time_assisted_filled_round_trip_count": 0,
        },
        "reconciliation_maturity": {
            "status": "ok",
            "order_history_mature": True,
            "current_reconciliation_clean": True,
            "mature_for_autonomy": True,
            "submitted_source_count": 12,
            "unresolved_count": 0,
        },
        "blocker_taxonomy": {
            "maturity_blockers": [],
            "fail_closed_at_rest": ["approval_freshness_ttl_status_not_allowed:blocked"],
            "runtime_blockers": [],
            "binding_blockers": [],
            "classification_note": "expected fail closed at rest",
        },
        "gates": [
            {
                "name": "approval_freshness_ttl",
                "status": "blocked",
                "runtime_status": "blocked",
                "path": "tmp/wf87-approval-freshness-ttl.json",
                "blockers": ["approval_freshness_ttl_status_not_allowed:blocked"],
                "runtime_blockers": [],
            }
        ],
    })
    write_json(module.GATE_EXPLANATION, {
        "status": "runtime_blocked_explained",
        "summary": {
            "blocker_count": 1,
            "unexplained_blocker_count": 0,
        },
    })
    write_json(module.WF85_PACKET, {
        "status": "warning",
        "summary": {
            "card_count": 300,
            "approval_card_draft_count": 0,
            "approval_gate_review_ready_count": 0,
            "capital_review_ready_count": 0,
            "wf67_paper_guard_status": "blocked",
            "wf67_paper_guard_fresh": False,
            "wf67_paper_guard_clean": False,
            "source_open_status_counts": {"blocked": 42},
            "next_safe_action": "repair source-open blockers",
        },
    })
    write_json(module.WF67_GUARD, {
        "status": "blocked",
        "verdict": "blocked",
        "ready_for_paper_submit_cancel": False,
        "live_trading_allowed": False,
        "money_movement_allowed": False,
        "summary": {"critical": 1},
    })


def test_governor_narrows_wf87_and_keeps_execution_blocked() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["shadow_threshold_met"] is True
        assert packet["summary"]["reconciliation_maturity_met"] is True
        assert packet["summary"]["assisted_filled_round_trips_all_time"] == 0
        assert packet["summary"]["required_assisted_filled_round_trips_for_phase_c_proposal"] == 5
        assert packet["summary"]["runtime_status"] == "blocked"
        assert packet["summary"]["phase_c_autonomous_paper_buy_ready"] is False
        assert packet["summary"]["execution_allowed"] is False
        assert packet["authority_boundary"]["paper_or_live_execution_allowed"] is False


def test_governor_exports_learning_signal_to_wf88_without_owning_learning() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        split = packet["responsibility_split"]
        export = packet["wf88_feedback_export"]
        assert "coding/behavior portability and cross-workflow learning" in split["wf88_owns"]
        assert packet["authority_boundary"]["wf88_learning_owner"] is False
        assert export["export_allowed"] is True
        assert export["shadow_scoreable_decision_count"] == 22
        assert export["model_performance_claim_allowed_now"] is False


if __name__ == "__main__":
    test_governor_narrows_wf87_and_keeps_execution_blocked()
    test_governor_exports_learning_signal_to_wf88_without_owning_learning()
    print("wf87 paper autonomy runtime governor tests passed")
