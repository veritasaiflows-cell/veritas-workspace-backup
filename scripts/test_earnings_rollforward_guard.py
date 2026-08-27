from __future__ import annotations

from official_earnings_source_discovery import discover_from_sec_payload
from earnings_rollforward_guard import build_guard
from official_earnings_auto_capture import (
    _etn_matching_period_10q_bridge,
    _status,
    build_generic_source_captures,
)
import chain_manifest


def sec_payload() -> dict:
    rows = {
        "form": ["10-Q", "8-K"],
        "filingDate": ["2026-07-31", "2026-07-31"],
        "accessionNumber": ["0001551182-26-000030", "0001551182-26-000027"],
        "primaryDocument": ["etn-20260630.htm", "etn-20260731.htm"],
        "primaryDocDescription": ["10-Q", "8-K"],
        "reportDate": ["2026-06-30", "2026-07-31"],
    }
    return {"filings": {"recent": rows}}


def exhibit_index() -> dict:
    return {"directory": {"item": [{"name": "etn06302026exhibit99.htm"}, {"name": "etn-20260731.htm"}]}}


def test_sec_discovery_resolves_new_period_and_exhibit() -> None:
    result = discover_from_sec_payload(
        ticker="ETN",
        cik="1551182",
        submissions=sec_payload(),
        index_payloads={"0001551182-26-000027": exhibit_index()},
        current_period_end="2026-03-31",
    )
    assert result["status"] == "new_source_detected"
    assert result["latest_detected_period_end"] == "2026-06-30"
    assert result["period_slug"] == "q2-2026"
    assert result["source_url"].endswith("/etn06302026exhibit99.htm")
    assert result["report_source_url"].endswith("/etn-20260630.htm")


def test_sec_discovery_ranks_ex99_variants_and_rejects_irrelevant_exhibits() -> None:
    variants = {
        "AMD": "amd-q2-ex99_1.htm",
        "GOOG": "goog-ex991.htm",
        "LMT": "lmt-ex99.htm",
        "MSFT": "msft-exhibit99_1.htm",
        "XOM": "xom-q2-ex99_1.htm",
    }
    for ticker, name in variants.items():
        result = discover_from_sec_payload(
            ticker=ticker,
            cik="1551182",
            submissions=sec_payload(),
            index_payloads={
                "0001551182-26-000027": {
                    "directory": {
                        "item": [
                            {"name": "employment-ex99_1.htm", "last-modified": "2026-07-31"},
                            {"name": name, "last-modified": "2026-07-31"},
                        ]
                    }
                }
            },
            current_period_end="2026-03-31",
        )
        assert result["status"] == "new_source_detected"
        assert result["source_url"].endswith("/" + name)
        assert result["candidate_score"] >= 54
        assert result["candidate_evidence"]

    rejected = discover_from_sec_payload(
        ticker="AMD",
        cik="1551182",
        submissions=sec_payload(),
        index_payloads={
            "0001551182-26-000027": {
                "directory": {"item": [{"name": "employment-ex99_1.htm", "last-modified": "2026-07-31"}]}
            }
        },
        current_period_end="2026-03-31",
    )
    assert rejected["status"] == "new_period_source_manual_required"
    assert rejected["source_type"] == "sec_10q_official_report"

    stale = discover_from_sec_payload(
        ticker="AMD",
        cik="1551182",
        submissions=sec_payload(),
        index_payloads={
            "0001551182-26-000027": {
                "directory": {"item": [{"name": "amd-ex99_1.htm", "last-modified": "2025-01-01"}]}
            }
        },
        current_period_end="2026-03-31",
    )
    assert stale["status"] == "new_period_source_manual_required"


def test_generic_capture_is_evidence_bearing_and_never_guesses_values() -> None:
    source_meta = {
        "ticker": "AMD",
        "source_url": "https://www.sec.gov/Archives/edgar/data/2488/example/amd-ex99_1.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/2488/example/index.htm",
        "period_end": "2026-06-27",
    }
    text = (
        "Financial results: adjusted earnings per share was reported. "
        "Guidance was reaffirmed. Revenue increased and backlog improved. "
        "The CEO said debt remains manageable."
    )
    captures = build_generic_source_captures(source_meta, text)
    assert len(captures) == 8
    assert _status({"known": 1, "unknown": None}, "exact official excerpt") == "manual_required"
    for field, block in captures.items():
        assert block["status"] == "manual_required", field
        assert block["value"] is None, field
        evidence = block["official_evidence"]
        assert evidence["field"] == field
        assert evidence["official_url"] == source_meta["source_url"]
        assert evidence["filing_url"] == source_meta["filing_url"]
        assert evidence["period_end"] == source_meta["period_end"]
        assert evidence["exact_official_excerpt"] == block["excerpt"]
    assert captures["adjusted_eps"]["official_evidence"]["exact_official_excerpt"]


def test_guard_emits_one_idempotent_catchup_row_without_editing_q1() -> None:
    registry = {
        "latest_by_ticker": {
            "ETN": {
                "ticker": "ETN",
                "period_end": "2026-03-31",
                "period_slug": "q1-2026",
                "capture_artifact": "tmp/official-ir-captures/etn-q1-2026.json",
                "validation_artifact": "tmp/official-ir-captures/etn-q1-2026-validation.json",
                "validation_clean": True,
                "capture_script": "etn_vrt_official_ir_capture.py",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000010/etn03312026exhibit99.htm",
            }
        }
    }

    def discoverer(**_kwargs: object) -> dict:
        return {
            "status": "new_source_detected",
            "ticker": "ETN",
            "latest_detected_period_end": "2026-06-30",
            "period_slug": "q2-2026",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000027/etn06302026exhibit99.htm",
        }

    first = build_guard(tracked={"ETN": {"earnings_policy": "timing_sensitive"}}, registry=registry, discoverer=discoverer)
    second = build_guard(tracked={"ETN": {"earnings_policy": "timing_sensitive"}}, registry=registry, discoverer=discoverer)
    assert first["summary"]["catch_up_required_count"] == 1
    assert first["tickers"][0]["status"] == "catch_up_required"
    assert second["tickers"][0]["status"] == first["tickers"][0]["status"]
    assert first["tickers"][0]["current_capture_artifact"].endswith("etn-q1-2026.json")


def test_guard_treats_clean_q2_as_current() -> None:
    registry = {
        "latest_by_ticker": {
            "ETN": {
                "period_end": "2026-06-30",
                "period_slug": "q2-2026",
                "validation_clean": True,
                "capture_script": "etn_vrt_official_ir_capture.py",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000027/etn06302026exhibit99.htm",
            }
        }
    }

    def discoverer(**_kwargs: object) -> dict:
        return {"status": "current", "latest_detected_period_end": "2026-06-30"}

    result = build_guard(tracked={"ETN": {"earnings_policy": "timing_sensitive"}}, registry=registry, discoverer=discoverer)
    assert result["status"] == "ok"
    assert result["summary"]["current_count"] == 1


def test_guard_treats_source_verified_capture_as_reconciliation_debt_not_outage() -> None:
    registry = {
        "latest_by_ticker": {
            "AMD": {
                "period_end": "2026-03-28",
                "period_slug": "q1-2026",
                "validation_clean": True,
                "capture_script": "batch2_official_ir_capture.py",
                "source_url": "https://www.sec.gov/Archives/edgar/data/2488/000000248826000072/q12026991.htm",
            }
        }
    }

    def discoverer(**_kwargs: object) -> dict:
        return {
            "status": "new_period_source_manual_required",
            "ticker": "AMD",
            "latest_detected_period_end": "2026-06-27",
            "period_slug": "q2-2026",
            "source_url": "https://www.sec.gov/Archives/edgar/data/2488/000000248826000123/amd-20260627.htm",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/2488/000000248826000123/0000002488-26-000123-index.htm",
            "accession_number": "0000002488-26-000123",
            "source_title": "AMD Q2 2026 SEC filing",
            "source_type": "sec_10q_official_report",
        }

    def capturer(discovered: dict, **_kwargs: object) -> dict:
        assert discovered["ticker"] == "AMD"
        return {"status": "source_verified_manual_reconciliation_pending", "ticker": "AMD"}

    result = build_guard(
        tracked={"AMD": {"earnings_policy": "timing_sensitive"}},
        registry=registry,
        discoverer=discoverer,
        auto_capture=True,
        auto_capturer=capturer,
    )
    assert result["status"] == "ok"
    assert result["tickers"][0]["status"] == "updated_source_verified_pending_reconciliation"
    assert result["summary"]["source_verified_pending_reconciliation_count"] == 1
    assert result["summary"]["unresolved_count"] == 0


def test_etn_matching_period_10q_bridge_requires_current_and_prior_contexts() -> None:
    raw = """
    <xbrli:context id="c-14"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id="c-15"><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2025-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <ix:nonFraction contextRef="c-14" name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" scale="6">8,531</ix:nonFraction>
    <ix:nonFraction contextRef="c-15" name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" scale="6">7,028</ix:nonFraction>
    <ix:nonFraction contextRef="c-14" name="us-gaap:NetIncomeLoss" scale="6">821</ix:nonFraction>
    <ix:nonFraction contextRef="c-15" name="us-gaap:NetIncomeLoss" scale="6">982</ix:nonFraction>
    <ix:nonFraction contextRef="c-14" name="us-gaap:EarningsPerShareDiluted" scale="0">2.11</ix:nonFraction>
    <ix:nonFraction contextRef="c-15" name="us-gaap:EarningsPerShareDiluted" scale="0">2.51</ix:nonFraction>
    <ix:nonFraction contextRef="c-14" name="us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding" scale="6">389.5</ix:nonFraction>
    <ix:nonFraction contextRef="c-15" name="us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding" scale="6">391.4</ix:nonFraction>
    """
    bridge = _etn_matching_period_10q_bridge(raw, "2026-06-30", "https://example.invalid/etn-10q")
    assert bridge is not None
    assert bridge["official_period_bridge_verified"] is True
    assert bridge["revenue"] == 8_531_000_000.0
    assert bridge["revenue_prior"] == 7_028_000_000.0
    assert bridge["diluted_eps"] == 2.11
    assert bridge["comparison_period_end"] == "2025-06-30"


def test_chain_inserts_guard_before_official_capture() -> None:
    for window in ("morning", "post-close", "post-earnings", "sunday"):
        steps = chain_manifest.manifest_steps(window)
        guard_index = next(index for index, step in enumerate(steps) if step["script"] == "earnings_rollforward_guard.py")
        capture_index = next(index for index, step in enumerate(steps) if step["script"] == "etn_vrt_official_ir_capture.py")
        assert guard_index < capture_index
        assert "earnings_rollforward_guard.py" in steps[capture_index]["depends_on"]


if __name__ == "__main__":
    test_sec_discovery_resolves_new_period_and_exhibit()
    test_sec_discovery_ranks_ex99_variants_and_rejects_irrelevant_exhibits()
    test_generic_capture_is_evidence_bearing_and_never_guesses_values()
    test_guard_emits_one_idempotent_catchup_row_without_editing_q1()
    test_guard_treats_clean_q2_as_current()
    test_guard_treats_source_verified_capture_as_reconciliation_debt_not_outage()
    test_etn_matching_period_10q_bridge_requires_current_and_prior_contexts()
    test_chain_inserts_guard_before_official_capture()
    print("earnings rollforward guard tests passed")
