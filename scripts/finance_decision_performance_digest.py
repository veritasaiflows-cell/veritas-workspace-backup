#!/usr/bin/env python3
"""Build a finance decision performance digest from WF55 and WF87 evidence.

The digest is a review-only finance slice: it summarizes tracked
recommendations, forward checkpoints, WF87 shadow outcomes, and paper journal
status. It does not assign predictive skill, approve trades, mutate finance
canon, or grant paper/live execution authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
WF55_LEDGER = ROOT / "data" / "state-history" / "outcome-ledger-v2.jsonl"
WF87_JOURNAL = ROOT / "tmp" / "paper-autotrader" / "trade-decision-journal.jsonl"
WF87_SHADOW_SCORECARD = ROOT / "tmp" / "wf87-shadow-outcome-scorecard.json"
WF87_READINESS = ROOT / "tmp" / "wf87-v2-readiness-rollup.json"
OUT = ROOT / "tmp" / "finance-decision-performance-digest.json"
MD_OUT = ROOT / "tmp" / "finance-decision-performance-digest.md"

SCHEMA = "veritas.finance_decision_performance_digest.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "decision_performance_tracking_only": True,
    "predictive_skill_claim_allowed_now": False,
    "model_performance_claim_allowed_now": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}


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


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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


def summarize_wf55(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
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
    return {
        "source": rel(WF55_LEDGER),
        "row_count": len(clean),
        "parse_error_count": len(rows) - len(clean),
        "recommendation_tracking_rows": len(tracking),
        "tracked_tickers": tickers,
        "tracked_ticker_count": len(tickers),
        "forward_checkpoint_status_counts": dict(sorted(checkpoint_status_counts.items())),
        "due_checkpoint_counts_by_horizon": dict(sorted(horizon_due_counts.items())),
        "due_unobserved_checkpoint_count": due_unobserved,
        "observed_checkpoint_count": observed,
        "outcome_grade_assigned_count": sum(1 for row in tracking if as_dict(row.get("forward_scorecard")).get("outcome_grade_assigned") is True),
    }


def summarize_journal(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [row for row in rows if not row.get("_parse_error")]
    terminal = [row for row in clean if as_dict(row.get("outcome")).get("terminal") is True]
    tracked = [row for row in clean if as_dict(row.get("outcome")).get("tracked") is True]
    tickers = sorted({str(as_dict(row.get("decision")).get("ticker") or "").upper() for row in clean if as_dict(row.get("decision")).get("ticker")})
    status_counts: dict[str, int] = {}
    for row in clean:
        status = str(as_dict(row.get("outcome")).get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "source": rel(WF87_JOURNAL),
        "record_count": len(clean),
        "parse_error_count": len(rows) - len(clean),
        "tracked_order_outcome_count": len(tracked),
        "terminal_order_outcome_count": len(terminal),
        "outcome_status_counts": dict(sorted(status_counts.items())),
        "tickers": tickers,
        "ticker_count": len(tickers),
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
    if authority_true_paths(payload):
        errors.append("authority_drift_detected")
    wf55 = as_dict(payload.get("wf55_recommendation_outcomes"))
    shadow = as_dict(payload.get("wf87_shadow_outcomes"))
    if int(wf55.get("outcome_grade_assigned_count") or 0) == 0 and int(shadow.get("scoreable_decision_count") or 0) == 0:
        warnings.append("no_mature_performance_observations_yet")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": authority_true_paths(payload),
    }


def build_payload(paths: dict[str, Path], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    wf55_rows = load_jsonl(paths["wf55_ledger"])
    journal_rows = load_jsonl(paths["wf87_journal"])
    shadow_scorecard = as_dict(load_json(paths["wf87_shadow_scorecard"]))
    readiness = as_dict(load_json(paths["wf87_readiness"]))
    wf55_summary = summarize_wf55(wf55_rows, current)
    journal_summary = summarize_journal(journal_rows)
    shadow_summary = as_dict(shadow_scorecard.get("summary"))
    readiness_phase = as_dict(readiness.get("phase_readiness"))
    has_mature_observations = (
        int(wf55_summary.get("outcome_grade_assigned_count") or 0) > 0
        or int(shadow_summary.get("scoreable_decision_count") or 0) > 0
    )
    status = "ok" if has_mature_observations else "pending_mature_observations"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Daily finance slice for decision capture, forward checkpoints, WF87 shadow scoring, and journal outcomes.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "wf55_recommendation_outcomes": wf55_summary,
        "wf87_trade_decision_journal": journal_summary,
        "wf87_shadow_outcomes": {
            "source": rel(paths["wf87_shadow_scorecard"]),
            "status": shadow_scorecard.get("status"),
            "decision_count": shadow_summary.get("decision_count"),
            "scoreable_decision_count": shadow_summary.get("scoreable_decision_count"),
            "pending_regular_session_followup_count": shadow_summary.get("pending_regular_session_followup_count"),
            "would_buy_favorable_count": shadow_summary.get("would_buy_favorable_count"),
            "would_buy_adverse_count": shadow_summary.get("would_buy_adverse_count"),
            "decision_quality_claim_allowed_now": shadow_summary.get("decision_quality_claim_allowed_now"),
            "model_performance_claim_allowed_now": shadow_summary.get("model_performance_claim_allowed_now"),
        },
        "wf87_v2_readiness": {
            "source": rel(paths["wf87_readiness"]),
            "status": readiness.get("status"),
            "phase_a_hardening_components_installed": readiness_phase.get("phase_a_hardening_components_installed"),
            "phase_a_runtime_gates_clean": readiness_phase.get("phase_a_runtime_gates_clean"),
            "phase_b_assisted_round_trip_ready": readiness_phase.get("phase_b_assisted_round_trip_ready"),
            "phase_c_autonomous_paper_buy_ready": readiness_phase.get("phase_c_autonomous_paper_buy_ready"),
        },
        "performance_claim_status": {
            "mature_observations_present": has_mature_observations,
            "predictive_skill_claim_allowed_now": False,
            "reason": "Forward windows and shadow outcomes are still too sparse for a skill or win-rate claim." if not has_mature_observations else "Mature observations exist, but claims still require a separate policy gate.",
        },
        "next_safe_action": "Keep collecting decisions; score only after forward windows mature and source observations are present.",
        "stop_lines": [
            "Digest rows are not recommendation approval.",
            "No predictive skill, win-rate, expected-return, capital, paper/live execution, account, or owner approval inference.",
        ],
        "source_artifacts": {key: rel(path) for key, path in paths.items()},
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    wf55 = as_dict(payload.get("wf55_recommendation_outcomes"))
    journal = as_dict(payload.get("wf87_trade_decision_journal"))
    shadow = as_dict(payload.get("wf87_shadow_outcomes"))
    readiness = as_dict(payload.get("wf87_v2_readiness"))
    claim = as_dict(payload.get("performance_claim_status"))
    lines = [
        "# Finance Decision Performance Digest",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{as_dict(payload.get('validation')).get('status')}`",
        f"- WF55 recommendation rows: `{wf55.get('recommendation_tracking_rows')}` across `{wf55.get('tracked_ticker_count')}` tickers",
        f"- WF55 due unobserved checkpoints: `{wf55.get('due_unobserved_checkpoint_count')}`",
        f"- WF87 journal rows: `{journal.get('record_count')}`; terminal order outcomes: `{journal.get('terminal_order_outcome_count')}`",
        f"- WF87 shadow scoreable decisions: `{shadow.get('scoreable_decision_count')}`; pending follow-up: `{shadow.get('pending_regular_session_followup_count')}`",
        f"- WF87 readiness: `{readiness.get('status')}`; Phase C autonomous paper buy ready: `{readiness.get('phase_c_autonomous_paper_buy_ready')}`",
        f"- Predictive skill claim allowed now: `{claim.get('predictive_skill_claim_allowed_now')}`",
        "",
        "## Boundary",
        "",
        "Review-only tracking. No approval, execution, account, capital, canon, or predictive-performance authority.",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wf55-ledger", type=Path, default=WF55_LEDGER)
    parser.add_argument("--wf87-journal", type=Path, default=WF87_JOURNAL)
    parser.add_argument("--wf87-shadow-scorecard", type=Path, default=WF87_SHADOW_SCORECARD)
    parser.add_argument("--wf87-readiness", type=Path, default=WF87_READINESS)
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
        "wf55_ledger": abs_path(args.wf55_ledger),
        "wf87_journal": abs_path(args.wf87_journal),
        "wf87_shadow_scorecard": abs_path(args.wf87_shadow_scorecard),
        "wf87_readiness": abs_path(args.wf87_readiness),
    }
    payload = build_payload(paths)
    out = abs_path(args.out)
    md_out = abs_path(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload), encoding="utf-8")
    print(
        "status={status} validation={validation} wf55_rows={wf55} journal_rows={journal} shadow_scoreable={shadow} out={out}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            wf55=payload["wf55_recommendation_outcomes"]["recommendation_tracking_rows"],
            journal=payload["wf87_trade_decision_journal"]["record_count"],
            shadow=payload["wf87_shadow_outcomes"]["scoreable_decision_count"],
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
