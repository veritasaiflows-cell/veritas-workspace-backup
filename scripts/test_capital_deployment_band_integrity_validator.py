#!/usr/bin/env python3
"""Regression tests for capital deployment band integrity validator."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import capital_deployment_band_integrity_validator as validator


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def with_temp_sources(fn):
    originals = {
        "WF78_CAPITAL_QUEUE": validator.WF78_CAPITAL_QUEUE,
        "FINANCE_DECISION_FACTORY": validator.FINANCE_DECISION_FACTORY,
        "CAPITAL_RECOMMENDATIONS": validator.CAPITAL_RECOMMENDATIONS,
        "OWNER_CARD_DIR": validator.OWNER_CARD_DIR,
        "WF67_REQUEST_DIR": validator.WF67_REQUEST_DIR,
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        validator.WF78_CAPITAL_QUEUE = root / "wf78.json"
        validator.FINANCE_DECISION_FACTORY = root / "factory.json"
        validator.CAPITAL_RECOMMENDATIONS = root / "recommendations.json"
        validator.OWNER_CARD_DIR = root / "cards"
        validator.WF67_REQUEST_DIR = root / "requests"
        try:
            return fn(root)
        finally:
            for name, value in originals.items():
                setattr(validator, name, value)


def seed_sources(root: Path, *, request_low: float, gate_low: float) -> None:
    write_json(
        root / "wf78.json",
        {
            "generated_at_utc": "2026-06-15T00:00:00Z",
            "rows": [{"ticker": "ABC", "written_band": {"entry_band_low": 10, "entry_band_high": 20, "stop_or_invalidation": 8}}],
        },
    )
    write_json(
        root / "factory.json",
        {"generated_at_utc": "2026-06-15T00:00:00Z", "decision_ledger": [{"ticker": "ABC", "entry_band_low": 10, "entry_band_high": 20, "stop": 8}]},
    )
    write_json(root / "recommendations.json", {"generated_at_utc": "2026-06-15T00:00:00Z", "proposals": []})
    write_json(
        root / "cards" / "ABC.owner-card.json",
        {"generated_at_utc": "2026-06-15T00:00:00Z", "order": {"symbol": "ABC"}, "risk_check": {"entry_band_low": 10, "entry_band_high": 20, "stop": 8}},
    )
    write_json(
        root / "requests" / "paper-trade-request.wf78-owner-card-prep-abc.json",
        {
            "created_at_utc": "2026-06-15T00:00:00Z",
            "order": {"symbol": "ABC"},
            "risk_check": {"entry_band_low": request_low, "entry_band_high": 20, "stop": 8},
            "source": {
                "chief_intelligence_promotion_gate": {
                    "ticker": "ABC",
                    "gate_generated_at_utc": "2026-06-15T00:00:00Z",
                    "entry_band": {"low": gate_low, "high": 20, "stop": 8},
                }
            },
        },
    )


def test_request_risk_check_mismatch_blocks_and_fails_validation() -> None:
    def run(root: Path) -> None:
        seed_sources(root, request_low=11, gate_low=10)
        report = validator.build_report()
        assert report["status"] == "blocked"
        assert report["validation"]["status"] == "error"
        assert "core_entry_band_mismatch" in report["validation"]["errors"]

    with_temp_sources(run)


def test_embedded_promotion_gate_drift_is_warning_only_when_core_agrees() -> None:
    def run(root: Path) -> None:
        seed_sources(root, request_low=10, gate_low=12)
        report = validator.build_report()
        assert report["status"] == "warning"
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["warning_tickers"] == ["ABC"]
        assert report["findings"][0]["code"] == "review_context_entry_band_drift"

    with_temp_sources(run)


def main() -> int:
    test_request_risk_check_mismatch_blocks_and_fails_validation()
    test_embedded_promotion_gate_drift_is_warning_only_when_core_agrees()
    print("capital_deployment_band_integrity_validator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
