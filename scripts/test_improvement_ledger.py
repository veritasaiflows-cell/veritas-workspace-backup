from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "improvement_ledger.py"
sys.path.insert(0, str(ROOT / "scripts"))
import improvement_ledger as ledger_mod  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    clean_runner = {
        "status": "ok",
        "summary": {
            "steps_blocked": 0,
            "finance_response_quality_status": "ok",
            "finance_response_quality_source_open_blocked_count": 0,
            "finance_response_quality_source_freshness_blocked_count": 0,
            "finance_response_quality_remediation_tracks_needing_repair": 0,
        },
    }
    clean_slice = {
        "status": "ok",
        "summary": {
            "blocked_archetype_count": 0,
            "source_open_blocked_count": 0,
            "source_freshness_blocked_count": 0,
            "remediation_tracks_needing_repair": 0,
        },
    }
    clean_repair_loop = {
        "status": "noop_ok",
        "summary": {
            "proposal_count": 0,
            "high_priority_count": 0,
            "source_open_blocked_count": 0,
            "source_freshness_blocked_count": 0,
            "remediation_tracks_needing_repair": 0,
        },
    }
    clean_wf85 = {
        "status": "ok",
        "generated_at_utc": "2026-06-30T03:52:43Z",
        "summary": {
            "fresh_verified_source_count": 300,
            "unnecessary_source_open_blocker_count": 0,
            "wrong_source_open_blocker_reason_count": 0,
            "mismatch_error_count": 0,
            "producer_order_error_count": 0,
        },
    }
    stale_finance_source_open = {
        "schema": "veritas.improvement_ledger_event.v1",
        "event_id": "synthetic-finance-source-open-stale",
        "recorded_at_utc": "2026-06-25T00:53:06Z",
        "source_type": "wf74_improvement_opportunity",
        "source_artifact": "tmp/wf74-improvement-opportunity-queue.json",
        "source_generated_at_utc": "2026-06-25T00:53:06Z",
        "source_key": "finance_mutation-source-open-test",
        "status": "open",
        "carry_forward": True,
        "category": "finance_mutation",
        "title": "Clear finance response quality source-open blockers so WF74 scorecard can pass",
        "priority": 96,
        "severity": "follow_up_required",
        "signal": "source_absence_without_followup",
        "decision": "follow_up_required_before_closure",
    }
    expect(
        ledger_mod.finance_response_quality_proof_clean(
            clean_runner,
            clean_slice,
            clean_repair_loop,
            clean_wf85,
        ),
        "clean finance response-quality proof should be recognized",
        errors,
    )
    close_events = ledger_mod.finance_response_quality_resolution_events(
        [stale_finance_source_open],
        [],
        clean_runner,
        clean_slice,
        clean_repair_loop,
        clean_wf85,
    )
    expect(len(close_events) == 1, "stale finance source-open row should close with clean proof", errors)
    if close_events:
        expect(close_events[0].get("status") == "complete", "finance closure event should be complete", errors)
        expect(close_events[0].get("carry_forward") is False, "finance closure event should not carry forward", errors)
        expect(
            close_events[0].get("resolution_reason") == "finance_response_quality_current_proof_clean",
            "finance closure reason mismatch",
            errors,
        )
        expect(
            ledger_mod.closure_type(close_events[0]) == "applied_fix",
            "finance clean proof closure should count as applied fix",
            errors,
        )
        expect(
            close_events[0].get("successor_id") == "wf85-source-open-repair-queue",
            "finance closure should point to WF88/WF85 successor action id",
            errors,
        )
        expect(
            close_events[0].get("successor_artifact") == "tmp/wf88-os2-control-packet.json",
            "finance closure should point to WF88 control packet successor artifact",
            errors,
        )
        expect(
            close_events[0].get("follow_up", {}).get("successor_artifact") == "tmp/wf88-os2-control-packet.json",
            "finance closure follow_up should preserve successor artifact",
            errors,
        )
    dirty_wf85 = json.loads(json.dumps(clean_wf85))
    dirty_wf85["summary"]["unnecessary_source_open_blocker_count"] = 1
    dirty_close_events = ledger_mod.finance_response_quality_resolution_events(
        [stale_finance_source_open],
        [],
        clean_runner,
        clean_slice,
        clean_repair_loop,
        dirty_wf85,
    )
    expect(not dirty_close_events, "dirty WF85 source-open proof must not close stale row", errors)

    standing_queue = {
        "generated_at_utc": "2026-06-30T04:45:00Z",
        "opportunities": [
            {
                "opportunity_id": "execution-random-source-key",
                "category": "execution",
                "title": "Maintain execution as proposal-only and exact-owner-gated",
                "priority": 35,
                "signal": "standing_execution_cadence",
                "proposal_gate": "standing_guardrail_no_execution",
                "recommended_action": "Continue producing approval-ready cards only.",
            },
            {
                "opportunity_id": "collector-random-source-key",
                "category": "collector_config",
                "title": "Owner-gated OTEL field-depth decision packet is ready",
                "priority": 70,
                "signal": "otel_field_depth_packet_owner_decision_required",
                "proposal_gate": "owner_decision_required",
                "recommended_action": "Wait for owner approval before collector/config mutation.",
            },
            {
                "opportunity_id": "wf87-runtime-blockers-visible-random-key",
                "category": "workflow_maturity",
                "title": "Keep WF87 runtime blockers visible as maturity blockers",
                "priority": 90,
                "signal": "wf87_runtime_blocker_visibility",
                "proposal_gate": "monitor_only",
                "recommended_action": "Keep the blocker visible in WF74/WF88 without treating it as immediate implementation debt.",
            },
        ],
    }
    standing_rows = ledger_mod.queue_events(standing_queue)
    standing_by_title = {row.get("title"): row for row in standing_rows}
    execution_guard = standing_by_title["Maintain execution as proposal-only and exact-owner-gated"]
    expect(
        execution_guard.get("source_key") == "execution-proposal-only-guardrail",
        "execution guardrail should use canonical source key",
        errors,
    )
    expect(execution_guard.get("standing_state") == "standing_policy", "execution guardrail should be standing policy", errors)
    expect(execution_guard.get("status") == "complete", "standing policy should not remain open", errors)
    field_depth = standing_by_title["Owner-gated OTEL field-depth decision packet is ready"]
    expect(
        field_depth.get("source_key") == "collector_config-otel-field-depth-owner-decision",
        "field-depth packet should use canonical source key",
        errors,
    )
    expect(field_depth.get("standing_state") == "owner_decision_pending", "field-depth packet should be owner-decision pending", errors)
    expect(field_depth.get("status") == "open", "owner-decision row should stay visible as one open row", errors)
    wf87_visible = standing_by_title["Keep WF87 runtime blockers visible as maturity blockers"]
    expect(
        wf87_visible.get("source_key") == "workflow_maturity-wf87-runtime-blockers-visible",
        "WF87 blocker visibility row should use canonical source key",
        errors,
    )
    expect(
        wf87_visible.get("standing_state") == "monitor_only_standing",
        "WF87 blocker visibility should be monitor-only standing",
        errors,
    )
    expect(wf87_visible.get("sla_exempt") is True, "WF87 blocker visibility should be SLA-exempt", errors)

    otel_standing_rows = ledger_mod.otel_events({
        "generated_at_utc": "2026-06-30T04:45:00Z",
        "recommendations": [
            {
                "id": "content_capture_boundary",
                "decision": "keep_raw_content_capture_blocked",
                "next_action": "Use targeted owner-approved packets only.",
            },
            {
                "id": "token_cost_metadata_depth",
                "severity": "warning",
                "decision": "prepare_owner_gated_metadata_depth_patch",
                "next_action": "Wait for owner approval.",
            },
            {
                "id": "cron_signal_learning_input",
                "severity": "warning",
                "decision": "route_cron_blockers_into_migration_plan",
                "next_action": "Monitor cron proof.",
            },
        ],
    })
    otel_by_key = {row.get("source_key"): row for row in otel_standing_rows}
    expect(otel_by_key["content_capture_boundary"].get("standing_state") == "standing_policy", "content boundary should be standing policy", errors)
    expect(otel_by_key["content_capture_boundary"].get("status") == "complete", "content boundary should not stay open", errors)
    expect(otel_by_key["token_cost_metadata_depth"].get("standing_state") == "owner_decision_pending", "token metadata should be owner pending", errors)
    expect(otel_by_key["cron_signal_learning_input"].get("standing_state") == "monitor_only_standing", "cron signal input should be monitor-only standing", errors)

    direct_standing_resolution = ledger_mod.standing_followup_required_resolution_events(
        [
            {
                "schema": "veritas.improvement_ledger_event.v1",
                "event_id": "synthetic-direct-open-standing-followup",
                "recorded_at_utc": "2026-06-01T00:00:00Z",
                "source_type": "otel_learning_loop_recommendation",
                "source_artifact": "tmp/otel-learning-loop.json",
                "source_generated_at_utc": "2026-06-01T00:00:00Z",
                "source_key": "wf74_queue_followup",
                "status": "open",
                "carry_forward": True,
                "category": "otel_learning_loop",
                "title": "wf74_queue_followup",
                "priority": 55,
                "severity": "follow_up_required",
                "signal": "source_absence_without_followup",
                "decision": "follow_up_required_before_closure",
                "follow_up": {
                    "status": "missing_followup",
                    "required": True,
                    "implemented_durable_change": False,
                },
            }
        ],
        {},
        {},
    )
    expect(len(direct_standing_resolution) == 1, "standing follow-up-required row should emit a resolution event", errors)
    if direct_standing_resolution:
        follow_up = direct_standing_resolution[0].get("follow_up", {})
        expect(
            direct_standing_resolution[0].get("resolution_reason") == "standing_followup_classification_repair",
            "direct standing follow-up closure reason mismatch",
            errors,
        )
        expect(
            follow_up.get("follow_up_class") == "monitor_only_rationale",
            "direct standing follow-up should carry monitor-only rationale class",
            errors,
        )

    out = ROOT / "tmp" / "test-improvement-ledger-current.json"
    md = ROOT / "tmp" / "test-improvement-ledger-current.md"
    ledger = ROOT / "tmp" / "test-improvement-ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    stale_seed = {
        "schema": "veritas.improvement_ledger_event.v1",
        "event_id": "synthetic-stale-improvement-open",
        "recorded_at_utc": "2026-06-01T00:00:00Z",
        "source_type": "wf74_improvement_opportunity",
        "source_artifact": "tmp/wf74-improvement-opportunity-queue.json",
        "source_generated_at_utc": "2026-06-01T00:00:00Z",
        "source_key": "synthetic-stale-improvement",
        "status": "open",
        "carry_forward": True,
        "category": "synthetic_followup",
        "title": "Synthetic stale candidate",
        "priority": 90,
        "severity": "high",
        "signal": "synthetic_test_signal",
        "decision": "main_review_required",
        "recommended_action": "Synthetic stale action",
        "next_action": "Synthetic stale action",
        "validation_command": "python scripts\\wf74_improvement_opportunity_queue.py --write --validate",
        "event_fingerprint": "synthetic-stale-open-fingerprint",
    }
    closed_source_absence_seed = {
        "schema": "veritas.improvement_ledger_event.v1",
        "event_id": "synthetic-closed-source-absence",
        "recorded_at_utc": "2026-06-01T00:00:00Z",
        "source_type": "wf74_improvement_opportunity",
        "source_artifact": "tmp/wf74-improvement-opportunity-queue.json",
        "source_generated_at_utc": "2026-06-01T00:00:00Z",
        "source_key": "synthetic-closed-source-absence",
        "status": "complete",
        "carry_forward": False,
        "category": "synthetic_followup",
        "title": "Synthetic closed source absence",
        "priority": 10,
        "severity": "resolved",
        "signal": "source_no_longer_emits_candidate",
        "decision": "resolved_by_latest_source_absence",
        "recommended_action": "Synthetic stale action",
        "next_action": "Synthetic stale action",
        "resolution_reason": "latest_source_no_longer_emits_candidate",
        "validation_command": "python scripts\\wf74_improvement_opportunity_queue.py --write --validate",
        "event_fingerprint": "synthetic-closed-source-absence-fingerprint",
    }
    monitor_only_seed = {
        "schema": "veritas.improvement_ledger_event.v1",
        "event_id": "synthetic-monitor-only-source-absence",
        "recorded_at_utc": "2026-06-01T00:00:00Z",
        "source_type": "otel_learning_loop_recommendation",
        "source_artifact": "tmp/otel-learning-loop.json",
        "source_generated_at_utc": "2026-06-01T00:00:00Z",
        "source_key": "synthetic-monitor-only-source-absence",
        "status": "complete",
        "carry_forward": False,
        "category": "otel_learning_loop",
        "title": "otel_drift_review",
        "priority": 55,
        "severity": "resolved",
        "signal": "source_no_longer_emits_candidate",
        "decision": "resolved_by_latest_source_absence",
        "recommended_action": "Synthetic monitor-only action",
        "next_action": "Synthetic monitor-only action",
        "resolution_reason": "latest_source_no_longer_emits_candidate",
        "validation_command": "python scripts\\otel_ops_control.py --write --validate",
        "event_fingerprint": "synthetic-monitor-only-source-absence-fingerprint",
    }
    open_standing_followup_seed = {
        "schema": "veritas.improvement_ledger_event.v1",
        "event_id": "synthetic-open-standing-followup",
        "recorded_at_utc": "2026-06-01T00:00:00Z",
        "source_type": "otel_learning_loop_recommendation",
        "source_artifact": "tmp/otel-learning-loop.json",
        "source_generated_at_utc": "2026-06-01T00:00:00Z",
        "source_key": "wf74_queue_followup",
        "status": "open",
        "carry_forward": True,
        "category": "otel_learning_loop",
        "title": "wf74_queue_followup",
        "priority": 55,
        "severity": "follow_up_required",
        "signal": "source_absence_without_followup",
        "decision": "follow_up_required_before_closure",
        "recommended_action": "Synthetic standing follow-up action",
        "next_action": "Synthetic standing follow-up action",
        "follow_up": {
            "status": "missing_followup",
            "required": True,
            "implemented_durable_change": False,
            "follow_up_class": "unclassified_missing_followup",
        },
        "event_fingerprint": "synthetic-open-standing-followup-fingerprint",
    }
    closed_wf88_missing_successor_seed = {
        "schema": "veritas.improvement_ledger_event.v1",
        "event_id": "synthetic-wf88-closed-missing-successor",
        "recorded_at_utc": "2026-06-01T00:00:00Z",
        "source_type": "wf74_improvement_opportunity",
        "source_artifact": "tmp/wf88-followup-debt-triage-packet.json",
        "source_generated_at_utc": "2026-06-01T00:00:00Z",
        "source_key": "synthetic-wf88-closed-missing-successor",
        "status": "complete",
        "carry_forward": False,
        "category": "finance_mutation",
        "title": "Clear finance response quality source-open blockers so WF74 scorecard can pass",
        "priority": 96,
        "severity": "resolved",
        "signal": "wf88_followup_debt_triage_closure",
        "decision": "resolved_by_wf88_followup_debt_triage",
        "recommended_action": "Synthetic closed action",
        "next_action": "Synthetic closed action",
        "resolution_reason": "wf88_followup_debt_triage",
        "follow_up": {
            "status": "verified_fix",
            "required": False,
            "implemented_durable_change": True,
            "follow_up_class": "live_code_or_validator",
        },
        "triage_action_state": "close_with_finance_response_quality_clean_proof",
        "event_fingerprint": "synthetic-wf88-closed-missing-successor-fingerprint",
    }
    ledger.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"))
            for row in (
                stale_seed,
                closed_source_absence_seed,
                monitor_only_seed,
                open_standing_followup_seed,
                closed_wf88_missing_successor_seed,
            )
        )
        + "\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--write",
        "--write-md",
        "--validate",
        "--json-out",
        str(out),
        "--md-out",
        str(md),
        "--ledger-out",
        str(ledger),
    ]
    first = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    expect(first.returncode == 0, f"first run failed: {first.stdout} {first.stderr}", errors)
    payload = load_json(out)
    expect(payload.get("schema") == "veritas.improvement_ledger_current.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") in {"ok", "warning"}, "validation should be ok or warning", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
    summary = payload.get("summary", {})
    expect(summary.get("latest_open_count", 0) > 0, "expected open improvements", errors)
    expect(summary.get("appended_event_count", 0) > 0, "expected first run to append events", errors)
    expect("latest_closed_count" in summary, "closed improvement count missing", errors)
    expect("historical_open_row_count" in summary, "historical open row count missing", errors)
    expect("actionable_open_count" in summary, "actionable open count missing", errors)
    expect("standing_policy_count" in summary, "standing policy count missing", errors)
    expect("owner_decision_pending_count" in summary, "owner-decision pending count missing", errors)
    expect("monitor_only_standing_count" in summary, "monitor-only standing count missing", errors)
    expect("recurring_open_count" in summary, "recurring open count missing", errors)
    open_keys = {
        row.get("source_key"): row
        for row in payload.get("latest_open_improvements", [])
        if isinstance(row, dict)
    }
    stale_followup = open_keys.get("synthetic-stale-improvement")
    expect(bool(stale_followup), "stale source candidate should stay open until follow-up is classified", errors)
    if stale_followup:
        expect(
            stale_followup.get("decision") == "follow_up_required_before_closure",
            "stale candidate should require follow-up before closure",
            errors,
        )
    wf87_open = open_keys.get("workflow_maturity-wf87-runtime-blockers-visible")
    expect(bool(wf87_open), "WF87 runtime blocker visibility should remain as one visible open monitor row", errors)
    if wf87_open:
        expect(
            wf87_open.get("standing_state") == "monitor_only_standing",
            "WF87 runtime blocker visibility should stay monitor-only standing in current ledger",
            errors,
        )
        expect(
            wf87_open.get("sla_status") == "monitor_only_standing",
            "WF87 runtime blocker visibility should not be overdue",
            errors,
        )
        expect(
            stale_followup.get("closure_blocked_reason") == "latest_source_absence_without_followup",
            "stale candidate closure blocked reason mismatch",
            errors,
        )
    closed_source_absence = open_keys.get("synthetic-closed-source-absence")
    expect(bool(closed_source_absence), "closed source absence without follow-up should be reopened", errors)
    if closed_source_absence:
        expect(
            closed_source_absence.get("decision") == "follow_up_required_before_closure",
            "closed source absence should require follow-up before closure",
            errors,
        )
        expect(
            closed_source_absence.get("closure_blocked_reason") == "latest_source_absence_without_followup",
            "closed source absence blocked reason mismatch",
            errors,
        )
    closed_keys = {
        row.get("source_key"): row
        for row in payload.get("latest_closed_improvements", [])
        if isinstance(row, dict)
    }
    monitor_only = closed_keys.get("synthetic-monitor-only-source-absence")
    expect(bool(monitor_only), "monitor-only source absence should remain closed with explicit rationale", errors)
    if monitor_only:
        follow_up = monitor_only.get("follow_up", {})
        expect(
            follow_up.get("status") == "monitor_only_drift_currently_absent",
            "monitor-only closure should carry monitor-only status",
            errors,
        )
        expect(
            follow_up.get("follow_up_class") == "monitor_only_rationale",
            "monitor-only closure should carry explicit follow-up class",
            errors,
        )
    standing_followup = closed_keys.get("wf74_queue_followup") or open_keys.get("wf74_queue_followup")
    expect(bool(standing_followup), "standing monitor-only follow-up should supersede follow-up-required row", errors)
    if standing_followup:
        follow_up = standing_followup.get("follow_up", {})
        expect(
            standing_followup.get("decision") != "follow_up_required_before_closure",
            "standing follow-up should not remain follow-up-required debt",
            errors,
        )
        expect(
            follow_up.get("status") in {"monitor_only_standing", "verified_fix"},
            "standing follow-up should carry monitor-only standing or verified-fix status",
            errors,
        )
        expect(
            follow_up.get("follow_up_class") in {"monitor_only_rationale", "live_code_or_validator"},
            "standing follow-up should carry monitor-only rationale or validator proof class",
            errors,
        )
    repaired_successor = closed_keys.get("synthetic-wf88-closed-missing-successor")
    expect(bool(repaired_successor), "closed WF88 row missing successor should stay closed with successor repair", errors)
    if repaired_successor:
        expect(
            repaired_successor.get("successor_artifact") == "tmp/wf88-os2-control-packet.json",
            "closed WF88 row should gain successor_artifact",
            errors,
        )
        expect(
            repaired_successor.get("successor_id") == "wf85-source-open-repair-queue",
            "closed WF88 row should gain successor action id",
            errors,
        )
    kpis = payload.get("learning_loop_kpis", {})
    expect(kpis.get("schema") == "veritas.learning_loop_kpis.v1", "learning loop KPI schema missing", errors)
    expect(kpis.get("anti_theater_status") in {
        "blocked_by_overdue_backlog",
        "proposal_loop_active_no_closure_proof",
        "proposal_loop_with_closure_proof",
    }, "anti-theater status missing", errors)
    expect("closure_rate" in kpis, "closure rate missing", errors)
    expect("applied_fix_closure_rate" in kpis, "applied-fix closure rate missing", errors)
    expect("signal_absence_closure_rate" in kpis, "signal-absence closure rate missing", errors)
    expect("pending_skill_proposal_closure_rate" in kpis, "pending skill proposal closure rate missing", errors)
    expect("followup_required_open_count" in summary, "follow-up-required open count missing", errors)
    expect(summary.get("followup_required_open_count", 0) >= 1, "expected at least one follow-up-required open item", errors)
    expect("unclassified_closed_followup_count" in summary, "unclassified closed follow-up count missing", errors)
    expect(summary.get("unclassified_closed_followup_count") == 0, "closed rows should all carry durable follow-up classification", errors)
    expect("skill_proposal_audit" in payload, "skill proposal audit missing", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "code_mutation_allowed",
        "skill_application_allowed",
        "collector_config_mutation_allowed",
        "runtime_config_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    expect(boundary.get("append_only") is True, "append_only must stay true", errors)
    expect(ledger.exists(), "ledger file missing", errors)
    first_line_count = len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()])

    second = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    expect(second.returncode == 0, f"second run failed: {second.stdout} {second.stderr}", errors)
    second_payload = load_json(out)
    expect(second_payload.get("summary", {}).get("appended_event_count") == 0, "second run should be idempotent for same source snapshot", errors)
    expect(second_payload.get("summary", {}).get("candidate_event_count", 0) > 0, "second run should still observe current candidates", errors)
    second_line_count = len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()])
    expect(first_line_count == second_line_count, "idempotent run changed ledger length", errors)
    expect(md.exists(), "markdown output missing", errors)

    check_out = ROOT / "tmp" / "test-improvement-ledger-check.json"
    check_cmd = [
        sys.executable,
        str(SCRIPT),
        "--check",
        "--write",
        "--validate",
        "--json-out",
        str(check_out),
        "--ledger-out",
        str(ledger),
    ]
    check = subprocess.run(check_cmd, cwd=ROOT, text=True, capture_output=True)
    expect(check.returncode == 0, f"check run failed: {check.stdout} {check.stderr}", errors)
    check_payload = load_json(check_out)
    expect(check_payload.get("mode") == "check", "check run should declare check mode", errors)
    expect(check_payload.get("summary", {}).get("appended_event_count") == 0, "check run must not append events", errors)
    check_line_count = len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()])
    expect(second_line_count == check_line_count, "check run changed ledger length", errors)
    expect("overdue_open_count" in check_payload.get("summary", {}), "SLA overdue count missing", errors)
    expect("escalation_level" in check_payload.get("summary", {}), "SLA escalation level missing", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: improvement ledger is append-only, idempotent per source snapshot, and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
