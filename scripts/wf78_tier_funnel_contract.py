#!/usr/bin/env python3
"""WF78 Phase 1: the canonical machine-readable tier-funnel promotion contract.

This is the single source of truth for the WF78 full funnel. It encodes, as data,
the four tiers (D/C/B/A), each transition's gate question and required evidence,
the per-transition competition rules, the state vocabularies, the decay/demotion
triggers, the capacity caps, and the authority boundary. `06. Playbooks/Coverage
Admission and Promotion Protocol.md` is the prose mirror of this contract.

The point of Phase 1 is to remove ambiguity and duplicate encoding: the future
`tier_funnel_promotion_gate` (Tier D->C, Tier C->B) and `tier_a_competitive_promotion_gate`
(Tier B->A) import these constants rather than re-deriving the rules. A separate
internal-consistency validator plus a caps cross-check against
`wf78_tier_capacity_policy_gate.py` prevents the contract from silently diverging
from the live capacity gate.

Report-only. It defines automated non-capital routing, imports nothing, mutates
no canon/portfolio state, infers no capital/execution approval, and authorizes
no paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

CAPACITY_POLICY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"

DEFAULT_OUT = TMP / "wf78-tier-funnel-contract.json"
SCHEMA = "veritas.wf78_tier_funnel_contract.v1"

# --- Capacity caps (the contract owns these; the capacity gate must agree) -----
TIER_A_CAP = 25
TIER_B_CAP = 50
TIER_A_B_COMBINED_CAP = 75
TIER_B_BATCH_NOMINATION_LIMIT = 15
TIER_A_CHALLENGER_MARGIN_POINTS = 5

# --- Tiers ---------------------------------------------------------------------
TIERS: dict[str, dict[str, str]] = {
    "tier_d": {
        "label": "Tier D",
        "role": "Raw intake / repair / watch: weak, incomplete, duplicate, stale, or low-conviction names held until identity and source evidence improve.",
        "authority": "discovery only; never investable, research-worthy, or production answer-path eligible",
    },
    "tier_c": {
        "label": "Tier C",
        "role": "Breadth radar and cheap monitor pool: macro/theme cues, repair state, and a small number of Tier B nominations.",
        "authority": "monitor/route only; not investable and not decision-grade",
    },
    "tier_b": {
        "label": "Tier B",
        "role": "Scarce research bench: full finance picture required (fundamentals, valuation, analyst/revision, technicals, thesis, counter-thesis, risk, source-open, portfolio role).",
        "authority": "serious-monitor research quality; not deployment quality and not capital-ready",
    },
    "tier_a": {
        "label": "Tier A",
        "role": "Scarce 25-seat deployment-review roster: complete, current, portfolio-useful, and better than the current alternative for a limited seat.",
        "authority": "deployment-review only; roster membership never authorizes paper/live/account/portfolio/money action",
    },
}

# --- State vocabularies (mirror of the Coverage Admission and Promotion Protocol) --
STATE_VOCABULARY: dict[str, list[str]] = {
    "tier_d": ["D-RAW", "D-IDENTITY-REPAIR", "D-SOURCE-REPAIR", "D-DUPLICATE-REVIEW", "D-REJECT"],
    "tier_c": ["C-MONITOR", "C-REPAIR", "C-THEME-WATCH", "C-CANDIDATE", "C-DECAY"],
    "tier_b": ["B-CANDIDATE", "B-VALIDATED", "B-STALE", "B-CHALLENGED", "B-REJECT-TO-C"],
    "tier_a": ["A-NOMINEE", "A-WATCH", "A-READY", "A-DEPLOY", "A-HOLD", "A-CHALLENGED", "A-DEMOTE"],
}

# --- Transitions (the gates). Each names its question, required evidence,
#     competition rule, what admission grants, and what it never grants. -------
TRANSITIONS: dict[str, dict[str, Any]] = {
    "d_to_c": {
        "from_tier": "tier_d",
        "to_tier": "tier_c",
        "gate_name": "monitorability gate",
        "question": "Is this clean enough to monitor cheaply?",
        "required_evidence": [
            "clean ticker/company identity",
            "sector and industry classification",
            "basic business model description",
            "source-open identity proof",
            "provider/runtime proof",
            "basic liquidity sanity check",
            "duplicate/conflict check against current universe",
            "explicit reason to monitor",
        ],
        "competition": {
            "competitive": False,
            "rule": "Admission is a quality floor, not a contest: any name that is cleanly monitorable may become Tier C.",
        },
        "grants": "safe enough for cheap monitoring",
        "never_grants": "research-worthy, decision-ready, investable, or production answer-path status",
        "implementation_target": "tier_funnel_promotion_gate",
    },
    "c_to_b": {
        "from_tier": "tier_c",
        "to_tier": "tier_b",
        "gate_name": "research-worthiness gate",
        "question": "Does this deserve scarce research time?",
        "required_evidence": [
            "macro/theme fit",
            "business quality reason",
            "initial fundamentals snapshot available",
            "valuation context available",
            "analyst/revision layer available or explicitly not applicable",
            "initial technical/price-band context",
            "risk reason understood",
            "portfolio role identified",
            "source-open proof usable",
            "evidence repair burden acceptable",
        ],
        "competition": {
            "competitive": True,
            "batch_nomination_limit": TIER_B_BATCH_NOMINATION_LIMIT,
            "batch_size": 100,
            "tier_b_cap": TIER_B_CAP,
            "rule": "Each 100-name batch may nominate no more than 15 Tier B candidates; only top-ranked Tier C names enter the queue; if Tier B is full at 50 a new candidate must beat the weakest Tier B candidate or remain Tier C.",
            "scores_nominate_not_promote": True,
        },
        "grants": "Tier B research-candidate status",
        "never_grants": "Tier A nomination, capital readiness, or auto-promotion from a score",
        "implementation_target": "tier_funnel_promotion_gate",
    },
    "b_to_a": {
        "from_tier": "tier_b",
        "to_tier": "tier_a",
        "gate_name": "competitive deployment-roster gate",
        "question": "Does this deserve one of only 25 Tier A seats more than current alternatives?",
        "ladder": ["B-CANDIDATE", "B-VALIDATED", "A-NOMINEE", "A-APPROVED"],
        "required_evidence": [
            "source-open proof",
            "complete current ticker card",
            "current price, entry band, and stop/invalidation",
            "thesis and counter-thesis",
            "risk register and invalidation event",
            "current fundamentals/earnings context",
            "valuation context",
            "analyst/revision layer",
            "portfolio-fit and concentration check",
            "deployment/readiness state",
            "Tier A capacity check",
            "owner approval",
        ],
        "competition": {
            "competitive": True,
            "tier_a_cap": TIER_A_CAP,
            "challenger_margin_points": TIER_A_CHALLENGER_MARGIN_POINTS,
            "open_seat_rule": "If Tier A holds fewer than 25 admitted names, a nominee may enter only after the full hard-gate evidence passes.",
            "full_roster_rule": "If Tier A holds 25 admitted names, the nominee must defeat the weakest relevant incumbent by at least 5 points.",
            "relevant_incumbents": [
                "weakest Tier A name",
                "most similar Tier A name",
                "same-sector name",
                "same-factor name",
                "same-portfolio-role name",
            ],
            "scores_create_eligibility_not_promotion": True,
        },
        "capital_execution_approval_required": True,
        "grants": "Tier A non-capital routing state (deployment-review only)",
        "never_grants": "paper execution, live execution, account action, portfolio mutation, money movement, or trade approval; A-DEPLOY means an approval-ready packet exists, not trade approval",
        "implementation_target": "tier_a_competitive_promotion_gate",
    },
}

# --- Decay / demotion triggers per tier ----------------------------------------
DECAY_TRIGGERS: dict[str, dict[str, Any]] = {
    "tier_b": {
        "triggers": [
            "stale research",
            "failed thesis",
            "unresolved evidence gaps",
            "broken valuation relevance",
            "a stronger candidate displaces it",
        ],
        "demote_to_states": ["B-STALE", "B-CHALLENGED", "B-REJECT-TO-C"],
        "demote_to_tiers": ["tier_c (repair/monitor)", "tier_d (repair)"],
    },
    "tier_a": {
        "triggers": [
            "stale ticker cards",
            "stale source proof",
            "earnings/thesis drift",
            "broken price structure",
            "excessive concentration",
            "weakening analyst/revision trend",
            "a superior Tier B challenger",
        ],
        "demote_to_states": ["A-CHALLENGED", "A-DEMOTE"],
        "reversible": True,
    },
}

CAPS: dict[str, int] = {
    "tier_a_max": TIER_A_CAP,
    "tier_b_max": TIER_B_CAP,
    "tier_a_b_combined_max": TIER_A_B_COMBINED_CAP,
    "tier_b_batch_nomination_limit": TIER_B_BATCH_NOMINATION_LIMIT,
    "tier_a_challenger_margin_points": TIER_A_CHALLENGER_MARGIN_POINTS,
}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "contract_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_by_score_or_checklist_alone_allowed": False,
    "capital_deployment_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "contract_only", "automated_non_capital_routing_allowed"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

STOP_LINES = [
    "Non-capital tier/routing movement may be automated only through validated workflow artifacts.",
    "No promotion from a score, checklist pass, ranking, or generated packet alone.",
    "No import/apply, no production answer-path expansion, no SQL-first promotion.",
    "No capital deployment, paper/live/account action, or money movement.",
    "No canon/portfolio mutation and no capital/execution owner approval inference.",
    "Any capital deployment or execution still requires exact owner approval.",
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


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def run_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    # Tier + state vocabulary integrity.
    add_check(checks, "four_tiers_present", set(TIERS) == {"tier_d", "tier_c", "tier_b", "tier_a"}, sorted(TIERS))
    for tier in ("tier_d", "tier_c", "tier_b", "tier_a"):
        states = STATE_VOCABULARY.get(tier) or []
        add_check(checks, f"{tier}_states_present", len(states) > 0 and all(isinstance(state, str) and state for state in states), states)
        add_check(checks, f"{tier}_states_prefixed", all(state.startswith(tier.split("_")[1].upper() + "-") for state in states), states)

    # Transition integrity: question, evidence, grants, and a named implementation target.
    for key in ("d_to_c", "c_to_b", "b_to_a"):
        transition = as_dict(TRANSITIONS.get(key))
        add_check(checks, f"{key}_has_question", bool(transition.get("question")), transition.get("question"))
        add_check(checks, f"{key}_has_required_evidence", bool(transition.get("required_evidence")), len(transition.get("required_evidence") or []))
        add_check(checks, f"{key}_has_grants", bool(transition.get("grants")), transition.get("grants"))
        add_check(checks, f"{key}_has_never_grants", bool(transition.get("never_grants")), transition.get("never_grants"))
        add_check(checks, f"{key}_has_implementation_target", bool(transition.get("implementation_target")), transition.get("implementation_target"))
        add_check(checks, f"{key}_from_to_known_tiers", transition.get("from_tier") in TIERS and transition.get("to_tier") in TIERS, {"from": transition.get("from_tier"), "to": transition.get("to_tier")})

    # Competition rules: C->B batch limit and B->A challenger margin / owner gate.
    c_to_b_comp = as_dict(as_dict(TRANSITIONS.get("c_to_b")).get("competition"))
    add_check(checks, "c_to_b_batch_limit_is_15", c_to_b_comp.get("batch_nomination_limit") == TIER_B_BATCH_NOMINATION_LIMIT, c_to_b_comp.get("batch_nomination_limit"))
    add_check(checks, "c_to_b_scores_do_not_auto_promote", c_to_b_comp.get("scores_nominate_not_promote") is True, c_to_b_comp)

    b_to_a = as_dict(TRANSITIONS.get("b_to_a"))
    b_to_a_comp = as_dict(b_to_a.get("competition"))
    add_check(checks, "b_to_a_challenger_margin_is_5", b_to_a_comp.get("challenger_margin_points") == TIER_A_CHALLENGER_MARGIN_POINTS, b_to_a_comp.get("challenger_margin_points"))
    add_check(checks, "b_to_a_capital_execution_approval_required", b_to_a.get("capital_execution_approval_required") is True, b_to_a.get("capital_execution_approval_required"))
    add_check(checks, "b_to_a_scores_do_not_auto_promote", b_to_a_comp.get("scores_create_eligibility_not_promotion") is True, b_to_a_comp)
    add_check(checks, "b_to_a_ladder_complete", b_to_a.get("ladder") == ["B-CANDIDATE", "B-VALIDATED", "A-NOMINEE", "A-APPROVED"], b_to_a.get("ladder"))

    # Caps cross-check against the live capacity gate (the contract owns the caps).
    capacity = as_dict(load_json_artifact(CAPACITY_POLICY_GATE))
    if capacity:
        policy = as_dict(capacity.get("policy"))
        add_check(checks, "caps_match_capacity_gate_tier_a", int(policy.get("tier_a_max") or -1) == TIER_A_CAP, {"contract": TIER_A_CAP, "capacity_gate": policy.get("tier_a_max")})
        add_check(checks, "caps_match_capacity_gate_tier_b", int(policy.get("tier_b_max") or -1) == TIER_B_CAP, {"contract": TIER_B_CAP, "capacity_gate": policy.get("tier_b_max")})
        add_check(checks, "caps_match_capacity_gate_combined", int(policy.get("tier_a_b_combined_max") or -1) == TIER_A_B_COMBINED_CAP, {"contract": TIER_A_B_COMBINED_CAP, "capacity_gate": policy.get("tier_a_b_combined_max")})
        add_check(checks, "caps_match_capacity_gate_batch_limit", int(policy.get("tier_b_batch_nomination_limit") or -1) == TIER_B_BATCH_NOMINATION_LIMIT, {"contract": TIER_B_BATCH_NOMINATION_LIMIT, "capacity_gate": policy.get("tier_b_batch_nomination_limit")})
    else:
        add_check(checks, "capacity_gate_present_for_caps_crosscheck", False, f"{rel(CAPACITY_POLICY_GATE)} not found; run wf78_tier_capacity_policy_gate.py --write to enable caps cross-check", "warning")

    # Authority boundary integrity.
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    # No transition may grant an execution/deployment/mutation verb.
    forbidden_grant_terms = ("execut", "deploy capital", "trade approval", "mutate", "money")
    for key in ("d_to_c", "c_to_b", "b_to_a"):
        grants = str(as_dict(TRANSITIONS.get(key)).get("grants") or "").lower()
        add_check(checks, f"{key}_grants_no_execution_authority", not any(term in grants for term in forbidden_grant_terms), grants)

    return checks


def build_contract() -> dict[str, Any]:
    checks = run_checks()
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    status = "ok" if not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Tier Funnel Promotion Contract (Phase 1)",
        "purpose": "Single machine-readable source for the WF78 D/C/B/A funnel: gate questions, required evidence, competition rules, state vocabularies, decay triggers, caps, and authority boundary.",
        "prose_mirror": "06. Playbooks/Coverage Admission and Promotion Protocol.md",
        "consumers": [
            "tier_funnel_promotion_gate (Phase 2): Tier D->C and Tier C->B",
            "tier_a_competitive_promotion_gate (Phase 3): Tier B->A",
            "wf78_auto_tier_router.py: derived non-capital routing state",
            "wf78_tier_capacity_policy_gate.py (caps must match this contract)",
        ],
        "tiers": TIERS,
        "state_vocabulary": STATE_VOCABULARY,
        "transitions": TRANSITIONS,
        "decay_triggers": DECAY_TRIGGERS,
        "caps": CAPS,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "status": status,
            "tier_count": len(TIERS),
            "transition_count": len(TRANSITIONS),
            "state_count": sum(len(states) for states in STATE_VOCABULARY.values()),
            "checks_total": len(checks),
            "checks_failed_error": len(errors),
            "checks_failed_warning": len(warnings),
            "caps_crosschecked_against_capacity_gate": CAPACITY_POLICY_GATE.exists(),
            "next_safe_action": "Build Phase 2 tier_funnel_promotion_gate (Tier D->C monitorability, Tier C->B research-worthiness) consuming this contract; it stays report-only.",
        },
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


def validate_outputs(contract: dict[str, Any], out: Path, write: bool) -> list[str]:
    errors: list[str] = []
    if as_dict(contract.get("validation")).get("status") != "ok":
        errors.append("contract validation is not ok")
    if write:
        loaded = load_json_artifact(out)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("main JSON missing or schema mismatch")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the WF78 Phase 1 tier-funnel promotion contract.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print stdout JSON")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    out = resolve(args.out)
    contract = build_contract()
    if args.write:
        atomic_write_json(out, contract, ensure_ascii=False)
    output_errors = validate_outputs(contract, out, args.write)
    status = contract["status"] if not output_errors else "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "validation_status": as_dict(contract.get("validation")).get("status"),
                "output_errors": output_errors,
                "out": rel(out) if args.write else None,
                "summary": contract.get("summary"),
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
