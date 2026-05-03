"""universe.py — single resolver for ticker lane membership and surface entitlement.

Phase 1 of the E17 Universe Synchronization project. Replaces the drifting
booleans (`include_in_technical_refresh`, `include_in_trigger_sheet`) with one
normalized lane model. Every downstream script (technical_refresh,
deployment_check, trigger_sheet_refresh, dashboard_payload, workbook_export)
should consume membership and entitlement decisions from this module rather
than re-deriving them from raw config flags.

Lanes:
- execution   — thesis-grade, deployable in principle, entitled to action cards.
- watch       — tracked thesis, monitored, not currently deployment-grade.
- macro       — regime-context instrument; never an action-card candidate.
- speculative — explicit speculative sleeve; surfaces only on opt-in panels.

Backward compatibility:
The resolver prefers an explicit `coverage_lane` field on each tracked_universe
entry. If absent, it synthesizes a lane from the legacy booleans so the chain
keeps working during the migration. Phase 1 sub-pass 2 will remove the legacy
fallback once every downstream script has been converted.
"""

from __future__ import annotations

from typing import Any, Iterable

LANES: tuple[str, ...] = ("execution", "watch", "macro", "speculative")

LANE_ENTITLEMENTS: dict[str, dict[str, bool]] = {
    "execution":   {"technical_refresh": True,  "trigger_sheet": True,  "action_card": True,  "band_drift": True,  "earnings_calendar": True,  "deployment_ranking": True},
    "watch":       {"technical_refresh": True,  "trigger_sheet": False, "action_card": False, "band_drift": True,  "earnings_calendar": True,  "deployment_ranking": False},
    "macro":       {"technical_refresh": False, "trigger_sheet": False, "action_card": False, "band_drift": False, "earnings_calendar": False, "deployment_ranking": False},
    "speculative": {"technical_refresh": False, "trigger_sheet": False, "action_card": False, "band_drift": False, "earnings_calendar": False, "deployment_ranking": False},
}

SURFACES: tuple[str, ...] = tuple(LANE_ENTITLEMENTS["execution"].keys())


def resolve_lane(ticker: str, meta: dict[str, Any]) -> str:
    """Return canonical lane for a ticker.

    Requires explicit `coverage_lane` field.
    """
    lane = meta.get("coverage_lane")
    if isinstance(lane, str) and lane in LANES:
        return lane
    
    raise ValueError(f"Ticker {ticker} is missing a valid 'coverage_lane' in portfolio-config.json")


def is_entitled(ticker: str, meta: dict[str, Any], surface: str) -> bool:
    """Is `ticker` entitled to `surface` based on its lane?"""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface {surface!r}; expected one of {SURFACES}")
    lane = resolve_lane(ticker, meta)
    return LANE_ENTITLEMENTS.get(lane, {}).get(surface, False)


def members(tracked_universe: dict[str, Any],
            lane: str | None = None,
            surface: str | None = None) -> dict[str, str]:
    """Return {ticker: lane} for tickers in the requested lane and/or with the requested entitlement.

    With no filters, returns the full universe. Filters compose (AND).
    """
    if lane is not None and lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    if surface is not None and surface not in SURFACES:
        raise ValueError(f"unknown surface {surface!r}; expected one of {SURFACES}")
    out: dict[str, str] = {}
    for ticker, meta in tracked_universe.items():
        if not isinstance(meta, dict):
            continue
        resolved = resolve_lane(ticker, meta)
        if lane is not None and resolved != lane:
            continue
        if surface is not None and not LANE_ENTITLEMENTS[resolved].get(surface, False):
            continue
        out[ticker] = resolved
    return out


def lane_summary(tracked_universe: dict[str, Any]) -> dict[str, list[str]]:
    """Return {lane: [tickers]} summary for diagnostics and consistency gates."""
    summary: dict[str, list[str]] = {lane: [] for lane in LANES}
    for ticker, meta in tracked_universe.items():
        if not isinstance(meta, dict):
            continue
        summary[resolve_lane(ticker, meta)].append(ticker)
    for lane in summary:
        summary[lane].sort()
    return summary


def entitled_set(tracked_universe: dict[str, Any], surface: str) -> set[str]:
    """Convenience: set of tickers entitled to a surface."""
    return set(members(tracked_universe, surface=surface).keys())
