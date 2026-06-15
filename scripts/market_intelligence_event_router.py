from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from source_freshness_classifier import classify_source_state, summarize_source_freshness

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SCHEMA_VERSION = 1

WINDOW_SPECS: dict[str, dict[str, Any]] = {
    "morning": {
        "output": TMP / "market-intelligence-events-morning.json",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "market_state": TMP / "market-state.json",
            "band_proposals": TMP / "band-proposals.json",
        },
        "optional": {
            "earnings_calendar": TMP / "earnings-calendar.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
    "post-close": {
        "output": TMP / "market-intelligence-events-post-close.json",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "market_state": TMP / "market-state.json",
            "band_proposals": TMP / "band-proposals.json",
        },
        "optional": {
            "earnings_calendar": TMP / "earnings-calendar.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
    "post-earnings": {
        "output": TMP / "market-intelligence-events-post-earnings.json",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "band_proposals": TMP / "band-proposals.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
        },
        "optional": {
            "market_state": TMP / "market-state.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
    "sunday": {
        "output": TMP / "market-intelligence-events-sunday.json",
        "required": {
            "deployment_surface": TMP / "deployment-readiness-surface.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "market_state": TMP / "market-state.json",
            "band_proposals": TMP / "band-proposals.json",
        },
        "optional": {
            "earnings_calendar": TMP / "earnings-calendar.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
            "fundamental_metrics": TMP / "fundamental-metrics-current.json",
            "fundamental_metrics_validation": TMP / "fundamental-metrics-validation.json",
            "fundamental_ir_packets": TMP / "fundamental-ir-reconciliation-packets.json",
        },
    },
}

URGENCY_RANK = {"today": 0, "this_week": 1, "monitor": 2}
ROUTE_RANK = {
    "risk_review": 0,
    "deployment_review": 1,
    "promotion_review": 2,
    "thesis_review": 3,
    "weekly_review": 4,
    "no_route": 5,
}

SOURCE_TRUST_RANK = {
    "clean": 0,
    "review_required": 1,
    "blocked": 2,
}


def worse_source_trust(current: str, candidate: str) -> str:
    return candidate if SOURCE_TRUST_RANK.get(candidate, 9) > SOURCE_TRUST_RANK.get(current, 9) else current


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build read-only market-intelligence event/materiality packets from approved workspace artifacts.",
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
        owner_layer="artifact:market_intelligence_event_router.py",
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


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def as_of_date(*artifacts: dict[str, Any] | None) -> date:
    for artifact in artifacts:
        if not artifact:
            continue
        parsed = parse_date(artifact.get("last_trading_day") or artifact.get("as_of_date") or artifact.get("generated_at_utc"))
        if parsed:
            return parsed
    return datetime.now(timezone.utc).date()


def event_id(window: str, event_type: str, key: str) -> str:
    safe_key = "".join(ch.lower() if ch.isalnum() else "-" for ch in key).strip("-") or "system"
    return f"{window}:{event_type}:{safe_key}"


def make_event(
    *,
    window: str,
    event_type: str,
    ticker_or_macro_sleeve: str,
    source_tier: str,
    materiality_score: int,
    thesis_field_impacted: str,
    portfolio_surface_impacted: str,
    recommended_route: str,
    urgency: str,
    event_title: str,
    evidence: list[str],
    blocked_reason: str = "",
    source_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    materiality_score = max(0, min(5, int(materiality_score)))
    return {
        "event_id": event_id(window, event_type, f"{ticker_or_macro_sleeve}:{event_title}"),
        "ticker_or_macro_sleeve": ticker_or_macro_sleeve,
        "source_tier": source_tier,
        "source_trust": "review_required" if blocked_reason else "clean",
        "source_freshness": {
            "classification": "unknown",
            "trust_level": "review_required" if blocked_reason else "clean",
            "source_artifacts": source_artifacts or [],
            "issues": [],
        },
        "event_type": event_type,
        "materiality_score": materiality_score,
        "thesis_field_impacted": thesis_field_impacted,
        "portfolio_surface_impacted": portfolio_surface_impacted,
        "recommended_route": recommended_route,
        "urgency": urgency,
        "blocked_reason": blocked_reason,
        "owner_review_required": True,
        "event_title": event_title,
        "evidence": evidence[:5],
        "source_artifacts": source_artifacts or [],
        "canonical_mutation_allowed": False,
        "deployment_state_mutation_allowed": False,
        "trade_execution_allowed": False,
    }


def source_trust_for_classification(classification: str, *, stop_line: bool = False) -> str:
    if stop_line or classification in {"missing", "contradictory"}:
        return "blocked"
    if classification in {"fresh", "current"}:
        return "clean"
    return "review_required"


def enrich_event_source_context(events: list[dict[str, Any]], source_records: dict[str, dict[str, Any]]) -> None:
    records_by_path: dict[str, dict[str, Any]] = {}
    for record in source_records.values():
        records_by_path[str(record.get("path") or "")] = record

    for event in events:
        artifacts = [str(item) for item in event.get("source_artifacts") or [] if str(item).strip()]
        matched = [records_by_path[item] for item in artifacts if item in records_by_path]
        if not matched:
            continue

        worst_classification = "fresh"
        trust = "clean"
        issues: list[str] = []
        generated_at: list[str] = []
        for record in matched:
            source_state = record.get("source_state") or {}
            classification = str(source_state.get("classification") or record.get("classification") or "missing")
            if source_state.get("freshness_rank", 0) > {"fresh": 0, "current": 1, "manual_dependency": 2, "partial": 3, "stale": 4, "contradictory": 5, "missing": 6}.get(worst_classification, 9):
                worst_classification = classification
            trust = worse_source_trust(trust, source_trust_for_classification(classification, stop_line=bool(source_state.get("stop_line"))))
            issues.extend([str(item) for item in source_state.get("issues") or [] if str(item).strip()])
            if source_state.get("generated_at_utc"):
                generated_at.append(str(source_state.get("generated_at_utc")))

        event["source_trust"] = trust
        event["source_freshness"] = {
            "classification": worst_classification,
            "trust_level": trust,
            "source_artifacts": artifacts,
            "generated_at_utc": list(dict.fromkeys(generated_at)),
            "issues": list(dict.fromkeys(issues))[:5],
        }


def unresolved_truth_events(window: str, source_freshness: dict[str, Any]) -> list[dict[str, Any]]:
    if source_freshness.get("trust_level") == "clean":
        return []
    sources = [source for source in source_freshness.get("sources") or [] if isinstance(source, dict)]
    unresolved = [source for source in sources if source.get("classification") not in {"fresh", "current"}]
    if not unresolved:
        return []
    required_unresolved = [source for source in unresolved if source.get("required")]
    stop_line = bool(source_freshness.get("stop_line"))
    materiality = 5 if stop_line else 4 if required_unresolved else 3
    urgency = "today" if stop_line or required_unresolved else "this_week"
    names = [str(source.get("source_key") or source.get("path") or "unknown") for source in unresolved]
    issues: list[str] = []
    artifacts: list[str] = []
    for source in unresolved:
        artifacts.append(str(source.get("path") or ""))
        issues.append(f"{source.get('source_key')}: {source.get('classification')}")
        issues.extend([str(item) for item in source.get("issues") or [] if str(item).strip()])
    return [make_event(
        window=window,
        event_type="unresolved_truth",
        ticker_or_macro_sleeve="SYSTEM",
        source_tier="tier_1_workspace_artifact",
        materiality_score=materiality,
        thesis_field_impacted="source_truth",
        portfolio_surface_impacted="market-intelligence source trust gate",
        recommended_route="risk_review" if required_unresolved or stop_line else "weekly_review",
        urgency=urgency,
        event_title="Market-intelligence source truth requires owner review",
        evidence=list(dict.fromkeys(issues))[:5],
        blocked_reason="Unresolved source freshness/trust prevents treating routed events as clean; review required before any downstream interpretation.",
        source_artifacts=[item for item in dict.fromkeys(artifacts) if item],
    )]


def no_route_event(window: str) -> dict[str, Any]:
    return make_event(
        window=window,
        event_type="no_route",
        ticker_or_macro_sleeve="SYSTEM",
        source_tier="tier_1_workspace_artifact",
        materiality_score=0,
        thesis_field_impacted="none",
        portfolio_surface_impacted="none",
        recommended_route="no_route",
        urgency="monitor",
        event_title="No material market-intelligence route generated for this window",
        evidence=["Router found no material review events in approved workspace artifacts."],
        blocked_reason="",
        source_artifacts=[],
    )


def iter_surface_records(deployment_surface: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rows in (deployment_surface.get("groups") or {}).values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                records.append(row)
    return records


def dashboard_events(window: str, dashboard_validation: dict[str, Any], deployment_surface: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    summary = dashboard_validation.get("summary") or {}
    warning_codes = [str(x) for x in ((deployment_surface.get("system") or {}).get("warning_codes") or [])]
    critical = int(summary.get("critical", 0) or 0)
    warning = int(summary.get("warning", 0) or 0)
    if critical or warning or warning_codes:
        score = 5 if critical else 4
        urgency = "today" if critical or warning_codes else "this_week"
        events.append(make_event(
            window=window,
            event_type="risk",
            ticker_or_macro_sleeve="SYSTEM",
            source_tier="tier_1_workspace_artifact",
            materiality_score=score,
            thesis_field_impacted="trust_ceiling",
            portfolio_surface_impacted="dashboard/deployment-readiness trust gate",
            recommended_route="risk_review",
            urgency=urgency,
            event_title="Dashboard/deployment validation limits decision-grade confidence",
            evidence=[f"critical={critical}", f"warning={warning}", f"warning_codes={warning_codes or []}"],
            blocked_reason="Resolve or explicitly accept trust warnings before treating recommendations as clean.",
            source_artifacts=["tmp/dashboard-validation.json", "tmp/deployment-readiness-surface.json"],
        ))
    return events


def macro_events(window: str, market_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not market_state:
        return []
    events: list[dict[str, Any]] = []
    warnings = [str(x) for x in market_state.get("warnings") or [] if str(x).strip()]
    data = market_state.get("data") or {}
    credit = data.get("credit") or {}
    breadth = data.get("breadth") or {}
    if warnings:
        events.append(make_event(
            window=window,
            event_type="macro",
            ticker_or_macro_sleeve="MACRO",
            source_tier="tier_1_workspace_artifact",
            materiality_score=3,
            thesis_field_impacted="market_data_freshness",
            portfolio_surface_impacted="macro regime / daily brief context",
            recommended_route="weekly_review",
            urgency="this_week",
            event_title="Macro artifact carries freshness or interpretation warnings",
            evidence=warnings,
            blocked_reason="Macro warning is context-only until owner review; no regime mutation is authorized.",
            source_artifacts=["tmp/market-state.json"],
        ))
    if str(credit.get("stress_regime") or "").lower() not in {"", "benign", "normal"}:
        events.append(make_event(
            window=window,
            event_type="rates",
            ticker_or_macro_sleeve="CREDIT",
            source_tier="tier_1_workspace_artifact",
            materiality_score=4,
            thesis_field_impacted="risk_discount_rate",
            portfolio_surface_impacted="macro gate / risk budget",
            recommended_route="risk_review",
            urgency="today",
            event_title="Credit stress regime is no longer benign",
            evidence=[json.dumps(credit, sort_keys=True)],
            blocked_reason="Credit stress must be reviewed before expanding risk.",
            source_artifacts=["tmp/market-state.json"],
        ))
    if str(breadth.get("participation_regime") or "").lower() in {"narrow", "weak", "deteriorating"}:
        events.append(make_event(
            window=window,
            event_type="sector",
            ticker_or_macro_sleeve="BREADTH",
            source_tier="tier_1_workspace_artifact",
            materiality_score=3,
            thesis_field_impacted="market_participation",
            portfolio_surface_impacted="risk budget / add discipline",
            recommended_route="weekly_review",
            urgency="this_week",
            event_title="Market breadth is weak enough to affect add discipline",
            evidence=[json.dumps(breadth, sort_keys=True)],
            blocked_reason="Breadth signal is context-only; no automatic portfolio posture change.",
            source_artifacts=["tmp/market-state.json"],
        ))
    return events


def deployment_events(window: str, deployment_surface: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in iter_surface_records(deployment_surface):
        ticker = str(row.get("ticker") or "").strip()
        state = str(legacy_state(row, "surface_state") or "")
        days = row.get("days_to_earnings")
        if state == "PROMOTION REVIEW":
            events.append(make_event(
                window=window,
                event_type="sector",
                ticker_or_macro_sleeve=ticker,
                source_tier="tier_1_workspace_artifact",
                materiality_score=4,
                thesis_field_impacted="promotion_candidate",
                portfolio_surface_impacted="deployment readiness / promotion review",
                recommended_route="promotion_review",
                urgency="today",
                event_title=f"{ticker} is in promotion review",
                evidence=[str(row.get("why") or ""), f"band_position={row.get('band_position')}", f"macro_gate={row.get('macro_gate')}"] ,
                blocked_reason="Owner approval required before deployable-now status or capital action.",
                source_artifacts=["tmp/deployment-readiness-surface.json"],
            ))
        elif state == "ALMOST DEPLOYABLE":
            urgency = "today" if isinstance(days, int) and 0 <= days <= 14 else "this_week"
            events.append(make_event(
                window=window,
                event_type="sector",
                ticker_or_macro_sleeve=ticker,
                source_tier="tier_1_workspace_artifact",
                materiality_score=3,
                thesis_field_impacted="setup_timing",
                portfolio_surface_impacted="deployment short list",
                recommended_route="deployment_review",
                urgency=urgency,
                event_title=f"{ticker} remains almost deployable",
                evidence=[str(row.get("why") or ""), f"band_position={row.get('band_position')}", str(row.get("catalyst_blocker") or "")],
                blocked_reason="Not a deployable-now authorization; keep as owner-gated setup review.",
                source_artifacts=["tmp/deployment-readiness-surface.json"],
            ))
        if bool(row.get("band_stale")):
            events.append(make_event(
                window=window,
                event_type="risk",
                ticker_or_macro_sleeve=ticker,
                source_tier="tier_1_workspace_artifact",
                materiality_score=4,
                thesis_field_impacted="technical_freshness",
                portfolio_surface_impacted="technical entry / invalidation sheet",
                recommended_route="risk_review",
                urgency="today",
                event_title=f"{ticker} has band-review debt",
                evidence=[str(row.get("why") or ""), f"band_position={row.get('band_position')}"],
                blocked_reason="Band staleness blocks clean deployment interpretation until reviewed.",
                source_artifacts=["tmp/deployment-readiness-surface.json", "tmp/dashboard-validation.json"],
            ))
    return events


def band_events(window: str, band_proposals: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for proposal in band_proposals.get("proposals") or []:
        if not isinstance(proposal, dict):
            continue
        ticker = str(proposal.get("ticker") or "").strip()
        if not ticker:
            continue
        if proposal.get("canonical_apply_eligible"):
            events.append(make_event(
                window=window,
                event_type="risk",
                ticker_or_macro_sleeve=ticker,
                source_tier="tier_1_workspace_artifact",
                materiality_score=3,
                thesis_field_impacted="technical_band_config",
                portfolio_surface_impacted="config-layer band proposal",
                recommended_route="deployment_review",
                urgency="this_week",
                event_title=f"{ticker} has native config-layer band update eligible under gates",
                evidence=[f"suggested_band={proposal.get('suggested_band_low')} to {proposal.get('suggested_band_high')}", f"suggested_stop={proposal.get('suggested_stop')}"] + [str(x) for x in proposal.get("reasons") or []],
                blocked_reason="Config-layer eligibility is not canonical note mutation and does not authorize trade execution.",
                source_artifacts=["tmp/band-proposals.json"],
            ))
        elif proposal.get("blocking_review"):
            events.append(make_event(
                window=window,
                event_type="risk",
                ticker_or_macro_sleeve=ticker,
                source_tier="tier_1_workspace_artifact",
                materiality_score=4,
                thesis_field_impacted="technical_band_config",
                portfolio_surface_impacted="deployment trust gate",
                recommended_route="risk_review",
                urgency="today",
                event_title=f"{ticker} has blocking band-review proposal",
                evidence=[str(x) for x in proposal.get("reasons") or []],
                blocked_reason="Blocking band review must be resolved before clean deployment interpretation.",
                source_artifacts=["tmp/band-proposals.json"],
            ))
    return events


def earnings_events(window: str, earnings_calendar: dict[str, Any] | None, ref_date: date) -> list[dict[str, Any]]:
    if not earnings_calendar:
        return []
    events: list[dict[str, Any]] = []
    for row in earnings_calendar.get("records") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip()
        earnings_date = parse_date(row.get("next_earnings_date"))
        if not ticker or not earnings_date:
            continue
        days = (earnings_date - ref_date).days
        if -2 <= days <= 14:
            source = str(row.get("source") or "unknown")
            source_class = str(row.get("date_source_class") or ("provider_estimate" if source.lower() == "yfinance" else "unknown"))
            primary_confirmed = bool(row.get("primary_confirmed"))
            events.append(make_event(
                window=window,
                event_type="earnings",
                ticker_or_macro_sleeve=ticker,
                source_tier="tier_3_provider_calendar" if source.lower() == "yfinance" else "tier_2_trusted",
                materiality_score=3 if days >= 0 else 2,
                thesis_field_impacted="catalyst_timing",
                portfolio_surface_impacted="deployment catalyst window",
                recommended_route="thesis_review" if days < 0 else "deployment_review",
                urgency="today" if days <= 3 else "this_week",
                event_title=f"{ticker} earnings catalyst window is active or near",
                evidence=[
                    f"next_earnings_date={earnings_date.isoformat()}",
                    f"days_to_earnings={days}",
                    f"source={source}",
                    f"date_source_class={source_class}",
                    f"primary_confirmed={primary_confirmed}",
                ],
                blocked_reason="Provider-calendar timing is not enough for autonomous thesis or deployment-state mutation; verify against IR when decision-critical.",
                source_artifacts=["tmp/earnings-calendar.json"],
            ))
    return events


def post_earnings_events(window: str, post_earnings_prep: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not post_earnings_prep:
        return []
    events: list[dict[str, Any]] = []
    status = str(post_earnings_prep.get("status") or "")
    warnings = [str(x) for x in post_earnings_prep.get("warnings") or [] if str(x).strip()]
    packets = [x for x in post_earnings_prep.get("packets") or [] if isinstance(x, dict)]
    if warnings:
        events.append(make_event(
            window=window,
            event_type="earnings",
            ticker_or_macro_sleeve="EARNINGS",
            source_tier="tier_1_workspace_artifact",
            materiality_score=3,
            thesis_field_impacted="post_earnings_freshness",
            portfolio_surface_impacted="post-earnings prep / note targeting",
            recommended_route="weekly_review",
            urgency="this_week",
            event_title="Post-earnings prep carries warnings",
            evidence=warnings,
            blocked_reason="Warnings are review-only and do not authorize note mutation.",
            source_artifacts=["tmp/post-earnings-prep.json"],
        ))
    for packet in packets:
        ticker = str(packet.get("ticker") or packet.get("symbol") or "").strip() or "EARNINGS"
        events.append(make_event(
            window=window,
            event_type="earnings",
            ticker_or_macro_sleeve=ticker,
            source_tier="tier_1_workspace_artifact",
            materiality_score=4,
            thesis_field_impacted="post_earnings_interpretation",
            portfolio_surface_impacted="post-earnings review queue",
            recommended_route="thesis_review",
            urgency="today",
            event_title=f"{ticker} has post-earnings review packet",
            evidence=[json.dumps(packet, sort_keys=True)[:500]],
            blocked_reason="Post-earnings packet requires owner review before thesis or deployment-state changes.",
            source_artifacts=["tmp/post-earnings-prep.json"],
        ))
    if status not in {"", "ok"} and not packets and not warnings:
        events.append(make_event(
            window=window,
            event_type="earnings",
            ticker_or_macro_sleeve="EARNINGS",
            source_tier="tier_1_workspace_artifact",
            materiality_score=2,
            thesis_field_impacted="post_earnings_freshness",
            portfolio_surface_impacted="post-earnings prep",
            recommended_route="weekly_review",
            urgency="monitor",
            event_title=f"Post-earnings prep status is {status}",
            evidence=[f"status={status}"],
            blocked_reason="Review-only status marker; no autonomous mutation.",
            source_artifacts=["tmp/post-earnings-prep.json"],
        ))
    return events


def fundamental_events(window: str, fundamental_metrics: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(fundamental_metrics, dict):
        return []
    events: list[dict[str, Any]] = []
    for row in fundamental_metrics.get("rows") or []:
        if not isinstance(row, dict) or row.get("instrument_type") != "equity":
            continue
        ticker = str(row.get("ticker") or "").strip()
        if not ticker:
            continue
        sec_status = str(((row.get("sec_reconciliation") or {}).get("status")) or "")
        ir_status = str(((row.get("company_ir_reconciliation") or {}).get("status")) or "")
        ca_quality = str(row.get("capital_allocation_quality") or "")
        anomalies = [item for item in row.get("capital_allocation_anomalies") or [] if isinstance(item, dict)]
        fcfps_yoy = row.get("fcf_per_share_yoy_pct")
        shares_yoy = row.get("diluted_shares_yoy_pct")
        sbc_fcf = row.get("sbc_pct_of_fcf")

        evidence: list[str] = []
        if sec_status == "conflict":
            evidence.append("SEC companyfacts conflict requires manual reconciliation")
        if ir_status in {"manual_required", "configured_manual_review_required"}:
            evidence.append(f"Company IR reconciliation status={ir_status}")
        if ca_quality in {"caution", "manual_review_required", "bank_manual_review"}:
            evidence.append(f"Capital allocation quality={ca_quality}")
        if row.get("fcf_interpretation") == "bank_structural":
            evidence.append("Bank sector: industrial FCF/share and debt-funded-return gates suppressed; use CET1/ROTCE/NIM/deposit/credit-quality review.")
        evidence.extend(str(item.get("message") or item.get("code")) for item in anomalies[:3])
        if row.get("fcf_interpretation") != "bank_structural" and isinstance(fcfps_yoy, (int, float)) and fcfps_yoy < -20:
            evidence.append(f"FCF/share YoY deteriorated {fcfps_yoy}%")
        if isinstance(shares_yoy, (int, float)) and shares_yoy > 3:
            evidence.append(f"Diluted share count rose {shares_yoy}%")
        if isinstance(sbc_fcf, (int, float)) and sbc_fcf > 25:
            evidence.append(f"SBC/FCF is elevated at {sbc_fcf}%")
        evidence = list(dict.fromkeys([item for item in evidence if item]))
        if not evidence:
            continue
        materiality = 4 if anomalies or sec_status == "conflict" or ca_quality in {"caution", "bank_manual_review"} else 3
        events.append(make_event(
            window=window,
            event_type="fundamental",
            ticker_or_macro_sleeve=ticker,
            source_tier="tier_2_aggregator_plus_sec_ir_review_gate",
            materiality_score=materiality,
            thesis_field_impacted="fundamental_quality_per_share_capital_allocation",
            portfolio_surface_impacted="WF65 full-picture ticker context / capital review evidence",
            recommended_route="thesis_review" if materiality >= 4 else "weekly_review",
            urgency="today" if materiality >= 4 else "this_week",
            event_title=f"{ticker} fundamental/per-share quality requires review",
            evidence=evidence[:5],
            blocked_reason="WF65 fundamental events are review-only evidence; they do not authorize deployment, portfolio mutation, approval, or trade execution.",
            source_artifacts=["tmp/fundamental-metrics-current.json", "tmp/fundamental-metrics-validation.json"],
        ))
    return events


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for event in events:
        existing = deduped.get(event["event_id"])
        if existing is None or int(event["materiality_score"]) > int(existing["materiality_score"]):
            deduped[event["event_id"]] = event
    ordered = sorted(
        deduped.values(),
        key=lambda item: (
            -int(item.get("materiality_score") or 0),
            URGENCY_RANK.get(str(item.get("urgency") or "monitor"), 9),
            ROUTE_RANK.get(str(item.get("recommended_route") or "no_route"), 9),
            str(item.get("ticker_or_macro_sleeve") or ""),
        ),
    )
    for idx, event in enumerate(ordered, start=1):
        event["rank"] = idx
    return ordered


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

    ref_date = as_of_date(required.get("market_state"), optional.get("earnings_calendar"), required.get("deployment_surface"))
    events: list[dict[str, Any]] = []
    events.extend(dashboard_events(window, required["dashboard_validation"], required["deployment_surface"]))
    events.extend(macro_events(window, required.get("market_state") or optional.get("market_state")))
    events.extend(deployment_events(window, required["deployment_surface"]))
    events.extend(band_events(window, required["band_proposals"]))
    events.extend(earnings_events(window, optional.get("earnings_calendar"), ref_date))
    events.extend(post_earnings_events(window, required.get("post_earnings_prep") or optional.get("post_earnings_prep")))
    events.extend(fundamental_events(window, optional.get("fundamental_metrics")))
    events.extend(unresolved_truth_events(window, source_freshness))
    ranked = sort_events(events)
    if not ranked:
        ranked = [no_route_event(window)]
    enrich_event_source_context(ranked, {**required_records, **optional_records})

    escalated = [event for event in ranked if int(event.get("materiality_score") or 0) >= 4 or event.get("urgency") == "today"][:5]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "consumer_posture": "review_only",
        "canonical_mutation_allowed": False,
        "deployment_state_mutation_allowed": False,
        "trade_execution_allowed": False,
        "owner_review_required": True,
        "source_artifacts": {"required": required_records, "optional": optional_records},
        "source_freshness": source_freshness,
        "summary": {
            "event_count": len(ranked),
            "escalated_count": len(escalated),
            "top_routes": sorted({str(event.get("recommended_route")) for event in escalated}),
            "top_tickers_or_sleeves": [event.get("ticker_or_macro_sleeve") for event in escalated],
        },
        "events": ranked,
        "escalations": escalated,
        "authority_boundary": "Read-only event/materiality router. It may rank and route review objects, but may not mutate thesis, portfolio state, canonical notes, config, or trades.",
    }


def main() -> int:
    args = parse_args()
    packet = build_packet(args.window)
    output_path = WINDOW_SPECS[args.window]["output"]
    atomic_write_json(output_path, packet)
    print(json.dumps({
        "status": "ok",
        "window": args.window,
        "output": str(output_path.relative_to(WORKSPACE)).replace("\\", "/"),
        "event_count": packet["summary"]["event_count"],
        "escalated_count": packet["summary"]["escalated_count"],
        "canonical_mutation_allowed": packet["canonical_mutation_allowed"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
