#!/usr/bin/env python3
"""Score WF86 shadow decisions against later regular-session observations.

The scorecard converts shadow logging from pure threshold-counting into
decision-quality calibration. It is conservative: after-hours duplicate rows
remain pending until a later regular-session observation exists.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SHADOW_LEDGER = TMP / "paper-autotrader" / "shadow-decisions.json"
OUT = TMP / "wf87-shadow-outcome-scorecard.json"

SCHEMA = "veritas.wf87_shadow_outcome_scorecard.v1"
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "shadow_mode_only": True,
    "paper_only_design": True,
    "outcome_calibration_only": True,
    "decision_quality_claim_allowed_now": False,
    "model_performance_claim_allowed_now": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
    "paper_to_live_promotion_allowed": False,
}

FORBIDDEN_TRUE_KEYS = (
    "decision_quality_claim_allowed_now",
    "model_performance_claim_allowed_now",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "owner_approval_inferred",
    "cron_direct_execution_allowed",
    "paper_to_live_promotion_allowed",
)

SCOREABLE_DECISIONS = {"would_buy_shadow", "would_sell_shadow"}
PENDING_AGING_MARKET_DAYS = 2


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


def parse_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def regular_session_context(dt: datetime | None) -> dict[str, Any]:
    if dt is None:
        return {"regular_market_hours": False, "market_date": None, "session_state": "unknown_time"}
    et = dt.astimezone(EASTERN)
    open_dt = datetime.combine(et.date(), time(9, 30), tzinfo=EASTERN)
    close_dt = datetime.combine(et.date(), time(16, 0), tzinfo=EASTERN)
    is_regular = et.weekday() < 5 and open_dt <= et < close_dt
    return {
        "regular_market_hours": is_regular,
        "market_date": et.date().isoformat(),
        "market_time_et": et.replace(microsecond=0).isoformat(),
        "session_state": "regular_market_hours" if is_regular else "outside_regular_market_hours",
    }


def market_day_age(start: datetime | None, end: datetime) -> int | None:
    if start is None:
        return None
    start_date = start.astimezone(EASTERN).date()
    end_date = end.astimezone(EASTERN).date()
    if end_date <= start_date:
        return 0
    days = 0
    cursor = start_date
    while cursor < end_date:
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
        if cursor.weekday() < 5:
            days += 1
    return days


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


def normalized_decision(row: dict[str, Any]) -> dict[str, Any]:
    generated = parse_utc(row.get("generated_at_utc"))
    price = parse_float(row.get("current_price"))
    band = as_dict(row.get("written_band"))
    stop = parse_float(band.get("stop_or_invalidation"))
    context = regular_session_context(generated)
    return {
        "decision_id": row.get("decision_id"),
        "session_key": row.get("session_key"),
        "generated_at_utc": generated,
        "generated_at_utc_text": generated.replace(microsecond=0).isoformat().replace("+00:00", "Z") if generated else None,
        "market_date": context.get("market_date"),
        "regular_market_hours": context.get("regular_market_hours") is True,
        "ticker": str(row.get("ticker") or "").upper(),
        "shadow_decision": row.get("shadow_decision"),
        "current_price": price,
        "current_band_status": row.get("current_band_status"),
        "stop_or_invalidation": stop,
        "assisted_review_ready": row.get("assisted_review_ready") is True,
        "execution_ready": row.get("execution_ready") is True,
    }


def later_regular_observation(decision: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    generated = decision.get("generated_at_utc")
    if not isinstance(generated, datetime):
        return None
    ticker = decision.get("ticker")
    market_date = decision.get("market_date")
    candidates = [
        row
        for row in rows
        if row.get("ticker") == ticker
        and isinstance(row.get("generated_at_utc"), datetime)
        and row["generated_at_utc"] > generated
        and row.get("regular_market_hours") is True
        and row.get("market_date") != market_date
        and row.get("current_price") is not None
    ]
    return min(candidates, key=lambda item: item["generated_at_utc"]) if candidates else None


def rejected_followup_context(decision: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    generated = decision.get("generated_at_utc")
    if not isinstance(generated, datetime):
        return {"candidate_count": 0, "rejection_counts": {}}
    ticker = decision.get("ticker")
    market_date = decision.get("market_date")
    rejection_counts: dict[str, int] = {}
    candidate_count = 0
    for row in rows:
        if row is decision:
            continue
        if row.get("ticker") != ticker:
            continue
        if not isinstance(row.get("generated_at_utc"), datetime) or row["generated_at_utc"] <= generated:
            continue
        candidate_count += 1
        if row.get("regular_market_hours") is not True:
            reason = "outside_regular_market_hours"
        elif row.get("market_date") == market_date:
            reason = "same_market_date"
        elif row.get("current_price") is None:
            reason = "missing_followup_price"
        else:
            reason = "unknown_rejected_context"
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
    return {"candidate_count": candidate_count, "rejection_counts": rejection_counts}


def pending_cause(decision: dict[str, Any], rows: list[dict[str, Any]], pending_stale: bool) -> tuple[str, dict[str, Any], list[str]]:
    context = rejected_followup_context(decision, rows)
    blockers = ["no_later_regular_session_followup"]
    rejection_counts = as_dict(context.get("rejection_counts"))
    blockers.extend(f"rejected_followup:{key}" for key in sorted(rejection_counts))
    if pending_stale:
        cause = "stale_pending_regular_session_followup"
    elif context.get("candidate_count"):
        cause = "duplicate_or_unaccepted_followup_context"
    else:
        cause = "awaiting_regular_session_followup"
    return cause, context, blockers


def score_decision(decision: dict[str, Any], rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    pending_age = market_day_age(decision.get("generated_at_utc"), now)
    base = {
        "decision_id": decision.get("decision_id"),
        "session_key": decision.get("session_key"),
        "generated_at_utc": decision.get("generated_at_utc_text"),
        "ticker": decision.get("ticker"),
        "shadow_decision": decision.get("shadow_decision"),
        "entry_price": decision.get("current_price"),
        "entry_band_status": decision.get("current_band_status"),
        "stop_or_invalidation": decision.get("stop_or_invalidation"),
        "scoreable": False,
        "outcome_status": "pending_regular_session_followup",
        "outcome_label": None,
        "later_observation": None,
        "return_pct": None,
        "stop_or_invalidation_breached": False,
        "pending_age_market_days": pending_age,
        "pending_followup_stale": False,
        "non_score_cause": None,
        "non_score_cause_detail": None,
        "score_blockers": [],
    }
    if decision.get("shadow_decision") not in SCOREABLE_DECISIONS:
        base["outcome_status"] = "informational_only"
        base["non_score_cause"] = "non_scoreable_shadow_decision"
        base["non_score_cause_detail"] = {"shadow_decision": decision.get("shadow_decision")}
        base["score_blockers"] = ["shadow_decision_not_scoreable"]
        return base
    if decision.get("current_price") is None:
        base["outcome_status"] = "pending_entry_price"
        base["non_score_cause"] = "missing_entry_price"
        base["score_blockers"] = ["missing_entry_price"]
        return base
    later = later_regular_observation(decision, rows)
    if later is None:
        base["pending_followup_stale"] = bool(
            pending_age is not None
            and pending_age >= PENDING_AGING_MARKET_DAYS
            and decision.get("shadow_decision") in SCOREABLE_DECISIONS
        )
        cause, detail, blockers = pending_cause(decision, rows, bool(base["pending_followup_stale"]))
        base["non_score_cause"] = cause
        base["non_score_cause_detail"] = detail
        base["score_blockers"] = blockers
        return base
    entry = float(decision["current_price"])
    later_price = float(later["current_price"])
    raw_return = (later_price - entry) / entry if entry else 0.0
    directional_return = raw_return if decision.get("shadow_decision") == "would_buy_shadow" else -raw_return
    stop = decision.get("stop_or_invalidation")
    breached = bool(stop is not None and later_price <= float(stop))
    if breached:
        label = "stop_or_invalidation_breached"
    elif directional_return >= 0.01:
        label = "favorable_follow_through"
    elif directional_return <= -0.01:
        label = "adverse_follow_through"
    else:
        label = "flat_or_noise"
    base.update(
        {
            "scoreable": True,
            "outcome_status": "scored",
            "outcome_label": label,
            "later_observation": {
                "decision_id": later.get("decision_id"),
                "generated_at_utc": later.get("generated_at_utc_text"),
                "market_date": later.get("market_date"),
                "price": later_price,
                "band_status": later.get("current_band_status"),
            },
            "return_pct": round(raw_return * 100, 4),
            "directional_return_pct": round(directional_return * 100, 4),
            "stop_or_invalidation_breached": breached,
            "pending_followup_stale": False,
            "non_score_cause": None,
            "non_score_cause_detail": None,
            "score_blockers": [],
        }
    )
    return base


def cause_counts(scores: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in scores:
        cause = row.get("non_score_cause")
        if cause:
            key = str(cause)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def summarize(scores: list[dict[str, Any]]) -> dict[str, Any]:
    scoreable = [row for row in scores if row.get("scoreable") is True]
    would_buy = [row for row in scoreable if row.get("shadow_decision") == "would_buy_shadow"]
    labels = [str(row.get("outcome_label") or "") for row in scoreable]
    stale_pending = [row for row in scores if row.get("pending_followup_stale") is True]
    return {
        "decision_count": len(scores),
        "scoreable_decision_count": len(scoreable),
        "pending_regular_session_followup_count": sum(1 for row in scores if row.get("outcome_status") == "pending_regular_session_followup"),
        "stale_pending_followup_count": len(stale_pending),
        "pending_aging_market_days": PENDING_AGING_MARKET_DAYS,
        "informational_only_count": sum(1 for row in scores if row.get("outcome_status") == "informational_only"),
        "non_score_cause_counts": cause_counts(scores),
        "would_buy_scored_count": len(would_buy),
        "would_buy_favorable_count": sum(1 for row in would_buy if row.get("outcome_label") == "favorable_follow_through"),
        "would_buy_adverse_count": sum(1 for row in would_buy if row.get("outcome_label") == "adverse_follow_through"),
        "would_buy_flat_or_noise_count": sum(1 for row in would_buy if row.get("outcome_label") == "flat_or_noise"),
        "stop_or_invalidation_breach_count": labels.count("stop_or_invalidation_breached"),
        "decision_quality_claim_allowed_now": False,
        "model_performance_claim_allowed_now": False,
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    authority_paths = authority_true_paths(payload)
    if authority_paths:
        errors.append("authority_drift_detected")
    summary = as_dict(payload.get("summary"))
    if int(summary.get("stale_pending_followup_count") or 0) > 0:
        warnings.append("stale_pending_shadow_followups")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": authority_paths,
    }


def build_payload(shadow_path: Path, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    ledger = load_dict(shadow_path)
    decisions = [normalized_decision(row) for row in as_list(ledger.get("decisions")) if isinstance(row, dict)]
    decisions = [row for row in decisions if row.get("ticker")]
    decisions.sort(key=lambda row: row.get("generated_at_utc") or datetime.min.replace(tzinfo=timezone.utc))
    scores = [score_decision(row, decisions, current) for row in decisions]
    summary = summarize(scores)
    if summary["stale_pending_followup_count"]:
        status = "pending_regular_session_followup_stale"
    else:
        status = "ok" if summary["scoreable_decision_count"] else "pending_regular_session_followup"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": status,
        "purpose": "Review-only forward outcome calibration for WF86 shadow decisions.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "scores": scores,
        "method": {
            "minimum_followup": "later regular-session same-ticker observation on a different market date",
            "after_hours_duplicate_rows": "left pending, not scored",
            "quality_claim_threshold": "future policy; current packet never claims performance quality",
            "pending_aging_threshold_market_days": PENDING_AGING_MARKET_DAYS,
        },
        "next_safe_action": "Keep accumulating regular-session follow-up observations before using shadow outcomes for calibration.",
        "stop_lines": [
            "Outcome scoring is calibration only, not approval or execution authority.",
            "Do not infer performance quality from pending or low-count observations.",
            "No paper/live submit, cancel, sell, account action, money movement, or owner approval inference.",
        ],
        "source_artifacts": {"shadow_ledger": rel(shadow_path)},
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shadow-ledger", type=Path, default=SHADOW_LEDGER)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    shadow_path = args.shadow_ledger if args.shadow_ledger.is_absolute() else ROOT / args.shadow_ledger
    payload = build_payload(shadow_path)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} scored={scored} pending={pending} out={out}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            scored=payload["summary"]["scoreable_decision_count"],
            pending=payload["summary"]["pending_regular_session_followup_count"],
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
