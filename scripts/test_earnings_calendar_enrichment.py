from __future__ import annotations

import json
from pathlib import Path

import earnings_calendar_enrichment as mod

WORKSPACE = Path(__file__).resolve().parents[1]
EARNINGS_PATH = WORKSPACE / "tmp" / "earnings-calendar.json"
BAND_PROPOSALS_PATH = WORKSPACE / "tmp" / "band-proposals.json"
DASHBOARD_DATA_PATH = WORKSPACE / "tmp" / "dashboard-data.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def test_earnings_calendar_records_expose_source_confidence(errors: list[str]) -> None:
    payload = load_json(EARNINGS_PATH)
    records = {row.get("ticker"): row for row in payload.get("records", []) if isinstance(row, dict) and row.get("ticker")}
    expect(bool(records), "earnings-calendar should contain records", errors)
    for ticker, record in records.items():
        expect("date_source_class" in record, f"{ticker} missing date_source_class", errors)
        expect("primary_confirmed" in record, f"{ticker} missing primary_confirmed", errors)
        if record.get("source") == "yfinance" and record.get("next_earnings_date"):
            expect(record.get("date_source_class") == "provider_estimate", f"{ticker} yfinance date should be provider_estimate: {record}", errors)
            expect(record.get("primary_confirmed") is False, f"{ticker} yfinance date should not be primary-confirmed: {record}", errors)

    for ticker in ["LIN", "ECL", "VMC", "META", "NFLX", "TMUS", "PH", "GE", "CME"]:
        expect(ticker in mod.COVERAGE, f"new sector-expansion equity missing from earnings coverage: {ticker}", errors)

    bkng = records.get("BKNG")
    expect(bool(bkng), "BKNG should be present in earnings-calendar", errors)
    if bkng:
        expect(bkng.get("next_earnings_date") == "2026-07-29", f"BKNG expected provider date 2026-07-29: {bkng}", errors)
        expect(bkng.get("date_source_class") == "provider_estimate", f"BKNG should stay provider_estimate: {bkng}", errors)
        expect(bkng.get("primary_confirmed") is False, f"BKNG should not be primary-confirmed: {bkng}", errors)


def test_bkng_source_confidence_propagates_to_review_artifacts(errors: list[str]) -> None:
    proposals_payload = load_json(BAND_PROPOSALS_PATH)
    proposals = {row.get("ticker"): row for row in proposals_payload.get("proposals", []) if isinstance(row, dict) and row.get("ticker")}
    bkng_proposal = proposals.get("BKNG")
    expect(bool(bkng_proposal), "BKNG should be present in band proposals", errors)
    if bkng_proposal:
        expect(bkng_proposal.get("earnings_date_source_class") == "provider_estimate", f"BKNG band proposal should carry provider_estimate: {bkng_proposal}", errors)
        expect(bkng_proposal.get("earnings_primary_confirmed") is False, f"BKNG band proposal should carry primary_confirmed=false: {bkng_proposal}", errors)
        expect(bkng_proposal.get("canonical_apply_eligible") is False, f"BKNG should remain non-applyable: {bkng_proposal}", errors)

    dashboard_payload = load_json(DASHBOARD_DATA_PATH)
    tech = {row.get("ticker"): row for row in dashboard_payload.get("technical", []) if isinstance(row, dict) and row.get("ticker")}
    bkng_dash = tech.get("BKNG")
    expect(bool(bkng_dash), "BKNG should be present in dashboard technical data", errors)
    if bkng_dash:
        expect(bkng_dash.get("earningsDateSourceClass") == "provider_estimate", f"BKNG dashboard data should carry provider_estimate: {bkng_dash}", errors)
        expect(bkng_dash.get("earningsPrimaryConfirmed") is False, f"BKNG dashboard data should carry primary_confirmed=false: {bkng_dash}", errors)


def main() -> int:
    errors: list[str] = []
    test_earnings_calendar_records_expose_source_confidence(errors)
    test_bkng_source_confidence_propagates_to_review_artifacts(errors)
    if errors:
        print("earnings_calendar_enrichment_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("earnings_calendar_enrichment_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
