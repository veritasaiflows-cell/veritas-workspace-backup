#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "actionable_improvement_queue.py"


def load_module():
    spec = importlib.util.spec_from_file_location("actionable_improvement_queue", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def configure(module, root: Path) -> None:
    tmp = root / "tmp"
    module.ROOT = root
    module.TMP = tmp
    module.OUT = tmp / "actionable-improvement-queue.json"
    module.MD_OUT = tmp / "actionable-improvement-queue.md"
    module.IMPROVEMENT_LEDGER = tmp / "improvement-ledger-current.json"
    module.WF88_FOLLOWUP_TRIAGE = tmp / "wf88-followup-debt-triage-packet.json"
    module.WF74_DECISION_DOCKET = tmp / "wf74-decision-docket.json"
    module.OWNER_GATED_QUEUE = tmp / "owner-gated-action-review-queue.json"
    module.PM_JOB_QUEUE = tmp / "pm-implementation-job-queue.json"
    module.WORKFLOW_FOLLOWUP_LEDGER = tmp / "workflow-implementation-followup-ledger.json"
    module.MAIN_ESCALATION_CONSUMER = tmp / "main-session-escalation-consumer.json"
    module.CRON_CONTROL_PACKET = tmp / "cron-control-packet.json"


def seed_routed_workspace(module) -> None:
    generated = module.utc_now()
    write_json(module.IMPROVEMENT_LEDGER, {
        "status": "warning",
        "generated_at_utc": generated,
        "summary": {"latest_open_count": 3},
        "latest_open_improvements": [
            {
                "source_key": "cron-1",
                "source_type": "wf74_improvement_opportunity",
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "category": "cron_migration",
                "priority": 92,
                "sla_status": "overdue",
                "decision": "follow_up_required_before_closure",
                "next_action": "Resolve current cron-control escalation.",
                "age_hours": 24,
            },
            {
                "source_key": "otel-1",
                "source_type": "wf74_improvement_opportunity",
                "title": "Review OTEL event-rate drift against the weekly baseline",
                "category": "collector_config",
                "priority": 88,
                "sla_status": "overdue",
                "decision": "follow_up_required_before_closure",
                "next_action": "Ask for exact authority before runtime config change.",
                "age_hours": 48,
            },
            {
                "source_key": "finance-1",
                "source_type": "wf74_auto_patch",
                "title": "Route finance response-quality gaps into repair proposals",
                "category": "finance_mutation",
                "priority": 66,
                "sla_status": "current",
                "decision": "owner_decision",
                "next_action": "Prepare owner decision packet.",
                "age_hours": 2,
            },
        ],
    })
    write_json(module.WF88_FOLLOWUP_TRIAGE, {
        "status": "warning",
        "generated_at_utc": generated,
        "active_followup_items": [
            {
                "source_key": "cron-1",
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "category": "cron_migration",
                "action_state": "active_successor_followup",
                "recommended_next_action": "Resolve current cron-control escalation.",
                "proof_artifacts": ["tmp/cron-control-packet.json"],
                "successor_id": "cron-cron-migration",
            }
        ],
    })
    write_json(module.WF74_DECISION_DOCKET, {
        "status": "warning",
        "generated_at_utc": generated,
        "rows": [
            {
                "source_id": "otel-1",
                "docket_id": "docket-otel",
                "title": "Review OTEL event-rate drift against the weekly baseline",
                "category": "collector_config",
                "priority": 88,
                "action_state": "hard_stop",
                "next_action": "Stop and ask Randall for exact authority.",
            },
            {
                "source_id": "finance-1",
                "docket_id": "docket-finance",
                "title": "Route finance response-quality gaps into repair proposals",
                "category": "finance_mutation",
                "priority": 66,
                "action_state": "owner_decision",
                "next_action": "Prepare owner decision card.",
            },
        ],
    })
    write_json(module.OWNER_GATED_QUEUE, {
        "status": "ok",
        "generated_at_utc": generated,
        "review_items": [
            {
                "item_id": "owner-finance",
                "title": "Route finance response-quality gaps into repair proposals",
                "gate": "finance_canon_portfolio_mutation",
                "priority": 66,
            }
        ],
    })
    write_json(module.PM_JOB_QUEUE, {"status": "ok", "generated_at_utc": generated, "jobs": []})
    write_json(module.WORKFLOW_FOLLOWUP_LEDGER, {"status": "ok", "generated_at_utc": generated, "followups": []})
    write_json(module.MAIN_ESCALATION_CONSUMER, {"status": "ok", "generated_at_utc": generated, "summary": {}})
    write_json(module.CRON_CONTROL_PACKET, {"status": "ok", "generated_at_utc": generated, "summary": {"blocked_count": 1, "escalation_signal_count": 1}})


def test_actionable_queue_routes_open_improvements() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(module, Path(tmpdir))
        seed_routed_workspace(module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "warning"
        assert packet["summary"]["action_item_count"] == 3
        assert packet["summary"]["orphan_count"] == 0
        assert packet["summary"]["active_followup_count"] == 1
        assert packet["summary"]["owner_decision_count"] == 2
        classes = {row["source_key"]: row["action_class"] for row in packet["action_items"]}
        assert classes["cron-1"] == "active_successor_followup"
        assert classes["otel-1"] == "owner_authority_required"
        assert classes["finance-1"] == "owner_decision"
        assert all(not row["missing_contract_fields"] for row in packet["action_items"])
        cron = next(row for row in packet["action_items"] if row["source_key"] == "cron-1")
        assert cron["proof_command"]
        assert cron["proof_artifact"]
        assert cron["close_condition"]


def test_actionable_queue_dedupes_duplicate_monitor_rows_with_traceability() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(module, Path(tmpdir))
        generated = module.utc_now()
        write_json(module.IMPROVEMENT_LEDGER, {
            "status": "warning",
            "generated_at_utc": generated,
            "latest_open_improvements": [
                {
                    "source_key": "cron-a",
                    "source_type": "wf74_improvement_opportunity",
                    "title": "Repair regressed cron signals after completed migration plan",
                    "category": "cron_migration",
                    "priority": 92,
                    "sla_status": "overdue",
                    "decision": "follow_up_required_before_closure",
                    "next_action": "Monitor only; cron control is green and escalation is zero. Reopen a repair lane only if cron blocked/escalation state returns.",
                },
                {
                    "source_key": "cron-b",
                    "source_type": "wf74_improvement_opportunity",
                    "title": "Repair regressed cron signals after completed migration plan",
                    "category": "cron_migration",
                    "priority": 92,
                    "sla_status": "overdue",
                    "decision": "follow_up_required_before_closure",
                    "next_action": "Monitor only; cron control is green and escalation is zero. Reopen a repair lane only if cron blocked/escalation state returns.",
                },
            ],
        })
        write_json(module.WF88_FOLLOWUP_TRIAGE, {
            "status": "warning",
            "generated_at_utc": generated,
            "active_followup_items": [
                {
                    "source_key": "cron-a",
                    "title": "Repair regressed cron signals after completed migration plan",
                    "category": "cron_migration",
                    "action_state": "monitor_only",
                    "recommended_next_action": "Monitor only; cron control is green and escalation is zero. Reopen a repair lane only if cron blocked/escalation state returns.",
                    "proof_artifacts": ["tmp/cron-control-packet.json"],
                    "successor_id": "cron-cron-migration",
                },
                {
                    "source_key": "cron-b",
                    "title": "Repair regressed cron signals after completed migration plan",
                    "category": "cron_migration",
                    "action_state": "monitor_only",
                    "recommended_next_action": "Monitor only; cron control is green and escalation is zero. Reopen a repair lane only if cron blocked/escalation state returns.",
                    "proof_artifacts": ["tmp/cron-control-packet.json"],
                    "successor_id": "cron-cron-migration",
                },
            ],
        })
        for path in [
            module.WF74_DECISION_DOCKET,
            module.OWNER_GATED_QUEUE,
            module.PM_JOB_QUEUE,
            module.WORKFLOW_FOLLOWUP_LEDGER,
            module.MAIN_ESCALATION_CONSUMER,
        ]:
            write_json(path, {"status": "ok", "generated_at_utc": generated})
        write_json(module.CRON_CONTROL_PACKET, {"status": "ok", "generated_at_utc": generated, "summary": {"blocked_count": 0, "escalation_signal_count": 0}})

        packet = module.build_packet()

        assert packet["summary"]["open_input_count"] == 2
        assert packet["summary"]["raw_action_item_count"] == 2
        assert packet["summary"]["action_item_count"] == 1
        assert packet["summary"]["duplicate_source_row_count"] == 1
        row = packet["action_items"][0]
        assert row["source_keys"] == ["cron-a", "cron-b"]
        assert row["duplicate_source_count"] == 1
        assert row["monitor_escalation_trigger"]
        assert row["close_condition"]
        assert row["proof_command"] == "python scripts\\wf88_followup_debt_triage_packet.py --write --write-md --validate"
        assert packet["validation"]["status"] == "ok"


def test_actionable_queue_blocks_orphaned_high_priority_item() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(module, Path(tmpdir))
        generated = module.utc_now()
        write_json(module.IMPROVEMENT_LEDGER, {
            "status": "warning",
            "generated_at_utc": generated,
            "latest_open_improvements": [
                {
                    "source_key": "orphan-1",
                    "title": "Unrouted high-priority debt",
                    "category": "workflow_maturity",
                    "priority": 90,
                    "sla_status": "overdue",
                    "decision": "follow_up_required_before_closure",
                    "next_action": "Route this item.",
                }
            ],
        })
        for path in [
            module.WF88_FOLLOWUP_TRIAGE,
            module.WF74_DECISION_DOCKET,
            module.OWNER_GATED_QUEUE,
            module.PM_JOB_QUEUE,
            module.WORKFLOW_FOLLOWUP_LEDGER,
            module.MAIN_ESCALATION_CONSUMER,
            module.CRON_CONTROL_PACKET,
        ]:
            write_json(path, {"status": "ok", "generated_at_utc": generated})

        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert packet["summary"]["orphan_count"] == 1
        assert "orphan_item:orphan-1:Unrouted high-priority debt" in packet["validation"]["errors"]


def main() -> int:
    test_actionable_queue_routes_open_improvements()
    test_actionable_queue_dedupes_duplicate_monitor_rows_with_traceability()
    test_actionable_queue_blocks_orphaned_high_priority_item()
    print("actionable improvement queue tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
