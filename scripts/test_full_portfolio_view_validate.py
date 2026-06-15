from __future__ import annotations

from full_portfolio_view_validate import validate_report


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def base_report() -> dict:
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-12T00:00:00Z",
        "window": "post-close",
        "market_data_as_of": "2026-05-11",
        "source_artifacts": [{"name": "trigger_sheet", "exists": True, "last_trading_day": "2026-05-11"}],
        "authority": {
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "owner_approval_granted": False,
            "sizing_or_weight_change_allowed": False,
            "trade_execution_allowed": False,
            "generated_report_is_canonical": False,
        },
        "summary": {"deployable_now_review_only": ["AAA"], "prepare_or_wait": [], "do_not_touch": [], "watch": [], "bench_or_repair": [], "monitor": []},
        "records": [{"ticker": "AAA", "source_provenance": ["portfolio_config"], "action_bucket": "deployable_now_review_only"}],
        "rendered_outputs": {"json": "tmp/full-portfolio-view.json"},
    }


def main() -> int:
    ok = validate_report(base_report())
    require(ok["status"] == "ok", f"valid report should pass, got {ok}")
    bad = base_report()
    bad["authority"]["trade_execution_allowed"] = True
    result = validate_report(bad)
    require(result["status"] == "critical", "authority widening should fail closed")
    require(any(f["code"] == "authority_not_fail_closed" for f in result["findings"]), "authority failure should be explicit")
    missing = base_report()
    missing["records"] = [{"ticker": "AAA", "action_bucket": "monitor"}]
    result = validate_report(missing)
    require(any(f["code"] == "record_provenance_missing" for f in result["findings"]), "missing provenance should fail")
    stale_theme = base_report()
    stale_theme["market_view"] = {"current_investment_themes": [{"read": "JPM is below stop despite owner-approval history"}]}
    result = validate_report(stale_theme)
    require(result["status"] == "critical", "stale hard-coded theme prose should fail validation")
    require(any(f["code"] == "stale_theme_language" for f in result["findings"]), "stale theme finding should be explicit")
    print("full_portfolio_view_validate_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
