#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "no_orphan_validator.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("no_orphan_validator", SCRIPT)
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
    module.OUT = tmp / "no-orphan-validator.json"
    module.QUEUE_PACKET = tmp / "actionable-improvement-queue.json"


def test_no_orphan_validator_passes_routed_queue_with_visible_warnings() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(module, Path(tmpdir))
        write_json(module.QUEUE_PACKET, {
            "schema": "veritas.actionable_improvement_queue.v1",
            "status": "actionable_queue_warning_no_apply_authority",
            "generated_at_utc": module.utc_now(),
            "validation": {"status": "warning", "errors": [], "warnings": ["owner_decisions_visible:1"]},
            "summary": {
                "action_item_count": 4,
                "orphan_count": 0,
                "high_priority_orphan_count": 0,
                "overdue_orphan_count": 0,
                "missing_contract_count": 0,
                "high_priority_missing_contract_count": 0,
                "owner_decision_count": 1,
                "hard_stop_count": 0,
                "monitor_only_count": 2,
                "top_action_title": "Route blocked cron signals",
                "top_action_destination": "wf88_followup_debt_triage",
                "top_next_action": "Resolve cron escalation.",
            },
        })

        packet = module.build_packet()

        assert packet["validation"]["status"] == "warning"
        assert packet["summary"]["validation_passed"] is True
        assert packet["summary"]["orphan_count"] == 0


def test_no_orphan_validator_treats_contract_complete_monitor_rows_as_ok() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(module, Path(tmpdir))
        write_json(module.QUEUE_PACKET, {
            "schema": "veritas.actionable_improvement_queue.v1",
            "status": "actionable_queue_ready_no_apply_authority",
            "generated_at_utc": module.utc_now(),
            "validation": {"status": "ok", "errors": [], "warnings": []},
            "summary": {
                "action_item_count": 3,
                "orphan_count": 0,
                "high_priority_orphan_count": 0,
                "overdue_orphan_count": 0,
                "missing_contract_count": 0,
                "high_priority_missing_contract_count": 0,
                "monitor_contract_gap_count": 0,
                "owner_decision_count": 0,
                "hard_stop_count": 0,
                "monitor_only_count": 3,
                "duplicate_source_row_count": 2,
            },
        })

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["status"] == "no_orphan_validation_ready"
        assert packet["summary"]["validation_passed"] is True
        assert packet["summary"]["duplicate_source_row_count"] == 2


def test_no_orphan_validator_blocks_orphaned_queue() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(module, Path(tmpdir))
        write_json(module.QUEUE_PACKET, {
            "schema": "veritas.actionable_improvement_queue.v1",
            "status": "actionable_queue_warning_no_apply_authority",
            "generated_at_utc": module.utc_now(),
            "validation": {"status": "blocked", "errors": ["orphan_item:abc"], "warnings": []},
            "summary": {
                "action_item_count": 1,
                "orphan_count": 1,
                "high_priority_orphan_count": 1,
                "overdue_orphan_count": 1,
                "missing_contract_count": 1,
                "high_priority_missing_contract_count": 1,
            },
        })

        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert packet["summary"]["validation_passed"] is False
        assert "open_improvement_orphans:1" in packet["validation"]["errors"]


def main() -> int:
    test_no_orphan_validator_passes_routed_queue_with_visible_warnings()
    test_no_orphan_validator_treats_contract_complete_monitor_rows_as_ok()
    test_no_orphan_validator_blocks_orphaned_queue()
    print("no-orphan validator tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
