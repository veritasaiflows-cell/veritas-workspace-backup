from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
TECH_PATH = TMP / "technical-refresh.json"
BAND_PATH = TMP / "band-proposals.json"
READINESS_PATH = TMP / "deployment-readiness-surface.json"
DASHBOARD_VALIDATION_PATH = TMP / "dashboard-validation.json"
REGIME_PATH = TMP / "regime-scores.json"
HISTORY_PATH = WORKSPACE / "data" / "state-history" / "state-history-v1.jsonl"
OUT_PATH = TMP / "daily-price-trend-signals.json"
SCHEMA_VERSION = 1

AUTHORITY_FLAGS = {
    "consumer_posture": "review_only",
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "trade_execution_allowed": False,
    "owner_approval_required": True,
    "owner_approval_granted": False,
}

DIRECTIONAL_LABELS = {"improving", "weakening", "stable", "blocked", "unknown"}
DIRECTION_LABELS = {"increased", "decreased", "unchanged", "blocked", "unknown"}
SHORTLIST_GROUPS = {"PROMOTION REVIEW", "ALMOST DEPLOYABLE"}
FORBIDDEN_TEXT = {
    "win probability",
    "deploy probability",
    "deployment probability",
    "expected return",
    "model says buy",
    "model buy",
    "model add",
    "model trim",
    "model sell",
    "position size",
    "sizing recommendation",
    "tactical add",
    "disciplined size",
    "trade execution",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only daily price-trend signal artifact.")
    parser.add_argument("--window", default="post-close", help="Review window label; defaults to post-close.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_ref(path: Path, payload: dict[str, Any], *, required: bool) -> dict[str, Any]:
    rel = path.relative_to(WORKSPACE).as_posix()
    return {
        "path": rel,
        "required": required,
        "exists": path.exists(),
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status") or payload.get("overall_classification"),
    }


def history_status(path: Path = HISTORY_PATH) -> tuple[str, dict[str, Any] | None, str]:
    if not path.exists():
        return "missing", None, "state history file is missing; prior-state deltas remain unknown"
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:  # pragma: no cover - defensive filesystem boundary
        return "partial", None, f"state history file is unreadable: {exc}"
    if not lines:
        return "partial", None, "state history file is empty; prior-state deltas remain unknown"
    try:
        latest = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        return "partial", None, f"latest state history row is invalid JSON: {exc}"
    return "partial", latest, "state history exists, but prior-state delta consumption is not wired in WF51 Phase 2; deltas remain unknown"

def index_by_ticker(items: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        if ticker:
            out[ticker] = item
    return out


def readiness_records(readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    groups = readiness.get("groups") or {}
    for group_name, records in groups.items():
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            ticker = str(record.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            merged = dict(record)
            merged.setdefault("surface_state", group_name)
            merged["source_group"] = group_name
            out[ticker] = merged
    return out


def proposal_band_state(proposal: dict[str, Any], technical: dict[str, Any]) -> str:
    status = str(proposal.get("band_status") or "").strip().upper()
    if status:
        return status
    if technical.get("below_stop") is True:
        return "STOPPED_OUT"
    if technical.get("in_entry_band") is True:
        return "IN_BAND"
    if technical.get("in_entry_band") is False:
        return "OUTSIDE_BAND"
    return "UNKNOWN"


def extension_flag(close: Any, low: Any, high: Any) -> str:
    try:
        c = float(close)
    except (TypeError, ValueError):
        return "unknown"
    try:
        if high is not None and c > float(high):
            return "above_envelope"
        if low is not None and c < float(low):
            return "below_envelope"
    except (TypeError, ValueError):
        return "unknown"
    return "none"


def near_catalyst(days_to_earnings: Any) -> bool:
    return isinstance(days_to_earnings, int) and 0 <= days_to_earnings <= 21


def system_trust_degraded(validation: dict[str, Any]) -> bool:
    source_freshness = validation.get("source_freshness") or {}
    system_flags = {
        "overall_classification": source_freshness.get("overall_classification"),
        "trust_level": source_freshness.get("trust_level"),
        "presentation_allowed": source_freshness.get("presentation_allowed"),
        "capital_action_allowed": source_freshness.get("capital_action_allowed"),
    }
    return (
        system_flags["overall_classification"] in {"manual_dependency", "partial", "stale", "missing", "contradictory", "blocked"}
        or system_flags["trust_level"] in {"review_required", "blocked"}
        or system_flags["presentation_allowed"] is False
        or system_flags["capital_action_allowed"] is False
    )


def classify_trend_signal(surface: dict[str, Any], technical: dict[str, Any], proposal: dict[str, Any]) -> str:
    surface_state = str(legacy_state(surface, "surface_state") or surface.get("source_group") or "").upper()
    band_state = proposal_band_state(proposal, technical)
    band_position = str(surface.get("band_position") or "").lower()
    if surface_state == "DEPLOYABLE NOW":
        return "stable"
    if technical.get("below_stop") is True or band_state in {"STOPPED_OUT", "BELOW_STOP"} or surface_state in {"DO NOT TOUCH", "BLOCKED", "SYSTEM HOLD"}:
        return "blocked"
    if band_state in {"BELOW_BAND", "OUTSIDE_BAND"} or "below band" in band_position:
        return "weakening"
    if band_state in {"IN_BAND", "NEAR_BAND"} or surface_state == "PROMOTION REVIEW":
        return "improving"
    if surface_state == "ALMOST DEPLOYABLE" and "above band" not in str(surface.get("band_position") or "").lower():
        return "improving"
    if technical.get("above_ma20") and technical.get("above_ma50") and technical.get("above_ma200"):
        return "stable"
    if technical.get("close") is None:
        return "unknown"
    return "stable"


def macro_gate_degraded(surface: dict[str, Any]) -> bool:
    return str(surface.get("macro_gate") or "").strip().upper() == "DEGRADED"


def classify_readiness_direction(signal: str, surface: dict[str, Any], proposal: dict[str, Any], technical: dict[str, Any], *, trust_degraded: bool = False) -> str:
    if signal == "blocked":
        return "blocked"
    surface_state = str(legacy_state(surface, "surface_state") or surface.get("source_group") or "").upper()
    band_state = proposal_band_state(proposal, technical)
    band_position = str(surface.get("band_position") or "").lower()
    macro_capped = macro_gate_degraded(surface) or trust_degraded
    if surface_state == "DEPLOYABLE NOW":
        return "unchanged"
    if band_state in {"BELOW_BAND", "OUTSIDE_BAND"} or "below band" in band_position:
        return "decreased"
    if surface_state == "PROMOTION REVIEW" or band_state in {"IN_BAND", "NEAR_BAND"}:
        return "unchanged" if macro_capped else "increased"
    if technical.get("below_stop") is True or band_state in {"STOPPED_OUT", "BELOW_STOP"}:
        return "blocked"
    if band_state == "BELOW_BAND":
        return "decreased"
    if signal == "unknown":
        return "unknown"
    return "unchanged"


def current_state(surface: dict[str, Any], technical: dict[str, Any], proposal: dict[str, Any], regime: dict[str, Any]) -> dict[str, Any]:
    days_to_earnings = proposal.get("days_to_earnings", surface.get("days_to_earnings", regime.get("days_to_earnings")))
    return {
        "surface_state": legacy_state(surface, "surface_state") or surface.get("source_group") or "UNKNOWN",
        "workflow_state": legacy_state(surface, "workflow_state") or legacy_state(proposal, "workflow_state") or "UNKNOWN",
        "action_state": legacy_state(surface, "action_state") or legacy_state(surface, "machine_state") or "UNKNOWN",
        "band_position": surface.get("band_position") or regime.get("band_note") or "unknown",
        "band_status": proposal_band_state(proposal, technical),
        "in_entry_band": technical.get("in_entry_band"),
        "below_stop": technical.get("below_stop"),
        "trend_stack": proposal.get("trend_stack") or "unknown",
        "ma_posture": technical.get("ma_posture") or regime.get("ma_posture") or "unknown",
        "above_ma20": technical.get("above_ma20"),
        "above_ma50": technical.get("above_ma50"),
        "above_ma200": technical.get("above_ma200"),
        "price_vs_band_midpoint_pct": proposal.get("price_vs_band_midpoint_pct"),
        "distance_to_band_pct": proposal.get("distance_to_band_pct"),
        "atrp20": proposal.get("atrp20"),
        "sma_envelope_low": proposal.get("sma_envelope_low"),
        "sma_envelope_high": proposal.get("sma_envelope_high"),
        "extension_flag": extension_flag(technical.get("close"), proposal.get("sma_envelope_low"), proposal.get("sma_envelope_high")),
        "days_to_earnings": days_to_earnings,
        "earnings_state": proposal.get("earnings_state") or "UNKNOWN",
        "near_catalyst_flag": near_catalyst(days_to_earnings),
        "macro_gate": surface.get("macro_gate") or "UNKNOWN",
        "regime_total": regime.get("total"),
        "regime_stance": regime.get("stance"),
        "thesis_status": regime.get("thesis_status"),
        "macro_capped": macro_gate_degraded(surface),
        "confidence_ceiling": "review_required" if macro_gate_degraded(surface) else "clean_or_source_defined",
    }


def build_signal(ticker: str, technical: dict[str, Any], proposal: dict[str, Any], surface: dict[str, Any], regime: dict[str, Any], hist_status: str, *, trust_degraded: bool = False) -> dict[str, Any]:
    signal = classify_trend_signal(surface, technical, proposal)
    direction = classify_readiness_direction(signal, surface, proposal, technical, trust_degraded=trust_degraded)
    blockers: list[str] = []
    if technical.get("below_stop") is True or proposal_band_state(proposal, technical) in {"STOPPED_OUT", "BELOW_STOP"}:
        blockers.append("below_stop")
    if surface.get("band_stale") is True or proposal.get("needs_review") is True:
        blockers.append("band_review_required")
    if current_state(surface, technical, proposal, regime).get("near_catalyst_flag"):
        blockers.append("near_catalyst_review_required")
    if macro_gate_degraded(surface):
        blockers.append("macro_gate_degraded")
    if trust_degraded:
        blockers.append("system_trust_review_required")
    if hist_status != "available":
        blockers.append("prior_state_history_unavailable")

    evidence = [
        f"surface_state={legacy_state(surface, "surface_state") or surface.get('source_group') or 'UNKNOWN'}",
        f"band_status={proposal_band_state(proposal, technical)}",
        f"ma_posture={technical.get('ma_posture') or regime.get('ma_posture') or 'unknown'}",
    ]
    if surface.get("why"):
        evidence.append(str(surface.get("why")))

    signal_payload = {
        "ticker": ticker,
        "data_date": technical.get("data_date") or proposal.get("data_date") or "unknown",
        "close": technical.get("close", proposal.get("close", surface.get("close"))),
        "current_state": current_state(surface, technical, proposal, regime),
        "prior_state": {
            "source": "data/state-history/state-history-v1.jsonl" if hist_status == "available" else "none",
            "captured_at_utc": None,
            "close": None,
            "surface_state": None,
            "band_status": None,
            "trend_stack": None,
            "ma_posture": None,
            "in_entry_band": None,
            "below_stop": None,
        },
        "deltas": {
            "price_direction": "unknown",
            "band_status_direction": "unknown",
            "ma_stack_direction": "unknown",
            "surface_state_direction": "unknown",
            "stop_status_direction": "unknown",
            "catalyst_window_direction": "unknown",
        },
        "trend_signal": signal,
        "promotion_readiness_direction": direction,
        "evidence": evidence,
        "blockers": blockers,
        "source_artifacts": [
            "tmp/technical-refresh.json",
            "tmp/band-proposals.json",
            "tmp/deployment-readiness-surface.json",
        ],
        **AUTHORITY_FLAGS,
    }
    return signal_payload


def material_shortlist(readiness: dict[str, Any], signals_by_ticker: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups = readiness.get("groups") or {}
    shortlist: list[dict[str, Any]] = []
    for group in ("PROMOTION REVIEW", "ALMOST DEPLOYABLE"):
        for record in groups.get(group, []) or []:
            if not isinstance(record, dict):
                continue
            ticker = str(record.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            signal = signals_by_ticker.get(ticker) or {}
            entry_quality = signal.get("current_state", {}).get("band_status") or "UNKNOWN"
            shortlist.append({
                "ticker": ticker,
                "surface_state": legacy_state(record, "surface_state") or group,
                "source_group": group,
                "why_material": "material deployment-readiness shortlist name; see source artifact for raw context",
                "peer_or_opportunity_cost_context": "shortlist visibility retained for owner review; no promotion, allocation, or account action is authorized by this artifact",
                "entry_quality_status": entry_quality,
                "trend_signal": signal.get("trend_signal", "unknown"),
                "promotion_readiness_direction": signal.get("promotion_readiness_direction", "unknown"),
                "owner_action_required": "review only; explicit owner approval required before any promotion or deployment-state change",
                **AUTHORITY_FLAGS,
            })
    return shortlist


def build_payload(window: str = "post-close") -> dict[str, Any]:
    technical = load_json(TECH_PATH)
    bands = load_json(BAND_PATH)
    readiness = load_json(READINESS_PATH)
    validation = load_json(DASHBOARD_VALIDATION_PATH, required=False)
    regime = load_json(REGIME_PATH, required=False)

    hist_status, _latest_history, hist_note = history_status()
    trust_degraded = system_trust_degraded(validation)
    tech_by = index_by_ticker(technical.get("records") or [])
    proposal_by = index_by_ticker(bands.get("proposals") or [])
    surface_by = readiness_records(readiness)
    regime_by = index_by_ticker(regime.get("records") or [])
    tickers = sorted(set(tech_by) | set(proposal_by) | set(surface_by) | set(regime_by))

    signals = [
        build_signal(
            ticker,
            tech_by.get(ticker, {}),
            proposal_by.get(ticker, {}),
            surface_by.get(ticker, {}),
            regime_by.get(ticker, {}),
            hist_status,
            trust_degraded=trust_degraded,
        )
        for ticker in tickers
    ]
    signals_by_ticker = {item["ticker"]: item for item in signals}
    shortlist = material_shortlist(readiness, signals_by_ticker)

    summary = {
        "signal_count": len(signals),
        "improving_count": sum(1 for item in signals if item.get("trend_signal") == "improving"),
        "weakening_count": sum(1 for item in signals if item.get("trend_signal") == "weakening"),
        "stable_count": sum(1 for item in signals if item.get("trend_signal") == "stable"),
        "blocked_count": sum(1 for item in signals if item.get("trend_signal") == "blocked"),
        "unknown_count": sum(1 for item in signals if item.get("trend_signal") == "unknown"),
        "baseline_missing_count": sum(1 for item in signals if item.get("deltas", {}).get("price_direction") == "unknown"),
        "material_shortlist_count": len(shortlist),
        "promotion_review_shortlist_count": sum(1 for item in shortlist if item.get("source_group") == "PROMOTION REVIEW"),
        "almost_deployable_shortlist_count": sum(1 for item in shortlist if item.get("source_group") == "ALMOST DEPLOYABLE"),
        "top_improving_tickers": [
            item["ticker"] for item in signals
            if item.get("trend_signal") == "improving" and item.get("promotion_readiness_direction") == "increased"
        ][:8],
        "top_weakening_tickers": [item["ticker"] for item in signals if item.get("trend_signal") == "weakening"][:8],
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "window": window or "post-close",
        **AUTHORITY_FLAGS,
        "market_data_as_of": technical.get("last_trading_day") or "unknown",
        "history_status": hist_status,
        "history_note": hist_note,
        "source_artifacts": {
            "required": [
                file_ref(TECH_PATH, technical, required=True),
                file_ref(BAND_PATH, bands, required=True),
                file_ref(READINESS_PATH, readiness, required=True),
            ],
            "optional": [
                file_ref(DASHBOARD_VALIDATION_PATH, validation, required=False),
                file_ref(REGIME_PATH, regime, required=False),
                {
                    "path": HISTORY_PATH.relative_to(WORKSPACE).as_posix(),
                    "required": False,
                    "exists": HISTORY_PATH.exists(),
                    "status": hist_status,
                },
            ],
        },
        "source_freshness": validation.get("source_freshness") or {},
        "system_context": readiness.get("system") or {},
        "summary": summary,
        "material_shortlist": shortlist,
        "signals": signals,
        "allowed_directional_labels": {
            "trend_signal": sorted(DIRECTIONAL_LABELS),
            "readiness_direction": sorted(DIRECTION_LABELS),
        },
        "authority_boundary": "Read-only price-trend signal artifact for directional review support only. No canonical, portfolio, deployment-state, or trade action is authorized; explicit owner approval remains required and is not granted.",
    }
    validate_payload(payload)
    return payload


def walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for key, child in value.items():
            out.extend(walk_strings(key))
            out.extend(walk_strings(child))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for child in value:
            out.extend(walk_strings(child))
        return out
    return []


def validate_payload(payload: dict[str, Any]) -> None:
    for key, expected in AUTHORITY_FLAGS.items():
        if payload.get(key) != expected:
            raise ValueError(f"authority flag mismatch: {key}")
    for signal in payload.get("signals") or []:
        for key, expected in AUTHORITY_FLAGS.items():
            if signal.get(key) != expected:
                raise ValueError(f"signal authority flag mismatch for {signal.get('ticker')}: {key}")
        if signal.get("trend_signal") not in DIRECTIONAL_LABELS:
            raise ValueError(f"invalid trend_signal for {signal.get('ticker')}: {signal.get('trend_signal')}")
        if signal.get("promotion_readiness_direction") not in DIRECTION_LABELS:
            raise ValueError(f"invalid promotion_readiness_direction for {signal.get('ticker')}: {signal.get('promotion_readiness_direction')}")
        for value in (signal.get("deltas") or {}).values():
            if value not in DIRECTION_LABELS:
                raise ValueError(f"invalid delta direction for {signal.get('ticker')}: {value}")
    for item in payload.get("material_shortlist") or []:
        for key, expected in AUTHORITY_FLAGS.items():
            if item.get(key) != expected:
                raise ValueError(f"shortlist authority flag mismatch for {item.get('ticker')}: {key}")
    combined = "\n".join(walk_strings(payload)).lower()
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in combined:
            raise ValueError(f"forbidden authority/probability vocabulary present: {forbidden}")


def main() -> int:
    args = parse_args()
    payload = build_payload(args.window or "post-close")
    atomic_write_json(OUT_PATH, payload)
    print(f"wrote {OUT_PATH.relative_to(WORKSPACE)}")
    print(
        "signals={signals} shortlist={shortlist} history_status={history}".format(
            signals=payload["summary"]["signal_count"],
            shortlist=payload["summary"]["material_shortlist_count"],
            history=payload["history_status"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
