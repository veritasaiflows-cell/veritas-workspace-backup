#!/usr/bin/env python3
"""Acceptance tests for wf78_source_open_patch_orchestrator.py."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf78_source_open_patch_orchestrator.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf78_source_open_patch_orchestrator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sample_card() -> dict:
    return {
        "ticker": "AAA",
        "missing_or_stale_evidence": [
            {
                "family": "price_band_stop_position_sizing",
                "severity": "blocking",
                "detail": "missing band",
            },
            {
                "family": "fundamentals",
                "severity": "review_required",
                "detail": "old fundamentals",
            },
        ],
        "recommendation_support": {
            "posture": "blocked",
            "blockers_or_gates": ["price_band_stop_position_sizing"],
        },
        "analyst_consensus_ratings_targets": {"status": "present"},
    }


def test_card_patch_is_review_only(errors: list[str]) -> None:
    module = load_module()
    with TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        card_path = tmp / "AAA.current.json"
        card_path.write_text(json.dumps(sample_card()), encoding="utf-8")
        module.BACKUP_DIR = tmp / "backups"

        def fake_technical_fetch(ticker: str) -> dict:
            return {
                "ticker": ticker,
                "status": "ok",
                "latest_close": 100.0,
                "data_date": "2026-06-29",
                "ma20": 98.0,
                "ma50": 95.0,
                "ma200": 85.0,
                "above_ma20": True,
                "above_ma50": True,
                "above_ma200": True,
                "source": "test",
                "source_url": "https://example.com/AAA",
                "review_monitor_band_proposal": {
                    "status": "available_review_only",
                    "latest_known_price": 100.0,
                    "data_date": "2026-06-29",
                    "proposed_band_low": 95.0,
                    "proposed_band_high": 105.0,
                    "proposed_stop": 90.0,
                    "authority_boundary": module.PROPOSAL_AUTHORITY,
                },
            }

        module.technical_fetch = fake_technical_fetch
        result = module.patch_card(
            "AAA",
            card_path,
            {"AAA": {"official_earnings_source_url": "https://ir.example.com/aaa", "source_label": "AAA IR"}},
            write=True,
            run_id="TEST-RUN",
        )
        patched = json.loads(card_path.read_text(encoding="utf-8"))
        patch = patched["review_monitor_source_open_patch"]
        expect(result["status"] == "ok", f"patch result not ok: {result}", errors)
        expect(result["blocking_rows_downgraded"] == 1, "blocking band row should be downgraded", errors)
        expect(patch["authority_boundary"]["review_only_source_open_patch_allowed"] is True, "review-only flag missing", errors)
        for key in (
            "canonical_note_mutation_allowed",
            "portfolio_mutation_allowed",
            "production_answer_path_expansion_allowed",
            "owner_approval_inferred",
            "paper_or_live_execution_allowed",
            "trade_or_account_action_allowed",
        ):
            expect(patch["authority_boundary"][key] is False, f"authority flag must stay false: {key}", errors)
        expect(
            patched["missing_or_stale_evidence"][0]["severity"] == "review_required",
            "patched band blocker should become review_required",
            errors,
        )
        expect(
            patched["recommendation_support"]["actionability"] == "review_only_owner_gated",
            "recommendation support should stay owner gated",
            errors,
        )
        expect((module.BACKUP_DIR / "TEST-RUN" / "AAA.current.json").exists(), "card backup should be written", errors)


def test_validate_report_rejects_widened_authority(errors: list[str]) -> None:
    module = load_module()
    report = {
        "ticker_count": 1,
        "status": "ok",
        "authority_boundary": {**module.AUTHORITY_BOUNDARY, "portfolio_mutation_allowed": True},
        "summary": {"technical_sourced": 1, "official_source_registered": 1},
    }
    failed = [row for row in module.validate_report(report) if not row["ok"]]
    expect(
        any(row["name"] == "authority_boundary_no_forbidden_true_flags" for row in failed),
        "validation must reject forbidden true authority flags",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    for test in (
        test_card_patch_is_review_only,
        test_validate_report_rejects_widened_authority,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok wf78 source-open patch orchestrator acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
