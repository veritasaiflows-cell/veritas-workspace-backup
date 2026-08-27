from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import finance_recommendation_correctness_ledger as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    proposal_id = "post-close:NVDA:capital-deployment-review:2026-06-11"
    inputs = {
        "capital_validation": {"status": "ok"},
        "wf55_reco_ledger": {
            "durable_v2_ledger": {
                "recommendation_tracking_rows": 1,
                "later_outcome_graded_rows": 43,
                "grade_history": {"graded_ledger_event_count": 43},
            },
            "tracked_rows": [
                {
                    "ticker": "NVDA",
                    "payload": {"recommendation_id": proposal_id},
                    "forward_scorecard": {
                        "status": "pending",
                        "outcome_grade_assigned": False,
                        "outcome_grade_status": "not_assigned_pending_mature_window_and_review",
                    },
                }
            ],
        },
        "capital_recs": {
            "proposals": [
                {
                    "proposal_id": proposal_id,
                    "ticker_or_scope": "NVDA",
                    "generated_at_utc": "2026-06-11T20:00:00Z",
                    "owner_decision_required": True,
                    "owner_approval_granted": False,
                    "apply_allowed": False,
                    "trade_or_account_action_allowed": False,
                    "portfolio_mutation_allowed": False,
                    "technical_gate": {
                        "close": 100.0,
                        "current_band_low": 95.0,
                        "current_band_high": 105.0,
                        "below_stop": False,
                        "entry_band_status": "IN_BAND",
                    },
                    "risk_rule_check": {"status": "review_required"},
                    "concentration_check": {"status": "review_required"},
                    "catalyst_gate": {"status": "review_required"},
                    "official_earnings_gate": {"status": "available_review_only"},
                    "source_freshness": {
                        "explicit_blocker": False,
                        "owner_review_required": True,
                        "capital_action_allowed": False,
                    },
                    "proposed_state": {"review_packet_only": True, "recommendation_posture": "deploy_candidate"},
                    "current_state": {"daily_review_state": "PROMOTION REVIEW"},
                }
            ]
        },
    }
    ledger = mod.build_ledger(inputs)
    row = ledger["rows"][0]
    summary = ledger["summary"]
    expect(row["process_correctness_status"] == "ok", "process correctness should be ok", errors)
    expect(row["outcome_quality_status"] == "pending", "outcome quality should come from WF55 scorecard", errors)
    expect(summary["process_correctness_ok_rows"] == 1, "summary process ok count", errors)
    expect(summary["outcome_quality_pending_rows"] == 1, "summary outcome pending count", errors)
    expect(summary["durable_v2_recommendation_tracking_rows"] == 1, "summary durable row count", errors)
    expect(summary["later_outcome_graded_rows_metric_scope"] == "current_capital_recommendation_rows_only", "later outcome metric scope missing", errors)
    expect(summary["capital_recommendation_later_outcome_graded_rows"] == 0, "current capital row graded count should stay separate", errors)
    expect(summary["durable_recommendation_later_outcome_graded_rows"] == 43, "durable WF88 grade count not surfaced", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("finance_recommendation_correctness_ledger_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
