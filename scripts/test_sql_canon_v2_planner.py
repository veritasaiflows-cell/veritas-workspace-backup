from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_v2_planner.py"

spec = importlib.util.spec_from_file_location("sql_canon_v2_planner", SCRIPT)
assert spec and spec.loader
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


def test_v2_plan_preserves_authority_boundary() -> None:
    plan = planner.build_plan()
    assert plan["activation_allowed_by_this_artifact"] is False
    assert plan["sql_writes_allowed_by_this_artifact"] is False
    assert plan["consumer_behavior_change_allowed_by_this_artifact"] is False
    assert plan["owner_approval_inferred"] is False
    assert plan["trade_or_account_action_allowed"] is False
    assert plan["paper_trade_authority_allowed"] is False
    assert plan["live_trade_authority_allowed"] is False
    assert plan["money_movement_allowed"] is False


def test_v2_plan_matches_current_265_row_boundary() -> None:
    plan = planner.build_plan()
    checks = planner.validate_plan(plan)
    failed = [check for check in checks if not check["ok"]]
    assert not failed
    cache = plan["current_state"]["canon_cache"]
    assert cache["row_count"] == 265
    assert cache["authority_boundaries"] == {
        "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority": 13,
        "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority": 252,
    }


def test_v2_plan_contains_future_candidate_and_blocked_execution_family() -> None:
    plan = planner.build_plan()
    families = {family["family"]: family for family in plan["candidate_families"]}
    assert families["analyst_consensus_metadata"]["status"] == "future_candidate_review_support_only"
    assert families["sizing_sleeve_cash_risk_rule_execution"]["status"] == "blocked_from_sql_canon_v2"
    assert len(plan["v2_phases"]) >= 5
