from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from veritas_finance_brief import SCHEMA, build_payload


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def base_paths(root: Path) -> dict[str, Path]:
    return {
        "finance_sync": root / "finance-decision-sync-spine.json",
        "trade_grade_cards": root / "trade-grade-decision-cards.json",
        "auto_router": root / "wf78-auto-tier-routing.json",
        "canonical_data_plane": root / "canonical-finance-data-plane.json",
        "cron_control": root / "cron-control-packet.json",
        "cron_freshness": root / "cron-freshness-spine.json",
        "market_loop": root / "finance-market-deployment-operating-loop.json",
        "band_hygiene": root / "band-hygiene-freshness-controller.json",
    }


def write_base_artifacts(root: Path, *, authority_widened: bool = False) -> dict[str, Path]:
    paths = base_paths(root)
    boundary = {
        "review_only": True,
        "capital_deployment_approved": authority_widened,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }
    write_json(paths["finance_sync"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": boundary,
        "summary": {
            "ticker_count": 4,
            "state_counts": {"blocked_missing_freshness": 2, "below_stop_or_invalidation": 1},
            "clean_for_paper_deployment_review_count": 0,
            "owner_action_required_count": 3,
            "sync_conflict_count": 0,
        },
        "rows": [
            {
                "ticker": "GOOG",
                "primary_state": "blocked_missing_freshness",
                "route_state": "A-READY",
                "current_price": 367.17,
                "band_status": "IN_BAND",
                "entry_band_low": 345.7,
                "entry_band_high": 369.82,
                "stop_or_invalidation": 332.3,
                "blockers": ["quote_not_intraday_fresh"],
                "owner_action_required": False,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
            {
                "ticker": "RTX",
                "primary_state": "blocked_missing_freshness",
                "route_state": "A-CHALLENGED",
                "band_status": "IN_BAND",
                "entry_policy_review_candidate": True,
                "entry_policy_review_action": "main_review_required",
                "blockers": ["band_exception_owner_review"],
                "owner_action_required": True,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
            {
                "ticker": "VMC",
                "primary_state": "blocked_missing_freshness",
                "route_state": "B-CANDIDATE",
                "band_status": "IN_BAND",
                "entry_policy_review_candidate": True,
                "entry_policy_review_action": "main_review_required",
                "blockers": ["band_exception_owner_review"],
                "owner_action_required": True,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
            {
                "ticker": "CVX",
                "primary_state": "below_stop_or_invalidation",
                "route_state": "A-WATCH",
                "band_status": "BELOW_STOP",
                "blockers": ["price_breaches_stop_or_below_stop"],
                "owner_action_required": True,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        ],
    })
    write_json(paths["trade_grade_cards"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": boundary,
        "summary": {
            "card_count": 4,
            "decision_state_counts": {"review_ready": 1, "monitor_only": 2, "below_stop_or_invalidation": 1},
            "approval_card_draft_count": 0,
            "authority_flags_false_by_contract": not authority_widened,
        },
        "cards": [
            {
                "ticker": "GOOG",
                "auto_tier": "Tier A",
                "auto_state": "A-READY",
                "primary_state": "approval_card_clean",
                "decision_state": "review_ready",
                "owner_action_required": True,
                "current_price": {"latest_known_price": 367.11},
                "entry_band": {"low": 345.7, "high": 369.82, "band_status": "IN_BAND"},
                "stop_or_invalidation": {"level": 332.3},
            },
            {"ticker": "RTX", "auto_tier": "Tier A", "auto_state": "A-CHALLENGED", "decision_state": "monitor_only"},
            {"ticker": "VMC", "auto_tier": "Tier B", "auto_state": "B-CANDIDATE", "decision_state": "monitor_only"},
            {"ticker": "CVX", "auto_tier": "Tier A", "auto_state": "A-WATCH", "decision_state": "below_stop_or_invalidation"},
        ],
    })
    write_json(paths["auto_router"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": boundary,
        "summary": {"auto_tier_counts": {"Tier A": 3, "Tier B": 1}},
        "rows": [
            {"ticker": "GOOG", "auto_tier": "Tier A", "auto_state": "A-READY"},
            {"ticker": "RTX", "auto_tier": "Tier A", "auto_state": "A-CHALLENGED"},
            {"ticker": "VMC", "auto_tier": "Tier B", "auto_state": "B-CANDIDATE"},
            {"ticker": "CVX", "auto_tier": "Tier A", "auto_state": "A-WATCH"},
        ],
    })
    write_json(paths["canonical_data_plane"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": boundary,
        "summary": {"tier_counts": {"Tier A": 3, "Tier B": 1}, "forbidden_authority_true_count": 1 if authority_widened else 0},
    })
    write_json(paths["cron_control"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": {"review_only": True, "cron_schedule_mutation_allowed": False, "owner_approval_inferred": False},
        "summary": {
            "blocked_count": 1,
            "escalation_signal_count": 1,
            "live_scheduler_last_run_exception_count": 1,
            "should_wake_main_session": True,
        },
        "escalation": {
            "escalation_signals": [
                {"source": "cron_job:Finance - Weekday Post-Close Review Refresh", "signal_class": "BLOCKED"}
            ]
        },
    })
    write_json(paths["cron_freshness"], {
        "status": "blocked",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": {"review_only": True, "cron_schedule_mutation_allowed": False, "owner_approval_inferred": False},
        "summary": {"blocked_count": 1},
    })
    write_json(paths["market_loop"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": boundary,
        "operator_action": {"state": "review_only"},
        "next_safe_action": "Review only.",
    })
    write_json(paths["band_hygiene"], {
        "status": "ok",
        "generated_at_utc": "2026-06-16T04:00:00Z",
        "authority_boundary": boundary,
        "summary": {"entry_policy_review_candidate_count": 2},
    })
    return paths


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_brief_surfaces_secondary_candidates(errors: list[str]) -> None:
    with TemporaryDirectory() as temp:
        payload = build_payload(write_base_artifacts(Path(temp)))
    attention = payload["attention_queues"]
    entry_tickers = [row["ticker"] for row in attention["entry_policy_review"]]
    secondary_tickers = [row["ticker"] for row in attention["secondary_opportunities_not_suppressed"]]
    review_tickers = [row["ticker"] for row in attention["review_ready_or_post_close_review_ready"]]
    actions = [row["action"] for row in payload["main_session_actions"]]
    expect(payload["status"] == "ok", f"brief should validate: {payload['validation']}", errors)
    expect("RTX" in entry_tickers and "VMC" in entry_tickers, f"entry policy queue missing candidates: {entry_tickers}", errors)
    expect("VMC" in secondary_tickers, f"Tier B secondary candidate should remain visible: {secondary_tickers}", errors)
    expect("GOOG" in review_tickers, f"review-ready card should surface: {review_tickers}", errors)
    expect("review_entry_policy_candidates" in actions, f"main actions should include entry-policy review: {actions}", errors)
    expect("repair_or_acknowledge_cron_blockers" in actions, f"main actions should include cron blocker repair: {actions}", errors)


def test_brief_fails_closed_on_authority_widening(errors: list[str]) -> None:
    with TemporaryDirectory() as temp:
        payload = build_payload(write_base_artifacts(Path(temp), authority_widened=True))
    expect(payload["status"] == "error", f"authority widening must fail payload: {payload['validation']}", errors)
    expect("source_authority_widened" in payload["validation"]["errors"], f"missing authority error: {payload['validation']}", errors)


def test_brief_delta_surfaces_new_candidates(errors: list[str]) -> None:
    previous = {
        "schema": SCHEMA,
        "generated_at_utc": "2026-06-16T03:00:00Z",
        "summary": {
            "cron_status": "ok",
            "cron_blocked_count": 0,
            "cron_escalation_signal_count": 0,
            "scheduler_exception_count": 0,
            "review_ready_card_count": 1,
            "entry_policy_review_candidate_count": 1,
            "secondary_opportunity_visible_count": 0,
            "owner_action_required_count": 1,
            "sync_conflict_count": 0,
        },
        "attention_queues": {
            "review_ready_or_post_close_review_ready": [{"ticker": "GOOG"}],
            "entry_policy_review": [{"ticker": "RTX"}],
            "secondary_opportunities_not_suppressed": [],
            "below_stop_or_reclaim_first": [],
            "promotion_vetoed": [],
            "freshness_blocked": [],
            "cron_blockers": [],
        },
    }
    with TemporaryDirectory() as temp:
        payload = build_payload(write_base_artifacts(Path(temp)), previous_payload=previous)
    delta = payload["status_delta"]
    expect(delta["has_previous"] is True, f"delta should detect baseline: {delta}", errors)
    expect(delta["changed"] is True, f"delta should detect changes: {delta}", errors)
    expect(
        delta["queue_changes"]["entry_policy_review"]["added"] == ["VMC"],
        f"delta should show VMC as new entry-policy candidate: {delta}",
        errors,
    )
    expect(
        delta["queue_changes"]["secondary_opportunities_not_suppressed"]["added"] == ["VMC"],
        f"delta should show VMC as new secondary visible candidate: {delta}",
        errors,
    )
    expect(
        delta["summary_changes"]["cron_blocked_count"] == {"from": 0, "to": 1},
        f"delta should show cron blocker count change: {delta}",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    test_brief_surfaces_secondary_candidates(errors)
    test_brief_fails_closed_on_authority_widening(errors)
    test_brief_delta_surfaces_new_candidates(errors)
    if errors:
        print("veritas_finance_brief_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("veritas_finance_brief_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
