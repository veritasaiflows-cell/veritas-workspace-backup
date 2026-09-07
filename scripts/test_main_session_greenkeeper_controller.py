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
                "opportunity_id": "workflow-maturity-1",
                "category": "workflow_maturity",
                "title": "Convert workflow advancement blockers into implementation follow-ups",
                "priority": 89,
                "proposal_gate": "main_review_required",
                "recommended_action": "Route repeated workflow blockers into scoped implementation lanes.",
                "authority_boundary": boundary,
            },
            {
                "opportunity_id": "retired-finance-route",
                "category": "finance_mutation",
                "title": "Legacy finance repair route",
                "priority": 99,
                "proposal_gate": "finance_repair_proposal_only",
                "authority_boundary": boundary,
            },
        ],
    }


def proposals_packet() -> dict:
    return {
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {"auto_apply_count": 0},
        "proposals": [{"proposal_id": "proposal-workflow", "source_opportunity_id": "workflow-maturity-1"}],
    }


def auto_patch_packet() -> dict:
    return {"status": "ok", "validation": {"status": "ok"}, "summary": {"auto_apply_count": 0}}


def test_wf74_keeps_generic_followup_and_suppresses_retired_finance() -> None:
    actions = greenkeeper.classify_wf74_auto_handling(
        queue_packet(), proposals_packet(), auto_patch_packet(), {"status": "ok"}
    )
    assert [row["id"] for row in actions] == ["wf74_workflow_maturity_auto_followup"]
    assert actions[0]["classification"] == "auto_repair"
    assert "workflow_advancement_scorecard" in actions[0]["commands"]


def test_wf74_blocks_authority_drift() -> None:
    bad = clean_boundary()
    bad["finance_canon_or_portfolio_mutation_allowed"] = True
    actions = greenkeeper.classify_wf74_auto_handling(
        queue_packet(bad), proposals_packet(), auto_patch_packet(), {"status": "ok"}
    )
    assert len(actions) == 1
    assert actions[0]["classification"] == "blocked"
    assert actions[0]["commands"] == []


def test_wf74_blocks_unclean_sources() -> None:
    queue = queue_packet()
    queue["validation"] = {"status": "error"}
    actions = greenkeeper.classify_wf74_auto_handling(
        queue, proposals_packet(), auto_patch_packet(), {"status": "ok"}
    )
    assert actions[0]["id"] == "wf74_opportunity_sources_not_clean"
    assert actions[0]["classification"] == "blocked"


def test_alerts_os_classifier_is_fail_closed() -> None:
    clean = greenkeeper.classify_alerts_os({"status": "ok", "blocked_proofs": []})
    assert clean[0]["id"] == "alerts_os_green"
    blocked = greenkeeper.classify_alerts_os({
        "status": "blocked",
        "blocked_proofs": ["quote_snapshot", "pivot_validator"],
    })
    by_id = {row["id"]: row for row in blocked}
    assert by_id["alerts_os_proof_refresh"]["commands"] == [
        "alerts_recommendations_midday_chain", "alerts_os_pivot_validator"
    ]
    assert by_id["alerts_os_boundary_blocked"]["classification"] == "main_handoff"


def test_retired_pm_handoff_is_suppressed() -> None:
    pm = {
        "summary": {
            "pm_readiness": {},
            "pm_cockpit_source_health": {},
            "implementation_queue": {},
            "top_next_action": {"action_id": "wf87-readiness"},
            "main_session_handoff": {"signal_class": "MAIN_SESSION_REQUIRED", "selected_action": "wf87-readiness"},
        }
    }
    assert greenkeeper.classify_pm(pm, {}) == [{
        "id": "pm_green",
        "classification": "no_reply",
        "severity": "info",
        "reason": "PM is green or warning-only with no blocked jobs",
        "commands": [],
        "owner_gate_required": False,
    }]


def write_contract(directory: Path, name: str, contract: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(contract), encoding="utf-8")


def telegram_runner_contract(*, approved: bool) -> dict:
    contract = {
        "name": "Owner review notifier",
        "enabled": True,
        "delivery": {"mode": "none"},
        "payload": {"message": "Execute exactly this single command: python scripts\\owner_review_notifier.py --send --write --validate."},
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
            "delivery_only_review_notification": True,
            "cron_delivery_mode_remains_none": True,
            "customer_or_public_delivery_allowed": False,
            "approval_or_execution_authority_allowed": False,
        }
    return contract


def test_contract_lint_preserves_owner_gate() -> None:
    original = greenkeeper.CRON_CONTRACTS
    with TemporaryDirectory() as tmpdir:
        greenkeeper.CRON_CONTRACTS = Path(tmpdir)
        try:
            write_contract(greenkeeper.CRON_CONTRACTS, "approved.json", telegram_runner_contract(approved=True))
            assert greenkeeper.contract_lint() == []
            write_contract(greenkeeper.CRON_CONTRACTS, "unapproved.json", telegram_runner_contract(approved=False))
            findings = greenkeeper.contract_lint()
            assert len(findings) == 1
            assert findings[0]["classification"] == "owner_decision"
        finally:
            greenkeeper.CRON_CONTRACTS = original


if __name__ == "__main__":
    test_wf74_keeps_generic_followup_and_suppresses_retired_finance()
    test_wf74_blocks_authority_drift()
    test_wf74_blocks_unclean_sources()
    test_alerts_os_classifier_is_fail_closed()
    test_retired_pm_handoff_is_suppressed()
    test_contract_lint_preserves_owner_gate()
    print("main_session_greenkeeper_controller tests passed")
