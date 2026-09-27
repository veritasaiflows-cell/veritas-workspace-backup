from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fundamental_metrics_refresh as mod
import validate_fundamental_metrics as validator


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_period_alias_candidate_order(errors: list[str]) -> None:
    aliases = {
        ("AMD", "2026-03-31"): {
            "ticker": "AMD",
            "workspace_expected_period_end": "2026-03-31",
            "fiscal_quarter_end_confirmed": "2026-03-28",
            "mapping_verdict": "legitimate_period_convention_mismatch",
            "mapping_rationale": "test mapping",
        }
    }
    candidates = mod.period_end_candidates("AMD", "2026-03-31", aliases)
    expect([c["period_end"] for c in candidates] == ["2026-03-31", "2026-03-28"], f"alias candidate order wrong: {candidates}", errors)
    expect(candidates[1]["mapping_source"] == "review_confirmed_period_alias", "alias source missing", errors)


def test_sec_fact_alias_match_carries_mapping(errors: list[str]) -> None:
    companyfacts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"val": 10253000000, "form": "10-Q", "end": "2026-03-28", "frame": "CY2026Q1", "filed": "2026-05-05"}
                        ]
                    }
                }
            }
        }
    }
    candidates = [
        {"period_end": "2026-03-31", "mapping_source": "workspace_period", "mapped_from": None, "mapping_verdict": None},
        {"period_end": "2026-03-28", "mapping_source": "review_confirmed_period_alias", "mapped_from": "2026-03-31", "mapping_verdict": "legitimate_period_convention_mismatch", "mapping_rationale": "test mapping"},
    ]
    fact = mod.sec_fact_latest_for_period_candidates(companyfacts, "revenue", candidates, "quarterly")
    expect(fact is not None, "alias fact should resolve", errors)
    expect((fact or {}).get("period_end") == "2026-03-28", f"unexpected fact: {fact}", errors)
    expect(((fact or {}).get("period_mapping") or {}).get("workspace_period_end") == "2026-03-31", f"mapping missing: {fact}", errors)


def test_net_income_definition_match_prefers_like_for_like(errors: list[str]) -> None:
    companyfacts = {
        "facts": {
            "us-gaap": {
                "NetIncomeLossAvailableToCommonStockholdersBasic": {
                    "units": {
                        "USD": [
                            {"val": 5403000000, "form": "10-Q", "end": "2026-03-31", "frame": "CY2026Q1", "filed": "2026-05-01"}
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {"val": 5630000000, "form": "10-Q", "end": "2026-03-31", "frame": "CY2026Q1", "filed": "2026-05-01"}
                        ]
                    }
                },
            }
        }
    }
    record = {
        "sector": "Financials",
        "income_statement_source_rows": {"net_income": "Net Income"},
    }
    candidates = [{"period_end": "2026-03-31", "mapping_source": "workspace_period", "mapped_from": None, "mapping_verdict": None}]
    fact = mod.sec_fact_latest_for_period_candidates(companyfacts, "net_income", candidates, "quarterly", record, 5630000000)
    expect(fact is not None, "net-income fact should resolve", errors)
    expect((fact or {}).get("concept") == "NetIncomeLoss", f"wrong net-income concept selected: {fact}", errors)
    expect((fact or {}).get("selection_method") == "same_period_best_definition_match", f"selection method missing: {fact}", errors)
    alternates = (fact or {}).get("alternate_sec_facts") or []
    expect(any(alt.get("concept") == "NetIncomeLossAvailableToCommonStockholdersBasic" for alt in alternates), f"alternate common-stockholder concept missing: {fact}", errors)


def test_ticker_metadata_repair_is_deduplicated_and_review_only(errors: list[str]) -> None:
    findings = [
        {
            "severity": "critical",
            "code": "bank_official_capital_period_mismatch",
            "ticker": "JPM",
            "evidence": {
                "local_period_end": "2026-06-30",
                "official_period": "1Q26 / March 31, 2026",
                "official_period_field": field,
                "official_source_url": "https://example.test/jpm-capital",
            },
        }
        for field in ("risk_based_capital_period", "cet1_ratio_period", "tier1_ratio_period")
    ]
    repairs = validator.build_repair_queue(findings)
    expect(len(repairs) == 1, f"expected one deduplicated repair: {repairs}", errors)
    repair = repairs[0] if repairs else {}
    expect(repair.get("ticker") == "JPM", f"ticker missing: {repair}", errors)
    expect(repair.get("deduplicated_finding_count") == 3, f"deduplicated count wrong: {repair}", errors)
    expect(repair.get("blocks_ticker_only") is True, f"ticker scope missing: {repair}", errors)
    expect(repair.get("source_open_required") is True and repair.get("manual_review_required") is True, f"review posture missing: {repair}", errors)
    evidence = repair.get("evidence") or {}
    expect(evidence.get("local_period_end") == "2026-06-30", f"local period evidence missing: {repair}", errors)
    expect(evidence.get("official_period") == "1Q26 / March 31, 2026", f"official period evidence missing: {repair}", errors)
    expect(evidence.get("official_period_fields") == ["cet1_ratio_period", "risk_based_capital_period", "tier1_ratio_period"], f"field evidence missing: {repair}", errors)
    authority = repair.get("authority") or {}
    for key, expected in validator.REPAIR_AUTHORITY_BOUNDARY.items():
        expect(authority.get(key) is expected, f"repair authority mismatch for {key}: {repair}", errors)
    reversed_repairs = validator.build_repair_queue(list(reversed(findings)))
    expect(reversed_repairs and reversed_repairs[0].get("fingerprint") == repair.get("fingerprint"), f"repair fingerprint is not stable: {reversed_repairs}", errors)


def test_distinct_ticker_repairs_remain_isolated(errors: list[str]) -> None:
    findings = [
        {
            "severity": "critical",
            "code": "bank_official_capital_period_mismatch",
            "ticker": ticker,
            "evidence": {
                "local_period_end": local_period,
                "official_period": official_period,
                "official_period_field": "risk_based_capital_period",
            },
        }
        for ticker, local_period, official_period in (
            ("JPM", "2026-06-30", "1Q26 / March 31, 2026"),
            ("GS", "2026-06-30", "2Q26 / June 30, 2026 restatement"),
        )
    ]
    repairs = validator.build_repair_queue(findings)
    expect([item.get("ticker") for item in repairs] == ["GS", "JPM"], f"ticker repairs were merged: {repairs}", errors)
    expect(all(item.get("blocks_ticker_only") is True for item in repairs), f"ticker-only scope was widened: {repairs}", errors)


def statement(columns: list[str], values: dict[str, list[float | None]]):
    import pandas as pd

    frame = pd.DataFrame(
        {pd.Timestamp(col): [values[row][i] for row in ("revenue", "net_income", "eps")] for i, col in enumerate(columns)},
        index=["Total Revenue", "Net Income", "Diluted EPS"],
    )
    return frame, {"revenue": "Total Revenue", "net_income": "Net Income", "diluted_eps": "Diluted EPS"}


def test_fully_reported_newest_quarter_is_not_skipped(errors: list[str]) -> None:
    cols = ["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31"]
    nan = None
    frame, rows = statement(cols, {
        "revenue": [7.0e9, 6.5e9, 6.6e9, 6.4e9, 6.3e9, 6.0e9],
        "net_income": [1.0e9, 0.9e9, 0.95e9, 0.9e9, nan, 0.8e9],
        "eps": [2.6, 2.4, 2.5, 2.3, nan, 2.1],
    })
    current, prior, metrics = mod.latest_comparable_pair(frame, rows, lag=4)
    expect(str(current.date()) == "2026-06-30" and str(prior.date()) == "2025-06-30",
           f"newest fully reported quarter skipped for an older one: {current} vs {prior}", errors)
    expect(metrics.get("net_income_prior") is None and metrics.get("diluted_eps_prior") is None,
           f"year-ago gaps must stay missing, not be filled: {metrics}", errors)
    # A newest quarter that is not fully reported keeps the completeness fallback.
    frame, rows = statement(cols, {
        "revenue": [7.0e9, 6.5e9, 6.6e9, 6.4e9, 6.3e9, 6.0e9],
        "net_income": [nan, 0.9e9, 0.95e9, 0.9e9, nan, 0.8e9],
        "eps": [nan, 2.4, 2.5, 2.3, nan, 2.1],
    })
    current, _, _ = mod.latest_comparable_pair(frame, rows, lag=4)
    expect(str(current.date()) == "2026-03-31", f"partial newest quarter should fall back: {current}", errors)


def test_implausible_price_to_book_is_missing_not_zero(errors: list[str]) -> None:
    record: dict = {}
    expect(mod.plausible_price_to_book(0.0011, record) is None, "BRK-B style 0.0011 P/B must be rejected", errors)
    expect(record.get("price_to_book_provider_rejected") == 0.0011, f"rejected value not recorded: {record}", errors)
    for value, want in ((1.534, 1.53), (0.05, 0.05), (-4.2, -4.2), (None, None)):
        record = {}
        got = mod.plausible_price_to_book(value, record)
        expect(got == want and "price_to_book_provider_rejected" not in record,
               f"plausible P/B {value!r} changed to {got!r} ({record})", errors)


def main() -> int:
    errors: list[str] = []
    test_fully_reported_newest_quarter_is_not_skipped(errors)
    test_implausible_price_to_book_is_missing_not_zero(errors)
    test_period_alias_candidate_order(errors)
    test_sec_fact_alias_match_carries_mapping(errors)
    test_net_income_definition_match_prefers_like_for_like(errors)
    test_ticker_metadata_repair_is_deduplicated_and_review_only(errors)
    test_distinct_ticker_repairs_remain_isolated(errors)
    if errors:
        print("fundamental_metrics_period_mapping_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("fundamental_metrics_period_mapping_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
