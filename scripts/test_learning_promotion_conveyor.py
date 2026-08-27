#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "scripts" / "learning_promotion_classifier.py"
REVIEW = ROOT / "scripts" / "learning_promotion_review_packet.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_inputs() -> dict:
    return {
        "actionable_queue": {"action_items": []},
        "wf74_docket": {},
        "wf88_wiki": {"action_items": []},
        "auto_patch": {},
        "improvement_ledger": {"summary": {}},
        "model_quality": {"validation": {"status": "ok"}},
        "token_efficiency": {"summary": {}},
        "implementation_token_bridge": {"summary": {}},
        "recommendation_ledger": {"validation": {"status": "ok"}},
    }


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_cron_signal_becomes_pm_candidate(errors: list[str]) -> None:
    module = load_module(CLASSIFIER, "learning_promotion_classifier_test_cron")
    inputs = base_inputs()
    inputs["actionable_queue"]["action_items"].append({
        "item_id": "cron_signal_learning_input",
        "title": "cron_signal_learning_input",
        "category": "otel_learning_loop",
        "priority": 75,
        "action_class": "monitor_only",
        "next_action": "Produce a dry-run migration plan with contract validation, rollback, and post-change freshness proof before mutating live schedules.",
        "proof_artifacts": ["tmp/otel-learning-loop.json", "tmp/cron-control-packet.json"],
    })
    packet = module.classify_signals(inputs)
    target_by_title = {row["title"]: row["promotion_target"] for row in packet["candidates"]}
    expect(target_by_title.get("cron_signal_learning_input") == "pm_implementation_job", "cron dry-run signal should route to PM implementation candidate", errors)
    expect(packet["summary"]["direct_apply_count"] == 0, "cron signal must not allow direct apply", errors)
    expect(packet["validation"]["status"] == "ok", f"cron packet should validate ok: {packet['validation']}", errors)


def test_execution_guardrail_becomes_skill_candidate_without_apply(errors: list[str]) -> None:
    module = load_module(CLASSIFIER, "learning_promotion_classifier_test_skill")
    inputs = base_inputs()
    inputs["actionable_queue"]["action_items"].append({
        "item_id": "execution-c025a631de11",
        "title": "Maintain execution as proposal-only and exact-owner-gated",
        "category": "execution",
        "priority": 35,
        "action_class": "monitor_only",
        "next_action": "Continue producing approval-ready cards and guard proof only; submit/cancel/replace remains separate exact approval.",
        "proof_artifacts": ["tmp/wf74-improvement-opportunity-queue.json"],
    })
    packet = module.classify_signals(inputs)
    rows = [row for row in packet["candidates"] if row["source_id"] == "execution-c025a631de11"]
    expect(len(rows) == 1, "expected execution candidate", errors)
    if rows:
        row = rows[0]
        expect(row["promotion_target"] == "skill_workshop_proposal", "execution guardrail should be a skill proposal candidate", errors)
        expect(row["suggested_skill"] == "automation-hardening-manager", "execution guardrail should route to automation hardening skill", errors)
        expect(row["direct_skill_write_allowed"] is False, "skill candidate must not write skills directly", errors)
        expect(row["direct_apply_allowed"] is False, "skill candidate must not apply directly", errors)


def test_memory_candidate_uses_canonical_daily_path(errors: list[str]) -> None:
    module = load_module(CLASSIFIER, "learning_promotion_classifier_test_memory")
    packet = module.classify_signals(base_inputs(), include_memory_candidate=True, memory_date="2026-06-29")
    memory_rows = [row for row in packet["candidates"] if row["promotion_target"] == "daily_memory_append"]
    expect(len(memory_rows) == 1, "expected one memory append preview", errors)
    if memory_rows:
        memory = memory_rows[0]["memory_append"]
        expect(memory["target_path"] == "memory/2026-06-29.md", "memory append target must be canonical daily note", errors)
        expect("MEMORY.md" not in memory["target_path"], "memory candidate must not target MEMORY.md", errors)
    expect(packet["validation"]["status"] == "ok", f"memory packet should validate ok: {packet['validation']}", errors)


def test_review_packet_blocks_direct_apply_residue(errors: list[str]) -> None:
    classifier = load_module(CLASSIFIER, "learning_promotion_classifier_test_review_classifier")
    review = load_module(REVIEW, "learning_promotion_review_packet_test")
    packet = classifier.classify_signals(base_inputs())
    packet["summary"]["direct_apply_count"] = 1
    review_packet = review.build_packet(packet)
    expect(review_packet["validation"]["status"] == "blocked", "review packet should block direct apply residue", errors)
    expect("direct_apply_count_must_be_zero" in review_packet["validation"]["errors"], "expected direct apply zero error", errors)


def test_live_workspace_packet_has_no_apply_authority(errors: list[str]) -> None:
    module = load_module(CLASSIFIER, "learning_promotion_classifier_test_live")
    packet = module.classify_signals()
    expect(packet["summary"]["direct_apply_count"] == 0, "live packet direct apply count must be zero", errors)
    expect(packet["summary"]["direct_memory_write_count"] == 0, "live packet direct memory write count must be zero", errors)
    expect(packet["summary"]["direct_skill_write_count"] == 0, "live packet direct skill write count must be zero", errors)
    expect(packet["validation"]["status"] in {"ok", "warning"}, f"live packet should not block: {packet['validation']}", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_cron_signal_becomes_pm_candidate,
        test_execution_guardrail_becomes_skill_candidate_without_apply,
        test_memory_candidate_uses_canonical_daily_path,
        test_review_packet_blocks_direct_apply_residue,
        test_live_workspace_packet_has_no_apply_authority,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: learning promotion conveyor tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
