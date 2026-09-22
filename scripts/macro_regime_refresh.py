"""macro_regime_refresh.py

Synthesize the three live data-layer artifacts into a composite macro regime
label and structured sector-fit adjustments. This is the bridge between raw
data signals and the regime-scoring layer.

Inputs (all from tmp/):
    policy-expectations.json  — Fed policy posture and implied rate
    credit-spreads.json       — IG/HY OAS levels and stress regime
    breadth-state.json        — RSP/SPY trend and sector participation

Output:
    tmp/macro-regime.json

Chain placement:
    After: policy_expectations_refresh.py, credit_spread_refresh.py,
           breadth_refresh.py
    Before: regime_scoring_refresh.py

Usage:
    python scripts/macro_regime_refresh.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from market_data_utils import (
    atomic_write_json,
    guard_dict_or_empty,
    guard_list_of_dicts_or_empty,
    guard_number_or_none,
)

WORKSPACE = Path(__file__).resolve().parents[1]

IN_POLICY   = WORKSPACE / "tmp" / "policy-expectations.json"
IN_CREDIT   = WORKSPACE / "tmp" / "credit-spreads.json"
IN_BREADTH  = WORKSPACE / "tmp" / "breadth-state.json"
OUT_PATH    = WORKSPACE / "tmp" / "macro-regime.json"

STALE_AFTER_HOURS = 24
EXPECTED_UPDATE_WINDOW = (
    "Refresh after the close and on FOMC decision days. "
    "Re-run whenever any upstream data artifact is updated."
)


# ---------------------------------------------------------------------------
# Sector fit adjustments by regime pillar combination
# Positive = boost above default, negative = reduce below default
# Applied additively on top of regime_scoring_refresh.py base scores
# ---------------------------------------------------------------------------
SECTOR_FIT_ADJUSTMENTS: dict[str, dict[str, int]] = {
    # Restrictive pause + benign credit + broad/recovering breadth
    # Risk-on with large-cap quality bias; defensives lag
    "restrictive_pause__benign__broad_recovering": {
        "Tech":                0,
        "Technology":          0,
        "Tech / AI Infrastructure": 0,
        "Tech / Defense":      0,
        "Defense":             0,
        "Defense / Aerospace": 0,
        "Industrials":         0,
        "Financials":          0,
        "Energy":              0,
        "Diversified Quality": 0,
        "Large-cap Quality":   0,
        "Commodities":        -1,
        "Macro":              -1,
        "Speculative":        -1,
    },
    # Restrictive pause + benign credit + narrow/deteriorating breadth
    # Breadth is thinning; stay with high-conviction large-cap, reduce cyclicals
    "restrictive_pause__benign__narrow_deteriorating": {
        "Tech":                0,
        "Technology":          0,
        "Tech / AI Infrastructure": 0,
        "Tech / Defense":      0,
        "Defense":             0,
        "Defense / Aerospace": 0,
        "Industrials":        -1,
        "Financials":         -1,
        "Energy":             -1,
        "Diversified Quality":  0,
        "Large-cap Quality":    0,
        "Commodities":         -1,
        "Macro":               +1,
        "Speculative":         -2,
    },
    # Restrictive pause + credit watch or stressed (any breadth)
    # Credit risk is real; move to defensive quality, reduce cyclicals/speculative
    "restrictive_pause__stressed": {
        "Tech":               -1,
        "Technology":         -1,
        "Tech / AI Infrastructure": -1,
        "Tech / Defense":      0,
        "Defense":            +1,
        "Defense / Aerospace": +1,
        "Industrials":        -1,
        "Financials":         -2,
        "Energy":              0,
        "Diversified Quality": +1,
        "Large-cap Quality":   +1,
        "Commodities":         0,
        "Macro":              +2,
        "Speculative":        -3,
    },
    # Easing cycle + benign credit + broad/recovering breadth
    # Best risk-on environment; increase cyclical and speculative tolerance
    "easing__benign__broad_recovering": {
        "Tech":               +0,
        "Technology":         +0,
        "Tech / AI Infrastructure": +0,
        "Tech / Defense":     +0,
        "Defense":            +0,
        "Defense / Aerospace": +0,
        "Industrials":        +1,
        "Financials":         +1,
        "Energy":             +1,
        "Diversified Quality": +0,
        "Large-cap Quality":  +0,
        "Commodities":        +1,
        "Macro":              -1,
        "Speculative":        +1,
    },
    # Easing cycle + stressed credit (any breadth)
    # Policy is cutting into a problem; defensive quality, avoid credit-sensitive
    "easing__stressed": {
        "Tech":               -1,
        "Technology":         -1,
        "Tech / AI Infrastructure": -1,
        "Tech / Defense":      0,
        "Defense":            +1,
        "Defense / Aerospace": +1,
        "Industrials":        -2,
        "Financials":         -3,
        "Energy":             -1,
        "Diversified Quality": +1,
        "Large-cap Quality":   +2,
        "Commodities":         0,
        "Macro":              +2,
        "Speculative":        -3,
    },
    # Tightening / hiking bias (any credit, any breadth)
    # Rate sensitivity dominates; reduce duration-sensitive, stay short-cycle
    "tightening": {
        "Tech":               -2,
        "Technology":         -2,
        "Tech / AI Infrastructure": -2,
        "Tech / Defense":     -1,
        "Defense":            +0,
        "Defense / Aerospace": +0,
        "Industrials":        -1,
        "Financials":         +1,
        "Energy":             +1,
        "Diversified Quality": 0,
        "Large-cap Quality":  +0,
        "Commodities":        +1,
        "Macro":              +1,
        "Speculative":        -3,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Strip null bytes that Windows/NTFS mounts sometimes append as padding
        content = content.rstrip("\x00")
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(content)
        return obj  # type: ignore[no-any-return]
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return {}


def get_path(obj: Any, dotted: str, default: Any = None) -> Any:
    parts = dotted.split(".")
    cur = obj
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return default
        if cur is None:
            return default
    return cur


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _policy_freshness_component(policy: dict[str, Any]) -> dict[str, Any]:
    contract = policy.get("freshness_contract") if isinstance(policy.get("freshness_contract"), dict) else {}
    categories = contract.get("categories") if isinstance(contract.get("categories"), list) else []
    status = contract.get("freshness_status") or policy.get("freshness_status") or policy.get("status") or "missing"
    return {
        "component": "policy",
        "status": status,
        "category": categories[0] if categories else ("ok" if status in {"ok", "fresh", "current"} else str(status)),
        "safe_for_macro_regime": bool(contract.get("safe_for_macro_regime", status not in {"blocked", "error", "missing"})),
        "hard_fail_closed": bool(contract.get("hard_fail_closed", False)),
        "remediation": contract.get("remediation") or {
            "owner": "policy_expectations_refresh.py",
            "command": "python scripts\\policy_expectations_refresh.py",
            "action": "Refresh or repair the policy expectations artifact before macro-sensitive use.",
        },
    }


def _macro_freshness_contract(
    *,
    policy_component: dict[str, Any],
    credit_key: str,
    breadth_key: str,
    invalid_shape_pillars: list[str],
    missing_pillars: list[str],
) -> dict[str, Any]:
    components = [
        policy_component,
        {
            "component": "credit",
            "status": "unknown" if credit_key == "unknown" else "ok",
            "category": "missing_or_invalid" if credit_key == "unknown" else "ok",
            "safe_for_macro_regime": credit_key != "unknown",
            "remediation": {"owner": "credit_spread_refresh.py", "command": "python scripts\\credit_spread_refresh.py", "action": "Refresh credit spread artifact if credit pillar is unknown."},
        },
        {
            "component": "breadth",
            "status": "unknown" if breadth_key == "unknown" else "ok",
            "category": "missing_or_invalid" if breadth_key == "unknown" else "ok",
            "safe_for_macro_regime": breadth_key != "unknown",
            "remediation": {"owner": "breadth_refresh.py", "command": "python scripts\\breadth_refresh.py", "action": "Refresh breadth artifact if breadth pillar is unknown."},
        },
    ]
    hard_blocked = bool(policy_component.get("hard_fail_closed") or invalid_shape_pillars)
    warning_only = bool(missing_pillars or any(c.get("status") not in {"ok", "fresh", "current"} for c in components))
    status = "blocked" if hard_blocked else ("warning" if warning_only else "ok")
    return {
        "schema_version": 1,
        "status": status,
        "summary": "Macro pillar has fail-closed input; regime label is conservative fallback." if hard_blocked else ("Macro usable with caution; degraded/missing pillars are routed to component repair." if warning_only else "Macro inputs are current enough for regime use."),
        "components": components,
        "blocked_pillars": sorted(set(invalid_shape_pillars + [p for p in missing_pillars if p == "policy" and policy_component.get("hard_fail_closed")])) ,
        "degraded_pillars": sorted(set(missing_pillars + [c["component"] for c in components if c.get("status") not in {"ok", "fresh", "current"}])),
        "routing": {
            "deployment_surface_blocked": False,
            "regime_confidence": "low" if hard_blocked or len(missing_pillars) >= 2 else ("medium" if warning_only else "normal"),
            "owner_action_required": hard_blocked or warning_only,
        },
    }


def _sanitize_policy_view(policy: dict[str, Any], warnings: list[str]) -> tuple[dict[str, Any], bool]:
    invalid = False
    data, bad = guard_dict_or_empty(policy.get("data"), warnings, "policy-expectations.data")
    invalid |= bad
    next_fomc, bad = guard_dict_or_empty(data.get("next_fomc"), warnings, "policy-expectations.data.next_fomc")
    invalid |= bad
    target_range, bad = guard_dict_or_empty(data.get("current_target_range"), warnings, "policy-expectations.data.current_target_range")
    invalid |= bad
    distribution, bad = guard_list_of_dicts_or_empty(
        next_fomc.get("distribution"), warnings, "policy-expectations.data.next_fomc.distribution"
    )
    invalid |= bad

    sanitized_distribution: list[dict[str, Any]] = []
    for idx, item in enumerate(distribution):
        outcome = _string_or_none(item.get("outcome"))
        probability, prob_bad = guard_number_or_none(
            item.get("probability"), warnings, f"policy-expectations.data.next_fomc.distribution[{idx}].probability"
        )
        if outcome is None or probability is None:
            if outcome is None:
                warnings.append(
                    f"policy-expectations.data.next_fomc.distribution[{idx}].outcome must be a non-empty string; using empty list."
                )
            if probability is None and not prob_bad:
                warnings.append(
                    f"policy-expectations.data.next_fomc.distribution[{idx}].probability must be numeric; using empty list."
                )
            invalid = True
            sanitized_distribution = []
            break
        sanitized_distribution.append({"outcome": outcome, "probability": probability})

    target_low, bad = guard_number_or_none(target_range.get("low"), warnings, "policy-expectations.data.current_target_range.low")
    invalid |= bad
    target_high, bad = guard_number_or_none(target_range.get("high"), warnings, "policy-expectations.data.current_target_range.high")
    invalid |= bad
    implied_rate, bad = guard_number_or_none(next_fomc.get("implied_rate"), warnings, "policy-expectations.data.next_fomc.implied_rate")
    invalid |= bad
    days_until, bad = guard_number_or_none(next_fomc.get("days_until"), warnings, "policy-expectations.data.next_fomc.days_until")
    invalid |= bad

    return {
        "distribution": sanitized_distribution,
        "distribution_map": {item["outcome"]: item["probability"] for item in sanitized_distribution},
        "target_range": {
            "low": target_low,
            "high": target_high,
        },
        "implied_rate": implied_rate,
        "next_fomc_date": _string_or_none(next_fomc.get("meeting_date")),
        "days_until_fomc": days_until,
    }, invalid


def _sanitize_credit_view(credit: dict[str, Any], warnings: list[str]) -> tuple[dict[str, Any], bool]:
    invalid = False
    data, bad = guard_dict_or_empty(credit.get("data"), warnings, "credit-spreads.data")
    invalid |= bad
    hy_block, bad = guard_dict_or_empty(data.get("high_yield_oas"), warnings, "credit-spreads.data.high_yield_oas")
    invalid |= bad
    ig_block, bad = guard_dict_or_empty(data.get("investment_grade_oas"), warnings, "credit-spreads.data.investment_grade_oas")
    invalid |= bad
    direction, bad = guard_dict_or_empty(data.get("direction"), warnings, "credit-spreads.data.direction")
    invalid |= bad

    stress_regime = data.get("stress_regime")
    if stress_regime is not None and not isinstance(stress_regime, str):
        warnings.append("credit-spreads.data.stress_regime must be a string; using null.")
        invalid = True
        stress_regime = None

    hy_oas, bad = guard_number_or_none(hy_block.get("value"), warnings, "credit-spreads.data.high_yield_oas.value")
    invalid |= bad
    ig_oas, bad = guard_number_or_none(ig_block.get("value"), warnings, "credit-spreads.data.investment_grade_oas.value")
    invalid |= bad
    hy_minus_ig, bad = guard_number_or_none(data.get("hy_minus_ig_spread"), warnings, "credit-spreads.data.hy_minus_ig_spread")
    invalid |= bad

    return {
        "stress_regime": stress_regime,
        "hy_oas": hy_oas,
        "ig_oas": ig_oas,
        "hy_minus_ig": hy_minus_ig,
        "hy_direction_5d": _string_or_none(direction.get("hy_5d")),
        "hy_direction_20d": _string_or_none(direction.get("hy_20d")),
    }, invalid


def _sanitize_breadth_view(breadth: dict[str, Any], warnings: list[str]) -> tuple[dict[str, Any], bool]:
    invalid = False
    data, bad = guard_dict_or_empty(breadth.get("data"), warnings, "breadth-state.data")
    invalid |= bad
    major, bad = guard_dict_or_empty(data.get("major_index_breadth"), warnings, "breadth-state.data.major_index_breadth")
    invalid |= bad
    participation, bad = guard_dict_or_empty(data.get("sector_participation"), warnings, "breadth-state.data.sector_participation")
    invalid |= bad
    equal_weight, bad = guard_dict_or_empty(data.get("equal_weight_vs_cap_weight"), warnings, "breadth-state.data.equal_weight_vs_cap_weight")
    invalid |= bad

    breadth_regime = major.get("breadth_regime")
    if breadth_regime is not None and not isinstance(breadth_regime, str):
        warnings.append("breadth-state.data.major_index_breadth.breadth_regime must be a string; using null.")
        invalid = True
        breadth_regime = None

    composite_score, bad = guard_number_or_none(major.get("composite_score"), warnings, "breadth-state.data.major_index_breadth.composite_score")
    invalid |= bad
    sectors_above_50dma, bad = guard_number_or_none(
        participation.get("sectors_above_50dma"), warnings, "breadth-state.data.sector_participation.sectors_above_50dma"
    )
    invalid |= bad
    sectors_total, bad = guard_number_or_none(
        participation.get("sectors_total"), warnings, "breadth-state.data.sector_participation.sectors_total"
    )
    invalid |= bad
    participation_pct, bad = guard_number_or_none(
        participation.get("participation_pct"), warnings, "breadth-state.data.sector_participation.participation_pct"
    )
    invalid |= bad
    rsp_spy_ratio, bad = guard_number_or_none(
        equal_weight.get("rsp_spy_ratio"), warnings, "breadth-state.data.equal_weight_vs_cap_weight.rsp_spy_ratio"
    )
    invalid |= bad
    rsp_spy_5d_change_pct, bad = guard_number_or_none(
        equal_weight.get("rsp_spy_ratio_5d_change_pct"), warnings, "breadth-state.data.equal_weight_vs_cap_weight.rsp_spy_ratio_5d_change_pct"
    )
    invalid |= bad

    return {
        "breadth_regime": breadth_regime,
        "composite_score": composite_score,
        "sectors_above_50dma": sectors_above_50dma,
        "sectors_total": sectors_total,
        "participation_pct": participation_pct,
        "rsp_spy_ratio": rsp_spy_ratio,
        "rsp_spy_direction": _string_or_none(equal_weight.get("direction")),
        "rsp_spy_5d_change_pct": rsp_spy_5d_change_pct,
    }, invalid


# ---------------------------------------------------------------------------
# Pillar classifiers
# ---------------------------------------------------------------------------

def classify_policy_pillar(policy: dict[str, Any]) -> tuple[str, str]:
    """
    Returns (pillar_key, pillar_label).
    pillar_key: one of 'tightening' | 'restrictive_pause' | 'easing' | 'unknown'
    """
    if not policy:
        return "unknown", "Policy data unavailable"

    distribution = policy.get("distribution") or []
    target_range = policy.get("target_range") or {}
    target_low = target_range.get("low")
    target_high = target_range.get("high")

    prob_map = policy.get("distribution_map") or {}
    hike_prob = prob_map.get("hike_25bp", 0.0)
    cut_prob  = prob_map.get("cut_25bp", 0.0)
    hold_prob = prob_map.get("hold", 0.0)

    # Tightening: active hike probability above noise threshold
    if hike_prob >= 25.0:
        return "tightening", f"Tightening bias ({hike_prob:.0f}% hike probability)"

    # Easing: meaningful cut probability
    if cut_prob >= 25.0:
        strength = "Active easing" if cut_prob >= 60.0 else "Easing cycle beginning"
        return "easing", f"{strength} ({cut_prob:.0f}% cut probability)"

    # Restrictive pause: high hold probability, rates elevated
    if hold_prob >= 70.0:
        rate_note = ""
        if target_low is not None and target_high is not None:
            mid = (target_low + target_high) / 2.0
            rate_note = f", target {target_low:.2f}–{target_high:.2f}%"
        return "restrictive_pause", f"Restrictive pause — hold dominant ({hold_prob:.0f}%{rate_note})"

    return "unknown", f"Policy posture unclear (hold {hold_prob:.0f}%, cut {cut_prob:.0f}%, hike {hike_prob:.0f}%)"


def classify_credit_pillar(credit: dict[str, Any]) -> tuple[str, str]:
    """
    Returns (pillar_key, pillar_label).
    pillar_key: one of 'benign' | 'watch' | 'stressed' | 'unknown'
    """
    if not credit:
        return "unknown", "Credit data unavailable"

    stress_regime = credit.get("stress_regime")
    hy_oas = credit.get("hy_oas")
    ig_oas = credit.get("ig_oas")
    hy_5d = credit.get("hy_direction_5d")
    direction_note = f"HY {hy_5d or 'unknown'}" if hy_5d else ""

    if stress_regime in ("severe", "stressed"):
        label = f"Credit stress — HY OAS {hy_oas:.2f}%" if hy_oas else "Credit stressed"
        return "stressed", label
    if stress_regime == "watch":
        label = f"Credit on watch — HY OAS {hy_oas:.2f}%" if hy_oas else "Credit on watch"
        return "watch", label
    if stress_regime == "benign":
        parts = []
        if hy_oas:
            parts.append(f"HY {hy_oas:.2f}%")
        if ig_oas:
            parts.append(f"IG {ig_oas:.2f}%")
        if direction_note:
            parts.append(direction_note)
        label = "Benign credit — " + ", ".join(parts) if parts else "Benign credit"
        return "benign", label

    return "unknown", "Credit posture unknown"


def classify_breadth_pillar(breadth: dict[str, Any]) -> tuple[str, str]:
    """
    Returns (pillar_key, pillar_label).
    pillar_key: one of 'broad_recovering' | 'narrow_deteriorating' | 'mixed' | 'unknown'
    """
    if not breadth:
        return "unknown", "Breadth data unavailable"

    regime = breadth.get("breadth_regime")
    above_count = breadth.get("sectors_above_50dma")
    total = breadth.get("sectors_total")
    rsp_5d = breadth.get("rsp_spy_5d_change_pct")

    if regime is None and above_count is None and total is None and rsp_5d is None:
        return "unknown", "Breadth posture unknown"

    participation = f"{above_count}/{total}" if above_count is not None and total else ""
    rsp_note = f", RSP/SPY {rsp_5d:+.2f}% 5d" if rsp_5d is not None else ""

    if regime in ("broad", "recovering"):
        label = f"Breadth {regime} — {participation} sectors above 50DMA{rsp_note}"
        return "broad_recovering", label
    if regime in ("narrow", "deteriorating"):
        label = f"Breadth {regime} — {participation} sectors above 50DMA{rsp_note}"
        return "narrow_deteriorating", label

    # mixed or unknown
    label = f"Breadth mixed — {participation} sectors above 50DMA{rsp_note}" if participation else "Breadth mixed"
    return "mixed", label


# ---------------------------------------------------------------------------
# Composite regime synthesis
# ---------------------------------------------------------------------------

def synthesize_regime(
    policy_key: str,
    credit_key: str,
    breadth_key: str,
) -> tuple[str, str, str]:
    """
    Returns (regime_key, regime_label, adjustment_key).
    adjustment_key indexes into SECTOR_FIT_ADJUSTMENTS.
    """
    # Tightening overrides everything
    if policy_key == "tightening":
        return (
            "tightening",
            "Tightening risk — rate-sensitivity elevated, risk-off posture warranted",
            "tightening",
        )

    # Credit stress overrides breadth signal
    if credit_key in ("stressed",):
        if policy_key == "easing":
            return (
                "easing_credit_stress",
                "Easing into stress — policy cutting into a credit/growth problem, defensive quality",
                "easing__stressed",
            )
        return (
            "restrictive_credit_stress",
            "Restrictive pause with credit stress — risk-off, quality defense, avoid cyclicals",
            "restrictive_pause__stressed",
        )

    # Credit on watch: treat as partial stress for conservative regime label
    if credit_key == "watch":
        if policy_key == "easing":
            return (
                "easing_credit_watch",
                "Easing cycle, credit on watch — cautious risk-on, avoid credit-sensitive cyclicals",
                "easing__stressed",  # conservative: use stressed adjustments
            )
        return (
            "restrictive_credit_watch",
            "Restrictive pause, credit on watch — selective quality, reduce speculative exposure",
            "restrictive_pause__stressed",  # conservative
        )

    # Easing + benign credit
    if policy_key == "easing":
        if breadth_key in ("broad_recovering",):
            return (
                "easing_benign_broad",
                "Easing cycle, healthy conditions, broad participation — risk-on",
                "easing__benign__broad_recovering",
            )
        return (
            "easing_benign_mixed",
            "Easing cycle, healthy credit, mixed breadth — selective risk-on",
            "easing__benign__broad_recovering",  # same adjustments, label captures nuance
        )

    # Restrictive pause + benign credit — the core split is on breadth
    if policy_key == "restrictive_pause":
        if breadth_key in ("broad_recovering",):
            return (
                "restrictive_pause_benign_broad",
                "Restrictive pause, resilient growth, selective risk-on — large-cap quality bias",
                "restrictive_pause__benign__broad_recovering",
            )
        if breadth_key in ("narrow_deteriorating",):
            return (
                "restrictive_pause_benign_narrow",
                "Restrictive pause, thinning breadth — stay with high-conviction large-cap, reduce cyclicals",
                "restrictive_pause__benign__narrow_deteriorating",
            )
        # mixed breadth
        return (
            "restrictive_pause_benign_mixed",
            "Restrictive pause, benign credit, mixed breadth — quality-selective, watch for breadth deterioration",
            "restrictive_pause__benign__broad_recovering",  # default to the more constructive set
        )

    # Unknown policy — default to cautious
    return (
        "uncertain",
        "Regime uncertain — policy posture unclear, default to quality and reduced cyclical exposure",
        "restrictive_pause__benign__narrow_deteriorating",
    )


def build_sector_fit_table(adjustment_key: str) -> dict[str, dict[str, Any]]:
    """
    Build the final per-sector fit table combining base scores from
    regime_scoring_refresh.py with the dynamic adjustments.
    """
    BASE_SCORES: dict[str, int] = {
        "Tech":                5,
        "Technology":          5,
        "Tech / AI Infrastructure": 5,
        "Tech / Defense":      5,
        "Defense":             5,
        "Defense / Aerospace": 5,
        "Industrials":         5,
        "Financials":          4,
        "Energy":              4,
        "Diversified Quality": 4,
        "Large-cap Quality":   4,
        "Commodities":         3,
        "Macro":               3,
        "Speculative":         2,
    }

    adjustments = SECTOR_FIT_ADJUSTMENTS.get(adjustment_key, {})
    out: dict[str, dict[str, Any]] = {}
    for sector, base in BASE_SCORES.items():
        adj = adjustments.get(sector, 0)
        final = max(1, min(5, base + adj))
        out[sector] = {"base": base, "adjustment": adj, "final": final}
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    warnings: list[str] = []

    print("Synthesizing macro regime...")

    policy  = load_json(IN_POLICY)
    credit  = load_json(IN_CREDIT)
    breadth = load_json(IN_BREADTH)
    policy_view, policy_shape_invalid = _sanitize_policy_view(policy, warnings)
    credit_view, credit_shape_invalid = _sanitize_credit_view(credit, warnings)
    breadth_view, breadth_shape_invalid = _sanitize_breadth_view(breadth, warnings)

    policy_component = _policy_freshness_component(policy)
    if not policy_component.get("safe_for_macro_regime"):
        warnings.append(
            "policy-expectations freshness contract is not safe for macro-regime use; policy pillar is fail-closed to unknown and routed to policy remediation."
        )
        policy_view = {}
        policy_shape_invalid = True

    # Check artifact staleness
    for name, artifact, path in [
        ("policy-expectations", policy, IN_POLICY),
        ("credit-spreads",      credit, IN_CREDIT),
        ("breadth-state",       breadth, IN_BREADTH),
    ]:
        if not artifact:
            warnings.append(f"{name} artifact missing or unreadable — pillar will degrade to unknown.")
        elif artifact.get("status") == "error":
            warnings.append(f"{name} artifact has status=error — pillar may be unreliable.")

    # Classify each pillar
    policy_key,  policy_label  = classify_policy_pillar(policy_view)
    credit_key,  credit_label  = classify_credit_pillar(credit_view)
    breadth_key, breadth_label = classify_breadth_pillar(breadth_view)

    # Synthesize composite regime
    regime_key, regime_label, adjustment_key = synthesize_regime(
        policy_key, credit_key, breadth_key
    )

    # Build sector fit table
    sector_fit = build_sector_fit_table(adjustment_key)

    # Determine overall data quality / status
    missing_pillars = [k for k, v in [
        ("policy", policy_key), ("credit", credit_key), ("breadth", breadth_key)
    ] if v == "unknown"]

    invalid_shape_pillars = [
        pillar for pillar, invalid in [
            ("policy", policy_shape_invalid),
            ("credit", credit_shape_invalid),
            ("breadth", breadth_shape_invalid),
        ] if invalid
    ]

    if invalid_shape_pillars:
        status = "partial"
        warnings.append(
            f"Invalid nested payload shape detected in {', '.join(invalid_shape_pillars)}; affected fields were nulled and regime output was downgraded to partial."
        )
    elif len(missing_pillars) >= 2:
        status = "partial"
        warnings.append(f"Two or more pillars are unknown ({', '.join(missing_pillars)}); regime label is a best-effort fallback.")
    elif missing_pillars:
        status = "ok"
        warnings.append(f"{missing_pillars[0].capitalize()} pillar is unknown; regime label derived from remaining two pillars.")
    else:
        status = "ok"

    freshness_contract = _macro_freshness_contract(
        policy_component=policy_component,
        credit_key=credit_key,
        breadth_key=breadth_key,
        invalid_shape_pillars=invalid_shape_pillars,
        missing_pillars=missing_pillars,
    )

    # Collect last_trading_day across all three artifacts
    dates = [
        get_path(policy, "last_trading_day"),
        get_path(credit, "last_trading_day"),
        get_path(breadth, "last_trading_day"),
    ]
    valid_dates = [d for d in dates if d]
    last_trading_day = max(valid_dates) if valid_dates else None

    print(f"  Policy pillar ........ {policy_label}")
    print(f"  Credit pillar ........ {credit_label}")
    print(f"  Breadth pillar ....... {breadth_label}")
    print(f"  Composite regime ..... {regime_label}")

    payload: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "warnings": list(dict.fromkeys(warnings)),
        "freshness_contract": freshness_contract,
        "regime": {
            "key": regime_key,
            "label": regime_label,
            "adjustment_key": adjustment_key,
        },
        "pillars": {
            "policy": {
                "key": policy_key,
                "label": policy_label,
                "source_status": policy.get("status"),
                "freshness_status": policy_component.get("status"),
                "freshness_category": policy_component.get("category"),
                "safe_for_macro_regime": policy_component.get("safe_for_macro_regime"),
                "remediation": policy_component.get("remediation"),
                "implied_rate": policy_view.get("implied_rate"),
                "hold_probability": policy_view.get("distribution_map", {}).get("hold"),
                "cut_probability": policy_view.get("distribution_map", {}).get("cut_25bp"),
                "hike_probability": policy_view.get("distribution_map", {}).get("hike_25bp"),
                "target_range": policy_view.get("target_range"),
                "next_fomc_date": policy_view.get("next_fomc_date"),
                "days_until_fomc": policy_view.get("days_until_fomc"),
            },
            "credit": {
                "key": credit_key,
                "label": credit_label,
                "source_status": credit.get("status"),
                "stress_regime": credit_view.get("stress_regime"),
                "hy_oas": credit_view.get("hy_oas"),
                "ig_oas": credit_view.get("ig_oas"),
                "hy_minus_ig": credit_view.get("hy_minus_ig"),
                "hy_direction_5d": credit_view.get("hy_direction_5d"),
                "hy_direction_20d": credit_view.get("hy_direction_20d"),
            },
            "breadth": {
                "key": breadth_key,
                "label": breadth_label,
                "source_status": breadth.get("status"),
                "breadth_regime": breadth_view.get("breadth_regime"),
                "composite_score": breadth_view.get("composite_score"),
                "sectors_above_50dma": breadth_view.get("sectors_above_50dma"),
                "sectors_total": breadth_view.get("sectors_total"),
                "participation_pct": breadth_view.get("participation_pct"),
                "rsp_spy_ratio": breadth_view.get("rsp_spy_ratio"),
                "rsp_spy_direction": breadth_view.get("rsp_spy_direction"),
                "rsp_spy_5d_change_pct": breadth_view.get("rsp_spy_5d_change_pct"),
            },
        },
        "sector_fit": sector_fit,
        "notes": [
            "Composite regime is derived from policy posture, credit stress regime, and breadth classification.",
            "Sector fit adjustments are additive on top of base scores in regime_scoring_refresh.py.",
            "Tightening risk overrides all other signals. Credit stress overrides breadth.",            "Tightening risk overrides all other signals. Credit stress overrides breadth.",
            "Regime label and sector fit table are consumed by regime_scoring_refresh.py.",
        ],
    }

    atomic_write_json(OUT_PATH, payload, indent=2, default=str)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
