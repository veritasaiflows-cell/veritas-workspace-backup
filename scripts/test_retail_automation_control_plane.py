from datetime import datetime, timedelta, timezone

from retail_automation_control_plane import readiness_pilot_state, source_state, staleness_queue


def test_source_state_enforces_artifact_age(tmp_path) -> None:
    now = datetime(2026, 8, 11, 4, 0, tzinfo=timezone.utc)
    path = tmp_path / "proof.json"
    path.write_text("{}", encoding="utf-8")
    fresh_payload = {"status": "ok", "generated_at_utc": now.isoformat().replace("+00:00", "Z")}
    stale_payload = {
        "status": "ok",
        "generated_at_utc": (now - timedelta(days=8)).isoformat().replace("+00:00", "Z"),
    }
    fresh = source_state(path, fresh_payload, now)
    stale = source_state(path, stale_payload, now)
    assert fresh["fresh"] is True
    assert stale["fresh"] is False
    assert stale["freshness"]["status"] == "expired"


def test_staleness_queue_names_exact_expired_dependency(tmp_path) -> None:
    now = datetime(2026, 8, 11, 4, 0, tzinfo=timezone.utc)
    path = tmp_path / "old-proof.json"
    path.write_text("{}", encoding="utf-8")
    state = source_state(
        path,
        {"status": "ok", "generated_at_utc": "2000-01-01T00:00:00Z"},
        now,
    )
    prompts = staleness_queue(
        {"source_artifacts": [], "finance_sql_canon": {"status": "ok"}},
        {"status": "ok"},
        {"status": "ok"},
        [state],
    )
    assert len(prompts) == 1
    assert prompts[0]["route"] == "artifact_ttl"
    assert prompts[0]["freshness_status"] == "expired"
    assert prompts[0]["source"].endswith("old-proof.json")


def test_pilot_tickers_require_fresh_valid_review_only_source() -> None:
    readiness = {
        "validation": {"status": "ok"},
        "summary": {
            "total_tickers": 300,
            "production_answer_path_count": 0,
            "review_monitor_count": 300,
            "recommended_pilot_tickers": ["AAPL", "AVGO"],
            "answer_consumer_cutover_allowed": False,
        },
        "authority": {
            "report_only": True,
            "read_existing_artifacts_only": True,
            "import_or_apply_allowed": False,
            "promotion_allowed": False,
            "production_answer_path_change_allowed": False,
            "sql_canon_expansion_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    current = readiness_pilot_state(readiness, {"fresh": True})
    stale = readiness_pilot_state(readiness, {"fresh": False})
    incomplete_authority = dict(readiness)
    incomplete_authority["authority"] = {"owner_approval_inferred": False}
    incomplete = readiness_pilot_state(incomplete_authority, {"fresh": True})
    missing = readiness_pilot_state({}, {"fresh": False})

    assert current["status"] == "review_only_current"
    assert current["candidate_tickers"] == ["AAPL", "AVGO"]
    assert current["total_tickers"] == 300
    assert current["production_answer_path_count"] == 0
    assert current["review_monitor_count"] == 300
    assert stale["candidate_tickers"] == []
    assert stale["total_tickers"] is None
    assert stale["production_answer_path_count"] is None
    assert stale["review_monitor_count"] is None
    assert incomplete["candidate_tickers"] == []
    assert missing["candidate_tickers"] == []
