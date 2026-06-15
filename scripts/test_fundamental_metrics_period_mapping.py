from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fundamental_metrics_refresh as mod


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


def main() -> int:
    errors: list[str] = []
    test_period_alias_candidate_order(errors)
    test_sec_fact_alias_match_carries_mapping(errors)
    test_net_income_definition_match_prefers_like_for_like(errors)
    if errors:
        print("fundamental_metrics_period_mapping_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("fundamental_metrics_period_mapping_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
