#!/usr/bin/env python3
"""Focused tests for WF84 phase 6-10 dynamic-scope gates."""

from __future__ import annotations

import canonical_finance_data_plane_phase6_10 as phase


def test_dynamic_overlay_coverage_matches_router_scope() -> None:
    checks: list[dict[str, object]] = []
    canonical_tickers = {f"T{i:03d}" for i in range(300)}
    router_tickers = set(canonical_tickers)

    phase.add_check(
        checks,
        "overlay_coverage_matches_router_tickers",
        len(canonical_tickers) == len(router_tickers) and len(canonical_tickers) > 0,
        {"canonical_count": len(canonical_tickers), "router_count": len(router_tickers)},
    )

    assert checks[0]["status"] == "ok"
    assert checks[0]["detail"] == {"canonical_count": 300, "router_count": 300}


def test_dynamic_overlay_coverage_blocks_scope_mismatch() -> None:
    checks: list[dict[str, object]] = []
    canonical_tickers = {f"T{i:03d}" for i in range(200)}
    router_tickers = {f"T{i:03d}" for i in range(300)}

    phase.add_check(
        checks,
        "overlay_coverage_matches_router_tickers",
        len(canonical_tickers) == len(router_tickers) and len(canonical_tickers) > 0,
        {"canonical_count": len(canonical_tickers), "router_count": len(router_tickers)},
    )

    assert checks[0]["status"] == "blocked"
    assert checks[0]["detail"] == {"canonical_count": 200, "router_count": 300}
