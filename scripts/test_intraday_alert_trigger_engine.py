#!/usr/bin/env python3
"""Targeted WF68 Phase 2 trigger engine behavior checks."""
from __future__ import annotations

import copy
import json
import tempfile
from argparse import Namespace
from pathlib import Path

from intraday_alert_trigger_engine import ROOT, run_engine

BASE_QUOTES = ROOT / "tmp" / "intraday-alerts" / "quote-snapshot-proof.json"
BASE_CONFIG = ROOT / "tmp" / "portfolio-config.json"
BASE_PAPER = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-execution-result.etn-2026-05-19-market.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def set_quote(quotes: dict, symbol: str, price: float, freshness: str = "fresh") -> None:
    for quote in quotes["snapshots"]:
        if quote["symbol"] == symbol:
            quote.update(
                {
                    "price": price,
                    "bid": price - 0.05,
                    "ask": price + 0.05,
                    "freshness_status": freshness,
                    "age_seconds": 30,
                    "source_timestamp_utc": "2026-05-19T18:30:00Z",
                    "received_at_utc": "2026-05-19T18:30:30Z",
                }
            )
            return
    quotes.setdefault("snapshots", []).append(
        {
            "symbol": symbol,
            "price": price,
            "bid": price - 0.05,
            "ask": price + 0.05,
            "freshness_status": freshness,
            "age_seconds": 30,
            "source_timestamp_utc": "2026-05-19T18:30:00Z",
            "received_at_utc": "2026-05-19T18:30:30Z",
        }
    )


def run_case(td: Path, quotes: dict, config: dict, paper: dict | None = None, use_dedupe_state: bool = False):
    quotes_path = td / "quotes.json"
    config_path = td / "portfolio-config.json"
    paper_path = td / "paper.json"
    write(quotes_path, quotes)
    write(config_path, config)
    if paper is not None:
        write(paper_path, paper)
    args = Namespace(
        quotes=quotes_path,
        portfolio_config=config_path,
        paper_result=paper_path if paper is not None else None,
        output_json=td / "current-alerts.json",
        output_md=td / "current-alerts.md",
        validation_output=td / "trigger-engine-validation.json",
        dedupe_state=td / "dedupe.json",
        use_dedupe_state=use_dedupe_state,
    )
    return run_engine(args)["alerts"]


def main() -> int:
    base_quotes = load(BASE_QUOTES)
    base_config = load(BASE_CONFIG)
    base_paper = load(BASE_PAPER)

    with tempfile.TemporaryDirectory() as raw_td:
        td = Path(raw_td)

        # In-band entry alert: ETN inside written band emits HIGH owner-decision packet.
        quotes = copy.deepcopy(base_quotes)
        config = copy.deepcopy(base_config)
        set_quote(quotes, "ETN", config["entry_bands"]["ETN"]["low"] + 1, "fresh")
        doc = run_case(td / "in_band", quotes, config)
        etn = [p for p in doc["alerts"] if p["event"]["ticker"] == "ETN"]
        assert etn and etn[0]["event"]["event_type"] == "price_enters_band", doc
        assert etn[0]["taxonomy"]["severity"] == "HIGH", etn[0]

        # Below-stop alert emits CRITICAL invalidation review packet.
        quotes = copy.deepcopy(base_quotes)
        config = copy.deepcopy(base_config)
        set_quote(quotes, "ETN", config["entry_bands"]["ETN"]["stop"] - 1, "fresh")
        doc = run_case(td / "below_stop", quotes, config)
        etn = [p for p in doc["alerts"] if p["event"]["ticker"] == "ETN"]
        assert etn and etn[0]["event"]["event_type"] == "price_breaches_stop", doc
        assert etn[0]["taxonomy"]["severity"] == "CRITICAL", etn[0]

        # Above no-chase band emits MONITOR review packet, not HIGH/CRITICAL actionability.
        quotes = copy.deepcopy(base_quotes)
        config = copy.deepcopy(base_config)
        set_quote(quotes, "ETN", config["entry_bands"]["ETN"]["high"] + 5, "fresh")
        doc = run_case(td / "above_no_chase", quotes, config)
        etn = [p for p in doc["alerts"] if p["event"]["ticker"] == "ETN"]
        assert etn and etn[0]["event"]["event_type"] == "no_chase_upper_band_breach", doc
        assert etn[0]["taxonomy"]["severity"] == "MONITOR", etn[0]

        # Stale/non-intraday-fresh quote does not emit an actionable packet.
        quotes = copy.deepcopy(base_quotes)
        config = copy.deepcopy(base_config)
        set_quote(quotes, "ETN", config["entry_bands"]["ETN"]["low"] + 1, "current_but_not_intraday_fresh")
        doc = run_case(td / "stale_no_fire", quotes, config)
        assert not [p for p in doc["alerts"] if p["event"]["ticker"] == "ETN"], doc
        assert any(r["ticker"] == "ETN" and r["reason"] == "freshness_policy_no_fire" for r in doc["no_fire_or_monitor_only"]), doc

        # Duplicate suppression: persisted dedupe state suppresses a repeated same-severity key.
        quotes = copy.deepcopy(base_quotes)
        config = copy.deepcopy(base_config)
        set_quote(quotes, "ETN", config["entry_bands"]["ETN"]["low"] + 1, "fresh")
        dup_dir = td / "duplicate"
        first = run_case(dup_dir, quotes, config, use_dedupe_state=True)
        second = run_case(dup_dir, quotes, config, use_dedupe_state=True)
        assert [p for p in first["alerts"] if p["event"]["ticker"] == "ETN"], first
        assert not [p for p in second["alerts"] if p["event"]["ticker"] == "ETN"], second
        assert any(r["ticker"] == "ETN" and r["reason"] == "duplicate_same_or_lower_severity" for r in second["duplicate_suppressed"]), second

        # Paper-fill/order state is captured as placeholder and does not create paper/action authority.
        quotes = copy.deepcopy(base_quotes)
        config = copy.deepcopy(base_config)
        set_quote(quotes, "ETN", config["entry_bands"]["ETN"]["high"] + 5, "current_but_not_intraday_fresh")
        paper = copy.deepcopy(base_paper)
        paper["broker_redacted_result"]["paper_order_status"] = "filled"
        doc = run_case(td / "paper_placeholder", quotes, config, paper)
        assert doc["paper_state_placeholders"], doc
        assert doc["authority"]["paper_trade_allowed"] is False, doc

    print("intraday_alert_trigger_engine targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
