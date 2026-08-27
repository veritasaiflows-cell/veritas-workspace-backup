from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_DIR = TMP / "portfolio-mutation-proposals"
OUT_PATH = OUT_DIR / "current-capital-deployment-recommendations.json"
WF78_CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
SCHEMA_VERSION = 1
SUPPORTED_WINDOWS = {"morning", "post-close", "post-earnings", "sunday"}
AUTHORITY_FLAGS = {
    "owner_decision_required": True,
    "owner_approval_granted": False,
    "apply_allowed": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "trade_or_account_action_allowed": False,
    "main_session_final_action_required": True,
}
TOP_LEVEL_AUTHORITY = {
    "review_packet_generation_allowed": True,
    "approved_scope": "main-session standing approval for bounded workspace portfolio note/model/canon maintenance under WF58/WF56 guardrails",
    "gated_portfolio_note_model_mutation_allowed": True,
    "canonical_note_mutation_allowed": True,
    "portfolio_mutation_allowed": True,
    "owner_approval_granted": True,
    "apply_allowed": False,
    "proposal_apply_allowed": False,
    "per_packet_owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "trade_execution_allowed": False,
    "main_session_final_action_required": True,
    "blocked_scope": "live trade/account actions, brokerage orders, money movement, and unscoped execution entitlement remain blocked; paper submit/cancel is separate WF63/WF67 guarded authority",
}
REQUIRED_UNRESOLVED_OFFICIAL_FIELDS = {
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
}
FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"\bbuy\b", re.IGNORECASE),
    re.compile(r"\bsell\b", re.IGNORECASE),
    re.compile(r"\btrim\b", re.IGNORECASE),
    re.compile(r"\bexecute\b", re.IGNORECASE),
    re.compile(r"\bexecution\b", re.IGNORECASE),
    re.compile(r"\btrade\b", re.IGNORECASE),
    re.compile(r"owner[-\s]+approved", re.IGNORECASE),
    re.compile(r"approval\s+granted", re.IGNORECASE),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate review-only capital-deployment proposal packets tied to entry-band state.",
    )
    parser.add_argument("--window", default="post-close", choices=sorted(SUPPORTED_WINDOWS))
    parser.add_argument("--write", action="store_true", help="Write tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE)).replace("\\", "/")


def load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    data = load_json_artifact(path)
    if data is None:
        if required:
            raise FileNotFoundError(path)
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return data


def index_by_ticker(items: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        if ticker:
            out[ticker] = item
    return out


def clean_text(text: Any, fallback: str = "Manual owner review required.") -> str:
    value = str(text or "").strip()
    if not value:
        value = fallback
    for pattern in FORBIDDEN_VALUE_PATTERNS:
        value = pattern.sub("owner-gated action", value)
    return value


def source_freshness(daily: dict[str, Any]) -> dict[str, Any]:
    raw = daily.get("source_freshness") or {}
    classification = raw.get("overall_classification") or "unknown"
    trust = raw.get("trust_level") or "unknown"
    review_required = classification not in {"fresh", "current"} or trust not in {"clean", "current"}
    return {
        "overall_classification": classification,
        "trust_level": trust,
        "owner_review_required": True,
        "explicit_blocker": bool(raw.get("stop_line") or review_required),
        "capital_action_allowed": False,
    }


def risk_rule_check() -> dict[str, Any]:
    return {
        "status": "review_required",
        "references": [
            "25% sector cap",
            "15% normal single-name ceiling",
            "speculative sleeve cap",
            "catalyst-window exception",
        ],
        "review_boundary": "Risk context only; no size, cash, sleeve, or account action is authorized by this packet.",
    }


def concentration_check(rec: dict[str, Any]) -> dict[str, Any]:
    envelope = rec.get("sizing_risk_envelope") or {}
    thresholds = envelope.get("risk_thresholds") or {}
    return {
        "status": "review_required",
        "ticker": rec.get("ticker"),
        "single_name_after_pct": None,
        "max_single_name_after_pct": None,
        "sector_after_pct": None,
        "normal_single_name_ceiling_pct": thresholds.get("max_single_position_normal_pct"),
        "sector_cap_pct": thresholds.get("max_sector_pct"),
        "written_exception": False,
        "note": "No pro-forma exposure change is proposed; owner must review concentration before any action.",
    }


def live_distance_to_current_band_pct(band_proposal: dict[str, Any], deployment_record: dict[str, Any]) -> float | None:
    raw_distance = band_proposal.get("distance_to_band_pct")
    if raw_distance is not None:
        return raw_distance
    close = deployment_record.get("close") or band_proposal.get("close")
    low = band_proposal.get("current_band_low")
    high = band_proposal.get("current_band_high")
    try:
        close_f = float(close)
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return None
    if low_f <= close_f <= high_f:
        midpoint = (low_f + high_f) / 2
        return round(((close_f - midpoint) / midpoint) * 100, 2) if midpoint else None
    if close_f > high_f:
        return round(((close_f - high_f) / high_f) * 100, 2) if high_f else None
    return round(((close_f - low_f) / low_f) * 100, 2) if low_f else None


def live_band_status(band_proposal: dict[str, Any], deployment_record: dict[str, Any], fallback: Any) -> str | None:
    close = deployment_record.get("close") or band_proposal.get("close")
    low = band_proposal.get("current_band_low")
    high = band_proposal.get("current_band_high")
    try:
        close_f = float(close)
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return str(fallback) if fallback else None
    if close_f > high_f:
        return "ABOVE_BAND_WAIT"
    if close_f < low_f:
        return "BELOW_BAND_WAIT"
    return "IN_BAND"


def band_proposal_reference_overlay(band_proposal: dict[str, Any]) -> dict[str, Any]:
    overlay = dict(band_proposal)
    use_suggested = band_proposal.get("canonical_apply_eligible") is True
    if not use_suggested:
        return overlay
    overlay["current_band_low"] = band_proposal.get("suggested_band_low")
    overlay["current_band_high"] = band_proposal.get("suggested_band_high")
    overlay["stop_or_invalidation"] = band_proposal.get("suggested_stop")
    overlay["band_source"] = "sql_first_band_proposal"
    overlay["distance_to_band_pct"] = None
    overlay["raw_band_proposal"] = {
        "current_band_low": band_proposal.get("current_band_low"),
        "current_band_high": band_proposal.get("current_band_high"),
        "current_stop": band_proposal.get("current_stop"),
        "suggested_band_low": band_proposal.get("suggested_band_low"),
        "suggested_band_high": band_proposal.get("suggested_band_high"),
        "suggested_stop": band_proposal.get("suggested_stop"),
        "band_status": band_proposal.get("band_status"),
        "distance_to_band_pct": band_proposal.get("distance_to_band_pct"),
        "source_priority": "sql_first_band_proposal",
    }
    return overlay


def capital_review_band_overlay(band_proposal: dict[str, Any], capital_queue_row: dict[str, Any]) -> dict[str, Any]:
    band_proposal = band_proposal_reference_overlay(band_proposal)
    written = capital_queue_row.get("written_band") if isinstance(capital_queue_row.get("written_band"), dict) else {}
    if not written:
        return band_proposal
    overlay = dict(band_proposal)
    overlay["current_band_low"] = written.get("entry_band_low")
    overlay["current_band_high"] = written.get("entry_band_high")
    overlay["stop_or_invalidation"] = written.get("stop_or_invalidation")
    overlay["band_status"] = capital_queue_row.get("current_band_status") or written.get("current_band_status") or band_proposal.get("band_status")
    overlay["band_source"] = "wf78_capital_review_queue"
    overlay["raw_band_proposal"] = {
        "current_band_low": band_proposal.get("current_band_low"),
        "current_band_high": band_proposal.get("current_band_high"),
        "band_status": band_proposal.get("band_status"),
        "distance_to_band_pct": band_proposal.get("distance_to_band_pct"),
    }
    return overlay


def band_stop_or_invalidation(band: dict[str, Any]) -> Any:
    for key in ("stop_or_invalidation", "current_stop", "stop", "suggested_stop"):
        value = band.get(key)
        if value is not None:
            return value
    return None


def technical_gate(rec: dict[str, Any], band_proposal: dict[str, Any], deployment_record: dict[str, Any], capital_queue_row: dict[str, Any] | None = None) -> dict[str, Any]:
    effective_band = capital_review_band_overlay(band_proposal, capital_queue_row or {})
    entry_status = live_band_status(effective_band, deployment_record, rec.get("entry_band_status") or band_proposal.get("band_status"))
    raw_status = effective_band.get("band_status")
    return {
        "status": "review_required" if rec.get("recommended_action") != "deploy_candidate" else "candidate_review",
        "entry_band_status": entry_status,
        "band_status": entry_status,
        "proposal_band_status": rec.get("proposal_band_status"),
        "raw_band_status": raw_status,
        "band_status_note": rec.get("band_status_note"),
        "distance_to_band_pct": live_distance_to_current_band_pct(effective_band, deployment_record),
        "close": deployment_record.get("close"),
        "current_band_low": effective_band.get("current_band_low"),
        "current_band_high": effective_band.get("current_band_high"),
        "stop_or_invalidation": band_stop_or_invalidation(effective_band),
        "band_source": effective_band.get("band_source") or "band_proposals",
        "raw_band_proposal": effective_band.get("raw_band_proposal"),
        "in_entry_band": deployment_record.get("in_entry_band"),
        "below_stop": deployment_record.get("below_stop"),
        "stop_line": "Do not treat in-band status as approval, sizing, or account-action authority.",
    }


def catalyst_gate(rec: dict[str, Any], band_proposal: dict[str, Any]) -> dict[str, Any]:
    blocked = [str(item) for item in rec.get("blocked_reasons") or [] if str(item).strip()]
    return {
        "status": "review_required" if blocked else "manual_review_required",
        "days_to_earnings": band_proposal.get("days_to_earnings"),
        "earnings_state": band_proposal.get("earnings_state"),
        "blockers": blocked[:5],
    }


def official_earnings_gate(rec: dict[str, Any]) -> dict[str, Any]:
    bridge = rec.get("official_earnings_bridge") or {}
    if not isinstance(bridge, dict):
        bridge = {}
    return {
        "status": bridge.get("status") or "missing_manual_review_required",
        "manual_review_required": bridge.get("manual_review_required") is not False,
        "capital_action_allowed": False,
        "deployment_authority_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "summary": clean_text(bridge.get("summary"), "Official earnings bridge requires manual review."),
    }


def compact_official_earnings_bridge(rec: dict[str, Any]) -> dict[str, Any]:
    bridge = rec.get("official_earnings_bridge") or {}
    if not isinstance(bridge, dict):
        bridge = {}
    source_urls = bridge.get("source_urls") if isinstance(bridge.get("source_urls"), dict) else {}
    source_freshness = bridge.get("source_freshness") if isinstance(bridge.get("source_freshness"), dict) else {}
    evidence_claims = bridge.get("evidence_claims") if isinstance(bridge.get("evidence_claims"), list) else []
    unresolved = bridge.get("unresolved_official_fields") if isinstance(bridge.get("unresolved_official_fields"), list) else []
    official_status = bridge.get("official_evidence_status") or "manual_required"
    if official_status == "manual_required" and not unresolved:
        unresolved = sorted(REQUIRED_UNRESOLVED_OFFICIAL_FIELDS)
    return {
        "status": bridge.get("status") or "missing_manual_review_required",
        "source_artifact": bridge.get("source_artifact") or "tmp/fundamental-ir-reconciliation-packets.json",
        "period_end": bridge.get("period_end"),
        "source_urls": source_urls,
        "official_evidence_status": official_status,
        "official_evidence_posture": bridge.get("official_evidence_posture") or "review_only",
        "source_authority_level": bridge.get("source_authority_level") or "official_company_ir_metadata_only",
        "source_freshness": source_freshness,
        "evidence_claims": evidence_claims,
        "unresolved_official_fields": unresolved,
        "bank_native_metrics": bridge.get("bank_native_metrics") if isinstance(bridge.get("bank_native_metrics"), dict) else None,
        "sec_reconciliation_status": bridge.get("sec_reconciliation_status"),
        "adjusted_eps_status": bridge.get("adjusted_eps_status") or "manual_required",
        "guidance_status": bridge.get("guidance_status") or "manual_required",
        "manual_review_required": bridge.get("manual_review_required") is not False,
        "blockers": bridge.get("blockers") or [],
        "summary": clean_text(bridge.get("summary"), "Official earnings bridge is review-only and manual-required where unresolved."),
        "capital_action_allowed": False,
        "deployment_authority_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }


def lane_tuple(rec: dict[str, Any], config_meta: dict[str, Any], deployment_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": rec.get("ticker"),
        "workflow_state": legacy_state(config_meta, "workflow_state") or legacy_state(deployment_record, "action_state") or rec.get("current_state"),
        "coverage_lane": clean_text(config_meta.get("coverage_lane"), "manual review lane"),
        "entry_policy": clean_text(config_meta.get("entry_policy"), "manual entry-policy review"),
        "recommendation_action": rec.get("recommendation_action"),
        "review_state": "owner_review_required",
    }


def proposal_for(
    rec: dict[str, Any],
    *,
    window: str,
    generated_at: str,
    daily: dict[str, Any],
    config: dict[str, Any],
    config_meta: dict[str, Any],
    band_proposal: dict[str, Any],
    deployment_record: dict[str, Any],
    capital_queue_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ticker = str(rec.get("ticker") or "").upper()
    current_tuple = lane_tuple(rec, config_meta, deployment_record)
    proposed_tuple = dict(current_tuple)
    proposed_tuple["review_state"] = "review_packet_only_no_state_change"
    bridge = compact_official_earnings_bridge(rec)
    technical = technical_gate(rec, band_proposal, deployment_record, capital_queue_row or {})
    action = str(rec.get("recommended_action") or "review_required")
    if bridge.get("official_evidence_status") == "manual_required" and technical.get("entry_band_status") == "IN_BAND":
        action = "manual_evidence_review_required"
    elif action == "wait_for_band" and technical.get("entry_band_status") == "IN_BAND":
        action = "owner_gated_band_review"
    proposed_tuple["recommendation_posture"] = action
    incoming_why = rec.get("why_stack") or rec.get("decision_rationale") or {}
    if not isinstance(incoming_why, dict):
        incoming_why = {}
    why_now = clean_text(
        incoming_why.get("setup_reason")
        or f"{ticker} surfaced from {window} capital-review output with entry-band status {rec.get('entry_band_status') or 'unknown'} and action family {rec.get('recommendation_action') or 'review'}.",
    )
    why_stack = {
        "setup_reason": clean_text(incoming_why.get("setup_reason"), why_now),
        "entry_reason": clean_text(incoming_why.get("entry_reason"), f"Entry-band status: {rec.get('entry_band_status') or 'unknown'}; owner review required."),
        "fundamental_reason": clean_text(incoming_why.get("fundamental_reason"), "WF65 fundamental context requires manual review."),
        "official_earnings_reason": clean_text(incoming_why.get("official_earnings_reason"), "Official earnings bridge remains manual-required/review-only where unresolved."),
        "sector_macro_reason": clean_text(incoming_why.get("sector_macro_reason"), "Sector/macro context requires review."),
        "risk_blocker_reason": clean_text(incoming_why.get("risk_blocker_reason"), "Risk, stop, catalyst, and concentration blockers require owner review."),
        "missing_evidence_reason": clean_text(incoming_why.get("missing_evidence_reason"), "; ".join(str(x) for x in rec.get("missing_evidence") or []) or "Missing-evidence review required."),
        "authority_boundary": "Review-only packet rationale; standing main-session workspace canon/portfolio maintenance authority is recognized, but this individual packet does not self-apply and grants no external financial, account, cash, live-order, or unguarded paper-submit authority.",
    }
    evidence = [
        clean_text(f"Daily review object action family: {rec.get('recommendation_action') or 'review'}"),
        clean_text(f"Entry-band status: {rec.get('entry_band_status') or 'unknown'}"),
        clean_text(f"Deployment state: {legacy_state(deployment_record, "action_state") or rec.get('current_state') or 'unknown'}"),
        clean_text(f"Band proposal status: {band_proposal.get('band_status') or 'unknown'}"),
    ]
    evidence.append(clean_text(
        f"Official earnings bridge: {bridge.get('status')}; SEC reconciliation: {bridge.get('sec_reconciliation_status') or 'unknown'}; adjusted EPS/guidance remain manual where unresolved.",
    ))
    stop_lines = [
        "Owner decision required before any portfolio state changes.",
        "No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.",
    ]
    if deployment_record.get("below_stop") is True:
        stop_lines.append("Below-stop condition blocks capital review until manually resolved.")
    if rec.get("blocked_reasons"):
        stop_lines.append("Recommendation has unresolved blockers or missing evidence.")

    portfolio = config.get("portfolio") if isinstance(config.get("portfolio"), dict) else {}
    current_cash = portfolio.get("cash")

    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "proposal_id": f"{window}:{ticker}:capital-deployment-review:{generated_at[:10]}",
        "mutation_type": "ticker_lane_change",
        "ticker_or_scope": ticker,
        "current_state": {
            "source_window": window,
            "daily_review_state": rec.get("current_state"),
            "deployment_state": legacy_state(deployment_record, "action_state"),
            "band_status": rec.get("entry_band_status") or band_proposal.get("band_status"),
            "proposal_band_status": rec.get("proposal_band_status"),
            "raw_band_status": band_proposal.get("band_status"),
            "band_status_note": rec.get("band_status_note"),
        },
        "proposed_state": {
            "recommendation_posture": action,
            "state_change_requested": False,
            "review_packet_only": True,
        },
        "why_now": why_now,
        "why_stack": why_stack,
        "decision_rationale": why_stack,
        "evidence": evidence,
        "source_freshness": source_freshness(daily),
        "base_case": clean_text(f"Base case: {ticker} remains review-worthy only if thesis, macro fit, written entry band, stop/invalidation, and catalyst gates are manually confirmed."),
        "bear_case": clean_text(f"Bear case: defer or reject {ticker} if price violates stop/invalidation, catalyst risk worsens, macro fit deteriorates, or evidence remains incomplete."),
        "risk_rule_check": risk_rule_check(),
        "concentration_check": concentration_check(rec),
        "technical_gate": technical,
        "disciplined_extension_gate": rec.get("disciplined_extension_gate"),
        "disciplined_staleness_alert": rec.get("disciplined_staleness_alert"),
        "catalyst_gate": catalyst_gate(rec, band_proposal),
        "official_earnings_gate": official_earnings_gate(rec),
        "official_earnings_bridge": bridge,
        "proposed_files_to_edit": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json"],
        "rollback_or_reversal_note": "Delete or ignore this generated packet; it has no apply path and changes no canonical state.",
        "stop_lines_triggered": stop_lines,
        **AUTHORITY_FLAGS,
        "ticker": ticker,
        "current_lane_status_tuple": current_tuple,
        "proposed_lane_status_tuple": proposed_tuple,
        "thesis_gate": {"status": "manual_review_required", "summary": clean_text(rec.get("thesis"), "Manual thesis review required.")},
        "macro_regime_gate": {"status": "review_required", "summary": clean_text(rec.get("macro_regime_check"), "Macro fit requires review.")},
        "risk_sizing_gate": {"status": "review_required", "summary": clean_text((rec.get("sizing_risk_envelope") or {}).get("review_boundary"))},
        "sector_correlation_artifact": {
            "status": clean_text(rec.get("sector_correlation_check") or (rec.get("sector_context") or {}).get("status"), "manual_review_required"),
            "fresh_artifacts": (rec.get("sector_context") or {}).get("fresh_artifacts") or [],
            "summary": "Sector/correlation context is review-only and does not grant authority.",
        },
        "owner_conflict_check": {"status": "review_required", "summary": "Check owner notes before any state change."},
        "promotion_review_queue": {"status": "review_only", "recommended_action": action},
        "current_portfolio_model": "unchanged",
        "proposed_portfolio_model": "unchanged",
        "current_cash_target_pct": current_cash,
        "proposed_cash_target_pct": current_cash,
        "sleeve_deltas": [],
        "sector_exposure_before_after": [],
        "correlated_sleeve_exposure_before_after": [],
    }
    return packet


def build_payload(window: str) -> dict[str, Any]:
    daily_path = TMP / f"daily-review-objects-{window}.json"
    daily = load_json(daily_path)
    config = load_json(TMP / "portfolio-config.json", required=False)
    band = load_json(TMP / "band-proposals.json", required=False)
    deployment = load_json(TMP / "deployment-check.json", required=False)
    capital_queue = load_json(WF78_CAPITAL_QUEUE, required=False)

    tracked = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}
    band_by_ticker = index_by_ticker(band.get("proposals") or [])
    deployment_by_ticker = index_by_ticker(deployment.get("records") or [])
    capital_queue_by_ticker = index_by_ticker(capital_queue.get("rows") or [])
    generated_at = utc_now()
    proposals: list[dict[str, Any]] = []
    for rec in daily.get("capital_deployment_recommendations") or []:
        if not isinstance(rec, dict):
            continue
        ticker = str(rec.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        proposals.append(proposal_for(
            rec,
            window=window,
            generated_at=generated_at,
            daily=daily,
            config=config,
            config_meta=tracked.get(ticker) or {},
            band_proposal=band_by_ticker.get(ticker) or {},
            deployment_record=deployment_by_ticker.get(ticker) or {},
            capital_queue_row=capital_queue_by_ticker.get(ticker) or {},
        ))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "status": "ok" if proposals else "no_candidates",
        "window": window,
        "canonical_note_mutation_allowed": True,
        "owner_approval_granted": True,
        "portfolio_mutation_allowed": True,
        "apply_allowed": False,
        "proposal_apply_allowed": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "authority": dict(TOP_LEVEL_AUTHORITY),
        "source_artifacts": [
            rel(daily_path),
            "tmp/fundamental-ir-reconciliation-packets.json",
            "tmp/band-proposals.json",
            "tmp/deployment-check.json",
            rel(WF78_CAPITAL_QUEUE),
            "tmp/portfolio-config.json",
        ],
        "output_path": rel(OUT_PATH),
        "proposal_count": len(proposals),
        "proposals": proposals,
        "stop_lines": [
            "Generated proposal packets are review-only surfaces and do not apply changes by themselves.",
            "The approved automation scope is portfolio note/model mutation under WF58/WF56 guardrails only; per-packet apply remains false until an exact validated apply artifact exists.",
            "Trade/account actions, brokerage orders, money movement, and unscoped execution entitlement remain blocked.",
            "Validators must pass before treating packets as decision-grade review inputs.",
        ],
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args.window)
    if args.write:
        atomic_write_json(OUT_PATH, payload)
    print(json.dumps({
        "status": payload["status"],
        "window": args.window,
        "output": rel(OUT_PATH),
        "proposal_count": payload["proposal_count"],
        "write": bool(args.write),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
