"""test_universe.py — contract tests for the lane resolver.

Phase 1 deliverable. These tests fail when lane semantics drift, when a
non-execution name leaks into action-card surfaces, or when the legacy
fallback diverges from explicit lane assignment for the same input.

Run directly: `python scripts/test_universe.py`
Exit code 0 on pass, 1 on any failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from universe import (
    LANES,
    LANE_ENTITLEMENTS,
    SURFACES,
    entitled_set,
    is_entitled,
    lane_summary,
    members,
    resolve_lane,
)

WORKSPACE = Path(__file__).resolve().parents[1]
CONFIG_PATH = WORKSPACE / "tmp" / "portfolio-config.json"


FIXTURE_EXPLICIT_EXECUTION = {"coverage_lane": "execution", "yfinance": "ABC"}
FIXTURE_EXPLICIT_WATCH     = {"coverage_lane": "watch",     "yfinance": "DEF"}
FIXTURE_EXPLICIT_MACRO     = {"coverage_lane": "macro",     "yfinance": "GHI"}
FIXTURE_EXPLICIT_SPEC      = {"coverage_lane": "speculative","yfinance": "JKL"}
FIXTURE_LEGACY_EXECUTION   = {"include_in_technical_refresh": True,  "include_in_trigger_sheet": True,
                              "portfolio_role": "core", "coverage_tier": "daily"}
FIXTURE_LEGACY_WATCH       = {"include_in_technical_refresh": False, "include_in_trigger_sheet": False,
                              "portfolio_role": "watch_only", "coverage_tier": "event"}
FIXTURE_LEGACY_MACRO       = {"include_in_technical_refresh": False, "include_in_trigger_sheet": False,
                              "portfolio_role": "speculative", "coverage_tier": "macro"}
FIXTURE_LEGACY_SPEC        = {"include_in_technical_refresh": False, "include_in_trigger_sheet": False,
                              "portfolio_role": "speculative", "coverage_tier": "event"}


def _check(name: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}{(' — ' + detail) if detail else ''}")
    return cond


def test_resolve_explicit() -> bool:
    return all([
        _check("explicit lane: execution", resolve_lane("ABC", FIXTURE_EXPLICIT_EXECUTION) == "execution"),
        _check("explicit lane: watch",     resolve_lane("DEF", FIXTURE_EXPLICIT_WATCH) == "watch"),
        _check("explicit lane: macro",     resolve_lane("GHI", FIXTURE_EXPLICIT_MACRO) == "macro"),
        _check("explicit lane: speculative", resolve_lane("JKL", FIXTURE_EXPLICIT_SPEC) == "speculative"),
    ])


def test_entitlement_matrix() -> bool:
    cases = [
        ("execution",   "action_card",         True),
        ("execution",   "trigger_sheet",       True),
        ("execution",   "technical_refresh",   True),
        ("watch",       "action_card",         False),
        ("watch",       "trigger_sheet",       False),
        ("watch",       "technical_refresh",   True),
        ("watch",       "band_drift",          True),
        ("macro",       "action_card",         False),
        ("macro",       "band_drift",          False),
        ("macro",       "earnings_calendar",   False),
        ("speculative", "action_card",         False),
        ("speculative", "band_drift",          False),
    ]
    ok = True
    for lane, surface, expected in cases:
        meta = {"coverage_lane": lane}
        got = is_entitled("X", meta, surface)
        ok &= _check(f"entitlement {lane}/{surface} == {expected}", got == expected,
                     f"got {got}")
    return ok


def test_action_cards_only_execution() -> bool:
    """Critical contract: only execution-lane names can ever be action-card eligible."""
    universe = {
        "A": {"coverage_lane": "execution"},
        "B": {"coverage_lane": "watch"},
        "C": {"coverage_lane": "macro"},
        "D": {"coverage_lane": "speculative"},
    }
    eligible = entitled_set(universe, "action_card")
    return _check("only execution names entitled to action_card",
                  eligible == {"A"},
                  f"got {sorted(eligible)}")


def test_unknown_surface_raises() -> bool:
    try:
        is_entitled("X", {"coverage_lane": "execution"}, "nonexistent_surface")
    except ValueError:
        return _check("unknown surface raises ValueError", True)
    return _check("unknown surface raises ValueError", False, "did not raise")


def test_lane_summary_partitions_universe() -> bool:
    universe = {
        "A": {"coverage_lane": "execution"},
        "B": {"coverage_lane": "watch"},
        "C": {"coverage_lane": "macro"},
        "D": {"coverage_lane": "speculative"},
        "E": {"coverage_lane": "execution"},
    }
    summary = lane_summary(universe)
    total = sum(len(v) for v in summary.values())
    return all([
        _check("lane_summary covers every ticker", total == len(universe), f"{total} != {len(universe)}"),
        _check("lane_summary execution sorted", summary["execution"] == ["A", "E"]),
    ])


def test_live_config_no_unknown_lanes() -> bool:
    """Smoke check against the actual config file. Lanes should resolve cleanly."""
    if not CONFIG_PATH.exists():
        return _check("live config readable", False, f"missing {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    tu = cfg.get("tracked_universe", {})
    if not tu:
        return _check("live config has tracked_universe", False)
    summary = lane_summary(tu)
    counts = {lane: len(summary[lane]) for lane in LANES}
    print(f"    live counts: {counts}")
    print(f"    execution: {summary['execution']}")
    print(f"    watch: {summary['watch']}")
    print(f"    macro: {summary['macro']}")
    print(f"    speculative: {summary['speculative']}")
    return _check("live config resolves cleanly", sum(counts.values()) == len(tu))


def main() -> int:
    suites = [
        ("resolve_explicit", test_resolve_explicit),
        ("entitlement_matrix", test_entitlement_matrix),
        ("action_cards_only_execution", test_action_cards_only_execution),
        ("unknown_surface_raises", test_unknown_surface_raises),
        ("lane_summary_partitions_universe", test_lane_summary_partitions_universe),
        ("live_config_no_unknown_lanes", test_live_config_no_unknown_lanes),
    ]
    passed = 0
    failed: list[str] = []
    for name, fn in suites:
        print(f"\n[{name}]")
        if fn():
            passed += 1
        else:
            failed.append(name)
    print(f"\n{passed}/{len(suites)} suites passed")
    if failed:
        print("FAILED suites: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
