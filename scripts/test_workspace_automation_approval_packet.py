from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workspace_automation_approval_packet.py"
REPORT = ROOT / "tmp" / "workspace-automation-approval-packet.json"
REPORT_MD = ROOT / "tmp" / "workspace-automation-approval-packet.md"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("workspace_automation_approval_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_automation_approval_packet_is_bounded() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--write-md", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert REPORT.exists()
    assert REPORT_MD.exists()

    packet = json.loads(REPORT.read_text(encoding="utf-8"))
    assert packet["schema"] == "veritas.workspace_automation_approval_packet.v1"
    assert packet["validation"]["status"] == "ok"
    assert len(packet["implementation_plan"]) == 9

    areas = {row["area"] for row in packet["implementation_plan"]}
    assert areas == {
        "Workspace cleanup",
        "Cron efficiency",
        "Session startup",
        "Session closeout",
        "Helper lanes",
        "Repeated friction",
        "Token/cost control",
        "Finance OS",
        "Security/runtime",
    }

    boundary = packet["authority_boundary"]
    for flag in (
        "delete_archive_move_allowed",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "sql_or_source_mutation_allowed",
        "canon_or_portfolio_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        assert boundary[flag] is False, flag

    decisions = {item["decision"] for item in packet["owner_approval_items"]}
    assert "Cleanup apply authority" in decisions
    assert "Cron prefilter patch queue" in decisions
    assert "Finance OS non-capital expansion" in decisions
    cleanup = packet["area_state"]["workspace_cleanup"]
    assert cleanup["tmp_cleanup_protected_violation_count"] in {0, None}
    token_control = packet["area_state"]["token_cost_control"]
    assert "api_equivalent_cost_usd" in token_control
    assert "api_equivalent_estimate_status" in token_control
    assert "api_equivalent_cost_rows" in token_control
    assert "api_equivalent_cost_event_coverage_percent" in token_control
    assert "estimated_chatgpt_credits" in token_control
    assert "chatgpt_credit_estimate_status" in token_control
    assert "estimated_chatgpt_credit_rows" in token_control
    assert "actual_billed_cost_usd" in token_control
    assert "oauth_capacity_control" in token_control
    assert "usage_pace" in token_control


def test_token_prefilter_queue_is_not_ready_with_blocked_scorecard_or_bridge() -> None:
    module = load_module()
    artifacts = {name: {} for name in module.INPUTS}
    artifacts["token_efficiency"] = {
        "status": "blocked",
        "validation": {"status": "blocked"},
        "summary": {"api_call_reduction_candidate_count": 3},
    }
    artifacts["implementation_token_bridge"] = {
        "status": "blocked",
        "validation": {"status": "error"},
        "summary": {"implementation_token_gap_count": 3},
    }

    area_state = module.current_area_state(artifacts)
    approval_item = next(
        item
        for item in module.owner_approval_items(area_state)
        if item["decision"] == "Cron prefilter patch queue"
    )
    token_plan = next(
        item
        for item in module.area_plan(area_state)
        if item["area"] == "Token/cost control"
    )

    assert area_state["token_cost_control"]["prefilter_telemetry_ready"] is False
    assert approval_item["ready_now"] is False
    assert token_plan["status"] == "token_telemetry_repair_required"
