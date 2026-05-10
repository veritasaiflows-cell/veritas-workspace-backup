from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import daily_review_objects


WORKSPACE = SCRIPTS_DIR.parent


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)



def test_trust_escalation_priority(errors: list[str]) -> None:
    review_objects = [
        {"id": "sys", "category": "trust_ceiling", "signal_score": 90},
        {"id": "etn", "category": "promotion_review", "signal_score": 92, "ticker": "ETN"},
        {"id": "gs", "category": "promotion_review", "signal_score": 92, "ticker": "GS"},
        {"id": "jpm", "category": "near_deployable", "signal_score": 86, "ticker": "JPM"},
    ]
    system = {"stop_line": False, "trust_level": "review_required"}
    escalations = daily_review_objects.ranked_escalations(review_objects, system)
    expect(bool(escalations), "escalations should not be empty", errors)
    expect(escalations[0].get("category") == "trust_ceiling", "trust ceiling should be escalated first when trust is degraded", errors)
    expect(len(escalations) == 3, "degraded trust should cap escalations at 3", errors)



def test_recommendation_boundaries(errors: list[str]) -> None:
    system_blocked = {"stop_line": True, "critical": 0}
    system_clean = {"stop_line": False, "critical": 0}
    surface = {"surface_state": "PROMOTION REVIEW", "days_to_earnings": 40}
    deployment = {"in_entry_band": True}
    proposal = {"canonical_apply_eligible": True}

    blocked = daily_review_objects.recommendation_class(surface, deployment, proposal, system_blocked)
    clean = daily_review_objects.recommendation_class(surface, deployment, proposal, system_clean)

    expect(blocked == "no_new_approval", "stop-line workflow should block approval recommendations", errors)
    expect(clean == "review_for_possible_add", "promotion-review candidate should remain owner-gated, not autonomous", errors)



def test_live_artifact_boundaries(errors: list[str]) -> None:
    path = WORKSPACE / "tmp" / "daily-review-objects-post-close.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    expect(data.get("consumer_posture") == "review_only", "daily review objects should remain review_only", errors)
    expect(data.get("canonical_mutation_allowed") is False, "daily review objects must not allow canonical mutation", errors)
    expect(data.get("portfolio_mutation_allowed") is False, "daily review objects must not allow portfolio mutation", errors)
    expect(data.get("deployment_state_mutation_allowed") is False, "daily review objects must not allow deployment-state mutation", errors)
    expect(data.get("trade_execution_allowed") is False, "daily review objects must not allow trade execution", errors)
    expect(data.get("owner_approval_required_for_capital") is True, "capital recommendations must require owner approval", errors)
    expect(data.get("owner_approval_granted") is False, "daily review objects must not infer owner approval", errors)
    source_freshness = data.get("source_freshness") or {}
    expect(source_freshness.get("canonical_note_mutation_allowed") is False, "source freshness must not allow canonical mutation", errors)
    expect(source_freshness.get("capital_action_allowed") is False, "source freshness must not grant capital action", errors)
    expect(source_freshness.get("trust_level") in {"clean", "review_required", "blocked"}, "daily review must emit normalized source trust", errors)
    portfolio_call = ((data.get("summary") or {}).get("portfolio_call") or {})
    expect(portfolio_call.get("recommended_action") != "autonomous_apply", "portfolio call must never imply autonomous apply", errors)
    for item in data.get("capital_deployment_recommendations", []) or []:
        expect(item.get("owner_approval_required") is True, "every capital recommendation must require owner approval", errors)
        expect(item.get("owner_approval_granted") is False, "capital recommendations must not infer owner approval", errors)
        expect(item.get("canonical_mutation_allowed") is False, "capital recommendations must not allow canonical mutation", errors)
        expect(item.get("portfolio_mutation_allowed") is False, "capital recommendations must not allow portfolio mutation", errors)
        expect(item.get("deployment_state_mutation_allowed") is False, "capital recommendations must not allow deployment-state mutation", errors)
        expect(item.get("trade_execution_allowed") is False, "capital recommendations must not allow trade execution", errors)
        expect(item.get("recommended_action") != "autonomous_apply", "capital recommendations must not imply autonomous apply", errors)
        expect(item.get("recommendation_action") in {"deploy", "wait", "reject", "review"}, "capital recommendations must map to WF42 action vocabulary", errors)
        expect(isinstance(item.get("evidence_provenance"), list) and bool(item.get("evidence_provenance")), "capital recommendations must carry evidence provenance", errors)
        expect(isinstance(item.get("source_freshness"), dict) and bool(item.get("source_freshness")), "capital recommendations must carry source freshness", errors)
        expect("sector/correlation" in " ".join(item.get("missing_evidence") or []), "missing sector/correlation artifact must be explicit", errors)
        expect(item.get("sector_correlation_check") == "missing_artifact_manual_fallback_required", "sector/correlation check must fail to explicit manual fallback", errors)
        expect(item.get("fresh_intelligence_status") != "not_wired_yet", "capital recommendations should consume the market-intelligence router when the live artifact exists", errors)


def test_market_intelligence_review_object(errors: list[str]) -> None:
    event_packet = {
        "events": [
            {"rank": 1, "ticker_or_macro_sleeve": "ETN", "recommended_route": "promotion_review", "urgency": "today", "materiality_score": 4}
        ],
        "escalations": [
            {
                "rank": 1,
                "ticker_or_macro_sleeve": "ETN",
                "recommended_route": "promotion_review",
                "urgency": "today",
                "materiality_score": 4,
                "event_type": "sector",
                "event_title": "ETN is in promotion review",
                "evidence": ["in band"],
                "blocked_reason": "Owner approval required.",
            }
        ],
    }
    objects = daily_review_objects.market_intelligence_review_objects("post-close", event_packet)
    expect(len(objects) == 1, "market-intelligence escalation should become a daily review object", errors)
    expect(objects[0].get("category") == "fresh_intelligence", "market-intelligence review object should use fresh_intelligence category", errors)
    status = daily_review_objects.fresh_intelligence_status_for("ETN", event_packet)
    expect(status == "promotion_review:today:materiality_4", "ticker capital packets should carry routed fresh-intelligence status", errors)



def main() -> int:
    errors: list[str] = []
    test_trust_escalation_priority(errors)
    test_recommendation_boundaries(errors)
    test_live_artifact_boundaries(errors)
    test_market_intelligence_review_object(errors)
    if errors:
        print("daily_review_objects_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("daily_review_objects_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
