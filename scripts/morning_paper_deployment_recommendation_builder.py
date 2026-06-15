#!/usr/bin/env python3
"""Build weekday morning review-only paper deployment recommendation cards.

This runner sits above the existing WF78/WF67 card-prep chain. It refreshes
read-only quote proof, updates the capital-review queue, asks the existing
owner-card/WF67 request generator to run, then classifies every candidate with
the stricter morning rules Randall asked for:

- fresh same-morning price proof is required for a clean approval-card posture
- in-band alone is not enough when repair mode, challenged routing, stale quote,
  gate vetoes, or other non-clean posture is present
- owner cards and WF67 request artifacts remain non-executing review surfaces

No paper/live order submit, cancel, sell, modify, approval, account action,
money movement, canon mutation, or portfolio mutation is performed here.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "morning-paper-deployment-recommendation-cards.json"
MD_OUT = TMP / "morning-paper-deployment-recommendation-cards.md"

QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
MARKET_HARDENING = TMP / "market-execution-readiness-cron-hardening.json"
CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
DECISION_FACTORY = TMP / "finance-decision-factory.json"
OWNER_CARD_PREP = TMP / "wf78-owner-card-prep-loop.json"
PROMOTION_GATE = TMP / "chief-intelligence-promotion-gate.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
CONFIDENCE_GATE = TMP / "wf78-tier-a-confidence-gate.json"
BAND_PROPOSALS = TMP / "band-proposals.json"
HYGIENE_CONTROLLER = TMP / "band-hygiene-freshness-controller.json"
SYNC_SPINE = TMP / "finance-decision-sync-spine.json"
WF84_DB = TMP / "canonical-finance-data-plane.sqlite"
WF84_PHASE = TMP / "canonical-finance-data-plane-phase6-10.json"
BAND_INTEGRITY = TMP / "capital-deployment-band-integrity-validator.json"

SCHEMA = "veritas.morning_paper_deployment_recommendation_cards.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "morning_paper_recommendation_cards_only": True,
    "owner_card_generation_allowed": True,
    "wf67_request_artifact_generation_allowed": True,
    "fresh_quote_required_for_clean_card": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_cancel_sell_modify_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_FLAGS = {
    "review_only",
    "morning_paper_recommendation_cards_only",
    "owner_card_generation_allowed",
    "wf67_request_artifact_generation_allowed",
    "fresh_quote_required_for_clean_card",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


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


def age_seconds(value: Any) -> int | None:
    parsed = parse_utc(value)
    if not parsed:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))


def run_step(name: str, command: list[str], timeout: int, *, allow_failure: bool = True) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        ok = proc.returncode == 0
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": ok,
            "allowed_failure": allow_failure,
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "allowed_failure": allow_failure,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def refresh_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.ledger_only:
        return [
            run_step(
                "finance_decision_factory_ledger_only",
                py_cmd("scripts\\finance_decision_factory.py", "--ledger-only", "--write", "--validate"),
                240,
            )
        ]

    steps = [
        run_step(
            "intraday_quote_snapshot_proof",
            py_cmd("scripts\\intraday_quote_snapshot_proof.py"),
            90,
        ),
        run_step(
            "market_execution_readiness_cron_hardening",
            py_cmd("scripts\\market_execution_readiness_cron_hardening.py", "--write", "--validate"),
            90,
        ),
    ]
    if args.skip_provider_refresh and not args.include_band_hygiene_refresh:
        steps.append({
            "name": "band_hygiene_freshness_controller",
            "command": [],
            "started_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "returncode": 0,
            "ok": True,
            "allowed_failure": True,
            "skipped": True,
            "reason": "skip_provider_refresh_fast_path_uses_existing_band_hygiene_artifact",
            "stdout_preview": "",
            "stderr_preview": "",
        })
    else:
        steps.append(
            run_step(
                "band_hygiene_freshness_controller",
                py_cmd(
                    "scripts\\band_hygiene_freshness_controller.py",
                    "--skip-quote-refresh",
                    "--apply-eligible",
                    "--write",
                    "--write-md",
                    "--validate",
                ),
                args.band_hygiene_timeout_seconds,
            )
        )
    steps.append(
        run_step(
            "wf78_capital_review_queue",
            py_cmd("scripts\\wf78_capital_review_queue.py", "--write", "--write-db", "--validate"),
            120,
        )
    )
    if not args.skip_card_refresh:
        orch = py_cmd("scripts\\parallel_repeatable_work_orchestrator.py", "--write", "--validate")
        if args.skip_provider_refresh:
            orch.append("--skip-provider-refresh")
        steps.append(run_step("parallel_repeatable_work_orchestrator", orch, args.card_refresh_timeout_seconds))
    steps.append(
        run_step(
            "finance_decision_factory_ledger_only",
            py_cmd("scripts\\finance_decision_factory.py", "--ledger-only", "--write", "--validate"),
            240,
        )
    )
    steps.append(
        run_step(
            "capital_deployment_band_integrity_validator",
            py_cmd("scripts\\capital_deployment_band_integrity_validator.py", "--write", "--write-md", "--validate"),
            60,
            allow_failure=False,
        )
    )
    return steps


def index_by_ticker(rows: list[Any], key: str = "ticker") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get(key))
        if symbol:
            out[symbol] = row_dict
    return out


def quote_index() -> dict[str, dict[str, Any]]:
    return index_by_ticker(as_list(load_dict(QUOTE_PROOF).get("snapshots")), key="symbol")


def gate_index() -> dict[str, dict[str, Any]]:
    return index_by_ticker(as_list(load_dict(PROMOTION_GATE).get("candidates")))


def router_index() -> dict[str, dict[str, Any]]:
    return index_by_ticker(as_list(load_dict(AUTO_ROUTER).get("rows")))


def confidence_index() -> dict[str, dict[str, Any]]:
    return index_by_ticker(as_list(load_dict(CONFIDENCE_GATE).get("rows")))


def band_posture_index() -> dict[str, dict[str, Any]]:
    payload = load_dict(BAND_PROPOSALS)
    blocking_tickers = {ticker(item) for item in as_list(as_dict(payload.get("summary")).get("blocking_review_tickers"))}
    rows = as_list(payload.get("proposals"))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if symbol:
            row_dict["blocking_review"] = symbol in blocking_tickers
            out[symbol] = row_dict
    return out


def band_hygiene_index() -> dict[str, dict[str, Any]]:
    return index_by_ticker(as_list(load_dict(HYGIENE_CONTROLLER).get("rows")))


def band_integrity_index() -> dict[str, dict[str, Any]]:
    payload = load_dict(BAND_INTEGRITY)
    out: dict[str, dict[str, Any]] = {}
    for finding in as_list(payload.get("findings")):
        item = as_dict(finding)
        symbol = ticker(item.get("ticker"))
        if not symbol:
            continue
        out.setdefault(symbol, {"critical": [], "warnings": []})
        if item.get("severity") == "critical":
            out[symbol]["critical"].append(item)
        else:
            out[symbol]["warnings"].append(item)
    return out


def connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def wf84_switch_enabled() -> bool:
    phase = load_dict(WF84_PHASE)
    summary = as_dict(phase.get("summary"))
    validation = as_dict(phase.get("validation"))
    authority = as_dict(phase.get("authority_boundary"))
    return (
        phase.get("status") == "ok"
        and validation.get("status") == "ok"
        and summary.get("consumer_default_switch_allowed") is True
        and authority.get("default_route_switch_allowed") is True
        and authority.get("capital_deployment_allowed") is False
        and authority.get("trade_or_execution_approved") is False
        and authority.get("paper_or_live_execution_allowed") is False
        and authority.get("owner_approval_inferred") is False
    )


def wf84_canonical_index() -> dict[str, dict[str, Any]]:
    if not WF84_DB.exists() or not wf84_switch_enabled():
        return {}
    try:
        with connect_ro(WF84_DB) as conn:
            authority = conn.execute("SELECT * FROM v_authority_boundary_false").fetchone()
            if authority and any(dict(authority).values()):
                return {}
            return {
                ticker(row["ticker"]): dict(row)
                for row in conn.execute("SELECT * FROM v_current_decision_overview")
            }
    except sqlite3.Error:
        return {}


def owner_card_mtime(path_value: Any) -> str | None:
    if not path_value:
        return None
    path = Path(str(path_value))
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def price_fresh_clean(snapshot: dict[str, Any]) -> bool:
    age = snapshot.get("age_seconds")
    age_value = int(age) if age is not None else 999999
    return (
        snapshot.get("freshness_status") == "fresh"
        and snapshot.get("price") is not None
        and age_value <= 15 * 60
    )


def effective_band_fields(item: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    """Prefer the validated WF84 overlay when it exists.

    The WF78/owner-card chain can contain pre-apply band values when band
    maintenance runs earlier in the same morning. The WF84 canonical overlay is
    the fresher route after the default switch gate has passed.
    """
    if canonical:
        return {
            "band_status": canonical.get("band_status") or item.get("current_band_status"),
            "entry_band_low": canonical.get("entry_band_low") if canonical.get("entry_band_low") is not None else item.get("entry_band_low"),
            "entry_band_high": canonical.get("entry_band_high") if canonical.get("entry_band_high") is not None else item.get("entry_band_high"),
            "stop_or_invalidation": canonical.get("stop_or_invalidation") if canonical.get("stop_or_invalidation") is not None else item.get("stop_or_invalidation"),
            "source": "wf84_canonical_overlay",
        }
    return {
        "band_status": item.get("current_band_status"),
        "entry_band_low": item.get("entry_band_low"),
        "entry_band_high": item.get("entry_band_high"),
        "stop_or_invalidation": item.get("stop_or_invalidation"),
        "source": "decision_factory",
    }


def authority_flags_clean(row: dict[str, Any]) -> bool:
    return (
        row.get("capital_deployment_approved") is False
        and row.get("trade_or_execution_approved") is False
        and row.get("paper_or_live_execution_allowed") is False
        and row.get("owner_approval_inferred") is False
    )


def classify_candidate(
    row: dict[str, Any],
    snapshot: dict[str, Any],
    gate: dict[str, Any],
    router: dict[str, Any],
    canonical: dict[str, Any],
    confidence: dict[str, Any],
    band_posture: dict[str, Any],
    band_hygiene: dict[str, Any],
    band_integrity: dict[str, Any] | None = None,
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    band_integrity = band_integrity or {}

    if row.get("disposition") != "owner_card_and_wf67_request_ready":
        blockers.append(f"decision_factory_disposition={row.get('disposition')}")
    if row.get("wf67_request_generation_status") != "ok" or not row.get("wf67_request_path"):
        blockers.append("wf67_request_artifact_not_ready")
    if not row.get("owner_card_path"):
        blockers.append("owner_card_missing")
    if not canonical:
        blockers.append("wf84_canonical_default_overlay_missing")
    if gate and gate.get("chief_intelligence_verdict") != "promote_for_owner_review":
        blockers.append(f"promotion_gate_verdict={gate.get('chief_intelligence_verdict')}")
    gate_vetoes = as_list(row.get("gate_vetoes")) or as_list(gate.get("vetoes"))
    if gate_vetoes:
        blockers.append("promotion_gate_vetoes_present")
    band_fields = effective_band_fields(row, canonical)
    effective_band_status = str(band_fields.get("band_status") or "").upper()
    if effective_band_status != "IN_BAND":
        blockers.append(f"band_status_not_clean:{band_fields.get('band_status')}")
    if not price_fresh_clean(snapshot):
        blockers.append(f"fresh_morning_price_not_clean:{snapshot.get('freshness_status') or 'missing'}")
    if str(band_posture.get("entry_policy") or "").lower() == "repair_mode":
        blockers.append("repair_mode_active")
    hygiene_state = band_hygiene.get("state")
    hygiene_blockers = as_list(band_hygiene.get("blockers"))
    auto_applied_band_review = (
        hygiene_state == "applied_auto_maintenance"
        or as_dict(band_hygiene.get("auto_apply")).get("applied") is True
    )
    if (band_posture.get("needs_review") is True or band_posture.get("blocking_review") is True) and not auto_applied_band_review:
        blockers.append("band_review_required")
    if hygiene_state == "post_apply_review_still_open":
        blockers.append("post_apply_band_review_still_open")
    elif hygiene_state == "applied_auto_maintenance_watch":
        blockers.append("band_hygiene_applied_but_context_watch")
    elif hygiene_state == "exception_owner_review":
        blockers.append("band_hygiene_exception_owner_review")
    elif hygiene_state == "eligible_auto_maintenance_pending":
        blockers.append("eligible_band_maintenance_pending")
    elif hygiene_state in {"missing_band_context", "band_refresh_skipped"}:
        blockers.append(f"band_hygiene_state={hygiene_state}")
    if "quote_not_intraday_fresh" in hygiene_blockers or "missing_quote_snapshot" in hygiene_blockers:
        blockers.append("band_hygiene_quote_not_fresh")
    for finding in as_list(band_integrity.get("critical")):
        blockers.append(f"band_integrity_{finding.get('code')}")
    for finding in as_list(band_integrity.get("warnings")):
        warnings.append(f"band_integrity_{finding.get('code')}")
    if str(router.get("auto_state") or "").upper().endswith("CHALLENGED") or "CHALLENGED" in str(router.get("auto_state") or "").upper():
        blockers.append(f"wf78_route_not_clean:{router.get('auto_state')}")
    if canonical and str(canonical.get("auto_state") or "").upper().endswith("CHALLENGED"):
        blockers.append(f"wf84_route_not_clean:{canonical.get('auto_state')}")
    confidence_status = str(confidence.get("tier_a_confidence_status") or confidence.get("promotion_effect") or "")
    if any(token in confidence_status.lower() for token in ("challenged", "manual_review", "force_a_challenged")):
        blockers.append(f"confidence_gate_not_clean:{confidence_status}")
    if not authority_flags_clean(row):
        blockers.append("authority_flags_not_all_false")
    canonical_authority_flags = [
        canonical.get("capital_deployment_approved"),
        canonical.get("trade_or_execution_approved"),
        canonical.get("paper_or_live_execution_allowed"),
        canonical.get("owner_approval_inferred"),
    ]
    if canonical and any(int(value or 0) for value in canonical_authority_flags):
        blockers.append("wf84_authority_flags_not_all_false")

    quote_context = as_dict(row.get("quote_repair_context"))
    if quote_context.get("execution_freshness_approved") is not False:
        warnings.append("execution_freshness_flag_not_false")
    if row.get("quote_freshness_status") != "current_market_day_quote_available_for_non_executing_review":
        warnings.append(f"decision_factory_quote_status={row.get('quote_freshness_status')}")
    if row.get("blocked_reason"):
        warnings.append(f"blocked_reason={row.get('blocked_reason')}")

    status = "approval_card_clean_ready_for_randall_review" if not blockers else "blocked_or_not_clean_for_approval"
    return status, sorted(set(blockers)), sorted(set(warnings))


def build_cards() -> list[dict[str, Any]]:
    decision = load_dict(DECISION_FACTORY)
    quotes = quote_index()
    gates = gate_index()
    routers = router_index()
    canonical_rows = wf84_canonical_index()
    confidence = confidence_index()
    band_postures = band_posture_index()
    band_hygiene_rows = band_hygiene_index()
    band_integrity_rows = band_integrity_index()
    cards: list[dict[str, Any]] = []
    for row in as_list(decision.get("decision_ledger")):
        item = as_dict(row)
        symbol = ticker(item.get("ticker"))
        if not symbol:
            continue
        snapshot = quotes.get(symbol, {})
        gate = gates.get(symbol, {})
        router = routers.get(symbol, {})
        canonical = canonical_rows.get(symbol, {})
        conf = confidence.get(symbol, {})
        band_posture = band_postures.get(symbol, {})
        band_hygiene = band_hygiene_rows.get(symbol, {})
        band_integrity = band_integrity_rows.get(symbol, {})
        status, blockers, warnings = classify_candidate(item, snapshot, gate, router, canonical, conf, band_posture, band_hygiene, band_integrity)
        band_fields = effective_band_fields(item, canonical)
        cards.append({
            "ticker": symbol,
            "status": status,
            "clean_for_randall_approval_review": status == "approval_card_clean_ready_for_randall_review",
            "blockers": blockers,
            "warnings": warnings,
            "current_price": snapshot.get("price") if snapshot.get("price") is not None else item.get("current_price"),
            "quote_snapshot": {
                "price": snapshot.get("price"),
                "bid": snapshot.get("bid"),
                "ask": snapshot.get("ask"),
                "freshness_status": snapshot.get("freshness_status"),
                "age_seconds": snapshot.get("age_seconds"),
                "source_timestamp_utc": snapshot.get("source_timestamp_utc"),
                "received_at_utc": snapshot.get("received_at_utc"),
            },
            "band_status": band_fields.get("band_status"),
            "entry_band_low": band_fields.get("entry_band_low"),
            "entry_band_high": band_fields.get("entry_band_high"),
            "stop_or_invalidation": band_fields.get("stop_or_invalidation"),
            "band_field_source": band_fields.get("source"),
            "decision_factory_band_snapshot": {
                "band_status": item.get("current_band_status"),
                "entry_band_low": item.get("entry_band_low"),
                "entry_band_high": item.get("entry_band_high"),
                "stop_or_invalidation": item.get("stop_or_invalidation"),
            },
            "gate_verdict": item.get("gate_verdict") or gate.get("chief_intelligence_verdict"),
            "gate_vetoes": as_list(item.get("gate_vetoes")) or as_list(gate.get("vetoes")),
            "repair_mode": str(band_posture.get("entry_policy") or "").lower() == "repair_mode",
            "band_review_required": (
                (band_posture.get("needs_review") is True or band_posture.get("blocking_review") is True)
                and not (
                    band_hygiene.get("state") == "applied_auto_maintenance"
                    or as_dict(band_hygiene.get("auto_apply")).get("applied") is True
                )
            ),
            "band_hygiene_state": band_hygiene.get("state"),
            "band_hygiene_blockers": as_list(band_hygiene.get("blockers")),
            "band_hygiene_auto_apply": as_dict(band_hygiene.get("auto_apply")),
            "band_integrity": {
                "critical": [as_dict(item).get("code") for item in as_list(band_integrity.get("critical"))],
                "warnings": [as_dict(item).get("code") for item in as_list(band_integrity.get("warnings"))],
            },
            "wf84_canonical_data_plane": {
                "status": "ok" if canonical else "missing_or_switch_disabled",
                "ticker": canonical.get("ticker"),
                "auto_tier": canonical.get("auto_tier"),
                "auto_state": canonical.get("auto_state"),
                "primary_state": canonical.get("primary_state"),
                "queue_state": canonical.get("queue_state"),
                "actionability": canonical.get("actionability"),
                "latest_known_price": canonical.get("latest_known_price"),
                "band_status": canonical.get("band_status"),
                "entry_band_low": canonical.get("entry_band_low"),
                "entry_band_high": canonical.get("entry_band_high"),
                "stop_or_invalidation": canonical.get("stop_or_invalidation"),
                "owner_action_required": bool(canonical.get("owner_action_required")) if canonical else None,
                "authority_flags_false": (
                    not any(int(canonical.get(key) or 0) for key in (
                        "capital_deployment_approved",
                        "trade_or_execution_approved",
                        "paper_or_live_execution_allowed",
                        "owner_approval_inferred",
                    ))
                    if canonical else None
                ),
            },
            "repair_mode_detail": {
                "entry_policy": band_posture.get("entry_policy"),
                "needs_review": band_posture.get("needs_review"),
                "blocking_review": band_posture.get("blocking_review"),
                "band_status": band_posture.get("band_status"),
                "rationale": band_posture.get("rationale") or band_posture.get("reason") or band_posture.get("reasons"),
            } if band_posture else None,
            "wf78_route_state": router.get("auto_state"),
            "confidence_gate_state": conf.get("tier_a_confidence_status") or conf.get("promotion_effect"),
            "owner_card_path": item.get("owner_card_path"),
            "owner_card_mtime_utc": owner_card_mtime(item.get("owner_card_path")),
            "wf67_request_path": item.get("wf67_request_path"),
            "wf67_request_generation_status": item.get("wf67_request_generation_status"),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "owner_action_required": True,
        })
    return cards


def validate_authority() -> list[str]:
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        expected = True if key in TRUE_FLAGS else False
        if value is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    return errors


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    steps = refresh_steps(args)
    cards = build_cards()
    clean_cards = [card for card in cards if card.get("clean_for_randall_approval_review")]
    blocked_cards = [card for card in cards if not card.get("clean_for_randall_approval_review")]
    clean_cards_with_warnings = [card for card in clean_cards if as_list(card.get("warnings"))]
    clean_cards_without_warnings = [card for card in clean_cards if not as_list(card.get("warnings"))]
    canonical_overlay_count = len([card for card in cards if as_dict(card.get("wf84_canonical_data_plane")).get("status") == "ok"])
    hard_step_failures = [step["name"] for step in steps if not step.get("ok") and not step.get("allowed_failure")]
    soft_step_failures = [step["name"] for step in steps if not step.get("ok") and step.get("allowed_failure")]
    authority_errors = validate_authority()
    wf84_errors = [] if canonical_overlay_count == len(cards) else ["wf84_canonical_overlay_missing_for_candidates"]
    errors = list(hard_step_failures) + authority_errors + wf84_errors
    warnings = list(soft_step_failures)
    band_integrity = load_dict(BAND_INTEGRITY)
    band_integrity_summary = as_dict(band_integrity.get("summary"))
    band_integrity_status = band_integrity.get("status")
    if band_integrity_status == "blocked":
        errors.append("capital_deployment_band_integrity_blocked")
    skipped_band_hygiene = any(step.get("name") == "band_hygiene_freshness_controller" and step.get("skipped") for step in steps)
    band_hygiene_artifact_age_seconds = age_seconds(load_dict(HYGIENE_CONTROLLER).get("generated_at_utc")) if skipped_band_hygiene else None
    if skipped_band_hygiene and (band_hygiene_artifact_age_seconds is None or band_hygiene_artifact_age_seconds > 3600):
        warnings.append("band_hygiene_fast_path_used_with_stale_or_unknown_artifact")
    warning_conditions = bool(clean_cards_with_warnings) or band_integrity_status == "warning" or bool(warnings)
    status = "ok" if clean_cards and not errors and not warning_conditions else "warning" if cards and not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Weekday morning review-only paper deployment recommendation approval-card builder from WF78/WF67.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "schedule_design": {
            "intended_window": "weekday premarket after morning freshness producers and before regular-session open",
            "timezone": "America/Phoenix",
            "clean_card_requires_fresh_quote_seconds": 900,
        },
        "summary": {
            "candidate_count": len(cards),
            "clean_approval_card_count": len(clean_cards),
            "clean_without_warnings_count": len(clean_cards_without_warnings),
            "clean_with_warnings_count": len(clean_cards_with_warnings),
            "blocked_or_not_clean_count": len(blocked_cards),
            "clean_tickers": [card["ticker"] for card in clean_cards],
            "clean_without_warnings_tickers": [card["ticker"] for card in clean_cards_without_warnings],
            "clean_with_warnings_tickers": [card["ticker"] for card in clean_cards_with_warnings],
            "blocked_or_not_clean_tickers": [card["ticker"] for card in blocked_cards],
            "wf84_canonical_default_overlay_count": canonical_overlay_count,
            "wf84_canonical_default_switch_enabled": wf84_switch_enabled(),
            "soft_step_failures": soft_step_failures,
            "skipped_steps": [step["name"] for step in steps if step.get("skipped")],
            "band_hygiene_artifact_age_seconds": band_hygiene_artifact_age_seconds,
            "band_integrity_status": band_integrity_status,
            "band_integrity_critical_tickers": as_list(band_integrity_summary.get("mismatch_tickers")),
            "band_integrity_warning_tickers": as_list(band_integrity_summary.get("warning_tickers")),
            "next_safe_action": (
                "Present clean approval cards to Randall for exact approval; no execution is authorized."
                if clean_cards
                else "Do not ask for approval yet; repair/freshness/posture blockers remain."
            ),
        },
        "cards": cards,
        "source_artifacts": {
            "quote_snapshot_proof": rel(QUOTE_PROOF),
            "market_execution_readiness": rel(MARKET_HARDENING),
            "capital_review_queue": rel(CAPITAL_QUEUE),
            "finance_decision_factory": rel(DECISION_FACTORY),
            "owner_card_prep_loop": rel(OWNER_CARD_PREP),
            "promotion_gate": rel(PROMOTION_GATE),
            "auto_router": rel(AUTO_ROUTER),
            "confidence_gate": rel(CONFIDENCE_GATE),
            "band_proposals": rel(BAND_PROPOSALS),
            "band_hygiene_freshness_controller": rel(HYGIENE_CONTROLLER),
            "finance_decision_sync_spine": rel(SYNC_SPINE),
            "wf84_canonical_data_plane_sqlite": rel(WF84_DB),
            "wf84_phase6_10_switch_proof": rel(WF84_PHASE),
            "capital_deployment_band_integrity_validator": rel(BAND_INTEGRITY),
        },
        "steps": steps,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "This cron produces recommendation approval cards only.",
            "Clean means ready for Randall review, not approved.",
            "No paper/live submit, cancel, sell, modify, replace, close-position, account action, money movement, capital deployment, canon/portfolio mutation, or owner approval inference is allowed.",
            "Any exact paper order still requires Randall approval plus WF67 wrapper, fresh kill switch, and clean guard validation.",
        ],
    }


def markdown(report: dict[str, Any]) -> str:
    def integrity_label(card_dict: dict[str, Any]) -> str:
        integrity = as_dict(card_dict.get("band_integrity"))
        critical = as_list(integrity.get("critical"))
        warnings = as_list(integrity.get("warnings"))
        if critical:
            return "critical:" + ",".join(str(item) for item in critical)
        if warnings:
            return "warning:" + ",".join(str(item) for item in warnings)
        return "ok"

    lines = [
        "# Morning Paper Deployment Recommendation Cards",
        "",
        f"- Generated UTC: `{report.get('generated_at_utc')}`",
        f"- Status: `{report.get('status')}`",
        f"- Clean cards: `{as_dict(report.get('summary')).get('clean_approval_card_count')}`",
        f"- Clean without warnings: `{as_dict(report.get('summary')).get('clean_without_warnings_tickers')}`",
        f"- Clean with warnings: `{as_dict(report.get('summary')).get('clean_with_warnings_tickers')}`",
        f"- Blocked/not clean: `{as_dict(report.get('summary')).get('blocked_or_not_clean_count')}`",
        f"- Band integrity: `{as_dict(report.get('summary')).get('band_integrity_status')}`",
        f"- Band warnings: `{as_dict(report.get('summary')).get('band_integrity_warning_tickers')}`",
        "",
        "| Ticker | Status | Price freshness | Price | Band | Gate | WF67 | Band integrity | Main blocker |",
        "|---|---|---|---:|---|---|---|---|---|",
    ]
    for card in as_list(report.get("cards")):
        card_dict = as_dict(card)
        blockers = as_list(card_dict.get("blockers"))
        quote = as_dict(card_dict.get("quote_snapshot"))
        lines.append(
            "| {ticker} | {status} | {fresh} | {price} | {band} | {gate} | {wf67} | {integrity} | {blocker} |".format(
                ticker=card_dict.get("ticker"),
                status=card_dict.get("status"),
                fresh=quote.get("freshness_status"),
                price=card_dict.get("current_price"),
                band=card_dict.get("band_status"),
                gate=card_dict.get("gate_verdict"),
                wf67=card_dict.get("wf67_request_generation_status"),
                integrity=integrity_label(card_dict),
                blocker=blockers[0] if blockers else "",
            )
        )
    lines.extend([
        "",
        "Boundary: review-only approval-card prep. No paper/live order action, account action, money movement, capital deployment approval, portfolio/canon mutation, or owner approval inference.",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--ledger-only", action="store_true", help="Only rebuild from current artifacts.")
    parser.add_argument("--skip-card-refresh", action="store_true", help="Do not regenerate owner cards/WF67 request artifacts.")
    parser.add_argument("--skip-provider-refresh", action="store_true", help="Pass local-only mode to the owner-card prep orchestrator.")
    parser.add_argument("--include-band-hygiene-refresh", action="store_true", help="Run the heavy band-hygiene controller even in local skip-provider mode.")
    parser.add_argument("--band-hygiene-timeout-seconds", type=int, default=300)
    parser.add_argument("--card-refresh-timeout-seconds", type=int, default=300)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    report = build_report(args)
    if args.write:
        atomic_write_json(out, report)
    if args.write_md:
        atomic_write_text(md_out, markdown(report))
    sync_step = None
    if args.write:
        sync_step = run_step(
            "finance_decision_sync_spine",
            py_cmd("scripts\\finance_decision_sync_spine.py", "--write", "--write-md", "--validate"),
            120,
            allow_failure=False,
        )
    print(json.dumps({
        "status": report["status"],
        "out": rel(out),
        "md_out": rel(md_out) if args.write_md else None,
        "summary": report["summary"],
        "validation": report["validation"],
        "sync_spine": sync_step,
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    if args.validate and sync_step is not None and not sync_step.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
