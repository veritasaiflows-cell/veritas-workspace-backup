#!/usr/bin/env python3
"""Build a review-only recommendation outcome digest.

The digest summarizes recommendation tracking and forward checkpoints from the
durable outcome ledgers.  It intentionally has no simulated-account, order,
execution-readiness, or retired workflow inputs.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
RECOMMENDATION_LEDGER = ROOT / "data" / "state-history" / "outcome-ledger-v2.jsonl"
RECOMMENDATION_GRADE_HISTORY = ROOT / "data" / "state-history" / "recommendation-outcome-grades.jsonl"
OUT = ROOT / "tmp" / "finance-decision-performance-digest.json"
MD_OUT = ROOT / "tmp" / "finance-decision-performance-digest.md"

SCHEMA = "veritas.finance_decision_performance_digest.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "recommendation_outcome_tracking_only": True,
    "predictive_skill_claim_allowed_now": False,
    "model_performance_claim_allowed_now": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": str(exc), "_line_number": line_number})
            continue
        rows.append(value if isinstance(value, dict) else {"_parse_error": "row is not an object", "_line_number": line_number})
    return rows


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def summarize_grade_history(rows: list[dict[str, Any]], source_path: Path) -> dict[str, Any]:
    clean = [row for row in rows if not row.get("_parse_error")]
    assigned = [row for row in clean if row.get("grade_status") == "assigned" and row.get("assigned_grade")]
    grade_counts: dict[str, int] = {}
    for row in assigned:
        grade = str(row.get("assigned_grade") or "unknown")
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    return {
        "source": rel(source_path),
        "row_count": len(clean),
        "parse_error_count": len(rows) - len(clean),
        "assigned_grade_event_count": len(assigned),
        "graded_ledger_event_count": len({str(row.get("ledger_event_id") or "") for row in assigned if row.get("ledger_event_id")}),
        "grade_counts": dict(sorted(grade_counts.items())),
    }


def summarize_recommendation_outcomes(
    rows: list[dict[str, Any]],
    now: datetime,
    grade_rows: list[dict[str, Any]] | None = None,
    grade_history_path: Path = RECOMMENDATION_GRADE_HISTORY,
) -> dict[str, Any]:
    clean = [row for row in rows if not row.get("_parse_error")]
    tracking = [row for row in clean if row.get("event_family") == "recommendation_tracking"]
    checkpoint_status_counts: dict[str, int] = {}
    horizon_due_counts: dict[str, int] = {}
    due_unobserved = 0
    observed = 0
    for row in tracking:
        scorecard = as_dict(row.get("forward_scorecard"))
        for checkpoint in as_list(scorecard.get("checkpoints")):
            if not isinstance(checkpoint, dict):
                continue
            status = str(checkpoint.get("status") or "unknown")
            checkpoint_status_counts[status] = checkpoint_status_counts.get(status, 0) + 1
            due = parse_utc(checkpoint.get("due_at_utc"))
            horizon = str(checkpoint.get("horizon_days") or "unknown")
            if due and due <= now:
                horizon_due_counts[horizon] = horizon_due_counts.get(horizon, 0) + 1
                if checkpoint.get("observed_price") is None:
                    due_unobserved += 1
                else:
                    observed += 1
    tickers = sorted({str(row.get("ticker") or "").upper() for row in tracking if row.get("ticker")})
    grade_summary = summarize_grade_history(grade_rows or [], grade_history_path)
    legacy_assigned = sum(1 for row in tracking if as_dict(row.get("forward_scorecard")).get("outcome_grade_assigned") is True)
    history_assigned = int(grade_summary.get("graded_ledger_event_count") or 0)
    return {
        "source": rel(RECOMMENDATION_LEDGER),
        "row_count": len(clean),
        "parse_error_count": len(rows) - len(clean),
        "recommendation_tracking_rows": len(tracking),
        "tracked_tickers": tickers,
        "tracked_ticker_count": len(tickers),
        "forward_checkpoint_status_counts": dict(sorted(checkpoint_status_counts.items())),
        "due_checkpoint_counts_by_horizon": dict(sorted(horizon_due_counts.items())),
        "due_unobserved_checkpoint_count": due_unobserved,
        "observed_checkpoint_count": observed,
        "outcome_grade_assigned_count": max(legacy_assigned, history_assigned),
        "legacy_forward_scorecard_grade_count": legacy_assigned,
        "grade_history": grade_summary,
    }


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


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append("authority_drift_detected")
    outcomes = as_dict(payload.get("recommendation_outcomes"))
    if int(outcomes.get("outcome_grade_assigned_count") or 0) == 0:
        warnings.append("no_mature_recommendation_outcomes_yet")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": drift,
    }


def build_payload(paths: dict[str, Path], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    ledger_rows = load_jsonl(paths["recommendation_ledger"])
    grade_rows = load_jsonl(paths["recommendation_grade_history"])
    outcomes = summarize_recommendation_outcomes(ledger_rows, current, grade_rows, paths["recommendation_grade_history"])
    mature = int(outcomes.get("outcome_grade_assigned_count") or 0) > 0
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if mature else "pending_mature_observations",
        "purpose": "Daily review-only recommendation outcome and forward-checkpoint digest.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "recommendation_outcomes": outcomes,
        "performance_claim_status": {
            "mature_observations_present": mature,
            "predictive_skill_claim_allowed_now": False,
            "model_performance_claim_allowed_now": False,
            "reason": "Outcome observations support review but never independently authorize predictive or model-ranking claims.",
        },
        "next_safe_action": "Keep collecting recommendation outcomes and source observations; preserve review-only claim gates.",
        "stop_lines": [
            "Outcome rows are not recommendation approval.",
            "No predictive skill, expected-return, capital, execution, account, or owner-approval inference.",
        ],
        "source_artifacts": {key: rel(path) for key, path in paths.items()},
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    outcomes = as_dict(payload.get("recommendation_outcomes"))
    claim = as_dict(payload.get("performance_claim_status"))
    return "\n".join([
        "# Recommendation Outcome Performance Digest",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{as_dict(payload.get('validation')).get('status')}`",
        f"- Recommendation rows: `{outcomes.get('recommendation_tracking_rows')}` across `{outcomes.get('tracked_ticker_count')}` tickers",
        f"- Later-outcome graded rows: `{outcomes.get('outcome_grade_assigned_count')}`",
        f"- Due unobserved checkpoints: `{outcomes.get('due_unobserved_checkpoint_count')}`",
        f"- Predictive skill claim allowed now: `{claim.get('predictive_skill_claim_allowed_now')}`",
        "",
        "Review-only outcome tracking. No approval, execution, account, capital, canon, or predictive-performance authority.",
        "",
    ])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recommendation-ledger", dest="recommendation_ledger", type=Path, default=RECOMMENDATION_LEDGER)
    parser.add_argument("--recommendation-grade-history", dest="recommendation_grade_history", type=Path, default=RECOMMENDATION_GRADE_HISTORY)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    paths = {
        "recommendation_ledger": abs_path(args.recommendation_ledger),
        "recommendation_grade_history": abs_path(args.recommendation_grade_history),
    }
    payload = build_payload(paths)
    out = abs_path(args.out)
    md_out = abs_path(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload), encoding="utf-8")
    outcomes = payload["recommendation_outcomes"]
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"recommendation_rows={outcomes['recommendation_tracking_rows']} "
        f"graded={outcomes['outcome_grade_assigned_count']} out={rel(out) if args.write else None}"
    )
    return 1 if args.validate and payload["validation"]["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
