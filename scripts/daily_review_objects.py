from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from source_freshness_classifier import classify_source_state, summarize_source_freshness

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SCHEMA_VERSION = 1
OWNER_LAYERS = [
    "03. Portfolio/Deployment Trigger Sheet.md",
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
            "post_earnings_prep": TMP / "post-earnings-prep.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
            "market_intelligence_events": TMP / "market-intelligence-events-morning.json",
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
            "earnings_calendar": TMP / "earnings-calendar.json",
            "market_intelligence_events": TMP / "market-intelligence-events-post-close.json",
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
            "market_state": TMP / "market-state.json",
            "primary_summary": TMP / "daily-executive-brief.json",
            "snapshot": TMP / "postmarket-snapshot.json",
            "market_intelligence_events": TMP / "market-intelligence-events-post-earnings.json",
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
            "earnings_calendar": TMP / "earnings-calendar.json",
            "market_intelligence_events": TMP / "market-intelligence-events-sunday.json",
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



def category_for(surface_record: dict[str, Any], deployment_record: dict[str, Any] | None, proposal: dict[str, Any] | None) -> str:
    state = str(surface_record.get("surface_state") or "")
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
    state = str(surface_record.get("surface_state") or "")
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



def recommended_next_step(ticker: str, rec_class: str) -> str:
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
    state = str(surface_record.get("surface_state") or "")
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
            owner_reads = list(OWNER_LAYERS)
            if category in {"review_debt", "risk_hold"}:
                owner_reads = [
                    "03. Portfolio/Deployment Trigger Sheet.md",
                    "03. Portfolio/Portfolio Snapshot.md",
                    "07. Risk/Risk Rules.md",
                ]

            objects.append({
                "id": f"{window}:{ticker.lower()}",
                "object_type": "ticker",
                "ticker": ticker,
                "category": category,
                "surface_state": surface_record.get("surface_state"),
                "machine_state": surface_record.get("machine_state"),
                "workflow_state": surface_record.get("workflow_state"),
                "signal_score": score,
                "days_to_earnings": surface_record.get("days_to_earnings"),
                "band_position": surface_record.get("band_position"),
                "band_status": proposal.get("band_status") if proposal else None,
                "band_stale": bool(surface_record.get("band_stale")),
                "canonical_apply_eligible": bool(proposal.get("canonical_apply_eligible")) if proposal else False,
                "macro_gate": surface_record.get("macro_gate") or system.get("macro_gate"),
                "recommendation_class": rec_class,
                "why_now": str(surface_record.get("why") or "") or str((deployment_record or {}).get("reason") or ""),
                "evidence": evidence_lines(surface_record, deployment_record, proposal),
                "blockers": blocker_lines(surface_record, proposal, system),
                "owner_question": owner_question(ticker, category),
                "recommended_next_step": recommended_next_step(ticker, rec_class),
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
            "surface_state": "REVIEW REQUIRED",
            "escalation_reason": "Primary summary and deployment surface disagree on deployable-now state.",
            "why_now": f"deployment surface={surface_deployable or ['<none>']} vs primary summary={summary_deployable or ['<none>']}",
            "recommended_next_step": "Review the summary surface before treating deployable-now language as authoritative.",
            "owner_question": "Is this a stale summary surface, a trust downgrade, or a deeper state contradiction?",
            "owner_reads": [
                "03. Portfolio/Deployment Trigger Sheet.md",
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
            "surface_state": "REVIEW REQUIRED",
            "escalation_reason": "Primary summary and deployment surface disagree on almost-deployable names.",
            "why_now": f"deployment surface={surface_almost or ['<none>']} vs primary summary={summary_almost or ['<none>']}",
            "recommended_next_step": "Review the summary surface before treating almost-deployable language as current.",
            "owner_question": "Did a trust gate, stale brief, or stale state summary create this mismatch?",
            "owner_reads": [
                "03. Portfolio/Deployment Trigger Sheet.md",
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


def action_family_for(recommended_action: str) -> str:
    """Map existing recommendation classes into the WF42 deploy/wait/reject/review vocabulary."""
    if recommended_action == "deploy_candidate":
        return "deploy"
    if recommended_action in {"wait_for_band", "wait_for_catalyst_clearance"}:
        return "wait"
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


def missing_evidence_for_capital_packet(item: dict[str, Any], market_intelligence_events: dict[str, Any] | None) -> list[str]:
    missing = [
        "sector/correlation check artifact is not wired; treat as manual fallback before position-impact judgment",
        "state-history / owner-outcome retention is not wired; no predictive outcome score is available",
    ]
    ticker = str(item.get("ticker") or "")
    if fresh_intelligence_status_for(ticker, market_intelligence_events) == "not_wired_yet":
        missing.append("fresh-intelligence event packet unavailable for this window")
    return missing

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
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for item in review_objects:
        if item.get("object_type") != "ticker":
            continue
        if item.get("category") not in CAPITAL_CANDIDATE_CATEGORIES:
            continue
        rec_class = str(item.get("recommendation_class") or "")
        action = rec_class
        if rec_class == "conditional_pullback_review":
            action = "wait_for_band"
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

        guidance = item.get("recommended_next_step") or "owner review required"
        if system["trust_level"] != "clean" and action == "deploy_candidate":
            guidance = f"Trust ceiling applies: {guidance}"

        risk_invalidation = item.get("blockers") or []
        missing_evidence = missing_evidence_for_capital_packet(item, market_intelligence_events)
        recommendations.append({
            "ticker": item.get("ticker"),
            "current_state": item.get("surface_state"),
            "entry_band_status": item.get("band_status") or item.get("band_position"),
            "macro_regime_check": item.get("macro_gate"),
            "fresh_intelligence_status": fresh_intelligence_status_for(str(item.get("ticker") or ""), market_intelligence_events),
            "sector_correlation_check": "missing_artifact_manual_fallback_required",
            "state_history_status": "missing_artifact_manual_fallback_required",
            "risk_invalidation": risk_invalidation,
            "risk_invalidation_summary": "; ".join(str(x) for x in risk_invalidation) or "No ticker-specific blocker surfaced; owner must still verify stop/invalidation layers.",
            "recommended_action": action,
            "recommendation_class": rec_class,
            "recommendation_action": action_family_for(action),
            "action_vocabulary": "WF42 deploy/wait/reject/review; existing recommended_action retained for compatibility.",
            "confidence": "moderate" if item.get("signal_score", 0) >= 75 else "guarded",
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
        "Sector/correlation checks are not yet exposed as a stable machine-readable artifact for this packet.",
        "State-history / owner-outcome retention is not yet wired, so this layer does not score realized outcomes or predictive labels.",
        "Canonical note mutation stays blocked; this packet is recommendation-only / review-only.",
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
    capital_packets, portfolio_call = capital_recommendations(review_objects, system, market_intelligence_events, source_freshness)

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
        "known_gaps": known_gaps(),
        "promotion_rule": "This packet may rank and recommend, but it may not mutate canonical notes, change deployment state, or trigger execution.",
    }



def main() -> int:
    args = parse_args()
    packet = build_packet(args.window)
    output_path = WINDOW_SPECS[args.window]["output"]
    atomic_write_json(output_path, packet)
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
