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
    # WF87 live row is retired (closed upstream as resolved_as_monitor_only_standing).
    # Prior open-seed attempt removed: source processing closes it, so the hermetic
    # guarantee is asserted deterministically in-process below (standing_rows fixture).
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
    # WF87 hermetic fixture: live WF87 is retired (resolved_as_monitor_only_standing
    # upstream); never depend on live latest_open for it. The standing_rows fixture
    # above already proves source-key/standing/SLA semantics; here we lock the
    # capped-one / open-monitor / SLA-exempt guarantees deterministically.
    wf87_fixture_rows = [
        row
        for row in standing_rows
        if row.get("source_key") == "workflow_maturity-wf87-runtime-blockers-visible"
    ]
    expect(len(wf87_fixture_rows) == 1, "WF87 fixture should emit exactly one capped monitor row", errors)
    if wf87_fixture_rows:
        wf87_fixture = wf87_fixture_rows[0]
        expect(wf87_fixture.get("status") == "open", "WF87 fixture should stay open as monitor", errors)
        expect(
            wf87_fixture.get("standing_state") == "monitor_only_standing",
            "WF87 fixture should stay monitor-only standing",
            errors,
        )
        expect(wf87_fixture.get("sla_exempt") is True, "WF87 fixture should be SLA-exempt", errors)
        expect(
            wf87_fixture.get("follow_up", {}).get("follow_up_class") == "monitor_only_rationale",
            "WF87 fixture should carry monitor-only rationale class",
            errors,
        )
    # Live ledger must not reopen WF87 as actionable debt; if a live row surfaces it
    # must already be monitor-only standing and SLA-exempt. Absence is the expected
    # retired state and is not a failure.
    wf87_live_open = open_keys.get("workflow_maturity-wf87-runtime-blockers-visible")
    if wf87_live_open is not None:
        expect(
            wf87_live_open.get("standing_state") == "monitor_only_standing",
            "live WF87 open row must stay monitor-only standing",
            errors,
        )
        expect(wf87_live_open.get("sla_exempt") is True, "live WF87 open row must stay SLA-exempt", errors)
    if stale_followup:
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
    check_historical_terminal_claim_limit(errors)
    check_event_identity_layer(errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: improvement ledger is append-only, idempotent per source snapshot, and bounded")
    return 0



def check_historical_terminal_claim_limit(errors: list[str]) -> None:
    from datetime import datetime, timedelta, timezone
    from pathlib import Path as _P
    import importlib.util as _ilu
    if "historical_terminal_unavailable_claim_limit" not in ledger_mod.TRIAGE_CLOSURE_STATUSES:
        errors.append("consumer missing new closure status in TRIAGE_CLOSURE_STATUSES")
        return
    if ledger_mod.FOLLOW_UP_CLASS_BY_STATUS.get("historical_terminal_unavailable_claim_limit") != "monitor_only_rationale":
        errors.append("consumer class for new status must be monitor_only_rationale")
        return
    spec = _ilu.spec_from_file_location("sibling_triage", str(_P(__file__).with_name("wf88_followup_debt_triage_packet.py")))
    tri = _ilu.module_from_spec(spec)
    spec.loader.exec_module(tri)
    gen = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    bridge = {"schema": "veritas.implementation_token_attribution_bridge.v1", "status": "warning", "generated_at_utc": gen, "summary": {"action_required_supported_runtime_gap_count": 0, "post_cutoff_supported_unresolved_gap_count": 0, "unknown_completion_supported_unresolved_gap_count": 0, "gap_resolution_status": "terminal_unavailable_only"}, "validation": {"status": "warning", "errors": [], "warnings": ["t"]}}
    row = {"source_type": "otel_learning_loop", "source_key": "usage_source_reverification_required", "title": "usage_source_reverification_required", "category": "otel_learning_loop", "priority": 60, "decision": "follow_up_required_before_closure"}
    item = tri.classify_usage_source_reverification(row, {"implementation_token_bridge": bridge})
    if not item.get("closure_allowed") or item.get("closure_status") != "historical_terminal_unavailable_claim_limit" or item.get("action_state") != "monitor_only":
        errors.append("triage/consumer disagreement on fresh terminal-only bridge")
        return
    existing = [{"schema": "veritas.improvement_ledger_event.v1", "source_type": "otel_learning_loop", "source_key": "usage_source_reverification_required", "title": "usage_source_reverification_required", "category": "otel_learning_loop", "priority": 60, "status": "open", "carry_forward": True, "decision": "follow_up_required_before_closure", "follow_up": {"required": True}, "source_generated_at_utc": gen}]
    pkt = {"validation": {"status": "ok"}, "closure_items": [{**item, "source_type": "otel_learning_loop", "source_key": "usage_source_reverification_required"}]}
    rows = ledger_mod.wf88_followup_triage_resolution_events(existing, pkt, {}, {})
    if len(rows) != 1:
        errors.append(f"fresh terminal-only bridge should close exactly 1 row, got {len(rows)}")
        return
    r = rows[0]
    fu = r.get("follow_up", {}) if isinstance(r.get("follow_up"), dict) else {}
    if r.get("status") != "complete" or r.get("decision") != "resolved_by_wf88_followup_debt_triage":
        errors.append("wrong emitted status/decision")
    if fu.get("status") != "historical_terminal_unavailable_claim_limit":
        errors.append("wrong follow_up.status")
    if fu.get("implemented_durable_change") is not False:
        errors.append("new closure must NOT claim implemented durable change")
    if fu.get("follow_up_class") != "monitor_only_rationale":
        errors.append("wrong follow_up_class")
    if r.get("triage_action_state") != "monitor_only":
        errors.append("wrong triage_action_state")
    neg1 = {"validation": {"status": "ok"}, "closure_items": [{"source_type": "otel_learning_loop", "source_key": "usage_source_reverification_required", "closure_allowed": True, "closure_status": "verified_fix_masquerade", "proof_artifacts": ["tmp/implementation-token-attribution-bridge.json"], "closure_reason": "x", "recommended_next_action": "x", "action_state": "monitor_only"}]}
    if ledger_mod.wf88_followup_triage_resolution_events(existing, neg1, {}, {}):
        errors.append("NEG1 FAIL: status-not-allowlisted WITH valid proof must not close")
    neg2 = {"validation": {"status": "ok"}, "closure_items": [{"source_type": "otel_learning_loop", "source_key": "usage_source_reverification_required", "closure_allowed": True, "closure_status": "historical_terminal_unavailable_claim_limit", "proof_artifacts": [], "closure_reason": "x", "recommended_next_action": "x", "action_state": "monitor_only"}]}
    if ledger_mod.wf88_followup_triage_resolution_events(existing, neg2, {}, {}):
        errors.append("NEG2 FAIL: allowed status with MISSING proof must not close")


IDENTITY_BASE_ROW = {
    "source_type": "wf74_improvement_opportunity",
    "source_key": "identity_probe_key",
    "status": "open",
    "carry_forward": True,
    "category": "identity_probe",
    "title": "identity probe row",
    "priority": 70,
    "severity": "medium",
    "signal": "identity_probe_signal",
    "decision": "identity_probe_decision",
    "recommended_action": "identity probe recommended action",
    "next_action": "identity probe next action",
    "validation_command": "python scripts/test_improvement_ledger.py",
    "requires_before_apply": [],
    "allowed_autonomous_output": [],
    "review_cadence": "weekly",
    "source_generated_at_utc": "2026-01-01T00:00:00Z",
}


def identity_of(overrides: dict) -> tuple[str, str]:
    """Return (event_fingerprint, event_id) for one synthetic row."""
    import copy as _copy

    row = _copy.deepcopy(IDENTITY_BASE_ROW)
    row.update(overrides)
    for key, value in list(row.items()):
        if value is _IDENTITY_ABSENT:
            del row[key]
    ledger_mod.finalize_event_ids([row])
    return str(row["event_fingerprint"]), str(row["event_id"])


class _IdentityAbsent:
    pass


_IDENTITY_ABSENT = _IdentityAbsent()


def check_event_identity_layer(errors: list[str]) -> None:
    """Cover finalize_event_ids / event_fingerprint ahead of WF88 Phase 3 typed event identity.

    Two groups below. Invariants must hold. Characterizations pin known defects so that
    changing them in Phase 3 is a visible, deliberate edit rather than a silent behavior drift.
    """
    base_fp, base_id = identity_of({})

    # --- Invariants: these protect real behavior and must keep passing. ---

    # An open event keeps one identity while its producer regenerates. Without this,
    # every upstream rebuild would re-open the same debt as a new row.
    regen_fp, regen_id = identity_of({"source_generated_at_utc": "2026-02-02T00:00:00Z"})
    expect(
        (base_fp, base_id) == (regen_fp, regen_id),
        "open-event identity must not change when only source_generated_at_utc changes",
        errors,
    )

    # prior_event_id participates in the fingerprint. This is the close/reopen fix: an event
    # that legitimately recurs after closure must not collide with its own prior cycle.
    reopen_fp, reopen_id = identity_of({"prior_event_id": "0123456789abcdef"})
    expect(
        reopen_fp != base_fp and reopen_id != base_id,
        "prior_event_id must change identity so a reopened event is not suppressed as a duplicate",
        errors,
    )

    # Semantic content still drives identity.
    retitled_fp, retitled_id = identity_of({"title": "different identity probe title"})
    expect(
        retitled_fp != base_fp and retitled_id != base_id,
        "a changed title must mint a new identity",
        errors,
    )

    closed_fp, closed_id = identity_of({"status": "complete", "carry_forward": False})
    expect(
        closed_id != base_id,
        "closing an event must change its event_id",
        errors,
    )

    # --- Characterizations: known defects recorded in WF88 under enhancement #3. ---
    # Each one FAILS once Phase 3 fixes the defect. That failure is the intended signal:
    # update the characterization here in the same change that fixes the behavior.

    # Defect A - over-minting. Terminal identity includes source_generated_at_utc, so one
    # semantic closure mints a fresh event_id on every producer rebuild. Measured 2026-09-18:
    # 47 identities for a single closure over one week.
    closed_regen_fp, closed_regen_id = identity_of(
        {"status": "complete", "carry_forward": False, "source_generated_at_utc": "2026-02-02T00:00:00Z"}
    )
    expect(
        closed_fp == closed_regen_fp and closed_id != closed_regen_id,
        "WF88 #3 defect A characterization changed: closed-event identity no longer churns on "
        "source_generated_at_utc. If Phase 3 removed occurrence time from semantic identity, update this case.",
        errors,
    )

    # Defect B - under-minting. The fingerprint covers a fixed field tuple, so state carried in
    # follow_up / triage_action_state and 31 other keys is invisible to identity. A row whose
    # only change lives there cannot mint a new event and is dropped by the append guard.
    state_fp, state_id = identity_of(
        {
            "follow_up": {"required": True, "note": "materially different follow-up state"},
            "triage_action_state": "monitor_only",
            "successor_id": "successor-identity-probe",
            "sla_status": "overdue",
        }
    )
    expect(
        state_fp == base_fp and state_id == base_id,
        "WF88 #3 defect B characterization changed: follow_up / triage_action_state / successor_id / "
        "sla_status now affect identity. If Phase 3 widened the identity field set, update this case.",
        errors,
    )

    # Latent fragility: the fingerprint includes a key only when present, so an absent field and
    # an explicit None are two different identities for the same meaning.
    absent_fp, _ = identity_of({"severity": _IDENTITY_ABSENT})
    none_fp, _ = identity_of({"severity": None})
    expect(
        absent_fp != none_fp,
        "WF88 #3 characterization changed: absent field and explicit None now fingerprint alike. "
        "If Phase 3 normalized missing values, update this case.",
        errors,
    )


if __name__ == "__main__":
    raise SystemExit(main())
