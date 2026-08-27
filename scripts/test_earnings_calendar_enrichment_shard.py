import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import earnings_calendar_enrichment as enrichment


def fake_record(display_ticker: str, provider_ticker: str) -> dict[str, object]:
    return {
        "ticker": display_ticker,
        "next_earnings_date": "2099-01-15",
        "source": "fake:" + provider_ticker,
        "date_source_class": "provider_estimate",
        "primary_confirmed": False,
        "fetched_at_utc": "2026-08-07T00:00:00+00:00",
        "error": None,
    }


def test_ticker_shard_merges_existing_and_never_applies_config(monkeypatch, tmp_path):
    output_path = tmp_path / "earnings-calendar.json"
    config_path = tmp_path / "portfolio-config.json"
    output_path.write_text(
        json.dumps(
            {
                "records": [
                    {"ticker": "KEEP", "next_earnings_date": "2099-02-01", "error": None},
                    {"ticker": "AJG", "next_earnings_date": "2000-01-01", "error": None},
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(json.dumps({"sentinel": "unchanged"}), encoding="utf-8")

    fetched: list[tuple[str, str]] = []

    def fetch(display_ticker: str, provider_ticker: str) -> dict[str, object]:
        fetched.append((display_ticker, provider_ticker))
        return fake_record(display_ticker, provider_ticker)

    monkeypatch.setattr(enrichment, "OUT_PATH", output_path)
    monkeypatch.setattr(enrichment, "CONFIG_PATH", config_path)
    monkeypatch.setattr(enrichment, "WORKSPACE", tmp_path)
    monkeypatch.setattr(enrichment, "fetch_earnings_date", fetch)
    monkeypatch.setattr(
        enrichment,
        "apply_watchlist_lifecycle_closeouts",
        lambda *_args, **_kwargs: pytest.fail("shard mode must not apply portfolio config"),
    )

    enrichment.main(["--tickers", "ajg", "AXON", "AJG", "--merge-existing"])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    records = {record["ticker"]: record for record in payload["records"]}
    assert fetched == [("AJG", "AJG"), ("AXON", "AXON")]
    assert records["KEEP"]["next_earnings_date"] == "2099-02-01"
    assert records["AJG"]["next_earnings_date"] == "2099-01-15"
    assert records["AXON"]["source"] == "fake:AXON"
    assert payload["refresh_scope"] == {
        "mode": "ticker_shard",
        "tickers": ["AJG", "AXON"],
        "merge_existing": True,
        "review_only": True,
        "portfolio_config_mutation_allowed": False,
    }
    assert payload["earnings_lifecycle"]["config_apply"]["reason"] == "disabled_in_ticker_shard_mode"
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"sentinel": "unchanged"}


def test_no_arg_mode_keeps_full_coverage_and_lifecycle_apply(monkeypatch, tmp_path):
    output_path = tmp_path / "earnings-calendar.json"
    config_path = tmp_path / "portfolio-config.json"
    config_path.write_text("{}", encoding="utf-8")
    applied: list[list[dict[str, object]]] = []

    monkeypatch.setattr(enrichment, "OUT_PATH", output_path)
    monkeypatch.setattr(enrichment, "CONFIG_PATH", config_path)
    monkeypatch.setattr(enrichment, "WORKSPACE", tmp_path)
    monkeypatch.setattr(enrichment, "COVERAGE", {"KNOWN": "KNOWN-YF"})
    monkeypatch.setattr(enrichment, "fetch_earnings_date", fake_record)
    monkeypatch.setattr(enrichment, "build_watchlist_lifecycle_closeouts", lambda **_kwargs: [])
    monkeypatch.setattr(enrichment, "build_existing_watchlist_lifecycle_holds", lambda **_kwargs: [])

    def apply(_config, closeouts):
        applied.append(closeouts)
        return {"applied": False, "count": 0, "tickers": []}

    monkeypatch.setattr(enrichment, "apply_watchlist_lifecycle_closeouts", apply)

    enrichment.main([])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["records"][0]["source"] == "fake:KNOWN-YF"
    assert "refresh_scope" not in payload
    assert applied == [[]]


def test_merge_existing_requires_explicit_tickers():
    with pytest.raises(SystemExit):
        enrichment.parse_args(["--merge-existing"])
