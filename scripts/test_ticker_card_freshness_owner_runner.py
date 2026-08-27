#!/usr/bin/env python3
"""Focused tests for ticker-card freshness runner review-only blockers."""
from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import ticker_card_freshness_owner_runner as runner


def test_position_sizing_capital_validator_blocker_is_review_only() -> None:
    readiness = {
        "status": "critical",
        "critical_findings": ["capital deployment validator is not ok"],
        "authority": {
            "live_trade_allowed": False,
            "paper_order_execution_allowed": False,
            "owner_approval_inferred": False,
            "sizing_recommendation_review_allowed": True,
            "paper_request_preparation_allowed_after_exact_owner_terms": True,
        },
    }

    assert runner.position_sizing_review_blockers(readiness) == ["capital deployment validator is not ok"]


def test_tuesday_readiness_command_failure_is_not_production_blocker_when_review_only() -> None:
    commands = [
        {
            "command": "python scripts\\tuesday_position_sizing_readiness.py --write --write-legacy",
            "returncode": 1,
        }
    ]
    readiness = {
        "status": "critical",
        "critical_findings": ["capital deployment validator is not ok"],
        "authority": {
            "live_trade_allowed": False,
            "paper_order_execution_allowed": False,
            "owner_approval_inferred": False,
            "sizing_recommendation_review_allowed": True,
            "paper_request_preparation_allowed_after_exact_owner_terms": True,
        },
    }

    assert runner.true_blockers(commands, {"validation": {"status": "ok"}, "authority": {}}, readiness) == []


def test_unexpected_position_sizing_failure_still_blocks() -> None:
    commands = [
        {
            "command": "python scripts\\tuesday_position_sizing_readiness.py --write --write-legacy",
            "returncode": 1,
        }
    ]
    readiness = {
        "status": "critical",
        "critical_findings": ["unexpected"],
        "authority": {"owner_approval_inferred": False},
    }

    blockers = runner.true_blockers(commands, {"validation": {"status": "ok"}, "authority": {}}, readiness)

    assert "position_sizing_readiness_status:critical" in blockers
    assert any(item.startswith("command_failed:") for item in blockers)


def seed_prefilter_workspace(root: Path, generated_at_utc: str) -> tuple[Path, Path, Namespace]:
    output = root / "ticker-card-freshness-owner-runner.json"
    prefilter = root / "ticker-card-freshness-owner-runner-prefilter.json"
    (root / "scripts").mkdir()
    (root / "scripts" / "ticker_card_freshness_owner_runner.py").write_text("runner", encoding="utf-8")
    (root / "scripts" / "finance_ticker_card_refresh_gate.py").write_text("gate", encoding="utf-8")
    (root / "scripts" / "tuesday_position_sizing_readiness.py").write_text("sizing", encoding="utf-8")
    (root / "state" / "finance").mkdir(parents=True)
    (root / "state" / "finance" / "finance-canon.sqlite").write_text("canon", encoding="utf-8")
    output.write_text(
        json.dumps(
            {
                "generated_at_utc": generated_at_utc,
                "status": "ok",
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }
        ),
        encoding="utf-8",
    )
    return output, prefilter, Namespace(
        output=output,
        prefilter_output=prefilter,
        full_answer_mode="changed",
        skip_provider_refresh=False,
    )


def test_prefilter_skips_same_day_successful_output() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _output, _prefilter, args = seed_prefilter_workspace(root, "2026-07-06T22:31:36Z")
        with (
            patch.object(runner, "ROOT", root),
            patch.object(runner, "phoenix_date", lambda value=None: "2026-07-06"),
        ):
            proof = runner.build_prefilter_report(args)

    assert proof["status"] == "skipped_unchanged"
    assert proof["action"] == "skip_worker"
    assert proof["would_run_existing_worker"] is False
    assert proof["would_spawn_model_or_agent_turn"] is False
    assert proof["validation"]["status"] == "ok"
    assert proof["worker_prefilter"]["reason"] == "source_unchanged_and_same_day_successful_output_present"


def test_prefilter_requires_run_for_prior_day_output() -> None:
    def fake_phoenix_date(value=None):
        if isinstance(value, datetime):
            return "2026-07-05"
        return "2026-07-06"

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _output, _prefilter, args = seed_prefilter_workspace(root, "2026-07-05T22:31:36Z")
        with (
            patch.object(runner, "ROOT", root),
            patch.object(runner, "phoenix_date", fake_phoenix_date),
        ):
            proof = runner.build_prefilter_report(args)

    assert proof["status"] == "run_required"
    assert proof["action"] == "run_worker_when_promoted"
    assert proof["would_run_existing_worker"] is True
    assert proof["worker_prefilter"]["reason"] == "previous_output_not_same_market_date"


def test_owner_runner_keeps_rollforward_single_owned_by_card_gate() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    build_body = source[source.index("def build("):source.index("def parse_args(")]
    assert '"scripts\\\\earnings_rollforward_guard.py"' not in build_body
    assert '"scripts\\\\finance_ticker_card_refresh_gate.py"' in build_body
    assert '"scripts\\\\finance_source_freshness_maturity.py"' in build_body


if __name__ == "__main__":
    test_position_sizing_capital_validator_blocker_is_review_only()
    test_tuesday_readiness_command_failure_is_not_production_blocker_when_review_only()
    test_unexpected_position_sizing_failure_still_blocks()
    test_prefilter_skips_same_day_successful_output()
    test_prefilter_requires_run_for_prior_day_output()
    test_owner_runner_keeps_rollforward_single_owned_by_card_gate()
    print("ticker_card_freshness_owner_runner targeted tests passed")
