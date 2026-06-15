#!/usr/bin/env python3
"""WF68 immediate-vs-digest delivery router.

Consumes the advisor alert packet and creates a narrow immediate execution
recommendation surface for Randall's preferred alert policy:

- Immediate main-session alert only when a ticker is in the written entry band
  and can be packaged with explicit paper-order recommendation terms.
- All stop/no-chase/monitor/stale/not-ready items are grouped into a digest
  artifact and should not interrupt the user unless requested or scheduled.

This script writes recommendation artifacts only. It does not submit/cancel
orders, create a kill switch, call Alpaca, mutate cron/channel/config state,
change canonical notes/portfolio state, or infer owner approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_ADVISOR_PACKET = OUT_DIR / "advisor-alert-packet.json"
DEFAULT_OUTPUT_JSON = OUT_DIR / "delivery-router-status.json"
DEFAULT_OUTPUT_MD = OUT_DIR / "delivery-router-status.md"
DEFAULT_EXECUTION_DIR = OUT_DIR / "execution-recommendations"
DEFAULT_WF67_GUARD = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
DEFAULT_WF67_REQUEST_DIR = ROOT / "tmp" / "alpaca-paper-readiness"
REQUEST_MAX_AGE_MINUTES = 90.0

AUTHORITY = {
    "posture": "owner_review_packet_only_until_wf67_execution_gate_clean",
    "live_trade_or_account_action_allowed": False,
    "paper_trade_execution_allowed_by_this_script": False,
    "paper_or_live_order_submission_allowed": False,
    "paper_or_live_order_cancellation_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "cron_channel_config_mutation_allowed": False,
    "owner_approval_inferred": False,
}

BOUNDARY = (
    "Owner-review packet only unless WF67 guard, fresh kill switch, and exact scoped request proof "
    "are all clean. This script never submits paper/live orders, mutates accounts, moves money, "
    "or infers owner approval."
)
APPROVAL_BOUNDARY = (
    "Execution-ready paper packet only after clean WF67 guard, fresh kill switch, and exact scoped "
    "request proof. Reply APPROVE may authorize only the exact paper-only WF67 request described in "
    "this packet; live trades/accounts/money movement remain blocked."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json(path)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def authority_clean(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, bool) and child is True:
                lowered = str(key).lower()
                if any(token in lowered for token in [
                    "trade", "order", "cancel", "account", "broker", "money", "portfolio",
                    "canonical", "approval", "mutation", "config", "channel", "cron", "execution",
                ]):
                    # Allow positive descriptive fields only if they are explicitly not authority flags.
                    if "required" not in lowered and "reviewed" not in lowered:
                        return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def request_age_minutes(request: dict[str, Any]) -> float | None:
    created = parse_utc(request.get("created_at_utc") or request.get("generated_at_utc"))
    if created is None:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 60.0), 2)


def latest_scoped_request(symbol: str, request_dir: Path, max_age_minutes: float = REQUEST_MAX_AGE_MINUTES) -> dict[str, Any] | None:
    symbol = symbol.upper()
    candidates: list[tuple[datetime, Path, dict[str, Any]]] = []
    for path in request_dir.glob("paper-trade-request*.json"):
        payload = load_json_if_exists(path)
        if not isinstance(payload, dict):
            continue
        order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
        if str(order.get("symbol") or "").upper() != symbol:
            continue
        if payload.get("artifact_type") != "wf67_paper_trade_request":
            continue
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        if source.get("scoped_paper_trade_or_pilot") is not True:
            continue
        age = request_age_minutes(payload)
        if age is None or age > max_age_minutes:
            continue
        created = parse_utc(payload.get("created_at_utc") or payload.get("generated_at_utc"))
        if created is None:
            continue
        candidates.append((created, path, payload))
    if not candidates:
        return None
    created, path, payload = max(candidates, key=lambda item: item[0])
    return {
        "path": rel(path),
        "created_at_utc": created.isoformat().replace("+00:00", "Z"),
        "age_minutes": request_age_minutes(payload),
        "request_id": payload.get("request_id"),
        "exact_order_owner_approval_status": as_dict(payload.get("execution_readiness")).get("exact_order_owner_approval_status"),
        "currently_executable": as_dict(payload.get("execution_readiness")).get("currently_executable"),
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def wf67_execution_gate_blockers(symbol: str, guard_path: Path, request_dir: Path) -> tuple[list[str], dict[str, Any]]:
    guard = load_json_if_exists(guard_path)
    request = latest_scoped_request(symbol, request_dir)
    blockers: list[str] = []
    context: dict[str, Any] = {
        "guard_path": rel(guard_path),
        "request_dir": rel(request_dir),
        "latest_scoped_request": request,
    }

    if not isinstance(guard, dict):
        blockers.append("wf67_guard_missing")
        context["guard_status"] = None
        context["guard_ready_for_paper_submit_cancel"] = False
    else:
        context["guard_generated_at_utc"] = guard.get("generated_at_utc")
        context["guard_status"] = guard.get("status")
        context["guard_ready_for_paper_submit_cancel"] = guard.get("ready_for_paper_submit_cancel") is True
        critical_findings = [
            as_dict(item).get("code") or "critical_finding"
            for item in guard.get("findings", [])
            if isinstance(item, dict) and item.get("severity") == "critical"
        ]
        context["guard_critical_findings"] = critical_findings
        if guard.get("status") != "ok":
            blockers.append(f"wf67_guard_not_ok:{guard.get('status')}")
        if guard.get("ready_for_paper_submit_cancel") is not True:
            blockers.append("wf67_guard_not_ready_for_submit_cancel")
        for finding in critical_findings:
            if finding == "kill_switch_missing_or_expired":
                blockers.append("fresh_short_lived_kill_switch_missing_or_expired")
            else:
                blockers.append(f"wf67_guard_critical:{finding}")

    if request is None:
        blockers.append("exact_scoped_wf67_request_artifact_missing_or_stale")
    return blockers, context


def readiness_blockers(alert: dict[str, Any]) -> list[str]:
    d = alert.get("advisor_decision_packet") if isinstance(alert.get("advisor_decision_packet"), dict) else {}
    entry = d.get("entry_context") if isinstance(d.get("entry_context"), dict) else {}
    source = d.get("source_freshness") if isinstance(d.get("source_freshness"), dict) else {}
    adequacy = d.get("official_evidence_adequacy") if isinstance(d.get("official_evidence_adequacy"), dict) else {}
    route = d.get("wf67_paper_package_route") if isinstance(d.get("wf67_paper_package_route"), dict) else {}
    recommendation = d.get("recommendation_context") if isinstance(d.get("recommendation_context"), dict) else {}
    observed = as_float(entry.get("observed_price"))
    low = as_float(entry.get("entry_band_low"))
    high = as_float(entry.get("entry_band_high"))
    blockers: list[str] = []
    if alert.get("event_type") != "price_enters_band":
        blockers.append("not_a_price_enters_band_trigger")
    if entry.get("observed_entry_status") != "IN_BAND":
        blockers.append(f"entry_status_not_in_band:{entry.get('observed_entry_status')}")
    if source.get("alert_freshness_status") != "fresh":
        blockers.append(f"alert_quote_not_fresh:{source.get('alert_freshness_status')}")
    if adequacy.get("sufficient_for_paper_execution_recommendation") is not True:
        decision = adequacy.get("decision") or "missing_official_evidence_adequacy"
        blockers.append(f"official_evidence_not_sufficient:{decision}")
        for blocker in adequacy.get("blockers") or []:
            blockers.append(f"official_evidence_blocker:{blocker}")
    if observed is None or low is None or high is None:
        blockers.append("missing_price_or_entry_band")
    elif not (low <= observed <= high):
        blockers.append("observed_price_outside_entry_band")
    if route.get("status") != "allowed_under_wf67_guardrails":
        blockers.append("missing_clean_wf67_paper_package_route")
    blockers.extend(recommendation_context_blockers(recommendation))
    if not authority_clean(alert.get("authority", {})):
        blockers.append("authority_flags_not_clean")
    return blockers


def recommendation_context_blockers(recommendation: dict[str, Any]) -> list[str]:
    """Block immediate paper packets when portfolio/deployment posture is not affirmative.

    WF68 quote alerts are allowed to say "price entered the written band", but
    paper-ready delivery must also respect the capital/deployment layer. This
    prevents repair/watch/missing-recommendation names from being promoted only
    because their price moved back into a numeric band.
    """
    blockers: list[str] = []
    status = str(recommendation.get("status") or "").lower()
    posture = str(recommendation.get("recommendation_posture") or "").lower()
    action = str(recommendation.get("recommended_action") or "").lower()
    current = recommendation.get("current_state") if isinstance(recommendation.get("current_state"), dict) else {}
    current_text = " ".join(
        str(current.get(key) or "")
        for key in ("daily_review_state", "deployment_state", "band_status", "proposal_band_status", "raw_band_status")
    ).lower()

    if status != "available_review_only":
        blockers.append(f"capital_recommendation_not_available:{status or 'missing'}")

    blocked_posture_tokens = (
        "wait",
        "repair",
        "risk_review",
        "manual_review_required",
        "monitor",
        "watch",
        "missing",
    )
    if any(token in posture for token in blocked_posture_tokens):
        blockers.append(f"recommendation_posture_not_execution_ready:{posture}")
    if any(token in action for token in ("wait", "repair", "monitor", "watch", "grouped_digest", "stop_breach")):
        blockers.append(f"recommended_action_not_execution_ready:{action}")
    if any(token in current_text for token in ("do not touch", "repair", "bench", "below_stop", "below stop")):
        blockers.append("deployment_state_blocks_execution_ready_packet")
    return blockers


def order_terms(alert: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    d = alert.get("advisor_decision_packet") if isinstance(alert.get("advisor_decision_packet"), dict) else {}
    entry = d.get("entry_context") if isinstance(d.get("entry_context"), dict) else {}
    stop = d.get("stop_context") if isinstance(d.get("stop_context"), dict) else {}
    observed = as_float(entry.get("observed_price"))
    high = as_float(entry.get("entry_band_high"))
    symbol = str(alert.get("ticker", "")).upper()
    blockers: list[str] = []
    if observed is None:
        blockers.append("missing_observed_price_for_limit")
        limit_price = None
    else:
        limit_price = round(observed, 2)
    if high is not None and limit_price is not None and limit_price > high:
        blockers.append("limit_price_above_entry_band_high")
    qty = 1.0
    estimated = round(qty * limit_price, 2) if limit_price is not None else None
    if estimated is None or estimated > 500:
        blockers.append("estimated_notional_exceeds_default_wf67_pilot_cap")
    terms = {
        "symbol": symbol,
        "side": "buy",
        "order_type": "limit",
        "time_in_force": "day",
        "qty": qty,
        "limit_price": limit_price,
        "estimated_notional_usd": estimated,
        "max_notional_usd": 500.0,
        "max_loss_usd": estimated,
        "entry_band_low": entry.get("entry_band_low"),
        "entry_band_high": entry.get("entry_band_high"),
        "observed_price": observed,
        "stop_reference": stop.get("stop"),
        "approval_word": "APPROVE",
        "decline_word": "DECLINE",
    }
    return terms, blockers


def build_execution_packet(alert: dict[str, Any], source_path: Path, generated_at: str, gate_context: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    d = alert.get("advisor_decision_packet") if isinstance(alert.get("advisor_decision_packet"), dict) else {}
    terms, term_blockers = order_terms(alert)
    packet_id = f"wf68-exec-{str(alert.get('ticker', 'unknown')).upper()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    packet = {
        "schema_version": "wf68.execution_recommendation_packet.v1",
        "workflow": "WF68",
        "packet_id": packet_id,
        "generated_at_utc": generated_at,
        "ticker": alert.get("ticker"),
        "status": "PAPER_EXECUTION_RECOMMENDATION_READY" if not term_blockers else "BLOCKED",
        "recommendation": "paper_test_buy_limit_day",
        "one_word_approval_contract": {
            "approval_word": "APPROVE",
            "meaning": "Approve exactly the paper-only WF67 request terms in this packet; live execution remains blocked.",
            "non_approval_words": ["DECLINE", "WAIT", "CHANGE"],
        },
        "recommended_order_terms": terms,
        "rationale": {
            "trigger": alert.get("event_type"),
            "entry_logic": d.get("entry_logic"),
            "thesis": d.get("thesis"),
            "recommendation_context": d.get("recommendation_context"),
            "source_freshness": d.get("source_freshness"),
            "official_evidence_adequacy": d.get("official_evidence_adequacy"),
            "concentration_risk_note": d.get("concentration_risk_note"),
            "invalidation": d.get("invalidation"),
        },
        "source": {
            "advisor_packet_path": rel(source_path),
            "source_alert_packet_path": alert.get("source_alert_packet_path"),
            "source_handoff_path": alert.get("source_handoff_path"),
        },
        "wf67_next_step": {
            "generate_request_after_approval": True,
            "generator": "scripts/wf67_advisor_paper_request_generator.py",
            "required_after_request": [
                "dry_run",
                "clean_wf67_guard_validation",
                "fresh_short_lived_kill_switch",
                "execute_through_wf67_wrapper_only",
                "redacted_audit_log",
                "main_session_capital_package_notification",
            ],
        },
        "wf67_execution_gate": gate_context or {},
        "blockers": term_blockers,
        "authority": AUTHORITY,
        "boundary": APPROVAL_BOUNDARY,
    }
    return packet, term_blockers


def build_blocked_execution_packet(alert: dict[str, Any], source_path: Path, generated_at: str, blockers: list[str]) -> dict[str, Any]:
    packet, term_blockers = build_execution_packet(alert, source_path, generated_at)
    packet["status"] = "BLOCKED"
    packet["recommendation"] = "blocked_in_band_not_execution_ready"
    packet["recommended_order_terms"]["approval_word"] = None
    packet["recommended_order_terms"]["decline_word"] = None
    packet["one_word_approval_contract"] = {
        "approval_word": None,
        "meaning": "No approval word is active while this packet is BLOCKED.",
        "non_approval_words": ["APPROVE", "DECLINE", "WAIT", "CHANGE"],
    }
    packet["blockers"] = [*blockers, *term_blockers]
    packet["wf67_next_step"] = {
        "generate_request_after_approval": False,
        "blocked_reason": "WF68 alert is in the written band, but portfolio/deployment recommendation context is not execution-ready.",
        "required_before_request": [
            "capital/deployment recommendation layer must be available",
            "ticker must not be repair/do-not-touch/watch-only/missing recommendation",
            "fresh WF68 quote must still be in band",
        ],
    }
    packet["boundary"] = (
        "Blocked recommendation packet only. It does not authorize WF67 request generation, "
        "paper/live order submission, account action, money movement, portfolio/canon mutation, "
        "or owner approval inference."
    )
    return packet


def build_owner_review_packet(alert: dict[str, Any], source_path: Path, generated_at: str, blockers: list[str], gate_context: dict[str, Any]) -> dict[str, Any]:
    packet, term_blockers = build_execution_packet(alert, source_path, generated_at, gate_context)
    packet["status"] = "OWNER_REVIEW_PACKET_READY"
    packet["recommendation"] = "owner_review_only_not_execution_ready"
    packet["recommended_order_terms"]["approval_word"] = None
    packet["recommended_order_terms"]["decline_word"] = None
    packet["one_word_approval_contract"] = {
        "approval_word": None,
        "meaning": "No one-word approval is active until WF67 guard, fresh kill switch, and exact scoped request proof are clean.",
        "non_approval_words": ["APPROVE", "DECLINE", "WAIT", "CHANGE"],
    }
    packet["blockers"] = [*blockers, *term_blockers]
    packet["wf67_next_step"] = {
        "generate_request_after_approval": False,
        "blocked_reason": "WF68 found an in-band review opportunity, but execution gates are not clean.",
        "required_before_approve_language": [
            "clean WF67 guard validation",
            "fresh short-lived kill switch",
            "exact scoped WF67 request artifact",
            "exact Randall approval after those gates are clean",
        ],
    }
    packet["boundary"] = BOUNDARY
    return packet


def write_execution_md(path: Path, packet: dict[str, Any]) -> None:
    terms = packet["recommended_order_terms"]
    lines = [
        f"# WF68 Execution Recommendation - {packet.get('ticker')}",
        "",
        f"- Generated UTC: {packet['generated_at_utc']}",
        f"- Status: **{packet['status']}**",
        f"- Recommendation: **{packet['recommendation']}**",
        f"- Exact approval word: **{packet['one_word_approval_contract']['approval_word'] or 'none - blocked'}**",
        "",
        "## Recommended paper order terms",
        "",
        f"- Symbol: `{terms['symbol']}`",
        f"- Side: `{terms['side']}`",
        f"- Type/TIF: `{terms['order_type']}` / `{terms['time_in_force']}`",
        f"- Qty: `{terms['qty']}`",
        f"- Limit price: `{terms['limit_price']}`",
        f"- Estimated notional: `${terms['estimated_notional_usd']}`",
        f"- Entry band: `{terms['entry_band_low']}`–`{terms['entry_band_high']}`",
        f"- Stop/reference: `{terms['stop_reference']}`",
        "",
        "## Boundary",
        "",
        packet.get("boundary") or BOUNDARY,
    ]
    if packet.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend([f"- `{b}`" for b in packet["blockers"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_router(
    advisor_path: Path,
    execution_dir: Path,
    guard_path: Path = DEFAULT_WF67_GUARD,
    request_dir: Path = DEFAULT_WF67_REQUEST_DIR,
) -> dict[str, Any]:
    generated_at = utc_now()
    packet = load_json(advisor_path)
    alerts = packet.get("alerts") if isinstance(packet.get("alerts"), list) else []
    immediate: list[dict[str, Any]] = []
    owner_review: list[dict[str, Any]] = []
    grouped: list[dict[str, Any]] = []
    blocked_in_band: list[dict[str, Any]] = []
    execution_paths: list[str] = []

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        blockers = readiness_blockers(alert)
        if not blockers:
            symbol = str(alert.get("ticker") or "").upper()
            gate_blockers, gate_context = wf67_execution_gate_blockers(symbol, guard_path, request_dir)
            exec_packet, term_blockers = build_execution_packet(alert, advisor_path, generated_at, gate_context)
            if term_blockers:
                blocked_in_band.append({"ticker": alert.get("ticker"), "event_type": alert.get("event_type"), "blockers": term_blockers})
                grouped.append({"ticker": alert.get("ticker"), "bucket": "in_band_blocked", "blockers": term_blockers})
                continue
            if gate_blockers:
                review_packet = build_owner_review_packet(alert, advisor_path, generated_at, gate_blockers, gate_context)
                json_path = execution_dir / f"execution-recommendation.{slug(str(alert.get('ticker')))}.json"
                md_path = execution_dir / f"execution-recommendation.{slug(str(alert.get('ticker')))}.md"
                write_json(json_path, review_packet)
                write_execution_md(md_path, review_packet)
                owner_review.append({
                    "ticker": alert.get("ticker"),
                    "status": review_packet["status"],
                    "approval_word": None,
                    "blockers": [*gate_blockers, *term_blockers],
                    "recommended_order_terms": review_packet["recommended_order_terms"],
                    "packet_json": rel(json_path),
                    "packet_md": rel(md_path),
                    "wf67_execution_gate": gate_context,
                })
                execution_paths.append(rel(json_path))
                continue
            json_path = execution_dir / f"execution-recommendation.{slug(str(alert.get('ticker')))}.json"
            md_path = execution_dir / f"execution-recommendation.{slug(str(alert.get('ticker')))}.md"
            write_json(json_path, exec_packet)
            write_execution_md(md_path, exec_packet)
            immediate.append({
                "ticker": alert.get("ticker"),
                "status": exec_packet["status"],
                "approval_word": "APPROVE",
                "recommended_order_terms": exec_packet["recommended_order_terms"],
                "packet_json": rel(json_path),
                "packet_md": rel(md_path),
            })
            execution_paths.append(rel(json_path))
        else:
            bucket = "grouped_digest"
            if alert.get("event_type") == "price_enters_band":
                bucket = "in_band_not_execution_ready"
                blocked_in_band.append({"ticker": alert.get("ticker"), "event_type": alert.get("event_type"), "blockers": blockers})
                blocked_packet = build_blocked_execution_packet(alert, advisor_path, generated_at, blockers)
                json_path = execution_dir / f"execution-recommendation.{slug(str(alert.get('ticker')))}.json"
                md_path = execution_dir / f"execution-recommendation.{slug(str(alert.get('ticker')))}.md"
                write_json(json_path, blocked_packet)
                write_execution_md(md_path, blocked_packet)
            grouped.append({
                "ticker": alert.get("ticker"),
                "event_type": alert.get("event_type"),
                "severity": alert.get("severity"),
                "bucket": bucket,
                "blockers": blockers,
            })

    status = "EXECUTION_PACKET_READY" if immediate else "OWNER_REVIEW_PACKET_READY" if owner_review else "GROUPED_DIGEST_READY" if grouped else "NO_REPLY"
    user_message = "NO_REPLY"
    if immediate:
        first = immediate[0]
        terms = first["recommended_order_terms"]
        user_message = (
            f"WF68 TRADE-READY PAPER PACKET: {first['ticker']} in band. Recommend {terms['side'].upper()} "
            f"{terms['qty']:g} share limit/day at ${terms['limit_price']:.2f} "
            f"(~${terms['estimated_notional_usd']:.2f}); stop/reference ${terms['stop_reference']}. Packet: {first['packet_md']}. {APPROVAL_BOUNDARY}"
        )
    elif owner_review:
        first = owner_review[0]
        terms = first["recommended_order_terms"]
        blockers = ", ".join(first.get("blockers") or [])
        user_message = (
            f"WF68 OWNER-REVIEW PACKET: {first['ticker']} is in band at ${terms['observed_price']:.2f}, "
            f"but paper execution is not ready. Blockers: {blockers}. Packet: {first['packet_md']}. {BOUNDARY}"
        )
    elif grouped:
        user_message = "NO_REPLY - no in-band execution-ready packet; non-immediate alerts were grouped into the WF68 digest artifact."

    return {
        "schema_version": "wf68.delivery_router_status.v1",
        "workflow": "WF68",
        "generated_at_utc": generated_at,
        "status": status,
        "immediate_policy": "execution-ready packets interrupt as paper execution review; owner-review packets interrupt only as non-executable review work; all other alerts are grouped",
        "action_needed": bool(immediate or owner_review),
        "owner_review_action_needed": bool(owner_review),
        "immediate_count": len(immediate),
        "owner_review_count": len(owner_review),
        "grouped_count": len(grouped),
        "blocked_in_band_count": len(blocked_in_band),
        "immediate_execution_recommendations": immediate,
        "owner_review_packets": owner_review,
        "blocked_in_band_candidates": blocked_in_band,
        "grouped_digest_items": grouped,
        "execution_recommendation_paths": execution_paths,
        "user_facing_message": user_message,
        "authority": AUTHORITY,
        "authority_clean": authority_clean(AUTHORITY),
        "boundary": BOUNDARY,
    }


def write_router_md(path: Path, router: dict[str, Any]) -> None:
    lines = [
        "# WF68 Delivery Router Status",
        "",
        f"- Generated UTC: {router['generated_at_utc']}",
        f"- Status: **{router['status']}**",
        f"- Immediate count: {router['immediate_count']}",
        f"- Owner-review count: {router.get('owner_review_count', 0)}",
        f"- Grouped count: {router['grouped_count']}",
        f"- Blocked in-band count: {router['blocked_in_band_count']}",
        f"- Boundary: {BOUNDARY}",
        "",
        "## Main-session message",
        "",
        router["user_facing_message"],
        "",
    ]
    if router["immediate_execution_recommendations"]:
        lines.append("## Immediate execution recommendation packets")
        for item in router["immediate_execution_recommendations"]:
            terms = item["recommended_order_terms"]
            lines.append(f"- **{item['ticker']}** {terms['side']} {terms['qty']:g} limit/day @ `{terms['limit_price']}` (~`${terms['estimated_notional_usd']}`), packet `{item['packet_md']}`")
        lines.append("")
    if router.get("owner_review_packets"):
        lines.append("## Owner-review packets")
        for item in router["owner_review_packets"]:
            terms = item["recommended_order_terms"]
            lines.append(f"- **{item['ticker']}** in band @ `{terms['observed_price']}` but not execution-ready, packet `{item['packet_md']}`; blockers `{', '.join(item.get('blockers') or [])}`")
        lines.append("")
    if router["grouped_digest_items"]:
        lines.append("## Grouped digest items")
        for item in router["grouped_digest_items"]:
            lines.append(f"- {item.get('severity')} {item.get('ticker')} `{item.get('event_type')}` bucket `{item.get('bucket')}` blockers `{', '.join(item.get('blockers') or []) or 'none'}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route WF68 advisor alerts into immediate execution packets or grouped digest.")
    parser.add_argument("--advisor-packet", type=Path, default=DEFAULT_ADVISOR_PACKET)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--execution-dir", type=Path, default=DEFAULT_EXECUTION_DIR)
    parser.add_argument("--wf67-guard", type=Path, default=DEFAULT_WF67_GUARD)
    parser.add_argument("--wf67-request-dir", type=Path, default=DEFAULT_WF67_REQUEST_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    advisor_path = args.advisor_packet if args.advisor_packet.is_absolute() else ROOT / args.advisor_packet
    output_json = args.output_json if args.output_json.is_absolute() else ROOT / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else ROOT / args.output_md
    execution_dir = args.execution_dir if args.execution_dir.is_absolute() else ROOT / args.execution_dir
    guard_path = args.wf67_guard if args.wf67_guard.is_absolute() else ROOT / args.wf67_guard
    request_dir = args.wf67_request_dir if args.wf67_request_dir.is_absolute() else ROOT / args.wf67_request_dir
    router = build_router(advisor_path, execution_dir, guard_path, request_dir)
    write_json(output_json, router)
    write_router_md(output_md, router)
    print(json.dumps({
        "status": router["status"],
        "action_needed": router["action_needed"],
        "immediate_count": router["immediate_count"],
        "owner_review_count": router["owner_review_count"],
        "grouped_count": router["grouped_count"],
        "output_json": rel(output_json),
        "output_md": rel(output_md),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
