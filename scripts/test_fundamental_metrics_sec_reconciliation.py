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


def test_financial_subtypes_are_not_all_banks(errors: list[str]) -> None:
    expect(mod.financial_company_subtype({"ticker": "JPM", "sector": "Financials"}) == "bank_broker", "JPM should be bank_broker", errors)
    expect(mod.financial_company_subtype({"ticker": "GS", "sector": "Financials"}) == "bank_broker", "GS should be bank_broker", errors)
    expect(mod.financial_company_subtype({"ticker": "ALL", "sector": "Financials", "industry": "Property & Casualty Insurance"}) == "insurer", "ALL should be insurer", errors)
    expect(mod.financial_company_subtype({"ticker": "APO", "sector": "Financials", "industry": "Asset Management & Custody Banks"}) == "asset_manager", "APO should be asset_manager", errors)
    expect(mod.financial_company_subtype({"ticker": "MA", "sector": "Financials", "industry": "Payments"}) == "payments_network", "MA should be payments_network", errors)
    expect(not mod.is_bank_sector({"ticker": "ALL", "sector": "Financials", "industry": "Property & Casualty Insurance"}), "ALL must not inherit bank-native rules", errors)


def test_net_income_reclassification_keeps_common_stockholder_as_context(errors: list[str]) -> None:
    companyfacts = {
        "facts": {
            "us-gaap": {
                "NetIncomeLossAvailableToCommonStockholdersBasic": {
                    "units": {"USD": [{"val": 685000000, "form": "10-Q", "end": "2026-03-31", "frame": "CY2026Q1", "filed": "2026-05-08"}]}
                },
                "NetIncomeLoss": {
                    "units": {"USD": [{"val": 695000000, "form": "10-Q", "end": "2026-03-31", "frame": "CY2026Q1", "filed": "2026-05-08"}]}
                },
            }
        }
    }
    record = {
        "ticker": "ABBV",
        "sector": "Health Care",
        "period_type": "quarterly",
        "income_statement_source_rows": {"net_income": "Net Income"},
    }
    fact = mod.sec_fact_latest_for_date(companyfacts, "net_income", "2026-03-31", "quarterly", record, 695000000)
    expect(fact is not None, "net income fact should resolve", errors)
    expect((fact or {}).get("concept") == "NetIncomeLoss", f"wrong concept selected: {fact}", errors)
    expect((fact or {}).get("selection_method") == "same_period_best_definition_match", f"wrong selection method: {fact}", errors)
    alternates = (fact or {}).get("alternate_sec_facts") or []
    expect(any(item.get("concept") == "NetIncomeLossAvailableToCommonStockholdersBasic" for item in alternates), f"alternate context missing: {fact}", errors)


def test_nearby_period_match_classifies_alias_candidate(errors: list[str]) -> None:
    companyfacts = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [{"val": 1000, "form": "10-Q", "end": "2026-04-26", "frame": "CY2026Q1", "filed": "2026-05-20"}]}},
                "NetIncomeLoss": {"units": {"USD": [{"val": 200, "form": "10-Q", "end": "2026-04-26", "frame": "CY2026Q1", "filed": "2026-05-20"}]}},
                "EarningsPerShareDiluted": {"units": {"USD/shares": [{"val": 2.0, "form": "10-Q", "end": "2026-04-26", "frame": "CY2026Q1", "filed": "2026-05-20"}]}},
            }
        }
    }
    record = {
        "ticker": "TEST",
        "sector": "Information Technology",
        "instrument_type": "equity",
        "period_type": "quarterly",
        "period_end": "2026-04-30",
        "revenue": 1000,
        "net_income": 200,
        "diluted_eps": 2.0,
        "income_statement_source_rows": {"revenue": "Total Revenue", "net_income": "Net Income", "diluted_eps": "Diluted EPS"},
    }
    result = {"metrics": {}, "notes": []}
    mod.classify_no_period_reconciliation("TEST", record, companyfacts, result)
    expect(result.get("status") == "matched_via_period_alias", f"nearby period status wrong: {result}", errors)
    expect((result.get("period_mapping") or {}).get("mapping_source") == "auto_detected_nearby_fiscal_period", f"mapping missing: {result}", errors)


def main() -> int:
    errors: list[str] = []
    test_financial_subtypes_are_not_all_banks(errors)
    test_net_income_reclassification_keeps_common_stockholder_as_context(errors)
    test_nearby_period_match_classifies_alias_candidate(errors)
    if errors:
        print("fundamental_metrics_sec_reconciliation_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("fundamental_metrics_sec_reconciliation_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
