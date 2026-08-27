#!/usr/bin/env python3
"""Review-only ticker-card refresh gate for finance intelligence.

This runner refreshes upstream evidence, rebuilds ticker-card artifacts, and
classifies remaining stale-card reasons. It intentionally grants no canon,
portfolio, import, promotion, approval, paper, live, or account authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import FinanceSqlCanonAccess


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUTPUT = TMP / "finance-ticker-card-refresh-gate.json"
DEFAULT_CARD_SUMMARY = TMP / "ticker-card-refresh-gate-card-build-summary.json"

FINANCE_STATE_VALIDATION = TMP / "finance-intelligence-state-validation.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"
PRICE_FRESHNESS_BRIDGE = TMP / "wf77-price-freshness-bridge.json"
PRICE_STATE_CURRENT = ROOT / "data" / "market" / "price-snapshots" / "wf77-price-state-current.json"
FINANCE_COVERAGE = TMP / "finance-data-coverage-current.json"
SQL_CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
PRICE_DRIFT_TOLERANCE = 0.02
FULL_ANSWER_MODES = {"changed", "always", "never"}
LEGACY_PRODUCTION_COMPATIBILITY_COUNT = 42

AUTHORITY = {
    "review_only": True,
    "report_only": True,
    "ticker_card_review_artifact_rebuild_allowed": True,
    "durable_sql_canon_current_state_allowed": True,
    "canon_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sql_first_answer_allowed": False,
    "sql_canon_mutation_allowed": False,
    "import_apply_allowed": False,
    "production_promotion_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_execution_allowed": False,
    "live_execution_allowed": False,
    "account_action_allowed": False,
    "owner_approval_inferred": False,
}


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def run_command(args: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        shell=False,
    )
    ended = datetime.now(timezone.utc).isoformat()
    elapsed = (
        datetime.fromisoformat(ended) - datetime.fromisoformat(started)
    ).total_seconds()
    return {
        "command": args,
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_seconds": round(elapsed, 3),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def provider_refresh_commands(tickers: list[str] | None = None) -> list[list[str]]:
    python = sys.executable
    shard = list(tickers or [])
    if shard:
        return [
            [python, "scripts\\earnings_calendar_enrichment.py", "--tickers", *shard, "--merge-existing"],
            [python, "scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"],
            [python, "scripts\\fundamental_metrics_refresh.py", "--tickers", *shard, "--merge-existing", "--no-history"],
            [python, "scripts\\analyst_consensus_refresh.py", "--tickers", *shard, "--write", "--validate", "--merge-existing"],
        ]
    return [
        [python, "scripts\\technical_refresh.py"],
        [python, "scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"],
        [python, "scripts\\fundamental_metrics_refresh.py", "--merge-existing", "--no-history"],
        [python, "scripts\\analyst_consensus_refresh.py", "--write", "--validate", "--merge-existing"],
    ]


def earnings_rollforward_guard_command(tickers: list[str] | None = None) -> list[str]:
    """Return the pre-refresh missed-earnings guard command.

    Explicit ticker shards are checked exactly; broad refreshes use the
    priority/event-sensitive universe so a missed scheduler window is detected
    before provider refresh and card rebuild.  The guard is review-only and
    may auto-capture only an explicitly proven parser/source pair.
    """
    command = [
        sys.executable,
        "scripts\\earnings_rollforward_guard.py",
        "--auto-capture",
        "--write",
        "--validate",
    ]
    if tickers:
        for ticker in tickers:
            command.extend(["--ticker", ticker])
    else:
        command.append("--priority-only")
    return command


def post_earnings_reconciliation_commands() -> list[list[str]]:
    """Return the one conditional rebuild chain after a new source capture.

    It intentionally does not run on an unchanged guard: source discovery stays
    cheap, and alerts represent a real unresolved capture/transport failure, not
    ordinary review-only field reconciliation debt.
    """
    python = sys.executable
    return [
        [python, "scripts\\official_capture_period_registry.py", "--write"],
        [python, "scripts\\fundamental_ir_reconciliation_packets.py", "--write"],
        [python, "scripts\\validate_fundamental_ir_reconciliation.py", "--write"],
        [python, "scripts\\official_earnings_bridge.py", "--write"],
        [python, "scripts\\validate_official_earnings_bridge.py", "--write"],
    ]


def guard_requires_reconciliation(guard: dict[str, Any] | None) -> bool:
    summary = as_dict((guard or {}).get("summary"))
    return any(
        int(summary.get(key) or 0) > 0
        for key in (
            "updated_review_only_count",
            "source_verified_pending_reconciliation_count",
        )
    )


def card_refresh_commands(card_summary: Path, tickers: list[str] | None = None) -> list[list[str]]:
    python = sys.executable
    card_args = [python, "scripts\\ticker_intelligence_card.py"]
    for ticker in tickers or []:
        card_args.extend(["--ticker", ticker])
    if not tickers:
        card_args.append("--all-from-coverage")
    card_args.extend(["--summary-output", str(card_summary)])
    return [
        [python, "scripts\\finance_data_coverage.py", "--validate", "--write-contract"],
        card_args,
        [python, "scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"],
    ]


def full_answer_command() -> list[str]:
    return [
        sys.executable,
        "scripts\\trade_grade_full_answer_assembler.py",
        "--all-wf84",
        "--write",
        "--validate",
    ]


def state_validation_commands(*, refresh_state: bool = True) -> list[list[str]]:
    python = sys.executable
    commands: list[list[str]] = []
    if refresh_state:
        commands.append([python, "scripts\\finance_intelligence_state.py", "refresh-100", "--pretty"])
    commands.extend([
        [python, "scripts\\finance_intelligence_state.py", "validate", "--pretty"],
        [python, "scripts\\finance_intelligence_state.py", "stale-tickers", "--pretty", "--limit", "500"],
    ])
    return commands


def build_commands(
    skip_provider_refresh: bool,
    card_summary: Path,
    full_answer_mode: str = "always",
    tickers: list[str] | None = None,
) -> list[list[str]]:
    """Return the static command plan for callers/tests.

    ``changed`` is runtime-dependent, so the static plan shows the fast path.
    ``build_packet`` records whether the full-answer command actually ran.
    """
    commands: list[list[str]] = []
    commands.append(earnings_rollforward_guard_command(tickers))
    if not skip_provider_refresh:
        commands.extend(provider_refresh_commands(tickers))
    commands.extend(card_refresh_commands(card_summary, tickers))
    if full_answer_mode == "always":
        commands.append(full_answer_command())
    commands.extend(state_validation_commands(refresh_state=not tickers and not skip_provider_refresh))
    return commands


def strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_volatile(child)
            for key, child in sorted(value.items())
            if key
            not in {
                "generated_at_utc",
                "generated_utc",
                "started_utc",
                "ended_utc",
                "started_at_utc",
                "completed_at_utc",
                "finished_at_utc",
                "elapsed_seconds",
                "stdout_tail",
                "stderr_tail",
                "stdout_preview",
                "stderr_preview",
                "age_hours",
                "file_mtime_utc",
            }
            and not key.endswith("_generated_at_utc")
            and not key.endswith("_generated_utc")
        }
    if isinstance(value, (list, tuple)):
        normalized = [strip_volatile(item) for item in value]
        if all(isinstance(item, dict) and "ticker" in item for item in normalized):
            return sorted(normalized, key=lambda item: str(item.get("ticker")))
        return normalized
    return value


def semantic_digest(*payloads: Any) -> str:
    normalized = strip_volatile(payloads)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def previous_full_answer_digest(output: Path) -> str | None:
    previous = load_json(output)
    if not isinstance(previous, dict):
        return None
    full_answer = as_dict(as_dict(previous.get("summary")).get("full_answer_rebuild"))
    digest = full_answer.get("source_digest")
    return str(digest) if digest else None


def full_answer_rebuild_decision(
    mode: str,
    previous_digest: str | None,
    source_digest: str,
) -> dict[str, Any]:
    if mode == "always":
        should_run = True
        reason = "full_answer_mode_always"
    elif mode == "never":
        should_run = False
        reason = "full_answer_mode_never"
    else:
        should_run = previous_digest != source_digest
        reason = "source_digest_changed" if should_run else "source_digest_unchanged"
    return {
        "mode": mode,
        "previous_source_digest": previous_digest,
        "source_digest": source_digest,
        "source_digest_changed": previous_digest != source_digest,
        "command_run": should_run,
        "skip_reason": None if should_run else reason,
        "run_reason": reason if should_run else None,
    }


def summarize_cards(card_summary: dict[str, Any] | None, stale_tickers: set[str] | None = None) -> dict[str, Any]:
    stale_tickers = stale_tickers or set()
    if not isinstance(card_summary, dict):
        return {
            "status": "missing",
            "card_count": 0,
            "cards_with_missing_or_stale": None,
            "missing_or_stale_total": None,
            "card_build_complete_count": 0,
            "decision_ready_card_count": 0,
            "approval_ready_card_count": 0,
        }
    cards = card_summary.get("cards") or []
    cards_with_gaps = 0
    missing_total = 0
    card_build_complete = 0
    approval_ready = 0
    recommendation_counts: dict[str, int] = {}
    top_gap_examples: list[dict[str, Any]] = []
    for card in cards:
        missing_or_stale = card.get("missing_or_stale") or []
        if isinstance(missing_or_stale, list):
            missing_count = len(missing_or_stale)
        else:
            missing_or_stale = []
            missing_count = 0
        if "missing_or_stale_count" in card:
            try:
                missing_count = int(card.get("missing_or_stale_count") or 0)
            except (TypeError, ValueError):
                missing_count = len(missing_or_stale)
        if missing_count:
            cards_with_gaps += 1
            missing_total += missing_count
            if len(top_gap_examples) < 25:
                top_gap_examples.append(
                    {
                        "ticker": card.get("ticker"),
                        "missing_or_stale": missing_or_stale,
                        "missing_or_stale_count": missing_count,
                        "card_path": card.get("card_path") or card.get("path"),
                    }
                )
        support = str(card.get("recommendation_support") or "unknown")
        support_key = support.lower().replace(" ", "_").replace("-", "_")
        recommendation_counts[support] = recommendation_counts.get(support, 0) + 1
        ticker = str(card.get("ticker") or "")
        if card.get("card_path") or card.get("path"):
            card_build_complete += 1
        if ticker not in stale_tickers and missing_count == 0 and support_key.startswith("approval_ready"):
            approval_ready += 1
    return {
        "status": card_summary.get("status", "unknown"),
        "card_count": card_summary.get("card_count", len(cards)),
        "cards_with_missing_or_stale": cards_with_gaps,
        "missing_or_stale_total": missing_total,
        "card_build_complete_count": card_build_complete,
        "decision_ready_card_count": approval_ready,
        "approval_ready_card_count": approval_ready,
        "readiness_semantics": {
            "card_build_complete_count": "cards rebuilt into local evidence-cache artifacts",
            "decision_ready_card_count": "approval-support-ready cards only; does not imply owner approval",
        },
        "recommendation_support_counts": recommendation_counts,
        "top_gap_examples": top_gap_examples,
    }


def self_test() -> dict[str, Any]:
    summary = summarize_cards(
        {
            "status": "ok",
            "card_count": 3,
            "cards": [
                {
                    "ticker": "AAA",
                    "path": "tmp/AAA.json",
                    "missing_or_stale_count": 0,
                    "recommendation_support": "approval-ready paper starter if fresh in band",
                },
                {
                    "ticker": "BBB",
                    "path": "tmp/BBB.json",
                    "missing_or_stale_count": 1,
                    "recommendation_support": "approval-ready paper starter if fresh in band",
                },
                {
                    "ticker": "CCC",
                    "path": "tmp/CCC.json",
                    "missing_or_stale_count": 0,
                    "recommendation_support": "monitor-only",
                },
            ],
        },
        {"BBB"},
    )
    errors: list[str] = []
    if summary.get("card_build_complete_count") != 3:
        errors.append("card_build_complete_count_did_not_count_rebuilt_cards")
    if summary.get("decision_ready_card_count") != 1 or summary.get("approval_ready_card_count") != 1:
        errors.append("decision_ready_count_includes_non_approval_or_stale_cards")
    return {
        "status": "ok" if not errors else "blocked",
        "tests": {
            "card_build_complete_split_from_decision_ready": summary.get("card_build_complete_count") == 3
            and summary.get("decision_ready_card_count") == 1,
            "stale_card_not_decision_ready": summary.get("decision_ready_card_count") < summary.get("card_build_complete_count"),
        },
        "errors": errors,
        "sample_summary": summary,
    }


def summarize_stale(stale_packet: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stale_packet, dict):
        return {"status": "missing", "stale_count": None, "repair_queue": []}
    stale_cards = stale_packet.get("stale_ticker_cards") or []
    repair_queue = []
    for item in stale_cards:
        repair_queue.append(
            {
                "ticker": item.get("ticker"),
                "stale_reasons": item.get("stale_reasons")
                or item.get("missing_or_stale")
                or [],
                "card_path": item.get("card_path"),
            }
        )
    return {
        "status": stale_packet.get("status", "unknown"),
        "stale_count": len(stale_cards),
        "repair_queue": repair_queue,
    }


def universe_scope_index(db_path: Path = FINANCE_STATE_DB) -> dict[str, dict[str, Any]]:
    if not db_path.exists():
        return {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        records = conn.execute(
            """
            SELECT ticker, tier, universe_scope, production_answer_path_member, thin_monitor_row
            FROM universe
            """
        ).fetchall()
    return {str(row["ticker"]).upper(): dict(row) for row in records}


DECISION_TIERS = {"A", "B"}


def normalize_tier(tier: Any) -> str:
    """Normalize 'Tier A' / 'a' / 'A' to 'A'."""
    text = str(tier or "").strip().upper()
    if text.startswith("TIER"):
        text = text[4:].strip()
    return text


def is_decision_tier(tier: Any) -> bool:
    """Tier A/B carry real freshness debt regardless of production answer-path state."""
    return normalize_tier(tier) in DECISION_TIERS


def sql_canon_scope_index(base_scope: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    context: dict[str, Any] = {
        "schema": "veritas.finance_ticker_card_refresh_gate.sql_canon_scope.v1",
        "status": "blocked",
        "sql_canon_db": rel(SQL_CANON_DB),
        "typed_access_layer": "scripts/finance_sql_canon_access.py",
        "production_answer_count": None,
        "base_scope_count": len(base_scope),
        "missing_from_sql": [],
        "missing_from_base_scope": [],
        "scope_diff": {},
        "registry_summary": {},
        "validation": {"status": "blocked", "errors": [], "warnings": []},
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    overlay = {ticker: dict(row) for ticker, row in base_scope.items()}
    try:
        client = FinanceSqlCanonAccess(SQL_CANON_DB)
        validation = client.validate()
        context["access_validation_status"] = validation.get("status")
        if validation.get("status") != "ok":
            context["validation"]["errors"].append({"sql_canon_access_blocked": validation.get("errors")})
            return context, overlay
        states = client.ticker_states(base_scope.keys())
        production = set(client.production_answer_tickers())
        legacy = set(client.legacy_production_answer_tickers())
        if not production:
            context["validation"]["warnings"].append("production_grade_set_empty_wait_for_decision_grade_gates")
        base_production = {
            ticker
            for ticker, row in base_scope.items()
            if bool(row.get("production_answer_path_member"))
        }
        context["production_answer_count"] = len(production)
        context["legacy_production_answer_count"] = len(legacy)
        context["effective_production_answer_count"] = len(production)
        context["legacy_42_retired_from_blocking"] = True
        context["legacy_42_count_advisory_only"] = True
        context["registry_summary"] = client.migration_registry_summary()
        context["missing_from_sql"] = sorted(set(base_scope) - set(states))
        context["missing_from_base_scope"] = sorted(set(states) - set(base_scope))
        context["scope_diff"] = {
            "extra_in_sql_production": sorted(production - base_production),
            "missing_from_sql_production": sorted(base_production - production),
            "legacy_base_scope_retired_from_blocking": True,
        }
        decision_tier_non_production: list[str] = []
        for ticker, state in states.items():
            row = overlay.setdefault(ticker, {})
            is_production = ticker in production
            decision_tier = is_decision_tier(state.legacy_tier)
            base_thin = base_scope.get(ticker, {}).get("thin_monitor_row")
            # Thin-monitor means Tier C / review-monitor scope. An unopened
            # production answer path must not silently reclassify Tier A/B as
            # expected context, which would hide real freshness debt.
            thin_monitor = (not is_production) if base_thin is None else bool(base_thin)
            if decision_tier:
                thin_monitor = False
                if not is_production:
                    decision_tier_non_production.append(ticker)
            row["ticker"] = ticker
            row["tier"] = state.legacy_tier
            row["universe_scope"] = state.universe_scope
            row["production_answer_path_member"] = is_production
            row["thin_monitor_row"] = thin_monitor
            row["decision_tier_row"] = decision_tier
            row["sql_canon_scope_source"] = True
        context["decision_tier_non_production_count"] = len(decision_tier_non_production)
        context["decision_tier_non_production_tickers"] = sorted(decision_tier_non_production)
        errors = context["validation"]["errors"]
        if context["missing_from_sql"]:
            errors.append({"base_scope_missing_sql_state": context["missing_from_sql"][:25]})
        if context["scope_diff"]["extra_in_sql_production"] or context["scope_diff"]["missing_from_sql_production"]:
            context["validation"]["warnings"].append({"legacy_base_scope_vs_strategic_production_diff": context["scope_diff"]})
        context["validation"]["status"] = "blocked" if errors else "ok"
        context["status"] = "blocked" if errors else "ok"
    except Exception as exc:  # noqa: BLE001 - refresh gate must fail closed on SQL-canon guard errors.
        context["validation"]["errors"].append({"exception": repr(exc)})
    return context, overlay


def quote_freshness_context_only(item: dict[str, Any]) -> bool:
    reasons = item.get("stale_reasons")
    if not isinstance(reasons, list) or not reasons:
        return False
    for reason in reasons:
        if not isinstance(reason, dict):
            return False
        if reason.get("family") != "fresh_price_quote":
            return False
        if reason.get("severity") not in {"context", "info"}:
            return False
    return True


def context_only(item: dict[str, Any]) -> bool:
    reasons = item.get("stale_reasons")
    if not isinstance(reasons, list) or not reasons:
        return False
    return all(isinstance(reason, dict) and reason.get("severity") in {"context", "info"} for reason in reasons)


def classify_repair_queue(repair_queue: list[dict[str, Any]], scope_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    production: list[dict[str, Any]] = []
    expected_context: list[dict[str, Any]] = []
    quote_freshness_context: list[dict[str, Any]] = []
    production_expected_context: list[dict[str, Any]] = []
    decision_tier_stale: list[str] = []
    for item in repair_queue:
        ticker = str(item.get("ticker") or "").upper()
        scope = scope_index.get(ticker, {})
        decision_tier = is_decision_tier(scope.get("tier"))
        thin_monitor = bool(scope.get("thin_monitor_row")) and not decision_tier
        production_member = bool(scope.get("production_answer_path_member"))
        quote_context = quote_freshness_context_only(item)
        non_blocking_context = context_only(item)
        enriched_item = {
            **item,
            "tier": scope.get("tier"),
            "universe_scope": scope.get("universe_scope"),
            "production_answer_path_member": production_member,
            "thin_monitor_row": thin_monitor,
            "decision_tier_row": decision_tier,
            "repair_scope": (
                "thin_monitor_expected_context"
                if thin_monitor and not production_member
                else "fresh_quote_required_context"
                if quote_context
                else "production_expected_context"
                if non_blocking_context
                else "production_answer_path"
            ),
        }
        enriched.append(enriched_item)
        if decision_tier:
            decision_tier_stale.append(ticker)
        if thin_monitor and not production_member:
            expected_context.append(enriched_item)
        elif quote_context:
            quote_freshness_context.append(enriched_item)
        elif non_blocking_context:
            production_expected_context.append(enriched_item)
        else:
            production.append(enriched_item)
    return {
        "repair_queue": enriched,
        "production_repair_queue": production,
        "thin_monitor_expected_context_queue": expected_context,
        "fresh_quote_required_context_queue": quote_freshness_context,
        "production_expected_context_queue": production_expected_context,
        "production_repair_count": len(production),
        "thin_monitor_expected_context_count": len(expected_context),
        "fresh_quote_required_context_count": len(quote_freshness_context),
        "production_expected_context_count": len(production_expected_context),
        "decision_tier_stale_count": len(decision_tier_stale),
        "decision_tier_stale_tickers": sorted(decision_tier_stale),
    }


def summarize_stale_scope(db_path: Path = FINANCE_STATE_DB) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "status": "missing",
            "all_stale_count": None,
            "production_answer_path_stale_count": None,
            "thin_monitor_stale_count": None,
            "production_answer_path_total": None,
            "thin_monitor_total": None,
        }
    with sqlite3.connect(db_path) as conn:
        all_stale = conn.execute("SELECT COUNT(*) FROM stale_ticker_cards").fetchone()[0]
        prod_stale = conn.execute(
            """
            SELECT COUNT(*)
            FROM stale_ticker_cards s
            JOIN universe u ON u.ticker = s.ticker
            WHERE u.production_answer_path_member = 1
            """
        ).fetchone()[0]
        thin_stale = conn.execute(
            """
            SELECT COUNT(*)
            FROM stale_ticker_cards s
            JOIN universe u ON u.ticker = s.ticker
            WHERE u.thin_monitor_row = 1
            """
        ).fetchone()[0]
        prod_total = conn.execute(
            "SELECT COUNT(*) FROM universe WHERE production_answer_path_member = 1"
        ).fetchone()[0]
        thin_total = conn.execute(
            "SELECT COUNT(*) FROM universe WHERE thin_monitor_row = 1"
        ).fetchone()[0]
    return {
        "status": "ok",
        "all_stale_count": all_stale,
        "production_answer_path_stale_count": prod_stale,
        "thin_monitor_stale_count": thin_stale,
        "production_answer_path_total": prod_total,
        "thin_monitor_total": thin_total,
    }


def summarize_price_bridge(price_bridge: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(price_bridge, dict):
        return {"status": "missing"}
    return {
        "status": price_bridge.get("status"),
        "freshness_status": price_bridge.get("freshness_status"),
        "tickers_checked": price_bridge.get("tickers_checked"),
        "fresh_count": price_bridge.get("fresh_count"),
        "stale_count": price_bridge.get("stale_count"),
        "authority": price_bridge.get("authority"),
    }


def summarize_card_price_drift(price_state: dict[str, Any] | None, scope_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(price_state, dict):
        return {
            "status": "missing",
            "production_price_drift_count": None,
            "drift_tolerance": PRICE_DRIFT_TOLERANCE,
            "drift_rows": [],
        }
    rows = price_state.get("rows") or []
    drift_rows: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        scope = scope_index.get(ticker, {})
        if not scope.get("production_answer_path_member"):
            continue
        price_state_row = row.get("price_state") if isinstance(row.get("price_state"), dict) else {}
        card_context = row.get("card_price_context") if isinstance(row.get("card_price_context"), dict) else {}
        if price_state_row.get("status") != "ok":
            continue
        fresh_price = price_state_row.get("latest_close")
        card_price = card_context.get("card_latest_known_price")
        try:
            diff = round(float(fresh_price) - float(card_price), 4)
        except (TypeError, ValueError):
            continue
        if abs(diff) <= PRICE_DRIFT_TOLERANCE:
            continue
        drift_rows.append({
            "ticker": ticker,
            "fresh_latest_close": fresh_price,
            "card_latest_known_price": card_price,
            "fresh_minus_card_price": diff,
            "price_data_date": price_state_row.get("data_date"),
            "price_source": price_state_row.get("source"),
            "card_generated_at_utc": card_context.get("card_generated_at_utc"),
            "card_path": card_context.get("card_path"),
            "production_answer_path_member": bool(scope.get("production_answer_path_member")),
            "tier": scope.get("tier"),
            "repair_scope": "production_card_price_drift",
        })
    return {
        "status": "ok" if not drift_rows else "warning",
        "production_price_drift_count": len(drift_rows),
        "drift_tolerance": PRICE_DRIFT_TOLERANCE,
        "drift_rows": drift_rows,
        "source": rel(PRICE_STATE_CURRENT),
    }


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    TMP.mkdir(parents=True, exist_ok=True)
    card_summary_path = Path(args.card_summary_output)
    if not card_summary_path.is_absolute():
        card_summary_path = ROOT / card_summary_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    command_results: list[dict[str, Any]] = []
    commands: list[list[str]] = []
    tickers = sorted({str(ticker).upper() for ticker in (args.tickers or []) if str(ticker).strip()})
    guard_command = earnings_rollforward_guard_command(tickers)
    commands.append(guard_command)
    command_results.append(run_command(guard_command))
    rollforward_guard = load_json(TMP / "earnings-rollforward-guard.json")
    reconciliation_commands: list[list[str]] = []
    if guard_requires_reconciliation(rollforward_guard):
        reconciliation_commands = post_earnings_reconciliation_commands()
        commands.extend(reconciliation_commands)
        command_results.extend(run_command(command) for command in reconciliation_commands)
    if not args.skip_provider_refresh:
        commands.extend(provider_refresh_commands(tickers))
    commands.extend(card_refresh_commands(card_summary_path, tickers))
    command_results.extend(run_command(command) for command in commands[1 + len(reconciliation_commands):])

    card_summary = load_json(card_summary_path)
    price_bridge = load_json(PRICE_FRESHNESS_BRIDGE)
    coverage = load_json(FINANCE_COVERAGE)
    full_answer_source_digest = semantic_digest(card_summary, price_bridge, coverage)
    full_answer_rebuild = full_answer_rebuild_decision(
        args.full_answer_mode,
        previous_full_answer_digest(output_path),
        full_answer_source_digest,
    )
    if full_answer_rebuild["command_run"]:
        command_results.append(run_command(full_answer_command()))

    state_refresh_requested = not tickers and not args.skip_provider_refresh
    state_commands = state_validation_commands(refresh_state=state_refresh_requested)
    command_results.extend(run_command(command) for command in state_commands)

    finance_validation = load_json(FINANCE_STATE_VALIDATION)
    stale_packet = load_json(STALE_TICKERS)
    price_state_current = load_json(PRICE_STATE_CURRENT)
    coverage = load_json(FINANCE_COVERAGE)

    failed = [result for result in command_results if not result["ok"]]
    base_scope_index = universe_scope_index()
    sql_canon_scope, scope_index = sql_canon_scope_index(base_scope_index)
    stale_rollup = summarize_stale(stale_packet)
    stale_scope = summarize_stale_scope()
    queue_classification = classify_repair_queue(stale_rollup["repair_queue"], scope_index)
    card_price_drift = summarize_card_price_drift(price_state_current, scope_index)
    stale_rollup["repair_queue"] = queue_classification["repair_queue"]
    stale_rollup["production_repair_count"] = queue_classification["production_repair_count"]
    stale_rollup["thin_monitor_expected_context_count"] = queue_classification["thin_monitor_expected_context_count"]
    stale_rollup["fresh_quote_required_context_count"] = queue_classification["fresh_quote_required_context_count"]
    stale_rollup["production_expected_context_count"] = queue_classification["production_expected_context_count"]
    stale_tickers = {str(item.get("ticker") or "") for item in queue_classification["production_repair_queue"]}
    card_rollup = summarize_cards(card_summary, stale_tickers)
    coverage_summary = coverage.get("summary") if isinstance(coverage, dict) and isinstance(coverage.get("summary"), dict) else {}
    expected_card_count = (
        len(tickers)
        if tickers
        else int(coverage_summary.get("ticker_count_indexed") or card_rollup["card_count"] or 0)
    )

    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    if failed:
        validation_errors.append(f"{len(failed)} refresh command(s) failed")
    if not isinstance(rollforward_guard, dict):
        validation_errors.append("earnings roll-forward guard artifact is missing")
    else:
        guard_summary = as_dict(rollforward_guard.get("summary"))
        if rollforward_guard.get("status") == "blocked" or int(guard_summary.get("critical_finding_count") or 0) > 0:
            validation_errors.append("earnings roll-forward guard is blocked")
        elif int(guard_summary.get("unresolved_count") or 0) > 0:
            validation_warnings.append(
                f"{guard_summary.get('unresolved_count')} earnings roll-forward item(s) remain manual/catch-up required"
            )
    if card_rollup["status"] not in {"ok", "missing"}:
        validation_warnings.append(f"card summary status is {card_rollup['status']}")
    if expected_card_count and card_rollup["card_count"] != expected_card_count:
        validation_errors.append(f"expected {expected_card_count} ticker cards, got {card_rollup['card_count']}")
    if sql_canon_scope.get("status") != "ok":
        validation_errors.append(f"durable SQL-canon scope guard blocked: {sql_canon_scope.get('validation')}")
    if not isinstance(finance_validation, dict):
        validation_errors.append("finance intelligence validation artifact is missing")
    elif finance_validation.get("status") != "ok":
        validation_errors.append(
            f"finance intelligence validation status is {finance_validation.get('status')}"
        )
    stale_scope["production_answer_path_stale_count"] = queue_classification["production_repair_count"]
    stale_scope["fresh_quote_required_context_count"] = queue_classification["fresh_quote_required_context_count"]
    stale_scope["production_expected_context_count"] = queue_classification["production_expected_context_count"]
    stale_scope["fresh_quote_required_context_rule"] = (
        "Fresh quote required before final approval is expected decision context for ticker cards; exact approval cards still fail closed on quote freshness."
    )
    if stale_scope.get("production_answer_path_stale_count"):
        validation_warnings.append(
            f"{stale_scope['production_answer_path_stale_count']} production answer-path ticker card(s) still need evidence repair"
        )
    if card_price_drift.get("production_price_drift_count"):
        validation_warnings.append(
            f"{card_price_drift['production_price_drift_count']} production answer-path ticker card(s) differ from fresher WF77 price-state rows"
        )
    if stale_scope.get("thin_monitor_stale_count"):
        stale_scope["thin_monitor_expected_context_count"] = queue_classification["thin_monitor_expected_context_count"]
        stale_scope["thin_monitor_expected_context_rule"] = "Tier C/review-monitor absence is expected context and is not production stale debt."
    stale_scope["decision_tier_stale_count"] = queue_classification["decision_tier_stale_count"]
    stale_scope["decision_tier_stale_tickers"] = queue_classification["decision_tier_stale_tickers"]
    stale_scope["decision_tier_stale_rule"] = (
        "Tier A/B staleness is real freshness debt and is never expected thin-monitor context, "
        "regardless of whether the production answer path is open."
    )
    if queue_classification["decision_tier_stale_count"]:
        validation_warnings.append(
            f"{queue_classification['decision_tier_stale_count']} Tier A/B ticker card(s) carry stale evidence"
        )
    if any(
        AUTHORITY[key]
        for key in (
            "canon_mutation_allowed",
            "portfolio_mutation_allowed",
            "import_apply_allowed",
            "production_promotion_allowed",
            "customer_or_external_delivery_allowed",
            "paper_execution_allowed",
            "live_execution_allowed",
            "account_action_allowed",
            "owner_approval_inferred",
        )
    ):
        validation_errors.append("authority boundary widened unexpectedly")

    status = "error" if validation_errors else "ok_with_production_stale_cards"
    if not validation_errors and not stale_scope.get("production_answer_path_stale_count") and (
        stale_scope.get("thin_monitor_stale_count") or stale_scope.get("fresh_quote_required_context_count")
        or stale_scope.get("production_expected_context_count")
    ):
        status = "ok_with_expected_context"
    if not validation_errors and not stale_rollup["stale_count"]:
        status = "ok"

    next_actions = []
    if stale_scope.get("production_answer_path_stale_count"):
        next_actions.append(
            "Use repair_queue to refresh production answer-path evidence families before Tier B/Tier A promotion."
        )
    if stale_scope.get("thin_monitor_stale_count"):
        next_actions.append(
            "Treat Tier C/thin-monitor absence as expected context unless the ticker is promoted toward the production answer path."
        )
    if stale_scope.get("fresh_quote_required_context_count"):
        next_actions.append(
            "Treat fresh-quote-required card context as an approval-card freshness gate, not as stale production-card evidence."
        )
    if stale_scope.get("production_expected_context_count"):
        next_actions.append(
            "Treat production answer-path context-only gaps as enrichment debt; fail closed only on blocking evidence families."
        )
    next_actions.extend(
        [
            "Keep 101-200 WF78 import decision scoped to Tier C review-monitor only.",
            "Run this gate before any production answer-path promotion packet.",
            "Do not infer owner approval, import authority, canon mutation, portfolio mutation, or execution authority.",
        ]
    )

    generated_at_utc = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "generated_at_utc": generated_at_utc,
        "generated_utc": generated_at_utc,
        "status": status,
        "review_scope": "ticker_card_refresh_gate",
        "inputs": {
            "skip_provider_refresh": args.skip_provider_refresh,
            "tickers": tickers,
            "technical_refresh_posture": (
                "not_run_for_explicit_shard_preserves_technical_refresh_entitlement_boundary"
                if tickers
                else "full_entitled_universe_refresh"
            ),
            "full_answer_mode": args.full_answer_mode,
            "card_summary_output": rel(card_summary_path),
            "finance_state_validation": rel(FINANCE_STATE_VALIDATION),
            "stale_tickers": rel(STALE_TICKERS),
            "price_freshness_bridge": rel(PRICE_FRESHNESS_BRIDGE),
            "finance_coverage": rel(FINANCE_COVERAGE),
            "earnings_rollforward_guard": rel(TMP / "earnings-rollforward-guard.json"),
            "post_earnings_reconciliation": [" ".join(command) for command in reconciliation_commands],
            "state_refresh_posture": (
                "broad_refresh_100_for_entitled_full_gate"
                if state_refresh_requested
                else "validate_existing_state_only_for_targeted_or_provider_skipped_gate"
            ),
            "durable_sql_canon_db": rel(SQL_CANON_DB),
        },
        "authority": AUTHORITY,
        "commands": command_results,
        "summary": {
            "command_count": len(command_results),
            "failed_command_count": len(failed),
            "expected_card_count": expected_card_count,
            "card_rollup": card_rollup,
            "stale_rollup": stale_rollup,
            "stale_scope": stale_scope,
            "price_bridge": summarize_price_bridge(price_bridge),
            "card_price_drift": card_price_drift,
            "coverage_status": coverage.get("status") if isinstance(coverage, dict) else "missing",
            "earnings_rollforward_guard": {
                "status": rollforward_guard.get("status") if isinstance(rollforward_guard, dict) else "missing",
                "summary": as_dict(rollforward_guard.get("summary")) if isinstance(rollforward_guard, dict) else {},
                "source": rel(TMP / "earnings-rollforward-guard.json"),
                "reconciliation_triggered": bool(reconciliation_commands),
                "reconciliation_command_count": len(reconciliation_commands),
            },
            "full_answer_rebuild": full_answer_rebuild,
            "sql_canon_scope": sql_canon_scope,
        },
        "repair_queue": stale_rollup["repair_queue"],
        "production_repair_queue": queue_classification["production_repair_queue"],
        "production_price_drift_queue": card_price_drift.get("drift_rows", []),
        "thin_monitor_expected_context_queue": queue_classification["thin_monitor_expected_context_queue"],
        "fresh_quote_required_context_queue": queue_classification["fresh_quote_required_context_queue"],
        "production_expected_context_queue": queue_classification["production_expected_context_queue"],
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "next_actions": next_actions,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh ticker-card evidence and classify stale-card repair needs."
    )
    parser.add_argument("--write", action="store_true", help="Write the gate packet.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero on validation errors.")
    parser.add_argument(
        "--skip-provider-refresh",
        action="store_true",
        help="Rebuild cards from existing local evidence without provider refresh commands.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=[],
        help="Optional explicit ticker shard propagated through provider and card refresh commands.",
    )
    parser.add_argument(
        "--full-answer-mode",
        choices=sorted(FULL_ANSWER_MODES),
        default="changed",
        help=(
            "Control WF85 full-answer rebuild inside this gate: changed (default) "
            "runs only when card/source digest changes, always preserves the old full path, "
            "never keeps the gate as a fast ticker-card-only proof."
        ),
    )
    parser.add_argument(
        "--skip-full-answer-rebuild",
        action="store_true",
        help="Alias for --full-answer-mode never.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local readiness-semantics proof cases.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    parser.add_argument(
        "--card-summary-output",
        default=str(DEFAULT_CARD_SUMMARY),
        help="Ticker card build summary JSON path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.skip_full_answer_rebuild:
        args.full_answer_mode = "never"
    test_result = self_test()
    if args.self_test and not args.write:
        print(json.dumps(test_result, indent=2, sort_keys=True))
        return 0 if test_result.get("status") == "ok" else 1
    packet = build_packet(args)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, sort_keys=True))
    if args.validate and (packet["validation"]["errors"] or test_result.get("status") != "ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
