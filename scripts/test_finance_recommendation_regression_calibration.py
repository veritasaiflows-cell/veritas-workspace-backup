from __future__ import annotations

import json
import tempfile
from pathlib import Path

import finance_recommendation_regression_calibration as mod


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def paths(base: Path, ledger: dict, shadow: dict | None = None) -> dict[str, Path]:
    return {
        "performance_digest": write_json(base / "performance.json", {"status": "ok"}),
        "shadow_scorecard": write_json(base / "shadow.json", shadow or {"status": "ok", "scores": []}),
        "recommendation_ledger": write_json(base / "ledger.json", ledger),
    }


def tracked_row(ticker: str, signal: float | None, return_pct: float | None, horizon: int = 1) -> dict:
    return {
        "ledger_event_id": f"ledger_{ticker}_{signal}_{return_pct}_{horizon}",
        "ticker": ticker,
        "payload": {"recommendation_id": f"rec_{ticker}", "signal_score": signal},
        "forward_scorecard": {
            "known_at_time": {"anchor_price": 100.0, "entry_band_low": 90.0, "entry_band_high": 110.0},
            "checkpoints": [
                {
                    "horizon_days": horizon,
                    "status": "observed" if return_pct is not None else "pending_window",
                    "observed_price": 100.0 + (return_pct or 0.0) if return_pct is not None else None,
                    "absolute_return_pct": return_pct,
                }
            ],
        },
    }


def test_insufficient_sample_blocks_predictive_claims() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        report = mod.build_report(
            paths(
                base,
                {
                    "status": "ok",
                    "tracked_rows": [
                        tracked_row("VRT", 0.7, None),
                        tracked_row("GOOG", 0.8, None),
                    ],
                },
            )
        )
        assert report["status"] == "review_only_calibration_not_ready"
        assert report["sample_counts"]["scored_row_count"] == 0
        assert report["walk_forward_readiness"]["classification"] == "not_ready_no_scored_outcomes"
        assert report["regression_diagnostics"]["status"] == "insufficient_numeric_pairs"
        assert report["authority_boundary"]["predictive_skill_claim_allowed_now"] is False
        assert report["decision_contract"]["cannot_rank_capital_deployment"] is True
        assert "insufficient_sample_no_predictive_skill_claim" in report["validation"]["warnings"]


def test_numeric_slope_and_correlation_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ledger = {
            "status": "ok",
            "tracked_rows": [
                tracked_row("AAA", 1.0, 2.0),
                tracked_row("BBB", 2.0, 4.0),
                tracked_row("CCC", 3.0, 6.0),
                tracked_row("DDD", 4.0, 8.0),
            ],
        }
        report = mod.build_report(paths(base, ledger))
        regression = report["regression_diagnostics"]
        assert regression["status"] == "computed_review_only"
        assert regression["pair_count"] == 4
        assert regression["slope"] == 2.0
        assert regression["intercept"] == 0.0
        assert regression["correlation"] == 1.0
        assert report["grouped_average_forward_returns"][0]["average_forward_return_pct"] == 5.0
        assert report["authority_boundary"]["capital_deployment_approved"] is False


if __name__ == "__main__":
    test_insufficient_sample_blocks_predictive_claims()
    test_numeric_slope_and_correlation_path()
    print("finance_recommendation_regression_calibration_tests_passed")
