from datetime import datetime, timedelta, timezone

from retail_truth_safety import (
    INTERNAL_AUDIENCE,
    claim_freshness,
    export_guard,
    freshness_record,
    parse_utc,
    render_internal_route,
)


NOW = datetime(2026, 8, 11, 4, 0, tzinfo=timezone.utc)


def _claim(**overrides):
    claim = {
        "claim_type": "routing_state",
        "text": "Issuer source endpoint is queued for source-open review.",
        "source_label": "issuer_ir_endpoint_fixture_unfetched",
        "source_url": "https://investors.example.com/",
        "as_of_utc": NOW.isoformat().replace("+00:00", "Z"),
    }
    claim.update(overrides)
    return claim


def _route(final_answer_allowed=False):
    return {
        "question_class": "ticker_intelligence",
        "answer_contract_v2": {
            "freshness_and_conflict_checks": {"final_answer_allowed": final_answer_allowed}
        },
    }


def test_timestamps_and_ttl_fail_closed() -> None:
    assert parse_utc("2026-08-11T04:00:00") is None
    assert freshness_record("2026-08-11T03:00:00Z", 24, NOW)["fresh"] is True
    assert freshness_record("2026-08-09T03:00:00Z", 24, NOW)["fresh"] is False
    assert freshness_record("2026-08-11T04:00:01Z", 24, NOW)["status"] == "future_timestamp"
    assert freshness_record("2026-08-11T04:05:00Z", 24, NOW)["fresh"] is False
    assert freshness_record("2026-08-12T03:00:00Z", 24, NOW)["status"] == "future_timestamp"


def test_claim_requires_source_label_url_and_current_ttl() -> None:
    assert claim_freshness(_claim(), NOW)["fresh"] is True
    expired = _claim(as_of_utc=(NOW - timedelta(hours=25)).isoformat().replace("+00:00", "Z"))
    assert claim_freshness(expired, NOW)["fresh"] is False
    assert claim_freshness(_claim(source_url="tmp/private.json"), NOW)["fresh"] is False
    assert claim_freshness(_claim(claim_type="market_price"), NOW)["fresh"] is False


def test_internal_render_allows_only_internal_export() -> None:
    rendered = render_internal_route(ticker="DASH", route=_route(), claims=[_claim()], now=NOW)
    assert rendered["audience"] == INTERNAL_AUDIENCE
    assert rendered["render_safe"] is True
    assert rendered["recommendation_allowed"] is False
    internal = export_guard(rendered, "internal_state")
    assert internal["allowed"] is True and internal["serialized"] is True
    external = export_guard(rendered, "customer")
    assert external["allowed"] is False and external["serialized"] is False
    assert external["payload"] is None
    assert "BLOCKED_EXTERNAL_DELIVERY" in external["reasons"]


def test_path_leak_and_expired_claim_block_before_serialization() -> None:
    leaked = render_internal_route(
        ticker="TSM",
        route=_route(),
        claims=[_claim(text=r"Read C:\Users\Veritas\.openclaw\workspace\tmp\proof.json")],
        now=NOW,
    )
    assert leaked["render_safe"] is False
    assert export_guard(leaked, "internal_state")["serialized"] is False
    expired = render_internal_route(
        ticker="AVGO",
        route=_route(),
        claims=[_claim(as_of_utc=(NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"))],
        now=NOW,
    )
    assert export_guard(expired, "internal_state")["allowed"] is False
