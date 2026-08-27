from datetime import datetime, timezone
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_freshness_opportunity_cron_runner as runner
from market_data_utils import atomic_write_json


def test_changed_only_skip_requires_matching_digest_and_fresh_review(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "TMP", tmp_path / "tmp")
    runner.TMP.mkdir()

    review = runner.TMP / "research-freshness-opportunity-review.json"
    atomic_write_json(review, {
        "generated_at_utc": runner.utc_now(),
        "status": "ok",
        "authority": {
            "capital_action_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    })
    cache = runner.TMP / "research-freshness-opportunity-cron-cache.json"
    atomic_write_json(cache, {
        "schema": runner.CACHE_SCHEMA,
        "last_completed_run": {
            "status": "ok",
            "source_digest": "abc",
        },
    })

    can_skip, reason = runner.can_skip_changed_only(cache, "abc", 20.0)

    assert can_skip is True
    assert reason == "source_digest_unchanged_and_previous_review_fresh"


def test_changed_only_skip_rejects_digest_change(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "TMP", tmp_path / "tmp")
    runner.TMP.mkdir()
    cache = runner.TMP / "research-freshness-opportunity-cron-cache.json"
    atomic_write_json(cache, {
        "schema": runner.CACHE_SCHEMA,
        "last_completed_run": {
            "status": "ok",
            "source_digest": "old",
        },
    })

    can_skip, reason = runner.can_skip_changed_only(cache, "new", 20.0)

    assert can_skip is False
    assert reason == "source_digest_changed"


def test_validation_blocks_authority_widening(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "TMP", tmp_path / "tmp")
    runner.TMP.mkdir()
    atomic_write_json(runner.TMP / "research-freshness-opportunity-review.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "authority": {
            "capital_action_allowed": True,
            "portfolio_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    })
    atomic_write_json(runner.TMP / "small-mid-cap-regime-feed.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "authority": {
            "capital_action_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    })

    payload = runner.build_payload(
        steps=[],
        mode="classified_only",
        current_digest={"digest": "abc", "entries": []},
        skip_reason=None,
        window="post-close",
        changed_only=True,
    )

    assert payload["status"] == "blocked"
    assert "research_review_authority_widened:capital_action_allowed" in payload["validation"]["errors"]
