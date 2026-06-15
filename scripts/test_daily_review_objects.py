from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import daily_review_objects


WORKSPACE = SCRIPTS_DIR.parent

CAPITAL_ADVICE_FIELDS = {
    "thesis",
    "setup_summary",
    "catalyst_risk",
    "sizing_risk_envelope",
    "base_case",
    "bull_case",
    "bear_case",
}

FORBIDDEN_FINAL_ADVICE_PATTERNS = [
    r"\bprobability\b",
    r"\bwin\s+probability\b",
    r"\bwin_probability\b",
    r"\bwin\s+rate\b",
    r"\bwin_rate\b",
    r"\bdeploy\s+probability\b",
    r"\bdeploy_probability\b",
    r"\bexpected\s+return\b",
    r"\bexpected_return\b",
    r"\bcalibrated\s+score\b",
    r"\bcalibrated\s+readiness\s+score\b",
    r"\bmodel-ranked\b",
    r"\bmodel\s+ranked\b",
    r"\bmodel_ranked\b",
    r"\bpredicted\s+outcome\b",
    r"\bforecast\s+accuracy\b",
    r"\b\d+(?:\.\d+)?\s*%\s+chance\b",
    r"\b\d+(?:\.\d+)?\s*%\s+likelihood\b",
    r"\bprobability\s*[:=]\s*\d+(?:\.\d+)?\s*%?\b",
    r"\bautonomous\b",
]

FORBIDDEN_SIZING_ENVELOPE_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?\s*%",
    r'"range"\s*:',
    r'"max"\s*:',
]


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
        missing_fields = sorted(field for field in CAPITAL_ADVICE_FIELDS if field not in item)
        expect(not missing_fields, f"capital recommendations missing final-advice fields: {missing_fields}", errors)
        for field in CAPITAL_ADVICE_FIELDS:
            expect(bool(item.get(field)), f"capital recommendation {field} must not be empty", errors)
        final_advice_text = json.dumps({field: item.get(field) for field in CAPITAL_ADVICE_FIELDS}, sort_keys=True).lower()
        for pattern in FORBIDDEN_FINAL_ADVICE_PATTERNS:
            expect(re.search(pattern, final_advice_text) is None, f"final-advice field contains forbidden readiness/probability/autonomy language: {pattern}", errors)
        nested_item_text = json.dumps(item, sort_keys=True).lower()
        for pattern in FORBIDDEN_FINAL_ADVICE_PATTERNS:
            expect(re.search(pattern, nested_item_text) is None, f"capital recommendation nested field contains forbidden readiness/probability/autonomy language: {pattern}", errors)
        expect("confidence_basis" in item, "capital recommendation confidence must carry heuristic/uncalibrated annotation", errors)
        expect("signal_score_basis" in item, "capital recommendation signal_score must carry heuristic/uncalibrated annotation", errors)
        annotation_text = f"{item.get('confidence_basis', '')} {item.get('signal_score_basis', '')}".lower()
        expect("heuristic" in annotation_text and "uncalibrated" in annotation_text, "confidence/signal annotations must be explicitly heuristic and uncalibrated", errors)
        sizing_envelope = item.get("sizing_risk_envelope")
        expect(isinstance(sizing_envelope, dict), "sizing_risk_envelope must be a structured dictionary", errors)
        if isinstance(sizing_envelope, dict):
            expect("config_sizing_rule" not in sizing_envelope, "sizing envelope must not expose raw config sizing ranges/maxes", errors)
            sizing_text = json.dumps(sizing_envelope, sort_keys=True).lower()
            for pattern in FORBIDDEN_SIZING_ENVELOPE_PATTERNS:
                expect(re.search(pattern, sizing_text) is None, f"sizing envelope contains actionable position-sizing language: {pattern}", errors)
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
        sector_status = item.get("sector_correlation_check")
        missing_text = " ".join(item.get("missing_evidence") or [])
        if sector_status == "available_review_only":
            expect("sector/correlation" not in missing_text, "fresh sector/correlation artifacts should not be listed as missing", errors)
            context = item.get("sector_context") or {}
            expect(context.get("status") == "available_review_only", "fresh sector/correlation context should be embedded", errors)
            expect(bool(context.get("fresh_artifacts")), "fresh sector/correlation context should name the fresh artifacts used", errors)
        else:
            expect("sector/correlation" in missing_text, "missing sector/correlation artifact must be explicit", errors)
            expect(sector_status == "missing_artifact_manual_fallback_required", "sector/correlation check must fail to explicit manual fallback", errors)
        expect(item.get("fresh_intelligence_status") != "not_wired_yet", "capital recommendations should consume the market-intelligence router when the live artifact exists", errors)

    for collection_name in ("review_objects", "escalations"):
        for item in data.get(collection_name, []) or []:
            if not isinstance(item, dict) or "signal_score" not in item:
                continue
            expect("signal_score_basis" in item, f"{collection_name} signal_score must carry heuristic/uncalibrated annotation", errors)
            basis = str(item.get("signal_score_basis", "")).lower()
            expect(
                "heuristic" in basis and "uncalibrated" in basis,
                f"{collection_name} signal_score_basis must be explicitly heuristic and uncalibrated",
                errors,
            )


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_old() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sector_board_doc(generated_at: str) -> dict:
    return {
        "generated_at_utc": generated_at,
        "status": "ok",
        "sectors": [
            {
                "ticker": "XLK",
                "sector": "Technology",
                "leadership_status": "improving_leadership",
                "underexposed": False,
                "portfolio_exposure": {"tickers": ["NVDA"], "draft_weight_pct": 25, "status": "at_cap"},
                "tracked_universe_candidates": [],
                "promotion_review_status": [{"candidate": "NVDA", "owner_approval_granted": False}],
                "warnings": ["STALE_BOARD_WARNING" if generated_at == old_stamp else "FRESH_BOARD_WARNING"],
            }
        ],
    }


def sector_correlation_doc(generated_at: str) -> dict:
    return {
        "generated_at_utc": generated_at,
        "status": "ok",
        "promotion_impact_checks": [
            {
                "ticker": "NVDA",
                "candidate_sector": "Technology",
                "current_sector_weight_pct": 25,
                "cap_status_after": "at_cap",
                "warnings": ["STALE_CORR_WARNING" if generated_at == old_stamp else "FRESH_CORR_WARNING"],
            }
        ],
    }


old_stamp = iso_old()


def test_sector_context_freshness_gating(errors: list[str]) -> None:
    fresh_stamp = iso_now()

    stale_board_fresh_corr = daily_review_objects.sector_context_for_ticker(
        "NVDA", sector_board_doc(old_stamp), sector_correlation_doc(fresh_stamp)
    )
    expect(stale_board_fresh_corr.get("fresh_artifacts") == ["tmp/sector-correlation-check.json"], "stale board should not be listed as fresh", errors)
    expect(stale_board_fresh_corr.get("sector_etf") is None, "stale board ETF field must not leak", errors)
    expect(stale_board_fresh_corr.get("leadership_status") is None, "stale board leadership must not leak", errors)
    expect("STALE_BOARD_WARNING" not in stale_board_fresh_corr.get("warnings", []), "stale board warnings must not leak", errors)
    expect("FRESH_CORR_WARNING" in stale_board_fresh_corr.get("warnings", []), "fresh correlation warning should remain visible", errors)

    fresh_board_stale_corr = daily_review_objects.sector_context_for_ticker(
        "NVDA", sector_board_doc(fresh_stamp), sector_correlation_doc(old_stamp)
    )
    expect(fresh_board_stale_corr.get("fresh_artifacts") == ["tmp/sector-expansion-board.json"], "stale correlation should not be listed as fresh", errors)
    expect(fresh_board_stale_corr.get("sector_etf") == "XLK", "fresh board ETF field should remain available", errors)
    expect("FRESH_BOARD_WARNING" in fresh_board_stale_corr.get("warnings", []), "fresh board warning should remain visible", errors)
    expect("STALE_CORR_WARNING" not in fresh_board_stale_corr.get("warnings", []), "stale correlation warnings must not leak", errors)

    both_stale = daily_review_objects.sector_context_for_ticker(
        "NVDA", sector_board_doc(old_stamp), sector_correlation_doc(old_stamp)
    )
    expect(both_stale.get("status") == "missing_or_stale_manual_fallback_required", "both stale artifacts must force manual fallback", errors)


def test_live_band_status_overrides_proposed_reclaim_status(errors: list[str]) -> None:
    surface = {"band_position": "1.2% above band top"}
    deployment = {"in_entry_band": False, "below_stop": False}
    proposal = {"band_status": "BELOW_STOP"}
    status = daily_review_objects.live_entry_band_status(surface, deployment, proposal)
    note = daily_review_objects.combined_band_status_note("BELOW_STOP", "BELOW_RECLAIM_STOP", status, deployment)
    expect(status == "ABOVE_BAND_WAIT", f"live above-band/no-chase status should override proposed reclaim-stop status: {status}", errors)
    expect("Live written-band status is ABOVE_BAND_WAIT" in str(note), f"status mismatch should be auditable: {note}", errors)


def test_in_band_conditional_review_not_labeled_wait_for_band(errors: list[str]) -> None:
    system = {"trust_level": "clean", "stop_line": False, "critical": 0, "trust_ceiling_reasons": [], "macro_gate": "CLEAN"}
    review_objects = [{
        "object_type": "ticker",
        "ticker": "ETN",
        "category": "near_deployable",
        "surface_state": "DEPLOYABLE NOW",
        "recommendation_class": "conditional_pullback_review",
        "band_status": "IN_BAND",
        "band_position": "IN BAND",
        "macro_gate": "CLEAN",
        "blockers": [],
        "evidence": ["in band"],
        "supporting_artifacts": ["tmp/deployment-readiness-surface.json"],
        "owner_reads": ["03. Portfolio/Execution Board.md"],
        "signal_score": 80,
        "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
    }]
    recommendations, _summary = daily_review_objects.capital_recommendations(review_objects, system)
    expect(recommendations[0]["recommended_action"] == "owner_decision_required", f"in-band conditional review must not say wait_for_band: {recommendations[0]}", errors)
    expect(recommendations[0]["recommendation_action"] == "review", "owner decision required should map to WF42 review, not deploy/wait", errors)


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
    test_sector_context_freshness_gating(errors)
    test_live_band_status_overrides_proposed_reclaim_status(errors)
    test_in_band_conditional_review_not_labeled_wait_for_band(errors)
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
