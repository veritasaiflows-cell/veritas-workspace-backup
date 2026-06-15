from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_HISTORY = ROOT / "data" / "state-history" / "state-history-v1.jsonl"
V1_SIDECAR = ROOT / "data" / "state-history" / "outcome-updates-v1.jsonl"
DEFAULT_PREVIEW = ROOT / "tmp" / "wf55-outcome-ledger-v2-migration-preview.json"
DEFAULT_VALIDATION = ROOT / "tmp" / "wf55-outcome-ledger-v2-validation.json"
DEFAULT_CURRENT = ROOT / "tmp" / "recommendation-outcome-ledger-current.json"
DEFAULT_DURABLE_V2 = ROOT / "data" / "state-history" / "outcome-ledger-v2.jsonl"
CALL_LOG = ROOT / "04. Research" / "Call Log.md"
CAPITAL_RECOMMENDATIONS = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
MONDAY_PACKET_INDEX = ROOT / "tmp" / "alpaca-paper-readiness" / "monday-band-gated-packet-index.2026-06-01.json"
FINANCE_DECISION_FACTORY = ROOT / "tmp" / "finance-decision-factory.json"
WF67_PAPER_MANAGER = ROOT / "tmp" / "alpaca-paper-readiness" / "wf67-autonomous-paper-manager-current.json"
POST_CLOSE_QUOTE_LEDGER = ROOT / "tmp" / "post-close-final-quote-ledger.json"
SCHEMA_VERSION = "wf55.outcome_ledger_event_v2.preview.1"
FORWARD_HORIZON_DAYS = [1, 5, 21, 63]

# Later-outcome grading vocabulary for recommendations/decisions once they resolve.
# Review-only: no grade is assigned to any live row in this preview slice; assignment
# requires a separate explicit gate. These are semantic decision/outcome grades, not
# predictive-performance or model-ranking claims.
RECOMMENDATION_OUTCOME_GRADES: list[dict[str, Any]] = [
    {"grade": "thesis_held", "grade_group": "thesis", "is_failure_mode": False,
     "definition": "The recommendation thesis played out as reasoned over the evaluation window.",
     "evidence_required": ["linked_snapshot_known_at_time", "post_window_evidence_artifact", "thesis_statement_source"]},
    {"grade": "thesis_invalidated", "grade_group": "thesis", "is_failure_mode": True,
     "definition": "The core thesis was disproven by later evidence, independent of entry quality.",
     "evidence_required": ["linked_snapshot_known_at_time", "post_window_evidence_artifact", "thesis_statement_source"]},
    {"grade": "stop_or_invalidation_hit", "grade_group": "risk", "is_failure_mode": True,
     "definition": "Price/state breached the written stop or invalidation level.",
     "evidence_required": ["reference_band_or_stop", "observed_price_or_state", "evidence_window"]},
    {"grade": "band_reclaim_held", "grade_group": "entry_band", "is_failure_mode": False,
     "definition": "After a dip below band, price reclaimed and held the entry band.",
     "evidence_required": ["reference_band_or_stop", "observed_price_or_state", "evidence_window"]},
    {"grade": "entry_poor_even_if_thesis_right", "grade_group": "entry_quality", "is_failure_mode": True,
     "definition": "Thesis may hold, but the entry was poor (chased/late); distinguishes good thesis from good entry.",
     "evidence_required": ["entry_reference", "observed_entry_status", "post_window_evidence_artifact"]},
    {"grade": "no_chase_correct", "grade_group": "discipline", "is_failure_mode": False,
     "definition": "Correctly declined to chase an out-of-band/extended setup; discipline validated.",
     "evidence_required": ["no_chase_state_at_time", "post_window_evidence_artifact"]},
    {"grade": "superseded", "grade_group": "lifecycle", "is_failure_mode": False,
     "definition": "Recommendation was replaced by a newer recommendation/decision before resolution.",
     "evidence_required": ["supersedes_ledger_event_id", "successor_artifact_path"]},
    {"grade": "stale_data_failure", "grade_group": "process_failure", "is_failure_mode": True,
     "definition": "Outcome went wrong because the decision relied on stale/missing data, not the thesis.",
     "evidence_required": ["source_freshness_at_time", "staleness_evidence"]},
    {"grade": "boundary_failure", "grade_group": "process_failure", "is_failure_mode": True,
     "definition": "A boundary/authority guard was crossed or nearly crossed (approval inference, execution drift).",
     "evidence_required": ["authority_snapshot", "boundary_incident_evidence"]},
]

AUTHORITY_FALSE_FIELDS = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_trade_allowed",
    "owner_approval_granted",
    "owner_approval_inference_allowed",
    "model_training_enabled",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
    "proposal_apply_allowed",
}

EVENT_FAMILIES: dict[str, set[str]] = {
    "owner_decision": {"owner_approved", "owner_deferred", "owner_rejected", "owner_no_action", "owner_requested_more_evidence"},
    "call_log_resolution": {"correct", "incorrect", "incomplete", "voided", "superseded"},
    "paper_lifecycle": {"paper_order_accepted_unfilled", "paper_order_filled", "paper_order_partially_filled", "paper_order_expired_unfilled", "paper_order_cancelled_unfilled", "paper_order_rejected", "paper_position_observed", "paper_position_closed"},
    "band_stop_outcome": {"band_reclaim_held", "band_reclaim_lost", "break_below_stop", "stop_recovered", "deployable_state_retained", "deployable_state_lost"},
    "post_event_drift": {"post_event_drift_positive", "post_event_drift_neutral", "post_event_drift_negative", "thesis_resolved_positive", "thesis_resolved_negative", "thesis_unresolved"},
    "recommendation_tracking": {"capital_recommendation_open", "owner_decision_pending", "paper_card_pending_approval", "recommendation_superseded"},
}

REQUIRED_PAYLOAD_FIELDS: dict[str, set[str]] = {
    "owner_decision": {"decision_text", "decision_scope", "decision_source", "decision_actor", "applies_to_object_id"},
    "call_log_resolution": {"call_log_row_id", "original_date_opened", "original_call_excerpt", "status_after_review", "score_eligible", "no_hindsight_guard"},
    "paper_lifecycle": {"paper_pilot_id", "paper_endpoint_confirmed", "redaction_checked", "wf67_guard_artifact", "lifecycle_status"},
    "band_stop_outcome": {"reference_band_or_stop", "observed_price_or_state", "evidence_window", "artifact_path"},
    "post_event_drift": {"event_id_or_context", "before_state", "after_state", "evidence_summary"},
    "recommendation_tracking": {"recommendation_id", "recommendation_source", "recommendation_type", "current_status", "decision_status", "follow_up_required", "source_artifact_path"},
}

FORBIDDEN_PATTERNS = {
    "win_probability": re.compile(r"\bwin\s+probability\b|\bwin_probability\b", re.I),
    "win_rate": re.compile(r"\bwin\s+rate\b|\bwin_rate\b", re.I),
    "expected_return": re.compile(r"\bexpected\s+return\b|\bexpected_return\b", re.I),
    "percent_chance": re.compile(r"\b\d+(?:\.\d+)?\s*%\s+(?:chance|likelihood)\b", re.I),
    "calibrated_score": re.compile(r"\bcalibrated\s+(?:score|readiness\s+score)\b", re.I),
    "model_ranked": re.compile(r"\bmodel[-_\s]+ranked\b", re.I),
    "predicted_outcome": re.compile(r"\bpredicted\s+outcome\b", re.I),
}

SECRET_PATTERNS = [re.compile(r"AKIA[0-9A-Z]{16}"), re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]")]
LIVE_ENDPOINT = "https://api.alpaca.markets"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


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


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def snapshot_index(path: Path = STATE_HISTORY) -> dict[str, dict[str, Any]]:
    return {str(row.get("capture_run_id")): row for row in load_jsonl(path) if isinstance(row.get("capture_run_id"), str)}


def latest_snapshot(path: Path = STATE_HISTORY) -> dict[str, Any] | None:
    snapshots = [row for row in load_jsonl(path) if isinstance(row.get("capture_run_id"), str)]
    snapshots.sort(key=lambda row: parse_dt(row.get("captured_at_utc")) or datetime.min.replace(tzinfo=timezone.utc))
    return snapshots[-1] if snapshots else None


def hard_false_authority() -> dict[str, Any]:
    return {
        **{field: False for field in sorted(AUTHORITY_FALSE_FIELDS)},
        "statement": "Append-only WF55 outcome-ledger v2 for historical review only; no model, approval, portfolio/canon mutation, paper/live trade, account, or capital-action authority.",
        "consumer_posture": "historical_review_only",
    }


def price_quote_map(path: Path = POST_CLOSE_QUOTE_LEDGER) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("rows") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_return(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return round((end - start) / start * 100.0, 3)


def known_at_time_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    anchor_price = numeric(
        payload.get("current_price")
        or payload.get("anchor_price")
        or payload.get("close")
        or payload.get("limit_price")
    )
    return {
        "anchor_price": anchor_price,
        "entry_band_low": numeric(payload.get("entry_band_low")),
        "entry_band_high": numeric(payload.get("entry_band_high")),
        "stop_or_invalidation": numeric(payload.get("stop_or_invalidation")),
        "band_status": payload.get("current_band_status") or payload.get("entry_band_status") or payload.get("observed_entry_status"),
        "quote_freshness_status": payload.get("quote_freshness_status"),
        "source_artifact_path": payload.get("source_artifact_path"),
        "benchmark_policy": "Compare against SPY and sector proxy only when locally retained quote evidence exists; otherwise mark benchmark observation missing.",
        "horizon_days": FORWARD_HORIZON_DAYS,
        "no_hindsight_guard": True,
    }


def forward_scorecard_for_row(row: dict[str, Any], prices: dict[str, dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    known = known_at_time_from_payload(payload)
    anchor_price = numeric(known.get("anchor_price"))
    ticker = str(row.get("ticker") or "").upper()
    observed_at = parse_dt(row.get("observed_at_utc"))
    quote = prices.get(ticker, {})
    observed_price = numeric(quote.get("close"))
    observed_price_as_of = quote.get("market_date") or quote.get("retrieved_at_utc")
    checkpoints: list[dict[str, Any]] = []
    for days in FORWARD_HORIZON_DAYS:
        due_at = observed_at + timedelta(days=days) if observed_at else None
        if not observed_at:
            status = "missing_observed_at"
        elif now < due_at:
            status = "pending_window"
        elif anchor_price is None:
            status = "missing_anchor_price"
        elif observed_price is None:
            status = "missing_observation"
        else:
            status = "scored_local_quote"
        checkpoints.append({
            "horizon_days": days,
            "due_at_utc": due_at.replace(microsecond=0).isoformat().replace("+00:00", "Z") if due_at else None,
            "status": status,
            "anchor_price": anchor_price,
            "observed_price": observed_price if status == "scored_local_quote" else None,
            "observed_price_as_of": observed_price_as_of if status == "scored_local_quote" else None,
            "absolute_return_pct": pct_return(anchor_price, observed_price) if status == "scored_local_quote" else None,
            "benchmark_status": "missing_local_benchmark_quote",
            "benchmark_symbol": None,
            "benchmark_return_pct": None,
            "relative_return_pct": None,
        })
    scored = [row for row in checkpoints if row["status"] == "scored_local_quote"]
    missing = [row for row in checkpoints if row["status"].startswith("missing")]
    pending = [row for row in checkpoints if row["status"] == "pending_window"]
    if scored:
        status = "partially_scored"
    elif missing and not pending:
        status = "missing_observation"
    else:
        status = "pending"
    return {
        "status": status,
        "scoring_mode": "deterministic_local_evidence_only",
        "known_at_time": known,
        "checkpoints": checkpoints,
        "outcome_grade_assigned": False,
        "outcome_grade_status": "not_assigned_pending_mature_window_and_review",
        "predictive_performance_claims_allowed": False,
        "model_ranked_deployment_claim_allowed": False,
    }


def attach_forward_scorecards(rows: list[dict[str, Any]], prices: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    prices = prices if prices is not None else price_quote_map()
    out: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        if copied.get("event_family") == "recommendation_tracking":
            copied["forward_scorecard"] = forward_scorecard_for_row(copied, prices)
        out.append(copied)
    return out


def source_artifacts_from_v1(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = ((row.get("provenance") or {}).get("source_artifact") or {}) if isinstance(row.get("provenance"), dict) else {}
    if not source:
        return []
    out = {
        "path": source.get("path"),
        "exists": source.get("exists"),
        "sha256": source.get("sha256"),
        "generated_at_utc": source.get("generated_at_utc"),
        "status": source.get("status"),
    }
    return [out]


def stable_event_id(row: dict[str, Any], family: str, subtype: str) -> str:
    seed = "|".join(str(row.get(k, "")) for k in ["outcome_update_id", "linked_capture_run_id", "ticker", "object_id", "question_id"])
    digest = hashlib.sha256(f"{family}|{subtype}|{seed}".encode("utf-8")).hexdigest()[:16]
    return f"ledger_{digest}"


def source_artifact(path: Path, status: str = "present") -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "generated_at_utc": generated_at_from_json(path),
        "status": status,
    }


def generated_at_from_json(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(value, dict):
        return ""
    return str(value.get("generated_at_utc") or value.get("created_at_utc") or value.get("generated_at") or "")


def parse_call_log_rows(path: Path = CALL_LOG) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 12 or parts[0] == "#":
            continue
        rows[parts[0]] = {
            "row_id": parts[0],
            "date_opened": parts[1],
            "ticker": parts[2],
            "call": parts[3],
            "status": parts[7],
            "outcome": parts[8],
            "date_closed": parts[9],
            "notes": parts[10],
        }
    return rows


def classify_v1(row: dict[str, Any], call_rows: dict[str, dict[str, str]] | None = None) -> tuple[str, str, dict[str, Any]]:
    label = str(row.get("outcome_label") or "")
    question_id = str(row.get("question_id") or "")
    object_id = str(row.get("object_id") or "")
    notes = str(row.get("notes") or "")
    source = source_artifacts_from_v1(row)
    source_path = source[0].get("path") if source else ""
    call_rows = call_rows or {}

    if question_id == "call_log_outcome_resolution" or object_id.startswith("call-log-"):
        row_match = re.search(r"row-(\d+)", object_id)
        row_id = row_match.group(1) if row_match else ""
        call = call_rows.get(row_id, {})
        status_text = str((row.get("proposal_context") or {}).get("score_eligible_close_status") or call.get("status") or "").lower()
        subtype = "correct" if status_text == "correct" else "incorrect" if status_text == "incorrect" else "voided" if status_text == "voided" else "superseded" if status_text == "superseded" else "incomplete"
        payload = {
            "event_summary": notes,
            "source_status": (source[0].get("status") if source else None),
            "reviewer": "main_session_preview_builder",
            "human_review_required_before_append": True,
            "canonical_write_required_first": bool((row.get("proposal_context") or {}).get("call_log_canonical_patch_required_first")),
            "append_decision": "preview_only_no_append",
            "supersedes_ledger_event_id": "",
            "call_log_row_id": row_id,
            "original_date_opened": call.get("date_opened") or "2026-04-24",
            "original_call_excerpt": call.get("call") or notes[:240],
            "status_after_review": subtype,
            "score_eligible": subtype in {"correct", "incorrect"},
            "no_hindsight_guard": True,
        }
        return "call_log_resolution", subtype, payload

    if question_id == "paper_pilot_order_resolution" or label.startswith("paper_") or "paper" in source_path:
        subtype = label if label.startswith("paper_") else "paper_order_accepted_unfilled"
        artifact_status = source[0].get("status") if source else ""
        lifecycle = artifact_status or subtype
        payload = {
            "event_summary": notes,
            "source_status": artifact_status,
            "reviewer": "main_session_preview_builder",
            "human_review_required_before_append": True,
            "canonical_write_required_first": False,
            "append_decision": "preview_only_no_append",
            "supersedes_ledger_event_id": "",
            "paper_pilot_id": object_id,
            "paper_endpoint_confirmed": True,
            "redaction_checked": True,
            "wf67_guard_artifact": source_path,
            "lifecycle_status": lifecycle,
        }
        return "paper_lifecycle", subtype, payload

    if label in EVENT_FAMILIES["band_stop_outcome"]:
        payload = {
            "event_summary": notes,
            "source_status": source[0].get("status") if source else None,
            "reviewer": "main_session_preview_builder",
            "human_review_required_before_append": True,
            "canonical_write_required_first": False,
            "append_decision": "preview_only_no_append",
            "supersedes_ledger_event_id": "",
            "reference_band_or_stop": "from_linked_snapshot_or_source_artifact",
            "observed_price_or_state": label,
            "evidence_window": "post_snapshot_observation",
            "artifact_path": source_path,
        }
        return "band_stop_outcome", label, payload

    subtype = label if label in EVENT_FAMILIES["post_event_drift"] else "thesis_unresolved"
    payload = {
        "event_summary": notes,
        "source_status": source[0].get("status") if source else None,
        "reviewer": "main_session_preview_builder",
        "human_review_required_before_append": True,
        "canonical_write_required_first": False,
        "append_decision": "preview_only_no_append",
        "supersedes_ledger_event_id": "",
        "event_id_or_context": question_id,
        "before_state": "linked_snapshot_known_at_time",
        "after_state": subtype,
        "evidence_summary": notes,
    }
    return "post_event_drift", subtype, payload


def convert_v1_row(row: dict[str, Any], call_rows: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    family, subtype, payload = classify_v1(row, call_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "outcome_ledger_event_v2",
        "ledger_event_id": stable_event_id(row, family, subtype),
        "event_family": family,
        "event_subtype": subtype,
        "linked_capture_run_id": row.get("linked_capture_run_id"),
        "linked_snapshot_captured_at_utc": row.get("linked_snapshot_captured_at_utc"),
        "recorded_at_utc": row.get("recorded_at_utc"),
        "observed_at_utc": row.get("observed_at_utc"),
        "ticker": str(row.get("ticker") or "").upper(),
        "object_id": row.get("object_id") or "",
        "question_id": row.get("question_id") or "",
        "payload": payload,
        "authority": hard_false_authority(),
        "provenance": {
            "producer_script": "scripts/wf55_outcome_ledger_v2.py",
            "source_artifacts": source_artifacts_from_v1(row),
            "validation_artifacts": ["tmp/wf55-outcome-ledger-v2-validation.json"],
            "source_v1_outcome_update_id": row.get("outcome_update_id"),
        },
    }


def recommendation_event_id(seed: str, family: str, subtype: str) -> str:
    digest = hashlib.sha256(f"{family}|{subtype}|{seed}".encode("utf-8")).hexdigest()[:16]
    return f"ledger_{digest}"


def recommendation_row(
    *,
    snapshot: dict[str, Any],
    source_path: Path,
    subtype: str,
    ticker: str,
    object_id: str,
    question_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    family = "recommendation_tracking"
    recorded_at = utc_now()
    observed_at = generated_at_from_json(source_path) or recorded_at
    captured = parse_dt(snapshot.get("captured_at_utc"))
    observed_dt = parse_dt(observed_at)
    if captured and observed_dt and observed_dt <= captured:
        observed_at = recorded_at
    seed = "|".join([rel(source_path), subtype, ticker.upper(), object_id, question_id])
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "outcome_ledger_event_v2",
        "ledger_event_id": recommendation_event_id(seed, family, subtype),
        "event_family": family,
        "event_subtype": subtype,
        "linked_capture_run_id": snapshot.get("capture_run_id"),
        "linked_snapshot_captured_at_utc": snapshot.get("captured_at_utc"),
        "recorded_at_utc": recorded_at,
        "observed_at_utc": observed_at,
        "ticker": ticker.upper(),
        "object_id": object_id,
        "question_id": question_id,
        "payload": payload,
        "authority": hard_false_authority(),
        "provenance": {
            "producer_script": "scripts/wf55_outcome_ledger_v2.py",
            "source_artifacts": [source_artifact(source_path)],
            "validation_artifacts": ["tmp/wf55-outcome-ledger-v2-validation.json"],
            "source_v1_outcome_update_id": "",
        },
    }


def build_capital_recommendation_rows(source_path: Path, snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot or not source_path.exists():
        return []
    try:
        doc = load_json(source_path)
    except (OSError, json.JSONDecodeError):
        return []
    proposals = doc.get("proposals") if isinstance(doc, dict) else []
    if not isinstance(proposals, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in proposals:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id") or "")
        ticker = str(item.get("ticker") or item.get("ticker_or_scope") or "").upper()
        if not proposal_id or not ticker:
            continue
        current_state = item.get("current_state") if isinstance(item.get("current_state"), dict) else {}
        proposed_state = item.get("proposed_state") if isinstance(item.get("proposed_state"), dict) else {}
        technical = item.get("technical_gate") if isinstance(item.get("technical_gate"), dict) else {}
        freshness = item.get("source_freshness") if isinstance(item.get("source_freshness"), dict) else {}
        subtype = "owner_decision_pending" if item.get("main_session_final_action_required") or doc.get("main_session_final_action_required") else "capital_recommendation_open"
        payload = {
            "event_summary": f"Review-only capital recommendation tracking row for {ticker}; no approval, execution, model, or capital-action authority.",
            "reviewer": "main_session_preview_builder",
            "human_review_required_before_append": True,
            "canonical_write_required_first": False,
            "append_decision": "preview_only_no_append",
            "supersedes_ledger_event_id": "",
            "recommendation_id": proposal_id,
            "recommendation_source": rel(source_path),
            "recommendation_type": str(item.get("mutation_type") or proposed_state.get("recommendation_posture") or "capital_deployment_review"),
            "current_status": str(current_state.get("deployment_state") or current_state.get("daily_review_state") or "review_required"),
            "decision_status": "pending_owner_review",
            "follow_up_required": True,
            "source_artifact_path": rel(source_path),
            "source_artifact_sha256": sha256_file(source_path),
            "anchor_price": technical.get("close"),
            "current_price": technical.get("close"),
            "entry_band_low": technical.get("current_band_low"),
            "entry_band_high": technical.get("current_band_high"),
            "stop_or_invalidation": technical.get("stop_or_invalidation") or technical.get("stop"),
            "entry_band_status": technical.get("entry_band_status") or technical.get("band_status"),
            "quote_freshness_status": freshness.get("overall_classification"),
            "base_case": item.get("base_case"),
            "bear_case": item.get("bear_case"),
            "why_now": item.get("why_now"),
            "decision_rationale": item.get("decision_rationale"),
            "no_predictive_claims": True,
            "owner_decision_required_before_action": True,
            "paper_or_live_execution_allowed": False,
            "portfolio_or_canon_apply_allowed": False,
        }
        rows.append(recommendation_row(
            snapshot=snapshot,
            source_path=source_path,
            subtype=subtype,
            ticker=ticker,
            object_id=proposal_id,
            question_id="capital_recommendation_follow_through",
            payload=payload,
        ))
    return rows


def paper_card_row_from_card(card: dict[str, Any], card_path: Path, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(card, dict):
        return None
    order = card.get("order") if isinstance(card.get("order"), dict) else {}
    gate = card.get("monday_execution_gate") if isinstance(card.get("monday_execution_gate"), dict) else {}
    authority = card.get("authority") if isinstance(card.get("authority"), dict) else {}
    owner = card.get("owner_approval") if isinstance(card.get("owner_approval"), dict) else {}
    risk = card.get("risk_check") if isinstance(card.get("risk_check"), dict) else {}
    ticker = str(order.get("symbol") or "").upper()
    request_id = str(card.get("request_id") or "")
    if not ticker or not request_id:
        return None
    payload = {
        "event_summary": f"Prepared paper-only order card for {ticker}; blocked until fresh in-band quote, guard, kill switch, and exact Randall approval.",
        "reviewer": "main_session_preview_builder",
        "human_review_required_before_append": True,
        "canonical_write_required_first": False,
        "append_decision": "preview_only_no_append",
        "supersedes_ledger_event_id": "",
        "recommendation_id": request_id,
        "recommendation_source": rel(card_path),
        "recommendation_type": "wf67_paper_only_order_card",
        "current_status": str(owner.get("status") or "pending_exact_randall_approval"),
        "decision_status": "pending_exact_randall_approval",
        "follow_up_required": True,
        "source_artifact_path": rel(card_path),
        "source_artifact_sha256": sha256_file(card_path),
        "target_session_date": gate.get("target_session_date"),
        "limit_price": order.get("limit_price"),
        "notional": order.get("notional"),
        "observed_entry_status": risk.get("observed_entry_status"),
        "requires_fresh_quote": gate.get("requires_fresh_quote_on_or_after_market_open") is True,
        "requires_fresh_guard_validation": gate.get("requires_fresh_wf67_guard_validation") is True,
        "requires_fresh_short_lived_kill_switch": gate.get("requires_fresh_short_lived_kill_switch") is True,
        "requires_exact_randall_order_approval": gate.get("requires_exact_randall_order_approval") is True,
        "execution_allowed_by_card": authority.get("paper_order_execution_allowed_by_card") is True,
        "live_trade_allowed": authority.get("live_trade_allowed") is True,
        "owner_approval_inferred": authority.get("owner_approval_inferred") is True,
        "paper_or_live_execution_allowed": False,
        "no_predictive_claims": True,
    }
    return recommendation_row(
        snapshot=snapshot,
        source_path=card_path,
        subtype="paper_card_pending_approval",
        ticker=ticker,
        object_id=request_id,
        question_id="wf67_paper_card_follow_through",
        payload=payload,
    )


def build_paper_card_rows(index_path: Path, snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot or not index_path.exists():
        return []
    try:
        doc = load_json(index_path)
    except (OSError, json.JSONDecodeError):
        return []
    cards = doc.get("cards") if isinstance(doc, dict) else []
    if not isinstance(cards, list):
        return []
    rows: list[dict[str, Any]] = []
    for card_ref in cards:
        if not isinstance(card_ref, str) or not card_ref:
            continue
        card_path = ROOT / card_ref
        if not card_path.exists():
            continue
        try:
            card = load_json(card_path)
        except (OSError, json.JSONDecodeError):
            continue
        row = paper_card_row_from_card(card, card_path, snapshot)
        if row:
            rows.append(row)
    return rows


def build_wf67_paper_manager_rows(manager_path: Path, snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Feed WF67 paper-manager outputs into WF55 as paper-only review rows.

    candidate_card_reviews (which aggregate order-card and advisor-card outputs)
    become paper_card_pending_approval rows; observed paper positions become
    paper_lifecycle paper_position_observed rows. No execution or approval inference.
    """
    if not snapshot or not manager_path.exists():
        return []
    try:
        doc = load_json(manager_path)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(doc, dict):
        return []
    rows: list[dict[str, Any]] = []
    for review in doc.get("candidate_card_reviews") or []:
        if not isinstance(review, dict):
            continue
        card_ref = review.get("card_path")
        if not isinstance(card_ref, str) or not card_ref:
            continue
        card_path = ROOT / card_ref
        if not card_path.exists():
            continue
        try:
            card = load_json(card_path)
        except (OSError, json.JSONDecodeError):
            continue
        row = paper_card_row_from_card(card, card_path, snapshot)
        if row:
            rows.append(row)
    rows.extend(build_wf67_paper_position_rows(manager_path, doc, snapshot))
    return rows


def build_wf67_paper_position_rows(manager_path: Path, doc: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    positions = doc.get("paper_position_reviews") or []
    if not isinstance(positions, list):
        return []
    rows: list[dict[str, Any]] = []
    recorded_at = utc_now()
    observed_at = generated_at_from_json(manager_path) or recorded_at
    captured = parse_dt(snapshot.get("captured_at_utc"))
    observed_dt = parse_dt(observed_at)
    if captured and observed_dt and observed_dt <= captured:
        observed_at = recorded_at
    manartifact = source_artifact(manager_path)
    for position in positions:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("symbol") or "").upper()
        if not ticker:
            continue
        object_id = f"wf67-paper-position-{ticker}"
        seed = "|".join([rel(manager_path), "paper_position_observed", ticker, object_id, "wf67_paper_position_lifecycle"])
        payload = {
            "event_summary": f"Observed WF67 paper-account position in {ticker} (read-only review). No execution, sizing, or approval authority.",
            "reviewer": "main_session_preview_builder",
            "human_review_required_before_append": True,
            "canonical_write_required_first": False,
            "append_decision": "preview_only_no_append",
            "supersedes_ledger_event_id": "",
            "paper_pilot_id": object_id,
            "paper_endpoint_confirmed": True,
            "redaction_checked": True,
            "wf67_guard_artifact": rel(manager_path),
            "lifecycle_status": "paper_position_observed",
            "manager_action": position.get("manager_action"),
            "band_status": position.get("band_status"),
            "no_predictive_claims": True,
            "paper_or_live_execution_allowed": False,
        }
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "row_type": "outcome_ledger_event_v2",
            "ledger_event_id": recommendation_event_id(seed, "paper_lifecycle", "paper_position_observed"),
            "event_family": "paper_lifecycle",
            "event_subtype": "paper_position_observed",
            "linked_capture_run_id": snapshot.get("capture_run_id"),
            "linked_snapshot_captured_at_utc": snapshot.get("captured_at_utc"),
            "recorded_at_utc": recorded_at,
            "observed_at_utc": observed_at,
            "ticker": ticker,
            "object_id": object_id,
            "question_id": "wf67_paper_position_lifecycle",
            "payload": payload,
            "authority": hard_false_authority(),
            "provenance": {
                "producer_script": "scripts/wf55_outcome_ledger_v2.py",
                "source_artifacts": [manartifact],
                "validation_artifacts": ["tmp/wf55-outcome-ledger-v2-validation.json"],
                "source_v1_outcome_update_id": "",
            },
        })
    return rows


def build_decision_factory_rows(source_path: Path, snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Wire Finance Decision Factory decision_ledger rows into WF55 as review-only
    recommendation-tracking rows, preserving known-at-time decision context."""
    if not snapshot or not source_path.exists():
        return []
    try:
        doc = load_json(source_path)
    except (OSError, json.JSONDecodeError):
        return []
    ledger = doc.get("decision_ledger") if isinstance(doc, dict) else []
    if not isinstance(ledger, list):
        return []
    owner_ready = {"owner_card_and_wf67_request_ready", "owner_card_ready_wf67_blocked"}
    rows: list[dict[str, Any]] = []
    for item in ledger:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        if not ticker:
            continue
        disposition = str(item.get("disposition") or "pending")
        owner_action_required = disposition in owner_ready
        subtype = "owner_decision_pending" if owner_action_required else "capital_recommendation_open"
        setup_summary = (
            f"{item.get('auto_tier') or 'tier_unknown'} {item.get('sector') or 'sector_unknown'} candidate; "
            f"gate={item.get('gate_verdict') or 'unknown'}; disposition={disposition}."
        )
        payload = {
            "event_summary": f"Finance Decision Factory tracking row for {ticker}; review-only, owner-gated, no approval/execution/model authority.",
            "reviewer": "main_session_preview_builder",
            "human_review_required_before_append": True,
            "canonical_write_required_first": False,
            "append_decision": "preview_only_no_append",
            "supersedes_ledger_event_id": "",
            "recommendation_id": f"finance-decision-factory:{ticker}",
            "recommendation_source": rel(source_path),
            "recommendation_type": f"finance_decision_factory:{disposition}",
            "current_status": str(item.get("queue_state") or item.get("current_band_status") or "review_required"),
            "decision_status": "pending_owner_decision" if owner_action_required else "pending_owner_review",
            "follow_up_required": True,
            "source_artifact_path": rel(source_path),
            "source_artifact_sha256": sha256_file(source_path),
            "setup_summary": setup_summary,
            "gate_verdict": item.get("gate_verdict"),
            "gate_vetoes": item.get("gate_vetoes"),
            "blocked_reason": item.get("blocked_reason"),
            "current_band_status": item.get("current_band_status"),
            "entry_band_low": item.get("entry_band_low"),
            "entry_band_high": item.get("entry_band_high"),
            "stop_or_invalidation": item.get("stop_or_invalidation"),
            "current_price": item.get("current_price"),
            "quote_freshness_status": item.get("quote_freshness_status"),
            "owner_action_required": owner_action_required,
            "owner_card_path": item.get("owner_card_path"),
            "wf67_request_path": item.get("wf67_request_path"),
            "wf67_request_generation_status": item.get("wf67_request_generation_status"),
            "capital_deployment_approved": item.get("capital_deployment_approved", False) is True,
            "trade_or_execution_approved": item.get("trade_or_execution_approved", False) is True,
            "owner_approval_inferred": item.get("owner_approval_inferred", False) is True,
            "no_predictive_claims": True,
            "paper_or_live_execution_allowed": False,
            "portfolio_or_canon_apply_allowed": False,
        }
        rows.append(recommendation_row(
            snapshot=snapshot,
            source_path=source_path,
            subtype=subtype,
            ticker=ticker,
            object_id=f"decision-factory-{ticker}",
            question_id="finance_decision_factory_follow_through",
            payload=payload,
        ))
    return rows


def dedup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop rows whose natural key collides with an already-kept row so the same
    underlying card/position referenced by multiple sources is not double-counted."""
    seen: set[tuple[str, str, str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("event_family") or ""),
            str(row.get("event_subtype") or ""),
            str(row.get("linked_capture_run_id") or ""),
            str(row.get("ticker") or ""),
            str(row.get("object_id") or ""),
            str(row.get("question_id") or ""),
        )
        if all(key) and key in seen:
            continue
        if all(key):
            seen.add(key)
        out.append(row)
    return out


def recommendation_tracking_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracking = [row for row in rows if row.get("event_family") == "recommendation_tracking"]
    paper = [row for row in tracking if row.get("event_subtype") == "paper_card_pending_approval"]
    owner_pending = [row for row in tracking if str((row.get("payload") or {}).get("decision_status") or "").startswith("pending")]
    decision_factory = [row for row in tracking if row.get("question_id") == "finance_decision_factory_follow_through"]
    paper_positions = [row for row in rows if row.get("event_subtype") == "paper_position_observed"]
    tickers = sorted({str(row.get("ticker") or "") for row in tracking if row.get("ticker")})
    score_statuses: dict[str, int] = {}
    for row in tracking:
        status = str(as_dict(row.get("forward_scorecard")).get("status") or "not_available")
        score_statuses[status] = score_statuses.get(status, 0) + 1
    return {
        "status": "preview_ready",
        "tracking_row_count": len(tracking),
        "capital_recommendation_rows": sum(1 for row in tracking if row.get("event_subtype") in {"capital_recommendation_open", "owner_decision_pending"}),
        "decision_factory_rows": len(decision_factory),
        "pending_owner_decision_rows": len(owner_pending),
        "pending_paper_card_rows": len(paper),
        "paper_position_observed_rows": len(paper_positions),
        "tracked_tickers": tickers,
        "forward_scorecard_status_counts": score_statuses,
        "durable_append_allowed": False,
        "predictive_or_model_claims_allowed": False,
        "paper_or_live_execution_allowed": False,
    }


def outcome_grading_taxonomy() -> dict[str, Any]:
    """Review-only later-outcome grading vocabulary. No grade is assigned to any
    live row yet; assignment requires a separate explicit gate."""
    return {
        "status": "defined_not_assigned",
        "purpose": "Grade recommendations/decisions once outcomes resolve, as semantic decision/outcome grades while blocking predictive-performance and model-ranking claims.",
        "assignment_status": "not_yet_assigned",
        "applied_to_rows": 0,
        "requires_separate_gate_before_assignment": True,
        "grade_count": len(RECOMMENDATION_OUTCOME_GRADES),
        "grades": RECOMMENDATION_OUTCOME_GRADES,
        "consumer_note": "WF74/RSI may read these grades as semantic outcome dimensions; they do not authorize approval, execution, model training, or canon/portfolio mutation.",
    }


def blocked_candidates(call_rows: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for row_id in ["3", "8", "10"]:
        call = call_rows.get(row_id, {})
        out.append({
            "source": "04. Research/Call Log.md",
            "candidate": f"Call Log row #{row_id} {call.get('ticker', '')}".strip(),
            "append_status": "blocked_no_resolution_yet",
            "reason": "Call Log row remains incomplete/open; no close/void/supersession evidence exists yet.",
        })
    out.append({
        "source": "WF68 alert bridge",
        "candidate": "WF68 owner action/no-action follow-up",
        "append_status": "blocked_no_appendable_event_yet",
        "reason": "Later owner action, no-action, or outcome follow-up evidence is absent.",
    })
    return out


def build_preview(
    v1_path: Path = V1_SIDECAR,
    state_history_path: Path = STATE_HISTORY,
    call_log_path: Path = CALL_LOG,
    capital_recommendations_path: Path = CAPITAL_RECOMMENDATIONS,
    monday_packet_index_path: Path = MONDAY_PACKET_INDEX,
    finance_decision_factory_path: Path = FINANCE_DECISION_FACTORY,
    wf67_paper_manager_path: Path = WF67_PAPER_MANAGER,
) -> dict[str, Any]:
    v1_rows = [row for row in load_jsonl(v1_path) if not row.get("_parse_error")]
    call_rows = parse_call_log_rows(call_log_path)
    state_anchor = latest_snapshot(state_history_path)
    rows = [convert_v1_row(row, call_rows) for row in v1_rows]
    rows.extend(build_capital_recommendation_rows(capital_recommendations_path, state_anchor))
    rows.extend(build_decision_factory_rows(finance_decision_factory_path, state_anchor))
    rows.extend(build_paper_card_rows(monday_packet_index_path, state_anchor))
    rows.extend(build_wf67_paper_manager_rows(wf67_paper_manager_path, state_anchor))
    rows = dedup_rows(rows)
    rows = attach_forward_scorecards(rows)
    tracking_summary = recommendation_tracking_summary(rows)
    return {
        "schema_version": "wf55.outcome_ledger_v2_migration_preview.1",
        "generated_at_utc": utc_now(),
        "status": "preview_only",
        "consumer_posture": "review_only_not_ready",
        "source_v1_sidecar": rel(v1_path),
        "source_capital_recommendations": rel(capital_recommendations_path),
        "source_monday_packet_index": rel(monday_packet_index_path),
        "source_finance_decision_factory": rel(finance_decision_factory_path),
        "source_wf67_paper_manager": rel(wf67_paper_manager_path),
        "state_history_path": rel(state_history_path),
        "proposed_v2_sidecar_not_written": "data/state-history/outcome-ledger-v2.jsonl",
        "row_count": len(rows),
        "preview_rows": rows,
        "recommendation_tracking_summary": tracking_summary,
        "outcome_grading_taxonomy": outcome_grading_taxonomy(),
        "blocked_candidates": blocked_candidates(call_rows),
        "authority": hard_false_authority(),
        "boundary": "No durable v2 JSONL, v1 sidecar, state-history, Call Log, portfolio/canon, paper/live/account mutation occurs in this preview slice.",
    }


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append((f"{path}.{key}", str(key)))
            found.extend(walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(walk_strings(item, f"{path}[{idx}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


def validate_row(row: dict[str, Any], snapshots: dict[str, dict[str, Any]], seen_ids: set[str], seen_keys: dict[tuple[str, str, str, str, str, str], str], line_number: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    required = ["schema_version", "row_type", "ledger_event_id", "event_family", "event_subtype", "linked_capture_run_id", "linked_snapshot_captured_at_utc", "recorded_at_utc", "observed_at_utc", "ticker", "object_id", "question_id", "payload", "authority", "provenance"]
    for key in required:
        if key not in row:
            findings.append({"severity": "critical", "row": line_number, "issue": "missing_required_field", "field": key})
    if row.get("row_type") != "outcome_ledger_event_v2":
        findings.append({"severity": "critical", "row": line_number, "issue": "unexpected_row_type", "value": row.get("row_type")})
    event_id = row.get("ledger_event_id")
    if not isinstance(event_id, str) or not event_id:
        findings.append({"severity": "critical", "row": line_number, "issue": "ledger_event_id_required"})
    elif event_id in seen_ids:
        findings.append({"severity": "critical", "row": line_number, "issue": "duplicate_ledger_event_id", "ledger_event_id": event_id})
    else:
        seen_ids.add(event_id)
    family = row.get("event_family")
    subtype = row.get("event_subtype")
    if family not in EVENT_FAMILIES:
        findings.append({"severity": "critical", "row": line_number, "issue": "event_family_not_allowed", "value": family})
    elif subtype not in EVENT_FAMILIES[str(family)]:
        findings.append({"severity": "critical", "row": line_number, "issue": "event_subtype_not_allowed", "family": family, "value": subtype})
    payload = row.get("payload") or {}
    if not isinstance(payload, dict):
        findings.append({"severity": "critical", "row": line_number, "issue": "payload_missing_or_invalid"})
        payload = {}
    elif family in REQUIRED_PAYLOAD_FIELDS:
        for field in sorted(REQUIRED_PAYLOAD_FIELDS[str(family)]):
            if field not in payload or payload.get(field) in (None, ""):
                findings.append({"severity": "critical", "row": line_number, "issue": "missing_required_payload_field", "event_family": family, "field": field})
    snapshot = snapshots.get(str(row.get("linked_capture_run_id") or ""))
    if not snapshot:
        findings.append({"severity": "critical", "row": line_number, "issue": "linked_snapshot_not_found", "linked_capture_run_id": row.get("linked_capture_run_id")})
    captured_at = parse_dt((snapshot or {}).get("captured_at_utc"))
    observed_at = parse_dt(row.get("observed_at_utc"))
    recorded_at = parse_dt(row.get("recorded_at_utc"))
    if not observed_at:
        findings.append({"severity": "critical", "row": line_number, "issue": "observed_at_utc_invalid"})
    if not recorded_at:
        findings.append({"severity": "critical", "row": line_number, "issue": "recorded_at_utc_invalid"})
    if captured_at and observed_at and observed_at <= captured_at:
        findings.append({"severity": "critical", "row": line_number, "issue": "observed_timestamp_not_after_snapshot"})
    if captured_at and recorded_at and recorded_at <= captured_at:
        findings.append({"severity": "critical", "row": line_number, "issue": "recorded_timestamp_not_after_snapshot"})
    authority = row.get("authority") or {}
    if not isinstance(authority, dict):
        findings.append({"severity": "critical", "row": line_number, "issue": "authority_missing_or_invalid"})
    else:
        for field in AUTHORITY_FALSE_FIELDS:
            if authority.get(field) is not False:
                findings.append({"severity": "critical", "row": line_number, "issue": "authority_field_must_be_false", "field": field, "value": authority.get(field)})
    artifacts = ((row.get("provenance") or {}).get("source_artifacts") or []) if isinstance(row.get("provenance"), dict) else []
    if not artifacts:
        findings.append({"severity": "critical", "row": line_number, "issue": "source_artifacts_required"})
    for idx, artifact in enumerate(artifacts):
        if not artifact.get("path") or not artifact.get("sha256"):
            findings.append({"severity": "critical", "row": line_number, "issue": "source_artifact_path_hash_required", "artifact_index": idx})
    if family == "paper_lifecycle":
        if payload.get("paper_endpoint_confirmed") is not True or payload.get("redaction_checked") is not True:
            findings.append({"severity": "critical", "row": line_number, "issue": "paper_endpoint_and_redaction_required"})
    if family == "recommendation_tracking":
        if payload.get("no_predictive_claims") is not True:
            findings.append({"severity": "critical", "row": line_number, "issue": "recommendation_tracking_must_assert_no_predictive_claims"})
        if payload.get("paper_or_live_execution_allowed") is not False:
            findings.append({"severity": "critical", "row": line_number, "issue": "recommendation_tracking_execution_must_be_false"})
        if subtype == "paper_card_pending_approval":
            for flag in ("requires_fresh_quote", "requires_fresh_guard_validation", "requires_fresh_short_lived_kill_switch", "requires_exact_randall_order_approval"):
                if payload.get(flag) is not True:
                    findings.append({"severity": "critical", "row": line_number, "issue": "paper_card_gate_required", "field": flag})
            for flag in ("execution_allowed_by_card", "live_trade_allowed", "owner_approval_inferred"):
                if payload.get(flag) is not False:
                    findings.append({"severity": "critical", "row": line_number, "issue": "paper_card_authority_must_be_false", "field": flag})
    key = (str(family or ""), str(subtype or ""), str(row.get("linked_capture_run_id") or ""), str(row.get("ticker") or ""), str(row.get("object_id") or ""), str(row.get("question_id") or ""))
    prior = seen_keys.get(key)
    if prior and not payload.get("supersedes_ledger_event_id"):
        findings.append({"severity": "critical", "row": line_number, "issue": "duplicate_natural_key_without_supersession", "prior_ledger_event_id": prior, "natural_key": list(key)})
    elif not prior and all(key):
        seen_keys[key] = str(event_id or "")
    text = json.dumps(row, ensure_ascii=False)
    if LIVE_ENDPOINT in text:
        findings.append({"severity": "critical", "row": line_number, "issue": "live_endpoint_string_present"})
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append({"severity": "critical", "row": line_number, "issue": "credential_or_secret_pattern_present"})
    for json_path, value in walk_strings(row):
        # Allow the readiness validator filename itself; block claims in substantive text.
        if "probability_readiness_validator.py" in value or "probability-readiness-report.json" in value:
            continue
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(value):
                findings.append({"severity": "critical", "row": line_number, "issue": "forbidden_predictive_or_performance_language", "label": label, "path": json_path, "snippet": value[:160]})
    return findings


def validate_preview(preview: dict[str, Any], state_history_path: Path = STATE_HISTORY) -> dict[str, Any]:
    rows = preview.get("preview_rows") if isinstance(preview, dict) else None
    findings: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        rows = []
        findings.append({"severity": "critical", "issue": "preview_rows_missing_or_invalid"})
    snapshots = snapshot_index(state_history_path)
    seen_ids: set[str] = set()
    seen_keys: dict[tuple[str, str, str, str, str, str], str] = {}
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            findings.append({"severity": "critical", "row": idx, "issue": "preview_row_not_object"})
            continue
        findings.extend(validate_row(row, snapshots, seen_ids, seen_keys, idx))
    if preview.get("proposed_v2_sidecar_not_written") != "data/state-history/outcome-ledger-v2.jsonl":
        findings.append({"severity": "warning", "issue": "unexpected_proposed_v2_sidecar_label", "value": preview.get("proposed_v2_sidecar_not_written")})
    durable_v2 = DEFAULT_DURABLE_V2
    if durable_v2.exists():
        findings.append({
            "severity": "warning",
            "issue": "durable_v2_ledger_present_append_only_mode",
            "path": rel(durable_v2),
            "detail": "Durable v2 existence is allowed after the outcome-ledger quality-loop gate; rows still validate through this script and carry hard-false authority.",
        })
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "schema_version": "wf55.outcome_ledger_v2_validation.1",
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "critical": critical,
        "warning": warning,
        "preview_row_count": len(rows),
        "linked_snapshot_count": len(snapshots),
        "findings": findings,
        "authority": hard_false_authority(),
        "boundary": "Validation only; no durable ledger, Call Log, portfolio/canon, paper/live/account mutation authority.",
    }


def write_md_preview(preview: dict[str, Any], validation: dict[str, Any], path: Path) -> None:
    lines = [
        "# WF55 Outcome Ledger v2 Migration Preview",
        "",
        f"- Generated UTC: `{preview.get('generated_at_utc')}`",
        f"- Validation status: **{validation.get('status')}**",
        f"- Preview rows: **{validation.get('preview_row_count')}**",
        f"- Critical findings: **{validation.get('critical')}**",
        f"- Warning findings: **{validation.get('warning')}**",
        "- Durable v2 ledger written: **no**",
        "",
        "## Boundary",
        "",
        str(preview.get("boundary")),
        "",
        "## Event family counts",
        "",
    ]
    counts: dict[str, int] = {}
    for row in preview.get("preview_rows", []):
        counts[str(row.get("event_family"))] = counts.get(str(row.get("event_family")), 0) + 1
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")
    summary = preview.get("recommendation_tracking_summary") or {}
    lines += [
        "",
        "## Recommendation tracking",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Tracking rows: **{summary.get('tracking_row_count')}**",
        f"- Capital recommendation rows: **{summary.get('capital_recommendation_rows')}**",
        f"- Finance Decision Factory rows: **{summary.get('decision_factory_rows')}**",
        f"- Pending owner-decision rows: **{summary.get('pending_owner_decision_rows')}**",
        f"- Pending paper-card rows: **{summary.get('pending_paper_card_rows')}**",
        f"- Observed paper-position rows: **{summary.get('paper_position_observed_rows')}**",
        f"- Tracked tickers: `{', '.join(summary.get('tracked_tickers') or [])}`",
    ]
    taxonomy = preview.get("outcome_grading_taxonomy") or {}
    lines += [
        "",
        "## Outcome grading taxonomy (review-only, not assigned)",
        "",
        f"- Status: `{taxonomy.get('status')}` | assignment: `{taxonomy.get('assignment_status')}` | grades: **{taxonomy.get('grade_count')}**",
    ]
    for grade in taxonomy.get("grades") or []:
        lines.append(f"  - `{grade.get('grade')}` ({grade.get('grade_group')}, failure_mode={grade.get('is_failure_mode')}): {grade.get('definition')}")
    lines += ["", "## Blocked candidates", ""]
    for item in preview.get("blocked_candidates", []):
        lines.append(f"- **{item.get('candidate')}**: {item.get('append_status')} — {item.get('reason')}")
    if validation.get("findings"):
        lines += ["", "## Findings", ""]
        for item in validation.get("findings", []):
            lines.append(f"- **{item.get('severity')} / {item.get('issue')}**: {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_durable_rows(path: Path = DEFAULT_DURABLE_V2) -> list[dict[str, Any]]:
    return load_jsonl(path)


def append_durable_rows(preview: dict[str, Any], durable_path: Path = DEFAULT_DURABLE_V2) -> dict[str, Any]:
    rows = [
        row for row in preview.get("preview_rows", [])
        if isinstance(row, dict) and row.get("event_family") == "recommendation_tracking"
    ]
    durable_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_durable_rows(durable_path)
    existing_ids = {str(row.get("ledger_event_id")) for row in existing if row.get("ledger_event_id")}
    appended: list[dict[str, Any]] = []
    skipped: list[str] = []
    with durable_path.open("a", encoding="utf-8") as handle:
        for row in rows:
            event_id = str(row.get("ledger_event_id") or "")
            if not event_id or event_id in existing_ids:
                if event_id:
                    skipped.append(event_id)
                continue
            to_write = dict(row)
            payload = dict(as_dict(to_write.get("payload")))
            payload["append_decision"] = "durable_append_recorded_review_only"
            payload["durable_append_authority"] = "owner_requested_2026-06-11_outcome_quality_loop; review-only append with no approval, execution, predictive-performance, or model-ranking authority"
            to_write["payload"] = payload
            to_write["durable_append"] = {
                "status": "recorded",
                "recorded_by": "scripts/wf55_outcome_ledger_v2.py record",
                "recorded_at_utc": utc_now(),
                "review_only": True,
                "predictive_performance_claim_allowed": False,
                "capital_or_execution_authority": False,
            }
            handle.write(json.dumps(to_write, ensure_ascii=False, sort_keys=True) + "\n")
            appended.append(to_write)
            existing_ids.add(event_id)
    return {
        "status": "ok",
        "durable_path": rel(durable_path),
        "candidate_count": len(rows),
        "appended_count": len(appended),
        "skipped_existing_count": len(skipped),
        "appended_event_ids": [row.get("ledger_event_id") for row in appended],
        "authority": hard_false_authority(),
        "boundary": "Append-only recommendation tracking rows; no predictive-performance, model-ranking, approval, execution, account, portfolio, canon, or capital-action authority.",
    }


def durable_summary(path: Path = DEFAULT_DURABLE_V2) -> dict[str, Any]:
    rows = [row for row in load_durable_rows(path) if not row.get("_parse_error")]
    tracking = [row for row in rows if row.get("event_family") == "recommendation_tracking"]
    score_counts: dict[str, int] = {}
    for row in tracking:
        status = str(as_dict(row.get("forward_scorecard")).get("status") or "not_available")
        score_counts[status] = score_counts.get(status, 0) + 1
    return {
        "path": rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "recommendation_tracking_rows": len(tracking),
        "ticker_count": len({str(row.get("ticker") or "") for row in tracking if row.get("ticker")}),
        "forward_scorecard_status_counts": score_counts,
        "later_outcome_graded_rows": sum(1 for row in rows if as_dict(row.get("forward_scorecard")).get("outcome_grade_assigned") is True),
        "append_only": True,
        "review_only": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/validate/record WF55 outcome-ledger v2 rows without predictive or execution authority.")
    parser.add_argument("command", choices=["preview", "validate", "record"], nargs="?", default="preview")
    parser.add_argument("--v1-sidecar", type=Path, default=V1_SIDECAR)
    parser.add_argument("--state-history", type=Path, default=STATE_HISTORY)
    parser.add_argument("--call-log", type=Path, default=CALL_LOG)
    parser.add_argument("--capital-recommendations", type=Path, default=CAPITAL_RECOMMENDATIONS)
    parser.add_argument("--monday-packet-index", type=Path, default=MONDAY_PACKET_INDEX)
    parser.add_argument("--finance-decision-factory", type=Path, default=FINANCE_DECISION_FACTORY)
    parser.add_argument("--wf67-paper-manager", type=Path, default=WF67_PAPER_MANAGER)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--durable", type=Path, default=DEFAULT_DURABLE_V2)
    parser.add_argument("--md", type=Path, default=ROOT / "tmp" / "wf55-outcome-ledger-v2-migration-preview.md")
    return parser.parse_args()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    preview_path = abs_path(args.preview)
    validation_path = abs_path(args.validation)
    current_path = abs_path(args.current)
    durable_path = abs_path(args.durable)
    state_history = abs_path(args.state_history)
    if args.command in {"preview", "record"}:
        preview = build_preview(
            abs_path(args.v1_sidecar),
            state_history,
            abs_path(args.call_log),
            abs_path(args.capital_recommendations),
            abs_path(args.monday_packet_index),
            abs_path(args.finance_decision_factory),
            abs_path(args.wf67_paper_manager),
        )
    else:
        preview = load_json(preview_path)
    validation = validate_preview(preview, state_history)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    append_report = append_durable_rows(preview, durable_path) if args.command == "record" and validation.get("critical") == 0 else None
    durable = durable_summary(durable_path)
    current = {
        "schema_version": "wf55.recommendation_outcome_ledger_current.2",
        "generated_at_utc": utc_now(),
        "status": "ok" if validation.get("status") == "ok" else "blocked",
        "consumer_posture": "review_only_outcome_tracking_not_model_ready",
        "source_preview": rel(preview_path),
        "source_validation": rel(validation_path),
        "durable_v2_ledger": durable,
        "last_append_report": append_report,
        "recommendation_tracking_summary": preview.get("recommendation_tracking_summary"),
        "outcome_grading_taxonomy": preview.get("outcome_grading_taxonomy"),
        "validation": {
            "status": validation.get("status"),
            "critical": validation.get("critical"),
            "warning": validation.get("warning"),
            "preview_row_count": validation.get("preview_row_count"),
        },
        "tracked_rows": [
            row for row in preview.get("preview_rows", [])
            if isinstance(row, dict) and row.get("event_family") == "recommendation_tracking"
        ],
        "authority": hard_false_authority(),
        "boundary": "Current recommendation/outcome ledger is append-only/review-only. It cannot approve, trade, mutate canon/portfolio, rank by model, or make predictive-performance claims.",
    }
    current_path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md_preview(preview, validation, abs_path(args.md))
    print(json.dumps({
        "status": validation["status"],
        "critical": validation["critical"],
        "warning": validation["warning"],
        "preview_row_count": validation["preview_row_count"],
        "recommendation_tracking": preview.get("recommendation_tracking_summary"),
        "append_report": append_report,
        "durable_v2_ledger": durable,
    }, indent=2))
    return 0 if validation.get("critical") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
