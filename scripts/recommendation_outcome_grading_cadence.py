#!/usr/bin/env python3
"""Append review-only recommendation outcome grades from mature local evidence.

This script is deliberately narrow. It reads immutable WF55 recommendation rows,
recomputes mature forward checkpoints from the local post-close quote ledger,
and appends separate grade events to an audit ledger. It does not rewrite the
original recommendation ledger and grants no approval, trading, portfolio/canon,
or predictive-performance authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text
import wf55_outcome_ledger_v2 as wf55


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "state-history" / "outcome-ledger-v2.jsonl"
DEFAULT_GRADE_LEDGER = ROOT / "data" / "state-history" / "recommendation-outcome-grades.jsonl"
DEFAULT_QUOTE_LEDGER = ROOT / "tmp" / "post-close-final-quote-ledger.json"
OUT = ROOT / "tmp" / "recommendation-outcome-grading-cadence.json"
MD_OUT = ROOT / "tmp" / "recommendation-outcome-grading-cadence.md"

SCHEMA = "veritas.recommendation_outcome_grading_cadence.v1"
GRADE_ROW_SCHEMA = "veritas.recommendation_outcome_grade_event.v1"
MIN_GRADE_EVENTS_FOR_MODEL_PERFORMANCE_CLAIM = 30

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "append_only_grade_history": True,
    "predictive_skill_claim_allowed": False,
    "model_performance_claim_allowed": False,
    "model_ranked_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_FIELDS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}
GRADE_BY_NAME = {row["grade"]: row for row in wf55.RECOMMENDATION_OUTCOME_GRADES}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    return wf55.parse_dt(value)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def numeric(value: Any) -> float | None:
    return wf55.numeric(value)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return wf55.load_jsonl(path)


def load_quote_map(path: Path) -> dict[str, dict[str, Any]]:
    return wf55.price_quote_map(path)


def hard_false_authority() -> dict[str, Any]:
    return {
        **AUTHORITY_BOUNDARY,
        "statement": "Review-only outcome grade history from local evidence; no approval, execution, account, portfolio/canon, capital, model-ranking, or predictive-performance authority.",
    }


def model_performance_claim_gate(total_grade_events: int, graded_ledger_events: int) -> dict[str, Any]:
    return {
        "schema": "veritas.recommendation_model_performance_claim_gate.v1",
        "model_performance_claim_allowed": False,
        "predictive_skill_claim_allowed": False,
        "review_only_outcome_measurement_available": total_grade_events > 0,
        "total_grade_event_count": total_grade_events,
        "graded_ledger_event_count": graded_ledger_events,
        "required_grade_event_count": MIN_GRADE_EVENTS_FOR_MODEL_PERFORMANCE_CLAIM,
        "sample_gate_met": total_grade_events >= MIN_GRADE_EVENTS_FOR_MODEL_PERFORMANCE_CLAIM,
        "reason": (
            "Recommendation grade events are conservative local outcome measurements. "
            "They do not authorize model-performance, predictive-skill, ranking, capital, or execution claims."
        ),
    }


def source_artifact(path: Path, status: str = "present") -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": wf55.sha256_file(path),
        "generated_at_utc": wf55.generated_at_from_json(path),
        "status": status,
    }


def grade_event_id(ledger_event_id: str, horizon_days: int, observed_price_as_of: str, observed_price: float, grade: str) -> str:
    seed = f"{ledger_event_id}|{horizon_days}|{observed_price_as_of}|{observed_price:.6f}|{grade}"
    return "rec_grade_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18]


def latest_scored_checkpoint(scorecard: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    scored: list[dict[str, Any]] = []
    for checkpoint in as_list(scorecard.get("checkpoints")):
        if not isinstance(checkpoint, dict) or checkpoint.get("status") != "scored_local_quote":
            continue
        due = parse_utc(checkpoint.get("due_at_utc"))
        if due is None or due > now:
            continue
        scored.append(checkpoint)
    scored.sort(key=lambda row: int(row.get("horizon_days") or 0))
    return scored[-1] if scored else None


def classify_grade(row: dict[str, Any], scorecard: dict[str, Any], checkpoint: dict[str, Any]) -> tuple[str | None, str]:
    known = as_dict(scorecard.get("known_at_time"))
    observed_price = numeric(checkpoint.get("observed_price"))
    absolute_return_pct = numeric(checkpoint.get("absolute_return_pct"))
    if observed_price is None:
        return None, "missing_observed_price"

    entry_low = numeric(known.get("entry_band_low"))
    entry_high = numeric(known.get("entry_band_high"))
    stop = numeric(known.get("stop_or_invalidation"))
    band_status = str(known.get("band_status") or "").upper()
    has_band = entry_low is not None or entry_high is not None

    if stop is not None and observed_price <= stop:
        return "stop_or_invalidation_hit", "observed price is at or below the written stop/invalidation level"

    if "ABOVE" in band_status:
        if entry_high is not None and observed_price <= entry_high:
            return "no_chase_correct", "setup was above band at capture and later moved back into the entry band"
        if absolute_return_pct is not None and absolute_return_pct <= -3.0:
            return "no_chase_correct", "setup was above band at capture and later pulled back materially"
        return None, "above_band_setup_has_not_validated_no_chase_yet"

    if entry_low is not None and observed_price < entry_low:
        return "entry_poor_even_if_thesis_right", "observed price is below the captured entry-band low"

    if has_band and entry_low is not None and observed_price >= entry_low:
        return "band_reclaim_held", "price-only band evidence remains at or above the captured entry-band low"

    if not has_band and absolute_return_pct is not None and absolute_return_pct <= -5.0:
        return "entry_poor_even_if_thesis_right", "no band was retained locally and observed return is materially negative"

    return None, "no_conservative_semantic_grade_from_local_quote_only"


def build_grade_event(
    row: dict[str, Any],
    scorecard: dict[str, Any],
    checkpoint: dict[str, Any],
    grade: str,
    reason: str,
    *,
    ledger_path: Path,
    quote_path: Path,
    graded_at_utc: str,
) -> dict[str, Any]:
    known = as_dict(scorecard.get("known_at_time"))
    payload = as_dict(row.get("payload"))
    grade_def = GRADE_BY_NAME[grade]
    observed_price = float(numeric(checkpoint.get("observed_price")) or 0.0)
    observed_as_of = str(checkpoint.get("observed_price_as_of") or "")
    horizon_days = int(checkpoint.get("horizon_days") or 0)
    ledger_event_id = str(row.get("ledger_event_id") or "")
    event = {
        "schema": GRADE_ROW_SCHEMA,
        "row_type": "recommendation_outcome_grade_v1",
        "grade_event_id": grade_event_id(ledger_event_id, horizon_days, observed_as_of, observed_price, grade),
        "ledger_event_id": ledger_event_id,
        "ticker": str(row.get("ticker") or "").upper(),
        "recommendation_id": payload.get("recommendation_id"),
        "event_subtype": row.get("event_subtype"),
        "graded_at_utc": graded_at_utc,
        "grade_status": "assigned",
        "assigned_grade": grade,
        "grade_group": grade_def.get("grade_group"),
        "is_failure_mode": grade_def.get("is_failure_mode"),
        "grading_mode": "deterministic_local_quote_and_band_evidence_only",
        "evidence_summary": reason,
        "evidence_window": {
            "horizon_days": horizon_days,
            "due_at_utc": checkpoint.get("due_at_utc"),
            "observed_price_as_of": observed_as_of,
        },
        "known_at_time": {
            "anchor_price": known.get("anchor_price"),
            "entry_band_low": known.get("entry_band_low"),
            "entry_band_high": known.get("entry_band_high"),
            "stop_or_invalidation": known.get("stop_or_invalidation"),
            "band_status": known.get("band_status"),
            "source_artifact_path": known.get("source_artifact_path"),
            "no_hindsight_guard": known.get("no_hindsight_guard") is True,
        },
        "observed": {
            "observed_price": observed_price,
            "absolute_return_pct": checkpoint.get("absolute_return_pct"),
            "benchmark_status": checkpoint.get("benchmark_status"),
            "relative_return_pct": checkpoint.get("relative_return_pct"),
        },
        "source_artifacts": [
            source_artifact(ledger_path),
            source_artifact(quote_path),
        ],
        "authority": hard_false_authority(),
        "boundary": "Outcome grade is review-only measurement. It is not recommendation approval, a predictive claim, a model ranking, or permission to mutate portfolio/canon state or trade.",
    }
    source_path = payload.get("source_artifact_path")
    if isinstance(source_path, str) and source_path:
        candidate = ROOT / source_path
        event["source_artifacts"].append(source_artifact(candidate, "linked_recommendation_source"))
    return event


def build_payload(paths: dict[str, Path], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    graded_at = utc_now()

    rows = [row for row in load_jsonl(paths["ledger"]) if not row.get("_parse_error")]
    recommendation_rows = [row for row in rows if row.get("event_family") == "recommendation_tracking"]
    prices = load_quote_map(paths["quote_ledger"])
    existing_grade_rows = [row for row in load_jsonl(paths["grade_ledger"]) if not row.get("_parse_error")]
    existing_ids = {str(row.get("grade_event_id")) for row in existing_grade_rows if row.get("grade_event_id")}

    candidate_events: list[dict[str, Any]] = []
    skipped_existing: list[str] = []
    ungraded: list[dict[str, Any]] = []
    for row in recommendation_rows:
        ticker = str(row.get("ticker") or "").upper()
        ledger_event_id = str(row.get("ledger_event_id") or "")
        if ticker not in prices:
            ungraded.append({"ledger_event_id": ledger_event_id, "ticker": ticker, "reason": "missing_local_quote"})
            continue
        scorecard = wf55.forward_scorecard_for_row(row, prices, current)
        checkpoint = latest_scored_checkpoint(scorecard, current)
        if checkpoint is None:
            ungraded.append({"ledger_event_id": ledger_event_id, "ticker": ticker, "reason": scorecard.get("status") or "no_mature_scored_checkpoint"})
            continue
        grade, reason = classify_grade(row, scorecard, checkpoint)
        if grade is None:
            ungraded.append({"ledger_event_id": ledger_event_id, "ticker": ticker, "reason": reason})
            continue
        event = build_grade_event(
            row,
            scorecard,
            checkpoint,
            grade,
            reason,
            ledger_path=paths["ledger"],
            quote_path=paths["quote_ledger"],
            graded_at_utc=graded_at,
        )
        if event["grade_event_id"] in existing_ids:
            skipped_existing.append(str(event["grade_event_id"]))
            continue
        candidate_events.append(event)

    grade_counts = Counter(str(row.get("assigned_grade") or "unknown") for row in candidate_events)
    ungraded_counts = Counter(str(row.get("reason") or "unknown") for row in ungraded)
    existing_assigned_ids = {
        str(row.get("ledger_event_id"))
        for row in existing_grade_rows
        if row.get("grade_status") == "assigned" and row.get("ledger_event_id")
    }
    candidate_assigned_ids = {str(row.get("ledger_event_id")) for row in candidate_events if row.get("ledger_event_id")}
    total_grade_events_after_append = len(existing_grade_rows) + len(candidate_events)
    graded_events_after_append = len(existing_assigned_ids | candidate_assigned_ids)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": graded_at,
        "status": "ok" if candidate_events or existing_grade_rows else "pending_mature_grade_events",
        "cadence": "daily_with_wf88_wiki_synthesis_refresh",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "ledger": rel(paths["ledger"]),
            "grade_ledger": rel(paths["grade_ledger"]),
            "quote_ledger": rel(paths["quote_ledger"]),
        },
        "summary": {
            "recommendation_row_count": len(recommendation_rows),
            "local_quote_ticker_count": len(prices),
            "eligible_new_grade_event_count": len(candidate_events),
            "skipped_existing_grade_event_count": len(skipped_existing),
            "existing_grade_event_count": len(existing_grade_rows),
            "total_grade_event_count_after_append": total_grade_events_after_append,
            "graded_ledger_event_count_after_append": graded_events_after_append,
            "grade_counts_for_new_events": dict(sorted(grade_counts.items())),
            "ungraded_count": len(ungraded),
            "ungraded_reason_counts": dict(sorted(ungraded_counts.items())),
            "model_performance_claim_gate": model_performance_claim_gate(
                total_grade_events_after_append,
                graded_events_after_append,
            ),
        },
        "grade_events_to_append": candidate_events,
        "skipped_existing_grade_event_ids": skipped_existing,
        "ungraded_rows": ungraded[:100],
        "source_artifacts": {
            "ledger": source_artifact(paths["ledger"]),
            "quote_ledger": source_artifact(paths["quote_ledger"]),
            "grade_ledger": source_artifact(paths["grade_ledger"], "append_only_target"),
        },
        "validation": {},
        "boundary": "Append-only review-only outcome grade cadence. No model-performance, win-rate, expected-return, approval, execution, account, portfolio, canon, or capital-action authority.",
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "blocked":
        payload["status"] = "blocked"
    return payload


def append_grade_events(events: list[dict[str, Any]], grade_ledger: Path) -> dict[str, Any]:
    grade_ledger.parent.mkdir(parents=True, exist_ok=True)
    existing = [row for row in load_jsonl(grade_ledger) if not row.get("_parse_error")]
    existing_ids = {str(row.get("grade_event_id")) for row in existing if row.get("grade_event_id")}
    appended: list[str] = []
    skipped: list[str] = []
    with grade_ledger.open("a", encoding="utf-8") as handle:
        for event in events:
            event_id = str(event.get("grade_event_id") or "")
            if not event_id or event_id in existing_ids:
                if event_id:
                    skipped.append(event_id)
                continue
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            existing_ids.add(event_id)
            appended.append(event_id)
    return {
        "status": "ok",
        "grade_ledger": rel(grade_ledger),
        "appended_count": len(appended),
        "skipped_existing_count": len(skipped),
        "appended_grade_event_ids": appended,
        "skipped_grade_event_ids": skipped,
        "authority": hard_false_authority(),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    if boundary.get("review_only") is not True or boundary.get("append_only_grade_history") is not True:
        errors.append("authority_boundary_review_append_flags_invalid")
    for key in FALSE_AUTHORITY_FIELDS:
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")

    seen: set[str] = set()
    for idx, event in enumerate(as_list(payload.get("grade_events_to_append")), start=1):
        event = as_dict(event)
        if event.get("schema") != GRADE_ROW_SCHEMA:
            errors.append(f"event_{idx}_schema_invalid")
        event_id = event.get("grade_event_id")
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"event_{idx}_grade_event_id_missing")
        elif event_id in seen:
            errors.append(f"event_{idx}_duplicate_grade_event_id")
        else:
            seen.add(event_id)
        grade = event.get("assigned_grade")
        if grade not in GRADE_BY_NAME:
            errors.append(f"event_{idx}_grade_not_in_taxonomy")
        if event.get("grade_status") != "assigned":
            errors.append(f"event_{idx}_grade_status_not_assigned")
        authority = as_dict(event.get("authority"))
        for key in FALSE_AUTHORITY_FIELDS:
            if authority.get(key) is not False:
                errors.append(f"event_{idx}_authority_{key}_must_be_false")
        artifacts = as_list(event.get("source_artifacts"))
        if len(artifacts) < 2:
            errors.append(f"event_{idx}_source_artifacts_missing")
        if as_dict(event.get("known_at_time")).get("no_hindsight_guard") is not True:
            errors.append(f"event_{idx}_no_hindsight_guard_missing")
    if not as_list(payload.get("grade_events_to_append")) and not int(as_dict(payload.get("summary")).get("existing_grade_event_count") or 0):
        warnings.append("no_grade_events_available_yet")
    return {
        "status": "blocked" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Recommendation Outcome Grading Cadence",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{as_dict(payload.get('validation')).get('status')}`",
        f"- Recommendation rows: `{summary.get('recommendation_row_count')}`",
        f"- New grade events: `{summary.get('eligible_new_grade_event_count')}`",
        f"- Existing grade events: `{summary.get('existing_grade_event_count')}`",
        f"- Graded recommendation rows after append: `{summary.get('graded_ledger_event_count_after_append')}`",
        f"- Ungraded rows: `{summary.get('ungraded_count')}`",
        f"- Model-performance claim allowed: `{as_dict(summary.get('model_performance_claim_gate')).get('model_performance_claim_allowed')}`",
        "",
        "## New Grade Counts",
        "",
    ]
    for grade, count in as_dict(summary.get("grade_counts_for_new_events")).items():
        lines.append(f"- `{grade}`: `{count}`")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Append-only review-only measurement. No approval, execution, account, capital, portfolio/canon, model-ranking, or predictive-performance authority.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--grade-ledger", type=Path, default=DEFAULT_GRADE_LEDGER)
    parser.add_argument("--quote-ledger", type=Path, default=DEFAULT_QUOTE_LEDGER)
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
        "ledger": abs_path(args.ledger),
        "grade_ledger": abs_path(args.grade_ledger),
        "quote_ledger": abs_path(args.quote_ledger),
    }
    payload = build_payload(paths)
    append_report = None
    if args.write and payload["validation"]["status"] != "blocked":
        append_report = append_grade_events(as_list(payload.get("grade_events_to_append")), paths["grade_ledger"])
        payload["append_report"] = append_report
        payload = build_payload(paths)
        payload["append_report"] = append_report
    out = abs_path(args.out)
    md_out = abs_path(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    summary = as_dict(payload.get("summary"))
    print(json.dumps({
        "status": payload.get("status"),
        "validation": payload.get("validation"),
        "new_grade_events": summary.get("eligible_new_grade_event_count"),
        "existing_grade_events": summary.get("existing_grade_event_count"),
        "graded_ledger_event_count_after_append": summary.get("graded_ledger_event_count_after_append"),
        "append_report": append_report,
        "out": rel(out) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
