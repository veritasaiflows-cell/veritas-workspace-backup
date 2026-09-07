#!/usr/bin/env python3
"""Focused regression proof for Phase 3D observed-entitlement coverage."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from finance_sql_canon_access import DynamicEntitlementScope
from tier_entitlement_phase3d_observed_coverage import (
    ArtifactSnapshot,
    ENROLLED_NOT_OBSERVED,
    NO_OWNER_SURFACE,
    OBSERVED,
    _safe_parse_utc,
    _validate_output_vocabulary,
    build_observed_coverage_proof,
)


def test_timestamp_parser_accepts_supported_forms() -> None:
    assert _safe_parse_utc("2026-06-16")[1] is None
    assert _safe_parse_utc("2026-09-01T19:59:54.689893378Z")[1] is None
    assert _safe_parse_utc("2026-09-01T19:59:54+00:00")[1] is None
    assert _safe_parse_utc("bad")[1] == "unparseable_timestamp"


RUN_AT = "2026-09-01T21:00:00Z"

# Synthetic fixtures below pin their own artifact timestamps, so RUN_AT stays
# frozen for them.  The live positive control cannot: producers regenerate, and
# a frozen anchor eventually sits before every artifact, which reads as
# ``future_timestamp`` and collapses all 32 names to enrolled-but-not-observed.
# That would hide the real coverage gap behind a clock artifact, so the control
# derives its anchor from the newest live producer artifact instead.
LIVE_PRODUCER_ARTIFACTS = (
    "tmp/alert-level-freshness-controller.json",
    "tmp/analyst-consensus-current.json",
)


def live_control_anchor() -> str:
    root = Path(__file__).resolve().parents[1]
    latest = None
    for relative in LIVE_PRODUCER_ARTIFACTS:
        payload = json.loads((root / relative).read_text(encoding="utf-8"))
        parsed, reason = _safe_parse_utc(payload["generated_at_utc"])
        assert parsed is not None and reason is None, relative
        latest = parsed if latest is None else max(latest, parsed)
    assert latest is not None
    return (latest + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_scope(*tickers: str, overflow: tuple[str, ...] = ()) -> DynamicEntitlementScope:
    members = {
        ticker: SimpleNamespace(tier="A" if index == 0 else "B")
        for index, ticker in enumerate(tickers)
    }
    aliases = {ticker: ticker for ticker in tickers}
    aliases.update({ticker.replace(".", "-"): ticker for ticker in tickers})
    return DynamicEntitlementScope(
        source="guarded_sql:test",
        memberships=members,
        identities=dict(members),
        aliases=aliases,
        fingerprint="scope-test-fingerprint",
        tier_breakdown={"A": 1, "B": max(0, len(tickers) - 1)},
        integrity_breaches=(),
        envelope_name="test",
        envelope_count=1 if overflow else len(tickers),
        overflow_tickers=overflow,
    )


def snapshot(path: str, payload: dict[str, object]) -> ArtifactSnapshot:
    return ArtifactSnapshot(path=path, sha256=f"{path}-sha", payload=payload)


def quote_rows(*tickers: str) -> list[dict[str, object]]:
    return [
        {
            "ticker": ticker,
            "quote_as_of_utc": "2026-09-01T20:00:00.123456789Z",
            "quote_freshness_status": "current_last_completed_session",
            "validation_status": "ok",
        }
        for ticker in tickers
    ]


def analyst_rows(*tickers: str) -> dict[str, dict[str, str]]:
    return {
        ticker: {
            "as_of": "2026-09-01T20:00:00+00:00",
            "source_status": "auto_sourced_test",
        }
        for ticker in tickers
    }


class FakeClient:
    def __init__(self, scope: DynamicEntitlementScope, reference_error: str | None = None) -> None:
        self.scope = scope
        self.reference_error = reference_error
        self.scope_calls = 0

    def dynamic_entitlement_scope(self, **_kwargs: object) -> DynamicEntitlementScope:
        self.scope_calls += 1
        return self.scope

    def reference_level_records(self, tickers: tuple[str, ...]) -> dict[str, SimpleNamespace]:
        if self.reference_error:
            raise RuntimeError(self.reference_error)
        return {
            ticker: SimpleNamespace(
                source_generated_at_utc="2026-09-01",
                source_status="ok",
                validator_status="ok",
            )
            for ticker in tickers
        }

    def evidence_freshness(self, _ticker: str) -> SimpleNamespace:
        return SimpleNamespace(
            resolution_state="recommendation_evidence_review_required",
            card_generated_at_utc=None,
        )

    def ticker_states(self, tickers: tuple[str, ...]) -> dict[str, SimpleNamespace]:
        return {ticker: SimpleNamespace(has_production_card=False) for ticker in tickers}


def build_fake(
    client: FakeClient,
    *,
    quote: list[dict[str, object]],
    analyst: dict[str, dict[str, str]],
    analyst_status: str = "ok",
) -> dict[str, object]:
    return build_observed_coverage_proof(
        client=client,  # type: ignore[arg-type]
        quote_artifact=snapshot(
            "tmp/quote-test.json",
            {"generated_at_utc": "2026-09-01T20:30:00Z", "rows": quote},
        ),
        analyst_artifact=snapshot(
            "tmp/analyst-test.json",
            {
                "generated_at_utc": "2026-09-01T20:30:00Z",
                "status": analyst_status,
                "tickers": analyst,
            },
        ),
        run_as_of_utc=RUN_AT,
        envelope_count=1,
    )


def cell(proof: dict[str, object], ticker: str, evidence_class: str) -> dict[str, object]:
    rows = proof["rows"]
    assert isinstance(rows, list)
    row = next(item for item in rows if item["ticker"] == ticker)
    return row["evidence"][evidence_class]


def test_membership_parity_never_truncates_an_over_envelope_scope() -> None:
    client = FakeClient(make_scope("ALPHA", "BRAVO", overflow=("BRAVO",)))
    proof = build_fake(client, quote=quote_rows("ALPHA", "BRAVO"), analyst=analyst_rows("ALPHA", "BRAVO"))
    assert {row["ticker"] for row in proof["rows"]} == {"ALPHA", "BRAVO"}
    assert proof["scope"]["scope_over_envelope"] == ["BRAVO"]
    assert proof["resolver_invocation_count"] == 1
    assert client.scope_calls == 1


def test_current_baseline_positive_control_keeps_the_known_fourteen_name_gap_visible() -> None:
    proof = build_observed_coverage_proof(run_as_of_utc=live_control_anchor())
    # Fourteen Tier A+B names have no quote row in the producer artifact at all.
    absent_from_producer = {
        "CME", "ITA", "LIN", "META", "PH", "BKNG", "ECL", "GE", "KTOS",
        "NFLX", "SMCI", "TMUS", "VMC", "WMB",
    }
    # PLTR is a distinct, tracked producer defect rather than a missing name:
    # its row carries quote_freshness_status "fresh" and quote_calendar_status
    # "fresh_intraday" while its own reasons claim the quote is stale, so the
    # controller refuses to call it current.  Keep it named and separate so a
    # fix, or a spread to other names, both fail this control loudly.
    contradicting_producer = {"PLTR"}
    by_reason: dict[str, set[str]] = {}
    for row in proof["rows"]:
        quote = row["evidence"]["quote_session"]
        by_reason.setdefault(quote["reason"], set()).add(row["ticker"])
    assert proof["scope"]["count"] == 32
    assert proof["source_presence_counts"] == {"quote_session": 18, "analyst_symbol": 18}
    assert proof["scope"]["source"] == "guarded_sql:universe_membership.tier"
    assert by_reason["quote_source_row_missing"] == absent_from_producer
    assert by_reason["quote_not_current"] == contradicting_producer
    observed_quotes = {
        row["ticker"]
        for row in proof["rows"]
        if row["evidence"]["quote_session"]["state"] == OBSERVED
    }
    assert len(observed_quotes) == 17
    assert (
        set(row["ticker"] for row in proof["rows"]) - observed_quotes
        == absent_from_producer | contradicting_producer
    )
    assert proof["coverage_counts"]["recommendation_card"][OBSERVED] == 0
    assert proof["coverage_counts"]["queue"][NO_OWNER_SURFACE] == 32


def test_undefined_recency_never_becomes_reference_or_lineage_observation() -> None:
    client = FakeClient(make_scope("ALPHA", "BRAVO"))
    proof = build_fake(client, quote=quote_rows("ALPHA", "BRAVO"), analyst=analyst_rows("ALPHA", "BRAVO"))
    for ticker in ("ALPHA", "BRAVO"):
        assert cell(proof, ticker, "reference_level")["state"] == ENROLLED_NOT_OBSERVED
        assert cell(proof, ticker, "reference_level")["reason"] == "recency_limit_undefined"
        assert cell(proof, ticker, "lineage")["reason"] == "recency_limit_undefined"
        assert cell(proof, ticker, "queue")["state"] == NO_OWNER_SURFACE


def test_reference_lineage_error_blocks_the_run_but_keeps_every_member_visible() -> None:
    client = FakeClient(make_scope("ALPHA", "BRAVO"), reference_error="synthetic_lineage_failure")
    proof = build_fake(client, quote=quote_rows("ALPHA"), analyst=analyst_rows("ALPHA"))
    assert proof["status"] == "blocked"
    assert {row["ticker"] for row in proof["rows"]} == {"ALPHA", "BRAVO"}
    for ticker in ("ALPHA", "BRAVO"):
        assert cell(proof, ticker, "reference_level")["reason"] == "lineage_blocked"
        assert cell(proof, ticker, "lineage")["detail"] == "synthetic_lineage_failure"


def test_aliases_resolve_only_from_the_scope_and_never_add_an_out_of_scope_symbol() -> None:
    client = FakeClient(make_scope("BRK.B"))
    client.scope.aliases["TIER-C"] = "TIER.C"
    proof = build_fake(
        client,
        quote=quote_rows("BRK-B", "TIER-C", "UNKNOWN"),
        analyst=analyst_rows("BRK-B", "TIER-C", "UNKNOWN"),
    )
    assert cell(proof, "BRK.B", "quote_session")["state"] == OBSERVED
    assert {item["reason"] for item in proof["artifact_symbol_debt"]["quote_session"]} == {
        "out_of_scope", "unresolved_symbol",
    }
    assert [row["ticker"] for row in proof["rows"]] == ["BRK.B"]


def test_placeholder_analyst_data_is_never_observed_even_when_a_symbol_is_present() -> None:
    client = FakeClient(make_scope("ALPHA"))
    proof = build_fake(
        client,
        quote=quote_rows("ALPHA"),
        analyst=analyst_rows("ALPHA"),
        analyst_status="placeholder_manual_required",
    )
    analyst = cell(proof, "ALPHA", "analyst_symbol")
    assert analyst["state"] == ENROLLED_NOT_OBSERVED
    assert analyst["reason"] == "analyst_placeholder_manual_required"


def test_alias_collision_and_adversarial_timestamps_fail_closed() -> None:
    client = FakeClient(make_scope("BRK.B"))
    duplicate_rows = quote_rows("BRK-B", "BRK.B")
    proof = build_fake(client, quote=duplicate_rows, analyst=analyst_rows("BRK-B"))
    assert cell(proof, "BRK.B", "quote_session")["reason"] == "alias_conflict"

    future = quote_rows("BRK.B")
    future[0]["quote_as_of_utc"] = "2026-09-01T22:00:00Z"
    future_proof = build_fake(FakeClient(make_scope("BRK.B")), quote=future, analyst=analyst_rows("BRK.B"))
    assert cell(future_proof, "BRK.B", "quote_session")["reason"] == "future_timestamp"

    missing = quote_rows("BRK.B")
    del missing[0]["quote_as_of_utc"]
    missing_proof = build_fake(FakeClient(make_scope("BRK.B")), quote=missing, analyst=analyst_rows("BRK.B"))
    assert cell(missing_proof, "BRK.B", "quote_session")["reason"] == "missing_timestamp"


def test_build_is_deterministic_and_has_no_writer_or_subprocess_side_effect() -> None:
    client = FakeClient(make_scope("ALPHA"))
    with (
        mock.patch.object(Path, "write_text", side_effect=AssertionError("write attempted")),
        mock.patch("subprocess.run", side_effect=AssertionError("subprocess attempted")),
    ):
        first = build_fake(client, quote=quote_rows("ALPHA"), analyst=analyst_rows("ALPHA"))
    second = build_fake(FakeClient(make_scope("ALPHA")), quote=quote_rows("ALPHA"), analyst=analyst_rows("ALPHA"))
    assert first["coverage_fingerprint"] == second["coverage_fingerprint"]
    _validate_output_vocabulary(first)
    with pytest.raises(RuntimeError, match="phase3d_output_vocabulary_blocked"):
        _validate_output_vocabulary({"example_allowed": False})
