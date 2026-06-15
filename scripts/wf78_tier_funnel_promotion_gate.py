#!/usr/bin/env python3
"""WF78 Phase 2: report-only deterministic Tier D->C and Tier C->B promotion gate.

This gate consumes the Phase 1 funnel contract (`wf78_tier_funnel_contract.py`)
and turns its rules into a deterministic evaluator. For each candidate transition
request it answers one question with one verdict:

  - Tier D -> C (monitorability gate): is this clean enough to monitor cheaply?
  - Tier C -> B (research-worthiness gate): does this deserve scarce research time,
    and is there room under the 15-per-batch nomination limit and the 50-name
    Tier B cap?

It evaluates required-evidence completeness, decay/reject states, the C->B
nomination batch limit, and Tier B cap pressure (read live from the capacity
gate). The live candidate population defaults from the tier-promotion review
gate's Tier C->B research queue; an explicit `--requests <path>` JSON can feed
ad-hoc candidate transition requests instead.

Report-only. It promotes nothing, admits nothing, imports nothing, mutates no
canon/portfolio state, infers no approval, and authorizes no paper/live/account
action. An `eligible_for_admission` verdict means the evidence/competition gate
would pass; an actual admitted tier change still requires the separate apply path
and, for Tier B/A, exact owner approval. Tier B->A is out of scope here and is
routed to the Phase 3 `tier_a_competitive_promotion_gate`.
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
    TIER_B_BATCH_NOMINATION_LIMIT,
    TIER_B_CAP,
    TRANSITIONS,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

CONTRACT_GATE = TMP / "wf78-tier-funnel-contract.json"
CAPACITY_POLICY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"
TIER_PROMOTION_REVIEW_GATE = TMP / "wf78-tier-promotion-review-gate.json"

DEFAULT_OUT = TMP / "wf78-tier-funnel-promotion-gate.json"
SCHEMA = "veritas.wf78_tier_funnel_promotion_gate.v1"

# (from_tier, to_tier) -> contract transition key handled by THIS gate.
HANDLED_TRANSITIONS = {
    ("tier_d", "tier_c"): "d_to_c",
    ("tier_c", "tier_b"): "c_to_b",
}
# Routed elsewhere: Tier B->A belongs to the Phase 3 competitive gate.
ROUTED_ELSEWHERE = {("tier_b", "tier_a"): "tier_a_competitive_promotion_gate"}

# Terminal decay/reject from-states that block a transition outright.
BLOCKING_FROM_STATES = {
    "tier_d": {"D-REJECT"},
    "tier_c": {"C-DECAY"},
}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "evaluation_gate_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "admission_executed": False,
    "promotion_by_score_or_checklist_alone_allowed": False,
    "tier_b_promotion_allowed": False,
    "tier_a_promotion_allowed": False,
    "capital_deployment_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "evaluation_gate_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

STOP_LINES = [
    "This gate evaluates eligibility only; it admits and promotes nothing.",
    "An eligible_for_admission verdict is not an admission and not owner approval.",
    "No promotion from a score, checklist pass, ranking, or generated packet alone.",
    "No import/apply, no production answer-path expansion, no SQL-first promotion.",
    "No capital deployment, paper/live/account action, or money movement.",
    "No canon/portfolio mutation and no owner approval inference.",
    "Tier B->A is out of scope here; route it to the Phase 3 competitive gate.",
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


def required_evidence(transition_key: str) -> list[str]:
    return [str(item) for item in as_list(as_dict(TRANSITIONS.get(transition_key)).get("required_evidence"))]


def is_competitive(transition_key: str) -> bool:
    return bool(as_dict(as_dict(TRANSITIONS.get(transition_key)).get("competition")).get("competitive"))


def normalize_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    evidence = [str(item) for item in as_list(raw.get("evidence_present"))]
    return {
        "ticker": str(raw.get("ticker") or "").upper() or None,
        "name": raw.get("name"),
        "from_tier": str(raw.get("from_tier") or "").strip(),
        "to_tier": str(raw.get("to_tier") or "").strip(),
        "current_state": str(raw.get("current_state") or "").strip() or None,
        "evidence_present": evidence,
        "batch_id": str(raw.get("batch_id") or "unspecified"),
        "evidence_source": raw.get("evidence_source"),
    }


def evaluate_transition(candidate: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Deterministically evaluate one candidate transition against the contract.

    `state` carries the live competitive counters mutated as eligible C->B
    nominations accumulate: nominated_by_batch (dict), tier_b_nominated_this_run
    (int), tier_b_admitted (int), tier_b_cap (int).
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
        "batch_id": candidate.get("batch_id"),
        "evidence_source": candidate.get("evidence_source"),
        "admission_executed": False,
        "requires_separate_apply_path": True,
    }

    if pair in ROUTED_ELSEWHERE:
        return {**base, "status": "routed_to_other_gate", "gate": ROUTED_ELSEWHERE[pair],
                "reason": "Tier B->A is evaluated by the Phase 3 competitive deployment-roster gate."}

    transition_key = HANDLED_TRANSITIONS.get(pair)
    if not transition_key:
        return {**base, "status": "blocked_unknown_transition",
                "reason": f"{from_tier} -> {to_tier} is not a funnel transition this gate handles."}

    base["transition_key"] = transition_key
    base["gate_question"] = as_dict(TRANSITIONS.get(transition_key)).get("question")

    valid_states = STATE_VOCABULARY.get(from_tier) or []
    current_state = candidate.get("current_state")
    if current_state is not None and current_state not in valid_states:
        return {**base, "status": "blocked_invalid_state",
                "reason": f"{current_state} is not a valid {from_tier} state.",
                "valid_states": valid_states}

    if current_state in BLOCKING_FROM_STATES.get(from_tier, set()):
        return {**base, "status": "blocked_decay_state",
                "reason": f"{current_state} is a decay/reject state; repair before re-evaluating."}

    required = required_evidence(transition_key)
    present = set(candidate.get("evidence_present") or [])
    missing = [item for item in required if item not in present]
    base["required_evidence_count"] = len(required)
    base["evidence_present_count"] = len([item for item in required if item in present])
    base["missing_evidence"] = missing
    if missing:
        return {**base, "status": "blocked_missing_evidence",
                "reason": f"{len(missing)} of {len(required)} required evidence families are not proven present."}

    # Evidence complete. Non-competitive (D->C) admission is a clean quality floor.
    if not is_competitive(transition_key):
        return {**base, "status": "eligible_for_admission",
                "reason": "Monitorability evidence complete; eligible for Tier C monitor admission (report-only)."}

    # Competitive (C->B): enforce per-batch nomination limit, then Tier B cap.
    batch_id = candidate.get("batch_id") or "unspecified"
    nominated_in_batch = int(state["nominated_by_batch"].get(batch_id, 0))
    if nominated_in_batch >= TIER_B_BATCH_NOMINATION_LIMIT:
        return {**base, "status": "blocked_batch_nomination_limit",
                "reason": f"Batch {batch_id} already holds {nominated_in_batch} nominations (limit {TIER_B_BATCH_NOMINATION_LIMIT}).",
                "batch_nomination_limit": TIER_B_BATCH_NOMINATION_LIMIT}

    projected_tier_b = int(state["tier_b_admitted"]) + int(state["tier_b_nominated_this_run"])
    if projected_tier_b >= int(state["tier_b_cap"]):
        return {**base, "status": "blocked_tier_b_cap",
                "reason": f"Tier B is full (admitted {state['tier_b_admitted']} + nominated {state['tier_b_nominated_this_run']} >= cap {state['tier_b_cap']}); a new candidate must defeat the weakest Tier B incumbent, which this evidence gate does not decide.",
                "tier_b_cap": int(state["tier_b_cap"])}

    # Eligible nomination: reserve a slot deterministically.
    state["nominated_by_batch"][batch_id] = nominated_in_batch + 1
    state["tier_b_nominated_this_run"] = int(state["tier_b_nominated_this_run"]) + 1
    return {**base, "status": "eligible_for_admission",
            "reason": "Research-worthiness evidence complete and within batch/cap room; eligible for Tier B research-candidate nomination (report-only).",
            "batch_nomination_index": nominated_in_batch + 1}


def default_c_to_b_candidates(review_gate: dict[str, Any]) -> list[dict[str, Any]]:
    """Map the review gate's Tier C->B research queue into candidate requests.

    The review queue marks the full Tier B evidence set as not-yet-built for every
    lead, so each defaulted candidate carries an empty proven-evidence set and is
    correctly evaluated as blocked_missing_evidence. This reflects the live truth
    (tier_b_research_eligible_now_count == 0), not an invented evidence state.
    """
    candidates: list[dict[str, Any]] = []
    for lead in as_list(review_gate.get("tier_c_to_b_research_queue")):
        if not isinstance(lead, dict):
            continue
        ticker = str(lead.get("ticker") or "").upper()
        if not ticker:
            continue
        candidates.append(
            normalize_candidate(
                {
                    "ticker": ticker,
                    "name": lead.get("name"),
                    "from_tier": "tier_c",
                    "to_tier": "tier_b",
                    "current_state": "C-CANDIDATE",
                    "evidence_present": [],
                    "batch_id": "101-200",
                    "evidence_source": "wf78-tier-promotion-review-gate research queue (marks full Tier B evidence set unbuilt)",
                }
            )
        )
    candidates.sort(key=lambda item: str(item.get("ticker")))
    return candidates


def load_requests(path: Path) -> list[dict[str, Any]]:
    payload = load_json_artifact(path)
    rows = payload.get("requests") if isinstance(payload, dict) else payload
    return [normalize_candidate(row) for row in as_list(rows) if isinstance(row, dict)]


def self_test_fixtures() -> list[dict[str, Any]]:
    """Synthetic candidates that exercise every verdict branch deterministically."""
    d_required = required_evidence("d_to_c")
    c_required = required_evidence("c_to_b")
    return [
        {"label": "d_to_c_complete_clean_eligible",
         "candidate": {"ticker": "TST1", "from_tier": "tier_d", "to_tier": "tier_c", "current_state": "D-RAW", "evidence_present": d_required},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "eligible_for_admission"},
        {"label": "d_to_c_missing_evidence_blocked",
         "candidate": {"ticker": "TST2", "from_tier": "tier_d", "to_tier": "tier_c", "current_state": "D-RAW", "evidence_present": d_required[:-1]},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "blocked_missing_evidence"},
        {"label": "d_to_c_reject_state_blocked",
         "candidate": {"ticker": "TST3", "from_tier": "tier_d", "to_tier": "tier_c", "current_state": "D-REJECT", "evidence_present": d_required},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "blocked_decay_state"},
        {"label": "c_to_b_complete_with_room_eligible",
         "candidate": {"ticker": "TST4", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "C-CANDIDATE", "evidence_present": c_required, "batch_id": "selftest"},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "eligible_for_admission"},
        {"label": "c_to_b_missing_evidence_blocked",
         "candidate": {"ticker": "TST5", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "C-CANDIDATE", "evidence_present": c_required[:3], "batch_id": "selftest"},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "blocked_missing_evidence"},
        {"label": "c_to_b_batch_limit_blocked",
         "candidate": {"ticker": "TST6", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "C-CANDIDATE", "evidence_present": c_required, "batch_id": "selftest"},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {"selftest": TIER_B_BATCH_NOMINATION_LIMIT}, "expected": "blocked_batch_nomination_limit"},
        {"label": "c_to_b_cap_pressure_blocked",
         "candidate": {"ticker": "TST7", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "C-CANDIDATE", "evidence_present": c_required, "batch_id": "selftest"},
         "cap_state": {"tier_b_admitted": TIER_B_CAP}, "batch_state": {}, "expected": "blocked_tier_b_cap"},
        {"label": "c_to_b_decay_state_blocked",
         "candidate": {"ticker": "TST8", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "C-DECAY", "evidence_present": c_required, "batch_id": "selftest"},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "blocked_decay_state"},
        {"label": "c_to_b_invalid_state_blocked",
         "candidate": {"ticker": "TST9", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "B-CANDIDATE", "evidence_present": c_required, "batch_id": "selftest"},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "blocked_invalid_state"},
        {"label": "b_to_a_routed_to_phase3",
         "candidate": {"ticker": "TST10", "from_tier": "tier_b", "to_tier": "tier_a", "current_state": "B-VALIDATED", "evidence_present": []},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "routed_to_other_gate"},
        {"label": "unknown_transition_blocked",
         "candidate": {"ticker": "TST11", "from_tier": "tier_d", "to_tier": "tier_b", "current_state": "D-RAW", "evidence_present": []},
         "cap_state": {"tier_b_admitted": 0}, "batch_state": {}, "expected": "blocked_unknown_transition"},
    ]


def run_self_tests() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture in self_test_fixtures():
        state = {
            "nominated_by_batch": dict(fixture.get("batch_state") or {}),
            "tier_b_nominated_this_run": 0,
            "tier_b_admitted": int(as_dict(fixture.get("cap_state")).get("tier_b_admitted") or 0),
            "tier_b_cap": TIER_B_CAP,
        }
        verdict = evaluate_transition(normalize_candidate(fixture["candidate"]), state)
        actual = verdict.get("status")
        results.append(
            {
                "label": fixture["label"],
                "expected": fixture["expected"],
                "actual": actual,
                "ok": actual == fixture["expected"],
            }
        )
    return results


def summarize_decisions(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        status = str(decision.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def build_report(requests_path: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    contract = load_dict(CONTRACT_GATE)
    capacity = load_dict(CAPACITY_POLICY_GATE)
    review_gate = load_dict(TIER_PROMOTION_REVIEW_GATE)

    capacity_summary = as_dict(capacity.get("summary"))
    tier_b_admitted = int(capacity_summary.get("tier_b_admitted_or_research_ready_count") or 0)
    tier_b_remaining = int(capacity_summary.get("tier_b_remaining_capacity") or max(0, TIER_B_CAP - tier_b_admitted))

    if requests_path is not None:
        candidates = load_requests(requests_path)
        candidate_source = rel(requests_path)
    else:
        candidates = default_c_to_b_candidates(review_gate)
        candidate_source = f"{rel(TIER_PROMOTION_REVIEW_GATE)} research queue (D->C population currently empty: no Tier D intake artifact)"

    state = {
        "nominated_by_batch": {},
        "tier_b_nominated_this_run": 0,
        "tier_b_admitted": tier_b_admitted,
        "tier_b_cap": TIER_B_CAP,
    }
    decisions = [evaluate_transition(candidate, state) for candidate in candidates]
    d_to_c_decisions = [d for d in decisions if d.get("from_tier") == "tier_d" and d.get("to_tier") == "tier_c"]
    c_to_b_decisions = [d for d in decisions if d.get("from_tier") == "tier_c" and d.get("to_tier") == "tier_b"]
    other_decisions = [d for d in decisions if d not in d_to_c_decisions and d not in c_to_b_decisions]

    self_tests = run_self_tests()
    eligible = [d for d in decisions if d.get("status") == "eligible_for_admission"]

    # Contract wiring integrity.
    add_check(checks, "contract_artifact_present", bool(contract), rel(CONTRACT_GATE))
    add_check(checks, "contract_schema_matches", contract.get("schema") == CONTRACT_SCHEMA, contract.get("schema"))
    add_check(checks, "contract_validation_ok_if_present", (not contract) or as_dict(contract.get("validation")).get("status") == "ok", as_dict(contract.get("validation")).get("status"))
    add_check(checks, "contract_transitions_loaded", set(HANDLED_TRANSITIONS.values()).issubset(set(TRANSITIONS)), sorted(TRANSITIONS))
    add_check(checks, "tier_b_cap_from_contract_is_50", TIER_B_CAP == 50, TIER_B_CAP)
    add_check(checks, "tier_b_batch_limit_from_contract_is_15", TIER_B_BATCH_NOMINATION_LIMIT == 15, TIER_B_BATCH_NOMINATION_LIMIT)

    # Upstream presence (warnings: the gate still runs and reports honestly).
    add_check(checks, "capacity_gate_present", bool(capacity), rel(CAPACITY_POLICY_GATE), "warning")
    add_check(checks, "capacity_gate_validation_ok_if_present", (not capacity) or as_dict(capacity.get("validation")).get("status") == "ok", as_dict(capacity.get("validation")).get("status"), "warning")
    add_check(checks, "review_gate_present", bool(review_gate) or requests_path is not None, rel(TIER_PROMOTION_REVIEW_GATE), "warning")

    # Every self-test branch must pass (runtime proof of the rule engine).
    for result in self_tests:
        add_check(checks, f"self_test_{result['label']}", result["ok"], {"expected": result["expected"], "actual": result["actual"]})

    # Safety invariants on emitted decisions.
    add_check(checks, "every_eligible_has_complete_evidence", all(not d.get("missing_evidence") for d in eligible), [d.get("ticker") for d in eligible if d.get("missing_evidence")])
    add_check(checks, "no_decision_executed_admission", all(d.get("admission_executed") is False for d in decisions), True)
    add_check(checks, "c_to_b_eligible_within_batch_limit", all(int(d.get("batch_nomination_index") or 0) <= TIER_B_BATCH_NOMINATION_LIMIT for d in c_to_b_decisions if d.get("status") == "eligible_for_admission"), True)
    add_check(checks, "c_to_b_eligible_within_tier_b_cap", (tier_b_admitted + state["tier_b_nominated_this_run"]) <= TIER_B_CAP, {"admitted": tier_b_admitted, "nominated": state["tier_b_nominated_this_run"], "cap": TIER_B_CAP})

    # Authority boundary integrity.
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
        "workflow": "WF78 - Tier Funnel Promotion Gate (Phase 2: Tier D->C and Tier C->B)",
        "purpose": "Deterministically evaluate Tier D->C monitorability and Tier C->B research-worthiness against the Phase 1 contract, enforcing required evidence, decay states, the 15-per-batch nomination limit, and Tier B cap pressure.",
        "contract_ref": {"schema": CONTRACT_SCHEMA, "path": rel(CONTRACT_GATE), "prose_mirror": "06. Playbooks/Coverage Admission and Promotion Protocol.md"},
        "candidate_source": candidate_source,
        "cap_state": {
            "tier_b_admitted_or_research_ready_count": tier_b_admitted,
            "tier_b_cap": TIER_B_CAP,
            "tier_b_remaining_capacity": tier_b_remaining,
            "tier_b_nominated_this_run": state["tier_b_nominated_this_run"],
            "tier_b_batch_nomination_limit": TIER_B_BATCH_NOMINATION_LIMIT,
            "source": rel(CAPACITY_POLICY_GATE) if capacity else "capacity gate not found; assumed 0 admitted",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "status": status,
            "candidate_count": len(decisions),
            "d_to_c_candidate_count": len(d_to_c_decisions),
            "c_to_b_candidate_count": len(c_to_b_decisions),
            "other_candidate_count": len(other_decisions),
            "eligible_for_admission_count": len(eligible),
            "decision_status_counts": summarize_decisions(decisions),
            "self_tests_total": len(self_tests),
            "self_tests_passed": len([r for r in self_tests if r["ok"]]),
            "checks_total": len(checks),
            "checks_failed_error": len(errors),
            "checks_failed_warning": len(warnings),
            "next_safe_action": "Build evidence packets for the highest-priority Tier C->B leads; once a lead's required evidence is proven present, this gate marks it eligible for nomination (still report-only, still owner/apply-gated).",
        },
        "batch_nomination_state": [
            {"batch_id": batch_id, "nominated": count, "limit": TIER_B_BATCH_NOMINATION_LIMIT, "within_limit": count <= TIER_B_BATCH_NOMINATION_LIMIT}
            for batch_id, count in sorted(state["nominated_by_batch"].items())
        ],
        "d_to_c_decisions": d_to_c_decisions,
        "c_to_b_decisions": c_to_b_decisions,
        "other_decisions": other_decisions,
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
    parser = argparse.ArgumentParser(description="Build the WF78 Phase 2 Tier D->C / Tier C->B promotion gate.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print stdout JSON")
    parser.add_argument("--requests", type=Path, default=None, help="Optional JSON of explicit candidate transition requests")
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
