from __future__ import annotations

import json
import tempfile
from pathlib import Path

import research_freshness_opportunity_review as mod


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_payload_composes_existing_outputs_review_only() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        tmp = root / "tmp"
        generated = "2026-05-13T22:00:00Z"
        sector_board = tmp / "sector-expansion-board.json"
        ticker_perf = tmp / "ticker-monitoring-performance.json"
        promo_csv = tmp / "sector-dashboard-promotion-queue.csv"
        dashboard = tmp / "sector-dashboard-suite.html"
        portfolio_config = tmp / "portfolio-config.json"
        write_json(sector_board, {
            "generated_at_utc": generated,
            "status": "ok",
            "summary": {
                "improving_leadership_sectors": ["Health Care"],
                "underexposed_sectors": ["Health Care"],
                "promotion_review_candidates": ["LLY"],
            },
            "sectors": [
                {
                    "ticker": "XLV",
                    "sector": "Health Care",
                    "leadership_status": "improving_leadership",
                    "underexposed": True,
                    "promotion_review_status": [
                        {
                            "candidate": "LLY",
                            "promotion_review_pending": True,
                            "blocking_gate": "sizing / explicit promotion judgment",
                            "automated_queue_judgment": "hold in promotion review",
                            "next_action": "manual review only",
                        }
                    ],
                }
            ],
        })
        write_json(ticker_perf, {
            "generated_at_utc": generated,
            "status": "ok",
            "history_status": {"outcome_analytics_ready": False},
            "summary": {"fail_closed_tickers": []},
            "tickers": [
                {
                    "ticker": "LLY",
                    "known_at_time": {"data_date": "2026-05-13", "close": 720.0},
                    "workflow_state": "WATCH",
                    "deployment_status": "ALMOST DEPLOYABLE",
                    "band_status": "ABOVE_BAND",
                    "below_stop_or_repair": False,
                    "monitoring_flags": ["band_review_required"],
                    "blocked_reasons": ["band_review_debt"],
                }
            ],
        })
        promo_csv.write_text(
            "Candidate,Sector,ETF,Blocking Gate,Queue Judgment,Next Action,Owner Approval Granted,Watchlist Promotion Allowed\n"
            "LLY,Health Care,XLV,sizing / explicit promotion judgment,hold in promotion review,manual review only,No,No\n",
            encoding="utf-8",
        )
        dashboard.write_text("<html></html>", encoding="utf-8")
        write_json(portfolio_config, {
            "generated_at_utc": generated,
            "tracked_universe": {
                "LIN": {
                    "workflow_state": "PROMOTION REVIEW",
                    "portfolio_role": "portfolio_review_candidate",
                    "sector": "Materials",
                    "thesis_status": "Owner-approved portfolio-review candidate 2026-05-15; review-only.",
                },
                "ECL": {
                    "workflow_state": "WATCH",
                    "portfolio_role": "sector_monitor",
                    "sector": "Materials",
                    "thesis_status": "promoted 2026-05-15 to machine-tracked Materials research monitor",
                },
            },
        })

        old_workspace = mod.WORKSPACE
        try:
            mod.WORKSPACE = root
            payload = mod.build_payload(
                "post-close",
                sector_board_path=sector_board,
                ticker_performance_path=ticker_perf,
                promotion_queue_path=promo_csv,
                dashboard_html_path=dashboard,
                portfolio_config_path=portfolio_config,
            )
        finally:
            mod.WORKSPACE = old_workspace

    assert payload["consumer_posture"] == "review_only"
    assert all(value is False for value in payload["authority"].values())
    assert payload["research_freshness_review"]["future_realized_outcomes_used"] is False
    assert payload["opportunity_review"]["promotion_review_candidates"] == ["LLY"]
    assert payload["opportunity_review"]["blocked_or_review_required_candidates"] == ["LLY"]
    digest = payload["response_recommendation_digest"]
    assert digest["digest_posture"] == "review_only_opportunity_radar"
    assert digest["include_in_veritas_responses"] is True
    assert digest["portfolio_review_candidates"] == ["LIN"]
    assert "ECL" in digest["conditional_watch"]
    assert digest["blocked_or_deferred"] == ["LLY"]
    assert "no promotion" in digest["required_boundary_sentence"]
    candidate = next(row for row in payload["candidate_reviews"] if row["ticker"] == "LLY")
    assert candidate["owner_approval_granted"] is False
    assert candidate["watchlist_promotion_allowed"] is False
    assert candidate["monitoring_context_available"] is True
    assert candidate["blocked_reasons"] == ["band_review_debt"]


def test_validate_rejects_authority_drift() -> None:
    payload = {
        "consumer_posture": "review_only",
        "authority": dict(mod.AUTHORITY, capital_action_allowed=True),
        "research_freshness_review": {"future_realized_outcomes_used": False},
        "response_recommendation_digest": {
            "digest_posture": "review_only_opportunity_radar",
            "top_review_cues": [],
            "diversified_fund_regime_cues": {"review_only": True, "macro_correlation_required": True},
        },
        "candidate_reviews": [],
    }
    try:
        mod.validate_payload(payload)
    except ValueError as exc:
        assert "capital_action_allowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected authority drift rejection")


def test_validate_rejects_digest_authority_drift() -> None:
    payload = {
        "consumer_posture": "review_only",
        "authority": dict(mod.AUTHORITY),
        "research_freshness_review": {"future_realized_outcomes_used": False},
        "response_recommendation_digest": {
            "digest_posture": "review_only_opportunity_radar",
            "diversified_fund_regime_cues": {"review_only": True, "macro_correlation_required": True},
            "top_review_cues": [{"ticker": "LLY", "owner_approval_granted": True, "apply_allowed": False}],
        },
        "candidate_reviews": [],
    }
    try:
        mod.validate_payload(payload)
    except ValueError as exc:
        assert "digest authority drift" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected digest authority drift rejection")


def test_required_json_without_timestamp_degrades_and_is_not_fresh() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        tmp = root / "tmp"
        sector_board = tmp / "sector-expansion-board.json"
        ticker_perf = tmp / "ticker-monitoring-performance.json"
        write_json(sector_board, {"status": "ok", "summary": {}, "sectors": []})
        write_json(ticker_perf, {"status": "ok", "history_status": {"outcome_analytics_ready": False}, "summary": {}, "tickers": []})

        old_workspace = mod.WORKSPACE
        try:
            mod.WORKSPACE = root
            payload = mod.build_payload(
                "post-close",
                sector_board_path=sector_board,
                ticker_performance_path=ticker_perf,
                promotion_queue_path=tmp / "missing.csv",
                dashboard_html_path=tmp / "missing.html",
            )
        finally:
            mod.WORKSPACE = old_workspace

    assert payload["status"] == "degraded"
    assert payload["research_freshness_review"]["all_required_sources_fresh_enough"] is False
    assert set(payload["research_freshness_review"]["stale_or_missing_required_sources"]) == {
        "sector_expansion_board",
        "ticker_monitoring_performance",
    }
    assert any("unstamped" in warning for warning in payload["warnings"])


def test_fresh_monitoring_reconciles_stale_jpm_queue_text() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        tmp = root / "tmp"
        generated = "2026-06-12T21:00:00Z"
        sector_board = tmp / "sector-expansion-board.json"
        ticker_perf = tmp / "ticker-monitoring-performance.json"
        promo_csv = tmp / "sector-dashboard-promotion-queue.csv"
        dashboard = tmp / "sector-dashboard-suite.html"
        write_json(sector_board, {
            "generated_at_utc": generated,
            "status": "ok",
            "summary": {
                "improving_leadership_sectors": ["Financials"],
                "underexposed_sectors": [],
                "promotion_review_candidates": [],
            },
            "sectors": [
                {
                    "ticker": "XLF",
                    "sector": "Financials",
                    "leadership_status": "improving_leadership",
                    "underexposed": False,
                    "promotion_review_status": [
                        {
                            "candidate": "JPM",
                            "promotion_review_pending": False,
                            "blocking_gate": "below formal band / near invalidation",
                            "automated_queue_judgment": "approval recorded; trigger not live",
                            "next_action": (
                                "Explicit owner approval granted 2026-05-07, but latest close is below "
                                "the 306.82-318.12 band and close to 301.17 invalidation."
                            ),
                        }
                    ],
                }
            ],
        })
        write_json(ticker_perf, {
            "generated_at_utc": generated,
            "status": "ok",
            "history_status": {"outcome_analytics_ready": False},
            "summary": {"fail_closed_tickers": []},
            "tickers": [
                {
                    "ticker": "JPM",
                    "known_at_time": {"data_date": "2026-06-12", "close": 320.72},
                    "workflow_state": "ALMOST",
                    "deployment_status": "ALMOST DEPLOYABLE",
                    "band_status": "ABOVE_BAND_WAIT",
                    "below_stop_or_repair": False,
                    "monitoring_flags": ["band_review_required"],
                    "blocked_reasons": ["band_review_debt"],
                }
            ],
        })
        promo_csv.write_text(
            "Candidate,Sector,ETF,Blocking Gate,Queue Judgment,Next Action,Owner Approval Granted,Watchlist Promotion Allowed\n",
            encoding="utf-8",
        )
        dashboard.write_text("<html></html>", encoding="utf-8")

        old_workspace = mod.WORKSPACE
        try:
            mod.WORKSPACE = root
            payload = mod.build_payload(
                "post-close",
                sector_board_path=sector_board,
                ticker_performance_path=ticker_perf,
                promotion_queue_path=promo_csv,
                dashboard_html_path=dashboard,
                small_mid_cap_regime_feed_path=tmp / "missing-feed.json",
            )
        finally:
            mod.WORKSPACE = old_workspace

    row = next(item for item in payload["candidate_reviews"] if item["ticker"] == "JPM")
    assert row["stale_queue_text_reconciled"] is True
    assert row["band_status"] == "ABOVE_BAND_WAIT"
    assert row["blocking_gate"].startswith("above current band / no-chase")
    assert "below formal band" not in row["blocking_gate"].lower()
    assert "near invalidation" not in row["blocking_gate"].lower()
    assert "below the 306.82" not in row["next_action"]
    assert "320.72" in row["next_action"]
    assert "JPM" in payload["response_recommendation_digest"]["blocked_or_deferred"]
    cue = next(item for item in payload["response_recommendation_digest"]["top_review_cues"] if item["ticker"] == "JPM")
    assert str(cue["blocker"]).startswith("above current band / no-chase")


if __name__ == "__main__":
    test_payload_composes_existing_outputs_review_only()
    test_validate_rejects_authority_drift()
    test_validate_rejects_digest_authority_drift()
    test_required_json_without_timestamp_degrades_and_is_not_fresh()
    test_fresh_monitoring_reconciles_stale_jpm_queue_text()
    print("research_freshness_opportunity_review tests passed")
