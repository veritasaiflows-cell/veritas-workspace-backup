#!/usr/bin/env python3
"""WF78 Phase 3: deterministic Tier B->A competitive routing gate.

This gate consumes the Phase 1 funnel contract (`wf78_tier_funnel_contract.py`)
and evaluates the scarce, competitive Tier B -> Tier A transition. Unlike the
Phase 2 D->C / C->B gate, Tier A admission is a contest for one of only 25 seats:

  - A nominee must already be B-VALIDATED (the ladder is
    B-CANDIDATE -> B-VALIDATED -> A-NOMINEE -> A-APPROVED).
  - It must prove the 10 hard-evidence families (source-open, current ticker
    card, price/band/stop, thesis+counter-thesis, risk register, fundamentals,
    valuation, analyst layer, portfolio-fit, deployment/readiness).
  - If Tier A has an open seat (admitted < 25) it may be nominated after the
    hard-evidence gate passes.
  - If Tier A is full (25 admitted) it must defeat the weakest relevant incumbent
    by at least 5 points; scores create eligibility, never promotion.
  - Tier A capacity is the 11th required family, handled by the open-seat or
    challenger logic.

The deepest a candidate can reach through this gate is
`eligible_for_auto_tier_a_routing`. That is non-capital routing eligibility only:
`A-DEPLOY` and every capital/trade/order/account action still require separate
exact approval before any paper/live/account action.

Report-only proof and derived routing input. It mutates no universe/canon/portfolio
state, infers no capital approval, and authorizes no paper/live/account action.
D->C and C->B are routed to the Phase 2 gate.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

from wf78_tier_funnel_contract import (
    SCHEMA as CONTRACT_SCHEMA,
    STATE_VOCABULARY,
    TIER_A_CAP,
    TIER_A_CHALLENGER_MARGIN_POINTS,
    TRANSITIONS,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

CONTRACT_GATE = TMP / "wf78-tier-funnel-contract.json"
CAPACITY_POLICY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
DECISION_CARDS = TMP / "trade-grade-decision-cards.json"

DEFAULT_OUT = TMP / "wf78-tier-a-competitive-promotion-gate.json"
SCHEMA = "veritas.wf78_tier_a_competitive_promotion_gate.v1"

HANDLED_PAIR = ("tier_b", "tier_a")
ROUTED_ELSEWHERE = {
    ("tier_d", "tier_c"): "tier_funnel_promotion_gate",
    ("tier_c", "tier_b"): "tier_funnel_promotion_gate",
}

REQUIRED_VALIDATED_STATE = "B-VALIDATED"
# Tier B from-states that block a Tier A nomination outright (must repair/revalidate).
BLOCKING_FROM_STATES = {"B-STALE", "B-CHALLENGED", "B-REJECT-TO-C"}
# Family that the seat/challenger logic handles, not the checkbox gate.
COMPETITION_FAMILY = "Tier A capacity check"
OWNER_APPROVAL_FAMILY = "owner approval"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "evaluation_gate_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_state_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "tier_a_admission_executed": False,
    "promotion_by_score_or_checklist_alone_allowed": False,
    "tier_a_routing_allowed": True,
    "tier_a_promotion_allowed": True,
    "incumbent_displacement_executed": False,
    "capital_deployment_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "report_only",
    "evaluation_gate_only",
    "automated_non_capital_routing_allowed",
    "derived_state_only",
    "tier_a_routing_allowed",
    "tier_a_promotion_allowed",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

STOP_LINES = [
    "This gate evaluates non-capital Tier A routing eligibility only; it does not grant capital approval.",
    "eligible_for_auto_tier_a_routing is routing eligibility, not deployment or order approval.",
    "Scores and evidence may create routing eligibility; they never authorize capital deployment or execution.",
    "No incumbent is displaced into execution authority by this gate.",
    "A-DEPLOY still requires a separate exact order approval before any paper/live/account action.",
    "No import/apply, no capital deployment, no canon/portfolio mutation, no money movement.",
    "D->C and C->B are out of scope here; route them to the Phase 2 gate.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }


def b_to_a_required_evidence() -> list[str]:
    return [str(item) for item in as_list(as_dict(TRANSITIONS.get("b_to_a")).get("required_evidence"))]


def hard_evidence_families() -> list[str]:
    return [item for item in b_to_a_required_evidence() if item not in {COMPETITION_FAMILY, OWNER_APPROVAL_FAMILY}]


def has_text(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    if isinstance(value, dict):
        return any(has_text(item) for item in value.values())
    return value is not None


def evidence_from_decision_card(card: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    source_freshness = as_dict(card.get("source_freshness"))
    entry_band = as_dict(card.get("entry_band"))
    stop = as_dict(card.get("stop_or_invalidation"))
    authority = as_dict(card.get("authority_boundary"))
    current_price = card.get("current_price")

    if source_freshness and not authority.get("source_open_required_missing", False):
        evidence.append("source-open proof")
    if card.get("ticker") and card.get("name") and source_freshness:
        evidence.append("complete current ticker card")
    if (
        current_price is not None
        and entry_band.get("low") is not None
        and entry_band.get("high") is not None
        and stop.get("level") is not None
    ):
        evidence.append("current price, entry band, and stop/invalidation")
    if has_text(card.get("thesis_snapshot")) and has_text(card.get("counterargument")):
        evidence.append("thesis and counter-thesis")
    if has_text(card.get("key_risks")) and stop.get("level") is not None:
        evidence.append("risk register and invalidation event")
    if has_text(card.get("base_case")) and has_text(card.get("bull_case")) and has_text(card.get("bear_case")):
        evidence.append("current fundamentals/earnings context")
    if has_text(card.get("sizing_staggering_recommendation")) or has_text(card.get("decision_state_reason")):
        evidence.append("valuation context")
    if has_text(as_dict(card.get("source_drillback")).get("analyst_consensus")) or has_text(card.get("source_drillback")):
        evidence.append("analyst/revision layer")
    if has_text(card.get("queue_state")) or has_text(card.get("primary_state")):
        evidence.append("portfolio-fit and concentration check")
    if has_text(card.get("decision_state")) and entry_band.get("band_status") not in {None, "UNKNOWN"}:
        evidence.append("deployment/readiness state")
    return sorted(set(evidence), key=hard_evidence_families().index)


def score_from_decision_card(card: dict[str, Any], route: dict[str, Any]) -> float:
    evidence_count = len(evidence_from_decision_card(card))
    score = evidence_count * 8.0
    decision_state = str(card.get("decision_state") or "")
    band_status = str(as_dict(card.get("entry_band")).get("band_status") or "")
    if decision_state in {"no_chase", "monitor_only"}:
        score -= 5
    if band_status == "IN_BAND":
        score += 8
    elif band_status in {"NEAR_BAND", "BELOW_BAND"}:
        score += 4
    elif band_status == "ABOVE_BAND":
        score -= 3
    if route.get("auto_state") == "B-VALIDATED":
        score += 5
    return round(score, 2)


def live_b_to_a_candidates(auto_router: dict[str, Any], decision_cards: dict[str, Any]) -> list[dict[str, Any]]:
    cards = by_ticker(as_list(decision_cards.get("cards")))
    candidates: list[dict[str, Any]] = []
    for route in as_list(auto_router.get("rows")):
        if not isinstance(route, dict):
            continue
        prior_gate_promotion = "auto_promoted_from_b_to_a_competitive_gate" in str(route.get("route_reason") or "")
        if route.get("auto_tier") != "Tier B" and not prior_gate_promotion:
            continue
        ticker = str(route.get("ticker") or "").upper()
        card = cards.get(ticker, {})
        evidence = evidence_from_decision_card(card)
        current_state = "B-VALIDATED" if prior_gate_promotion else route.get("auto_state") or "B-CANDIDATE"
        candidates.append(
            normalize_candidate(
                {
                    "ticker": ticker,
                    "name": route.get("name") or card.get("name"),
                    "from_tier": "tier_b",
                    "to_tier": "tier_a",
                    "current_state": current_state,
                    "evidence_present": evidence,
                    "score": score_from_decision_card(card, route),
                    "sector": route.get("sector"),
                    "portfolio_role": route.get("legacy_monitoring_role") or card.get("queue_state"),
                }
            )
        )
    return candidates


def live_tier_a_incumbents(auto_router: dict[str, Any], decision_cards: dict[str, Any]) -> list[dict[str, Any]]:
    cards = by_ticker(as_list(decision_cards.get("cards")))
    incumbents: list[dict[str, Any]] = []
    for route in as_list(auto_router.get("rows")):
        if not isinstance(route, dict) or route.get("auto_tier") != "Tier A":
            continue
        ticker = str(route.get("ticker") or "").upper()
        card = cards.get(ticker, {})
        incumbents.append(
            {
                "ticker": ticker,
                "score": score_from_decision_card(card, route),
                "sector": route.get("sector"),
                "portfolio_role": route.get("legacy_monitoring_role") or card.get("queue_state"),
            }
        )
    return incumbents


def as_score(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(raw.get("ticker") or "").upper() or None,
        "name": raw.get("name"),
        "from_tier": str(raw.get("from_tier") or "tier_b").strip(),
        "to_tier": str(raw.get("to_tier") or "tier_a").strip(),
        "current_state": str(raw.get("current_state") or "").strip() or None,
        "evidence_present": [str(item) for item in as_list(raw.get("evidence_present"))],
        "score": as_score(raw.get("score")),
        "sector": raw.get("sector"),
        "factor": raw.get("factor"),
        "portfolio_role": raw.get("portfolio_role"),
    }


def normalize_incumbent(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(raw.get("ticker") or "").upper() or None,
        "score": as_score(raw.get("score")),
        "sector": raw.get("sector"),
        "factor": raw.get("factor"),
        "portfolio_role": raw.get("portfolio_role"),
    }


def weakest_relevant_incumbent(candidate: dict[str, Any], incumbents: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The weakest incumbent that shares the candidate's sector, factor, or role;
    falls back to the globally weakest incumbent when none are relevant."""
    scored = [inc for inc in incumbents if inc.get("score") is not None]
    if not scored:
        return None
    relevant = [
        inc
        for inc in scored
        if (candidate.get("sector") is not None and inc.get("sector") == candidate.get("sector"))
        or (candidate.get("factor") is not None and inc.get("factor") == candidate.get("factor"))
        or (candidate.get("portfolio_role") is not None and inc.get("portfolio_role") == candidate.get("portfolio_role"))
    ]
    pool = relevant or scored
    return min(pool, key=lambda inc: inc["score"])


def evaluate_b_to_a(candidate: dict[str, Any], roster_state: dict[str, Any]) -> dict[str, Any]:
    """Deterministically evaluate one Tier B -> Tier A nomination against the contract.

    `roster_state` carries tier_a_admitted (int), tier_a_cap (int),
    open_seats_reserved_this_run (int, mutated as open-seat nominees accumulate),
    and incumbents (list of normalized incumbents with scores).
    """
    from_tier = candidate["from_tier"]
    to_tier = candidate["to_tier"]
    pair = (from_tier, to_tier)

    base = {
        "ticker": candidate["ticker"],
        "name": candidate.get("name"),
        "from_tier": from_tier,
        "to_tier": to_tier,
        "current_state": candidate.get("current_state"),
        "score": candidate.get("score"),
        "tier_a_admission_executed": False,
        "capital_or_execution_approval_executed": False,
        "requires_separate_capital_or_execution_approval": True,
    }

    if pair in ROUTED_ELSEWHERE:
        return {**base, "status": "routed_to_other_gate", "gate": ROUTED_ELSEWHERE[pair],
                "reason": f"{from_tier} -> {to_tier} is evaluated by the Phase 2 tier_funnel_promotion_gate."}
    if pair != HANDLED_PAIR:
        return {**base, "status": "blocked_unknown_transition",
                "reason": f"{from_tier} -> {to_tier} is not the Tier B -> Tier A transition this gate handles."}

    base["transition_key"] = "b_to_a"
    base["gate_question"] = as_dict(TRANSITIONS.get("b_to_a")).get("question")

    valid_states = STATE_VOCABULARY.get("tier_b") or []
    current_state = candidate.get("current_state")
    if current_state is not None and current_state not in valid_states:
        return {**base, "status": "blocked_invalid_state",
                "reason": f"{current_state} is not a valid Tier B state.", "valid_states": valid_states}
    if current_state in BLOCKING_FROM_STATES:
        return {**base, "status": "blocked_decay_state",
                "reason": f"{current_state} is a stale/challenged/rejected Tier B state; revalidate to B-VALIDATED before nomination."}
    if current_state != REQUIRED_VALIDATED_STATE:
        return {**base, "status": "blocked_not_validated",
                "reason": f"Tier A nomination requires {REQUIRED_VALIDATED_STATE}; current state is {current_state}. Ladder: B-CANDIDATE -> B-VALIDATED -> A-NOMINEE -> A-APPROVED."}

    required = hard_evidence_families()
    present = set(candidate.get("evidence_present") or [])
    missing = [item for item in required if item not in present]
    base["hard_evidence_required_count"] = len(required)
    base["hard_evidence_present_count"] = len([item for item in required if item in present])
    base["missing_evidence"] = missing
    if missing:
        return {**base, "status": "blocked_missing_evidence",
                "reason": f"{len(missing)} of {len(required)} hard-evidence families are not proven present."}

    # Hard evidence complete. Now the scarce-seat competition (capacity family).
    admitted = int(roster_state["tier_a_admitted"])
    cap = int(roster_state["tier_a_cap"])
    reserved = int(roster_state["open_seats_reserved_this_run"])
    projected = admitted + reserved
    base["tier_a_admitted"] = admitted
    base["tier_a_cap"] = cap

    if projected < cap:
        roster_state["open_seats_reserved_this_run"] = reserved + 1
        return {**base, "status": "eligible_for_auto_tier_a_routing", "competition_path": "open_seat",
                "open_seat_index": projected + 1,
                "reason": f"Open Tier A seat available ({projected}/{cap} filled) and hard evidence complete; eligible for automatic non-capital Tier A routing. Capital deployment and execution still require separate exact approval."}

    # Full roster: must defeat the weakest relevant incumbent by >= margin.
    candidate_score = candidate.get("score")
    incumbents = as_list(roster_state.get("incumbents"))
    if candidate_score is None:
        return {**base, "status": "blocked_tier_a_full_needs_score", "competition_path": "full_roster",
                "reason": f"Tier A is full ({admitted}/{cap}); a challenger needs a comparable score to test the +{TIER_A_CHALLENGER_MARGIN_POINTS}-point margin, and none was supplied."}
    weakest = weakest_relevant_incumbent(candidate, [normalize_incumbent(inc) for inc in incumbents])
    if weakest is None:
        return {**base, "status": "blocked_tier_a_full_needs_challenger_comparison", "competition_path": "full_roster",
                "reason": f"Tier A is full ({admitted}/{cap}); no scored incumbents were supplied to run the +{TIER_A_CHALLENGER_MARGIN_POINTS}-point challenge."}
    margin = candidate_score - float(weakest["score"])
    base["weakest_relevant_incumbent"] = weakest
    base["challenger_margin"] = round(margin, 4)
    base["required_margin"] = TIER_A_CHALLENGER_MARGIN_POINTS
    if margin >= TIER_A_CHALLENGER_MARGIN_POINTS:
        return {**base, "status": "eligible_for_auto_tier_a_routing", "competition_path": "full_roster_challenger_win",
                "reason": f"Tier A is full ({admitted}/{cap}) but the challenger beats the weakest relevant incumbent ({weakest.get('ticker')}, score {weakest['score']}) by {round(margin, 2)} >= {TIER_A_CHALLENGER_MARGIN_POINTS}; eligible for automatic non-capital Tier A routing. Capital deployment and execution still require separate exact approval."}
    return {**base, "status": "blocked_tier_a_full_no_challenger_win", "competition_path": "full_roster",
            "reason": f"Tier A is full ({admitted}/{cap}) and the challenger's margin over the weakest relevant incumbent ({weakest.get('ticker')}, score {weakest['score']}) is {round(margin, 2)} < {TIER_A_CHALLENGER_MARGIN_POINTS}; remains Tier B."}


def self_test_fixtures() -> list[dict[str, Any]]:
    hard = hard_evidence_families()
    return [
        {"label": "b_to_a_validated_complete_open_seat_eligible",
         "candidate": {"ticker": "AAA", "current_state": "B-VALIDATED", "evidence_present": hard},
         "roster": {"tier_a_admitted": 10, "incumbents": []}, "expected": "eligible_for_auto_tier_a_routing"},
        {"label": "b_to_a_missing_evidence_blocked",
         "candidate": {"ticker": "BBB", "current_state": "B-VALIDATED", "evidence_present": hard[:-1]},
         "roster": {"tier_a_admitted": 10, "incumbents": []}, "expected": "blocked_missing_evidence"},
        {"label": "b_to_a_not_validated_blocked",
         "candidate": {"ticker": "CCC", "current_state": "B-CANDIDATE", "evidence_present": hard},
         "roster": {"tier_a_admitted": 10, "incumbents": []}, "expected": "blocked_not_validated"},
        {"label": "b_to_a_decay_state_blocked",
         "candidate": {"ticker": "DDD", "current_state": "B-CHALLENGED", "evidence_present": hard},
         "roster": {"tier_a_admitted": 10, "incumbents": []}, "expected": "blocked_decay_state"},
        {"label": "b_to_a_invalid_state_blocked",
         "candidate": {"ticker": "EEE", "current_state": "A-NOMINEE", "evidence_present": hard},
         "roster": {"tier_a_admitted": 10, "incumbents": []}, "expected": "blocked_invalid_state"},
        {"label": "b_to_a_full_roster_challenger_win_eligible",
         "candidate": {"ticker": "FFF", "current_state": "B-VALIDATED", "evidence_present": hard, "score": 90, "sector": "Tech"},
         "roster": {"tier_a_admitted": TIER_A_CAP, "incumbents": [{"ticker": "OLD", "score": 80, "sector": "Tech"}]}, "expected": "eligible_for_auto_tier_a_routing"},
        {"label": "b_to_a_full_roster_margin_too_small_blocked",
         "candidate": {"ticker": "GGG", "current_state": "B-VALIDATED", "evidence_present": hard, "score": 82, "sector": "Tech"},
         "roster": {"tier_a_admitted": TIER_A_CAP, "incumbents": [{"ticker": "OLD", "score": 80, "sector": "Tech"}]}, "expected": "blocked_tier_a_full_no_challenger_win"},
        {"label": "b_to_a_full_roster_no_incumbent_scores_blocked",
         "candidate": {"ticker": "HHH", "current_state": "B-VALIDATED", "evidence_present": hard, "score": 90},
         "roster": {"tier_a_admitted": TIER_A_CAP, "incumbents": []}, "expected": "blocked_tier_a_full_needs_challenger_comparison"},
        {"label": "b_to_a_full_roster_no_candidate_score_blocked",
         "candidate": {"ticker": "III", "current_state": "B-VALIDATED", "evidence_present": hard},
         "roster": {"tier_a_admitted": TIER_A_CAP, "incumbents": [{"ticker": "OLD", "score": 80}]}, "expected": "blocked_tier_a_full_needs_score"},
        {"label": "c_to_b_routed_to_phase2",
         "candidate": {"ticker": "JJJ", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "C-CANDIDATE", "evidence_present": []},
         "roster": {"tier_a_admitted": 0, "incumbents": []}, "expected": "routed_to_other_gate"},
        {"label": "unknown_transition_blocked",
         "candidate": {"ticker": "KKK", "from_tier": "tier_b", "to_tier": "tier_c", "current_state": "B-VALIDATED", "evidence_present": []},
         "roster": {"tier_a_admitted": 0, "incumbents": []}, "expected": "blocked_unknown_transition"},
    ]


def run_self_tests() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture in self_test_fixtures():
        roster = as_dict(fixture.get("roster"))
        roster_state = {
            "tier_a_admitted": int(roster.get("tier_a_admitted") or 0),
            "tier_a_cap": TIER_A_CAP,
            "open_seats_reserved_this_run": 0,
            "incumbents": as_list(roster.get("incumbents")),
        }
        verdict = evaluate_b_to_a(normalize_candidate(fixture["candidate"]), roster_state)
        actual = verdict.get("status")
        results.append({"label": fixture["label"], "expected": fixture["expected"], "actual": actual, "ok": actual == fixture["expected"]})
    return results


def summarize_decisions(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        status = str(decision.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def load_requests(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int | None]:
    payload = load_json_artifact(path)
    if isinstance(payload, list):
        return [normalize_candidate(row) for row in payload if isinstance(row, dict)], [], None
    payload = as_dict(payload)
    candidates = [normalize_candidate(row) for row in as_list(payload.get("requests")) if isinstance(row, dict)]
    incumbents = [normalize_incumbent(row) for row in as_list(payload.get("incumbents")) if isinstance(row, dict)]
    admitted_override = payload.get("tier_a_admitted")
    admitted = int(admitted_override) if isinstance(admitted_override, (int, float)) else None
    return candidates, incumbents, admitted


def build_report(requests_path: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    contract = load_dict(CONTRACT_GATE)
    capacity = load_dict(CAPACITY_POLICY_GATE)
    auto_router = load_dict(AUTO_ROUTER)
    decision_cards = load_dict(DECISION_CARDS)
    capacity_summary = as_dict(capacity.get("summary"))
    tier_a_admitted_live = int(capacity_summary.get("tier_a_admitted_or_deployment_ready_count") or 0)
    live_tier_a_count = len([row for row in as_list(auto_router.get("rows")) if isinstance(row, dict) and row.get("auto_tier") == "Tier A"])

    incumbents: list[dict[str, Any]] = []
    admitted_override: int | None = None
    if requests_path is not None:
        candidates, incumbents, admitted_override = load_requests(requests_path)
        candidate_source = rel(requests_path)
    else:
        candidates = live_b_to_a_candidates(auto_router, decision_cards)
        incumbents = live_tier_a_incumbents(auto_router, decision_cards)
        candidate_source = f"{rel(AUTO_ROUTER)} Tier B rows + {rel(DECISION_CARDS)} WF85 decision cards"

    tier_a_admitted = admitted_override if admitted_override is not None else live_tier_a_count or tier_a_admitted_live
    roster_state = {
        "tier_a_admitted": int(tier_a_admitted),
        "tier_a_cap": TIER_A_CAP,
        "open_seats_reserved_this_run": 0,
        "incumbents": incumbents,
    }
    decisions = [evaluate_b_to_a(candidate, roster_state) for candidate in candidates]
    self_tests = run_self_tests()
    eligible = [d for d in decisions if d.get("status") == "eligible_for_auto_tier_a_routing"]

    add_check(checks, "contract_artifact_present", bool(contract), rel(CONTRACT_GATE))
    add_check(checks, "contract_schema_matches", contract.get("schema") == CONTRACT_SCHEMA, contract.get("schema"))
    add_check(checks, "contract_validation_ok_if_present", (not contract) or as_dict(contract.get("validation")).get("status") == "ok", as_dict(contract.get("validation")).get("status"))
    add_check(checks, "b_to_a_transition_loaded", "b_to_a" in TRANSITIONS, sorted(TRANSITIONS))
    add_check(checks, "tier_a_cap_from_contract_is_25", TIER_A_CAP == 25, TIER_A_CAP)
    add_check(checks, "challenger_margin_from_contract_is_5", TIER_A_CHALLENGER_MARGIN_POINTS == 5, TIER_A_CHALLENGER_MARGIN_POINTS)
    add_check(checks, "hard_evidence_excludes_capacity_and_owner_approval", COMPETITION_FAMILY not in hard_evidence_families() and OWNER_APPROVAL_FAMILY not in hard_evidence_families(), hard_evidence_families())
    add_check(checks, "ten_hard_evidence_families", len(hard_evidence_families()) == 10, len(hard_evidence_families()))

    add_check(checks, "capacity_gate_present", bool(capacity), rel(CAPACITY_POLICY_GATE), "warning")
    add_check(checks, "capacity_gate_validation_ok_if_present", (not capacity) or as_dict(capacity.get("validation")).get("status") == "ok", as_dict(capacity.get("validation")).get("status"), "warning")
    add_check(checks, "auto_router_present", bool(auto_router), rel(AUTO_ROUTER), "warning")
    add_check(checks, "auto_router_validation_ok_if_present", (not auto_router) or as_dict(auto_router.get("validation")).get("status") == "ok", as_dict(auto_router.get("validation")).get("status"), "warning")
    add_check(checks, "decision_cards_present", bool(decision_cards), rel(DECISION_CARDS), "warning")
    add_check(checks, "decision_cards_validation_ok_if_present", (not decision_cards) or as_dict(decision_cards.get("validation")).get("status") == "ok", as_dict(decision_cards.get("validation")).get("status"), "warning")

    for result in self_tests:
        add_check(checks, f"self_test_{result['label']}", result["ok"], {"expected": result["expected"], "actual": result["actual"]})

    # Safety invariants: the gate never admits, approves, or displaces.
    add_check(checks, "every_eligible_has_complete_hard_evidence", all(not d.get("missing_evidence") for d in eligible), [d.get("ticker") for d in eligible if d.get("missing_evidence")])
    add_check(checks, "no_decision_executed_admission", all(d.get("tier_a_admission_executed") is False for d in decisions), True)
    add_check(checks, "no_decision_executed_capital_or_execution_approval", all(d.get("capital_or_execution_approval_executed") is False for d in decisions), True)
    add_check(checks, "open_seat_eligibles_within_capacity", (tier_a_admitted + roster_state["open_seats_reserved_this_run"]) <= TIER_A_CAP, {"admitted": tier_a_admitted, "reserved": roster_state["open_seats_reserved_this_run"], "cap": TIER_A_CAP})

    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    status = "ok" if not errors else "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Tier A Competitive Promotion Gate (Phase 3: Tier B->A)",
        "purpose": "Deterministically evaluate the competitive Tier B->A transition for the scarce 25-seat roster against the Phase 1 contract: B-VALIDATED ladder state, 10 hard-evidence families, and open-seat vs full-roster +5 challenger competition. This emits non-capital routing eligibility only.",
        "contract_ref": {"schema": CONTRACT_SCHEMA, "path": rel(CONTRACT_GATE), "prose_mirror": "06. Playbooks/Coverage Admission and Promotion Protocol.md"},
        "candidate_source": candidate_source,
        "roster_state": {
            "tier_a_admitted": int(tier_a_admitted),
            "tier_a_cap": TIER_A_CAP,
            "tier_a_open_seats": max(0, TIER_A_CAP - int(tier_a_admitted)),
            "open_seats_reserved_this_run": roster_state["open_seats_reserved_this_run"],
            "challenger_margin_points": TIER_A_CHALLENGER_MARGIN_POINTS,
            "incumbent_count": len(incumbents),
            "source": rel(AUTO_ROUTER) if (auto_router and admitted_override is None) else ("requests file" if admitted_override is not None else rel(CAPACITY_POLICY_GATE)),
        },
        "ladder": as_dict(TRANSITIONS.get("b_to_a")).get("ladder"),
        "hard_evidence_families": hard_evidence_families(),
        "terminal_gates": {"capacity": COMPETITION_FAMILY, "capital_or_execution_approval": OWNER_APPROVAL_FAMILY},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "status": status,
            "candidate_count": len(decisions),
            "eligible_for_auto_tier_a_routing_count": len(eligible),
            "eligible_for_owner_approval_count": 0,
            "decision_status_counts": summarize_decisions(decisions),
            "self_tests_total": len(self_tests),
            "self_tests_passed": len([r for r in self_tests if r["ok"]]),
            "checks_total": len(checks),
            "checks_failed_error": len(errors),
            "checks_failed_warning": len(warnings),
            "next_safe_action": "Feed eligible_for_auto_tier_a_routing decisions into the auto-router as non-capital Tier A routing state. Capital deployment and execution remain separately owner-gated.",
        },
        "decisions": decisions,
        "self_tests": self_tests,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": [check["name"] for check in errors],
            "warnings": [check["name"] for check in warnings],
            "checks": checks,
        },
        "stop_lines": STOP_LINES,
    }


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def validate_outputs(report: dict[str, Any], out: Path, write: bool) -> list[str]:
    errors: list[str] = []
    if as_dict(report.get("validation")).get("status") != "ok":
        errors.append("report validation is not ok")
    if write:
        loaded = load_json_artifact(out)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("main JSON missing or schema mismatch")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the WF78 Phase 3 Tier B->A competitive promotion gate.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print stdout JSON")
    parser.add_argument("--requests", type=Path, default=None, help="Optional JSON of explicit Tier B->A nominees (and optional incumbents / tier_a_admitted)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    out = resolve(args.out)
    requests_path = resolve(args.requests) if args.requests is not None else None
    report = build_report(requests_path)
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
    output_errors = validate_outputs(report, out, args.write)
    status = report["status"] if not output_errors else "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "validation_status": as_dict(report.get("validation")).get("status"),
                "output_errors": output_errors,
                "out": rel(out) if args.write else None,
                "summary": report.get("summary"),
            },
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    if args.validate and status != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
