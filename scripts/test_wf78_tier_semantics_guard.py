from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf78_tier_semantics_guard.py"

spec = importlib.util.spec_from_file_location("wf78_tier_semantics_guard", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def safe_production_summary(production_count: int = 0) -> dict:
    return {
        "production_grade_candidate_count": production_count,
        "answer_consumer_cutover_allowed": False,
    }


def safe_production_authority(**overrides: object) -> dict:
    authority = {
        "answer_consumer_cutover_allowed": False,
        "customer_or_external_delivery_allowed": False,
        "capital_deployment_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_allowed": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }
    authority.update(overrides)
    return authority


def safe_depth_summary(**overrides: object) -> dict:
    summary = {
        "decision_grade_allowed_count": 2,
        "customer_output_allowed": False,
        "capital_or_execution_allowed": False,
    }
    summary.update(overrides)
    return summary


def safe_depth_authority(**overrides: object) -> dict:
    authority = {
        "customer_or_external_output_allowed": False,
        "capital_deployment_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "owner_approval_inferred": False,
    }
    authority.update(overrides)
    return authority


def boundary_detail(
    production_summary: dict | None = None,
    production_authority: dict | None = None,
    depth_summary: dict | None = None,
    depth_authority: dict | None = None,
) -> dict:
    return module.decision_grade_boundary_detail(
        production_summary or safe_production_summary(),
        production_authority or safe_production_authority(),
        depth_summary or safe_depth_summary(),
        depth_authority or safe_depth_authority(),
    )


def test_internal_decision_grade_count_is_allowed_when_all_external_authority_stays_false() -> None:
    detail = boundary_detail()

    assert detail["safe"] is True
    assert detail["decision_grade_allowed_count"] == 2
    assert detail["production_grade_candidate_count"] == 0
    assert detail["non_false_flags"] == {}


def test_production_grade_candidates_still_block_semantics_guard() -> None:
    detail = boundary_detail(production_summary=safe_production_summary(production_count=1))

    assert detail["safe"] is False
    assert detail["production_grade_candidate_count"] == 1


def test_customer_cutover_or_execution_flags_block_semantics_guard() -> None:
    customer_detail = boundary_detail(
        production_authority=safe_production_authority(answer_consumer_cutover_allowed=True)
    )
    execution_detail = boundary_detail(
        depth_summary=safe_depth_summary(capital_or_execution_allowed=True)
    )

    assert customer_detail["safe"] is False
    assert customer_detail["non_false_flags"]["production_authority.answer_consumer_cutover_allowed"] is True
    assert execution_detail["safe"] is False
    assert execution_detail["non_false_flags"]["depth_summary.capital_or_execution_allowed"] is True


def test_router_lineage_detects_router_change_after_publication() -> None:
    published_router = {
        "status": "ok",
        "generated_at_utc": "2026-08-08T12:00:00Z",
        "rows": [{"ticker": "NVDA", "auto_tier": "Tier B", "auto_state": "B-VALIDATED"}],
    }
    timestamp_only_refresh = {
        **published_router,
        "generated_at_utc": "2026-08-08T12:05:00Z",
    }
    changed_router = {
        **timestamp_only_refresh,
        "rows": [{"ticker": "NVDA", "auto_tier": "Tier A", "auto_state": "A-READY"}],
    }

    published_lineage = module.source_router_lineage(published_router)
    timestamp_only_lineage = module.source_router_lineage(timestamp_only_refresh)
    changed_lineage = module.source_router_lineage(changed_router)

    assert published_lineage["content_sha256"] == timestamp_only_lineage["content_sha256"]
    assert published_lineage["content_sha256"] != changed_lineage["content_sha256"]
    assert module.router_lineage_matches(published_lineage, timestamp_only_lineage) is False
    assert module.router_lineage_matches(published_lineage, changed_lineage) is False


if __name__ == "__main__":
    test_internal_decision_grade_count_is_allowed_when_all_external_authority_stays_false()
    test_production_grade_candidates_still_block_semantics_guard()
    test_customer_cutover_or_execution_flags_block_semantics_guard()
    test_router_lineage_detects_router_change_after_publication()
    print("wf78_tier_semantics_guard tests passed")
