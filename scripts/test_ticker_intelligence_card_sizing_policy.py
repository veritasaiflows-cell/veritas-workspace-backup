from __future__ import annotations

from ticker_intelligence_card import build_missing_and_stale


def families(rows: list[dict[str, str]]) -> set[str]:
    return {row.get("family", "") for row in rows}


def test_tier_c_monitor_missing_sizing_is_expected_context() -> None:
    rows = build_missing_and_stale(
        "PAVE",
        fundamentals={"ticker": "PAVE"},
        readiness=None,
        post_close_quote=None,
        deployment_entry={"ticker": "PAVE"},
        analyst_entry={"ticker": "PAVE"},
        universe_entry={"ticker": "PAVE", "tier": "C"},
        auto_tier_entry={"ticker": "PAVE", "auto_tier": "Tier C", "auto_state": "C-MONITOR"},
    )
    assert "price_band_stop_position_sizing" not in families(rows)


def test_tier_b_missing_sizing_remains_repair_debt() -> None:
    rows = build_missing_and_stale(
        "XLB",
        fundamentals={"ticker": "XLB"},
        readiness=None,
        post_close_quote=None,
        deployment_entry={"ticker": "XLB"},
        analyst_entry={"ticker": "XLB"},
        universe_entry={"ticker": "XLB", "tier": "C"},
        auto_tier_entry={"ticker": "XLB", "auto_tier": "Tier B", "auto_state": "B-VALIDATED"},
    )
    assert "price_band_stop_position_sizing" in families(rows)


if __name__ == "__main__":
    test_tier_c_monitor_missing_sizing_is_expected_context()
    test_tier_b_missing_sizing_remains_repair_debt()
    print("ticker_intelligence_card_sizing_policy: ok")
