#!/usr/bin/env python3
"""WF68 Phase 4 advisor enricher for intraday alert handoffs.

Consumes the Phase 3 artifact-proof main-session handoff and attaches WF58
capital-deployment recommendation context plus WF66/official-source why-stack
context for each actionable alert. This script writes artifact-backed advisor
packets under ``tmp/intraday-alerts`` and deliberately performs no external
channel delivery, cron/config mutation, brokerage/account action, paper order,
canonical-note mutation, portfolio mutation, or owner-approval inference. A
packet may surface a WF67 paper-only package route; execution still belongs to
the WF67 wrapper and guardrail stack, not this script.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_HANDOFF = OUT_DIR / "forced-main-session-handoff.json"
DEFAULT_RECOMMENDATIONS = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_RECOMMENDATION_VALIDATION = ROOT / "tmp" / "capital-deployment-recommendation-validation.json"
DEFAULT_FRESHNESS_REVIEW = ROOT / "tmp" / "research-freshness-opportunity-review.json"
DEFAULT_WF66_OFFICIAL_BRIDGE = ROOT / "tmp" / "fundamental-ir-reconciliation-packets.json"
DEFAULT_OUTPUT_JSON = OUT_DIR / "advisor-alert-packet.json"
DEFAULT_OUTPUT_MD = OUT_DIR / "advisor-alert-packet.md"
DEFAULT_VALIDATION = OUT_DIR / "advisor-alert-packet-validation.json"

AUTHORITY = {
    "posture": "review_only_no_authority",
    "live_trade_or_account_action_allowed": False,
    "paper_trade_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cron_channel_config_mutation_allowed": False,
    "owner_approval_inferred": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "paper_or_live_order_submission_allowed": False,
    "paper_or_live_order_cancellation_allowed": False,
}

BOUNDARY_TEXT = (
    "Advisor alert packet. WF68 itself performs no live/paper trade or cancellation, account, "
    "brokerage, money movement, canonical-note, portfolio, sizing/sleeve/cash/risk-rule, "
    "cron/channel/config mutation, or inferred owner approval. Advisor-derived paper buy/sell "
    "packages may be routed to WF67 only under the 2026-05-19 paper-only approval, exact scoped "
    "request artifact, paper endpoint, fresh kill switch, clean guard validation, redacted audit log, "
    "and main-session capital-package notification."
)

WF67_PAPER_PACKAGE_ROUTE = {
    "status": "allowed_under_wf67_guardrails",
    "approval_artifact": "tmp/alpaca-paper-readiness/phase-7-advisor-paper-execution-approval-2026-05-19.json",
    "required_endpoint": "https://paper-api.alpaca.markets",
    "forbidden_endpoint": "https://" + "api.alpaca.markets",
    "allowed_sides": ["buy", "sell"],
    "allowed_order_types": ["limit", "market"],
    "time_in_force": ["day", "gtc"],
    "execution_owner": "WF67 wrapper only",
    "requires": [
        "advisor_or_capital_packet_source_artifact",
        "exact_scoped_paper_trade_request_artifact",
        "fresh_short_lived_kill_switch",
        "clean_wf67_guard_validation",
        "paper_specific_credentials_only",
        "redacted_audit_log",
        "main_session_capital_package_notification",
    ],
    "blocked": [
        "live_order",
        "live_endpoint",
        "live_credentials",
        "money_movement",
        "account_mutation",
        "close_position_or_liquidation_endpoint",
        "promotion_to_live",
        "owner_approval_inference",
    ],
}

REQUIRED_OFFICIAL_FIELDS = (
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
)

DATA_CONTRACT_FIELDS = [
    "as_of",
    "source_tier",
    "freshness_class",
    "provenance_path",
    "missing_partial_contradictory",
    "authority_block",
    "degradation_reason",
]


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, code: str) -> None:
        self.errors.append(code)

    def warn(self, code: str) -> None:
        self.warnings.append(code)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_alert_packet(packet_ref: Any, packet_id: Any = None) -> dict[str, Any]:
    """Resolve a source alert packet from either a direct file or collection ref.

    Phase 3 handoff paths use refs like
    ``tmp\\intraday-alerts\\current-alerts.json#alerts[wf68-...]``. Treating
    that as a filesystem path loses the source decision packet and makes the
    advisor validator complain about missing thesis/boundary fields. Resolve the
    JSON file first, then locate the packet inside its ``alerts`` array.
    """
    if not isinstance(packet_ref, str) or not packet_ref:
        return {}
    file_ref, _, fragment = packet_ref.partition("#")
    path = Path(file_ref)
    if not path.is_absolute():
        path = ROOT / path
    data = load_json(path, {})
    if not isinstance(data, dict):
        return {}
    if data.get("schema_version") == "wf68.alert_packet.v0":
        return data
    alerts = data.get("alerts")
    if not isinstance(alerts, list):
        return {}
    target_id = packet_id if isinstance(packet_id, str) and packet_id else None
    if not target_id and fragment.startswith("alerts[") and fragment.endswith("]"):
        target_id = fragment[len("alerts["):-1]
    for packet in alerts:
        if isinstance(packet, dict) and packet.get("packet_id") == target_id:
            return packet
    return {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def by_ticker(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        ticker = item.get("ticker") or item.get("ticker_or_scope")
        if isinstance(ticker, str) and ticker:
            out[ticker] = item
    return out


def authority_clean(value: Any, path: str, v: Validation) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(child, bool) and child is True:
                lowered = key.lower()
                if "sufficient_for_paper_execution_recommendation" in lowered:
                    pass
                elif any(token in lowered for token in ("trade", "account", "broker", "money", "canonical", "portfolio", "approval", "mutation", "sizing", "sleeve", "cash", "risk_rule", "order", "cancel", "execution", "channel", "config", "cron")):
                    v.error(f"forbidden_true_authority_flag:{child_path}")
            authority_clean(child, child_path, v)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            authority_clean(child, f"{path}[{idx}]", v)


def observed_entry_status(trigger: dict[str, Any]) -> str:
    try:
        observed = float(trigger.get("observed_price"))
        low = float(trigger.get("entry_band_low"))
        high = float(trigger.get("entry_band_high"))
        stop = float(trigger.get("stop")) if trigger.get("stop") is not None else None
    except (TypeError, ValueError):
        return "unknown_manual_review_required"
    if stop is not None and observed < stop:
        return "BELOW_STOP"
    if low <= observed <= high:
        return "IN_BAND"
    if observed > high:
        return "ABOVE_BAND_WAIT"
    return "BELOW_BAND"


def recommendation_context(ticker: str, proposal: dict[str, Any] | None) -> dict[str, Any]:
    if not proposal:
        return {
            "status": "missing_for_ticker",
            "ticker": ticker,
            "recommendation_posture": "manual_review_required",
            "recommended_action": "prepare_packet",
            "source_freshness": {"overall_classification": "missing", "owner_review_required": True, "capital_action_allowed": False},
            "why_stack": {"missing_evidence_reason": "No WF58 capital-deployment recommendation packet was found for this ticker."},
            "risk_note": "No pro-forma exposure context found; owner must review concentration/risk before any action.",
            "owner_decision_required": True,
            "apply_allowed": False,
            "trade_or_account_action_allowed": False,
        }

    technical = proposal.get("technical_gate") if isinstance(proposal.get("technical_gate"), dict) else {}
    concentration = proposal.get("concentration_check") if isinstance(proposal.get("concentration_check"), dict) else {}
    risk = proposal.get("risk_rule_check") if isinstance(proposal.get("risk_rule_check"), dict) else {}
    proposed = proposal.get("proposed_state") if isinstance(proposal.get("proposed_state"), dict) else {}
    promotion = proposal.get("promotion_review_queue") if isinstance(proposal.get("promotion_review_queue"), dict) else {}
    return {
        "status": "available_review_only",
        "source_artifact": rel(DEFAULT_RECOMMENDATIONS),
        "proposal_id": proposal.get("proposal_id"),
        "ticker": ticker,
        "current_state": proposal.get("current_state"),
        "recommendation_posture": proposed.get("recommendation_posture"),
        "recommended_action": promotion.get("recommended_action") or proposal.get("current_lane_status_tuple", {}).get("recommendation_action"),
        "why_now": proposal.get("why_now"),
        "why_stack": proposal.get("why_stack") or proposal.get("decision_rationale"),
        "base_case": proposal.get("base_case"),
        "bear_case": proposal.get("bear_case"),
        "source_freshness": proposal.get("source_freshness"),
        "technical_gate": {
            "status": technical.get("status"),
            "entry_band_status": technical.get("entry_band_status") or technical.get("band_status"),
            "close": technical.get("close"),
            "distance_to_band_pct": technical.get("distance_to_band_pct"),
            "below_stop": technical.get("below_stop"),
            "stop_line": technical.get("stop_line"),
        },
        "catalyst_gate": proposal.get("catalyst_gate"),
        "risk_note": concentration.get("note") or risk.get("review_boundary") or "Owner must review concentration/risk before any action.",
        "concentration_check": concentration,
        "risk_rule_check": risk,
        "owner_decision_required": proposal.get("owner_decision_required") is True,
        "apply_allowed": False,
        "trade_or_account_action_allowed": False,
    }


def alert_scoped_recommendation_context(rec_context: dict[str, Any], observed_status: str, event_type: Any) -> dict[str, Any]:
    """Scope daily WF58 posture to the live WF68 alert condition.

    A ticker can be owner-decision/deploy-candidate in the daily review layer
    while the live intraday alert is above band/no-chase or below band. Preserve
    the original context for provenance, but expose a non-actionable posture for
    non-entry alerts so validators and delivery routing do not disagree.
    """
    scoped = dict(rec_context)
    original = {
        "recommendation_posture": rec_context.get("recommendation_posture"),
        "recommended_action": rec_context.get("recommended_action"),
    }
    if observed_status == "ABOVE_BAND_WAIT":
        scoped["original_daily_recommendation_context"] = original
        scoped["recommendation_posture"] = "wait_for_band"
        scoped["recommended_action"] = "no_chase_monitor"
        scoped["alert_scoped_reason"] = "Fresh intraday price is above the written entry band; preserve review context but do not label the alert actionable."
    elif observed_status == "BELOW_BAND":
        scoped["original_daily_recommendation_context"] = original
        scoped["recommendation_posture"] = "wait_for_band"
        scoped["recommended_action"] = "wait_for_reclaim"
        scoped["alert_scoped_reason"] = "Fresh intraday price is below the written entry band; wait for reclaim before any paper-order recommendation."
    elif observed_status == "BELOW_STOP":
        scoped["original_daily_recommendation_context"] = original
        scoped["recommendation_posture"] = "risk_review_only"
        scoped["recommended_action"] = "stop_breach_review"
        scoped["alert_scoped_reason"] = "Fresh intraday price is below stop/reference; risk review only, not an execution recommendation."
    elif event_type != "price_enters_band" and observed_status != "IN_BAND":
        scoped["original_daily_recommendation_context"] = original
        scoped["recommendation_posture"] = "monitor_only"
        scoped["recommended_action"] = "grouped_digest"
        scoped["alert_scoped_reason"] = "Alert is not an in-band entry trigger; group it instead of surfacing as actionable."
    elif observed_status == "IN_BAND":
        posture = str(scoped.get("recommendation_posture") or "").lower()
        action = str(scoped.get("recommended_action") or "").lower()
        if "wait" in posture or "wait" in action:
            scoped["original_daily_recommendation_context"] = original
            scoped["recommendation_posture"] = "manual_review_required"
            scoped["recommended_action"] = "prepare_packet"
            scoped["alert_scoped_reason"] = (
                "Fresh intraday price is inside the written band, but the daily recommendation context "
                "still says wait; keep the alert reviewable while blocking execution-ready routing."
            )
    scoped["trade_or_account_action_allowed"] = False
    scoped["apply_allowed"] = False
    return scoped


def wf66_context(ticker: str, proposal: dict[str, Any] | None, official_packet: dict[str, Any] | None) -> dict[str, Any]:
    bridge_from_proposal = proposal.get("official_earnings_bridge") if isinstance(proposal, dict) and isinstance(proposal.get("official_earnings_bridge"), dict) else {}
    bridge_from_wf66 = official_packet.get("official_earnings_bridge") if isinstance(official_packet, dict) and isinstance(official_packet.get("official_earnings_bridge"), dict) else {}
    bridge = bridge_from_proposal or bridge_from_wf66
    return {
        "status": "available_review_only" if bridge else "missing_for_ticker",
        "source_artifact": rel(DEFAULT_WF66_OFFICIAL_BRIDGE) if official_packet else (bridge.get("source_artifact") if bridge else None),
        "ticker": ticker,
        "official_earnings_bridge_status": bridge.get("status"),
        "official_evidence_status": bridge.get("official_evidence_status"),
        "official_evidence_posture": bridge.get("official_evidence_posture"),
        "source_authority_level": bridge.get("source_authority_level"),
        "source_urls": bridge.get("source_urls") or (official_packet or {}).get("source_urls"),
        "source_freshness": bridge.get("source_freshness"),
        "sec_reconciliation_status": bridge.get("sec_reconciliation_status") or (official_packet or {}).get("sec_reconciliation_status"),
        "adjusted_eps_status": bridge.get("adjusted_eps_status") or (official_packet or {}).get("adjusted_eps_reconciliation", {}).get("status") if isinstance((official_packet or {}).get("adjusted_eps_reconciliation"), dict) else bridge.get("adjusted_eps_status"),
        "guidance_status": bridge.get("guidance_status") or (official_packet or {}).get("guidance_reconciliation", {}).get("status") if isinstance((official_packet or {}).get("guidance_reconciliation"), dict) else bridge.get("guidance_status"),
        "unresolved_official_fields": bridge.get("unresolved_official_fields") or [],
        "evidence_claims": bridge.get("evidence_claims") or [],
        "summary": bridge.get("summary") or "Official-source earnings bridge is missing; manual review required.",
        "manual_review_required": bridge.get("manual_review_required") is not False,
        "capital_action_allowed": False,
        "deployment_authority_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }


def claim_field_name(claim: dict[str, Any]) -> str | None:
    claim_type = str(claim.get("claim_type") or "")
    prefix = "official_capture_"
    if claim_type.startswith(prefix):
        return claim_type[len(prefix):]
    return None


def _nested_has_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and child not in (None, "", [], {}):
                return True
            if _nested_has_key(child, keys):
                return True
    elif isinstance(value, list):
        return any(_nested_has_key(item, keys) for item in value)
    return False


def _artifact_contract_gaps(path: Path) -> list[str]:
    if not path.exists():
        return list(DATA_CONTRACT_FIELDS)
    try:
        data = load_json(path, {})
    except (OSError, json.JSONDecodeError):
        return list(DATA_CONTRACT_FIELDS)
    if not isinstance(data, dict):
        return list(DATA_CONTRACT_FIELDS)

    gaps: list[str] = []
    if not any(data.get(key) for key in ("as_of", "as_of_utc", "generated_at_utc", "captured_at_utc", "timestamp_utc")):
        gaps.append("as_of")
    if not _nested_has_key(data, {"source_tier", "source_authority_level", "official_evidence_posture", "source"}):
        gaps.append("source_tier")
    if not _nested_has_key(data, {"freshness_class", "freshness_status", "overall_classification", "source_freshness", "research_freshness_review"}):
        gaps.append("freshness_class")
    if not any(data.get(key) for key in ("provenance_path", "producer", "script", "source_chain", "source_artifacts")):
        gaps.append("provenance_path")
    if not any(key in data for key in ("missing_partial_contradictory", "missing_partial_contradictory_status", "contradictory_status", "warnings", "errors", "findings", "limits")):
        gaps.append("missing_partial_contradictory")
    if not (data.get("authority_block") is True or isinstance(data.get("authority"), dict)):
        gaps.append("authority_block")
    status = str(data.get("status", "")).lower()
    if status in {"degraded", "warning", "error", "partial", "blocked"} and not any(data.get(key) for key in ("degradation_reason", "degraded_reason", "failure_reason", "warnings", "errors", "findings", "limits")):
        gaps.append("degradation_reason")
    return gaps


def data_contract_health(source_artifacts: dict[str, str], as_of: str) -> dict[str, Any]:
    gaps: list[str] = []
    for label, artifact in sorted(source_artifacts.items()):
        path = ROOT / artifact
        for field in _artifact_contract_gaps(path):
            gaps.append(f"{label}:{field}")
    if not source_artifacts:
        status = "MISSING"
    elif not gaps:
        status = "COMPLIANT"
    elif len(gaps) >= len(source_artifacts) * len(DATA_CONTRACT_FIELDS):
        status = "MISSING"
    else:
        status = "PARTIAL"
    return {
        "contract_version": "v2",
        "fields_checked": DATA_CONTRACT_FIELDS,
        "gaps": gaps,
        "overall_status": status,
        "authority_block": True,
        "as_of": as_of,
    }


def official_field_facts(official_context: dict[str, Any]) -> dict[str, Any]:
    claims = official_context.get("evidence_claims") if isinstance(official_context.get("evidence_claims"), list) else []
    by_field: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        field = claim_field_name(claim)
        if not field:
            continue
        by_field[field] = {
            "status": claim.get("capture_status") or ("manual_required" if claim.get("manual_capture_required") else "unknown"),
            "source_url": claim.get("source_url"),
            "source_section": claim.get("source_section"),
            "period": claim.get("period"),
            "value": claim.get("value"),
            "manual_capture_required": claim.get("manual_capture_required") is True,
            "manual_capture_date": claim.get("manual_capture_date"),
        }
    missing = [field for field in REQUIRED_OFFICIAL_FIELDS if field not in by_field]
    manual_required = [field for field, fact in by_field.items() if fact.get("manual_capture_required") or fact.get("status") == "manual_required"]
    captured = [field for field, fact in by_field.items() if fact.get("status") in {"official_captured", "partial", "not_disclosed_in_release"} and not fact.get("manual_capture_required")]
    return {
        "required_fields": list(REQUIRED_OFFICIAL_FIELDS),
        "captured_or_explicitly_addressed_fields": captured,
        "manual_required_fields": manual_required,
        "missing_fields": missing,
        "facts_by_field": by_field,
    }


def official_evidence_adequacy(official_context: dict[str, Any], rec_context: dict[str, Any]) -> dict[str, Any]:
    facts = official_field_facts(official_context)
    freshness = official_context.get("source_freshness") if isinstance(official_context.get("source_freshness"), dict) else {}
    unresolved = [str(item) for item in official_context.get("unresolved_official_fields") or []]
    blockers: list[str] = []
    if official_context.get("status") != "available_review_only":
        blockers.append("missing_wf66_official_source_context")
    if official_context.get("official_evidence_status") != "manual_confirmed":
        blockers.append(f"official_evidence_not_manual_confirmed:{official_context.get('official_evidence_status')}")
    if official_context.get("source_authority_level") != "manual_confirmed_official_source":
        blockers.append(f"source_authority_not_manual_confirmed:{official_context.get('source_authority_level')}")
    if freshness.get("freshness_status") != "current" or freshness.get("retrieval_status") != "manual_confirmed":
        blockers.append(f"official_source_not_current_manual_confirmed:{freshness.get('freshness_status')}/{freshness.get('retrieval_status')}")
    if not facts["facts_by_field"]:
        blockers.append("no_official_field_claims_captured")
    if facts["missing_fields"]:
        blockers.append("missing_official_fields:" + ",".join(facts["missing_fields"]))
    if facts["manual_required_fields"]:
        blockers.append("manual_required_official_fields:" + ",".join(facts["manual_required_fields"]))
    if unresolved:
        blockers.append("unresolved_official_fields:" + ",".join(unresolved))

    sufficient = not blockers
    return {
        "decision": "sufficient_for_paper_execution_recommendation" if sufficient else "insufficient_for_paper_execution_recommendation",
        "sufficient_for_paper_execution_recommendation": sufficient,
        "why_recommended_or_blocked": (
            "Latest official company-source evidence is manual-confirmed/current and required fields are captured or explicitly not disclosed; still review-only and non-authorizing."
            if sufficient else
            "Blocked from immediate paper execution recommendation because official company-source evidence is missing, stale, unresolved, or manual-heavy."
        ),
        "blockers": blockers,
        "latest_official_evidence": {
            "status": official_context.get("official_evidence_status"),
            "posture": official_context.get("official_evidence_posture"),
            "source_authority_level": official_context.get("source_authority_level"),
            "source_freshness": freshness,
            "source_urls": official_context.get("source_urls"),
            "summary": official_context.get("summary"),
        },
        "captured_official_facts": facts,
        "recommendation_source_freshness": rec_context.get("source_freshness"),
        "authority_boundary": "Evidence adequacy only gates recommendation packaging. It does not authorize paper/live order submission, account action, owner approval, or portfolio/canon mutation.",
    }


def build_advisor_packet(
    handoff_path: Path,
    recommendations_path: Path,
    recommendation_validation_path: Path,
    freshness_review_path: Path,
    wf66_official_bridge_path: Path,
) -> dict[str, Any]:
    generated_at = utc_now()
    handoff = load_json(handoff_path)
    recommendations = load_json(recommendations_path, {"proposals": []})
    recommendation_validation = load_json(recommendation_validation_path, {})
    freshness_review = load_json(freshness_review_path, {})
    official_bridge = load_json(wf66_official_bridge_path, {"packets": []})

    proposals = by_ticker([p for p in recommendations.get("proposals", []) if isinstance(p, dict)])
    official_packets = by_ticker([p for p in official_bridge.get("packets", []) if isinstance(p, dict)])

    alerts = handoff.get("alerts") if isinstance(handoff.get("alerts"), list) else []
    enriched_alerts: list[dict[str, Any]] = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        ticker = str(alert.get("ticker") or "")
        proposal = proposals.get(ticker)
        rec_context = recommendation_context(ticker, proposal)
        official_context = wf66_context(ticker, proposal, official_packets.get(ticker))
        evidence_adequacy = official_evidence_adequacy(official_context, rec_context)
        source_alert_packet = load_source_alert_packet(alert.get("packet_path"), alert.get("packet_id"))
        source_decision_packet = source_alert_packet.get("decision_packet") if isinstance(source_alert_packet.get("decision_packet"), dict) else {}
        source_event = source_alert_packet.get("event") if isinstance(source_alert_packet.get("event"), dict) else {}
        source_trigger = source_event.get("trigger") if isinstance(source_event.get("trigger"), dict) else {}
        observed_status = observed_entry_status(source_trigger if isinstance(source_trigger, dict) else {})
        rec_context = alert_scoped_recommendation_context(rec_context, observed_status, alert.get("event_type"))
        decision = {
            "thesis": (proposal or {}).get("thesis_gate", {}).get("summary") if isinstance((proposal or {}).get("thesis_gate"), dict) else source_decision_packet.get("thesis"),
            "entry_logic": source_decision_packet.get("entry_logic") or alert.get("summary"),
            "entry_context": {
                "observed_price": source_trigger.get("observed_price"),
                "entry_band_low": source_trigger.get("entry_band_low"),
                "entry_band_high": source_trigger.get("entry_band_high"),
                "no_chase_above": source_trigger.get("entry_band_high"),
                "observed_entry_status": observed_status,
                "technical_gate": rec_context.get("technical_gate"),
            },
            "invalidation": source_decision_packet.get("invalidation") or rec_context.get("technical_gate", {}).get("stop_line") or "Use written stop/reference invalidation from the owner surface; manual review required.",
            "stop_context": {
                "stop": source_trigger.get("stop"),
                "below_stop": rec_context.get("technical_gate", {}).get("below_stop"),
                "stop_line": rec_context.get("technical_gate", {}).get("stop_line"),
            },
            "source_freshness": {
                "alert_freshness_status": alert.get("freshness_status"),
                "alert_source_timestamp_utc": alert.get("source_timestamp_utc"),
                "recommendation_source_freshness": rec_context.get("source_freshness"),
                "official_source_freshness": official_context.get("source_freshness"),
                "research_freshness_review_status": freshness_review.get("status"),
            },
            "recommendation_context": rec_context,
            "wf66_official_source_context": official_context,
            "official_evidence_adequacy": evidence_adequacy,
            "concentration_risk_note": rec_context.get("risk_note"),
            "owner_action_required": "Live/account actions and workspace mutations still require explicit owner approval. Paper buy/sell may be packaged for WF67 under Randall's 2026-05-19 standing paper-only approval when the scoped request, kill switch, guard validation, audit log, and main-session capital-package notification are clean.",
            "wf67_paper_package_route": WF67_PAPER_PACKAGE_ROUTE,
            "next_step": "owner_decision_required" if alert.get("action_type") == "owner_decision_required" else "prepare_packet",
            "outcome_linkage": {
                "wf55_status": "not_yet_recorded",
                "call_log_required": True,
                "recommended_phase5_action": "Wire resolved WF68 advisor alerts into WF55/Call Log with packet_id, ticker, trigger, recommendation posture, owner decision, no-action/acted outcome, and later realized follow-up. Do not add probability claims until WF55 outcome retention is proof-clean.",
                "probability_claims_allowed": False,
            },
            "authority_boundary": BOUNDARY_TEXT,
        }
        if not decision["thesis"]:
            why_stack = rec_context.get("why_stack") if isinstance(rec_context.get("why_stack"), dict) else {}
            decision["thesis"] = (
                why_stack.get("fundamental_reason")
                or why_stack.get("missing_evidence_reason")
                or source_decision_packet.get("thesis")
                or "Manual thesis review required."
            )
        enriched_alerts.append({
            "packet_id": alert.get("packet_id"),
            "ticker": ticker,
            "severity": alert.get("severity"),
            "event_type": alert.get("event_type"),
            "source_alert_packet_path": alert.get("packet_path"),
            "source_handoff_path": rel(handoff_path),
            "owner_surfaces": alert.get("owner_surfaces"),
            "advisor_decision_packet": decision,
            "authority": AUTHORITY,
        })

    status = "ADVISOR_READY" if handoff.get("status") == "ALERT_READY" and enriched_alerts else "NO_REPLY" if handoff.get("status") == "NO_REPLY" else "BLOCKED"
    source_artifacts = {
        "handoff": rel(handoff_path),
        "wf58_recommendations": rel(recommendations_path),
        "wf58_validation": rel(recommendation_validation_path),
        "research_freshness_review": rel(freshness_review_path),
        "wf66_official_earnings_bridge": rel(wf66_official_bridge_path),
    }
    return {
        "schema_version": "wf68.advisor_alert_packet.v1",
        "workflow": "WF68",
        "phase": "phase_4_advisor_integration",
        "status": status,
        "generated_at_utc": generated_at,
        "delivery_surface": "artifact_proof_only",
        "actual_system_event_injected": False,
        "source_handoff_path": rel(handoff_path),
        "source_artifacts": source_artifacts,
        "data_contract_health": data_contract_health(source_artifacts, generated_at),
        "upstream_status": {
            "handoff_status": handoff.get("status"),
            "recommendations_status": recommendations.get("status"),
            "recommendation_validation_status": recommendation_validation.get("status"),
            "freshness_review_status": freshness_review.get("status"),
            "wf66_bridge_status": official_bridge.get("status"),
        },
        "alert_count": len(enriched_alerts),
        "alerts": enriched_alerts,
        "authority": AUTHORITY,
        "wf67_paper_package_route": WF67_PAPER_PACKAGE_ROUTE,
        "owner_boundary": BOUNDARY_TEXT,
        "phase5_wf55_recommendation": "Next WF68 Phase 5 should create an append-only WF55/Call Log outcome-link artifact for advisor alerts. Required fields: packet_id, ticker, alert trigger, advisor recommendation posture, owner decision, action/no-action, timestamp, follow-up window, realized outcome placeholder, and explicit no probability claim until outcome retention is validated.",
    }


def validate_advisor_packet(packet: dict[str, Any]) -> dict[str, Any]:
    v = Validation()
    if packet.get("schema_version") != "wf68.advisor_alert_packet.v1":
        v.error("schema_version_not_wf68_advisor_v1")
    if packet.get("workflow") != "WF68":
        v.error("workflow_not_wf68")
    if packet.get("phase") != "phase_4_advisor_integration":
        v.error("phase_not_4")
    contract = packet.get("data_contract_health")
    if not isinstance(contract, dict):
        v.error("missing_data_contract_health")
    else:
        if contract.get("contract_version") != "v2":
            v.error("bad_data_contract_version")
        if contract.get("fields_checked") != DATA_CONTRACT_FIELDS:
            v.error("bad_data_contract_fields_checked")
        if contract.get("overall_status") not in {"COMPLIANT", "PARTIAL", "MISSING"}:
            v.error("bad_data_contract_overall_status")
        if contract.get("authority_block") is not True:
            v.error("data_contract_authority_block_not_true")
        if not contract.get("as_of"):
            v.error("missing_data_contract_as_of")
    authority = packet.get("authority")
    if not isinstance(authority, dict):
        v.error("missing_authority")
    else:
        for flag, expected in AUTHORITY.items():
            if authority.get(flag) != expected:
                v.error(f"authority_mismatch:{flag}")
    authority_clean(packet, "packet", v)
    for idx, alert in enumerate(packet.get("alerts", [])):
        decision = alert.get("advisor_decision_packet") if isinstance(alert, dict) else None
        if not isinstance(decision, dict):
            v.error(f"missing_advisor_decision_packet:{idx}")
            continue
        for field in ("thesis", "entry_logic", "invalidation", "source_freshness", "recommendation_context", "wf66_official_source_context", "official_evidence_adequacy", "concentration_risk_note", "owner_action_required", "wf67_paper_package_route", "outcome_linkage"):
            if decision.get(field) in (None, "", [], {}):
                v.error(f"missing_decision_field:{idx}:{field}")
        if decision.get("outcome_linkage", {}).get("probability_claims_allowed") is not False:
            v.error(f"probability_claim_not_blocked:{idx}")
        if "explicit" not in str(decision.get("owner_action_required", "")):
            v.error(f"weak_owner_action_required:{idx}")
        route = decision.get("wf67_paper_package_route", {})
        if not isinstance(route, dict) or route.get("status") != "allowed_under_wf67_guardrails":
            v.error(f"missing_wf67_paper_package_route:{idx}")
        elif route.get("required_endpoint") != "https://paper-api.alpaca.markets" or route.get("forbidden_endpoint") != "https://" + "api.alpaca.markets":
            v.error(f"bad_wf67_endpoint_boundary:{idx}")
        rec = decision.get("recommendation_context", {})
        if isinstance(rec, dict) and rec.get("trade_or_account_action_allowed") is not False:
            v.error(f"recommendation_trade_boundary_not_false:{idx}")
        if isinstance(rec, dict):
            posture = rec.get("recommendation_posture") or rec.get("recommended_action")
            observed_status = (decision.get("entry_context") or {}).get("observed_entry_status") if isinstance(decision.get("entry_context"), dict) else None
            if observed_status == "IN_BAND" and posture == "wait_for_band":
                v.error(f"in_band_alert_labeled_wait_for_band:{idx}")
            if observed_status == "ABOVE_BAND_WAIT" and posture in {"deploy_candidate", "owner_decision_required", "owner_gated_band_review"}:
                v.error(f"above_band_alert_labeled_actionable:{idx}")
        wf66 = decision.get("wf66_official_source_context", {})
        if isinstance(wf66, dict) and wf66.get("trade_or_account_action_allowed") is not False:
            v.error(f"wf66_trade_boundary_not_false:{idx}")
        adequacy = decision.get("official_evidence_adequacy", {})
        if not isinstance(adequacy, dict):
            v.error(f"missing_official_evidence_adequacy:{idx}")
        else:
            if adequacy.get("decision") not in {"sufficient_for_paper_execution_recommendation", "insufficient_for_paper_execution_recommendation"}:
                v.error(f"bad_official_evidence_adequacy_decision:{idx}")
            if not isinstance(adequacy.get("captured_official_facts"), dict):
                v.error(f"missing_captured_official_facts:{idx}")
            if not isinstance(adequacy.get("blockers"), list):
                v.error(f"missing_official_evidence_blockers:{idx}")
            if adequacy.get("sufficient_for_paper_execution_recommendation") is True and adequacy.get("blockers"):
                v.error(f"official_evidence_sufficient_with_blockers:{idx}")
    if packet.get("status") == "ADVISOR_READY" and not packet.get("alerts"):
        v.error("advisor_ready_without_alerts")
    return {
        "generated_at_utc": utc_now(),
        "status": "ok" if not v.errors else "error",
        "summary": {"alerts_checked": len(packet.get("alerts", [])), "critical": len(v.errors), "warning": len(v.warnings)},
        "errors": v.errors,
        "warnings": v.warnings,
        "authority": AUTHORITY,
    }


def write_markdown(path: Path, packet: dict[str, Any], validation: dict[str, Any]) -> None:
    lines = [
        "# WF68 Advisor Alert Packet",
        "",
        f"- Generated UTC: {packet['generated_at_utc']}",
        f"- Status: {packet['status']}",
        f"- Delivery surface: {packet['delivery_surface']}",
        f"- Source handoff: `{packet['source_handoff_path']}`",
        f"- Alert count: {packet['alert_count']}",
        f"- Validation: {validation['status']} ({validation['summary']['critical']} critical)",
        f"- Authority: {BOUNDARY_TEXT}",
        "",
    ]
    for alert in packet.get("alerts", []):
        decision = alert["advisor_decision_packet"]
        rec = decision["recommendation_context"]
        wf66 = decision["wf66_official_source_context"]
        adequacy = decision["official_evidence_adequacy"]
        lines.extend([
            f"## {alert.get('ticker')} - {alert.get('severity')} {alert.get('event_type')}",
            "",
            f"- Source alert packet: `{alert.get('source_alert_packet_path')}`",
            f"- Thesis: {decision.get('thesis')}",
            f"- Entry/review logic: {decision.get('entry_logic')}",
            f"- Entry band/price context: observed `{decision.get('entry_context', {}).get('observed_price')}`, band `{decision.get('entry_context', {}).get('entry_band_low')}-{decision.get('entry_context', {}).get('entry_band_high')}`, no-chase above `{decision.get('entry_context', {}).get('no_chase_above')}`, observed status `{decision.get('entry_context', {}).get('observed_entry_status')}`",
            f"- Invalidation/stop context: {decision.get('invalidation')} Stop `{decision.get('stop_context', {}).get('stop')}`; below stop `{decision.get('stop_context', {}).get('below_stop')}`",
            f"- WF58 recommendation posture: {rec.get('recommendation_posture')} / action `{rec.get('recommended_action')}`",
            f"- Source freshness: alert `{decision['source_freshness'].get('alert_freshness_status')}`, WF58 `{(rec.get('source_freshness') or {}).get('overall_classification')}`, WF66 `{(wf66.get('source_freshness') or {}).get('freshness_status')}`",
            f"- WF66 official-source status: {wf66.get('status')} / evidence `{wf66.get('official_evidence_status')}` / SEC `{wf66.get('sec_reconciliation_status')}`",
            f"- Official evidence adequacy: `{adequacy.get('decision')}`; blockers `{', '.join(adequacy.get('blockers') or []) or 'none'}`",
            f"- Risk/concentration note: {decision.get('concentration_risk_note')}",
            f"- Owner action required: {decision.get('owner_action_required')}",
            f"- WF67 paper package route: {decision.get('wf67_paper_package_route', {}).get('status')} via `{decision.get('wf67_paper_package_route', {}).get('approval_artifact')}`; endpoint `{decision.get('wf67_paper_package_route', {}).get('required_endpoint')}` only",
            f"- Outcome linkage: {decision['outcome_linkage'].get('recommended_phase5_action')}",
            "",
        ])
    if not packet.get("alerts"):
        lines.extend(["## Quiet behavior", "", "No actionable alert exists in the source handoff; no advisor packet should be surfaced.", ""])
    lines.extend(["## Phase 5 recommendation", "", packet["phase5_wf55_recommendation"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WF68 Phase 4 advisor alert packet enricher.")
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--recommendations", type=Path, default=DEFAULT_RECOMMENDATIONS)
    parser.add_argument("--recommendation-validation", type=Path, default=DEFAULT_RECOMMENDATION_VALIDATION)
    parser.add_argument("--freshness-review", type=Path, default=DEFAULT_FRESHNESS_REVIEW)
    parser.add_argument("--wf66-official-bridge", type=Path, default=DEFAULT_WF66_OFFICIAL_BRIDGE)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    return parser.parse_args(argv)


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_advisor_packet(
        resolve(args.handoff),
        resolve(args.recommendations),
        resolve(args.recommendation_validation),
        resolve(args.freshness_review),
        resolve(args.wf66_official_bridge),
    )
    validation = validate_advisor_packet(packet)
    write_json(resolve(args.output_json), packet)
    write_json(resolve(args.validation_output), validation)
    write_markdown(resolve(args.output_md), packet, validation)
    print(json.dumps({
        "workflow": "WF68",
        "phase": "phase_4_advisor_integration",
        "status": packet["status"],
        "validation_status": validation["status"],
        "alert_count": packet["alert_count"],
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "validation_output": str(args.validation_output),
    }, indent=2))
    return 0 if validation["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
