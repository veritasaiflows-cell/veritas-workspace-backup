from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from source_freshness_classifier import classify_source_state, summarize_source_freshness
from disciplined_band_gate import (
    build_staleness_alert_payload,
    extension_assessment,
    load_disciplined_bands,
    proposal_index as disciplined_proposal_index,
    staleness_assessment,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SCHEMA_VERSION = 1
OWNER_LAYERS = [
    "03. Portfolio/Execution Board.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "05. Intelligence/Weekly Positioning Review.md",
    "07. Risk/Risk Rules.md",
]

WINDOW_SPECS: dict[str, dict[str, Any]] = {
    "morning": {
        "output": TMP / "daily-review-objects-morning.json",
        "review_window": "pre-market",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "deployment_check": TMP / "deployment-check.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "run_summary": TMP / "run-summary-morning.json",
            "market_state": TMP / "market-state.json",
            "band_proposals": TMP / "band-proposals.json",
            "primary_summary": TMP / "premarket-snapshot.json",
        },
        "optional": {
            "portfolio_config": TMP / "portfolio-config.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
            "market_intelligence_events": TMP / "market-intelligence-events-morning.json",
            "sector_correlation_check": TMP / "sector-correlation-check.json",
            "sector_expansion_board": TMP / "sector-expansion-board.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
    "post-close": {
        "output": TMP / "daily-review-objects-post-close.json",
        "review_window": "post-close",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "deployment_check": TMP / "deployment-check.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "run_summary": TMP / "run-summary-post-close.json",
            "market_state": TMP / "market-state.json",
            "band_proposals": TMP / "band-proposals.json",
            "primary_summary": TMP / "daily-executive-brief.json",
            "snapshot": TMP / "postmarket-snapshot.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
        },
        "optional": {
            "portfolio_config": TMP / "portfolio-config.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
            "market_intelligence_events": TMP / "market-intelligence-events-post-close.json",
            "sector_correlation_check": TMP / "sector-correlation-check.json",
            "sector_expansion_board": TMP / "sector-expansion-board.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
    "post-earnings": {
        "output": TMP / "daily-review-objects-post-earnings.json",
        "review_window": "post-earnings",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "deployment_check": TMP / "deployment-check.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "run_summary": TMP / "run-summary-post-earnings.json",
            "band_proposals": TMP / "band-proposals.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
        },
        "optional": {
            "portfolio_config": TMP / "portfolio-config.json",
            "market_state": TMP / "market-state.json",
            "primary_summary": TMP / "daily-executive-brief.json",
            "snapshot": TMP / "postmarket-snapshot.json",
            "market_intelligence_events": TMP / "market-intelligence-events-post-earnings.json",
            "sector_correlation_check": TMP / "sector-correlation-check.json",
            "sector_expansion_board": TMP / "sector-expansion-board.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
    "sunday": {
        "output": TMP / "daily-review-objects-sunday.json",
        "review_window": "weekly-rebuild",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "deployment_check": TMP / "deployment-check.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "run_summary": TMP / "run-summary-sunday.json",
            "market_state": TMP / "market-state.json",
            "band_proposals": TMP / "band-proposals.json",
            "primary_summary": TMP / "daily-executive-brief.json",
            "snapshot": TMP / "postmarket-snapshot.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
        },
        "optional": {
            "portfolio_config": TMP / "portfolio-config.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
            "market_intelligence_events": TMP / "market-intelligence-events-sunday.json",
            "sector_correlation_check": TMP / "sector-correlation-check.json",
            "sector_expansion_board": TMP / "sector-expansion-board.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
}

STATE_BASE_SCORES = {
    "DEPLOYABLE NOW": 88,
    "PROMOTION REVIEW": 84,
    "ALMOST DEPLOYABLE": 72,
    "ALMOST / NEAR-EARNINGS CAUTION": 66,
    "POST-EARNINGS REVIEW": 64,
    "BLOCKED": 60,
    "DO NOT TOUCH": 38,
    "WATCH / RESEARCH NEEDED": 22,
    "SYSTEM HOLD": 8,
}

CAPITAL_CANDIDATE_CATEGORIES = {
    "promotion_review",
    "near_deployable",
    "timing_caution",
    "post_earnings_review",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ranked daily decision-grade review objects and owner-gated capital-deployment recommendation packets.",
    )
    parser.add_argument("--window", required=True, choices=sorted(WINDOW_SPECS.keys()))
    return parser.parse_args()



def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def load_json(path: Path, *, required: bool) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    if data is None:
        if required:
            raise FileNotFoundError(path)
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return data



def artifact_record(path: Path, *, required: bool) -> dict[str, Any]:
    data = load_json_artifact(path)
    generated = ""
    if isinstance(data, dict):
        for key in ("generated_at_utc", "generated_at"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                generated = value
                break
    file_mtime = ""
    if path.exists():
        file_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not generated:
        generated = file_mtime
    rel_path = str(path.relative_to(WORKSPACE)).replace("\\", "/")
    source_state = classify_source_state(
        source_key=path.stem,
        path=rel_path,
        required=required,
        criticality="critical" if required else "context",
        owner_layer="artifact:daily_review_objects.py",
        exists=path.exists() and isinstance(data, dict),
        generated_at_utc=generated,
        file_mtime_utc=file_mtime,
        status_raw=(data or {}).get("status") if isinstance(data, dict) else "missing",
        stale_after_hours=30,
        warnings=(data or {}).get("warnings") if isinstance(data, dict) else [],
    )
    return {
        "path": rel_path,
        "required": required,
        "exists": path.exists(),
        "generated_at_utc": generated,
        "status": "ok" if path.exists() else "missing",
        "source_state": source_state,
        "classification": source_state["classification"],
    }



def parse_pct(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)%", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None



def clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]



def system_block(
    run_summary: dict[str, Any],
    validation: dict[str, Any],
    deployment_surface: dict[str, Any],
    primary_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    validation_summary = validation.get("summary") or {}
    warning_codes = clean_list(((deployment_surface.get("system") or {}).get("warning_codes")))
    warnings = clean_list(run_summary.get("warnings"))
    trust_reason = ""
    if primary_summary:
        trust_reason = str(primary_summary.get("trust_reason") or "")

    try:
        critical = int(validation_summary.get("critical", 0) or 0)
    except Exception:
        critical = 0
    try:
        warning = int(validation_summary.get("warning", 0) or 0)
    except Exception:
        warning = 0
    try:
        info = int(validation_summary.get("info", 0) or 0)
    except Exception:
        info = 0

    stop_line = bool(run_summary.get("stop_line")) or bool((deployment_surface.get("system") or {}).get("stop_line"))
    macro_gate = str((deployment_surface.get("system") or {}).get("macro_gate") or "unknown")
    canonical_mutation_allowed = bool(((run_summary.get("downstream") or {}).get("canonical_note_mutation_allowed")))
    trust_level = "clean"
    if stop_line or critical > 0:
        trust_level = "blocked"
    elif warning > 0 or warning_codes or macro_gate != "CLEAN" or bool(primary_summary and primary_summary.get("trust_gate_blocked")):
        trust_level = "review_required"

    trust_ceiling_reasons: list[str] = []
    if stop_line:
        trust_ceiling_reasons.append("workflow stop line is active")
    if critical > 0:
        trust_ceiling_reasons.append(f"dashboard validation has {critical} critical issue(s)")
    if warning > 0:
        trust_ceiling_reasons.append(f"dashboard validation has {warning} warning(s)")
    if macro_gate != "CLEAN":
        trust_ceiling_reasons.append(f"macro gate is {macro_gate}")
    if trust_reason:
        trust_ceiling_reasons.append(trust_reason)
    trust_ceiling_reasons.extend(warnings[:3])
    deduped_reasons: list[str] = []
    seen_reasons: set[str] = set()
    for item in trust_ceiling_reasons:
        if not item or item in seen_reasons:
            continue
        deduped_reasons.append(item)
        seen_reasons.add(item)

    return {
        "consumer_posture": "review_only",
        "trust_level": trust_level,
        "stop_line": stop_line,
        "critical": critical,
        "warning": warning,
        "info": info,
        "macro_gate": macro_gate,
        "warning_codes": warning_codes,
        "canonical_mutation_allowed": canonical_mutation_allowed,
        "owner_approval_required_for_capital": True,
        "trust_ceiling_reasons": deduped_reasons,
        "run_status": str(run_summary.get("status") or "unknown"),
        "presentation_allowed": bool(((run_summary.get("downstream") or {}).get("presentation_allowed"))),
    }



def build_system_review_object(system: dict[str, Any]) -> dict[str, Any] | None:
    if system["trust_level"] == "clean" and not system["warning_codes"]:
        return None
    score = 98 if system["stop_line"] else 90
    if system["critical"] > 0:
        score = max(score, 94)
    return {
        "id": "system-trust-ceiling",
        "object_type": "system",
        "category": "trust_ceiling",
        "signal_score": score,
        "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
        "surface_state": "SYSTEM HOLD" if system["stop_line"] else "REVIEW REQUIRED",
        "escalation_reason": "Trust posture directly limits what can be treated as decision-grade today.",
        "why_now": "; ".join(system["trust_ceiling_reasons"]) or "trust posture requires review",
        "recommended_next_step": "Review trust warnings before treating any capital recommendation as clean.",
        "owner_question": "Is today clean enough to review deployment candidates, or should trust debt be resolved first?",
        "owner_reads": [
            "tmp/dashboard-validation.json",
            "tmp/deployment-readiness-surface.json",
        ],
        "supporting_artifacts": [
            "tmp/dashboard-validation.json",
            "tmp/deployment-readiness-surface.json",
        ],
        "owner_review_required": True,
    }



def normalize_band_status(
    proposal: dict[str, Any] | None,
    deployment_record: dict[str, Any] | None,
) -> str | None:
    """Disambiguate proposal/reclaim stop weakness from a live stop breach.

    `band-proposals.json` can emit BELOW_STOP for a suggested reclaim/vault stop.
    Downstream capital packets must only expose literal BELOW_STOP when the
    authoritative deployment record says the live stop is actually breached.
    """
    if not proposal:
        return None
    raw = proposal.get("band_status")
    status = str(raw or "").strip()
    if status == "BELOW_STOP" and bool((deployment_record or {}).get("below_stop")) is not True:
        return "BELOW_RECLAIM_STOP"
    return status or None


def band_status_note(raw_status: str | None, normalized_status: str | None, deployment_record: dict[str, Any] | None) -> str | None:
    if raw_status == "BELOW_STOP" and normalized_status == "BELOW_RECLAIM_STOP":
        return "Band proposal is below a proposed reclaim/vault stop; authoritative deployment below_stop is false, so this is not a live stop breach."
    return None


def live_entry_band_status(surface_record: dict[str, Any], deployment_record: dict[str, Any] | None, proposal: dict[str, Any] | None) -> str | None:
    """Classify the live/current written-band posture, not the proposed-band posture.

    Band proposals may emit statuses for suggested reclaim/vault bands. Capital
    and advisor packets need the current entry state against the written band so
    they do not say "wait for band"/"below reclaim stop" while the live surface
    says in-band or above-band/no-chase.
    """
    if bool((deployment_record or {}).get("below_stop")):
        return "BELOW_STOP"
    if bool((deployment_record or {}).get("in_entry_band")):
        return "IN_BAND"

    band_position = str(surface_record.get("band_position") or "").strip().lower()
    if "above band" in band_position:
        return "ABOVE_BAND_WAIT"
    if "below band" in band_position:
        return "BELOW_BAND"
    if "in band" in band_position:
        return "IN_BAND"

    return normalize_band_status(proposal, deployment_record)


def combined_band_status_note(
    raw_status: str | None,
    proposal_status: str | None,
    live_status: str | None,
    deployment_record: dict[str, Any] | None,
) -> str | None:
    notes = []
    normalized_note = band_status_note(raw_status, proposal_status, deployment_record)
    if normalized_note:
        notes.append(normalized_note)
    if proposal_status and live_status and proposal_status != live_status:
        notes.append(f"Live written-band status is {live_status}; proposed-band/reclaim status is {proposal_status}.")
    return " ".join(notes) or None


def category_for(surface_record: dict[str, Any], deployment_record: dict[str, Any] | None, proposal: dict[str, Any] | None) -> str:
    state = str(legacy_state(surface_record, "surface_state") or "")
    days = surface_record.get("days_to_earnings")
    band_stale = bool(surface_record.get("band_stale"))
    below_stop = bool((deployment_record or {}).get("below_stop"))

    if band_stale:
        return "review_debt"
    if state == "PROMOTION REVIEW":
        return "promotion_review"
    if state == "ALMOST / NEAR-EARNINGS CAUTION":
        return "timing_caution"
    if state == "ALMOST DEPLOYABLE":
        if isinstance(days, int) and 0 < days <= 14:
            return "timing_caution"
        return "near_deployable"
    if state == "POST-EARNINGS REVIEW":
        return "post_earnings_review"
    if state in {"BLOCKED", "DO NOT TOUCH"} or below_stop:
        return "risk_hold"
    if proposal and proposal.get("canonical_apply_eligible"):
        return "near_deployable"
    return "monitor"



def band_distance_points(surface_record: dict[str, Any], deployment_record: dict[str, Any] | None) -> int:
    if bool((deployment_record or {}).get("in_entry_band")):
        return 10
    pct = parse_pct(str(surface_record.get("band_position") or ""))
    if pct is None:
        return 0
    if pct <= 0.5:
        return 6
    if pct <= 1.5:
        return 4
    if pct <= 3.0:
        return 2
    return 0



def signal_score(
    surface_record: dict[str, Any],
    deployment_record: dict[str, Any] | None,
    proposal: dict[str, Any] | None,
    system: dict[str, Any],
) -> int:
    state = str(legacy_state(surface_record, "surface_state") or "")
    category = category_for(surface_record, deployment_record, proposal)
    score = STATE_BASE_SCORES.get(state, 20)

    if category == "review_debt":
        score = max(score, 78)
    if category == "risk_hold":
        score = max(score, 58)

    score += band_distance_points(surface_record, deployment_record)

    if proposal and proposal.get("canonical_apply_eligible"):
        score += 8
    if proposal and str(proposal.get("band_status") or "") == "ABOVE_BAND_WAIT":
        score -= 8
    if proposal and str(proposal.get("band_status") or "") == "EARNINGS_IMMINENT":
        score -= 20

    days = surface_record.get("days_to_earnings")
    if isinstance(days, int) and 0 < days <= 14:
        score -= 18
    elif isinstance(days, int) and 15 <= days <= 21:
        score -= 8

    if surface_record.get("earnings_date_ir_confirmed") is False and isinstance(days, int) and 0 < days <= 21:
        score -= 6

    if system["trust_level"] == "blocked":
        score = min(score, 74)
    elif system["trust_level"] != "clean":
        score = min(score, 92)

    return max(0, min(99, score))



def recommendation_class(
    surface_record: dict[str, Any],
    deployment_record: dict[str, Any] | None,
    proposal: dict[str, Any] | None,
    system: dict[str, Any],
) -> str:
    category = category_for(surface_record, deployment_record, proposal)
    if system["stop_line"] or system["critical"] > 0:
        return "no_new_approval"
    if category == "review_debt":
        return "resolve_review_debt"
    if category == "risk_hold":
        return "risk_hold"
    if category == "timing_caution":
        return "wait_for_catalyst_clearance"
    if category == "post_earnings_review":
        return "hold_promotion_review"
    if category == "promotion_review":
        return "review_for_possible_add"
    if category == "near_deployable":
        in_band = bool((deployment_record or {}).get("in_entry_band"))
        near_band = band_distance_points(surface_record, deployment_record) >= 4
        if in_band or near_band:
            return "conditional_pullback_review"
        return "wait_for_band"
    return "monitor_only"



def owner_question(ticker: str, category: str) -> str:
    if category == "promotion_review":
        return f"Should {ticker} be promoted into live deployment review now?"
    if category == "near_deployable":
        return f"Is {ticker} close enough to keep on the short list, or does it stay in wait-state?"
    if category == "timing_caution":
        return f"Does {ticker} stay actionable enough to watch through the catalyst window, or should it be deferred?"
    if category == "review_debt":
        return f"Does {ticker} need trust-debt cleanup before any new conclusion is trusted?"
    if category == "risk_hold":
        return f"Does {ticker} require any risk-layer cleanup, or is continued no-touch discipline the right answer?"
    return f"What is the next bounded review step for {ticker}?"



def recommended_next_step(ticker: str, rec_class: str, *, band_status: str | None = None) -> str:
    normalized_band = str(band_status or "").upper().replace(" ", "_")
    mapping = {
        "review_for_possible_add": f"Read the owner layers for {ticker} and decide whether to open an owner-gated capital-deployment review.",
        "conditional_pullback_review": f"Keep {ticker} on the short list and only approve on a disciplined pullback / band interaction.",
        "wait_for_band": f"Do not approve {ticker} yet; wait for a cleaner band interaction.",
        "wait_for_catalyst_clearance": f"Do not approve {ticker} through the active catalyst window; recheck after timing risk clears.",
        "hold_promotion_review": f"Hold {ticker} in review-only posture until the post-event interpretation is refreshed.",
        "resolve_review_debt": f"Resolve the trust / band-review debt for {ticker} before elevating it in the decision stack.",
        "risk_hold": f"Keep {ticker} in no-touch / risk-hold posture; this is not a deployment candidate today.",
        "no_new_approval": f"Do not treat {ticker} as approvable while the workflow stop line or critical trust issue is active.",
        "monitor_only": f"Leave {ticker} in monitor-only posture.",
    }
    if rec_class == "conditional_pullback_review" and normalized_band == "IN_BAND":
        return f"{ticker} is inside the written band; prepare an owner-gated review/decision packet rather than waiting for another band interaction."
    return mapping.get(rec_class, f"Continue bounded review for {ticker}.")


def supporting_artifacts(window: str, ticker: str) -> list[str]:
    artifacts = [
        "tmp/deployment-readiness-surface.json",
        "tmp/deployment-check.json",
        "tmp/band-proposals.json",
        f"tmp/run-summary-{window}.json",
        "tmp/dashboard-validation.json",
    ]
    if window in {"post-close", "sunday"}:
        artifacts.extend(["tmp/daily-executive-brief.json", "tmp/postmarket-snapshot.json"])
    elif window == "morning":
        artifacts.append("tmp/premarket-snapshot.json")
    return artifacts



def evidence_lines(surface_record: dict[str, Any], deployment_record: dict[str, Any] | None, proposal: dict[str, Any] | None) -> list[str]:
    evidence: list[str] = []
    why = str(surface_record.get("why") or "").strip()
    if why:
        evidence.append(why)
    band_position = str(surface_record.get("band_position") or "").strip()
    if band_position:
        evidence.append(f"Band position: {band_position}")
    trigger = str(surface_record.get("trigger") or "").strip()
    if trigger:
        evidence.append(f"Trigger: {trigger}")
    if proposal and proposal.get("canonical_apply_eligible"):
        evidence.append("Band proposal is config-layer apply-eligible under the native gates.")
    if proposal:
        proposal_reasons = clean_list(proposal.get("reasons"))
        evidence.extend(proposal_reasons[:2])
    if deployment_record:
        reason = str(deployment_record.get("reason") or "").strip()
        if reason and reason not in evidence:
            evidence.append(reason)
    return evidence[:5]



def blocker_lines(surface_record: dict[str, Any], proposal: dict[str, Any] | None, system: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    override_reason = str(surface_record.get("override_reason") or "").strip()
    if override_reason and override_reason != "pass-through":
        blockers.append(override_reason)
    catalyst_blocker = str(surface_record.get("catalyst_blocker") or "").strip()
    if catalyst_blocker:
        blockers.append(catalyst_blocker)
    if bool(surface_record.get("band_stale")):
        blockers.append("band review debt remains active")
    if proposal and not proposal.get("canonical_apply_eligible") and proposal.get("needs_review"):
        blockers.append("band proposal remains review-only / non-applyable")
    if system["trust_level"] != "clean":
        blockers.extend(system["trust_ceiling_reasons"][:2])
    deduped: list[str] = []
    seen: set[str] = set()
    for item in blockers:
        if not item or item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped[:5]



def should_include_record(surface_record: dict[str, Any], deployment_record: dict[str, Any] | None, proposal: dict[str, Any] | None) -> bool:
    state = str(legacy_state(surface_record, "surface_state") or "")
    if state in {
        "PROMOTION REVIEW",
        "ALMOST DEPLOYABLE",
        "ALMOST / NEAR-EARNINGS CAUTION",
        "POST-EARNINGS REVIEW",
        "BLOCKED",
    }:
        return True
    if state == "DO NOT TOUCH":
        return bool(surface_record.get("band_stale")) or bool((deployment_record or {}).get("below_stop"))
    if state == "WATCH / RESEARCH NEEDED":
        return bool(surface_record.get("band_stale"))
    return proposal is not None and bool(proposal.get("canonical_apply_eligible"))



def ticker_review_objects(
    window: str,
    deployment_surface: dict[str, Any],
    deployment_check: dict[str, Any],
    band_proposals: dict[str, Any],
    system: dict[str, Any],
) -> list[dict[str, Any]]:
    deployment_records = {
        str(record.get("ticker")): record
        for record in deployment_check.get("records", []) or []
        if isinstance(record, dict) and record.get("ticker")
    }
    proposal_records = {
        str(record.get("ticker")): record
        for record in band_proposals.get("proposals", []) or []
        if isinstance(record, dict) and record.get("ticker")
    }

    objects: list[dict[str, Any]] = []
    groups = deployment_surface.get("groups") or {}
    for rows in groups.values():
        if not isinstance(rows, list):
            continue
        for surface_record in rows:
            if not isinstance(surface_record, dict):
                continue
            ticker = str(surface_record.get("ticker") or "").strip()
            if not ticker:
                continue
            deployment_record = deployment_records.get(ticker)
            proposal = proposal_records.get(ticker)
            if not should_include_record(surface_record, deployment_record, proposal):
                continue

            category = category_for(surface_record, deployment_record, proposal)
            rec_class = recommendation_class(surface_record, deployment_record, proposal, system)
            score = signal_score(surface_record, deployment_record, proposal, system)
            raw_band_status = str(proposal.get("band_status") or "").strip() if proposal else None
            proposal_band_status = normalize_band_status(proposal, deployment_record)
            live_band_status = live_entry_band_status(surface_record, deployment_record, proposal)
            normalized_band_note = combined_band_status_note(raw_band_status, proposal_band_status, live_band_status, deployment_record)
            owner_reads = list(OWNER_LAYERS)
            if category in {"review_debt", "risk_hold"}:
                owner_reads = [
                    "03. Portfolio/Execution Board.md",
                    "03. Portfolio/Portfolio Snapshot.md",
                    "07. Risk/Risk Rules.md",
                ]

            objects.append({
                "id": f"{window}:{ticker.lower()}",
                "object_type": "ticker",
                "ticker": ticker,
                "category": category,
                "surface_state": legacy_state(surface_record, "surface_state"),
                "machine_state": legacy_state(surface_record, "machine_state"),
                "workflow_state": legacy_state(surface_record, "workflow_state"),
                "signal_score": score,
                "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
                "days_to_earnings": surface_record.get("days_to_earnings"),
                "band_position": surface_record.get("band_position"),
                "band_status": live_band_status,
                "proposal_band_status": proposal_band_status,
                "raw_band_status": raw_band_status,
                "band_status_note": normalized_band_note,
                "band_stale": bool(surface_record.get("band_stale")),
                "canonical_apply_eligible": bool(proposal.get("canonical_apply_eligible")) if proposal else False,
                "macro_gate": surface_record.get("macro_gate") or system.get("macro_gate"),
                "recommendation_class": rec_class,
                "why_now": str(surface_record.get("why") or "") or str((deployment_record or {}).get("reason") or ""),
                "evidence": evidence_lines(surface_record, deployment_record, proposal),
                "blockers": blocker_lines(surface_record, proposal, system),
                "owner_question": owner_question(ticker, category),
                "recommended_next_step": recommended_next_step(ticker, rec_class, band_status=live_band_status),
                "owner_reads": owner_reads,
                "supporting_artifacts": supporting_artifacts(window, ticker),
                "owner_review_required": True,
            })
    return objects



def contradiction_objects(
    window: str,
    deployment_surface: dict[str, Any],
    primary_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not primary_summary:
        return []

    surface_groups = deployment_surface.get("groups") or {}
    surface_deployable = sorted(
        str(item.get("ticker"))
        for item in surface_groups.get("DEPLOYABLE NOW", []) or []
        if isinstance(item, dict) and item.get("ticker")
    )
    surface_almost = sorted(
        str(item.get("ticker"))
        for state in ("ALMOST DEPLOYABLE", "ALMOST / NEAR-EARNINGS CAUTION")
        for item in surface_groups.get(state, []) or []
        if isinstance(item, dict) and item.get("ticker")
    )

    summary_deployable = sorted(clean_list(primary_summary.get("deployable_now")))
    summary_almost = sorted(clean_list(primary_summary.get("almost_deployable")))

    objects: list[dict[str, Any]] = []
    if surface_deployable != summary_deployable:
        objects.append({
            "id": f"{window}:deployable-contradiction",
            "object_type": "system",
            "category": "surface_contradiction",
            "signal_score": 86,
            "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
            "surface_state": "REVIEW REQUIRED",
            "escalation_reason": "Primary summary and deployment surface disagree on deployable-now state.",
            "why_now": f"deployment surface={surface_deployable or ['<none>']} vs primary summary={summary_deployable or ['<none>']}",
            "recommended_next_step": "Review the summary surface before treating deployable-now language as authoritative.",
            "owner_question": "Is this a stale summary surface, a trust downgrade, or a deeper state contradiction?",
            "owner_reads": [
                "03. Portfolio/Execution Board.md",
                "03. Portfolio/Portfolio Snapshot.md",
            ],
            "supporting_artifacts": [
                "tmp/deployment-readiness-surface.json",
                "tmp/daily-executive-brief.json",
                "tmp/postmarket-snapshot.json",
            ],
            "owner_review_required": True,
        })
    if surface_almost != summary_almost:
        objects.append({
            "id": f"{window}:almost-contradiction",
            "object_type": "system",
            "category": "surface_contradiction",
            "signal_score": 78,
            "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
            "surface_state": "REVIEW REQUIRED",
            "escalation_reason": "Primary summary and deployment surface disagree on almost-deployable names.",
            "why_now": f"deployment surface={surface_almost or ['<none>']} vs primary summary={summary_almost or ['<none>']}",
            "recommended_next_step": "Review the summary surface before treating almost-deployable language as current.",
            "owner_question": "Did a trust gate, stale brief, or stale state summary create this mismatch?",
            "owner_reads": [
                "03. Portfolio/Execution Board.md",
                "03. Portfolio/Portfolio Snapshot.md",
            ],
            "supporting_artifacts": [
                "tmp/deployment-readiness-surface.json",
                "tmp/daily-executive-brief.json",
                "tmp/postmarket-snapshot.json",
            ],
            "owner_review_required": True,
        })
    return objects




def market_intelligence_review_objects(window: str, market_intelligence_events: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not market_intelligence_events:
        return []

    objects: list[dict[str, Any]] = []
    for event in market_intelligence_events.get("escalations") or []:
        if not isinstance(event, dict):
            continue
        route = str(event.get("recommended_route") or "")
        sleeve = str(event.get("ticker_or_macro_sleeve") or "").strip() or "SYSTEM"
        materiality = int(event.get("materiality_score") or 0)
        if materiality < 4 and event.get("urgency") != "today":
            continue
        score = 82 + min(12, materiality * 3)
        if route == "risk_review":
            score += 3
        objects.append({
            "id": f"{window}:market-intelligence:{event.get('rank') or sleeve.lower()}",
            "object_type": "market_intelligence_event",
            "ticker": None if sleeve in {"SYSTEM", "MACRO", "CREDIT", "BREADTH", "EARNINGS"} else sleeve,
            "category": "fresh_intelligence",
            "signal_score": max(0, min(99, score)),
            "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
            "surface_state": "REVIEW REQUIRED",
            "event_type": event.get("event_type"),
            "recommended_route": route,
            "urgency": event.get("urgency"),
            "materiality_score": materiality,
            "why_now": str(event.get("event_title") or ""),
            "evidence": clean_list(event.get("evidence")),
            "blockers": [str(event.get("blocked_reason"))] if event.get("blocked_reason") else [],
            "owner_question": f"Does this {route or 'review'} event change today's owner-gated review priorities?",
            "recommended_next_step": "Review the routed event packet before changing thesis, macro wording, deployment state, or capital posture.",
            "owner_reads": OWNER_LAYERS,
            "supporting_artifacts": ["tmp/market-intelligence-events-" + window + ".json"],
            "owner_review_required": True,
        })
    return objects


def fresh_intelligence_status_for(ticker: str, market_intelligence_events: dict[str, Any] | None) -> str:
    if not market_intelligence_events:
        return "not_wired_yet"
    relevant: list[dict[str, Any]] = []
    for event in market_intelligence_events.get("events") or []:
        if not isinstance(event, dict):
            continue
        if str(event.get("ticker_or_macro_sleeve") or "").upper() == ticker.upper():
            relevant.append(event)
    if not relevant:
        return "no_material_event_routed"
    top = min(relevant, key=lambda item: int(item.get("rank") or 9999))
    return f"{top.get('recommended_route')}:{top.get('urgency')}:materiality_{top.get('materiality_score')}"


def artifact_is_fresh_enough(doc: dict[str, Any] | None, max_age_hours: int = 30) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("status") == "blocked":
        return False
    raw = doc.get("generated_at_utc") or doc.get("generated_at")
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        generated = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600
    return age_hours <= max_age_hours


def sector_context_for_ticker(
    ticker: str,
    sector_board: dict[str, Any] | None,
    sector_correlation: dict[str, Any] | None,
) -> dict[str, Any]:
    ticker_upper = ticker.upper()
    board_fresh = artifact_is_fresh_enough(sector_board)
    corr_fresh = artifact_is_fresh_enough(sector_correlation)
    if not board_fresh and not corr_fresh:
        return {
            "status": "missing_or_stale_manual_fallback_required",
            "fresh_artifacts": [],
            "summary": "Sector/correlation context is not fresh enough for this packet; manual position-impact review required.",
        }

    fresh_artifacts: list[str] = []
    if board_fresh:
        fresh_artifacts.append("tmp/sector-expansion-board.json")
    if corr_fresh:
        fresh_artifacts.append("tmp/sector-correlation-check.json")

    fresh_sector_board = sector_board if board_fresh and isinstance(sector_board, dict) else None
    fresh_sector_correlation = sector_correlation if corr_fresh and isinstance(sector_correlation, dict) else None

    board_sector: dict[str, Any] | None = None
    if isinstance(fresh_sector_board, dict):
        for sector in fresh_sector_board.get("sectors") or []:
            if not isinstance(sector, dict):
                continue
            tickers = {str(t).upper() for t in ((sector.get("portfolio_exposure") or {}).get("tickers") or [])}
            tickers.update(str(c.get("ticker", "")).upper() for c in sector.get("tracked_universe_candidates") or [] if isinstance(c, dict))
            tickers.update(str(p.get("candidate", "")).upper() for p in sector.get("promotion_review_status") or [] if isinstance(p, dict))
            if ticker_upper in tickers:
                board_sector = sector
                break

    corr_context: dict[str, Any] | None = None
    if isinstance(fresh_sector_correlation, dict):
        for item in fresh_sector_correlation.get("promotion_impact_checks") or []:
            if isinstance(item, dict) and str(item.get("ticker") or "").upper() == ticker_upper:
                corr_context = item
                break
        if corr_context is None:
            for item in fresh_sector_correlation.get("tracked_universe_context") or []:
                if isinstance(item, dict) and str(item.get("ticker") or "").upper() == ticker_upper:
                    corr_context = item
                    break

    sector_name = (board_sector or {}).get("sector") or (corr_context or {}).get("candidate_sector") or (corr_context or {}).get("sector")
    warnings = []
    if board_sector:
        warnings.extend(str(w) for w in board_sector.get("warnings") or [])
    if corr_context:
        warnings.extend(str(w) for w in corr_context.get("warnings") or [])
    exposure = (board_sector or {}).get("portfolio_exposure") or {}
    return {
        "status": "available_review_only",
        "fresh_artifacts": fresh_artifacts,
        "sector": sector_name,
        "sector_etf": (board_sector or {}).get("ticker"),
        "leadership_status": (board_sector or {}).get("leadership_status"),
        "underexposed": (board_sector or {}).get("underexposed"),
        "sector_weight_pct": exposure.get("draft_weight_pct") or (corr_context or {}).get("current_sector_weight_pct"),
        "sector_cap_status": exposure.get("status") or (corr_context or {}).get("cap_status_after"),
        "promotion_review_status": (board_sector or {}).get("promotion_review_status") or [],
        "warnings": warnings[:4],
        "summary": f"{sector_name or 'Sector'} context available from fresh review-only sector artifacts; owner approval and sizing authority remain false.",
    }


def action_family_for(recommended_action: str) -> str:
    """Map existing recommendation classes into the WF42 deploy/wait/reject/review vocabulary."""
    if recommended_action == "deploy_candidate":
        return "deploy"
    if recommended_action in {"wait_for_band", "wait_for_catalyst_clearance", "extended_no_disciplined_entry"}:
        return "wait"
    if recommended_action in {"owner_decision_required", "owner_gated_band_review", "manual_review_required"}:
        return "review"
    if recommended_action in {"no_new_approval", "risk_hold"}:
        return "reject"
    return "review"


def evidence_provenance_for(item: dict[str, Any]) -> list[dict[str, str]]:
    artifacts = [str(path) for path in item.get("supporting_artifacts") or [] if str(path).strip()]
    default_artifact = artifacts[0] if artifacts else "unknown"
    provenance: list[dict[str, str]] = []
    for evidence in item.get("evidence") or []:
        text = str(evidence).strip()
        if not text:
            continue
        source_artifact = default_artifact
        if text.startswith("Band") or "band" in text.lower():
            source_artifact = "tmp/band-proposals.json" if "proposal" in text.lower() else "tmp/deployment-readiness-surface.json"
        if text.startswith("Trigger"):
            source_artifact = "tmp/deployment-readiness-surface.json"
        provenance.append({
            "claim": text,
            "source_artifact": source_artifact,
            "source_type": "workspace_artifact",
        })
    return provenance[:5]


def source_freshness_for_capital_packet(source_freshness: dict[str, Any] | None) -> dict[str, Any]:
    summary = source_freshness or {}
    sources = summary.get("sources") if isinstance(summary.get("sources"), list) else []
    degraded = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get("classification") not in {"fresh", "current"}:
            degraded.append({
                "source_key": source.get("source_key"),
                "classification": source.get("classification"),
                "confidence_ceiling": source.get("confidence_ceiling"),
            })
    return {
        "overall_classification": summary.get("overall_classification") or "unknown",
        "trust_level": summary.get("trust_level") or "unknown",
        "stop_line": bool(summary.get("stop_line")),
        "capital_action_allowed": False,
        "degraded_sources": degraded[:5],
    }


def missing_evidence_for_capital_packet(
    item: dict[str, Any],
    market_intelligence_events: dict[str, Any] | None,
    sector_context: dict[str, Any] | None = None,
    fundamental_context: dict[str, Any] | None = None,
    official_earnings_bridge: dict[str, Any] | None = None,
) -> list[str]:
    missing = [
        "state-history / owner-outcome retention is not wired; no predictive outcome score is available",
    ]
    if not sector_context or sector_context.get("status") != "available_review_only":
        missing.insert(0, "sector/correlation check artifact is missing or stale; treat as manual fallback before position-impact judgment")
    if not fundamental_context or fundamental_context.get("status") != "available_review_only":
        missing.insert(0, "WF65 full-picture fundamental/per-share context is missing; manual fundamental review required before capital judgment")
    elif fundamental_context.get("fundamental_data_quality") not in {"clean", "partial"}:
        missing.append(f"WF65 fundamental data quality is {fundamental_context.get('fundamental_data_quality')}; treat as manual review input only")
    if not official_earnings_bridge or official_earnings_bridge.get("status") != "available_review_only":
        missing.insert(0, "official earnings bridge / IR reconciliation context is missing; manual earnings-quality review required before capital judgment")
    elif official_earnings_bridge.get("manual_review_required") is True:
        missing.append("official earnings bridge remains manual-required; adjusted EPS, guidance, growth bridge, margin bridge, and management explanation need official-source review")
    ticker = str(item.get("ticker") or "")
    if fresh_intelligence_status_for(ticker, market_intelligence_events) == "not_wired_yet":
        missing.append("fresh-intelligence event packet unavailable for this window")
    return missing


def tracked_config_for_ticker(ticker: str, portfolio_config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(portfolio_config, dict):
        return {}
    ticker_upper = ticker.upper()
    tracked = portfolio_config.get("tracked_universe") or {}
    if isinstance(tracked, dict) and isinstance(tracked.get(ticker_upper), dict):
        return dict(tracked[ticker_upper])
    return {}


def entry_band_for_ticker(ticker: str, portfolio_config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(portfolio_config, dict):
        return {}
    bands = portfolio_config.get("entry_bands") or {}
    band = bands.get(ticker.upper()) if isinstance(bands, dict) else None
    return dict(band) if isinstance(band, dict) else {}


def fundamental_context_for_ticker(ticker: str, fundamental_metrics: dict[str, Any] | None) -> dict[str, Any]:
    ticker_upper = ticker.upper()
    if not isinstance(fundamental_metrics, dict):
        return {
            "status": "missing_artifact_manual_fallback_required",
            "summary": "WF65 fundamental metrics artifact is missing; manual full-picture review required before any capital decision.",
            "capital_action_allowed": False,
        }
    for row in fundamental_metrics.get("rows") or []:
        if not isinstance(row, dict) or str(row.get("ticker") or "").upper() != ticker_upper:
            continue
        sec = row.get("sec_reconciliation") or {}
        ir = row.get("company_ir_reconciliation") or {}
        return {
            "status": "available_review_only",
            "source_artifact": "tmp/fundamental-metrics-current.json",
            "fundamental_data_quality": row.get("data_quality"),
            "sec_reconciliation_status": sec.get("status") if isinstance(sec, dict) else None,
            "company_ir_reconciliation_status": ir.get("status") if isinstance(ir, dict) else None,
            "eps_yoy_pct": row.get("eps_yoy_pct"),
            "revenue_yoy_pct": row.get("revenue_yoy_pct"),
            "net_income_yoy_pct": row.get("net_income_yoy_pct"),
            "fcf_per_share": row.get("fcf_per_share"),
            "fcf_per_share_yoy_pct": row.get("fcf_per_share_yoy_pct"),
            "diluted_shares_yoy_pct": row.get("diluted_shares_yoy_pct"),
            "buyback_yield_pct": row.get("buyback_yield_pct"),
            "sbc_pct_of_revenue": row.get("sbc_pct_of_revenue"),
            "sbc_pct_of_fcf": row.get("sbc_pct_of_fcf"),
            "capital_return_to_fcf_pct": row.get("capital_return_to_fcf_pct"),
            "net_debt_issued": row.get("net_debt_issued"),
            "shareholder_yield_pct": row.get("shareholder_yield_pct"),
            "fcf_yield_pct": row.get("fcf_yield_pct"),
            "roic_proxy_pct": row.get("roic_proxy_pct"),
            "valuation_context": row.get("valuation_context"),
            "capital_allocation_quality": row.get("capital_allocation_quality"),
            "capital_allocation_notes": row.get("capital_allocation_notes") or [],
            "capital_allocation_anomalies": row.get("capital_allocation_anomalies") or [],
            "summary": "WF65 full-picture fundamental/per-share/capital-allocation context available as review-only evidence; no deployment or trade authority.",
            "capital_action_allowed": False,
        }
    return {
        "status": "missing_ticker_manual_fallback_required",
        "source_artifact": "tmp/fundamental-metrics-current.json",
        "summary": f"{ticker_upper} is missing from WF65 metrics; manual full-picture review required.",
        "capital_action_allowed": False,
    }


def official_earnings_bridge_for_ticker(ticker: str, fundamental_ir_packets: dict[str, Any] | None) -> dict[str, Any]:
    ticker_upper = ticker.upper()
    guards = {
        "capital_action_allowed": False,
        "deployment_authority_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }
    if not isinstance(fundamental_ir_packets, dict):
        return {
            "status": "missing_artifact_manual_fallback_required",
            "source_artifact": "tmp/fundamental-ir-reconciliation-packets.json",
            "ticker": ticker_upper,
            "manual_review_required": True,
            "summary": "Official earnings/IR reconciliation artifact is missing; manual official-source review required before capital judgment.",
            **guards,
        }
    for packet in fundamental_ir_packets.get("packets") or []:
        if not isinstance(packet, dict) or str(packet.get("ticker") or "").upper() != ticker_upper:
            continue
        bridge = packet.get("official_earnings_bridge") or {}
        adjusted = bridge.get("adjusted_eps") if isinstance(bridge, dict) else {}
        guidance = bridge.get("guidance") if isinstance(bridge, dict) else {}
        return {
            "status": "available_review_only",
            "source_artifact": "tmp/fundamental-ir-reconciliation-packets.json",
            "ticker": ticker_upper,
            "period_end": packet.get("period_end"),
            "comparison_period_end": packet.get("comparison_period_end"),
            "source_urls": packet.get("source_urls") or {},
            "official_evidence_status": bridge.get("official_evidence_status") if isinstance(bridge, dict) else "manual_required",
            "official_evidence_posture": bridge.get("official_evidence_posture") if isinstance(bridge, dict) else "review_only",
            "source_authority_level": bridge.get("source_authority_level") if isinstance(bridge, dict) else "official_company_ir_metadata_only",
            "source_freshness": bridge.get("source_freshness") if isinstance(bridge, dict) else {},
            "evidence_claims": bridge.get("evidence_claims") if isinstance(bridge, dict) else [],
            "unresolved_official_fields": bridge.get("unresolved_official_fields") if isinstance(bridge, dict) else [],
            "bank_native_metrics": bridge.get("bank_native_metrics") if isinstance(bridge, dict) else None,
            "sec_reconciliation_status": packet.get("sec_reconciliation_status"),
            "sec_conflicts": packet.get("sec_conflicts") or [],
            "bridge_status": bridge.get("status") if isinstance(bridge, dict) else "missing",
            "adjusted_eps_status": (adjusted or {}).get("status") or (packet.get("adjusted_eps_reconciliation") or {}).get("status") or "manual_required",
            "guidance_status": (guidance or {}).get("status") or (packet.get("guidance_reconciliation") or {}).get("status") or "manual_required",
            "growth_bridge": (bridge.get("growth_bridge") if isinstance(bridge, dict) else {}) or {},
            "segment_margins": (bridge.get("segment_margins") if isinstance(bridge, dict) else []) or [],
            "management_explanation": (bridge.get("management_explanation") if isinstance(bridge, dict) else {}) or {},
            "acquisition_debt_notes": (bridge.get("acquisition_debt_notes") if isinstance(bridge, dict) else {}) or {},
            "manual_review_required": True,
            "blockers": packet.get("blockers") or [],
            "summary": "Official earnings bridge is present as review-only context; adjusted EPS, guidance, growth bridge, segment margin, and management explanation remain manual-required until official capture.",
            "authority": packet.get("authority") or {},
            **guards,
        }
    return {
        "status": "missing_ticker_manual_fallback_required",
        "source_artifact": "tmp/fundamental-ir-reconciliation-packets.json",
        "ticker": ticker_upper,
        "manual_review_required": True,
        "summary": f"{ticker_upper} is missing from official earnings/IR reconciliation packets; manual official-source review required.",
        **guards,
    }


def holding_thesis_for_ticker(ticker: str, portfolio_config: dict[str, Any] | None) -> str:
    if not isinstance(portfolio_config, dict):
        return ""
    ticker_upper = ticker.upper()
    portfolio = portfolio_config.get("portfolio") or {}
    if not isinstance(portfolio, dict):
        return ""
    for sleeve in ("core", "tactical", "speculative"):
        rows = portfolio.get(sleeve) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker_upper:
                thesis = str(row.get("thesis") or "").strip()
                if thesis:
                    return thesis
    return ""


def thesis_text(ticker: str, tracked: dict[str, Any], portfolio_config: dict[str, Any] | None) -> str:
    thesis = str(tracked.get("thesis_status") or "").strip() or holding_thesis_for_ticker(ticker, portfolio_config)
    if thesis:
        return thesis
    return "Thesis not available in portfolio-config; manual thesis review required before any capital decision."


def setup_summary_text(item: dict[str, Any], tracked: dict[str, Any], band: dict[str, Any], guidance: str) -> str:
    band_label = str(band.get("label") or item.get("band_status") or item.get("band_position") or "entry band not defined").strip()
    trigger = str(tracked.get("trigger_condition") or guidance or "owner review required").strip()
    return (
        f"Current state: {legacy_state(item, "surface_state") or 'unknown'}. "
        f"Entry posture: {item.get('band_status') or item.get('band_position') or 'unknown'}; configured band: {band_label}. "
        f"Review trigger/guidance: {trigger}"
    )


def catalyst_risk_text(item: dict[str, Any], tracked: dict[str, Any], blockers: list[str]) -> str:
    days = item.get("days_to_earnings")
    earnings_policy = str(tracked.get("earnings_policy") or "").strip()
    catalyst_override = str(tracked.get("catalyst_blocker_override") or "").strip()
    if catalyst_override:
        return f"Catalyst blocker from portfolio-config: {catalyst_override}"
    if blockers:
        return "; ".join(str(blocker) for blocker in blockers[:3])
    if isinstance(days, int):
        if 0 <= days <= 21:
            return f"Earnings/catalyst window is close ({days} day(s)); keep review gated until timing risk clears."
        return f"No near-term earnings blocker surfaced in the artifact stack ({days} day(s) to earnings); manual catalyst review still required."
    if earnings_policy:
        return f"Earnings policy is {earnings_policy}; no current catalyst date was cleanly surfaced, so manual catalyst review is required."
    return "Manual catalyst review required; no clean catalyst-risk artifact was available for this packet."


def sizing_policy_context_for_tier(sizing_tier: str, portfolio_config: dict[str, Any] | None) -> str:
    """Return non-actionable sizing-policy context without per-name ranges or maxes."""
    if not isinstance(portfolio_config, dict):
        return "Portfolio-config sizing policy unavailable; owner must consult canonical risk rules before any sizing decision."
    rules = portfolio_config.get("sizing_rules") or []
    if not isinstance(rules, list):
        return "Portfolio-config sizing rules are not readable; owner must consult canonical risk rules before any sizing decision."
    tier_head = sizing_tier.split()[0:2]
    tier_key = " ".join(tier_head).strip().lower()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_tier = str(rule.get("tier") or "").strip()
        if tier_key and tier_key in rule_tier.lower():
            return f"{rule_tier} sizing policy exists; owner must consult canonical risk rules before any sizing decision."
    return "No matching sizing policy label found; manual sizing review required before any capital decision."


def why_stack_for_capital_packet(
    item: dict[str, Any],
    *,
    tracked: dict[str, Any],
    band: dict[str, Any],
    thesis: str,
    setup_summary: str,
    catalyst_risk: str,
    fundamental_context: dict[str, Any],
    official_earnings_bridge: dict[str, Any],
    sector_context: dict[str, Any],
    missing_evidence: list[str],
) -> dict[str, Any]:
    ticker = str(item.get("ticker") or "UNKNOWN")
    band_label = band.get("label") or item.get("band_status") or item.get("band_position") or "manual band review required"
    fundamental_status = fundamental_context.get("status") or "missing_manual_review_required"
    official_status = official_earnings_bridge.get("status") or "missing_manual_review_required"
    official_evidence_status = official_earnings_bridge.get("official_evidence_status") or "manual_required"
    official_evidence_posture = official_earnings_bridge.get("official_evidence_posture") or "review_only"
    guidance_status = official_earnings_bridge.get("guidance_status") or "manual_required"
    adjusted_status = official_earnings_bridge.get("adjusted_eps_status") or "manual_required"
    unresolved_fields = official_earnings_bridge.get("unresolved_official_fields") or []
    unresolved_text = ", ".join(str(field) for field in unresolved_fields[:7]) if isinstance(unresolved_fields, list) else "manual-required official fields"
    sector_status = sector_context.get("status") or "manual_review_required"
    blocker = "; ".join(str(x) for x in (item.get("blockers") or [])[:3]) or "No ticker-specific blocker surfaced; owner must still verify stop/invalidation layers."
    missing = "; ".join(str(x) for x in missing_evidence[:3]) or "No major missing-evidence line surfaced; owner review remains required."
    return {
        "setup_reason": f"{ticker} surfaced from ranked daily review because current state is {legacy_state(item, "surface_state") or 'unknown'} and recommendation class is {item.get('recommendation_class') or 'unknown'}.",
        "entry_reason": f"Entry context is {item.get('band_status') or item.get('band_position') or 'unknown'} against configured band {band_label}; this is setup context, not approval.",
        "fundamental_reason": f"WF65 fundamental context status is {fundamental_status}; thesis context: {thesis[:220]}",
        "official_earnings_reason": f"Official earnings bridge status is {official_status}; official evidence={official_evidence_status}/{official_evidence_posture}; adjusted EPS={adjusted_status}, guidance={guidance_status}; unresolved official fields remain manual-required: {unresolved_text}.",
        "sector_macro_reason": f"Sector/macro context is {sector_status}; macro gate is {item.get('macro_gate') or 'manual review required'}.",
        "risk_blocker_reason": f"Risk/catalyst blocker context: {catalyst_risk}; blockers: {blocker}",
        "missing_evidence_reason": missing,
        "authority_boundary": "Review-only rationale; no owner approval, portfolio mutation, deployment-state mutation, external financial, account, cash, or execution authority is granted.",
        "source_summary": setup_summary,
    }


def sizing_risk_envelope(
    item: dict[str, Any],
    tracked: dict[str, Any],
    band: dict[str, Any],
    portfolio_config: dict[str, Any] | None,
) -> dict[str, Any]:
    sizing_tier = str(tracked.get("sizing_tier") or "manual sizing review required").strip()
    risk_thresholds = (portfolio_config or {}).get("risk_thresholds") if isinstance(portfolio_config, dict) else {}
    if not isinstance(risk_thresholds, dict):
        risk_thresholds = {}
    sizing_policy_context = sizing_policy_context_for_tier(sizing_tier, portfolio_config)
    stop_label = str(band.get("stop_label") or band.get("stop") or "manual stop/invalidation review required").strip()
    return {
        "portfolio_role": tracked.get("portfolio_role") or "manual role review required",
        "sizing_tier": sizing_tier,
        "sizing_policy_context": sizing_policy_context,
        "risk_thresholds": {
            "max_single_position_normal_pct": risk_thresholds.get("max_single_position_normal"),
            "max_single_position_stretch_pct": risk_thresholds.get("max_single_position_stretch"),
            "max_sector_pct": risk_thresholds.get("max_sector_pct"),
            "min_cash_pct": risk_thresholds.get("min_cash_pct"),
            "drawdown_review_trigger_pct": risk_thresholds.get("drawdown_review_trigger_pct"),
        },
        "entry_band": band.get("label") or item.get("band_status") or item.get("band_position") or "manual band review required",
        "stop_or_invalidation": stop_label,
        "review_boundary": "Owner-gated risk envelope only; no dollar/share amount, portfolio mutation, deployment-state mutation, or trade execution authority.",
    }


def scenario_texts(
    item: dict[str, Any],
    tracked: dict[str, Any],
    thesis: str,
    catalyst_risk: str,
    guidance: str,
    band: dict[str, Any],
) -> dict[str, str]:
    macro_fit = str(tracked.get("macro_fit") or item.get("macro_gate") or "macro fit requires review").strip()
    trigger = str(tracked.get("trigger_condition") or guidance or "owner review required").strip()
    stop = str(band.get("stop_label") or band.get("stop") or "written invalidation layer").strip()
    return {
        "base_case": f"Base case: {thesis}; setup stays review-worthy only if current state and macro fit remain intact ({macro_fit}) and the owner-gated trigger is respected: {trigger}",
        "bull_case": f"Bull case: setup improves if price/structure confirms the written trigger without chasing, macro fit remains supportive, and catalyst risk clears: {catalyst_risk}",
        "bear_case": f"Bear case: defer or reject if the setup violates the stop/invalidation layer ({stop}), catalyst risk worsens, macro fit deteriorates, or blockers remain unresolved.",
    }

def ranked_escalations(review_objects: list[dict[str, Any]], system: dict[str, Any]) -> list[dict[str, Any]]:
    budget = 2 if system["stop_line"] else 3 if system["trust_level"] != "clean" else 4
    counts_by_category: dict[str, int] = {}
    selected: list[dict[str, Any]] = []

    def maybe_add(item: dict[str, Any]) -> None:
        category = str(item.get("category") or "")
        limit = 1 if category in {"trust_ceiling", "surface_contradiction"} else 2
        if counts_by_category.get(category, 0) >= limit:
            return
        selected.append(item)
        counts_by_category[category] = counts_by_category.get(category, 0) + 1

    for item in review_objects:
        if str(item.get("category") or "") in {"trust_ceiling", "surface_contradiction"}:
            maybe_add(item)
            if len(selected) >= budget:
                return selected[:budget]

    for item in review_objects:
        if item in selected:
            continue
        maybe_add(item)
        if len(selected) >= budget:
            break
    return selected



def capital_recommendations(
    review_objects: list[dict[str, Any]],
    system: dict[str, Any],
    market_intelligence_events: dict[str, Any] | None = None,
    source_freshness: dict[str, Any] | None = None,
    sector_board: dict[str, Any] | None = None,
    sector_correlation: dict[str, Any] | None = None,
    portfolio_config: dict[str, Any] | None = None,
    fundamental_metrics: dict[str, Any] | None = None,
    fundamental_ir_packets: dict[str, Any] | None = None,
    band_proposals: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    disciplined_bands = load_disciplined_bands()
    prop_index = disciplined_proposal_index(band_proposals or {})
    recommendations: list[dict[str, Any]] = []
    for item in review_objects:
        if item.get("object_type") != "ticker":
            continue
        if item.get("category") not in CAPITAL_CANDIDATE_CATEGORIES:
            continue
        rec_class = str(item.get("recommendation_class") or "")
        action = rec_class
        if rec_class == "conditional_pullback_review":
            action = "owner_decision_required" if item.get("band_status") == "IN_BAND" else "wait_for_band"
        elif rec_class == "review_for_possible_add":
            action = "deploy_candidate"
        elif rec_class == "hold_promotion_review":
            action = "hold_promotion_review"
        elif rec_class == "wait_for_catalyst_clearance":
            action = "wait_for_catalyst_clearance"
        elif rec_class == "wait_for_band":
            action = "wait_for_band"
        else:
            action = "no_new_approval"

        # Disciplined no-chase gate: bind the deployable slate to the fixed disciplined
        # band (SQL-canon companion table), not the price-chasing tracking band. A name
        # extended > threshold above the disciplined high is auto-dropped to watch.
        _dt = str(item.get("ticker") or "").upper()
        _drow = disciplined_bands.get(_dt)
        _dprop = prop_index.get(_dt) or {}
        extension_gate = extension_assessment(_dprop.get("close"), _drow, _dprop.get("atr14"))
        staleness_alert = staleness_assessment(_drow, price=_dprop.get("close"), atr14=_dprop.get("atr14"))
        if extension_gate.get("auto_drop") and action == "deploy_candidate":
            action = "extended_no_disciplined_entry"

        guidance = item.get("recommended_next_step") or "owner review required"
        if system["trust_level"] != "clean" and action == "deploy_candidate":
            guidance = f"Trust ceiling applies: {guidance}"
        if action == "extended_no_disciplined_entry":
            guidance = f"No-chase gate (disciplined band): {extension_gate.get('reason')}"

        risk_invalidation = item.get("blockers") or []
        sector_context = sector_context_for_ticker(str(item.get("ticker") or ""), sector_board, sector_correlation)
        ticker = str(item.get("ticker") or "")
        fundamental_context = fundamental_context_for_ticker(ticker, fundamental_metrics)
        official_earnings_bridge = official_earnings_bridge_for_ticker(ticker, fundamental_ir_packets)
        missing_evidence = missing_evidence_for_capital_packet(item, market_intelligence_events, sector_context, fundamental_context, official_earnings_bridge)
        tracked = tracked_config_for_ticker(ticker, portfolio_config)
        band = entry_band_for_ticker(ticker, portfolio_config)
        thesis = thesis_text(ticker, tracked, portfolio_config)
        setup_summary = setup_summary_text(item, tracked, band, str(guidance))
        catalyst_risk = catalyst_risk_text(item, tracked, risk_invalidation)
        scenarios = scenario_texts(item, tracked, thesis, catalyst_risk, str(guidance), band)
        why_stack = why_stack_for_capital_packet(
            item,
            tracked=tracked,
            band=band,
            thesis=thesis,
            setup_summary=setup_summary,
            catalyst_risk=catalyst_risk,
            fundamental_context=fundamental_context,
            official_earnings_bridge=official_earnings_bridge,
            sector_context=sector_context,
            missing_evidence=missing_evidence,
        )
        recommendations.append({
            "ticker": item.get("ticker"),
            "current_state": legacy_state(item, "surface_state"),
            "entry_band_status": item.get("band_status") or item.get("band_position"),
            "proposal_band_status": item.get("proposal_band_status"),
            "raw_band_status": item.get("raw_band_status"),
            "band_status_note": item.get("band_status_note"),
            "macro_regime_check": item.get("macro_gate"),
            "thesis": thesis,
            "setup_summary": setup_summary,
            "decision_rationale": why_stack,
            "why_stack": why_stack,
            "catalyst_risk": catalyst_risk,
            "sizing_risk_envelope": sizing_risk_envelope(item, tracked, band, portfolio_config),
            "base_case": scenarios["base_case"],
            "bull_case": scenarios["bull_case"],
            "bear_case": scenarios["bear_case"],
            "fresh_intelligence_status": fresh_intelligence_status_for(str(item.get("ticker") or ""), market_intelligence_events),
            "fundamental_context": fundamental_context,
            "official_earnings_bridge": official_earnings_bridge,
            "sector_correlation_check": sector_context.get("status"),
            "sector_context": sector_context,
            "state_history_status": "missing_artifact_manual_fallback_required",
            "risk_invalidation": risk_invalidation,
            "risk_invalidation_summary": "; ".join(str(x) for x in risk_invalidation) or "No ticker-specific blocker surfaced; owner must still verify stop/invalidation layers.",
            "recommended_action": action,
            "recommendation_class": rec_class,
            "recommendation_action": action_family_for(action),
            "action_vocabulary": "WF42 deploy/wait/reject/review; existing recommended_action retained for compatibility.",
            "disciplined_extension_gate": extension_gate,
            "disciplined_staleness_alert": staleness_alert,
            "confidence": "moderate" if item.get("signal_score", 0) >= 75 else "guarded",
            "confidence_basis": "Heuristic-only qualitative confidence; uncalibrated, non-predictive, and not_probability.",
            "signal_score_basis": item.get("signal_score_basis") or "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
            "trust_level": system.get("trust_level"),
            "source_freshness": source_freshness_for_capital_packet(source_freshness),
            "evidence": item.get("evidence") or [],
            "evidence_provenance": evidence_provenance_for(item),
            "missing_evidence": missing_evidence,
            "blocked_reasons": risk_invalidation + missing_evidence,
            "owner_approval_required": True,
            "owner_approval_granted": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "trust_ceiling": system.get("trust_ceiling_reasons"),
            "guidance": guidance,
            "required_owner_reads": item.get("owner_reads"),
        })

    recommendations.sort(key=lambda item: (0 if item["recommended_action"] == "deploy_candidate" else 1, item.get("ticker") or ""))

    portfolio_call = {
        "recommended_action": "no_new_approval",
        "owner_approval_required": True,
        "reason": "No clean capital-deployment candidate surfaced.",
    }
    if system["stop_line"] or system["critical"] > 0:
        portfolio_call = {
            "recommended_action": "no_new_approval",
            "owner_approval_required": True,
            "reason": "Workflow stop line or critical trust issue blocks capital-deployment approval.",
        }
    else:
        for item in recommendations:
            if item["recommended_action"] == "deploy_candidate":
                portfolio_call = {
                    "recommended_action": "owner_review_top_candidates",
                    "owner_approval_required": True,
                    "reason": "One or more names merit owner-gated deployment review, but nothing is autonomous.",
                }
                break
        else:
            if recommendations:
                portfolio_call = {
                    "recommended_action": "wait_for_better_entry_or_clearance",
                    "owner_approval_required": True,
                    "reason": "Candidates exist, but timing / band / trust gates still argue for wait-state discipline.",
                }
    return recommendations, portfolio_call



def known_gaps() -> list[str]:
    return [
        "Fresh-intelligence routing is now artifact-derived v1 only; it does not perform freeform web/news crawling or autonomous thesis updates.",
        "Sector/correlation checks are consumed when fresh enough; if absent, stale, or blocked they stay a manual fallback.",
        "Official earnings bridge / IR reconciliation context is review-only and manual where unresolved; it does not grant capital, deployment, note-mutation, or trade authority.",
        "State-history / owner-outcome retention is not yet wired, so this layer does not score realized outcomes or predictive labels.",
        "Generated recommendation packets stay non-self-applying; exact validator-backed portfolio note/model writes require an approved gated apply artifact.",
    ]



def build_packet(window: str) -> dict[str, Any]:
    spec = WINDOW_SPECS[window]
    required_records = {name: artifact_record(path, required=True) for name, path in spec["required"].items()}
    optional_records = {name: artifact_record(path, required=False) for name, path in spec["optional"].items()}
    source_freshness = summarize_source_freshness([
        {**record["source_state"], "source_key": name}
        for name, record in {**required_records, **optional_records}.items()
    ])

    required = {name: load_json(path, required=True) for name, path in spec["required"].items()}
    optional = {name: load_json(path, required=False) for name, path in spec["optional"].items()}

    primary_summary = required.get("primary_summary") or optional.get("primary_summary")
    deployment_surface = required["deployment_surface"]
    deployment_check = required["deployment_check"]
    validation = required["dashboard_validation"]
    run_summary = required["run_summary"]
    band_proposals = required["band_proposals"]

    system = system_block(run_summary, validation, deployment_surface, primary_summary)

    review_objects: list[dict[str, Any]] = []
    system_object = build_system_review_object(system)
    if system_object:
        review_objects.append(system_object)
    market_intelligence_events = optional.get("market_intelligence_events")
    review_objects.extend(ticker_review_objects(window, deployment_surface, deployment_check, band_proposals, system))
    review_objects.extend(market_intelligence_review_objects(window, market_intelligence_events))
    review_objects.extend(contradiction_objects(window, deployment_surface, primary_summary))
    review_objects.sort(key=lambda item: (-int(item.get("signal_score", 0)), str(item.get("ticker") or item.get("id") or "")))
    for idx, item in enumerate(review_objects, start=1):
        item["rank"] = idx

    escalations = ranked_escalations(review_objects, system)
    capital_packets, portfolio_call = capital_recommendations(
        review_objects,
        system,
        market_intelligence_events,
        source_freshness,
        optional.get("sector_expansion_board"),
        optional.get("sector_correlation_check"),
        optional.get("portfolio_config"),
        optional.get("fundamental_metrics"),
        optional.get("fundamental_ir_packets"),
        band_proposals,
    )

    disciplined_staleness_alerts = build_staleness_alert_payload(
        load_disciplined_bands(),
        disciplined_proposal_index(band_proposals),
        window=window,
    )

    top_tickers = [item.get("ticker") for item in escalations if item.get("ticker")]
    market_state = required.get("market_state") or optional.get("market_state") or {}
    market_data_as_of = str((primary_summary or {}).get("market_data_as_of") or (market_state.get("last_trading_day") or "unknown"))
    note_date = str((primary_summary or {}).get("brief_date") or (primary_summary or {}).get("snapshot_date") or market_data_as_of)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "review_window": spec["review_window"],
        "consumer_posture": "review_only",
        "canonical_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "deployment_state_mutation_allowed": False,
        "trade_execution_allowed": False,
        "owner_approval_required_for_capital": True,
        "owner_approval_granted": False,
        "market_data_as_of": market_data_as_of,
        "note_date": note_date,
        "owner_layers": OWNER_LAYERS,
        "source_artifacts": {
            "required": required_records,
            "optional": optional_records,
        },
        "source_freshness": source_freshness,
        "system": system,
        "summary": {
            "review_object_count": len(review_objects),
            "escalated_count": len(escalations),
            "capital_recommendation_count": len(capital_packets),
            "top_tickers": top_tickers,
            "portfolio_call": portfolio_call,
        },
        "review_objects": review_objects,
        "escalations": escalations,
        "capital_deployment_recommendations": capital_packets,
        "disciplined_band_staleness_alerts": disciplined_staleness_alerts,
        "known_gaps": known_gaps(),
        "promotion_rule": "This packet may rank and recommend, but it may not mutate canonical notes, change deployment state, or trigger execution.",
    }



def main() -> int:
    args = parse_args()
    packet = build_packet(args.window)
    output_path = WINDOW_SPECS[args.window]["output"]
    atomic_write_json(output_path, packet)
    staleness = packet.get("disciplined_band_staleness_alerts")
    if staleness:
        atomic_write_json(TMP / "disciplined-band-staleness-alerts.json", staleness)
    print(json.dumps({
        "status": "ok",
        "window": args.window,
        "output": str(output_path.relative_to(WORKSPACE)).replace('\\', '/'),
        "review_object_count": packet["summary"]["review_object_count"],
        "escalated_count": packet["summary"]["escalated_count"],
        "capital_recommendation_count": packet["summary"]["capital_recommendation_count"],
        "portfolio_call": packet["summary"]["portfolio_call"]["recommended_action"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
