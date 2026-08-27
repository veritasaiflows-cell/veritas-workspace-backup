#!/usr/bin/env python3
"""Explain WF87 runtime blockers as gate-by-gate follow-up actions.

The WF87 readiness rollup intentionally fails closed, but its top-level
blockers are compact machine strings. This packet expands every blocker into a
plain-English reason, source artifact, owner lane, next action, and validator.
It is review-only and does not clear gates or grant execution authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_ROLLUP = TMP / "wf87-v2-readiness-rollup.json"
DEFAULT_OUT = TMP / "wf87-runtime-gate-explanation.json"
DEFAULT_MD = TMP / "wf87-runtime-gate-explanation.md"

SCHEMA = "veritas.wf87_runtime_gate_explanation.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "explanation_only": True,
    "proposal_generation_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "autonomous_paper_cancel_allowed": False,
    "autonomous_paper_sell_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cron_direct_execution_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "autonomous_paper_submit_allowed",
    "autonomous_paper_cancel_allowed",
    "autonomous_paper_sell_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_or_live_execution_allowed_now",
    "autonomous_execution_allowed_now",
    "live_execution_allowed_now",
    "live_endpoint_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "cron_direct_execution_allowed",
    "owner_approval_inferred",
}

GATE_DEFS: dict[str, dict[str, Any]] = {
    "approval_freshness_ttl": {
        "title": "Approval and freshness TTL",
        "owner": "WF87 TTL proof lane",
        "validator": "python scripts\\wf87_approval_freshness_ttl.py --write --validate",
        "followup_type": "proof_refresh",
        "default_class": "fail_closed_at_rest",
        "reason": "Short-lived approval, quote, band/stop, guard, kill-switch, or reconciliation proof is expired or missing.",
        "owner_action": "Refresh the short-lived proof set only when a real assisted-paper review window exists; do not infer approval.",
    },
    "intraday_monitor": {
        "title": "Intraday monitor",
        "owner": "WF87 intraday monitor lane",
        "validator": "python scripts\\wf87_intraday_monitor.py --write --validate",
        "followup_type": "proof_refresh",
        "default_class": "fail_closed_at_rest",
        "reason": "The monitor is recommending a main-session review or is outside its clean monitoring state.",
        "owner_action": "Inspect wake reasons, refresh same-session stop/reconciliation proof if needed, and keep monitor action review-only.",
    },
    "paper_reconciliation_freshness": {
        "title": "Paper reconciliation freshness",
        "owner": "WF67/WF87 reconciliation lane",
        "validator": "python scripts\\alpaca_paper_order_history_classifier.py --write --validate",
        "followup_type": "proof_refresh",
        "default_class": "fail_closed_at_rest",
        "reason": "Paper order/position reconciliation is missing, stale, blocked, or not yet mature enough for autonomy.",
        "owner_action": "Refresh order history and reconciliation proof; maturity requires clean classifier evidence, not a parent-rollup patch.",
    },
    "position_sizing_runtime": {
        "title": "Position sizing runtime check",
        "owner": "WF87 runtime sizing lane",
        "validator": "python scripts\\wf87_position_sizing_runtime_check.py --write --validate",
        "followup_type": "implementation_repair",
        "default_class": "runtime_blocker",
        "reason": "Runtime sizing inputs are stale, missing, or blocked, so a candidate cannot be sized safely.",
        "owner_action": "Repair or refresh policy, guard, and candidate inputs until the sizing validator is clean.",
    },
    "portfolio_circuit_breakers": {
        "title": "Portfolio circuit breakers",
        "owner": "WF87 circuit-breaker lane",
        "validator": "python scripts\\wf87_portfolio_circuit_breakers.py --write --validate",
        "followup_type": "proof_refresh",
        "default_class": "fail_closed_at_rest",
        "reason": "Circuit-breaker inputs are stale, missing, or blocked, including policy, guard, paper positions, or anomaly halt proof.",
        "owner_action": "Refresh paper positions, policy, guard, order history, and anomaly halt proof; do not execute from this packet.",
    },
    "shadow_threshold": {
        "title": "Shadow proof threshold",
        "owner": "WF87 maturity lane",
        "validator": "python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
        "followup_type": "maturity_accrual",
        "default_class": "maturity_blocker",
        "reason": "Clean shadow decision threshold is not met yet.",
        "owner_action": "Continue regular-session shadow accrual until the clean decision threshold is met; no execution readiness claim.",
    },
    "reconciliation_maturity": {
        "title": "Reconciliation maturity",
        "owner": "WF87 maturity lane",
        "validator": "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
        "followup_type": "maturity_accrual",
        "default_class": "maturity_blocker",
        "reason": "Post-trade reconciliation history is not yet mature enough for autonomy.",
        "owner_action": "Continue assisted/reconciliation evidence accrual; do not clear parent maturity until child proof is clean.",
    },
}

BLOCKER_PREFIX_TO_GATE = {
    "approval_freshness_ttl_status_not_allowed": "approval_freshness_ttl",
    "intraday_monitor_status_not_allowed": "intraday_monitor",
    "paper_reconciliation_freshness_status_not_allowed": "paper_reconciliation_freshness",
    "position_sizing_runtime_status_not_allowed": "position_sizing_runtime",
    "portfolio_circuit_breakers_status_not_allowed": "portfolio_circuit_breakers",
}

EXACT_BLOCKER_TO_GATE = {
    "shadow_threshold_not_met": "shadow_threshold",
    "reconciliation_maturity_not_met": "reconciliation_maturity",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def gate_for_blocker(blocker: str) -> str | None:
    if blocker in EXACT_BLOCKER_TO_GATE:
        return EXACT_BLOCKER_TO_GATE[blocker]
    prefix = blocker.split(":", 1)[0]
    return BLOCKER_PREFIX_TO_GATE.get(prefix)


def blocker_class(blocker: str, taxonomy: dict[str, Any], gate_id: str) -> str:
    if blocker in set(str(item) for item in as_list(taxonomy.get("maturity_blockers"))):
        return "maturity_blocker"
    if blocker in set(str(item) for item in as_list(taxonomy.get("fail_closed_at_rest"))):
        return "fail_closed_at_rest"
    if blocker in set(str(item) for item in as_list(taxonomy.get("runtime_blockers"))):
        return "runtime_blocker"
    return str(GATE_DEFS.get(gate_id, {}).get("default_class") or "unclassified")


def source_path_for_gate(gate_id: str, rollup: dict[str, Any]) -> str | None:
    source_map = as_dict(rollup.get("source_artifacts"))
    if gate_id == "approval_freshness_ttl":
        return source_map.get("ttl")
    if gate_id == "intraday_monitor":
        return source_map.get("intraday")
    if gate_id == "paper_reconciliation_freshness":
        return source_map.get("paper_reconciliation")
    if gate_id == "position_sizing_runtime":
        return source_map.get("position_sizing")
    if gate_id == "portfolio_circuit_breakers":
        return source_map.get("circuit_breakers")
    if gate_id == "shadow_threshold":
        return source_map.get("wf86_shadow")
    if gate_id == "reconciliation_maturity":
        return source_map.get("order_history") or source_map.get("paper_reconciliation")
    return None


def rollup_gate_for(gate_id: str, rollup: dict[str, Any]) -> dict[str, Any]:
    gate_names = {
        "approval_freshness_ttl": "approval_freshness_ttl",
        "intraday_monitor": "intraday_monitor",
        "paper_reconciliation_freshness": "paper_reconciliation_freshness",
        "position_sizing_runtime": "position_sizing_runtime",
        "portfolio_circuit_breakers": "portfolio_circuit_breakers",
        "shadow_threshold": "wf86_shadow",
        "reconciliation_maturity": "order_history_reconciliation",
    }
    wanted = gate_names.get(gate_id)
    for row in as_list(rollup.get("gates")):
        row_dict = as_dict(row)
        if row_dict.get("name") == wanted:
            return row_dict
    return {}


def detail_summary(source: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(source.get("summary"))
    details: dict[str, Any] = {
        "status": source.get("status"),
        "validation_status": as_dict(source.get("validation")).get("status"),
    }
    if "critical_finding_count" in summary:
        details["critical_finding_count"] = summary.get("critical_finding_count")
    if "blocked_candidate_count" in summary:
        details["blocked_candidate_count"] = summary.get("blocked_candidate_count")
    if "decision_count" in summary:
        details["decision_count"] = summary.get("decision_count")
    if "scoreable_decision_count" in summary:
        details["scoreable_decision_count"] = summary.get("scoreable_decision_count")
    if "pending_regular_session_followup_count" in summary:
        details["pending_regular_session_followup_count"] = summary.get("pending_regular_session_followup_count")
    findings = [as_dict(item) for item in as_list(source.get("findings"))]
    if findings:
        details["finding_codes"] = [str(item.get("code")) for item in findings if item.get("code")]
        details["findings"] = findings[:12]
    blockers = [str(item) for item in as_list(source.get("blockers"))]
    if blockers:
        details["source_blockers"] = blockers
    checks = as_dict(source.get("checks"))
    if checks:
        details["check_keys"] = sorted(str(key) for key in checks.keys())
    return details


def maturity_context(gate_id: str, rollup: dict[str, Any]) -> dict[str, Any]:
    if gate_id == "shadow_threshold":
        threshold = as_dict(rollup.get("shadow_threshold"))
        done = threshold.get("clean_shadow_decision_count")
        required = threshold.get("required_clean_decisions")
        sessions = threshold.get("unique_clean_market_sessions")
        required_sessions = threshold.get("required_clean_market_sessions")
        return {
            "clean_shadow_decisions": done,
            "required_clean_shadow_decisions": required,
            "unique_clean_market_sessions": sessions,
            "required_clean_market_sessions": required_sessions,
            "gap": (required - done) if isinstance(done, int) and isinstance(required, int) else None,
        }
    if gate_id == "reconciliation_maturity":
        return as_dict(rollup.get("reconciliation_maturity"))
    return {}


def build_explanation(rollup_path: Path) -> dict[str, Any]:
    rollup = load_dict(rollup_path)
    taxonomy = as_dict(rollup.get("blocker_taxonomy"))
    blockers = [str(item) for item in as_list(rollup.get("blockers"))]
    explanations: list[dict[str, Any]] = []
    unexplained: list[str] = []
    authority_paths: list[str] = []

    for blocker in sorted(set(blockers)):
        gate_id = gate_for_blocker(blocker)
        if not gate_id:
            unexplained.append(blocker)
            continue
        definition = GATE_DEFS[gate_id]
        source_rel = source_path_for_gate(gate_id, rollup)
        source_payload = load_dict(resolve(Path(source_rel))) if source_rel else {}
        rollup_gate = rollup_gate_for(gate_id, rollup)
        authority_paths.extend(f"{gate_id}:{path}" for path in authority_true_paths(source_payload))
        gate_class = blocker_class(blocker, taxonomy, gate_id)
        explanation = {
            "gate_id": gate_id,
            "title": definition["title"],
            "blocker": blocker,
            "blocker_class": gate_class,
            "followup_type": definition["followup_type"],
            "source_artifact": source_rel,
            "source_status": source_payload.get("status") or rollup_gate.get("source_status"),
            "source_validation_status": as_dict(source_payload.get("validation")).get("status") or rollup_gate.get("validation_status"),
            "rollup_gate_runtime_status": rollup_gate.get("runtime_status"),
            "reason": definition["reason"],
            "owner": definition["owner"],
            "owner_action": definition["owner_action"],
            "validator": definition["validator"],
            "acceptance": acceptance_for(gate_id, gate_class),
            "detail": detail_summary(source_payload),
            "maturity_context": maturity_context(gate_id, rollup),
            "execution_impact": "blocks autonomous paper/live execution; review-only follow-up remains allowed",
            "authority_boundary": {
                "review_only": True,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        }
        explanations.append(explanation)

    counts: dict[str, int] = {}
    for row in explanations:
        key = str(row.get("blocker_class"))
        counts[key] = counts.get(key, 0) + 1

    validation_errors: list[str] = []
    if unexplained:
        validation_errors.append("unexplained_blockers_present")
    if authority_paths:
        validation_errors.append("authority_drift_detected")
    for row in explanations:
        for key in ("source_artifact", "reason", "owner_action", "validator", "owner"):
            if not row.get(key):
                validation_errors.append(f"missing_{key}:{row.get('blocker')}")

    status = "ok" if not blockers else "runtime_blocked_explained"
    if validation_errors:
        status = "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": status,
        "purpose": "Plain-English runtime gate diagnosis and follow-up routing for WF87.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "rollup": {
            "path": rel(rollup_path),
            "status": rollup.get("status"),
            "generated_at_utc": rollup.get("generated_at_utc"),
            "validation_status": as_dict(rollup.get("validation")).get("status"),
            "market_session": rollup.get("market_session"),
        },
        "summary": {
            "blocker_count": len(blockers),
            "explained_blocker_count": len(explanations),
            "unexplained_blocker_count": len(unexplained),
            "class_counts": dict(sorted(counts.items())),
            "next_safe_action": next_safe_action(explanations, unexplained),
            "execution_allowed": False,
            "owner_action_required_now": bool(explanations),
        },
        "explanations": explanations,
        "unexplained_blockers": unexplained,
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [],
            "authority_drift_paths": sorted(set(authority_paths)),
        },
        "stop_lines": [
            "Explanation rows are review-only and cannot clear gates.",
            "No autonomous paper submit/cancel/sell, live endpoint, account action, money movement, or owner approval inference.",
            "Maturity blockers clear only through evidence accrual; runtime blockers clear only through clean child validators.",
        ],
        "source_artifacts": {
            "wf87_rollup": rel(rollup_path),
        },
    }


def acceptance_for(gate_id: str, gate_class: str) -> list[str]:
    if gate_id == "shadow_threshold":
        return [
            "clean_shadow_decision_count >= required_clean_decisions",
            "unique_clean_market_sessions >= required_clean_market_sessions",
            "WF87 rollup still keeps execution authority false",
        ]
    if gate_id == "reconciliation_maturity":
        return [
            "current reconciliation status and freshness are clean",
            "order history has submitted source proof with unresolved_count == 0",
            "WF87 rollup validates clean after refresh",
        ]
    if gate_class == "fail_closed_at_rest":
        return [
            "source proof refreshed in a real review window",
            "child validator status is ok",
            "no owner approval or execution authority is inferred",
        ]
    return [
        "child validator status is ok",
        "source artifact explains zero critical runtime findings",
        "WF87 rollup no longer lists this blocker",
    ]


def next_safe_action(explanations: list[dict[str, Any]], unexplained: list[str]) -> str:
    if unexplained:
        return "Stop and classify unexplained blockers before opening repair lanes."
    if any(row.get("followup_type") == "implementation_repair" for row in explanations):
        return "Repair runtime implementation/proof inputs first, then rerun WF87 validators."
    if any(row.get("followup_type") == "maturity_accrual" for row in explanations):
        return "Continue scheduled maturity accrual and reconciliation proof; do not execute."
    if explanations:
        return "Refresh fail-closed proof only in a real review window; do not infer approval."
    return "No WF87 runtime blockers require explanation."


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WF87 Runtime Gate Explanation",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Rollup status: `{as_dict(payload.get('rollup')).get('status')}`",
        f"- Next safe action: {as_dict(payload.get('summary')).get('next_safe_action')}",
        "- Authority: review-only; no paper/live/account action; no owner approval inference.",
        "",
        "| Class | Gate | Blocker | Owner Action | Validator |",
        "|---|---|---|---|---|",
    ]
    for row in as_list(payload.get("explanations")):
        row_dict = as_dict(row)
        lines.append(
            "| {class_} | {gate} | `{blocker}` | {action} | `{validator}` |".format(
                class_=row_dict.get("blocker_class"),
                gate=row_dict.get("title"),
                blocker=row_dict.get("blocker"),
                action=str(row_dict.get("owner_action") or "").replace("|", "/"),
                validator=row_dict.get("validator"),
            )
        )
    if payload.get("unexplained_blockers"):
        lines.extend(["", "## Unexplained Blockers", ""])
        for blocker in as_list(payload.get("unexplained_blockers")):
            lines.append(f"- `{blocker}`")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollup", type=Path, default=DEFAULT_ROLLUP)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rollup_path = resolve(args.rollup)
    payload = build_explanation(rollup_path)
    out = resolve(args.out)
    md_out = resolve(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "status={status} validation={validation} blockers={blockers} unexplained={unexplained} out={out}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            blockers=payload["summary"]["blocker_count"],
            unexplained=payload["summary"]["unexplained_blocker_count"],
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
