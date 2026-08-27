from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import main_session_greenkeeper_controller as greenkeeper


def clean_boundary() -> dict:
    return {
        "review_only": True,
        "code_mutation_allowed": False,
        "skill_application_allowed": False,
        "collector_config_mutation_allowed": False,
        "runtime_config_mutation_allowed": False,
        "finance_canon_or_portfolio_mutation_allowed": False,
        "capital_deployment_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "external_export_allowed": False,
        "owner_approval_inferred": False,
    }


def queue_packet(boundary: dict | None = None) -> dict:
    boundary = boundary or clean_boundary()
    return {
        "status": "ok",
        "validation": {"status": "ok"},
        "opportunities": [
            {
                "opportunity_id": "workflow_maturity-1",
                "category": "workflow_maturity",
                "title": "Convert workflow advancement blockers into implementation follow-ups",
                "priority": 89,
                "proposal_gate": "main_review_required",
                "recommended_action": "Route repeated workflow blockers into scoped implementation lanes.",
                "evidence": {"blocked_count": 4},
                "authority_boundary": boundary,
            },
            {
                "opportunity_id": "finance_mutation-1",
                "category": "finance_mutation",
                "title": "Route finance response-quality gaps into repair proposals",
                "priority": 86,
                "proposal_gate": "finance_repair_proposal_only",
                "recommended_action": "Create repair proposals for source-freshness/remediation gaps.",
                "evidence": {"source_freshness_blocked_count": 24},
                "authority_boundary": boundary,
            },
        ],
    }


def proposals_packet() -> dict:
    return {
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {"auto_apply_count": 0},
        "proposals": [
            {
                "proposal_id": "proposal-workflow",
                "source_opportunity_id": "workflow_maturity-1",
                "proposal_status": "main_review_required",
            },
            {
                "proposal_id": "proposal-finance",
                "source_opportunity_id": "finance_mutation-1",
                "proposal_status": "finance_repair_proposal_only",
            },
        ],
    }


def auto_patch_packet() -> dict:
    return {
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {"auto_apply_count": 0},
    }


def test_wf74_auto_handling_classifies_opportunities() -> None:
    actions = greenkeeper.classify_wf74_auto_handling(
        queue_packet(),
        proposals_packet(),
        auto_patch_packet(),
        {
            "status": "ok",
            "summary": {
                "source_freshness_blocked_count": 24,
                "remediation_tracks_needing_repair": 1,
            },
        },
        {"status": "ok", "summary": {"blocked_count": 4}},
        {"status": "ok", "summary": {"total_repair_conveyor_row_count": 200}},
    )
    by_id = {action["id"]: action for action in actions}
    assert by_id["wf74_workflow_maturity_auto_followup"]["classification"] == "auto_repair"
    assert "workflow_advancement_scorecard" in by_id["wf74_workflow_maturity_auto_followup"]["commands"]
    assert "wf74_auto_patch_proposer" in by_id["wf74_workflow_maturity_auto_followup"]["commands"]
    assert "tmp/workflow-blocker-followups.json" in by_id["wf74_workflow_maturity_auto_followup"]["source_artifacts"]
    assert by_id["wf74_workflow_maturity_auto_followup"]["owner_gate_required"] is False

    assert by_id["wf74_finance_quality_repair_routing"]["classification"] == "auto_repair"
    assert "trade_grade_decision_cards" in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert "finance_response_quality_slice" not in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert "finance_response_quality_slice" in by_id["wf74_finance_quality_repair_routing"]["post_repair_verification_commands"]
    assert "wf74_model_quality_collection_cron_runner" in by_id["wf74_finance_quality_repair_routing"]["post_repair_verification_commands"]
    assert "trade_grade_repair_conveyor" in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert "wf78_source_open_repair_executor" in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert "wf78_deployment_readiness_review" in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert "wf78_tier_weighted_freshness_resolver" in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert "finance_response_quality_repair_loop" in by_id["wf74_finance_quality_repair_routing"]["commands"]
    assert by_id["wf74_finance_quality_repair_routing"]["owner_gate_required"] is False


def test_wf74_auto_handling_blocks_authority_drift() -> None:
    bad_boundary = clean_boundary()
    bad_boundary["finance_canon_or_portfolio_mutation_allowed"] = True
    actions = greenkeeper.classify_wf74_auto_handling(
        queue_packet(bad_boundary),
        proposals_packet(),
        auto_patch_packet(),
        {"status": "ok", "summary": {}},
        {"status": "ok", "summary": {}},
        {"status": "ok", "summary": {}},
    )
    assert actions
    assert all(action["classification"] == "blocked" for action in actions)
    assert all(action["commands"] == [] for action in actions)


def test_wf74_auto_handling_blocks_unclean_sources() -> None:
    queue = queue_packet()
    queue["validation"] = {"status": "error"}
    actions = greenkeeper.classify_wf74_auto_handling(
        queue,
        proposals_packet(),
        auto_patch_packet(),
        {"status": "ok", "summary": {}},
        {"status": "ok", "summary": {}},
        {"status": "ok", "summary": {}},
    )
    assert actions == [{
        "id": "wf74_opportunity_sources_not_clean",
        "classification": "blocked",
        "severity": "high",
        "reason": "WF74 opportunity/proposal sources are not clean enough for automatic main-session handling",
        "source_reasons": ["queue_validation=error"],
        "commands": [],
        "owner_gate_required": True,
    }]


def test_wf78_source_open_no_work_packet_is_clean_wait_state() -> None:
    assert greenkeeper.wf78_source_open_work_packet_no_work_ok({
        "status": "blocked",
        "summary": {
            "work_item_count": 0,
            "packet_count": 0,
            "top_recommendation": "No packet work available.",
        },
        "validation": {"errors": ["no source-open work items found"]},
        "authority_boundary": {
            "review_only": True,
            "work_packet_generation_only": True,
            "capital_deployment_allowed": False,
            "trade_or_execution_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    })


def write_contract(directory: Path, name: str, contract: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(contract), encoding="utf-8")


def telegram_runner_contract(*, approved: bool) -> dict:
    contract = {
        "name": "WF85 owner Telegram radar",
        "enabled": True,
        "delivery": {"mode": "none"},
        "payload": {
            "message": (
                "Execute exactly this single command: "
                "python scripts\\wf85_paper_deployment_telegram_cron_runner.py "
                "--send --write --validate. Boundaries: review only."
            )
        },
        "authority_boundary": {
            "review_only": True,
            "owner_telegram_delivery_allowed": approved,
            "customer_or_public_delivery_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    if approved:
        contract["internal_delivery"] = {
            "mode": "telegram_via_runner",
            "runner_flag": "--send",
            "recipient_scope": "randall_owner_only",
            "delivery_only_review_notification": True,
            "cron_delivery_mode_remains_none": True,
            "customer_or_public_delivery_allowed": False,
            "approval_or_execution_authority_allowed": False,
        }
    return contract


def test_contract_lint_allows_approved_owner_only_telegram_runner() -> None:
    original_contracts = greenkeeper.CRON_CONTRACTS
    with TemporaryDirectory() as tmp_dir:
        greenkeeper.CRON_CONTRACTS = Path(tmp_dir)
        write_contract(greenkeeper.CRON_CONTRACTS, "approved.json", telegram_runner_contract(approved=True))
        try:
            assert greenkeeper.contract_lint() == []
        finally:
            greenkeeper.CRON_CONTRACTS = original_contracts


def test_contract_lint_keeps_unapproved_send_as_owner_decision() -> None:
    original_contracts = greenkeeper.CRON_CONTRACTS
    with TemporaryDirectory() as tmp_dir:
        greenkeeper.CRON_CONTRACTS = Path(tmp_dir)
        write_contract(greenkeeper.CRON_CONTRACTS, "unapproved.json", telegram_runner_contract(approved=False))
        try:
            findings = greenkeeper.contract_lint()
        finally:
            greenkeeper.CRON_CONTRACTS = original_contracts
    assert len(findings) == 1
    assert findings[0]["id"] == "enabled_contract_internal_send_with_delivery_none"
    assert findings[0]["classification"] == "owner_decision"
    assert findings[0]["owner_gate_required"] is True


if __name__ == "__main__":
    test_wf74_auto_handling_classifies_opportunities()
    test_wf74_auto_handling_blocks_authority_drift()
    test_wf74_auto_handling_blocks_unclean_sources()
    test_wf78_source_open_no_work_packet_is_clean_wait_state()
    test_contract_lint_allows_approved_owner_only_telegram_runner()
    test_contract_lint_keeps_unapproved_send_as_owner_decision()
    print("main_session_greenkeeper_controller tests passed")
