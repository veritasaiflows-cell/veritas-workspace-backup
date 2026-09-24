#!/usr/bin/env python3
"""Build current, review-only alert states from guarded reference levels.

The controller never derives or applies new levels. It reads guarded SQL
reference metadata, reconciles it with current cached quote evidence, and
turns missing/stale/conflicted inputs into explicit freshness alerts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from finance_sql_canon_access import (
    DynamicEntitlementExternalGateError,
    EvidenceFreshness,
    FinanceSqlCanonAccess,
    ReferenceLevel,
    connect_readonly,
    require_dynamic_entitlement_external_gate,
    verify_dynamic_entitlement_payload,
)
from phase3f_external_canary_approval import (
    Phase3FCanaryAuthorization,
    create_phase3f_component_claim,
    phase3f_component_metrics_shell,
    require_phase3f_component_budget,
    require_phase3f_component_duration,
    require_phase3f_input_bytes,
    strict_canonical_evidence_json_object,
    verified_scope_tickers,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "alert-level-freshness-controller.json"
QUOTE_SNAPSHOT = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
QUOTE_SNAPSHOT_VALIDATION = TMP / "intraday-alerts" / "quote-snapshot-proof-validation.json"

QUOTE_PROOF_REQUIRED_FALSE_AUTHORITY = frozenset({
    "live_trade_or_account_action_allowed",
    "paper_trade_allowed",
    "brokerage_account_mutation_allowed",
    "money_movement_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "sizing_sleeve_cash_risk_rule_change_allowed",
    "cron_channel_config_mutation_allowed",
})

TRACKED_TICKERS = (
    "ETN", "JPM", "NVDA", "GOOG", "MSFT", "GS", "VRT", "BRK.B", "XOM",
    "LMT", "RTX", "AMZN", "CAT", "LLY", "CVX", "PLTR", "AMD", "LNG",
)

# Owner-approved 2026-09-20 (Randall): the Sunday weekly digest is a weekend
# review product. The 36h weekday-intraday quote-age limit would fail every
# Sunday by construction (Friday close to Sunday run is always 40h+), so the
# weekly window uses an 84h tolerance covering normal weekends plus 3-day
# holiday weekends. Weekday windows keep 36.0. Anything older than 84h on a
# weekend is a genuinely broken feed and still decays.
WEEKLY_WINDOW_MAX_QUOTE_AGE_HOURS = 84.0
# Owner-approved 2026-09-23 14:51 MST (Randall, Option A; reopens the
# 2026-09-20 "weekday windows keep 36.0" boundary). A live-intraday age
# ceiling cannot grade a closed-market window: the weekday 06:05 pre_open run
# evaluates the last completed session's quotes, which is 65h after a Friday
# close and so fails the 36h weekday ceiling by construction every Monday and
# post-holiday morning (measured 65.09h on 2026-09-21). Windows the producer
# already stamps closed_market_expected_stale_allowed=True are graded against
# the structural-gap tolerance instead and remain monitor-only. Live
# market_hours_fresh keeps the 36h intraday ceiling unchanged, so genuine
# intraday staleness still decays.
CLOSED_MARKET_MAX_QUOTE_AGE_HOURS = WEEKLY_WINDOW_MAX_QUOTE_AGE_HOURS

AUTHORITY = {
    "review_only": True,
    "derives_new_levels": False,
    "writes_finance_canon": False,
    "maintains_portfolio_state": False,
    "maintains_simulated_account_state": False,
    "capital_or_order_authority": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    if len(text) == 10:
        text += "T23:59:59+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(value: Any, now: datetime) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return (now - parsed).total_seconds() / 3600.0


def finite_age_within(value: Any, maximum: Any) -> bool:
    """Return true only for finite, non-boolean ages inside a closed range."""

    if isinstance(value, bool) or isinstance(maximum, bool):
        return False
    try:
        age = float(value)
        limit = float(maximum)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(age) and math.isfinite(limit) and limit >= 0.0 and 0.0 <= age <= limit


def display_age(value: float | None) -> float | None:
    return round(value, 2) if isinstance(value, float) and math.isfinite(value) else value


def _truthy_conflict_metadata(payload: dict[str, Any]) -> bool:
    clean_values = {None, False, 0, "", "clean", "none", "no_conflict", "unambiguous", "ok"}
    for key, value in payload.items():
        lowered_key = str(key).lower()
        if "conflict" not in lowered_key and "ambigu" not in lowered_key:
            continue
        if isinstance(value, (list, tuple, set, dict)):
            if value:
                return True
            continue
        normalized = value.lower() if isinstance(value, str) else value
        if normalized not in clean_values:
            return True
    return False


def quote_proof_is_clean(
    quote_proof: dict[str, Any] | None,
    quote_validation: dict[str, Any] | None = None,
    quote_row: dict[str, Any] | None = None,
    *,
    expected_artifact_identity: str = "tmp/intraday-alerts/quote-snapshot-proof.json",
) -> bool:
    """Validate quote-proof status, authority, conflicts, and session identity."""

    if not isinstance(quote_proof, dict) or quote_proof.get("status") != "ok":
        return False
    validation = quote_validation if isinstance(quote_validation, dict) else quote_proof.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "ok":
        return False
    if validation.get("critical_count") != 0:
        return False
    if validation.get("validated_artifact") != expected_artifact_identity:
        return False

    findings = validation.get("findings")
    if not isinstance(findings, list):
        return False
    for finding in findings:
        if not isinstance(finding, dict):
            return False
        severity = str(finding.get("severity") or "").lower()
        code = str(finding.get("code") or "").lower()
        if severity in {"critical", "error"} or "conflict" in code or "ambiguous" in code:
            return False

    authority = quote_proof.get("authority")
    if not isinstance(authority, dict):
        return False
    if not QUOTE_PROOF_REQUIRED_FALSE_AUTHORITY.issubset(authority):
        return False
    if any(value is not False for value in authority.values()):
        return False
    if _truthy_conflict_metadata(quote_proof) or _truthy_conflict_metadata(validation):
        return False

    credential_source = quote_proof.get("credential_source")
    if not isinstance(credential_source, dict) or credential_source.get("ambiguous_or_live_names_detected") is not False:
        return False
    if quote_proof.get("symbols_missing") != []:
        return False
    snapshots = quote_proof.get("snapshots")
    requested = quote_proof.get("symbols_requested")
    observed = quote_proof.get("symbols_observed")
    if not isinstance(snapshots, list) or not snapshots:
        return False
    if not isinstance(requested, list) or not isinstance(observed, list):
        return False
    snapshot_symbols = [
        str(item.get("symbol") or "").strip().upper()
        for item in snapshots
        if isinstance(item, dict)
    ]
    if not snapshot_symbols or any(not symbol for symbol in snapshot_symbols):
        return False
    if len(snapshot_symbols) != len(set(snapshot_symbols)):
        return False
    if set(snapshot_symbols) != {str(item).strip().upper() for item in requested}:
        return False
    if set(snapshot_symbols) != {str(item).strip().upper() for item in observed}:
        return False

    session = quote_proof.get("market_session")
    if not isinstance(session, dict):
        return False
    if not isinstance(session.get("market_session_window"), str):
        return False
    if not isinstance(session.get("fresh_intraday_allowed"), bool):
        return False
    if not isinstance(session.get("closed_market_expected_stale_allowed"), bool):
        return False
    if quote_row is not None:
        if not isinstance(quote_row, dict) or _truthy_conflict_metadata(quote_row):
            return False
        for field in (
            "market_session_window",
            "fresh_intraday_allowed",
            "closed_market_expected_stale_allowed",
        ):
            if quote_row.get(field) != session.get(field):
                return False
    return True


def rows_by_ticker(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            result[ticker] = row
    return result


def quote_rows_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("snapshots")
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("symbol") or "").strip().upper()
        if ticker:
            result[ticker] = row
    return result


def reference_lineage(ticker: str) -> dict[str, Any]:
    wanted = {"reference_price_low", "reference_price_high", "reference_invalidation_level"}
    with connect_readonly() as conn:
        rows = conn.execute(
            """
            SELECT field_name, source_artifact_path, source_artifact_sha256,
                   source_generated_at_utc, source_status, validator_status
            FROM source_lineage
            WHERE scope='ticker' AND scope_key=? AND field_family='reference_levels'
            """,
            (ticker,),
        ).fetchall()
    selected = [dict(row) for row in rows if str(row["field_name"]) in wanted]
    timestamps = [str(row.get("source_generated_at_utc")) for row in selected if row.get("source_generated_at_utc")]
    artifact_checks: list[dict[str, Any]] = []
    for row in selected:
        source = str(row.get("source_artifact_path") or "")
        expected_hash = str(row.get("source_artifact_sha256") or "").lower()
        path = ROOT / source if source else None
        actual_hash = None
        if path is not None and path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual_hash = digest.hexdigest()
        artifact_checks.append({
            "path": source or None,
            "exists": bool(path and path.is_file()),
            "expected_sha256": expected_hash or None,
            "actual_sha256": actual_hash,
            "hash_matches": bool(expected_hash and actual_hash == expected_hash),
        })
    return {
        "fields": selected,
        "artifact_checks": artifact_checks,
        "level_as_of_utc": max(timestamps) if timestamps else None,
        "source_paths": sorted({str(row.get("source_artifact_path")) for row in selected if row.get("source_artifact_path")}),
        "lineage_validation_ok": bool(selected) and all(
            str(row.get("source_status") or "").lower() == "ok"
            and str(row.get("validator_status") or "").lower() == "ok"
            for row in selected
        ) and all(check["hash_matches"] for check in artifact_checks),
    }


def confidence_label(raw: Any, stale: bool, conflicted: bool) -> str:
    if conflicted or stale:
        return "low"
    try:
        score = int(raw)
    except (TypeError, ValueError):
        return "medium"
    # Canon reference_confidence is a whole-number percent 0-100
    # (data_confidence_v1; owner-delegated rescale 2026-09-24). The old 1-5
    # thresholds labelled every percent value "high". Single-source Yahoo data
    # is capped at 50, so nothing reads "high" until a second source exists.
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def classify_signal(price: float | None, low: float | None, high: float | None, threshold: float | None) -> str:
    if price is None or low is None or high is None:
        return "freshness_decay"
    if threshold is not None and price < threshold:
        return "invalidation_alert"
    if low <= price <= high:
        return "band_entry"
    if price > high:
        return "no_chase"
    distance = (low - price) / low if low else 1.0
    return "near_band" if 0 <= distance <= 0.03 else "monitor_only"


def quote_evaluation_policy(
    quote_row: dict[str, Any],
    quote_age_hours: float | None,
    max_quote_age_hours: float,
    *,
    quote_proof: dict[str, Any] | None = None,
    quote_validation: dict[str, Any] | None = None,
    expected_artifact_identity: str = "tmp/intraday-alerts/quote-snapshot-proof.json",
) -> dict[str, bool | str]:
    """Separate calendar-current evidence from alert-fire eligibility.

    A last-completed-session quote can be valid review context while the market
    is closed, but it is never a fresh intraday alert trigger. A genuinely
    fresh intraday quote observed inside a session-boundary window
    (pre_open, open_settling, post_close) is likewise calendar-current
    review-only evidence: the producer deliberately withholds fire
    eligibility outside market hours, and such a quote is never
    fire-eligible and never decays merely for landing at a boundary.
    """

    # Per producer contract (market_calendar_freshness.py): the expected
    # closed_market_expected_stale_allowed flag for each boundary window.
    boundary_closed_flag = {"pre_open": True, "open_settling": False, "post_close": True}

    calendar_status = str(quote_row.get("calendar_freshness_status") or "")
    freshness_status = str(quote_row.get("freshness_status") or "")
    market_session_window = str(quote_row.get("market_session_window") or "")
    age_current = finite_age_within(quote_age_hours, max_quote_age_hours)
    # Closed-market windows are graded against the structural-gap tolerance,
    # never the live-intraday ceiling. Fire eligibility is untouched: it still
    # requires market_hours_fresh plus a clean intraday proof.
    closed_market_window = (
        market_session_window in {"market_closed_weekend_or_holiday", "pre_open", "post_close"}
        and quote_row.get("fresh_intraday_allowed") is False
        and quote_row.get("closed_market_expected_stale_allowed") is True
    )
    closed_market_age_current = finite_age_within(
        quote_age_hours,
        max(CLOSED_MARKET_MAX_QUOTE_AGE_HOURS, max_quote_age_hours) if closed_market_window else max_quote_age_hours,
    )
    proof_clean = quote_proof_is_clean(
        quote_proof,
        quote_validation,
        quote_row,
        expected_artifact_identity=expected_artifact_identity,
    )
    fresh_intraday_evidence = (
        proof_clean
        and age_current
        and calendar_status == "fresh_intraday"
        and freshness_status == "fresh"
    )
    fresh_intraday = (
        fresh_intraday_evidence
        and market_session_window == "market_hours_fresh"
        and quote_row.get("fresh_intraday_allowed") is True
        and quote_row.get("closed_market_expected_stale_allowed") is False
    )
    session_boundary_current = (
        fresh_intraday_evidence
        and market_session_window in boundary_closed_flag
        and quote_row.get("fresh_intraday_allowed") is False
        and quote_row.get("closed_market_expected_stale_allowed") is boundary_closed_flag[market_session_window]
    )
    closed_session_current = (
        proof_clean
        and closed_market_age_current
        and calendar_status in {"current_last_completed_session", "market_closed_expected_stale"}
        and freshness_status in {"current_but_not_intraday_fresh", "stale"}
        and market_session_window in {"market_closed_weekend_or_holiday", "pre_open", "post_close"}
        and quote_row.get("fresh_intraday_allowed") is False
        and quote_row.get("closed_market_expected_stale_allowed") is True
    )
    calendar_current = fresh_intraday or session_boundary_current or closed_session_current
    stale_or_missing = not calendar_current
    fire_eligible = fresh_intraday
    monitor_only = closed_session_current or session_boundary_current
    if fresh_intraday:
        classification = "market_hours_fresh"
    elif session_boundary_current:
        classification = "session_boundary_current"
    elif closed_session_current:
        classification = "closed_session_current"
    else:
        classification = "stale_or_missing"
    return {
        "calendar_current": calendar_current,
        "stale_or_missing": stale_or_missing,
        "fire_eligible": fire_eligible,
        "monitor_only": monitor_only,
        "classification": classification,
    }


def build_payload(
    *,
    tickers: Iterable[str] = TRACKED_TICKERS,
    now: datetime | None = None,
    max_quote_age_hours: float = 36.0,
    max_level_age_days: float = 14.0,
    client: FinanceSqlCanonAccess | None = None,
    quote_snapshot_payload: dict[str, Any] | None = None,
    quote_validation_payload: dict[str, Any] | None = None,
    quote_artifact_identity: str = "tmp/intraday-alerts/quote-snapshot-proof.json",
    quote_validation_identity: str | None = None,
    guard_validation_payload: dict[str, Any] | None = None,
    sql_guard_identity: str = "tmp/finance-sql-canon-access-validation.json",
    lineage_reader: Any = None,
    quote_ticker_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    observed_at = now or utc_now()
    sql = client or FinanceSqlCanonAccess()
    guard = (
        guard_validation_payload
        if guard_validation_payload is not None
        else sql.validate()
    )
    quote_snapshot = (
        quote_snapshot_payload
        if quote_snapshot_payload is not None
        else load_json(QUOTE_SNAPSHOT)
    )
    quote_validation = (
        quote_validation_payload
        if quote_validation_payload is not None
        else load_json(QUOTE_SNAPSHOT_VALIDATION)
    )
    lineage_lookup = lineage_reader or reference_lineage
    quote_rows = quote_rows_by_ticker(quote_snapshot)
    if quote_ticker_aliases is not None:
        quote_rows = {quote_ticker_aliases.get(symbol, symbol): row for symbol, row in quote_rows.items()}
    rows: list[dict[str, Any]] = []
    structural_errors: list[str] = []

    if guard.get("status") != "ok":
        structural_errors.append("guarded SQL access validation is not ok")
    if not quote_rows:
        structural_errors.append("current alert quote snapshot is unavailable")
    if not quote_proof_is_clean(
        quote_snapshot,
        quote_validation,
        expected_artifact_identity=quote_artifact_identity,
    ):
        structural_errors.append("current alert quote proof status, validation, authority, or conflict metadata is not clean")

    for raw_ticker in tickers:
        ticker = str(raw_ticker).strip().upper()
        reference = sql.reference_level(ticker) if guard.get("status") == "ok" else None
        freshness = sql.evidence_freshness(ticker) if guard.get("status") == "ok" else None
        quote_row = quote_rows.get(ticker, {})
        lineage = lineage_lookup(ticker) if guard.get("status") == "ok" else {
            "fields": [], "level_as_of_utc": None, "source_paths": [], "lineage_validation_ok": False,
        }

        low = reference.reference_price_low if reference else None
        high = reference.reference_price_high if reference else None
        threshold = reference.reference_invalidation_level if reference else None
        price = quote_row.get("price")
        quote_source = quote_artifact_identity
        quote_stamp = quote_row.get("source_timestamp_utc")
        quote_calendar_status = str(quote_row.get("calendar_freshness_status") or "")
        quote_freshness_status = str(quote_row.get("freshness_status") or "")
        quote_data_date = quote_row.get("source_market_date") or quote_row.get("latest_market_date")
        price = float(price) if isinstance(price, (int, float)) else None

        level_stamp = lineage.get("level_as_of_utc")
        level_source = ",".join(lineage.get("source_paths") or []) or None
        quote_age = age_hours(quote_stamp, observed_at)
        level_age = age_hours(level_stamp, observed_at)
        quote_policy = quote_evaluation_policy(
            quote_row,
            quote_age,
            max_quote_age_hours,
            quote_proof=quote_snapshot,
            quote_validation=quote_validation,
            expected_artifact_identity=quote_artifact_identity,
        )
        quote_calendar_current = quote_policy["calendar_current"]
        quote_stale = quote_policy["stale_or_missing"]
        alert_fire_eligible = quote_policy["fire_eligible"]
        quote_monitor_only = quote_policy["monitor_only"]
        quote_classification = quote_policy.get("classification")
        level_stale = not finite_age_within(level_age, max_level_age_days * 24.0)
        stale_families = list(freshness.stale_families) if freshness else ["evidence_freshness_missing"]
        if quote_calendar_current:
            stale_families = [family for family in stale_families if family != "fresh_price_quote"]
        conflicted = not bool(lineage.get("lineage_validation_ok"))
        level_relationship_state = classify_signal(price, low, high, threshold)
        alert_state = (
            "freshness_decay"
            if quote_stale or level_stale or conflicted or stale_families
            else ("monitor_only" if quote_monitor_only else level_relationship_state)
        )
        reasons: list[str] = []
        if quote_stale:
            reasons.append("quote evidence is stale or unstamped")
        if level_stale:
            reasons.append("reference level requires freshness review")
        if conflicted:
            reasons.append("reference-level lineage or value reconciliation is not clean")
        if stale_families:
            reasons.append("stale evidence families: " + ", ".join(sorted(stale_families)))
        if quote_monitor_only and alert_state == "monitor_only":
            if quote_classification == "session_boundary_current":
                reasons.append("fresh quote at a session boundary window is review-only and cannot fire an alert")
            else:
                reasons.append("last-completed-session quote is review-only and cannot fire an alert")
        if not reasons:
            reasons.append("guarded reference and fresh intraday quote evidence are structurally current")

        rows.append({
            "ticker": ticker,
            "reference_low": low,
            "reference_high": high,
            "invalidation_threshold": threshold,
            "latest_price": price,
            "level_as_of_utc": level_stamp,
            "quote_as_of_utc": quote_stamp,
            "quote_data_date": quote_data_date,
            "quote_calendar_status": quote_calendar_status or None,
            "quote_freshness_status": quote_freshness_status or None,
            "market_session_window": quote_row.get("market_session_window"),
            "alert_fire_eligible": alert_fire_eligible,
            "level_age_hours": display_age(level_age),
            "quote_age_hours": display_age(quote_age),
            "freshness_status": (
                "review_required"
                if alert_state == "freshness_decay"
                else ("current_last_completed_session_monitor" if quote_monitor_only else "current_intraday")
            ),
            "validation_status": "ok" if not conflicted and reference is not None and price is not None else "review_required",
            "confidence": confidence_label(reference.reference_confidence if reference else None, quote_stale or level_stale, conflicted),
            "level_relationship_state": level_relationship_state,
            "signal_state": alert_state,
            "alert_state": alert_state,
            "reasons": reasons,
            "source_path": level_source,
            "quote_source_path": quote_source,
            "sql_reference": asdict(reference) if reference else None,
        })

    required_fields = ("ticker", "reference_low", "reference_high", "invalidation_threshold", "alert_state")
    incomplete = [row["ticker"] for row in rows if any(row.get(field) is None for field in required_fields)]
    if incomplete:
        structural_errors.append("missing required level fields: " + ", ".join(incomplete))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["alert_state"]] = counts.get(row["alert_state"], 0) + 1

    status = "error" if structural_errors else "ok"
    return {
        "schema": "veritas.alert_level_freshness_controller.v1",
        "generated_at_utc": iso_utc(observed_at),
        "status": status,
        "purpose": "review-only current alert evaluation over guarded static reference levels",
        "authority": dict(AUTHORITY),
        "policy": {
            "max_quote_age_hours": max_quote_age_hours,
            "max_level_age_days": max_level_age_days,
            "stale_inputs_emit_freshness_alerts": True,
            "quote_proof_must_validate_cleanly": True,
            "price_does_not_rederive_levels": True,
        },
        "source_artifacts": {
            "sql_guard": sql_guard_identity,
            "quote_snapshot": quote_artifact_identity,
            "quote_snapshot_validation": (
                "tmp/intraday-alerts/quote-snapshot-proof-validation.json"
                if quote_validation_payload is None
                else quote_validation_identity or quote_artifact_identity + ".validation"
            ),
        },
        "summary": {
            "ticker_count": len(rows),
            "alert_state_counts": counts,
            "freshness_review_tickers": [row["ticker"] for row in rows if row["alert_state"] == "freshness_decay"],
            "band_entry_signal_tickers": [row["ticker"] for row in rows if row["alert_state"] == "band_entry"],
            "invalidation_signal_tickers": [row["ticker"] for row in rows if row["alert_state"] == "invalidation_alert"],
            "no_chase_signal_tickers": [row["ticker"] for row in rows if row["alert_state"] == "no_chase"],
            "monitor_only_tickers": [row["ticker"] for row in rows if row["alert_state"] == "monitor_only"],
            "fresh_intraday_signal_eligible_tickers": [
                row["ticker"] for row in rows if row["alert_fire_eligible"]
            ],
            "quote_session_dates": sorted({
                str(row["quote_data_date"])
                for row in rows
                if row.get("quote_data_date")
            }),
            "quote_as_of_utc_values": sorted({
                str(row["quote_as_of_utc"])
                for row in rows
                if row.get("quote_as_of_utc")
            }),
        },
        "rows": rows,
        "validation": {"status": status, "errors": structural_errors, "warnings": []},
    }


def _phase3f_exact_quote_symbols(
    quote_snapshot: dict[str, Any],
    expected_tickers: tuple[str, ...],
) -> None:
    snapshots = quote_snapshot.get("snapshots")
    requested = quote_snapshot.get("symbols_requested")
    observed = quote_snapshot.get("symbols_observed")
    if not isinstance(snapshots, list) or not isinstance(requested, list) or not isinstance(observed, list):
        raise ValueError("phase3f_quote_scope_mismatch")
    if not all(isinstance(item, str) and item == item.strip().upper() for item in requested):
        raise ValueError("phase3f_quote_scope_mismatch")
    if not all(isinstance(item, str) and item == item.strip().upper() for item in observed):
        raise ValueError("phase3f_quote_scope_mismatch")
    snapshot_symbols: list[str] = []
    for row in snapshots:
        if not isinstance(row, dict):
            raise ValueError("phase3f_quote_scope_mismatch")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or symbol != symbol.strip().upper():
            raise ValueError("phase3f_quote_scope_mismatch")
        snapshot_symbols.append(symbol)
    if (
        tuple(requested) != expected_tickers
        or tuple(observed) != expected_tickers
        or tuple(snapshot_symbols) != expected_tickers
        or len(set(snapshot_symbols)) != len(snapshot_symbols)
    ):
        raise ValueError("phase3f_quote_scope_mismatch")


_PHASE3F_REFERENCE_EVIDENCE_KEYS = frozenset(
    {
        "schema",
        "status",
        "database_path",
        "database_sha256",
        "scope_fingerprint",
        "scope_payload_sha256",
        "tickers",
        "reference_levels",
        "evidence_freshness",
        "lineage",
        "errors",
    }
)
_PHASE3F_REFERENCE_LEVEL_KEYS = frozenset(
    {
        "ticker",
        "reference_price_low",
        "reference_price_high",
        "reference_invalidation_level",
        "reference_confidence",
        "reference_band_status",
        "authority_class",
        "fallback_rule",
    }
)
_PHASE3F_FRESHNESS_KEYS = frozenset(
    {
        "ticker",
        "resolution_state",
        "required_depth",
        "card_generated_at_utc",
        "card_missing_or_stale_count",
        "stale_families",
        "source_confidence_class",
        "authority_class",
    }
)
_PHASE3F_LINEAGE_KEYS = frozenset(
    {
        "fields",
        "artifact_checks",
        "level_as_of_utc",
        "source_paths",
        "lineage_validation_ok",
    }
)


class _Phase3FFrozenReferenceClient:
    def __init__(
        self,
        references: dict[str, ReferenceLevel],
        freshness: dict[str, EvidenceFreshness],
    ) -> None:
        self._references = references
        self._freshness = freshness

    def validate(self) -> dict[str, Any]:
        raise AssertionError("Phase 3F frozen evidence must not run SQL validation")

    def reference_level(self, ticker: str) -> ReferenceLevel | None:
        return self._references.get(ticker)

    def evidence_freshness(self, ticker: str) -> EvidenceFreshness | None:
        return self._freshness.get(ticker)

    def dynamic_entitlement_scope(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Phase 3F child must not resolve membership")


def _phase3f_reference_evidence(
    raw: bytes,
    *,
    authorization: Phase3FCanaryAuthorization,
    tickers: tuple[str, ...],
    allow_missing: bool = False,
) -> tuple[_Phase3FFrozenReferenceClient, Any, str]:
    observed_hash = require_phase3f_input_bytes(
        authorization.approval,
        name="alert_reference_evidence",
        raw=raw,
    )
    payload = strict_canonical_evidence_json_object(
        raw, maximum_bytes=10 * 1024 * 1024
    )
    database_hash = payload.get("database_sha256")
    if (
        frozenset(payload) != _PHASE3F_REFERENCE_EVIDENCE_KEYS
        or payload.get("schema")
        != "veritas.phase3f.alert_reference_evidence.v1"
        or payload.get("status") != "ok"
        or payload.get("database_path") != "state/finance/finance-canon.sqlite"
        or not isinstance(database_hash, str)
        or len(database_hash) != 64
        or any(character not in "0123456789abcdef" for character in database_hash)
        or payload.get("scope_fingerprint") != authorization.scope.fingerprint
        or payload.get("scope_payload_sha256") != authorization.scope.payload_sha256
        or tuple(payload.get("tickers") or ()) != tickers
        or payload.get("errors") != []
    ):
        raise ValueError("phase3f_reference_evidence_invalid")
    reference_rows = payload.get("reference_levels")
    freshness_rows = payload.get("evidence_freshness")
    lineage_rows = payload.get("lineage")
    if (
        not isinstance(reference_rows, dict)
        or not isinstance(freshness_rows, dict)
        or not isinstance(lineage_rows, dict)
        or (not allow_missing and tuple(sorted(reference_rows)) != tickers)
        or (not allow_missing and tuple(sorted(freshness_rows)) != tickers)
        or (not allow_missing and tuple(sorted(lineage_rows)) != tickers)
        or not set(reference_rows).issubset(tickers)
        or not set(freshness_rows).issubset(tickers)
        or not set(lineage_rows).issubset(tickers)
    ):
        raise ValueError("phase3f_reference_evidence_invalid")
    references: dict[str, ReferenceLevel] = {}
    freshness: dict[str, EvidenceFreshness] = {}
    lineage: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        if allow_missing and any(ticker not in rows for rows in (reference_rows, freshness_rows, lineage_rows)):
            lineage[ticker] = {
                "fields": [], "artifact_checks": [], "level_as_of_utc": None,
                "source_paths": [], "lineage_validation_ok": False,
            }
            continue
        reference = reference_rows[ticker]
        fresh = freshness_rows[ticker]
        line = lineage_rows[ticker]
        if (
            not isinstance(reference, dict)
            or frozenset(reference) != _PHASE3F_REFERENCE_LEVEL_KEYS
            or reference.get("ticker") != ticker
            or not isinstance(fresh, dict)
            or frozenset(fresh) != _PHASE3F_FRESHNESS_KEYS
            or fresh.get("ticker") != ticker
            or not isinstance(fresh.get("stale_families"), list)
            or any(not isinstance(item, str) for item in fresh["stale_families"])
            or not isinstance(line, dict)
            or frozenset(line) != _PHASE3F_LINEAGE_KEYS
            or not isinstance(line.get("fields"), list)
            or not isinstance(line.get("artifact_checks"), list)
            or not isinstance(line.get("source_paths"), list)
            or any(not isinstance(item, str) for item in line["source_paths"])
            or not isinstance(line.get("lineage_validation_ok"), bool)
        ):
            raise ValueError("phase3f_reference_evidence_invalid")
        try:
            references[ticker] = ReferenceLevel(**reference)
            freshness[ticker] = EvidenceFreshness(**fresh)
        except (TypeError, ValueError) as exc:
            raise ValueError("phase3f_reference_evidence_invalid") from exc
        lineage[ticker] = line
    return (
        _Phase3FFrozenReferenceClient(references, freshness),
        lambda ticker: lineage[ticker],
        observed_hash,
    )


def _build_phase3f_alert_component_with_authorization(
    *,
    authorization: Phase3FCanaryAuthorization,
    reference_evidence_json: bytes,
    quote_snapshot_json: bytes,
    quote_validation_json: bytes,
    now: datetime | None = None,
    dynamic_execution: bool = False,
    max_quote_age_hours: float | None = None,
) -> dict[str, Any]:
    """Build an approved in-memory alert component with zero child SQL reads."""

    started = time.perf_counter()
    observed_at = now or utc_now()
    tickers = verified_scope_tickers(
        authorization,
        component_id="alert_level_freshness",
        now_utc=observed_at,
    )
    require_phase3f_component_budget(
        authorization,
        component_id="alert_level_freshness",
        provider_method_attempts=0,
        retries=0,
        now_utc=observed_at,
    )
    claim_path, claim_sha256 = create_phase3f_component_claim(
        authorization,
        component_id="alert_level_freshness",
        now_utc=observed_at,
    )
    quote_artifact_identity = authorization.approval.output_path(
        "alert_quote_snapshot"
    ).relative_to(authorization.approval.workspace_root).as_posix()
    quote_validation_identity = authorization.approval.output_path(
        "alert_quote_validation"
    ).relative_to(authorization.approval.workspace_root).as_posix()
    reference_evidence_identity = authorization.approval.output_path(
        "alert_reference_evidence"
    ).relative_to(authorization.approval.workspace_root).as_posix()
    quote_snapshot_hash = require_phase3f_input_bytes(
        authorization.approval,
        name="alert_quote_snapshot",
        raw=bytes(quote_snapshot_json),
    )
    quote_validation_hash = require_phase3f_input_bytes(
        authorization.approval,
        name="alert_quote_validation",
        raw=bytes(quote_validation_json),
    )
    frozen_client, frozen_lineage, reference_evidence_hash = (
        _phase3f_reference_evidence(
            bytes(reference_evidence_json),
            authorization=authorization,
            tickers=tickers,
            allow_missing=dynamic_execution,
        )
    )
    quote_snapshot = strict_canonical_evidence_json_object(
        bytes(quote_snapshot_json), maximum_bytes=10 * 1024 * 1024
    )
    quote_validation = strict_canonical_evidence_json_object(
        bytes(quote_validation_json), maximum_bytes=2 * 1024 * 1024
    )
    if dynamic_execution:
        # Explicit existing evidence keeps its original validation identity.
        # Partial or unclean evidence remains enrolled and blocked by build_payload.
        quote_artifact_identity = "tmp/intraday-alerts/quote-snapshot-proof.json"
        aliases = {alias: ticker for ticker in tickers for alias in
                   (ticker, ticker.replace(".", "-"), ticker.replace("-", "."))}
        snapshots = quote_snapshot.get("snapshots", [])
        if not isinstance(snapshots, list) or any(not isinstance(row, dict) for row in snapshots):
            raise ValueError("phase3f_quote_scope_mismatch")
        symbols = [row.get("symbol") for row in snapshots]
        if any(not isinstance(symbol, str) or symbol not in aliases for symbol in symbols):
            raise ValueError("phase3f_quote_scope_mismatch")
        canonical_symbols = [aliases[symbol] for symbol in symbols]
        if len(canonical_symbols) != len(set(canonical_symbols)):
            raise ValueError("phase3f_quote_scope_mismatch")
    else:
        _phase3f_exact_quote_symbols(quote_snapshot, tickers)
        if quote_validation.get("validated_artifact") != quote_artifact_identity:
            raise ValueError("phase3f_quote_artifact_identity_mismatch")
        if not quote_proof_is_clean(
            quote_snapshot,
            quote_validation,
            expected_artifact_identity=quote_artifact_identity,
        ):
            raise ValueError("phase3f_quote_proof_invalid")
    # Weekend-review tolerance (owner-approved 2026-09-20): the caller may
    # pass a wider quote-age limit for the weekly window. None keeps 36h.
    effective_max_quote_age_hours = (
        max_quote_age_hours if max_quote_age_hours is not None else 36.0
    )
    payload = build_payload(
        tickers=tickers,
        now=observed_at,
        max_quote_age_hours=effective_max_quote_age_hours,
        client=frozen_client,
        quote_snapshot_payload=quote_snapshot,
        quote_validation_payload=quote_validation,
        quote_artifact_identity=quote_artifact_identity,
        quote_validation_identity=quote_validation_identity,
        guard_validation_payload={"status": "ok"},
        sql_guard_identity=reference_evidence_identity,
        lineage_reader=frozen_lineage,
        **({"quote_ticker_aliases": aliases} if dynamic_execution else {}),
    )
    payload["phase3f_canary"] = {
        "record_id": authorization.approval.record_id,
        "scope_fingerprint": authorization.scope.fingerprint,
        "scope_payload_sha256": authorization.scope.payload_sha256,
        "receipt_sha256": authorization.receipt_sha256,
        "quote_artifact_identity": quote_artifact_identity,
        "quote_validation_identity": quote_validation_identity,
        "reference_evidence_identity": reference_evidence_identity,
        "reference_evidence_sha256": reference_evidence_hash,
        "quote_snapshot_sha256": quote_snapshot_hash,
        "quote_validation_sha256": quote_validation_hash,
        "component_claim_path": claim_path.relative_to(
            authorization.approval.workspace_root
        ).as_posix(),
        "component_claim_sha256": claim_sha256,
        "membership_resolver_invocations": 0,
        "sql_reads": 0,
        "max_quote_age_hours": effective_max_quote_age_hours,
        "parent_is_only_output_writer": True,
        "external_baseline_blocked": True,
    }
    if dynamic_execution:
        members = json.loads(authorization.scope.canonical_bytes)["members"]
        debt = [row["ticker"] for row in members if not row["decision_grade_eligible"]]
        payload["dynamic_entitlement"] = {"members": members, "decision_grade_debt": debt}
        for row in payload["rows"]:
            if row["ticker"] in debt:
                row.update(alert_state="freshness_decay", signal_state="freshness_decay",
                           alert_fire_eligible=False, freshness_status="review_required",
                           validation_status="review_required", confidence="low")
                row["reasons"].append("effective member is not decision-grade eligible")
            if row["alert_state"] == "freshness_decay":
                row["alert_fire_eligible"] = False
                row["validation_status"] = "review_required"
        # Recompute affected summaries rather than leaving prior green lists.
        counts: dict[str, int] = {}
        for row in payload["rows"]:
            counts[row["alert_state"]] = counts.get(row["alert_state"], 0) + 1
        payload["summary"]["alert_state_counts"] = counts
        for key, state in (("freshness_review_tickers", "freshness_decay"),
                           ("band_entry_signal_tickers", "band_entry"),
                           ("invalidation_signal_tickers", "invalidation_alert"),
                           ("no_chase_signal_tickers", "no_chase"),
                           ("monitor_only_tickers", "monitor_only")):
            payload["summary"][key] = [row["ticker"] for row in payload["rows"] if row["alert_state"] == state]
        payload["summary"]["fresh_intraday_signal_eligible_tickers"] = [
            row["ticker"] for row in payload["rows"] if row["alert_fire_eligible"]
        ]
    duration = time.perf_counter() - started
    final_now = observed_at if now is not None else utc_now()
    require_phase3f_component_duration(
        authorization,
        component_id="alert_level_freshness",
        duration_seconds=duration,
        now_utc=final_now,
    )
    metrics = phase3f_component_metrics_shell(
        "alert_level_freshness",
        status="completed" if payload.get("status") == "ok" and not (
            dynamic_execution and payload["summary"]["freshness_review_tickers"]
        ) else "completed_with_review_debt",
        provider_method_attempts=0,
        provider_method_completed=0,
        provider_method_failed=0,
        duration_seconds=duration,
    )
    return {"artifact": payload, "metrics": metrics}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def dynamic_entitlement_preview(
    client: FinanceSqlCanonAccess | None = None,
) -> tuple[object, dict[str, Any]]:
    """Return a local scope proof only; no quote or output work occurs."""

    scope = (client or FinanceSqlCanonAccess()).dynamic_entitlement_scope()
    payload = scope.payload()
    verify_dynamic_entitlement_payload(payload, scope.fingerprint)
    return scope, {
        "scope": payload,
        "external_scope_gate": "not_enabled",
        "provider_calls": 0,
        "output_writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--tickers", nargs="*", default=list(TRACKED_TICKERS))
    parser.add_argument("--max-quote-age-hours", type=float, default=36.0)
    parser.add_argument("--max-level-age-days", type=float, default=14.0)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--dynamic-entitlement-preview", action="store_true")
    parser.add_argument("--dynamic-entitlement-scope", action="store_true")
    parser.add_argument(
        "--scope-origin",
        default="ad_hoc",
        choices=("ad_hoc", "phase3f_dynamic_entitlement"),
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    from phase3g_dynamic_execution import add_arguments, dispatch
    add_arguments(parser)
    args = parser.parse_args()
    dynamic_result = dispatch(args, components=("alert_level_freshness",))
    if dynamic_result is not None:
        return dynamic_result
    if args.dynamic_entitlement_preview or args.dynamic_entitlement_scope:
        scope, preview = dynamic_entitlement_preview()
        errors: list[str] = []
        status = "planned"
        if args.dynamic_entitlement_scope:
            try:
                require_dynamic_entitlement_external_gate(scope, scope_origin=args.scope_origin)
            except DynamicEntitlementExternalGateError as exc:
                status = "error"
                errors.append(str(exc))
        print(json.dumps({
            "status": status,
            "dynamic_entitlement": preview,
            "errors": errors,
        }, indent=2, sort_keys=True))
        return 1 if errors else 0
    output = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(
        tickers=args.tickers,
        max_quote_age_hours=args.max_quote_age_hours,
        max_level_age_days=args.max_level_age_days,
    )
    if args.write:
        write_json(output, payload)
    print(json.dumps({
        "status": payload["status"],
        "ticker_count": payload["summary"]["ticker_count"],
        "alert_state_counts": payload["summary"]["alert_state_counts"],
        "output": output.relative_to(ROOT).as_posix(),
    }, indent=2))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
