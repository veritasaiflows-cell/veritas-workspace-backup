#!/usr/bin/env python3
"""Build a review-only current-regime analog scenario panel.

This consumes the WF55 historical regime library and current WF61 small/mid
context, then emits scenario context for finance intelligence packets. It does
not emit probabilities, scores, rankings, expected-return claims, sizing,
capital approval, or execution authority.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

HISTORICAL_LIBRARY = TMP / "historical-regime-event-library.json"
WF61_FEED = TMP / "small-mid-cap-regime-feed.json"
OUT_JSON = TMP / "current-regime-analog-match.json"
OUT_MD = TMP / "current-regime-analog-match.md"

SCHEMA = "veritas.current_regime_analog_match.v1"

AUTHORITY: dict[str, bool] = {
    "review_only": True,
    "scenario_context_only": True,
    "base_rate_context_only": True,
    "calibrated_probability_allowed": False,
    "prediction_allowed": False,
    "scoring_model_allowed": False,
    "model_ranked_deployment_allowed": False,
    "return_projection_claim_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "capital_action_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inference_allowed": False,
}

DOWNSTREAM_CONSUMERS = [
    "tmp/macro-judgment-draft.json",
    "tmp/small-mid-cap-regime-feed.json",
    "tmp/wf78-small-mid-cap-scaleout-candidate-pass.json",
    "tmp/finance-market-deployment-operating-loop.json",
    "tmp/trade-grade-decision-cards.json",
]

FORBIDDEN_LANGUAGE_RE = re.compile(
    r"\b(win probability|expected return|model-ranked|% chance|trade approval|approved to buy|approved to sell|execute order|submit order|place trade)\b",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def fmt_pct(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.1f}%"


def current_tags(historical: dict[str, Any], wf61: dict[str, Any]) -> list[str]:
    tags = list(as_dict(historical.get("current_context")).get("current_analog_tags") or [])
    bucket_summary = as_dict(as_dict(wf61.get("summary")).get("bucket_summary"))
    small_improving: list[str] = []
    for key, value in bucket_summary.items():
        if str(key).startswith(("small_cap", "mid_cap")) and isinstance(value, dict):
            small_improving.extend(str(item) for item in value.get("improving") or [])
    if small_improving:
        tags.extend(["small_mid_broadening_review", "breadth_repair"])
    if "rate_stabilization" not in tags:
        tags.append("rate_stabilization")
    return sorted(set(str(tag) for tag in tags if tag))


def event_fit(event: dict[str, Any], tags: list[str]) -> tuple[str, str]:
    shocks = set(str(item) for item in event.get("shock_types") or [])
    event_id = str(event.get("event_id") or "")
    if "rate_stabilization" in shocks or "breadth_repair" in shocks or "soft_landing" in shocks:
        return "direct_current_theme", "Directly overlaps current rate-stabilization/breadth-repair thesis."
    if shocks.intersection({"rate_shock", "policy_tightening", "bond_selloff"}) and "rate_stabilization" in tags:
        return "rate_shock_precedent", "Rate-shock precedent for asking whether stabilization is enough to broaden risk appetite."
    if shocks.intersection({"credit_crisis", "banking_crisis", "credit_stress", "liquidity_shock"}):
        return "stress_caution", "Stress analog; useful for checking whether credit/liquidity risk would overpower a small/mid broadening thesis."
    if shocks.intersection({"war", "oil_shock", "oil_supply_shock", "inflation"}):
        return "inflation_geopolitical_caution", "Inflation/geopolitical analog; useful for stress framing and false-broadening risk."
    return "background_context", "Background analog; usable as historical context but not central to the current thesis."


def small_large_signal(event: dict[str, Any]) -> dict[str, Any]:
    svl = as_dict(event.get("small_vs_large"))
    forward = as_dict(svl.get("forward_small_minus_large_pct"))
    return {
        "status": svl.get("status"),
        "event_window_small_minus_large_pct": svl.get("event_window_small_minus_large_pct"),
        "forward_small_minus_large_pct": {
            "20d": forward.get("20d"),
            "60d": forward.get("60d"),
            "120d": forward.get("120d"),
            "252d": forward.get("252d"),
        },
    }


def outcome_summary(event: dict[str, Any]) -> dict[str, Any]:
    outcomes = as_dict(event.get("outcomes"))
    large = as_dict(outcomes.get("large_cap"))
    small = as_dict(outcomes.get("small_cap"))
    large_forward = as_dict(large.get("forward_returns_pct"))
    small_forward = as_dict(small.get("forward_returns_pct"))
    return {
        "large_cap_event_return_pct": large.get("event_window_return_pct"),
        "small_cap_event_return_pct": small.get("event_window_return_pct"),
        "large_cap_forward_60d_pct": large_forward.get("60d"),
        "small_cap_forward_60d_pct": small_forward.get("60d"),
        "large_cap_forward_252d_pct": large_forward.get("252d"),
        "small_cap_forward_252d_pct": small_forward.get("252d"),
    }


def interpretation(event: dict[str, Any], fit: str) -> str:
    signal = small_large_signal(event)
    fwd60 = safe_float(as_dict(signal.get("forward_small_minus_large_pct")).get("60d"))
    label = event.get("label")
    if signal.get("status") != "ok":
        return f"{label}: small-vs-large comparison is unavailable; use only for broad macro/stress context."
    if fit in {"direct_current_theme", "rate_shock_precedent"}:
        if fwd60 is not None and fwd60 > 0:
            return f"{label}: small caps beat large caps in the 60d forward window, supporting review of broadening if credit conditions are contained."
        if fwd60 is not None and fwd60 < 0:
            return f"{label}: small caps lagged large caps in the 60d forward window; rate stabilization alone did not immediately create durable small-cap leadership."
    if fit == "stress_caution":
        return f"{label}: stress context; test credit/liquidity risk before treating small/mid weakness as only a rate problem."
    return f"{label}: context row for scenario review only."


def public_event_row(event: dict[str, Any], fit: str, reason: str) -> dict[str, Any]:
    row = {
        "event_id": event.get("event_id"),
        "label": event.get("label"),
        "period": {"start": event.get("start"), "end": event.get("end")},
        "shock_types": event.get("shock_types") or [],
        "fit": fit,
        "fit_reason": reason,
        "setup": event.get("setup"),
        "analog_notes": event.get("analog_notes"),
        "outcome_summary": outcome_summary(event),
        "small_vs_large_signal": small_large_signal(event),
    }
    row["scenario_interpretation"] = interpretation(event, fit)
    return row


def select_panel(events: list[dict[str, Any]], tags: list[str]) -> dict[str, Any]:
    rows = []
    for event in events:
        fit, reason = event_fit(event, tags)
        rows.append(public_event_row(event, fit, reason))

    primary_order = {"direct_current_theme": 0, "rate_shock_precedent": 1}
    primary = [row for row in rows if row["fit"] in primary_order]
    primary.sort(key=lambda row: (primary_order[row["fit"]], str(row["period"]["start"])))
    stress = [row for row in rows if row["fit"] in {"stress_caution", "inflation_geopolitical_caution"}]
    stress.sort(key=lambda row: str(row["period"]["start"]))
    background = [row for row in rows if row["fit"] == "background_context"]
    background.sort(key=lambda row: str(row["period"]["start"]))

    observations = [
        "Use direct analogs to challenge the current rate-stabilization and breadth-repair thesis.",
        "Use stress analogs to test whether credit/liquidity/geopolitical risk can break the small/mid-cap broadening setup.",
        "Small-cap rebound behavior is conditional; rate stabilization is supportive only when earnings, credit, and liquidity do not deteriorate.",
    ]
    return {
        "active_current_tags": tags,
        "primary_analogs": primary[:5],
        "stress_caution_analogs": stress[:5],
        "background_analogs": background[:3],
        "scenario_observations": observations,
        "decision_use": [
            "macro judgment scenario context",
            "WF61 small/mid-cap regime context",
            "WF78 candidate review context",
            "finance market deployment-loop context",
            "future decision-card scenario context",
        ],
        "blocked_use": [
            "calibrated probability",
            "predictive score",
            "deployment ranking",
            "sizing/allocation recommendation",
            "capital action",
            "paper/live execution",
            "owner approval inference",
        ],
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority"))
    for key, expected in AUTHORITY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_mismatch:{key}")
    panel = as_dict(payload.get("scenario_context_panel"))
    if not panel.get("primary_analogs"):
        errors.append("primary_analogs_missing")
    if not panel.get("stress_caution_analogs"):
        warnings.append("stress_caution_analogs_missing")
    text = json.dumps(payload, sort_keys=True)
    found = sorted(set(match.group(1).lower() for match in FORBIDDEN_LANGUAGE_RE.finditer(text)))
    if found:
        errors.append(f"forbidden_language:{found}")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "critical_count": len(errors),
        "warning_count": len(warnings),
    }


def build_payload(historical: dict[str, Any] | None = None, wf61: dict[str, Any] | None = None) -> dict[str, Any]:
    historical = historical if isinstance(historical, dict) else as_dict(load_json_artifact(HISTORICAL_LIBRARY))
    wf61 = wf61 if isinstance(wf61, dict) else as_dict(load_json_artifact(WF61_FEED))
    events = [event for event in as_list(historical.get("events")) if isinstance(event, dict)]
    tags = current_tags(historical, wf61)
    panel = select_panel(events, tags)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF55/WF61/WF78/WF85",
        "consumer_posture": "review_only",
        "purpose": "Current-regime historical analog scenario context panel for finance intelligence packets.",
        "authority": AUTHORITY,
        "source_artifacts": [
            {"path": rel(HISTORICAL_LIBRARY), "role": "historical regime analog library", "exists": HISTORICAL_LIBRARY.exists(), "status": historical.get("status")},
            {"path": rel(WF61_FEED), "role": "current small/mid proxy regime context", "exists": WF61_FEED.exists(), "status": wf61.get("status"), "market_data_as_of": wf61.get("market_data_as_of")},
        ],
        "scenario_context_panel": panel,
        "downstream_consumers": DOWNSTREAM_CONSUMERS,
        "stop_lines": [
            "Scenario context is not a probability model, ranking model, sizing system, approval card, or execution signal.",
            "No generated analog row can authorize capital deployment, paper/live execution, account action, money movement, or portfolio/canon mutation.",
        ],
    }
    payload["summary"] = {
        "historical_event_count": len(events),
        "primary_analog_count": len(panel["primary_analogs"]),
        "stress_caution_analog_count": len(panel["stress_caution_analogs"]),
        "current_tags": tags,
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    panel = as_dict(payload.get("scenario_context_panel"))
    lines = [
        "# Current Regime Analog Match",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Current tags: `{', '.join(panel.get('active_current_tags') or [])}`",
        "- Boundary: review-only scenario context; no probability, ranking, sizing, capital action, or execution authority.",
        "",
        "## Primary Analogs",
        "",
        "| Event | Fit | Small minus large 60d | Interpretation |",
        "|---|---|---:|---|",
    ]
    for row in panel.get("primary_analogs") or []:
        signal = as_dict(row.get("small_vs_large_signal"))
        forward = as_dict(signal.get("forward_small_minus_large_pct"))
        lines.append(f"| {row.get('label')} | {row.get('fit')} | {fmt_pct(forward.get('60d'))} | {row.get('scenario_interpretation')} |")
    lines.extend(["", "## Stress/Caution Analogs", "", "| Event | Fit | Small minus large 60d | Interpretation |", "|---|---|---:|---|"])
    for row in panel.get("stress_caution_analogs") or []:
        signal = as_dict(row.get("small_vs_large_signal"))
        forward = as_dict(signal.get("forward_small_minus_large_pct"))
        lines.append(f"| {row.get('label')} | {row.get('fit')} | {fmt_pct(forward.get('60d'))} | {row.get('scenario_interpretation')} |")
    lines.extend(["", "## Use", ""])
    lines.extend(f"- {item}" for item in panel.get("decision_use") or [])
    lines.extend(["", "## Blocked Use", ""])
    lines.extend(f"- {item}" for item in panel.get("blocked_use") or [])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only current-regime analog scenario context panel.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    parser.add_argument("--md-output", type=Path, default=OUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    if args.write:
        atomic_write_json(output, payload)
        atomic_write_text(md_output, render_markdown(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "validation": payload.get("validation"),
            "primary_analog_count": payload.get("summary", {}).get("primary_analog_count"),
            "stress_caution_analog_count": payload.get("summary", {}).get("stress_caution_analog_count"),
            "output": rel(output),
        }, indent=2, sort_keys=True))
    return 1 if args.validate and payload["validation"]["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
