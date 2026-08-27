from wf78_tier_c_to_b_auto_promotion_pipeline import (
    OFFICIAL_SOURCE_URLS,
    PHASE2_EVIDENCE_LABELS,
    analyst_context_available,
    official_earnings_capture_detail,
    phase2_evidence_row,
    repair_burden_acceptable,
    select_capacity_approved_tickers,
    unresolved_repair_blockers,
)


ATTENTION_SOURCE_OPEN_TICKERS = {
    "AVGO",
    "CCL",
    "CEG",
    "DASH",
    "EMR",
    "QCOM",
    "SCCO",
    "TDG",
    "TSM",
    "TXN",
}


def test_attention_candidates_have_official_source_urls() -> None:
    missing = [
        ticker
        for ticker in sorted(ATTENTION_SOURCE_OPEN_TICKERS)
        if not OFFICIAL_SOURCE_URLS.get(ticker, {}).get("url", "").startswith("https://")
    ]
    assert missing == []


def test_phase2_complete_candidate_eligible_without_attention_row() -> None:
    request = {
        "ticker": "ALLE",
        "name": "Allegion",
        "from_tier": "tier_c",
        "to_tier": "tier_b",
        "current_state": "C-CANDIDATE",
        "evidence_present": list(PHASE2_EVIDENCE_LABELS.values()),
    }
    decision = {
        "ticker": "ALLE",
        "name": "Allegion",
        "from_tier": "tier_c",
        "to_tier": "tier_b",
        "current_state": "C-CANDIDATE",
        "status": "eligible_for_admission",
        "required_evidence_count": len(PHASE2_EVIDENCE_LABELS),
        "evidence_present_count": len(PHASE2_EVIDENCE_LABELS),
        "missing_evidence": [],
        "admission_executed": False,
    }

    card = {
        "ticker": "ALLE",
        "latest_earnings_performance": {
            "status": "available",
            "period_end": "2026-03-31",
            "official_adjusted_eps": {"status": "available"},
        },
    }

    row = phase2_evidence_row("ALLE", request, decision, card, OFFICIAL_SOURCE_URLS)

    assert row["candidate_source"] == "phase2_funnel"
    assert row["status"] == "eligible_for_tier_b_research_bench"
    assert row["failed_evidence_families"] == []
    assert row["tier_b_research_bench_label_approved"] is False
    assert row["capital_deployment_approved"] is False
    assert row["trade_or_execution_approved"] is False
    assert row["would_mutate_universe"] is False
    assert row["official_source"]["url"].startswith("https://")


def test_official_capture_accepts_latest_metrics_with_official_source() -> None:
    card = {
        "latest_earnings_performance": {
            "status": "available",
            "period_end": "2026-03-31",
            "revenue": 100,
            "diluted_eps": 1.23,
            "official_adjusted_eps": {
                "status": "missing_manual_required",
                "manual_capture_required": True,
                "value": None,
            },
        },
    }

    detail = official_earnings_capture_detail(
        card,
        {"label": "Official earnings release", "url": "https://example.com/official-earnings"},
    )

    assert detail["gate_passed"] is True
    assert detail["capture_mode"] == "latest_earnings_metrics_with_source_open"
    assert detail["official_adjusted_eps_detail_unresolved"] is True
    assert detail["manual_capture_required_for_base_gate"] is False


def test_official_capture_still_requires_source_open_proof() -> None:
    card = {
        "latest_earnings_performance": {
            "status": "available",
            "period_end": "2026-03-31",
            "revenue": 100,
            "diluted_eps": 1.23,
            "official_adjusted_eps": {
                "status": "missing_manual_required",
                "manual_capture_required": True,
                "value": None,
            },
        },
    }

    detail = official_earnings_capture_detail(card, None)

    assert detail["gate_passed"] is False
    assert detail["capture_mode"] == "blocked_missing_official_source"


def test_capacity_selector_holds_eligible_rows_over_tier_b_cap() -> None:
    rows = [
        {"ticker": "AAA", "status": "eligible_for_tier_b_research_bench", "attention_score": 90},
        {"ticker": "BBB", "status": "eligible_for_tier_b_research_bench", "attention_score": 80},
        {"ticker": "CCC", "status": "eligible_for_tier_b_research_bench", "attention_score": 70},
    ]

    approved, newly_approved, held, remaining = select_capacity_approved_tickers(
        rows,
        existing_approved={"CCC"},
        current_router_tier_b={f"OLD{i}" for i in range(49)},
        cap=50,
    )

    assert remaining == 1
    assert newly_approved == ["AAA"]
    assert approved == ["AAA", "CCC"]
    assert held == ["BBB"]


def test_analyst_context_does_not_require_buy_skew() -> None:
    card = {
        "analyst_consensus_ratings_targets": {
            "status": "auto_sourced_yfinance",
            "consensus_rating": "Sell skew",
            "buy_count": 2,
            "hold_count": 5,
            "sell_count": 4,
            "source_url": "https://finance.yahoo.com/quote/SCCO/analysis",
        }
    }

    assert analyst_context_available(card) is True


def test_repair_burden_allows_visible_warnings_but_blocks_hard_blockers() -> None:
    assert repair_burden_acceptable([], "ABOVE_BAND_WAIT") is True
    assert repair_burden_acceptable(["high_leverage"], "ABOVE_BAND_WAIT") is False
    assert repair_burden_acceptable([], "BELOW_STOP") is False


def test_repaired_source_and_technical_context_clear_stale_blocker_text() -> None:
    blockers = [
        "official_growth_bridge_source_open_required",
        "official_guidance_source_open_required",
        "orders_backlog_manual_capture_required",
        "technical_posture_missing",
    ]

    assert unresolved_repair_blockers(blockers, source_open=True, technical_ok=True) == []
    assert unresolved_repair_blockers(blockers, source_open=True, technical_ok=False) == ["technical_posture_missing"]


if __name__ == "__main__":
    test_attention_candidates_have_official_source_urls()
    test_phase2_complete_candidate_eligible_without_attention_row()
    test_official_capture_accepts_latest_metrics_with_official_source()
    test_official_capture_still_requires_source_open_proof()
    test_capacity_selector_holds_eligible_rows_over_tier_b_cap()
    test_analyst_context_does_not_require_buy_skew()
    test_repair_burden_allows_visible_warnings_but_blocks_hard_blockers()
    test_repaired_source_and_technical_context_clear_stale_blocker_text()
    print("ok")
