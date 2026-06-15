#!/usr/bin/env python3
"""WF78 Phase 4: report-only owner decision packet generator for the tier funnel.

This script reads the Phase 2 and Phase 3 promotion-gate outputs and turns each
gate verdict into a precise, owner-readable decision packet. It is the output
layer of the promotion machinery: the gates decide *eligibility*; this layer
states exactly what owner action (if any) each verdict implies, what evidence is
missing, and what authority boundary still applies.

Inputs (read-only):
  - tmp/wf78-tier-funnel-promotion-gate.json   (Phase 2: Tier D->C, Tier C->B)
  - tmp/wf78-tier-a-competitive-promotion-gate.json (Phase 3: Tier B->A)

For every decision it emits one packet with: ticker, current tier/state,
requested tier/state, gate verdict, evidence present vs required, missing
evidence, the owner-action category, the precise owner action, and whether a
separate apply/approval path is still required.

Trust rule: a packet is only marked actionable when its source gate is present,
its status is `ok`, and its validation is `ok`. An untrusted/missing source gate
downgrades every derived packet to `no_action` rather than presenting a stale
"ready" decision.

Report-only. It admits nothing, promotes nothing, mutates no canon/portfolio
state, infers no owner approval, and authorizes no paper/live/account action.
An `actionable_now` packet is a *prepared* owner decision, not an approval.
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

PHASE2_GATE = TMP / "wf78-tier-funnel-promotion-gate.json"
PHASE3_GATE = TMP / "wf78-tier-a-competitive-promotion-gate.json"
PHASE2_SCHEMA = "veritas.wf78_tier_funnel_promotion_gate.v1"
PHASE3_SCHEMA = "veritas.wf78_tier_a_competitive_promotion_gate.v1"

DEFAULT_OUT = TMP / "wf78-funnel-owner-decision-packet.json"
SCHEMA = "veritas.wf78_funnel_owner_decision_packet.v1"

TIER_LABELS = {"tier_d": "Tier D", "tier_c": "Tier C", "tier_b": "Tier B", "tier_a": "Tier A"}
# The target state each handled transition nominates a name into.
REQUESTED_STATE = {"d_to_c": "C-MONITOR", "c_to_b": "B-CANDIDATE", "b_to_a": "A-NOMINEE"}
PACKET_TYPE = {"d_to_c": "monitor_admission", "c_to_b": "research_candidate", "b_to_a": "tier_a_nominee"}

ACTIONABLE = "actionable_now"
NEEDS_EVIDENCE = "needs_evidence"
NEEDS_VALIDATION = "needs_validation"
STATE_REPAIR = "state_repair_needed"
CAPACITY_BLOCKED = "capacity_or_competition_blocked"
ROUTED = "routed_elsewhere"
NO_ACTION = "no_action"

OWNER_ACTION_CATEGORIES = [
    ACTIONABLE, NEEDS_EVIDENCE, NEEDS_VALIDATION, STATE_REPAIR, CAPACITY_BLOCKED, ROUTED, NO_ACTION,
]

# Verdicts that, when their source gate is trusted, represent a prepared owner decision.
ACTIONABLE_VERDICTS = {"eligible_for_admission", "eligible_for_owner_approval"}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "decision_packet_only": True,
    "read_existing_artifacts_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "tier_admission_executed": False,
    "tier_a_admission_executed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "decision_packet_only", "read_existing_artifacts_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

STOP_LINES = [
    "This is a decision-packet layer; it admits, promotes, and approves nothing.",
    "An actionable_now packet is a prepared owner decision, not an owner approval.",
    "Tier admission (any tier) and Tier A roster admission require Randall's exact owner approval.",
    "A-DEPLOY still requires a separate exact order approval before any paper/live/account action.",
    "Packets are only actionable when the source gate is present and validated; stale gates downgrade to no_action.",
    "No import/apply, no capital deployment, no canon/portfolio mutation, no money movement, no approval inference.",
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


def gate_trusted(gate: dict[str, Any], expected_schema: str) -> bool:
    return bool(gate) and gate.get("schema") == expected_schema and gate.get("status") == "ok" \
        and as_dict(gate.get("validation")).get("status") == "ok"


def tier_label(tier: Any) -> str:
    return TIER_LABELS.get(str(tier), str(tier))


def normalize_decision(decision: dict[str, Any], transition_key: str) -> dict[str, Any]:
    """Flatten a Phase 2 or Phase 3 gate decision into a common packet shape.

    Phase 2 uses required_evidence_count/evidence_present_count; Phase 3 uses
    hard_evidence_required_count/hard_evidence_present_count. Both expose
    missing_evidence, status, reason, current_state, from_tier, to_tier.
    """
    required = decision.get("required_evidence_count")
    if required is None:
        required = decision.get("hard_evidence_required_count")
    present = decision.get("evidence_present_count")
    if present is None:
        present = decision.get("hard_evidence_present_count")
    missing = [str(m) for m in as_list(decision.get("missing_evidence"))]
    # Safety: capture any execution flags the source gate carried so we can assert they are False.
    admission_executed = bool(
        decision.get("admission_executed")
        or decision.get("tier_a_admission_executed")
        or decision.get("owner_approval_executed")
    )
    return {
        "ticker": decision.get("ticker"),
        "name": decision.get("name"),
        "from_tier": decision.get("from_tier"),
        "to_tier": decision.get("to_tier"),
        "current_state": decision.get("current_state"),
        "transition_key": transition_key,
        "gate_verdict": decision.get("status"),
        "gate_reason": decision.get("reason"),
        "required_evidence_count": required,
        "evidence_present_count": present,
        "missing_evidence": missing,
        "requires_separate_apply_path": bool(decision.get("requires_separate_apply_path", True)),
        "_source_admission_executed": admission_executed,
    }


def owner_action_for(verdict: str, rec: dict[str, Any]) -> tuple[str, str]:
    """Map a gate verdict + normalized record to (owner_action_category, owner_action_text)."""
    ticker = rec.get("ticker") or "candidate"
    to_label = tier_label(rec.get("to_tier"))
    requested_state = REQUESTED_STATE.get(rec.get("transition_key"), "")
    missing = rec.get("missing_evidence") or []
    n_missing = len(missing)
    current_state = rec.get("current_state")

    if verdict == "eligible_for_admission":
        return ACTIONABLE, (
            f"Owner may admit {ticker} to {to_label} as {requested_state}; all required evidence is present. "
            f"This is a tier-admission approval only — not capital deployment, a production answer-path change, or a trade."
        )
    if verdict == "eligible_for_owner_approval":
        return ACTIONABLE, (
            f"Owner may approve {ticker} for {to_label} roster admission (A-NOMINEE -> A-APPROVED). "
            f"A separate exact order approval is still required before any A-DEPLOY/paper/live action."
        )
    if verdict == "blocked_missing_evidence":
        shown = ", ".join(missing[:6]) + (" ..." if n_missing > 6 else "")
        return NEEDS_EVIDENCE, (
            f"Not decision-ready: build the {n_missing} missing evidence family(ies) [{shown}] for {ticker}, "
            f"then re-run the gate before owner review."
        )
    if verdict == "blocked_not_validated":
        return NEEDS_VALIDATION, (
            f"Advance {ticker} to B-VALIDATED (full research packet) before any Tier A nomination; "
            f"current state is {current_state}."
        )
    if verdict == "blocked_decay_state":
        return STATE_REPAIR, (
            f"Resolve decay/challenged state {current_state} for {ticker} (refresh/repair and revalidate) before nomination."
        )
    if verdict == "blocked_invalid_state":
        return STATE_REPAIR, (
            f"State {current_state} is not valid for this transition; correct {ticker}'s state before any decision."
        )
    if verdict == "blocked_batch_nomination_limit":
        return CAPACITY_BLOCKED, (
            f"Batch nomination limit reached; defer {ticker} to a later batch. No owner action available now."
        )
    if verdict == "blocked_tier_b_cap":
        return CAPACITY_BLOCKED, (
            f"Tier B is at cap; a Tier B seat must open (a demotion/decay) before {ticker} can be admitted."
        )
    if verdict in {
        "blocked_tier_a_full_needs_score",
        "blocked_tier_a_full_needs_challenger_comparison",
        "blocked_tier_a_full_no_challenger_win",
    }:
        return CAPACITY_BLOCKED, (
            f"Tier A is full; {ticker} has not won the +5 challenger test ({verdict}). "
            f"No owner action available until a seat opens or a winning comparison exists."
        )
    if verdict == "routed_to_other_gate":
        return ROUTED, f"{ticker}'s transition is evaluated by another gate; no packet decision here."
    return NO_ACTION, f"No owner action mapped for verdict {verdict}."


def build_packet(decision: dict[str, Any], transition_key: str, source_gate: str, trusted: bool) -> dict[str, Any]:
    rec = normalize_decision(decision, transition_key)
    verdict = str(rec.get("gate_verdict"))
    category, action = owner_action_for(verdict, rec)
    downgraded = False
    if not trusted and category == ACTIONABLE:
        category = NO_ACTION
        action = (
            f"Source gate {source_gate} is missing or not validated; refresh it before treating "
            f"{rec.get('ticker') or 'this candidate'} as an actionable owner decision."
        )
        downgraded = True
    return {
        "ticker": rec["ticker"],
        "name": rec["name"],
        "packet_type": PACKET_TYPE.get(transition_key, transition_key),
        "transition_key": transition_key,
        "from_tier": rec["from_tier"],
        "from_tier_label": tier_label(rec["from_tier"]),
        "to_tier": rec["to_tier"],
        "to_tier_label": tier_label(rec["to_tier"]),
        "current_state": rec["current_state"],
        "requested_state": REQUESTED_STATE.get(transition_key, ""),
        "gate_verdict": verdict,
        "gate_reason": rec["gate_reason"],
        "required_evidence_count": rec["required_evidence_count"],
        "evidence_present_count": rec["evidence_present_count"],
        "missing_evidence": rec["missing_evidence"],
        "owner_action_category": category,
        "owner_action": action,
        "requires_separate_apply_path": rec["requires_separate_apply_path"],
        "owner_approval_required": True,
        "owner_approval_inferred": False,
        "source_gate": source_gate,
        "source_gate_trusted": trusted,
        "actionable_downgraded_by_untrusted_gate": downgraded,
        "_source_admission_executed": rec["_source_admission_executed"],
    }


def collect_phase2_packets(gate: dict[str, Any], trusted: bool, source_label: str) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for decision in as_list(gate.get("d_to_c_decisions")):
        if isinstance(decision, dict):
            packets.append(build_packet(decision, "d_to_c", source_label, trusted))
    for decision in as_list(gate.get("c_to_b_decisions")):
        if isinstance(decision, dict):
            packets.append(build_packet(decision, "c_to_b", source_label, trusted))
    return packets


def collect_phase3_packets(gate: dict[str, Any], trusted: bool, source_label: str) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for decision in as_list(gate.get("decisions")):
        if isinstance(decision, dict):
            packets.append(build_packet(decision, "b_to_a", source_label, trusted))
    return packets


def count_by(packets: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for packet in packets:
        value = str(packet.get(key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def self_test_fixtures() -> list[dict[str, Any]]:
    return [
        {"label": "d_to_c_eligible_actionable", "transition": "d_to_c",
         "decision": {"ticker": "AAA", "status": "eligible_for_admission", "from_tier": "tier_d", "to_tier": "tier_c", "missing_evidence": []},
         "trusted": True, "expected": ACTIONABLE},
        {"label": "c_to_b_eligible_actionable", "transition": "c_to_b",
         "decision": {"ticker": "BBB", "status": "eligible_for_admission", "from_tier": "tier_c", "to_tier": "tier_b", "missing_evidence": []},
         "trusted": True, "expected": ACTIONABLE},
        {"label": "b_to_a_eligible_actionable", "transition": "b_to_a",
         "decision": {"ticker": "CCC", "status": "eligible_for_owner_approval", "from_tier": "tier_b", "to_tier": "tier_a", "missing_evidence": []},
         "trusted": True, "expected": ACTIONABLE},
        {"label": "eligible_downgraded_when_gate_untrusted", "transition": "c_to_b",
         "decision": {"ticker": "DDD", "status": "eligible_for_admission", "from_tier": "tier_c", "to_tier": "tier_b", "missing_evidence": []},
         "trusted": False, "expected": NO_ACTION},
        {"label": "missing_evidence_needs_evidence", "transition": "c_to_b",
         "decision": {"ticker": "EEE", "status": "blocked_missing_evidence", "from_tier": "tier_c", "to_tier": "tier_b", "missing_evidence": ["valuation", "risk reason"]},
         "trusted": True, "expected": NEEDS_EVIDENCE},
        {"label": "not_validated_needs_validation", "transition": "b_to_a",
         "decision": {"ticker": "FFF", "status": "blocked_not_validated", "from_tier": "tier_b", "to_tier": "tier_a", "current_state": "B-CANDIDATE", "missing_evidence": []},
         "trusted": True, "expected": NEEDS_VALIDATION},
        {"label": "decay_state_repair", "transition": "b_to_a",
         "decision": {"ticker": "GGG", "status": "blocked_decay_state", "from_tier": "tier_b", "to_tier": "tier_a", "current_state": "B-STALE", "missing_evidence": []},
         "trusted": True, "expected": STATE_REPAIR},
        {"label": "invalid_state_repair", "transition": "c_to_b",
         "decision": {"ticker": "HHH", "status": "blocked_invalid_state", "from_tier": "tier_c", "to_tier": "tier_b", "current_state": "BOGUS", "missing_evidence": []},
         "trusted": True, "expected": STATE_REPAIR},
        {"label": "batch_limit_capacity_blocked", "transition": "c_to_b",
         "decision": {"ticker": "III", "status": "blocked_batch_nomination_limit", "from_tier": "tier_c", "to_tier": "tier_b", "missing_evidence": []},
         "trusted": True, "expected": CAPACITY_BLOCKED},
        {"label": "tier_b_cap_capacity_blocked", "transition": "c_to_b",
         "decision": {"ticker": "JJJ", "status": "blocked_tier_b_cap", "from_tier": "tier_c", "to_tier": "tier_b", "missing_evidence": []},
         "trusted": True, "expected": CAPACITY_BLOCKED},
        {"label": "tier_a_full_no_win_capacity_blocked", "transition": "b_to_a",
         "decision": {"ticker": "KKK", "status": "blocked_tier_a_full_no_challenger_win", "from_tier": "tier_b", "to_tier": "tier_a", "missing_evidence": []},
         "trusted": True, "expected": CAPACITY_BLOCKED},
        {"label": "routed_elsewhere", "transition": "b_to_a",
         "decision": {"ticker": "LLL", "status": "routed_to_other_gate", "from_tier": "tier_c", "to_tier": "tier_b", "missing_evidence": []},
         "trusted": True, "expected": ROUTED},
    ]


def run_self_tests() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture in self_test_fixtures():
        packet = build_packet(fixture["decision"], fixture["transition"], "self-test", fixture["trusted"])
        actual = packet["owner_action_category"]
        executed_clean = packet["_source_admission_executed"] is False and packet["owner_approval_inferred"] is False
        results.append({
            "label": fixture["label"],
            "expected": fixture["expected"],
            "actual": actual,
            "ok": actual == fixture["expected"] and executed_clean,
        })
    return results


def build_report(phase2_path: Path = PHASE2_GATE, phase3_path: Path = PHASE3_GATE) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    phase2 = load_dict(phase2_path)
    phase3 = load_dict(phase3_path)
    phase2_trusted = gate_trusted(phase2, PHASE2_SCHEMA)
    phase3_trusted = gate_trusted(phase3, PHASE3_SCHEMA)

    packets = collect_phase2_packets(phase2, phase2_trusted, rel(phase2_path)) \
        + collect_phase3_packets(phase3, phase3_trusted, rel(phase3_path))
    self_tests = run_self_tests()

    actionable = [p for p in packets if p["owner_action_category"] == ACTIONABLE]

    add_check(checks, "phase2_gate_present", bool(phase2), rel(PHASE2_GATE), "warning")
    add_check(checks, "phase3_gate_present", bool(phase3), rel(PHASE3_GATE), "warning")
    add_check(checks, "phase2_gate_trusted_if_present", (not phase2) or phase2_trusted, {"status": phase2.get("status"), "validation": as_dict(phase2.get("validation")).get("status")}, "warning")
    add_check(checks, "phase3_gate_trusted_if_present", (not phase3) or phase3_trusted, {"status": phase3.get("status"), "validation": as_dict(phase3.get("validation")).get("status")}, "warning")

    for result in self_tests:
        add_check(checks, f"self_test_{result['label']}", result["ok"], {"expected": result["expected"], "actual": result["actual"]})

    # Safety invariants.
    add_check(checks, "no_packet_carries_executed_admission", all(p["_source_admission_executed"] is False for p in packets), [p.get("ticker") for p in packets if p["_source_admission_executed"]])
    add_check(checks, "no_packet_infers_owner_approval", all(p["owner_approval_inferred"] is False for p in packets), True)
    add_check(checks, "every_actionable_from_trusted_gate", all(p["source_gate_trusted"] for p in actionable), [p.get("ticker") for p in actionable if not p["source_gate_trusted"]])
    add_check(checks, "every_actionable_requires_owner_approval", all(p["owner_approval_required"] for p in actionable), True)
    add_check(checks, "all_categories_known", all(p["owner_action_category"] in OWNER_ACTION_CATEGORIES for p in packets), True)

    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [c for c in checks if c["severity"] == "critical" and not c["ok"]]
    warnings = [c for c in checks if c["severity"] == "warning" and not c["ok"]]
    status = "ok" if not errors else "blocked"

    # Strip internal-only keys from the published packets.
    published = []
    for packet in packets:
        clean = {k: v for k, v in packet.items() if not k.startswith("_")}
        published.append(clean)
    actionable_published = [p for p in published if p["owner_action_category"] == ACTIONABLE]

    if actionable_published:
        next_action = f"{len(actionable_published)} prepared owner decision(s) are ready for review; present them for exact owner approval (still not capital deployment)."
    elif not (phase2 or phase3):
        next_action = "No source gate found; run the Phase 2 and Phase 3 promotion gates first, then regenerate this packet."
    else:
        next_action = "No prepared owner decisions: every live candidate is blocked on evidence/validation/state/capacity. Build per-lead Tier B research evidence so the Phase 2 gate can rate a lead eligible."

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Funnel Owner Decision Packets (Phase 4)",
        "purpose": "Turn Phase 2 (D->C, C->B) and Phase 3 (B->A) gate verdicts into precise, report-only owner decision packets: requested tier/state, evidence gap, owner-action category, and the exact owner action, without inferring or executing any approval.",
        "source_gates": {
            "phase2": {"path": rel(phase2_path), "present": bool(phase2), "trusted": phase2_trusted, "generated_at_utc": phase2.get("generated_at_utc"), "status": phase2.get("status")},
            "phase3": {"path": rel(phase3_path), "present": bool(phase3), "trusted": phase3_trusted, "generated_at_utc": phase3.get("generated_at_utc"), "status": phase3.get("status")},
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "requires_owner_decision": bool(actionable_published),
        "summary": {
            "status": status,
            "packet_count": len(published),
            "actionable_now_count": len(actionable_published),
            "by_owner_action_category": count_by(published, "owner_action_category"),
            "by_packet_type": count_by(published, "packet_type"),
            "by_gate_verdict": count_by(published, "gate_verdict"),
            "self_tests_total": len(self_tests),
            "self_tests_passed": len([r for r in self_tests if r["ok"]]),
            "checks_total": len(checks),
            "checks_failed_error": len(errors),
            "checks_failed_warning": len(warnings),
            "next_safe_action": next_action,
        },
        "actionable_packets": actionable_published,
        "packets": published,
        "self_tests": self_tests,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": [c["name"] for c in errors],
            "warnings": [c["name"] for c in warnings],
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
    parser = argparse.ArgumentParser(description="Build the WF78 Phase 4 funnel owner decision packets.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print stdout JSON")
    parser.add_argument("--phase2", type=Path, default=PHASE2_GATE, help="Override the Phase 2 gate JSON path (testing/snapshot)")
    parser.add_argument("--phase3", type=Path, default=PHASE3_GATE, help="Override the Phase 3 gate JSON path (testing/snapshot)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    out = resolve(args.out)
    report = build_report(resolve(args.phase2), resolve(args.phase3))
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
