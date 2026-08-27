from __future__ import annotations

import sys
from pathlib import Path

import finance_ticker_card_refresh_gate as gate


def main() -> int:
    tickers = ["AJG", "AXON"]
    provider = gate.provider_refresh_commands(tickers)
    assert provider[0] == [
        sys.executable,
        "scripts\\earnings_calendar_enrichment.py",
        "--tickers",
        "AJG",
        "AXON",
        "--merge-existing",
    ]
    assert not any(any("technical_refresh.py" in part for part in command) for command in provider)
    assert provider[2][1:4] == ["scripts\\fundamental_metrics_refresh.py", "--tickers", "AJG"]
    assert provider[3][1:4] == ["scripts\\analyst_consensus_refresh.py", "--tickers", "AJG"]

    cards = gate.card_refresh_commands(Path("tmp/test-card-summary.json"), tickers)
    assert cards[1][1:6] == [
        "scripts\\ticker_intelligence_card.py",
        "--ticker",
        "AJG",
        "--ticker",
        "AXON",
    ]
    full = gate.build_commands(False, Path("tmp/test-card-summary.json"), "never", tickers)
    assert full[0] == [
        sys.executable,
        "scripts\\earnings_rollforward_guard.py",
        "--auto-capture",
        "--write",
        "--validate",
        "--ticker",
        "AJG",
        "--ticker",
        "AXON",
    ]
    assert any(any("earnings_calendar_enrichment.py" in part for part in command) for command in full)
    assert not any("--all-from-coverage" in command for command in full)
    assert not any(any("refresh-100" in part for part in command) for command in full)
    assert gate.guard_requires_reconciliation({"summary": {"updated_review_only_count": 1}}) is True
    assert gate.guard_requires_reconciliation({"summary": {"source_verified_pending_reconciliation_count": 1}}) is True
    assert gate.guard_requires_reconciliation({"summary": {"unresolved_count": 1}}) is False
    reconciliation = gate.post_earnings_reconciliation_commands()
    assert reconciliation[0][1:] == ["scripts\\official_capture_period_registry.py", "--write"]
    assert reconciliation[-1][1:] == ["scripts\\validate_official_earnings_bridge.py", "--write"]

    legacy = gate.build_commands(False, Path("tmp/test-card-summary.json"), "never")
    assert legacy[0] == [
        sys.executable,
        "scripts\\earnings_rollforward_guard.py",
        "--auto-capture",
        "--write",
        "--validate",
        "--priority-only",
    ]
    assert legacy[1] == [sys.executable, "scripts\\technical_refresh.py"]
    assert any("--all-from-coverage" in command for command in legacy)
    assert any(any("refresh-100" in part for part in command) for command in legacy)

    provider_skipped = gate.build_commands(True, Path("tmp/test-card-summary.json"), "never")
    assert not any(any("refresh-100" in part for part in command) for command in provider_skipped)

    args = gate.parse_args(["--tickers", "ajg", "AXON", "--skip-provider-refresh"])
    assert args.tickers == ["ajg", "AXON"]
    print("finance_ticker_card_refresh_gate tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
