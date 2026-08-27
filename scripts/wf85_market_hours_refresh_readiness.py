#!/usr/bin/env python3
"""Review-only WF85 market-hours refresh readiness precheck.

This precheck reads existing WF85/WF84 proof artifacts and decides whether a
future market-hours refresh would be safe and useful. It never refreshes market
data, cards, full answers, owner cards, order cards, or paper/live artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finance_sql_canon_access import DEFAULT_DB as SQL_CANON_DB, strategic_answer_route_context
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf85-market-hours-refresh-readiness.json"
DEFAULT_LANE_OUT = TMP / "wf85-market-hours-readiness-2522.json"
SCHEMA = "veritas.wf85_market_hours_refresh_readiness.v1"
AZ = ZoneInfo("America/Phoenix")

AUTHORITY_FLAGS = {
    "review_only": True,
    "creates_owner_cards": False,
    "creates_approval_cards": False,
    "creates_order_cards": False,
    "refreshes_cards_or_full_answers": False,
    "fetches_market_data": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = [key for key, value in AUTHORITY_FLAGS.items() if value is False]

ARTIFACTS = {
    "decision_cards": TMP / "trade-grade-decision-cards.json",
    "source_freshness_gate": TMP / "trade-grade-source-freshness-gate.json",
    "authority_validation": TMP / "trade-grade-decision-card-authority-validation.json",
    "approval_gate": TMP / "trade-grade-approval-card-gate.json",
    "readiness_rollup": TMP / "trade-grade-os-readiness-rollup.json",
    "repair_conveyor": TMP / "trade-grade-repair-conveyor.json",
    "parallel_answer_os_pass": TMP / "wf85-parallel-answer-os-pass-2505.json",
}

BLOCKED_STATUSES = {"blocked", "error", "failed", "critical"}
OK_STATUS_VALUES = {"ok", "ready_for_repair_execution", None}
MARKET_OPEN_AZ = time(6, 30)
MARKET_CLOSE_AZ = time(13, 0)
STALE_HOURS = 6.0
LEGACY_PRODUCTION_COMPATIBILITY_COUNT = 42


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    parsed = parse_utc(value)
    if parsed is None:
        raise ValueError(f"invalid --now-utc timestamp: {value}")
    return parsed.replace(microsecond=0)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def finance_sql_canon_context() -> dict[str, Any]:
    return strategic_answer_route_context(consumer="wf85_market_hours_refresh_readiness", db_path=SQL_CANON_DB)


def validation_status(payload: dict[str, Any]) -> str | None:
    validation = as_dict(payload.get("validation"))
    status = validation.get("status")
    return str(status).lower() if status is not None else None


def artifact_status(payload: dict[str, Any]) -> str | None:
    status = payload.get("status")
    return str(status).lower() if status is not None else None


def generated_at(payload: dict[str, Any]) -> str | None:
    value = payload.get("generated_at_utc") or payload.get("generated_at")
    return str(value) if value else None


def age_hours(payload: dict[str, Any], now: datetime) -> float | None:
    dt = parse_utc(generated_at(payload))
    if dt is None:
        return None
    return round(max(0.0, (now - dt).total_seconds() / 3600.0), 3)


def market_session(now: datetime) -> dict[str, Any]:
    local = now.astimezone(AZ)
    is_weekday = local.weekday() < 5
    is_regular = is_weekday and MARKET_OPEN_AZ <= local.time() < MARKET_CLOSE_AZ
    if is_regular:
        state = "REGULAR_MARKET_HOURS"
    elif is_weekday and local.time() < MARKET_OPEN_AZ:
        state = "PRE_MARKET_WAIT"
    elif is_weekday:
        state = "AFTER_MARKET_WAIT"
    else:
        state = "WEEKEND_WAIT"
    return {
        "timezone": "America/Phoenix",
        "now_utc": now.isoformat().replace("+00:00", "Z"),
        "now_local": local.isoformat(),
        "regular_market_hours": is_regular,
        "state": state,
        "assumption": "US regular equity market window approximated as 06:30-13:00 America/Phoenix on weekdays; holidays are not fetched.",
    }


def contains_forbidden_true(value: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}" if path else str(key)
            if key in FALSE_AUTHORITY_KEYS and item is True:
                hits.append(item_path)
            hits.extend(contains_forbidden_true(item, item_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            hits.extend(contains_forbidden_true(item, f"{path}[{idx}]"))
    return hits


def artifact_record(name: str, path: Path, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": artifact_status(payload) or ("missing" if not path.exists() else None),
        "validation_status": validation_status(payload),
        "generated_at_utc": generated_at(payload),
        "age_hours": age_hours(payload, now),
        "forbidden_true_authority_paths": contains_forbidden_true(payload)[:25],
    }


def count_cards(cards_payload: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(cards_payload.get("summary"))
    counts = as_dict(summary.get("decision_state_counts"))
    cards = as_list(cards_payload.get("cards"))
    stale_quote_context = [
        str(card.get("ticker") or "")
        for card in cards
        if as_dict(card).get("decision_state") == "review_ready"
        and as_dict(as_dict(card).get("source_freshness")).get("quote_freshness_status")
        not in {"fresh", "ok", "intraday_fresh"}
    ]
    return {
        "card_count": summary.get("card_count") or len(cards),
        "decision_state_counts": counts,
        "review_ready_count": int_or_zero(counts.get("review_ready")),
        "blocked_missing_freshness_count": int_or_zero(counts.get("blocked_missing_freshness")),
        "approval_card_draft_count": int_or_zero(summary.get("approval_card_draft_count")),
        "review_ready_with_non_execution_quote_context": [ticker for ticker in stale_quote_context if ticker],
    }


def source_trust_summary(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cards = count_cards(artifacts["decision_cards"])
    source_summary = as_dict(artifacts["source_freshness_gate"].get("summary"))
    authority_summary = as_dict(artifacts["authority_validation"].get("summary"))
    approval_summary = as_dict(artifacts["approval_gate"].get("summary"))
    conveyor_summary = as_dict(artifacts["repair_conveyor"].get("summary"))
    readiness = artifacts["readiness_rollup"]
    readiness_wf85 = as_dict(readiness.get("wf85_decision_os"))
    parallel_status = as_dict(artifacts["parallel_answer_os_pass"].get("current_wf85_status"))
    return {
        **cards,
        "source_open_status_counts": source_summary.get("source_open_status_counts")
        or parallel_status.get("source_open_status_counts"),
        "freshness_status_counts": source_summary.get("freshness_status_counts")
        or parallel_status.get("freshness_status_counts"),
        "authority_violation_count": int_or_zero(
            authority_summary.get("false_authority_violation_count")
            or parallel_status.get("authority_scan_false_authority_violation_count")
        ),
        "forbidden_action_phrase_count": int_or_zero(
            authority_summary.get("forbidden_action_phrase_count")
            or parallel_status.get("authority_scan_forbidden_action_phrase_count")
        ),
        "approval_gate_review_ready_count": int_or_zero(approval_summary.get("review_ready_count")),
        "approval_gate_draft_count": int_or_zero(approval_summary.get("approval_card_draft_count")),
        "approval_gate_blocked_count": int_or_zero(approval_summary.get("approval_draft_blocked_count")),
        "wf67_paper_guard_fresh": approval_summary.get("wf67_paper_guard_fresh"),
        "wf67_paper_guard_clean": approval_summary.get("wf67_paper_guard_clean"),
        "readiness_rollup_answer_ready_count": readiness_wf85.get("answer_ready_count"),
        "readiness_rollup_review_only_decision_ready_count": readiness_wf85.get("review_only_decision_ready_count"),
        "repair_conveyor_implementation_blocker_count": int_or_zero(
            conveyor_summary.get("implementation_blocker_count")
        ),
        "repair_conveyor_control_plane_blocker_count": int_or_zero(
            conveyor_summary.get("control_plane_blocker_count")
        ),
    }


def classify(
    records: list[dict[str, Any]],
    trust: dict[str, Any],
    session: dict[str, Any],
    finance_sql_canon: dict[str, Any],
    now: datetime,
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    reasons: list[str] = []
    if finance_sql_canon.get("status") != "ok":
        blockers.append("finance_sql_canon_guard_blocked")
    for record in records:
        if not record["exists"] or not record["parseable_json"]:
            blockers.append(f"artifact_missing_or_unparseable:{record['name']}")
        if record["status"] in BLOCKED_STATUSES:
            blockers.append(f"artifact_status_blocked:{record['name']}:{record['status']}")
        if record["validation_status"] in BLOCKED_STATUSES:
            blockers.append(f"artifact_validation_blocked:{record['name']}:{record['validation_status']}")
        if record["forbidden_true_authority_paths"]:
            blockers.append(f"authority_widened:{record['name']}")

    if trust["authority_violation_count"]:
        blockers.append("wf85_authority_violation_count_nonzero")
    if trust["forbidden_action_phrase_count"]:
        blockers.append("wf85_forbidden_action_phrase_count_nonzero")
    if trust["approval_gate_draft_count"]:
        blockers.append("approval_card_drafts_already_present_not_a_precheck_lane")
    if trust["repair_conveyor_implementation_blocker_count"]:
        blockers.append("repair_conveyor_implementation_blockers_present")
    if trust["repair_conveyor_control_plane_blocker_count"]:
        blockers.append("repair_conveyor_control_plane_blockers_present")

    if blockers:
        return "BLOCKED_FOR_SOURCE_TRUST/BOUNDARY", blockers, reasons

    card_record = next((record for record in records if record["name"] == "decision_cards"), {})
    cards_stale = card_record.get("age_hours") is None or float(card_record.get("age_hours") or 0) >= STALE_HOURS
    stale_or_market_needed = (
        cards_stale
        or trust["blocked_missing_freshness_count"] > 0
        or bool(trust["review_ready_with_non_execution_quote_context"])
    )
    if cards_stale:
        reasons.append(f"decision_cards_age_hours_at_or_above_{STALE_HOURS:g}")
    if trust["blocked_missing_freshness_count"] > 0:
        reasons.append("cards_include_blocked_missing_freshness_rows")
    if trust["review_ready_with_non_execution_quote_context"]:
        reasons.append("review_ready_rows_need_execution_fresh_market_hours_quote_context")

    if not session["regular_market_hours"]:
        return "WAIT_FOR_MARKET_HOURS", [str(session["state"])], reasons
    if stale_or_market_needed:
        return "READY", [], reasons
    return "WAIT_FOR_MARKET_HOURS", ["existing_artifacts_clean_and_not_stale_enough_to_refresh"], reasons


def next_safe_commands(classification: str) -> list[str]:
    base = [
        "python scripts\\trade_grade_os_freshness_cron_runner.py --component daily_core --full-answer-mode changed --write --validate",
        "python scripts\\trade_grade_repair_conveyor.py --write --validate",
        "python scripts\\trade_grade_os_readiness_rollup.py --write --validate",
    ]
    if classification == "READY":
        return base + [
            "Inspect GOOG/VRT review-ready waiting-approval-gate rows manually before any owner-review packet; do not infer approval.",
            "If WF67 context is needed, refresh only approved GET-only guard/readiness surfaces; no submit/cancel/sell/replace.",
        ]
    if classification == "WAIT_FOR_MARKET_HOURS":
        return [
            "Wait for regular market hours, then run the existing WF85 review-only refresh chain if still needed.",
            *base,
        ]
    return [
        "Do not run a market-hours refresh until source-trust or boundary blockers are inspected.",
        "Inspect this packet's blockers and the listed source artifacts first.",
    ]


def build_payload(now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    artifacts = {name: load(path) for name, path in ARTIFACTS.items()}
    records = [artifact_record(name, path, artifacts[name], now) for name, path in ARTIFACTS.items()]
    trust = source_trust_summary(artifacts)
    session = market_session(now)
    finance_sql_canon = finance_sql_canon_context()
    classification, blockers, reasons = classify(records, trust, session, finance_sql_canon, now)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if classification.startswith("BLOCKED") else "ok",
        "classification": classification,
        "purpose": "Review-only precheck for whether a future WF85 market-hours refresh is safe/useful.",
        "authority_flags": AUTHORITY_FLAGS,
        "market_session": session,
        "source_trust_summary": trust,
        "finance_sql_canon_context": finance_sql_canon,
        "blockers": blockers,
        "refresh_usefulness_reasons": reasons,
        "next_safe_command_suggestions_text_only": next_safe_commands(classification),
        "artifact_records": records,
        "source_artifacts": {name: rel(path) for name, path in ARTIFACTS.items()},
        "stop_lines": [
            "This script does not fetch market data or refresh WF85 cards/full answers.",
            "This script does not create owner cards, approval cards, paper requests, or order artifacts.",
            "No generated card, score, SQL row, packet, or readiness classification is owner approval.",
            "No paper/live execution, brokerage/account action, money movement, canon/portfolio/cash/sizing/risk-rule mutation, customer delivery, or owner approval inference.",
        ],
    }
    validation = validate_payload(payload)
    payload["validation"] = validation
    if validation["errors"]:
        payload["status"] = "blocked"
        payload["classification"] = "BLOCKED_FOR_SOURCE_TRUST/BOUNDARY"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    flags = as_dict(payload.get("authority_flags"))
    for key, expected in AUTHORITY_FLAGS.items():
        if flags.get(key) is not expected:
            errors.append(f"authority_flag_{key}_not_{str(expected).lower()}")
    classification = payload.get("classification")
    if classification not in {"READY", "WAIT_FOR_MARKET_HOURS", "BLOCKED_FOR_SOURCE_TRUST/BOUNDARY"}:
        errors.append(f"invalid_classification:{classification}")
    if classification == "READY" and not as_dict(payload.get("market_session")).get("regular_market_hours"):
        errors.append("ready_outside_regular_market_hours")
    if classification == "READY" and as_list(payload.get("blockers")):
        errors.append("ready_with_blockers")
    if flags.get("creates_owner_cards") is not False:
        errors.append("creates_owner_cards_not_false")
    if flags.get("paper_or_live_execution_allowed") is not False:
        errors.append("paper_or_live_execution_allowed_not_false")
    if flags.get("owner_approval_inferred") is not False:
        errors.append("owner_approval_inferred_not_false")
    if not as_list(payload.get("next_safe_command_suggestions_text_only")):
        errors.append("missing_next_safe_command_suggestions")
    if classification == "WAIT_FOR_MARKET_HOURS" and as_dict(payload.get("market_session")).get("regular_market_hours"):
        warnings.append("wait_classification_during_market_hours_existing_artifacts_not_stale_enough")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "critical_count": len(errors),
        "warning_count": len(warnings),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 market-hours refresh readiness precheck.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--now-utc", help="Deterministic UTC timestamp for tests, e.g. 2026-06-15T14:00:00Z.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--lane-out", type=Path, default=DEFAULT_LANE_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        now = parse_now(args.now_utc)
    except ValueError as exc:
        print(str(exc))
        return 2
    payload = build_payload(now)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        lane_out = args.lane_out if args.lane_out.is_absolute() else ROOT / args.lane_out
        atomic_write_json(out, payload)
        atomic_write_json(lane_out, payload)
    if args.pretty and not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "classification={classification} status={status} validation={validation} "
            "market_state={market_state} blockers={blockers} reasons={reasons}".format(
                classification=payload.get("classification"),
                status=payload.get("status"),
                validation=as_dict(payload.get("validation")).get("status"),
                market_state=as_dict(payload.get("market_session")).get("state"),
                blockers=len(as_list(payload.get("blockers"))),
                reasons=len(as_list(payload.get("refresh_usefulness_reasons"))),
            )
        )
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
