from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from market_data_utils import atomic_write_json, load_json_artifact
from state_history_outcome_update import ALLOWED_OUTCOME_LABELS

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history" / "state-history-v1.jsonl"
OUTCOME_UPDATES = ROOT / "data" / "state-history" / "outcome-updates-v1.jsonl"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
HISTORICAL_REGIME_LIBRARY = TMP / "historical-regime-event-library.json"
DEFAULT_OUT = TMP / "probability-readiness-report.json"
DEFAULT_MD = TMP / "probability-readiness-report.md"
SCHEMA_VERSION = 1

EVIDENCE_ARTIFACTS = {
    "state_history": STATE_HISTORY,
    "research_freshness_opportunity_review": TMP / "research-freshness-opportunity-review.json",
    "small_mid_cap_regime_feed": TMP / "small-mid-cap-regime-feed.json",
    "sector_expansion_board": TMP / "sector-expansion-board.json",
    "capital_deployment_recommendations": TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json",
    "capital_deployment_recommendation_validation": TMP / "capital-deployment-recommendation-validation.json",
    "recommendation_outcome_ledger_current": RECOMMENDATION_LEDGER,
    "historical_regime_event_library": HISTORICAL_REGIME_LIBRARY,
}

AUTHORITY_FALSE_FIELDS = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "owner_approval_granted",
    "owner_approval_inference_allowed",
    "per_packet_owner_approval_inferred",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
    "proposal_apply_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": str(exc), "_line_number": line_number})
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            rows.append({"_parse_error": "row is not an object", "_line_number": line_number})
    return rows


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def outcome_update_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    parse_errors = []
    labels: dict[str, int] = {}
    linked_snapshots: set[str] = set()
    observed: list[datetime] = []
    owner_decision_count = 0
    for index, row in enumerate(rows, start=1):
        if row.get("_parse_error"):
            parse_errors.append({"row": index, "detail": row.get("_parse_error")})
            continue
        if row.get("row_type") != "outcome_update_v1":
            continue
        label = str(row.get("outcome_label") or "unknown")
        labels[label] = labels.get(label, 0) + 1
        linked = row.get("linked_capture_run_id")
        if isinstance(linked, str) and linked:
            linked_snapshots.add(linked)
        observed_dt = parse_dt(row.get("observed_at_utc"))
        if observed_dt:
            observed.append(observed_dt)
        if row.get("owner_decision"):
            owner_decision_count += 1
    observed_sorted = sorted(observed)
    return {
        "path": rel(OUTCOME_UPDATES),
        "exists": OUTCOME_UPDATES.exists(),
        "row_count": len(rows),
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:10],
        "realized_outcome_count": sum(labels.values()),
        "owner_decision_count": owner_decision_count,
        "linked_snapshot_count": len(linked_snapshots),
        "label_counts": labels,
        "observed_start_utc": observed_sorted[0].isoformat().replace("+00:00", "Z") if observed_sorted else "",
        "observed_end_utc": observed_sorted[-1].isoformat().replace("+00:00", "Z") if observed_sorted else "",
    }


def state_history_summary(rows: list[dict[str, Any]], outcome_updates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    outcome_updates = outcome_updates or []
    outcome_sidecar = outcome_update_summary(outcome_updates)
    captured: list[datetime] = []
    embedded_realized_outcome_count = 0
    embedded_owner_decision_count = 0
    parse_errors = []
    future_timestamp_issues = []
    windows: dict[str, int] = {}
    for index, row in enumerate(rows, start=1):
        if row.get("_parse_error"):
            parse_errors.append({"row": index, "detail": row.get("_parse_error")})
            continue
        captured_at = parse_dt(row.get("captured_at_utc"))
        if captured_at:
            captured.append(captured_at)
        window = str(row.get("window") or "unknown")
        windows[window] = windows.get(window, 0) + 1
        future = row.get("future_outcomes") or {}
        if isinstance(future, dict):
            realized = future.get("realized_outcomes")
            if isinstance(realized, list):
                embedded_realized_outcome_count += len(realized)
            if future.get("owner_decision") is not None:
                embedded_owner_decision_count += 1
            for field in ("owner_decision_at_utc", "realized_outcomes_updated_at_utc"):
                future_dt = parse_dt(future.get(field))
                if future_dt and captured_at and future_dt <= captured_at:
                    future_timestamp_issues.append({
                        "row": index,
                        "field": field,
                        "captured_at_utc": row.get("captured_at_utc"),
                        "future_timestamp": future.get(field),
                    })
    captured_sorted = sorted(captured)
    timestamp_gap_hours: list[float] = []
    for earlier, later in zip(captured_sorted, captured_sorted[1:]):
        timestamp_gap_hours.append(round((later - earlier).total_seconds() / 3600, 2))
    return {
        "path": rel(STATE_HISTORY),
        "exists": STATE_HISTORY.exists(),
        "row_count": len(rows),
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:10],
        "captured_start_utc": captured_sorted[0].isoformat().replace("+00:00", "Z") if captured_sorted else "",
        "captured_end_utc": captured_sorted[-1].isoformat().replace("+00:00", "Z") if captured_sorted else "",
        "history_span_days": round((captured_sorted[-1] - captured_sorted[0]).total_seconds() / 86400, 2) if len(captured_sorted) >= 2 else 0,
        "max_timestamp_gap_hours": max(timestamp_gap_hours) if timestamp_gap_hours else 0,
        "timestamp_gap_hours": timestamp_gap_hours,
        "windows": windows,
        "embedded_realized_outcome_count": embedded_realized_outcome_count,
        "embedded_owner_decision_count": embedded_owner_decision_count,
        "outcome_sidecar": outcome_sidecar,
        "realized_outcome_count": embedded_realized_outcome_count + int(outcome_sidecar.get("realized_outcome_count") or 0),
        "owner_decision_count": embedded_owner_decision_count + int(outcome_sidecar.get("owner_decision_count") or 0),
        "outcome_analytics_ready": False,
        "future_timestamp_issue_count": len(future_timestamp_issues),
        "future_timestamp_issues": future_timestamp_issues[:20],
    }


def artifact_status(path: Path) -> dict[str, Any]:
    doc = load_json_artifact(path)
    generated = ""
    status = "missing"
    authority: dict[str, Any] = {}
    if isinstance(doc, dict):
        status = str(doc.get("status") or "present")
        generated = str(doc.get("generated_at_utc") or doc.get("generated_at") or "")
        raw_authority = doc.get("authority")
        if isinstance(raw_authority, dict):
            authority = {k: raw_authority.get(k) for k in sorted(raw_authority) if k in AUTHORITY_FALSE_FIELDS or k.endswith("allowed") or k.endswith("granted")}
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": status,
        "generated_at_utc": generated,
        "authority_snapshot": authority,
    }


def recommendation_tracking_summary(path: Path = RECOMMENDATION_LEDGER) -> dict[str, Any]:
    doc = load_json_artifact(path)
    if not isinstance(doc, dict):
        return {
            "path": rel(path),
            "exists": path.exists(),
            "status": "missing_or_unparseable",
            "tracking_row_count": 0,
            "pending_owner_decision_rows": 0,
            "pending_paper_card_rows": 0,
            "predictive_or_model_claims_allowed": False,
            "paper_or_live_execution_allowed": False,
        }
    summary = doc.get("recommendation_tracking_summary") if isinstance(doc.get("recommendation_tracking_summary"), dict) else {}
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": doc.get("status"),
        "tracking_status": summary.get("status"),
        "tracking_row_count": summary.get("tracking_row_count"),
        "capital_recommendation_rows": summary.get("capital_recommendation_rows"),
        "pending_owner_decision_rows": summary.get("pending_owner_decision_rows"),
        "pending_paper_card_rows": summary.get("pending_paper_card_rows"),
        "tracked_tickers": summary.get("tracked_tickers"),
        "durable_append_allowed": False,
        "predictive_or_model_claims_allowed": False,
        "paper_or_live_execution_allowed": False,
    }


def historical_regime_summary(path: Path = HISTORICAL_REGIME_LIBRARY) -> dict[str, Any]:
    doc = load_json_artifact(path)
    if not isinstance(doc, dict):
        return {
            "path": rel(path),
            "exists": path.exists(),
            "status": "missing_or_unparseable",
            "event_count": 0,
            "small_large_comparison_available_count": 0,
            "base_rate_context_only": True,
            "calibrated_probability_allowed": False,
            "predictive_or_model_claims_allowed": False,
        }
    summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
    authority = doc.get("authority") if isinstance(doc.get("authority"), dict) else {}
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": doc.get("status"),
        "event_count": summary.get("event_count"),
        "pre_1990_event_count": summary.get("pre_1990_event_count"),
        "post_2000_event_count": summary.get("post_2000_event_count"),
        "small_large_comparison_available_count": summary.get("small_large_comparison_available_count"),
        "rate_stabilization_direct_events": summary.get("rate_stabilization_direct_events"),
        "base_rate_context_only": authority.get("base_rate_context_only") is True,
        "calibrated_probability_allowed": False,
        "predictive_or_model_claims_allowed": False,
    }


def source_quality_gates(artifacts: dict[str, dict[str, Any]], history: dict[str, Any]) -> list[dict[str, Any]]:
    gates = []
    for key, record in artifacts.items():
        gates.append({
            "gate": key,
            "status": "pass" if record.get("exists") and record.get("status") not in {"missing", "blocked"} else "fail",
            "review_only": True,
            "detail": f"{record.get('path')} status={record.get('status')}",
        })
    gates.append({
        "gate": "retained_realized_outcomes",
        "status": "fail" if int(history.get("realized_outcome_count") or 0) == 0 else "partial",
        "review_only": True,
        "detail": f"realized_outcome_count={history.get('realized_outcome_count')}; owner_decision_count={history.get('owner_decision_count')}",
    })
    gates.append({
        "gate": "minimum_history_span",
        "status": "fail" if float(history.get("history_span_days") or 0) < 30 else "partial",
        "review_only": True,
        "detail": f"history_span_days={history.get('history_span_days')}; minimum review threshold is 30 days before calibration work is considered",
    })
    return gates


def build_report() -> dict[str, Any]:
    rows = load_jsonl(STATE_HISTORY)
    outcome_rows = load_jsonl(OUTCOME_UPDATES)
    history = state_history_summary(rows, outcome_rows)
    artifact_records = {key: artifact_status(path) for key, path in EVIDENCE_ARTIFACTS.items() if key != "state_history"}
    recommendation_summary = recommendation_tracking_summary()
    historical_summary = historical_regime_summary()
    realized_count = int(history.get("realized_outcome_count") or 0)
    verdict = "SAFE_WITH_GAPS" if rows and realized_count == 0 else "NOT_READY"
    if realized_count > 0 and float(history.get("history_span_days") or 0) >= 30:
        verdict = "SAFE_WITH_GAPS"
    if not rows:
        verdict = "NOT_READY"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "workflow": "WF55 - Probability Readiness and Outcome Retention Gate",
        "verdict": verdict,
        "consumer_posture": "review_only",
        "authority": {
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "watchlist_mutation_allowed": False,
            "watchlist_promotion_allowed": False,
            "sizing_allocation_recommendation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
            "owner_approval_inference_allowed": False,
            "model_driven_deployment_allowed": False,
            "model_ranked_deployment_allowed": False,
            "capital_action_allowed": False,
            "hard_false_authority_block": True,
        },
        "state_history_summary": history,
        "recommendation_tracking_summary": recommendation_summary,
        "historical_regime_analog_summary": historical_summary,
        "forecast_question_inventory": [
            {"id": "band_reclaim_retention", "question": "Did a written band interaction later retain or lose decision-grade state?", "ready": False, "missing": "retained realized outcome labels"},
            {"id": "stop_break_follow_through", "question": "Did a stop/invalidation break later repair or worsen?", "ready": False, "missing": "consistent post-event outcome labels"},
            {"id": "promotion_review_resolution", "question": "Did an owner-gated promotion review resolve as accepted, rejected, or deferred?", "ready": False, "missing": "owner decisions and later outcome tags"},
            {"id": "deployable_state_retention", "question": "Did a deployable or near-deployable state remain intact after the next review window?", "ready": False, "missing": "future outcome update flow"},
            {"id": "post_event_drift", "question": "Did a post-event setup improve, degrade, or stay unresolved?", "ready": False, "missing": "event-linked before/after labels"},
            {"id": "diversification_research_follow_through", "question": "Did a diversification research candidate improve enough to deserve manual promotion review?", "ready": False, "missing": "WF60/WF61 outcome retention"},
            {"id": "historical_regime_analog_base_rates", "question": "Which past regimes are relevant analog context for current macro and small/mid-cap broadening conditions?", "ready": True, "output": rel(HISTORICAL_REGIME_LIBRARY), "allowed_use": "base-rate and stress-context only"},
        ],
        "outcome_label_taxonomy": {
            "allowed_future_labels": sorted(ALLOWED_OUTCOME_LABELS),
            "known_at_time_required_fields": ["captured_at_utc", "window", "known_at_time", "source_artifacts"],
            "future_outcome_required_fields": ["row_type", "outcome_update_id", "linked_capture_run_id", "observed_at_utc", "recorded_at_utc", "ticker", "question_id", "outcome_label", "provenance"],
            "no_hindsight_rewrite_rule": "Known-at-time rows are append-only; future outcomes must be added to data/state-history/outcome-updates-v1.jsonl with later timestamps and provenance.",
        },
        "source_quality_gates": source_quality_gates(artifact_records, history),
        "probability_language_audit": {
            "validator": "scripts/probability_readiness_validator.py",
            "scope": "report plus live WF55/WF60/WF61/WF58 artifacts, including nested strings and authority fields",
            "status": "requires_validator_run",
        },
        "data_readiness_gaps": [
            "Retained outcome sidecar depth is below modeling thresholds; calibration and outcome-rate analysis remain blocked.",
            "Owner decisions are retained only when append-only outcome_update_v1 rows exist with provenance.",
            "History span is below the minimum review threshold for outcome analytics.",
            "WF60/WF61 diversification artifacts are context inputs only and do not create promotion or capital authority.",
            "Source-quality gates can describe freshness and staleness, but cannot convert sparse history into predictive readiness.",
            "Recommendation tracking now connects open recommendations and Monday paper-card follow-up, but it is still preview-only and does not make WF55 model-ready.",
            "Historical regime analogs are now available for base-rate and stress context, but they do not make WF55 model-ready or allow calibrated probability output.",
        ],
        "limits": [
            "This report is a methodology and guardrail object only.",
            "No predictive score, capital action, owner approval, portfolio mutation, account action, or execution authority is created.",
            "Borderline confidence and signal fields elsewhere must remain heuristic-only, uncalibrated, and non-predictive.",
        ],
        "evidence_artifacts": artifact_records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    history = report.get("state_history_summary") or {}
    tracking = report.get("recommendation_tracking_summary") or {}
    historical = report.get("historical_regime_analog_summary") or {}
    lines = [
        "# WF55 Probability Readiness Report",
        "",
        f"Generated: {report.get('generated_at_utc')}",
        f"Verdict: **{report.get('verdict')}**",
        "",
        "## Why this is not ready for modeling",
        f"- State-history rows: {history.get('row_count')}",
        f"- Realized outcomes retained: {history.get('realized_outcome_count')}",
        f"- Owner decisions retained: {history.get('owner_decision_count')}",
        f"- History span days: {history.get('history_span_days')}",
        f"- Recommendation tracking rows: {tracking.get('tracking_row_count')}",
        f"- Pending paper-card rows: {tracking.get('pending_paper_card_rows')}",
        f"- Historical analog events: {historical.get('event_count')}",
        f"- Small/large analog comparisons: {historical.get('small_large_comparison_available_count')}",
        "",
        "## Hard authority block",
        "Review support only. No portfolio mutation, owner approval, account action, capital action, or execution authority is created.",
        "",
        "## Main gaps",
    ]
    for gap in report.get("data_readiness_gaps") or []:
        lines.append(f"- {gap}")
    lines.append("")
    lines.append("## Next required work")
    lines.append("- Continue appending retained future-outcome sidecar rows with later timestamps and provenance before any predictive analytics work.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF55 read-only probability-readiness report.")
    parser.add_argument("--write", action="store_true", help="Write tmp/probability-readiness-report.json and .md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(DEFAULT_OUT, report, indent=2)
        DEFAULT_MD.write_text(render_markdown(report), encoding="utf-8", newline="\n")
        print(f"wrote {rel(DEFAULT_OUT)}")
        print(f"wrote {rel(DEFAULT_MD)}")
    print(json.dumps({
        "status": "ok",
        "verdict": report["verdict"],
        "state_history_rows": report["state_history_summary"]["row_count"],
        "realized_outcomes": report["state_history_summary"]["realized_outcome_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
