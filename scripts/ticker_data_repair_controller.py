#!/usr/bin/env python3
"""Review-only same-day repair and fresh in-band attention coordinator."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "ticker-data-repair-controller.json"
FUNDAMENTALS = TMP / "fundamental-metrics-validation.json"
WARNING_ROUTER = TMP / "finance-evidence-warning-router.json"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
QUOTE_VALIDATION = TMP / "intraday-alerts" / "quote-snapshot-proof-validation.json"
BAND_PROPOSALS = TMP / "band-proposals.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
BAND_HYGIENE = TMP / "band-hygiene-freshness-controller.json"
DECISION_SYNC = TMP / "finance-decision-sync-spine.json"
REVIEW_ATTENTION = TMP / "in-band-review-attention-bridge.json"
INTRADAY_REVIEW_OVERLAY = TMP / "wf85-intraday-review-overlay.json"
WF85_VISIBILITY_QUEUE = TMP / "wf85-opportunity-visibility-queue.json"
TICKER_CARD_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"

SCHEMA = "veritas.ticker_data_repair_controller.v1"
CADENCE = {
    "recommended": True,
    "cadence_minutes": 15,
    "timezone": "America/Phoenix",
    "regular_market_window_local": "06:00-13:45 weekdays; pre-open, regular session, and two post-close reconciliation passes",
    "cron_expression_recommendation": "*/15 6-13 * * 1-5",
    "purpose": "Refresh review-only repair classification every 15 minutes through post-close reconciliation; only --execute-safe may invoke the bounded quote-proof recheck during eligible market hours.",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "same_day_repair_coordination_only": True,
    "safe_quote_proof_recheck_allowed_when_explicitly_requested": True,
    "fundamental_source_mapping_mutation_allowed": False,
    "fundamental_auto_repair_or_apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_rule_or_execution_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

STALE_QUOTE_FRESHNESS = {
    "stale",
    "missing_source_timestamp",
    "current_but_not_intraday_fresh",
}
STALE_QUOTE_CALENDAR = {"stale_unexpected", "provider_missing", "unknown"}
CURRENT_QUOTE_CALENDAR = {
    "fresh_intraday",
    "current_last_completed_session",
    "market_closed_expected_stale",
}
REVIEW_TIERS = {"Tier A", "Tier B"}
MAX_TIER_ROUTER_AGE_SECONDS = 24 * 60 * 60


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
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
        return None
    return parsed.astimezone(timezone.utc)


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_source(path: Path, source_name: str) -> tuple[dict[str, Any], bool, list[str]]:
    """Load one optional JSON artifact without treating absence as a repair."""
    if not path.exists():
        return {}, False, [f"missing_source:{source_name}:{rel(path)}"]
    payload = load_json_artifact(path)
    if not isinstance(payload, dict):
        return {}, False, [f"unreadable_source:{source_name}:{rel(path)}"]
    return payload, True, []


def repair_rows_from_sources(fundamentals: dict[str, Any], warning_router: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized fundamental repair rows from both current proof layers."""
    rows: list[dict[str, Any]] = []
    source_queues = [
        ("fundamental_metrics_validation", as_list(fundamentals.get("repair_queue"))),
        (
            "finance_evidence_warning_router",
            as_list(as_dict(as_dict(warning_router.get("sections")).get("fundamentals")).get("repair_queue")),
        ),
    ]
    for source_name, queue in source_queues:
        for raw in queue:
            repair = as_dict(raw)
            ticker = normalize_ticker(repair.get("ticker"))
            code = str(repair.get("code") or "").strip()
            if not ticker or not code:
                continue
            rows.append({
                "source_name": source_name,
                "ticker": ticker,
                "code": code,
                "fingerprint": str(repair.get("fingerprint") or f"{ticker}:{code}").strip(),
                "severity": str(repair.get("severity") or "warning"),
                "classification": repair.get("classification"),
                "status": repair.get("status") or "repair_required",
                "deduplicated_finding_count": int(repair.get("deduplicated_finding_count") or 1),
                "source_open_required": repair.get("source_open_required") is True,
                "manual_review_required": repair.get("manual_review_required") is True,
                "blocks_ticker_only": repair.get("blocks_ticker_only") is True,
                "next_action": repair.get("next_action"),
                "source_artifact": repair.get("source_artifact"),
                "evidence": as_dict(repair.get("evidence")),
            })
    return rows


def stale_quote_rows(quote_proof: dict[str, Any]) -> list[dict[str, Any]]:
    """Identify ticker-scoped stale quote proof; this does not fetch or amend data."""
    rows: list[dict[str, Any]] = []
    for raw in as_list(quote_proof.get("snapshots")):
        snapshot = as_dict(raw)
        ticker = normalize_ticker(snapshot.get("symbol") or snapshot.get("ticker"))
        if not ticker:
            continue
        reasons: list[str] = []
        freshness = str(snapshot.get("freshness_status") or "").strip()
        calendar = str(snapshot.get("calendar_freshness_status") or "").strip()
        # Calendar freshness avoids false stale tickets outside market hours.
        calendar_current = calendar in CURRENT_QUOTE_CALENDAR
        if freshness in STALE_QUOTE_FRESHNESS and not calendar_current:
            reasons.append(f"freshness_status:{freshness}")
        if calendar in STALE_QUOTE_CALENDAR:
            reasons.append(f"calendar_freshness_status:{calendar}")
        if reasons:
            rows.append({
                "ticker": ticker,
                "reasons": sorted(set(reasons)),
                "source_timestamp_utc": snapshot.get("source_timestamp_utc"),
                "freshness_status": freshness or None,
                "calendar_freshness_status": calendar or None,
            })
    return rows


def rows_for(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "snapshots", "proposals"):
        rows = as_list(payload.get(key))
        if rows:
            return [as_dict(row) for row in rows]
    return []


def index_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows_for(payload):
        symbol = normalize_ticker(row.get("ticker") or row.get("symbol"))
        if symbol:
            result[symbol] = row
    return result


def quote_is_fresh_for_attention(snapshot: dict[str, Any]) -> bool:
    try:
        age = int(snapshot.get("age_seconds"))
    except (TypeError, ValueError):
        return False
    return (
        snapshot.get("freshness_status") == "fresh"
        and snapshot.get("calendar_freshness_status") == "fresh_intraday"
        and fnum(snapshot.get("price")) is not None
        and age <= 15 * 60
    )


def price_is_in_existing_band(price: float | None, proposal: dict[str, Any]) -> bool:
    low = fnum(proposal.get("current_band_low"))
    high = fnum(proposal.get("current_band_high"))
    stop = fnum(proposal.get("current_stop"))
    if price is None or low is None or high is None:
        return False
    if stop is not None and price < stop:
        return False
    return low <= price <= high


def fresh_in_band_tier_ab_rows(
    quote_proof: dict[str, Any], band_proposals: dict[str, Any], auto_router: dict[str, Any],
) -> list[dict[str, Any]]:
    bands = index_rows(band_proposals)
    routes = index_rows(auto_router)
    rows: list[dict[str, Any]] = []
    for snapshot in rows_for(quote_proof):
        symbol = normalize_ticker(snapshot.get("ticker") or snapshot.get("symbol"))
        if not symbol or not quote_is_fresh_for_attention(snapshot):
            continue
        route = routes.get(symbol, {})
        tier = str(route.get("auto_tier") or "")
        proposal = bands.get(symbol, {})
        price = fnum(snapshot.get("price"))
        if tier not in REVIEW_TIERS or not price_is_in_existing_band(price, proposal):
            continue
        rows.append({
            "ticker": symbol,
            "auto_tier": tier,
            "auto_state": route.get("auto_state"),
            "price": price,
            "source_timestamp_utc": snapshot.get("source_timestamp_utc"),
            "entry_band_low": fnum(proposal.get("current_band_low")),
            "entry_band_high": fnum(proposal.get("current_band_high")),
            "stop_or_invalidation": fnum(proposal.get("current_stop")),
        })
    return sorted(rows, key=lambda row: (str(row.get("auto_tier")), str(row.get("ticker"))))


def review_sync_needed(
    quote_proof: dict[str, Any],
    band_proposals: dict[str, Any],
    auto_router: dict[str, Any],
    band_hygiene: dict[str, Any],
    decision_sync: dict[str, Any],
    prior_attention: dict[str, Any],
    as_of_utc: str | None = None,
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    candidates = fresh_in_band_tier_ab_rows(quote_proof, band_proposals, auto_router)
    if not candidates:
        return False, candidates, ["no_fresh_tier_ab_in_band_quote"]
    quote_time = parse_utc(quote_proof.get("generated_at_utc"))
    if quote_time is None:
        return False, candidates, ["quote_proof_generated_at_missing"]
    as_of = parse_utc(as_of_utc) if as_of_utc else datetime.now(timezone.utc)
    if as_of is None or quote_time > as_of or (as_of - quote_time).total_seconds() > 15 * 60:
        return False, candidates, ["quote_proof_not_current_for_attention"]
    reasons: list[str] = []
    if quote_proof.get("status") != "ok":
        reasons.append(f"quote_proof_status_not_ok:{quote_proof.get('status') or 'missing'}")
    if auto_router.get("status") != "ok":
        reasons.append(f"tier_router_status_not_ok:{auto_router.get('status') or 'missing'}")
    router_generated = parse_utc(auto_router.get("generated_at_utc"))
    if router_generated is None:
        reasons.append("tier_router_generated_at_missing")
    elif (quote_time - router_generated).total_seconds() > MAX_TIER_ROUTER_AGE_SECONDS:
        reasons.append("tier_router_not_current_for_quote_proof")
    for name, payload in (
        ("band_hygiene", band_hygiene),
        ("decision_sync", decision_sync),
        ("review_attention", prior_attention),
    ):
        status = payload.get("status")
        if status != "ok":
            reasons.append(f"{name}_status_not_ok:{status or 'missing'}")
        generated = parse_utc(payload.get("generated_at_utc"))
        if generated is None:
            reasons.append(f"{name}_generated_at_missing")
        elif generated < quote_time:
            reasons.append(f"{name}_older_than_quote_proof")
    return bool(reasons), candidates, sorted(set(reasons)) or ["hygiene_sync_and_attention_current_for_quote"]


def merge_repair_queue(
    fundamental_rows: list[dict[str, Any]], quote_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Consolidate all affected data-quality work into exactly one row per ticker."""
    by_ticker: dict[str, dict[str, Any]] = {}

    def item_for(ticker: str) -> dict[str, Any]:
        if ticker not in by_ticker:
            by_ticker[ticker] = {
                "ticker": ticker,
                "issue_types": [],
                "fundamental_repairs": [],
                "quote_freshness": [],
                "source_open_required": False,
                "manual_review_required": False,
                "blocks_ticker_only": True,
                "automatic_fundamental_repair_allowed": False,
                "recommended_actions": [],
            }
        return by_ticker[ticker]

    seen_fundamentals: set[tuple[str, str, str]] = set()
    for row in fundamental_rows:
        ticker = row["ticker"]
        key = (ticker, row["code"], row["fingerprint"])
        if key in seen_fundamentals:
            continue
        seen_fundamentals.add(key)
        item = item_for(ticker)
        if "fundamental_source_period_mismatch" not in item["issue_types"]:
            item["issue_types"].append("fundamental_source_period_mismatch")
        item["fundamental_repairs"].append({
            "fingerprint": row["fingerprint"],
            "code": row["code"],
            "severity": row["severity"],
            "classification": row["classification"],
            "status": row["status"],
            "deduplicated_finding_count": row["deduplicated_finding_count"],
            "source_name": row["source_name"],
            "source_artifact": row["source_artifact"],
            "evidence": row["evidence"],
        })
        # Preserve source-open/manual-revalidation posture.
        item["source_open_required"] = True
        item["manual_review_required"] = True
        item["blocks_ticker_only"] = item["blocks_ticker_only"] and row["blocks_ticker_only"]
        action = row.get("next_action") or (
            f"Source-open and reconcile {ticker} fundamental period metadata, then revalidate only the affected ticker."
        )
        if action not in item["recommended_actions"]:
            item["recommended_actions"].append(action)

    for row in quote_rows:
        ticker = row["ticker"]
        item = item_for(ticker)
        if "quote_freshness" not in item["issue_types"]:
            item["issue_types"].append("quote_freshness")
        if row not in item["quote_freshness"]:
            item["quote_freshness"].append(deepcopy(row))
        action = f"Recheck {ticker} quote proof only with --execute-safe; do not use stale numeric quote fields until fresh proof is available."
        if action not in item["recommended_actions"]:
            item["recommended_actions"].append(action)

    queue = []
    for ticker in sorted(by_ticker):
        item = by_ticker[ticker]
        item["issue_types"] = sorted(item["issue_types"])
        item["fundamental_repairs"] = sorted(
            item["fundamental_repairs"], key=lambda row: (str(row["code"]), str(row["fingerprint"]))
        )
        item["quote_freshness"] = sorted(
            item["quote_freshness"], key=lambda row: tuple(row["reasons"])
        )
        item["fundamental_repair_count"] = len(item["fundamental_repairs"])
        item["quote_freshness_issue_count"] = len(item["quote_freshness"])
        item["repair_mode"] = (
            "manual_source_open_and_revalidate"
            if item["fundamental_repairs"] else "safe_quote_proof_recheck_only"
        )
        queue.append(item)
    return queue


def run_safe_quote_recheck() -> dict[str, Any]:
    """Run the existing bounded quote-hardening command, never a data repair command."""
    started = utc_now()
    command = [sys.executable, "scripts\\market_execution_readiness_cron_hardening.py", "--validate"]
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=300, check=False)
        return {
            "requested": True,
            "attempted": True,
            "command": "python scripts\\market_execution_readiness_cron_hardening.py --validate",
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_tail": proc.stdout[-1600:],
            "stderr_tail": proc.stderr[-1000:],
            "scope": "existing bounded quote-proof recheck only; no fundamental or canonical mutation",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "requested": True,
            "attempted": True,
            "command": "python scripts\\market_execution_readiness_cron_hardening.py --validate",
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": 300,
            "stdout_tail": (exc.stdout or "")[-1600:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1000:] if isinstance(exc.stderr, str) else "",
            "scope": "existing bounded quote-proof recheck only; no fundamental or canonical mutation",
        }
    except OSError as exc:
        return {
            "requested": True,
            "attempted": True,
            "command": "python scripts\\market_execution_readiness_cron_hardening.py --validate",
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "stderr_tail": f"quote_recheck_launch_error:{type(exc).__name__}:{exc}",
            "scope": "existing bounded quote-proof recheck only; no fundamental or canonical mutation",
        }


def attention_tickers(payload: dict[str, Any]) -> list[str]:
    """Return exactly the current fresh Tier A/B review/repair tickers."""
    tickers: set[str] = set()
    for section in ("review_attention", "repair_attention"):
        for raw in as_list(payload.get(section)):
            ticker = normalize_ticker(as_dict(raw).get("ticker"))
            if ticker:
                tickers.add(ticker)
    return sorted(tickers)


def run_bounded_review_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "name": name,
            "command": " ".join(command).replace(sys.executable, "python", 1),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_tail": proc.stdout[-1200:],
            "stderr_tail": proc.stderr[-800:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": " ".join(command).replace(sys.executable, "python", 1),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_tail": (exc.stdout or "")[-1200:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-800:] if isinstance(exc.stderr, str) else "",
        }
    except OSError as exc:
        return {
            "name": name,
            "command": " ".join(command).replace(sys.executable, "python", 1),
            "returncode": None,
            "ok": False,
            "stderr_tail": f"review_sync_launch_error:{type(exc).__name__}:{exc}",
        }


def load_current_intraday_review_overlay() -> dict[str, Any]:
    payload = load_json_artifact(INTRADAY_REVIEW_OVERLAY)
    return payload if isinstance(payload, dict) else {}


def review_only_overlay_tickers(payload: dict[str, Any]) -> list[str]:
    """Return only validated, non-approvable current overlay rows.

    The controller rechecks the overlay's authority semantics before it asks
    the evidence gate to do any source refresh.  This prevents a future WF85
    surface from changing a label into an accidental approval input.
    """
    if payload.get("status") not in {"ok", "warning"}:
        return []
    validation = as_dict(payload.get("validation"))
    if validation.get("status") not in {"ok", "warning"}:
        return []
    tickers: set[str] = set()
    for raw in as_list(payload.get("rows")):
        row = as_dict(raw)
        price = as_dict(row.get("current_price"))
        freshness = as_dict(row.get("source_freshness"))
        ticker = normalize_ticker(row.get("ticker"))
        if (
            ticker
            and price.get("quote_freshness_status") == "intraday_review_only_fresh"
            and price.get("review_only_quote") is True
            and price.get("approval_draft_eligible") is False
            and freshness.get("fresh_for_review") is True
            and freshness.get("fresh_for_approval") is False
            and row.get("capital_deployment_approved") is False
            and row.get("trade_or_execution_approved") is False
            and row.get("paper_or_live_execution_allowed") is False
        ):
            tickers.add(ticker)
    return sorted(tickers)


def skipped_review_step(name: str, reason: str, *, ok: bool) -> dict[str, Any]:
    return {"name": name, "attempted": False, "skipped": True, "ok": ok, "reason": reason}


def run_review_visibility_queue_refresh(
    command_runner: Callable[[str, list[str], int], dict[str, Any]] = run_bounded_review_step,
) -> dict[str, Any]:
    """Rebuild WF85 visibility on every safe cadence.

    The queue is responsible for expiring `intraday_review_only_fresh` rows.
    It must therefore run even on a quiet cadence that has no new in-band
    transition; otherwise a previous fresh overlay could remain displayed
    after its 15-minute review window ends.
    """
    return command_runner(
        "wf85_opportunity_visibility_queue",
        [sys.executable, "scripts\\wf85_opportunity_visibility_queue.py", "--write", "--validate"],
        90,
    )


def run_review_sync(
    command_runner: Callable[[str, list[str], int], dict[str, Any]] = run_bounded_review_step,
    attention_reader: Callable[[], dict[str, Any]] | None = None,
    overlay_reader: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Refresh review-only consumers after a fresh in-band transition.

    The band-hygiene command deliberately skips provider, technical, and band
    refreshes here: its job is to consume the already-current quote proof and
    existing technical/band surfaces.  Its auto-band step remains dry-run, so
    this branch cannot apply a portfolio/canonical change.  A successful core
    sync may then generate a *review-only* intraday overlay, refresh official
    evidence for exactly those fresh overlay tickers, and rebuild the WF85
    visibility queue.  No step is permitted to create an approval card, order,
    execution request, or portfolio/canon mutation.
    """
    started = utc_now()
    attention_reader = attention_reader or load_current_review_attention
    overlay_reader = overlay_reader or load_current_intraday_review_overlay
    specs = [
        (
            "band_hygiene_from_current_quote_proof",
            [
                sys.executable,
                "scripts\\band_hygiene_freshness_controller.py",
                "--skip-quote-refresh",
                "--skip-technical-refresh",
                "--skip-band-refresh",
                "--write",
                "--validate",
            ],
            240,
        ),
        (
            "finance_decision_sync",
            [sys.executable, "scripts\\finance_decision_sync_spine.py", "--write", "--validate"],
            180,
        ),
        (
            "in_band_review_attention_bridge",
            [sys.executable, "scripts\\in_band_review_attention_bridge.py", "--write", "--validate"],
            120,
        ),
    ]
    steps: list[dict[str, Any]] = []
    core_ok = True
    for name, command, timeout in specs:
        step = command_runner(name, command, timeout)
        steps.append(step)
        if step.get("ok") is not True:
            core_ok = False
            break

    attention_payload: dict[str, Any] = {}
    overlay_payload: dict[str, Any] = {}
    current_attention_tickers: list[str] = []
    fresh_overlay_tickers: list[str] = []
    overlay_step: dict[str, Any]
    evidence_step: dict[str, Any]

    if core_ok and len(steps) == len(specs):
        attention_payload = attention_reader()
        current_attention_tickers = attention_tickers(attention_payload)
        overlay_step = command_runner(
            "wf85_intraday_review_overlay",
            [sys.executable, "scripts\\wf85_intraday_review_overlay.py", "--write", "--validate"],
            90,
        )
        overlay_payload = overlay_reader()
        if overlay_step.get("ok") is True:
            fresh_overlay_tickers = review_only_overlay_tickers(overlay_payload)
            if fresh_overlay_tickers:
                evidence_step = command_runner(
                    "targeted_ticker_card_evidence_refresh",
                    [
                        sys.executable,
                        "scripts\\finance_ticker_card_refresh_gate.py",
                        "--tickers",
                        *fresh_overlay_tickers,
                        "--skip-provider-refresh",
                        "--full-answer-mode",
                        "never",
                        "--write",
                        "--validate",
                    ],
                    150,
                )
            else:
                evidence_step = skipped_review_step(
                    "targeted_ticker_card_evidence_refresh",
                    "no_current_review_only_overlay_tickers",
                    ok=True,
                )
        else:
            evidence_step = skipped_review_step(
                "targeted_ticker_card_evidence_refresh",
                "intraday_review_overlay_not_clean",
                ok=False,
            )
    else:
        overlay_step = skipped_review_step("wf85_intraday_review_overlay", "core_review_sync_not_clean", ok=False)
        evidence_step = skipped_review_step(
            "targeted_ticker_card_evidence_refresh",
            "core_review_sync_not_clean",
            ok=False,
        )
    steps.extend([overlay_step, evidence_step])

    # Always rebuild the review queue, even on a failed upstream repair.  The
    # queue degrades the affected attention row instead of hiding it, while its
    # own freshness/authority checks prevent stale overlay rows from reading as
    # current or approval-ready.
    queue_step = run_review_visibility_queue_refresh(command_runner)
    steps.append(queue_step)
    all_ok = all(step.get("ok") is True for step in steps)
    return {
        "requested": True,
        "attempted": True,
        "ok": bool(steps) and all_ok,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "steps": steps,
        "attention_tickers": current_attention_tickers,
        "overlay_tickers": fresh_overlay_tickers,
        "overlay_status": overlay_payload.get("status") if overlay_payload else None,
        "evidence_refresh_tickers": fresh_overlay_tickers if evidence_step.get("attempted") is not False else [],
        "visibility_queue_status": queue_step.get("ok"),
        "visibility_queue_refresh_attempted": True,
        "scope": (
            "Refresh review-only band-hygiene, decision-sync, attention, intraday-overlay, targeted official-evidence, and WF85 visibility artifacts from an already-fresh quote proof; "
            "no provider refresh, full-answer/approval-card rebuild, canonical/portfolio apply, capital approval, or execution."
        ),
    }


def load_current_review_attention() -> dict[str, Any]:
    payload = load_json_artifact(REVIEW_ATTENTION)
    return payload if isinstance(payload, dict) else {}


def build_report(
    *,
    fundamentals: dict[str, Any],
    warning_router: dict[str, Any],
    quote_proof: dict[str, Any],
    quote_validation: dict[str, Any],
    source_present: dict[str, bool],
    source_warnings: list[str],
    band_proposals: dict[str, Any] | None = None,
    auto_router: dict[str, Any] | None = None,
    band_hygiene: dict[str, Any] | None = None,
    decision_sync: dict[str, Any] | None = None,
    prior_review_attention: dict[str, Any] | None = None,
    execute_safe: bool = False,
    quote_recheck_runner: Callable[[], dict[str, Any]] = run_safe_quote_recheck,
    review_sync_runner: Callable[[], dict[str, Any]] = run_review_sync,
    visibility_queue_refresh_runner: Callable[[], dict[str, Any]] = run_review_visibility_queue_refresh,
    review_attention_reader: Callable[[], dict[str, Any]] = load_current_review_attention,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a pure, testable controller artifact from current proof inputs."""
    report_generated_at = generated_at_utc or utc_now()
    fundamental_rows = repair_rows_from_sources(fundamentals, warning_router)
    quote_rows = stale_quote_rows(quote_proof)
    queue = merge_repair_queue(fundamental_rows, quote_rows)
    tickers = [item["ticker"] for item in queue]
    ticker_count = len(tickers)
    band_proposals = band_proposals or {}
    auto_router = auto_router or {}
    band_hygiene = band_hygiene or {}
    decision_sync = decision_sync or {}
    prior_review_attention = prior_review_attention or {}
    review_needed, review_trigger_rows, review_trigger_reasons = review_sync_needed(
        quote_proof,
        band_proposals,
        auto_router,
        band_hygiene,
        decision_sync,
        prior_review_attention,
        report_generated_at,
    )

    if ticker_count >= 2:
        classification = "systemic_data_quality"
        chain_posture = "degraded_with_systemic_data_quality"
        status = "warning"
    elif ticker_count == 1:
        classification = "ticker_scoped_repair"
        chain_posture = "completed_with_ticker_repairs"
        status = "warning"
    else:
        classification = "no_action"
        chain_posture = "complete_no_ticker_repair"
        status = "warning" if source_warnings else "no_action"

    quote_recheck = {
        "requested": bool(execute_safe),
        "attempted": False,
        "ok": None,
        "scope": "not requested; controller only observes existing quote proof",
    }
    if execute_safe and quote_rows:
        quote_recheck = quote_recheck_runner()
    elif execute_safe:
        quote_recheck = {
            "requested": True,
            "attempted": False,
            "skipped": True,
            "ok": True,
            "reason": "no_ticker_scoped_quote_freshness_issue",
            "scope": "quote recheck is bounded to identified ticker-scoped quote freshness issues",
        }

    review_sync = {
        "requested": bool(execute_safe),
        "needed": review_needed,
        "attempted": False,
        "ok": None,
        "same_invocation_reload": False,
        "trigger_tickers": [row["ticker"] for row in review_trigger_rows],
        "trigger_reasons": review_trigger_reasons,
        "scope": "not requested; controller only observes existing in-band review attention state",
    }
    refreshed_attention = prior_review_attention
    if execute_safe and review_needed:
        review_sync = review_sync_runner()
        review_sync["needed"] = True
        review_sync["trigger_tickers"] = [row["ticker"] for row in review_trigger_rows]
        review_sync["trigger_reasons"] = review_trigger_reasons
        if review_sync.get("ok") is True:
            refreshed_attention = review_attention_reader()
            review_sync["same_invocation_reload"] = True
            review_sync["attention_artifact_status"] = refreshed_attention.get("status")
            review_sync["attention_fingerprint"] = as_dict(refreshed_attention.get("summary")).get("attention_fingerprint")
    elif execute_safe:
        queue_refresh = visibility_queue_refresh_runner()
        review_sync.update({
            "skipped": True,
            "ok": queue_refresh.get("ok") is True,
            "reason": "no_fresh_tier_ab_in_band_transition_requires_core_review_sync",
            "scope": "core review sync is bounded to a fresh Tier A/B in-band quote; the WF85 visibility queue still refreshes so expired review-only overlays cannot persist.",
            "visibility_queue_refresh_attempted": True,
            "visibility_queue_status": queue_refresh.get("ok"),
            "visibility_queue_refresh": queue_refresh,
        })

    fundamental_tickers = sorted({row["ticker"] for row in fundamental_rows})
    quote_tickers = sorted({row["ticker"] for row in quote_rows})
    warnings = sorted(set(source_warnings))
    if quote_validation and quote_validation.get("status") not in {None, "ok"}:
        warnings.append(f"quote_validation_status:{quote_validation.get('status')}")
    if quote_proof and quote_proof.get("status") not in {None, "ok"}:
        warnings.append(f"quote_proof_status:{quote_proof.get('status')}")
    if quote_recheck.get("attempted") and quote_recheck.get("ok") is not True:
        warnings.append("safe_quote_recheck_not_clean")
    if quote_recheck.get("attempted") and quote_recheck.get("ok") is True:
        warnings.append("quote_recheck_completed_reclassification_deferred_to_next_cadence")

    previous_summary = as_dict(prior_review_attention.get("summary"))
    refreshed_summary = as_dict(refreshed_attention.get("summary"))
    attention_count = int(refreshed_summary.get("review_attention_count") or 0) + int(refreshed_summary.get("repair_attention_count") or 0)
    prior_fingerprint = previous_summary.get("attention_fingerprint")
    refreshed_fingerprint = refreshed_summary.get("attention_fingerprint")
    attention_new_or_changed = bool(
        review_sync.get("ok") is True
        and attention_count > 0
        and refreshed_fingerprint
        and refreshed_fingerprint != prior_fingerprint
    )
    if review_sync.get("attempted") and review_sync.get("ok") is not True:
        warnings.append("review_attention_sync_not_clean")
    if review_sync.get("visibility_queue_refresh_attempted") is True and review_sync.get("visibility_queue_status") is not True:
        warnings.append("review_visibility_queue_not_clean")
    if review_sync.get("attempted") and review_sync.get("ok") is True and refreshed_attention.get("status") != "ok":
        warnings.append(f"review_attention_artifact_status:{refreshed_attention.get('status')}")

    review_sync_degraded = (
        bool(review_needed) and (
            not execute_safe
            or review_sync.get("ok") is not True
            or refreshed_attention.get("status") != "ok"
        )
    ) or (
        execute_safe
        and review_sync.get("visibility_queue_refresh_attempted") is True
        and review_sync.get("visibility_queue_status") is not True
    )
    if review_needed and not execute_safe:
        warnings.append("review_attention_sync_requires_execute_safe")

    if ticker_count == 0 and attention_new_or_changed:
        classification = "in_band_review_attention"
        chain_posture = "fresh_quote_review_attention_published"
        status = "warning"
    elif ticker_count == 0 and review_sync_degraded:
        classification = "in_band_review_sync_degraded"
        chain_posture = "fresh_in_band_review_sync_degraded"
        status = "warning"

    report = {
        "schema": SCHEMA,
        "generated_at_utc": report_generated_at,
        "status": status,
        "classification": classification,
        "purpose": "Consolidate same-day ticker data-quality repair work while allowing unrelated refresh branches to remain complete and explicitly caveated.",
        "authority_boundary": deepcopy(AUTHORITY_BOUNDARY),
        "source_artifacts": {
            "fundamental_metrics_validation": rel(FUNDAMENTALS),
            "finance_evidence_warning_router": rel(WARNING_ROUTER),
            "quote_snapshot_proof": rel(QUOTE_PROOF),
            "quote_snapshot_validation": rel(QUOTE_VALIDATION),
            "band_proposals": rel(BAND_PROPOSALS),
            "wf78_auto_router": rel(AUTO_ROUTER),
            "band_hygiene": rel(BAND_HYGIENE),
            "finance_decision_sync": rel(DECISION_SYNC),
            "in_band_review_attention": rel(REVIEW_ATTENTION),
            "wf85_intraday_review_overlay": rel(INTRADAY_REVIEW_OVERLAY),
            "wf85_opportunity_visibility_queue": rel(WF85_VISIBILITY_QUEUE),
            "finance_ticker_card_refresh_gate": rel(TICKER_CARD_REFRESH_GATE),
        },
        "source_presence": {
            "fundamental_metrics_validation_present": bool(source_present.get("fundamentals")),
            "finance_evidence_warning_router_present": bool(source_present.get("warning_router")),
            "quote_snapshot_proof_present": bool(source_present.get("quote_proof")),
            "quote_snapshot_validation_present": bool(source_present.get("quote_validation")),
            "band_proposals_present": bool(source_present.get("band_proposals", bool(band_proposals))),
            "wf78_auto_router_present": bool(source_present.get("auto_router", bool(auto_router))),
            "band_hygiene_present": bool(source_present.get("band_hygiene", bool(band_hygiene))),
            "finance_decision_sync_present": bool(source_present.get("decision_sync", bool(decision_sync))),
            "in_band_review_attention_present": bool(source_present.get("review_attention", bool(prior_review_attention))),
        },
        "summary": {
            "ticker_count": ticker_count,
            "tickers": tickers,
            "fundamental_repair_tickers": fundamental_tickers,
            "quote_freshness_tickers": quote_tickers,
            "manual_source_open_ticker_count": len(fundamental_tickers),
            "unrelated_chain_work_can_remain_complete": True,
            "chain_completion_posture": chain_posture,
            "systemic_data_quality": classification == "systemic_data_quality",
            "same_day_cadence": deepcopy(CADENCE),
            "quote_recheck_reclassification": {
                "same_invocation_reload": False,
                "next_cadence_reclassification_minutes": (
                    CADENCE["cadence_minutes"] if quote_recheck.get("attempted") and quote_recheck.get("ok") is True else None
                ),
                "reason": (
                    "The controller records the proof snapshot observed before the bounded recheck; a successful recheck is classified from refreshed proof on the next scheduled pass."
                    if quote_recheck.get("attempted") and quote_recheck.get("ok") is True else "No successful bounded quote-proof recheck requires deferred reclassification."
                ),
            },
            "in_band_review_attention": {
                "trigger_tickers": [row["ticker"] for row in review_trigger_rows],
                "refresh_needed": review_needed,
                "refresh_attempted": review_sync.get("attempted") is True,
                "same_invocation_reload": review_sync.get("same_invocation_reload") is True,
                "review_attention_count": int(refreshed_summary.get("review_attention_count") or 0),
                "review_attention_tickers": as_list(refreshed_summary.get("review_attention_tickers")),
                "repair_attention_count": int(refreshed_summary.get("repair_attention_count") or 0),
                "repair_attention_tickers": as_list(refreshed_summary.get("repair_attention_tickers")),
                "attention_new_or_changed": attention_new_or_changed,
                "attention_fingerprint": refreshed_fingerprint,
                "sync_degraded": review_sync_degraded,
                "current_attention_tickers": as_list(review_sync.get("attention_tickers")),
                "intraday_review_overlay_status": review_sync.get("overlay_status"),
                "intraday_review_overlay_tickers": as_list(review_sync.get("overlay_tickers")),
                "targeted_evidence_refresh_tickers": as_list(review_sync.get("evidence_refresh_tickers")),
                "wf85_visibility_queue_refresh_clean": review_sync.get("visibility_queue_status"),
            },
            "next_safe_action": (
                "Autonomous intraday review/evidence queue refreshed; separately recheck the listed quote-freshness repairs on the next bounded pass."
                if ticker_count and review_sync.get("ok") is True and as_list(review_sync.get("overlay_tickers")) else
                "Run the existing bounded quote-proof recheck only with --execute-safe; source-open and revalidate fundamentals manually per ticker."
                if ticker_count else
                "Review the fresh in-band attention artifact; resolve listed evidence or technical conflicts before capital-review language."
                if attention_new_or_changed else
                "A fresh Tier A/B in-band setup or review-queue refresh has non-clean proof; run the bounded --execute-safe sync or repair its blocked source before any capital-review language."
                if review_sync_degraded else
                "No ticker-specific repair or newly changed in-band review attention is currently identified; continue ordinary review-only freshness monitoring."
            ),
        },
        "repair_queue": queue,
        "execution_record": {
            "mode": "execute_safe" if execute_safe else "observe_only",
            "quote_proof_recheck": quote_recheck,
            "in_band_review_sync": review_sync,
            "fundamental_action": "none",
            "fundamental_source_mapping_mutated": False,
            "canonical_or_portfolio_mutated": False,
            "trade_or_account_action": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        },
        "warnings": sorted(set(warnings)),
        "errors": [],
        "stop_lines": [
            "Fundamental source-period or mapping mismatches remain source-open/manual/revalidate only; this controller must not amend the source or mapping.",
            "A ticker-scoped repair does not make the affected ticker decision-grade; suppress or caveat its affected fields until reconciliation succeeds.",
            "A systemic classification is a degraded data-quality state, not permission for canonical, portfolio, execution, brokerage, account, or schedule mutation.",
            "Only --execute-safe may invoke the existing quote-proof hardening command; default operation is observation and classification only.",
        ],
    }
    report["validation"] = validate_report(report)
    return report


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if report.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if as_dict(report.get("authority_boundary")) != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    summary = as_dict(report.get("summary"))
    queue = as_list(report.get("repair_queue"))
    tickers = [normalize_ticker(as_dict(item).get("ticker")) for item in queue]
    tickers = [ticker for ticker in tickers if ticker]
    if len(tickers) != len(set(tickers)):
        errors.append("repair_queue_not_deduplicated_by_ticker")
    if int(summary.get("ticker_count") or 0) != len(tickers):
        errors.append("ticker_count_mismatch")
    if summary.get("tickers") != sorted(tickers):
        errors.append("ticker_list_mismatch")
    expected = (
        "systemic_data_quality" if len(tickers) >= 2
        else "ticker_scoped_repair" if len(tickers) == 1
        else "in_band_review_attention"
        if as_dict(summary.get("in_band_review_attention")).get("attention_new_or_changed") is True
        else "in_band_review_sync_degraded"
        if as_dict(summary.get("in_band_review_attention")).get("sync_degraded") is True
        else "no_action"
    )
    if report.get("classification") != expected:
        errors.append("classification_threshold_mismatch")
    for item in queue:
        row = as_dict(item)
        if row.get("fundamental_repairs") and row.get("automatic_fundamental_repair_allowed") is not False:
            errors.append(f"fundamental_auto_repair_enabled:{row.get('ticker')}")
        if row.get("fundamental_repairs") and row.get("repair_mode") != "manual_source_open_and_revalidate":
            errors.append(f"fundamental_repair_mode_invalid:{row.get('ticker')}")
    execution = as_dict(report.get("execution_record"))
    for key in [
        "fundamental_source_mapping_mutated",
        "canonical_or_portfolio_mutated",
        "trade_or_account_action",
        "capital_deployment_approved",
        "trade_or_execution_approved",
    ]:
        if execution.get(key) is not False:
            errors.append(f"forbidden_execution_record:{key}")
    attention = as_dict(summary.get("in_band_review_attention"))
    if attention.get("attention_new_or_changed") is True and report.get("classification") != "in_band_review_attention" and not tickers:
        errors.append("review_attention_classification_missing")
    if attention.get("sync_degraded") is True and report.get("classification") != "in_band_review_sync_degraded" and not tickers:
        errors.append("review_attention_sync_degraded_classification_missing")
    if report.get("warnings"):
        warnings.extend(str(item) for item in as_list(report.get("warnings")))
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": sorted(set(warnings))}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fundamentals", type=Path, default=FUNDAMENTALS)
    parser.add_argument("--warning-router", type=Path, default=WARNING_ROUTER)
    parser.add_argument("--quote-proof", type=Path, default=QUOTE_PROOF)
    parser.add_argument("--quote-validation", type=Path, default=QUOTE_VALIDATION)
    parser.add_argument("--band-proposals", type=Path, default=BAND_PROPOSALS)
    parser.add_argument("--tier-router", type=Path, default=AUTO_ROUTER)
    parser.add_argument("--band-hygiene", type=Path, default=BAND_HYGIENE)
    parser.add_argument("--decision-sync", type=Path, default=DECISION_SYNC)
    parser.add_argument("--review-attention", type=Path, default=REVIEW_ATTENTION)
    parser.add_argument(
        "--execute-safe",
        action="store_true",
        help="Run bounded quote-hardening and, only for fresh Tier A/B in-band transitions, review-only hygiene/decision/attention sync.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fundamentals, fundamentals_present, fundamentals_warnings = load_source(args.fundamentals, "fundamentals")
    router, router_present, router_warnings = load_source(args.warning_router, "warning_router")
    quote_proof, quote_proof_present, quote_proof_warnings = load_source(args.quote_proof, "quote_proof")
    quote_validation, quote_validation_present, quote_validation_warnings = load_source(args.quote_validation, "quote_validation")
    band_proposals, band_proposals_present, band_proposals_warnings = load_source(args.band_proposals, "band_proposals")
    auto_router, auto_router_present, auto_router_warnings = load_source(args.tier_router, "auto_router")
    band_hygiene, band_hygiene_present, band_hygiene_warnings = load_source(args.band_hygiene, "band_hygiene")
    decision_sync, decision_sync_present, decision_sync_warnings = load_source(args.decision_sync, "decision_sync")
    prior_review_attention = load_json_artifact(args.review_attention) if args.review_attention.exists() else {}
    if not isinstance(prior_review_attention, dict):
        prior_review_attention = {}
    report = build_report(
        fundamentals=fundamentals,
        warning_router=router,
        quote_proof=quote_proof,
        quote_validation=quote_validation,
        source_present={
            "fundamentals": fundamentals_present,
            "warning_router": router_present,
            "quote_proof": quote_proof_present,
            "quote_validation": quote_validation_present,
            "band_proposals": band_proposals_present,
            "auto_router": auto_router_present,
            "band_hygiene": band_hygiene_present,
            "decision_sync": decision_sync_present,
            "review_attention": args.review_attention.exists(),
        },
        source_warnings=[
            *fundamentals_warnings,
            *router_warnings,
            *quote_proof_warnings,
            *quote_validation_warnings,
            *band_proposals_warnings,
            *auto_router_warnings,
            *band_hygiene_warnings,
            *decision_sync_warnings,
        ],
        band_proposals=band_proposals,
        auto_router=auto_router,
        band_hygiene=band_hygiene,
        decision_sync=decision_sync,
        prior_review_attention=prior_review_attention,
        execute_safe=args.execute_safe,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(
        "ticker_data_repair_controller: "
        f"status={report['status']} classification={report['classification']} "
        f"tickers={report['summary']['ticker_count']} "
        f"quote_recheck={report['execution_record']['quote_proof_recheck'].get('attempted')} "
        f"review_sync={report['execution_record']['in_band_review_sync'].get('attempted')}"
    )
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
