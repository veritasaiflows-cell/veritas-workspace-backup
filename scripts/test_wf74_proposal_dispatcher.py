#!/usr/bin/env python3
"""Regression tests for the WF74 proposal dispatcher."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "scripts" / "wf74_proposal_dispatcher.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf74_proposal_dispatcher_test", DISPATCHER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_packet(path: Path, payload: dict) -> Path:
    atomic_write_json(path, payload)
    return path


def base_files(root: Path) -> SimpleNamespace:
    docket = write_packet(root / "docket.json", {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "rows": [],
    })
    auto_patch = write_packet(root / "auto-patch.json", {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "summary": {"auto_apply_count": 0, "auto_apply_candidate_count": 0},
        "patch_plans": [],
        "skill_workshop_requests": [],
        "owner_gated_reviews": [],
    })
    router = write_packet(root / "router.json", {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "pm_job_candidates": [],
    })
    pm_queue = write_packet(root / "pm-queue.json", {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "jobs": [],
    })
    owner_queue = write_packet(root / "owner-queue.json", {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "items": [],
    })
    cron_control = write_packet(root / "cron.json", {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "summary": {
            "blocked_count": 0,
            "escalation_signal_count": 0,
            "requires_attention_count": 0,
            "should_wake_main_session": False,
        },
    })
    return SimpleNamespace(
        docket=str(docket),
        auto_patch=str(auto_patch),
        router=str(router),
        pm_queue=str(pm_queue),
        owner_queue=str(owner_queue),
        cron_control=str(cron_control),
        out=str(root / "out.json"),
        md_out=str(root / "out.md"),
        write=False,
        write_md=False,
        validate=True,
        print_json=False,
    )


def dispatches_by_title(packet: dict) -> dict[str, dict]:
    return {row["title"]: row for row in packet["dispatch_rows"]}


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_active_cron_regression_routes_to_pm(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        args = base_files(root)
        atomic_write_json(Path(args.cron_control), {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {"blocked_count": 2, "escalation_signal_count": 2, "should_wake_main_session": True},
        })
        atomic_write_json(Path(args.docket), {
            "status": "ok",
            "validation": {"status": "ok"},
            "rows": [{
                "source_id": "cron_migration-1",
                "source_kind": "opportunity",
                "title": "Repair regressed cron signals after completed migration plan",
                "category": "cron_migration",
                "priority": 92,
                "action_state": "fix_now",
            }],
        })
        atomic_write_json(Path(args.router), {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [{
                "job_id": "pm-wf74-cron-migration-regression-repair",
                "source_key": "cron_migration-1",
                "title": "Repair regressed cron signals after completed migration plan",
                "source_category": "cron_migration",
                "status": "ready_for_main_or_helper",
                "proof_commands": ["python scripts\\cron_control_packet.py --write --validate"],
            }],
        })
        packet = module.build_payload(args)
        row = dispatches_by_title(packet)["Repair regressed cron signals after completed migration plan"]
        expect(row["dispatch_destination"] == "pm_job", f"expected PM dispatch, got {row}", errors)
        expect(packet["validation"]["status"] == "ok", f"packet should validate ok: {packet['validation']}", errors)


def test_cron_green_residue_stays_monitor_only(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        args = base_files(root)
        atomic_write_json(Path(args.docket), {
            "status": "ok",
            "validation": {"status": "ok"},
            "rows": [{
                "source_id": "cron_migration-1",
                "source_kind": "opportunity",
                "title": "Repair regressed cron signals after completed migration plan",
                "category": "cron_migration",
                "priority": 92,
                "action_state": "fix_now",
            }],
        })
        packet = module.build_payload(args)
        row = dispatches_by_title(packet)["Repair regressed cron signals after completed migration plan"]
        expect(row["dispatch_destination"] == "monitor_only", f"green cron should be monitor-only: {row}", errors)


def test_pm_completion_ledger_suppression_becomes_validator_ticket(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        args = base_files(root)
        atomic_write_json(Path(args.cron_control), {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {"blocked_count": 1, "escalation_signal_count": 1, "should_wake_main_session": True},
        })
        atomic_write_json(Path(args.docket), {
            "status": "ok",
            "validation": {"status": "ok"},
            "rows": [{
                "source_id": "cron_migration-1",
                "source_kind": "opportunity",
                "title": "Repair regressed cron signals after completed migration plan",
                "category": "cron_migration",
                "priority": 92,
                "action_state": "fix_now",
            }],
        })
        atomic_write_json(Path(args.router), {
            "status": "ok",
            "validation": {"status": "ok"},
            "pm_job_candidates": [{
                "job_id": "pm-wf74-cron-migration-regression-repair",
                "source_key": "cron_migration-1",
                "title": "Repair regressed cron signals after completed migration plan",
                "source_category": "cron_migration",
                "status": "ready_for_main_or_helper",
            }],
        })
        atomic_write_json(Path(args.pm_queue), {
            "status": "ok",
            "validation": {"status": "ok"},
            "jobs": [{
                "job_id": "pm-wf74-cron-migration-regression-repair",
                "status": "completed_by_ledger",
                "allowed_execution_mode": "completed_by_ledger_resolved",
            }],
        })
        packet = module.build_payload(args)
        row = dispatches_by_title(packet)["Repair regressed cron signals after completed migration plan"]
        expect(row["dispatch_destination"] == "validator_ticket", f"suppression should be validator ticket: {row}", errors)
        expect(row["dispatch_reason"] == "fresh_router_candidate_suppressed_by_pm_completion_ledger", "wrong suppression reason", errors)
        expect(packet["summary"]["pm_ledger_suppression_ticket_count"] >= 1, "suppression count should be nonzero", errors)


def test_skill_and_owner_rows_do_not_apply(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        args = base_files(root)
        atomic_write_json(Path(args.docket), {
            "status": "ok",
            "validation": {"status": "ok"},
            "rows": [{
                "source_id": "skill-v2",
                "source_kind": "skill_workshop_request",
                "title": "Update disciplined implementation skill",
                "category": "skill_application",
                "priority": 80,
                "action_state": "skill_proposal",
            }],
        })
        atomic_write_json(Path(args.owner_queue), {
            "status": "ok",
            "validation": {"status": "ok"},
            "items": [{
                "item_id": "paper-execution-gate",
                "gate": "execution",
                "category": "execution",
                "title": "Paper/live execution is blocked by circuit breaker proof",
                "decision_required": True,
                "required_owner_decision": "keep_blocked_until_fresh_guard_proof",
            }],
        })
        packet = module.build_payload(args)
        rows = dispatches_by_title(packet)
        expect(rows["Update disciplined implementation skill"]["dispatch_destination"] == "skill_workshop_proposal", "skill row should be skill proposal", errors)
        expect(rows["Paper/live execution is blocked by circuit breaker proof"]["dispatch_destination"] == "owner_gated_packet", "owner row should be owner packet", errors)
        for row in packet["dispatch_rows"]:
            expect(row["direct_apply_allowed"] is False, "dispatch row must not allow apply", errors)
            expect(row["direct_skill_write_allowed"] is False, "dispatch row must not allow skill write", errors)


def test_forbidden_capture_blocks_and_auto_apply_blocks_packet(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        args = base_files(root)
        atomic_write_json(Path(args.docket), {
            "status": "ok",
            "validation": {"status": "ok"},
            "rows": [{
                "source_id": "raw-capture",
                "source_kind": "durable_improvement",
                "title": "Capture raw prompt and tool payload data",
                "category": "otel_learning_loop",
                "priority": 99,
                "action_state": "monitor_only",
            }],
        })
        atomic_write_json(Path(args.auto_patch), {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {"auto_apply_count": 1, "auto_apply_candidate_count": 0},
        })
        packet = module.build_payload(args)
        row = dispatches_by_title(packet)["Capture raw prompt and tool payload data"]
        expect(row["dispatch_destination"] == "blocked_no_dispatch", "raw capture should block dispatch", errors)
        expect(packet["validation"]["status"] == "blocked", "auto-apply residue should block packet validation", errors)
        expect("auto_patch_auto_apply_count_must_be_zero" in packet["validation"]["errors"], "expected auto-apply error", errors)


def test_auto_patch_plan_without_pm_candidate_routes_to_validator_ticket(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        args = base_files(root)
        atomic_write_json(Path(args.auto_patch), {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {"auto_apply_count": 0, "auto_apply_candidate_count": 0},
            "patch_plans": [{
                "plan_id": "wf74-auto-patch-validator-drag",
                "title": "Reduce validator drag for normal implementation passes",
                "category": "code_mutation",
                "priority": 72,
                "route": "patch_plan",
                "risk_class": "validator_routing_metadata",
                "validation_commands": ["python scripts\\changed_file_validator_router.py --write --validate"],
            }],
        })
        packet = module.build_payload(args)
        row = dispatches_by_title(packet)["Reduce validator drag for normal implementation passes"]
        expect(row["dispatch_destination"] == "validator_ticket", f"patch plan without PM candidate should be validator ticket: {row}", errors)
        expect(row["dispatch_reason"] == "auto_patch_plan_requires_pm_job_candidate", f"wrong patch-plan reason: {row}", errors)
        expect(row["pm_job_id"] is None, "validator ticket should not fabricate a PM job id", errors)
        expect(row["direct_apply_allowed"] is False, "patch plan dispatch must not allow direct apply", errors)
        expect(packet["validation"]["status"] == "ok", f"packet should validate ok: {packet['validation']}", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_active_cron_regression_routes_to_pm,
        test_cron_green_residue_stays_monitor_only,
        test_pm_completion_ledger_suppression_becomes_validator_ticket,
        test_skill_and_owner_rows_do_not_apply,
        test_forbidden_capture_blocks_and_auto_apply_blocks_packet,
        test_auto_patch_plan_without_pm_candidate_routes_to_validator_ticket,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: wf74 proposal dispatcher tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
