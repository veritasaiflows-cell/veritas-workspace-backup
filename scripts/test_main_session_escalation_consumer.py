#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "main_session_escalation_consumer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("main_session_escalation_consumer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def configure_paths(module, root: Path) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "main-session-escalation-consumer.json"
    module.LEDGER = root / "state" / "main-session-escalation-action-ledger.jsonl"
    module.PRIORITY_OUT = module.TMP / "main-session-priority-handoff.json"
    module.HEARTBEAT_OUT = module.TMP / "heartbeat-main-session-escalation-consumer.json"
    module.HEARTBEAT_PRIORITY_OUT = module.TMP / "heartbeat-main-session-priority-handoff.json"
    module.PRIORITY_DISPOSITION_LEDGER = root / "state" / "main-session-priority-disposition-ledger.jsonl"
    module.CRON_CONTROL = module.TMP / "cron-control-packet.json"
    module.FINANCE_EVIDENCE_WARNING_ROUTER = module.TMP / "finance-evidence-warning-router.json"
    module.CURRENT_WINDOW_ARTIFACTS = module.TMP / "current-window-artifacts.json"
    module.TICKER_FRESHNESS_RUNNER = module.TMP / "ticker-card-freshness-owner-runner.json"
    module.TRADE_GRADE_REPAIR_CONVEYOR = module.TMP / "trade-grade-repair-conveyor.json"


def args(module, *, context: str = "main_session", execute_safe: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        write=False,
        validate=True,
        refresh_frontdoors=False,
        execute_safe=execute_safe,
        append_ledger=False,
        context=context,
        max_actions=8,
        repeat_threshold=2,
        out=module.OUT,
        ledger=module.LEDGER,
        priority_out=module.PRIORITY_OUT,
        priority_disposition_ledger=module.PRIORITY_DISPOSITION_LEDGER,
        max_priority_items=25,
        priority_id=None,
        priority_disposition=None,
        priority_note=None,
        priority_proof=None,
        priority_observation_source=None,
    )


def cron_packet(signal: dict) -> dict:
    return {
        "status": "ok",
        "summary": {
            "should_wake_main_session": True,
            "escalation_signal_count": 1,
        },
        "escalation": {
            "should_wake_main_session": True,
            "escalation_signal_count": 1,
            "escalation_signals": [signal],
        },
    }


def test_digest_blocker_maps_to_safe_refresh() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(
            module.CRON_CONTROL,
            cron_packet({
                "source": "cron_job:Finance - Morning Control Digest Proof Refresh",
                "signal_class": "BLOCKED",
                "status": "blocked",
                "reason": "artifact_blocked_or_authority_widened",
                "artifact": "tmp/morning-control-digest.json",
            }),
        )
        write_json(root / "tmp" / "morning-control-digest.json", {"status": "critical", "authority": {"review_only": True}})
        report = module.build_report(args(module))
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["auto_actionable_count"] == 1
        action = report["actions"][0]
        assert action["handler_id"] == "morning_control_digest_refresh"
        assert action["classification"] == "auto_repair"
        assert "morning_control_digest" in action["commands"]


def test_authority_widened_artifact_becomes_owner_decision() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(
            module.CRON_CONTROL,
            cron_packet({
                "source": "cron_job:bad",
                "signal_class": "BLOCKED",
                "status": "blocked",
                "reason": "artifact_blocked_or_authority_widened",
                "artifact": "tmp/bad.json",
            }),
        )
        write_json(root / "tmp" / "bad.json", {"status": "blocked", "authority": {"paper_submit_allowed": True}})
        report = module.build_report(args(module))
        assert report["validation"]["status"] == "ok"
        action = report["actions"][0]
        assert action["classification"] == "owner_decision"
        assert action["commands"] == []
        assert action["owner_gate_required"] is True
        assert "authority.paper_submit_allowed" in action["authority_findings"]


def test_heartbeat_context_never_executes_and_rejects_execute_safe() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(
            module.CRON_CONTROL,
            cron_packet({
                "source": "cron_job:Finance - Post-Close Control Digest Consolidated Handoff",
                "signal_class": "BLOCKED",
                "status": "blocked",
                "reason": "artifact_blocked_or_authority_widened",
                "artifact": "tmp/post-close-control-digest.json",
            }),
        )
        write_json(root / "tmp" / "post-close-control-digest.json", {"status": "critical", "authority": {"review_only": True}})
        report = module.build_report(args(module, context="heartbeat", execute_safe=True))
        assert report["validation"]["status"] == "blocked"
        assert "heartbeat_execute_safe_requested" in report["validation"]["errors"]
        assert report["execution_results"] == []
        assert report["summary"]["executed_safe_action_count"] == 0
        assert report["actions"][0]["classification"] == "auto_repair"


def test_repeated_signal_is_marked_for_pm_or_helper_residue() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        signal = {
            "source": "cron_job:Finance - Morning Control Digest Proof Refresh",
            "signal_class": "BLOCKED",
            "status": "blocked",
            "reason": "artifact_blocked_or_authority_widened",
            "artifact": "tmp/morning-control-digest.json",
        }
        fp = module.fingerprint(signal)
        module.LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.LEDGER.write_text(json.dumps({"actions": [{"fingerprint": fp}]}) + "\n", encoding="utf-8")
        write_json(module.CRON_CONTROL, cron_packet(signal))
        write_json(root / "tmp" / "morning-control-digest.json", {"status": "critical", "authority": {"review_only": True}})
        report = module.build_report(args(module))
        action = report["actions"][0]
        assert action["repeat_count"] == 2
        assert action["repeated_blocker"] is True
        assert report["summary"]["repeated_blocker_count"] == 1
        assert "repeated_blocker_present" in report["validation"]["warnings"]


def test_ticker_repair_handoff_is_deduplicated_and_non_executable() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.CRON_CONTROL, cron_packet({
            "source": "cron_job:Finance - Weekday Morning Review Refresh",
            "signal_class": "BLOCKED",
            "status": "blocked",
            "reason": "morning_chain_blocked",
            "artifact": "tmp/weekday-morning-review-cron-runner.json",
        }))
        repair = {
            "fingerprint": "fundamental-repair-jpm-period",
            "ticker": "JPM",
            "code": "bank_official_capital_period_mismatch",
            "severity": "critical",
            "blocks_ticker_only": True,
            "source_open_required": True,
            "manual_review_required": True,
            "deduplicated_finding_count": 3,
            "evidence": {"local_period_end": "2026-06-30", "official_period": "2026-03-31"},
            "authority": {"capital_deployment_approved": False, "trade_or_execution_approved": False, "paper_or_live_execution_allowed": False},
        }
        write_json(module.FINANCE_EVIDENCE_WARNING_ROUTER, {
            "sections": {"fundamentals": {"repair_queue": [repair, dict(repair)]}},
        })
        report = module.build_report(args(module))
        handoffs = [item for item in report["actions"] if item.get("handler_id") == "ticker_fundamental_repair_handoff"]
        assert len(handoffs) == 1
        handoff = handoffs[0]
        assert handoff["ticker"] == "JPM"
        assert handoff["classification"] == "helper_lane_required"
        assert handoff["commands"] == []
        assert handoff["blocks_ticker_only"] is True
        assert report["summary"]["ticker_repair_handoff_tickers"] == ["JPM"]


def test_ticker_repair_handoff_survives_safe_action_refresh() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.CRON_CONTROL, cron_packet({
            "source": "cron_job:Finance - Morning Control Digest Proof Refresh",
            "signal_class": "BLOCKED",
            "status": "blocked",
            "reason": "artifact_blocked_or_authority_widened",
            "artifact": "tmp/morning-control-digest.json",
        }))
        write_json(root / "tmp" / "morning-control-digest.json", {"status": "critical", "authority": {"review_only": True}})
        write_json(module.FINANCE_EVIDENCE_WARNING_ROUTER, {
            "sections": {"fundamentals": {"repair_queue": [{
                "fingerprint": "fundamental-repair-jpm-period",
                "ticker": "JPM",
                "code": "bank_official_capital_period_mismatch",
                "blocks_ticker_only": True,
                "source_open_required": True,
                "manual_review_required": True,
                "authority": {"auto_repair_or_apply_allowed": False, "canonical_note_mutation_allowed": False},
            }]}},
        })
        original_execute_actions = module.execute_actions
        original_run_command_ids = module.run_command_ids
        module.execute_actions = lambda actions, _args: [{"name": "safe", "ok": True}]
        module.run_command_ids = lambda *args, **kwargs: []
        try:
            report = module.build_report(args(module, execute_safe=True))
        finally:
            module.execute_actions = original_execute_actions
            module.run_command_ids = original_run_command_ids
        handoffs = [item for item in report["post_execution_actions"] if item.get("handler_id") == "ticker_fundamental_repair_handoff"]
        assert len(handoffs) == 1
        assert report["summary"]["ticker_repair_handoff_count"] == 1
        assert report["summary"]["ticker_repair_handoff_tickers"] == ["JPM"]


def test_priority_handoff_ranks_current_window_and_freshness_failure_before_ticker_debt() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.CRON_CONTROL, cron_packet({
            "source": "cron_job:Finance - Ticker Card Freshness Owner Runner",
            "signal_class": "BLOCKED",
            "status": "scheduler_error",
            "reason": "enabled_job_repeated_scheduler_failures",
            "artifact": "tmp/ticker-card-freshness-owner-runner.json",
        }))
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {
                "current_usable": False,
                "window_completion_state": "missed_after_deadline",
                "critical_or_unreadable_roles": ["terminal_runner"],
            },
        })
        write_json(module.TRADE_GRADE_REPAIR_CONVEYOR, {"rows": [
            {
                "ticker": "AAA",
                "auto_tier": "Tier A",
                "repair_lane": "freshness_repair_after_band_review",
                "freshness_status": "stale",
                "freshness_ledger_state": "stale_refreshable",
                "decision_state": "watch",
                "repair_priority": 60,
                "source_open_status": "verified",
            },
            {
                "ticker": "CCC",
                "auto_tier": "Tier C",
                "repair_lane": "freshness_repair_after_band_review",
                "freshness_status": "stale",
                "freshness_ledger_state": "fresh",
                "decision_state": "watch",
                "repair_priority": 20,
                "source_open_status": "verified",
            },
        ]})
        report = module.build_report(args(module, context="heartbeat"))
        handoff = report["main_session_priority_handoff"]
        assert report["validation"]["status"] == "ok"
        assert handoff["receipt"] == "NEW_PRIORITY"
        assert handoff["selected_item"]["priority"] == "P0"
        assert handoff["selected_item"]["category"] == "current_window_unusable"
        assert handoff["summary"]["priority_counts"] == {"P0": 2, "P1": 1, "P2": 1}
        assert all(item["authority_boundary"] == module.priority_authority_boundary() for item in handoff["items"])

        write_json(module.PRIORITY_OUT, handoff)
        second = module.build_report(args(module, context="heartbeat"))["main_session_priority_handoff"]
        assert second["receipt"] == "NO_DELTA"
        assert second["selected_item"]["repeat_count"] == 2


def test_priority_disposition_requires_main_context_and_clean_closure_proof() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {"current_usable": False, "window_completion_state": "missed_after_deadline"},
        })
        handoff = module.build_report(args(module))["main_session_priority_handoff"]
        priority_id = handoff["selected_item"]["priority_id"]
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_id = priority_id
        heartbeat_args.priority_disposition = "accepted"
        assert module.record_priority_disposition(heartbeat_args, handoff)["error"] == "priority_disposition_requires_main_context"

        main_args = args(module)
        main_args.priority_id = priority_id
        main_args.priority_disposition = "closed"
        main_args.priority_proof = str(module.CURRENT_WINDOW_ARTIFACTS.relative_to(root))
        assert module.record_priority_disposition(main_args, handoff)["error"] == "current_window_not_usable"

        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "ok",
            "summary": {"current_usable": True, "window_completion_state": "completed"},
            "validation": {"status": "ok"},
        })
        result = module.record_priority_disposition(main_args, handoff)
        assert result["status"] == "ok"
        assert module.PRIORITY_DISPOSITION_LEDGER.exists()


def test_fundamental_ticker_priority_requires_its_router_finding_to_clear() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        repair = {
            "fingerprint": "fundamental-repair-jpm-period",
            "ticker": "JPM",
            "code": "bank_official_capital_period_mismatch",
            "blocks_ticker_only": True,
            "source_open_required": True,
            "manual_review_required": True,
            "authority": {"capital_deployment_approved": False, "trade_or_execution_approved": False},
        }
        write_json(module.FINANCE_EVIDENCE_WARNING_ROUTER, {
            "status": "warning",
            "sections": {"fundamentals": {"repair_queue": [repair]}},
            "validation": {"status": "ok"},
        })
        handoff = module.build_report(args(module))["main_session_priority_handoff"]
        item = next(item for item in handoff["items"] if item["category"] == "ticker_fundamental_source_repair")
        assert item["acceptance_proof"]["artifact"] == "tmp/finance-evidence-warning-router.json"
        main_args = args(module)
        main_args.priority_id = item["priority_id"]
        main_args.priority_disposition = "closed"
        main_args.priority_proof = "tmp/finance-evidence-warning-router.json"
        assert module.record_priority_disposition(main_args, handoff)["error"] == "ticker_fundamental_repair_still_present"
        write_json(module.FINANCE_EVIDENCE_WARNING_ROUTER, {
            "status": "ok",
            "sections": {"fundamentals": {"repair_queue": []}},
            "validation": {"status": "ok"},
        })
        assert module.record_priority_disposition(main_args, handoff)["status"] == "ok"


def test_priority_lifecycle_deduplicates_ages_omitted_items_and_reopens_changed_deferral() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        signal = {
            "source": "cron_job:Finance - Ticker Card Freshness Owner Runner",
            "signal_class": "BLOCKED",
            "status": "scheduler_error",
            "reason": "enabled_job_repeated_scheduler_failures",
            "artifact": "tmp/ticker-card-freshness-owner-runner.json",
        }
        packet = cron_packet(signal)
        packet["escalation"]["escalation_signals"].append(dict(signal))
        write_json(module.CRON_CONTROL, packet)
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {"current_usable": False, "window_completion_state": "not_started"},
        })
        # Escalation age is heartbeat-owned.  Main-session reads are
        # intentionally non-aging, so exercise the repeat transition through
        # an explicit heartbeat observation.
        limited_args = args(module, context="heartbeat")
        limited_args.priority_observation_source = "heartbeat"
        limited_args.max_priority_items = 1
        first = module.build_report(limited_args)["main_session_priority_handoff"]
        assert first["summary"]["duplicate_candidate_count"] == 1
        assert first["summary"]["priority_counts"]["P0"] == 2
        omitted_id = next(priority_id for priority_id in first["state_index"] if priority_id != first["selected_item"]["priority_id"])
        write_json(module.PRIORITY_OUT, first)
        second = module.build_report(limited_args)["main_session_priority_handoff"]
        assert second["state_index"][omitted_id]["repeat_count"] == 2

        write_json(module.TRADE_GRADE_REPAIR_CONVEYOR, {"rows": [{
            "ticker": "AAA",
            "auto_tier": "Tier A",
            "repair_lane": "freshness_repair_after_band_review",
            "freshness_status": "stale",
            "freshness_ledger_state": "fresh",
            "decision_state": "watch",
            "repair_priority": 50,
            "source_open_status": "verified",
        }]})
        p1_handoff = module.build_report(args(module))["main_session_priority_handoff"]
        p1 = next(item for item in p1_handoff["items"] if item["ticker"] == "AAA")
        module.PRIORITY_DISPOSITION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.PRIORITY_DISPOSITION_LEDGER.write_text(json.dumps({
            "priority_id": p1["priority_id"],
            "disposition": "deferred",
            "recorded_at_utc": "2026-08-20T00:00:00Z",
            "candidate_signature": p1["candidate_signature"],
        }) + "\n", encoding="utf-8")
        write_json(module.PRIORITY_OUT, p1_handoff)
        unchanged = module.build_report(args(module))["main_session_priority_handoff"]
        assert all(item["priority_id"] != p1["priority_id"] for item in [unchanged["selected_item"]] if item)
        conveyor = json.loads(module.TRADE_GRADE_REPAIR_CONVEYOR.read_text(encoding="utf-8"))
        conveyor["rows"][0]["freshness_status"] = "blocked"
        write_json(module.TRADE_GRADE_REPAIR_CONVEYOR, conveyor)
        reopened = module.build_report(args(module))["main_session_priority_handoff"]
        reopened_item = next(item for item in reopened["items"] if item["priority_id"] == p1["priority_id"])
        assert reopened_item["disposition"]["status"] == "pending"
        assert reopened_item["disposition"]["reopened_after_terminal_disposition"] is True
        recurrence = module.attach_priority_state(
            p1,
            {},
            {p1["priority_id"]: {
                "disposition": "closed",
                "candidate_signature": p1["candidate_signature"],
                "recorded_at_utc": "2026-08-20T00:00:00Z",
            }},
        )
        assert recurrence["disposition"]["status"] == "pending"
        assert recurrence["disposition"]["reopened_after_terminal_disposition"] is True


def test_current_window_unusable_is_p0_even_before_deadline() -> None:
    module = load_module()
    item = module.current_window_priority({"summary": {
        "current_usable": False,
        "window_completion_state": "not_started",
        "critical_or_unreadable_roles": ["terminal_runner"],
    }})
    assert item and item["priority"] == "P0"


def test_unchanged_p1_ages_into_a_bounded_reescalation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.TRADE_GRADE_REPAIR_CONVEYOR, {"rows": [{
            "ticker": "AAA",
            "auto_tier": "Tier A",
            "repair_lane": "freshness_repair_after_band_review",
            "freshness_status": "stale",
            "freshness_ledger_state": "fresh",
            "decision_state": "watch",
            "repair_priority": 50,
            "source_open_status": "verified",
        }]})
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_observation_source = "heartbeat"
        first = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        p1 = first["selected_item"]
        assert p1["priority"] == "P1"
        assert p1["owner"] == "main_session_ticker_review_owner"
        assert p1["due_window"] == "next_main_session"
        first["items"][0]["repeat_count"] = 7
        first["state_index"][p1["priority_id"]]["repeat_count"] = 7
        write_json(module.PRIORITY_OUT, first)
        aged = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        assert aged["selected_item"]["repeat_count"] == 8
        assert aged["receipt"] == "ESCALATED_PRIORITY"


def test_main_session_priority_pickup_does_not_age_heartbeat_repeat_counter() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {"current_usable": False, "window_completion_state": "missed_after_deadline"},
        })
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_observation_source = "heartbeat"
        first = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        selected_id = first["selected_item"]["priority_id"]
        assert first["state_index"][selected_id]["repeat_count"] == 1
        assert first["observation"]["priority_repeat_age_advanced"] is True
        first["items"][0]["repeat_count"] = 4
        first["state_index"][selected_id]["repeat_count"] = 4
        write_json(module.PRIORITY_OUT, first)

        pickup_args = args(module, context="main_session")
        pickup_args.priority_observation_source = "main_session"
        pickup = module.build_report(pickup_args)["main_session_priority_handoff"]
        assert pickup["state_index"][selected_id]["repeat_count"] == 4
        assert pickup["observation"]["priority_repeat_age_advanced"] is False
        assert pickup["receipt"] == "NO_DELTA"


def test_forbidden_heartbeat_arguments_fail_before_writes() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        old_argv = sys.argv
        sys.argv = [
            str(SCRIPT), "--context", "heartbeat", "--write", "--append-ledger",
            "--out", str(module.OUT), "--ledger", str(module.LEDGER),
        ]
        try:
            assert module.main() == 2
        finally:
            sys.argv = old_argv
        assert not module.OUT.exists()
        assert not module.LEDGER.exists()

        sys.argv = [
            str(SCRIPT), "--context", "heartbeat", "--write", "--validate",
        ]
        try:
            assert module.main() == 2
        finally:
            sys.argv = old_argv
        assert not module.OUT.exists()
        assert not module.PRIORITY_OUT.exists()

        sys.argv = [
            str(SCRIPT), "--context", "heartbeat", "--write", "--validate",
            "--out", str(module.HEARTBEAT_OUT),
            "--priority-out", str(module.HEARTBEAT_PRIORITY_OUT),
            "--priority-observation-source", "heartbeat",
        ]
        try:
            assert module.main() == 0
        finally:
            sys.argv = old_argv
        assert module.HEARTBEAT_OUT.exists()
        assert module.HEARTBEAT_PRIORITY_OUT.exists()
        assert not module.OUT.exists()
        assert not module.PRIORITY_OUT.exists()


def main() -> int:
    test_digest_blocker_maps_to_safe_refresh()
    test_authority_widened_artifact_becomes_owner_decision()
    test_heartbeat_context_never_executes_and_rejects_execute_safe()
    test_repeated_signal_is_marked_for_pm_or_helper_residue()
    test_ticker_repair_handoff_is_deduplicated_and_non_executable()
    test_ticker_repair_handoff_survives_safe_action_refresh()
    test_priority_handoff_ranks_current_window_and_freshness_failure_before_ticker_debt()
    test_priority_disposition_requires_main_context_and_clean_closure_proof()
    test_fundamental_ticker_priority_requires_its_router_finding_to_clear()
    test_priority_lifecycle_deduplicates_ages_omitted_items_and_reopens_changed_deferral()
    test_current_window_unusable_is_p0_even_before_deadline()
    test_unchanged_p1_ages_into_a_bounded_reescalation()
    test_main_session_priority_pickup_does_not_age_heartbeat_repeat_counter()
    test_forbidden_heartbeat_arguments_fail_before_writes()
    print("main_session_escalation_consumer tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
