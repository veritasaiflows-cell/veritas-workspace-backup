"""Review-only source freshness maturity scorecard for finance evidence.

This layer deliberately separates source verification, review freshness, and
decision freshness. It does not alter the SQL/canon state, portfolio, approval,
capital deployment, trade, account, paper, live, customer, or schedule surface.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT = TMP / "finance-source-freshness-maturity.json"

AUTHORITY = {
    "review_only": True,
    "source_evidence_classification_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "cron_schedule_mutation_allowed": False,
}

AUTO_RETRY_CODES = {"sec_lag_wait"}
MANUAL_REPAIR_CODES = {
    "sec_metric_conflict",
    "sec_manual_period_review_required",
    "foreign_issuer_ir_required",
    "tbv_ir_crosscheck_required",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def age_days(value: Any, *, as_of: date) -> int | None:
    """Return period age without treating an absent or future date as a value."""

    source_date = parse_iso_date(value)
    if not source_date:
        return None
    return max(0, (as_of - source_date).days)


def age_bucket(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days == 0:
        return "same_day"
    if days <= 7:
        return "one_to_seven_days"
    if days <= 30:
        return "eight_to_thirty_days"
    return "over_thirty_days"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def indexed_rows(payload: dict[str, Any], key: str = "ticker") -> dict[str, dict[str, Any]]:
    return {
        str(row.get(key) or "").upper(): row
        for row in as_list(payload.get("rows"))
        if isinstance(row, dict) and str(row.get(key) or "").strip()
    }


def repair_mode_for(ticker: str, tier: str | None, attention: dict[str, Any], validation_findings: list[dict[str, Any]]) -> str:
    ticker_findings = [item for item in validation_findings if str(item.get("ticker") or "").upper() == ticker]
    codes = {str(item.get("code") or "") for item in ticker_findings}
    if codes & MANUAL_REPAIR_CODES:
        return "manual_conflict_or_period_review"
    if codes & AUTO_RETRY_CODES:
        return "automatic_sec_lag_retry"
    if tier == "Tier C":
        return "selective_attention_repair" if attention.get("attention_triggered") is True else "monitor_hold_no_bulk_repair"
    return "routine_review_only_monitoring"


def source_grade_for(capture: dict[str, Any], rollforward: dict[str, Any]) -> tuple[bool, bool, str]:
    if not capture:
        return False, False, "no_validator_clean_capture"
    if capture.get("validation_clean") is not True or capture.get("authority_clean") is not True:
        return False, False, "capture_not_validator_or_authority_clean"
    state = str(capture.get("current_state") or "")
    source_verified = state.startswith("latest_") or capture.get("source_verified") is True
    if not source_verified:
        return False, False, state or "capture_not_current"
    if capture.get("source_capture_status") == "source_verified_manual_reconciliation_pending":
        return True, False, "source_verified_manual_reconciliation_pending"
    pending = str(rollforward.get("status") or "") == "updated_source_verified_pending_reconciliation"
    if pending:
        return True, False, "source_verified_manual_reconciliation_pending"
    return True, True, "validator_clean_substantive_or_bridged_capture"


def _queue_item(
    *,
    ticker: str,
    queue_status: str,
    reason: str,
    period_end: Any,
    as_of: date,
    routing: str,
    source_artifact: Any = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    days = age_days(period_end, as_of=as_of)
    return {
        "ticker": ticker,
        "queue_status": queue_status,
        "reason": reason,
        "reasons": [reason],
        "reason_codes": [reason_code or reason],
        "period_end": period_end or None,
        "age_days": days,
        "age_bucket": age_bucket(days),
        "routing": routing,
        "source_artifact": source_artifact,
        "review_only": True,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
    }


QUEUE_ROUTING_PRIORITY = {
    "manual_conflict_or_period_review": 100,
    "source_open_repair": 80,
    "source_open_field_reconciliation": 60,
    "automatic_sec_lag_retry": 40,
    "downstream_review_only_rebuild": 20,
}


def _queue_priority(item: dict[str, Any]) -> int:
    return QUEUE_ROUTING_PRIORITY.get(str(item.get("routing") or ""), 0)


def _append_distinct(values: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def _append_unique(items: list[dict[str, Any]], candidate: dict[str, Any]) -> None:
    """Merge duplicate ticker/status queue rows without hiding stronger escalation."""

    key = (str(candidate.get("ticker") or ""), str(candidate.get("queue_status") or ""))
    existing = next(
        (
            item
            for item in items
            if (str(item.get("ticker") or ""), str(item.get("queue_status") or "")) == key
        ),
        None,
    )
    if existing is None:
        items.append(candidate)
        return

    reasons = existing.setdefault("reasons", [str(existing.get("reason") or "")])
    reason_codes = existing.setdefault("reason_codes", [str(existing.get("reason") or "")])
    for reason in candidate.get("reasons", [candidate.get("reason")]):
        _append_distinct(reasons, reason)
    for code in candidate.get("reason_codes", [candidate.get("reason")]):
        _append_distinct(reason_codes, code)

    # A metric/period conflict must remain the primary route even when an
    # ordinary reconciliation row for the same ticker was seen first.
    if _queue_priority(candidate) > _queue_priority(existing):
        for field in ("reason", "routing", "period_end", "age_days", "age_bucket", "source_artifact"):
            value = candidate.get(field)
            if value is not None:
                existing[field] = value


def build_payload(as_of: datetime | None = None) -> dict[str, Any]:
    reference = as_of or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference_date = reference.astimezone(timezone.utc).date()
    registry = load_json(TMP / "wf70-official-capture-period-registry.json")
    ledger = load_json(TMP / "wf78-ticker-freshness-ledger.json")
    attention_payload = load_json(TMP / "wf78-tier-c-attention-trigger.json")
    metrics_validation = load_json(TMP / "fundamental-metrics-validation.json")
    rollforward = load_json(TMP / "earnings-rollforward-guard.json")
    bridge = load_json(TMP / "official-earnings-bridge.json")

    ledger_rows = indexed_rows(ledger)
    attention_rows = indexed_rows(attention_payload)
    rollforward_rows = {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(rollforward.get("tickers"))
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }
    latest = as_dict(registry.get("latest_by_ticker"))
    findings = [item for item in as_list(metrics_validation.get("findings")) if isinstance(item, dict)]
    bridge_rows = {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(bridge.get("bridges"))
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }

    auto_retry_queue = [
        {
            "ticker": str(item.get("ticker") or "").upper(),
            "code": item.get("code"),
            "message": item.get("message"),
            "routing": "automatic_sec_lag_retry",
            "manual_escalation_required": False,
        }
        for item in findings
        if str(item.get("code") or "") in AUTO_RETRY_CODES
    ]
    manual_conflict_queue = [
        {
            "ticker": str(item.get("ticker") or "").upper(),
            "code": item.get("code"),
            "message": item.get("message"),
            "routing": "manual_conflict_or_period_review",
            "manual_escalation_required": True,
        }
        for item in findings
        if str(item.get("code") or "") in MANUAL_REPAIR_CODES
    ]

    tickers = sorted(set(latest) | set(rollforward_rows))
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        capture = as_dict(latest.get(ticker))
        ledger_row = as_dict(ledger_rows.get(ticker))
        attention = as_dict(attention_rows.get(ticker))
        rollforward_row = as_dict(rollforward_rows.get(ticker))
        bridge_row = as_dict(bridge_rows.get(ticker))
        tier = ledger_row.get("auto_tier") or attention.get("legacy_tier")
        source_verified, review_fresh, source_reason = source_grade_for(capture, rollforward_row)
        bridge_state = as_dict(as_dict(bridge_row.get("official_earnings_bridge")).get("source_freshness"))
        if bridge_state.get("freshness_status") == "source_verified_not_review_fresh":
            source_verified, review_fresh, source_reason = True, False, "source_verified_manual_reconciliation_pending"
        decision_fresh = bool(
            review_fresh
            and tier in {"Tier A", "Tier B"}
            and ledger_row.get("overall_freshness_state") == "fresh"
        )
        monitor_fresh = bool(tier == "Tier C" and ledger_row.get("overall_freshness_state") == "fresh")
        rows.append({
            "ticker": ticker,
            "tier": tier or "unclassified",
            "source_verified": source_verified,
            "review_fresh": review_fresh,
            "decision_fresh": decision_fresh,
            "monitor_fresh": monitor_fresh,
            "source_reason": source_reason,
            "official_period_end": capture.get("period_end") or rollforward_row.get("expected_period_end"),
            "capture_artifact": capture.get("capture_artifact"),
            "validation_artifact": capture.get("validation_artifact"),
            "capture_state": capture.get("current_state"),
            "rollforward_status": rollforward_row.get("status"),
            "ledger_freshness_state": ledger_row.get("overall_freshness_state"),
            "attention_triggered": attention.get("attention_triggered") is True,
            "repair_mode": repair_mode_for(ticker, tier, attention, findings),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "owner_approval_inferred": False,
        })

    counts = Counter()
    tier_counts: dict[str, Counter[str]] = {}
    for row in rows:
        for grade in ("source_verified", "review_fresh", "decision_fresh", "monitor_fresh"):
            if row[grade]:
                counts[grade] += 1
                tier_counts.setdefault(str(row["tier"]), Counter())[grade] += 1
        tier_counts.setdefault(str(row["tier"]), Counter())["tracked"] += 1
    pending = [row for row in rows if row["source_verified"] and not row["review_fresh"]]
    unresolved = [row for row in as_list(rollforward.get("tickers")) if isinstance(row, dict) and row.get("status") in {"catch_up_required", "parser_failed_or_manual_required", "discovery_error", "missing_current_capture"}]
    rows_by_ticker = {str(row.get("ticker") or "").upper(): row for row in rows}
    auto_resolved_items: list[dict[str, Any]] = []
    automatic_retry_items: list[dict[str, Any]] = []
    needs_source_review_items: list[dict[str, Any]] = []

    for guard_row in as_list(rollforward.get("tickers")):
        if not isinstance(guard_row, dict):
            continue
        ticker = str(guard_row.get("ticker") or "").upper()
        if not ticker:
            continue
        guard_status = str(guard_row.get("status") or "")
        period_end = guard_row.get("expected_period_end") or guard_row.get("current_period_end")
        source_artifact = guard_row.get("current_capture_artifact") or as_dict(guard_row.get("discovery")).get("source_url")
        if guard_status == "updated_review_only":
            _append_unique(auto_resolved_items, _queue_item(
                ticker=ticker,
                queue_status="auto_resolved",
                reason="newer_official_period_captured_review_only",
                period_end=period_end,
                as_of=reference_date,
                routing="downstream_review_only_rebuild",
                source_artifact=source_artifact,
                reason_code="updated_review_only",
            ))
        elif guard_status == "updated_source_verified_pending_reconciliation":
            _append_unique(needs_source_review_items, _queue_item(
                ticker=ticker,
                queue_status="needs_source_review",
                reason="source_verified_field_reconciliation_pending",
                period_end=period_end,
                as_of=reference_date,
                routing="source_open_field_reconciliation",
                source_artifact=source_artifact,
                reason_code="updated_source_verified_pending_reconciliation",
            ))
        elif guard_status in {"catch_up_required", "discovery_error"}:
            _append_unique(automatic_retry_items, _queue_item(
                ticker=ticker,
                queue_status="automatic_retry",
                reason=str(guard_row.get("reason") or guard_status),
                period_end=period_end,
                as_of=reference_date,
                routing="automatic_sec_lag_retry",
                source_artifact=source_artifact,
                reason_code=guard_status,
            ))
        elif guard_status in {"parser_failed_or_manual_required", "missing_current_capture", "source_monitoring_manual_required"}:
            _append_unique(needs_source_review_items, _queue_item(
                ticker=ticker,
                queue_status="needs_source_review",
                reason=str(guard_row.get("reason") or guard_status),
                period_end=period_end,
                as_of=reference_date,
                routing="source_open_repair",
                source_artifact=source_artifact,
                reason_code=guard_status,
            ))

    for row in pending:
        _append_unique(needs_source_review_items, _queue_item(
            ticker=str(row["ticker"]),
            queue_status="needs_source_review",
            reason=str(row.get("source_reason") or "source_verified_manual_reconciliation_pending"),
            period_end=row.get("official_period_end"),
            as_of=reference_date,
            routing=str(row.get("repair_mode") or "source_open_field_reconciliation"),
            source_artifact=row.get("capture_artifact"),
            reason_code=str(row.get("source_reason") or "source_verified_manual_reconciliation_pending"),
        ))

    for item in auto_retry_queue:
        ticker = str(item.get("ticker") or "").upper()
        row = rows_by_ticker.get(ticker, {})
        _append_unique(automatic_retry_items, _queue_item(
            ticker=ticker,
            queue_status="automatic_retry",
            reason=str(item.get("message") or item.get("code") or "sec_lag_wait"),
            period_end=row.get("official_period_end"),
            as_of=reference_date,
            routing="automatic_sec_lag_retry",
            source_artifact=row.get("capture_artifact"),
            reason_code=str(item.get("code") or "sec_lag_wait"),
        ))

    for item in manual_conflict_queue:
        ticker = str(item.get("ticker") or "").upper()
        row = rows_by_ticker.get(ticker, {})
        _append_unique(needs_source_review_items, _queue_item(
            ticker=ticker,
            queue_status="needs_source_review",
            reason=str(item.get("message") or item.get("code") or "manual_conflict_or_period_review"),
            period_end=row.get("official_period_end"),
            as_of=reference_date,
            routing="manual_conflict_or_period_review",
            source_artifact=row.get("capture_artifact"),
            reason_code=str(item.get("code") or "manual_conflict_or_period_review"),
        ))

    queue_age_rows = sorted(
        [*auto_resolved_items, *automatic_retry_items, *needs_source_review_items],
        key=lambda item: (str(item.get("queue_status")), str(item.get("ticker"))),
    )
    known_ages = [int(item["age_days"]) for item in queue_age_rows if item.get("age_days") is not None]
    exception_queue = {
        "as_of_date_utc": reference_date.isoformat(),
        "auto_resolved": sorted(auto_resolved_items, key=lambda item: str(item.get("ticker"))),
        "automatic_retry": sorted(automatic_retry_items, key=lambda item: str(item.get("ticker"))),
        "needs_source_review": sorted(needs_source_review_items, key=lambda item: str(item.get("ticker"))),
        "age": {
            "rows": queue_age_rows,
            "oldest_age_days": max(known_ages) if known_ages else None,
            "unknown_age_count": sum(1 for item in queue_age_rows if item.get("age_days") is None),
        },
        "counts": {
            "auto_resolved": len(auto_resolved_items),
            "automatic_retry": len(automatic_retry_items),
            "needs_source_review": len(needs_source_review_items),
        },
        "authority": {
            "review_only": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "owner_approval_inferred": False,
        },
    }

    validation_errors: list[str] = []
    if any(row["decision_fresh"] and not row["review_fresh"] for row in rows):
        validation_errors.append("decision_fresh cannot be true when review_fresh is false")
    if any(row["review_fresh"] and not row["source_verified"] for row in rows):
        validation_errors.append("review_fresh cannot be true when source_verified is false")
    status = "error" if validation_errors else "warning" if pending or unresolved or automatic_retry_items or needs_source_review_items else "ok"
    return {
        "schema": "veritas.finance_source_freshness_maturity.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Separate verified official sources from review-ready and decision-ready evidence without widening finance authority.",
        "authority": AUTHORITY,
        "contract": {
            "source_verified_not_equal_review_fresh": True,
            "review_fresh_not_equal_decision_fresh": True,
            "tier_a_target": "decision_fresh when source, evidence, and existing tier freshness gates are clean",
            "tier_b_target": "decision_fresh or an explicit blocker",
            "tier_c_target": "monitor_fresh; repair only when attention-triggered or promoted",
            "sec_lag_policy": "automatic SEC retry; manual escalation only for true conflict/period-review/foreign-issuer classes",
            "exception_queue": "Daily queue distinguishes completed source-gap repair, automatic retry, and source-review debt with an explicit period age; it never grants review, deployment, or execution authority.",
            "alerts_only_for": "unresolved capture, validation, transport, or true reconciliation failure—not ordinary source-verified manual field debt",
        },
        "source_artifacts": {
            "capture_registry": "tmp/wf70-official-capture-period-registry.json",
            "earnings_rollforward_guard": "tmp/earnings-rollforward-guard.json",
            "official_earnings_bridge": "tmp/official-earnings-bridge.json",
            "tier_freshness_ledger": "tmp/wf78-ticker-freshness-ledger.json",
            "tier_c_attention_trigger": "tmp/wf78-tier-c-attention-trigger.json",
            "fundamental_metrics_validation": "tmp/fundamental-metrics-validation.json",
        },
        "summary": {
            "tracked_official_capture_tickers": len(rows),
            "source_verified_count": counts["source_verified"],
            "review_fresh_count": counts["review_fresh"],
            "decision_fresh_count": counts["decision_fresh"],
            "monitor_fresh_count": counts["monitor_fresh"],
            "manual_reconciliation_pending_count": len(pending),
            "unresolved_capture_count": len(unresolved),
            "tier_counts": {tier: dict(counter) for tier, counter in sorted(tier_counts.items())},
            "tier_c_attention_triggered_count": sum(1 for row in attention_rows.values() if row.get("attention_triggered") is True),
            "no_bulk_tier_c_repair": True,
            "automatic_sec_lag_retry_count": len(auto_retry_queue),
            "manual_conflict_or_period_review_count": len(manual_conflict_queue),
            "exception_queue_auto_resolved_count": exception_queue["counts"]["auto_resolved"],
            "exception_queue_automatic_retry_count": exception_queue["counts"]["automatic_retry"],
            "exception_queue_needs_source_review_count": exception_queue["counts"]["needs_source_review"],
            "exception_queue_oldest_age_days": exception_queue["age"]["oldest_age_days"],
        },
        "rows": rows,
        "manual_reconciliation_pending": pending,
        "unresolved_capture_queue": unresolved,
        "exception_queue": exception_queue,
        "fundamental_repair_routing": {
            "automatic_sec_lag_retry_queue": auto_retry_queue,
            "manual_conflict_or_period_review_queue": manual_conflict_queue,
            "contract": "SEC lag is retryable automatically in the normal bounded refresh loop; only true conflict/period-review/foreign-issuer classes require manual escalation.",
        },
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [
                f"{len(pending)} source-verified capture(s) remain intentionally review-fresh=false pending field reconciliation"
            ] if pending else [],
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-only finance source freshness maturity scorecard.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        write_json(output, payload)
    print(json.dumps({"status": payload["status"], "output": str(output.relative_to(ROOT)), "summary": payload["summary"], "validation": payload["validation"]}, indent=2, sort_keys=True))
    return 0 if not args.validate or payload["validation"]["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
