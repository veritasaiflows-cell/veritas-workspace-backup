"""Detect and safely repair missed official earnings-period captures.

This guard closes the outage gap between a scheduler run and a current
earnings artifact. It discovers the latest SEC reported period for tracked
names, compares it with the validator-clean capture registry, and writes a
deterministic review-only queue. Newly discovered supported SEC sources are
captured additively as source-verified metadata; unproven field extraction
remains explicit reconciliation debt rather than an alert-worthy outage.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from official_capture_period_registry import CAPTURE_SCRIPT_BY_TICKER, build_registry
from official_earnings_source_discovery import cik_from_source_url, discover_latest_sec_report

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT = TMP / "earnings-rollforward-guard.json"
DEFAULT_MD = DEFAULT_OUTPUT.with_suffix(".md")
PORTFOLIO_CONFIG = TMP / "portfolio-config.json"
CAPTURE_DIR = TMP / "official-ir-captures"

SCHEMA = "veritas.earnings_rollforward_guard.v1"
PRIORITY_POLICIES = {"timing_sensitive", "block_pre_earnings", "post_earnings_rebuild", "event_sensitive"}

AUTHORITY = {
    "review_only": True,
    "evidence_refresh_allowed": True,
    "official_source_discovery_allowed": True,
    "official_review_capture_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "paper_order_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def tracked_universe(config: dict[str, Any], *, priority_only: bool) -> dict[str, dict[str, Any]]:
    rows = config.get("tracked_universe")
    selected: dict[str, dict[str, Any]] = {}
    if isinstance(rows, dict):
        for ticker, row in rows.items():
            if not isinstance(row, dict):
                continue
            ticker_name = str(ticker).upper()
            policy = str(row.get("earnings_policy") or "").lower()
            if priority_only and policy not in PRIORITY_POLICIES:
                continue
            selected[ticker_name] = row
    if selected:
        return selected

    # portfolio-config.json is a retired surface. Fall back only to the
    # maintained official-capture registry so an absent legacy config cannot
    # yield a false-green zero-ticker guard or recreate configuration state.
    return {
        ticker: {
            "earnings_policy": "post_earnings_rebuild",
            "scope_source": "official_capture_registry_fallback",
        }
        for ticker in sorted(CAPTURE_SCRIPT_BY_TICKER)
    }


def _period_gt(left: str | None, right: str | None) -> bool:
    return bool(left and (not right or str(left) > str(right)))


def _latest_by_ticker(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = registry.get("latest_by_ticker")
    return rows if isinstance(rows, dict) else {}


def build_guard(
    *,
    tracked: dict[str, dict[str, Any]],
    registry: dict[str, Any],
    discoverer: Callable[..., dict[str, Any]],
    priority_only: bool = False,
    auto_capture: bool = False,
    timeout_seconds: int = 20,
    auto_capturer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    latest = _latest_by_ticker(registry)
    findings: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for ticker in sorted(tracked):
        current = latest.get(ticker)
        if not isinstance(current, dict):
            rows.append({
                "ticker": ticker,
                "status": "missing_current_capture",
                "reason": "tracked_ticker_has_no_capture_registry_entry",
                "capture_script": None,
                "current_period_end": None,
            })
            findings.append({"severity": "warning", "code": "missing_current_capture", "ticker": ticker})
            continue
        current_period = str(current.get("period_end") or "") or None
        source_url = str(current.get("source_url") or "")
        cik = cik_from_source_url(source_url)
        base = {
            "ticker": ticker,
            "capture_script": current.get("capture_script"),
            "current_period_end": current_period,
            "current_period_slug": current.get("period_slug"),
            "current_capture_artifact": current.get("capture_artifact"),
            "current_validation_artifact": current.get("validation_artifact"),
            "current_validation_clean": current.get("validation_clean") is True,
            "current_source_url": source_url or None,
            "cik": cik,
            "earnings_policy": tracked[ticker].get("earnings_policy"),
        }
        if not cik:
            rows.append({**base, "status": "source_monitoring_manual_required", "reason": "current_source_is_not_sec_addressable"})
            findings.append({"severity": "warning", "code": "non_sec_source_monitoring_required", "ticker": ticker})
            continue

        discovered = discoverer(
            ticker=ticker,
            cik=cik,
            current_period_end=current_period,
            timeout_seconds=timeout_seconds,
        )
        status = str(discovered.get("status") or "discovery_error")
        if status == "discovery_error":
            rows.append({**base, "status": "discovery_error", "reason": "sec_discovery_failed", "discovery": discovered})
            findings.append({"severity": "critical", "code": "sec_discovery_failed", "ticker": ticker, "error": discovered.get("error")})
            continue
        if status == "current":
            rows.append({**base, "status": "current", "reason": "validated_capture_matches_latest_sec_report", "discovery": discovered})
            continue

        expected_period = str(discovered.get("latest_detected_period_end") or "") or None
        row = {
            **base,
            "status": "catch_up_required",
            "reason": "newer_sec_report_than_validator_clean_capture",
            "expected_period_end": expected_period,
            "expected_period_slug": discovered.get("period_slug"),
            "recommended_command": f"python scripts\\earnings_rollforward_guard.py --ticker {ticker} --auto-capture --write --validate",
            "preserve_historical_artifacts": True,
            "discovery": discovered,
        }
        if auto_capture and status in {"new_source_detected", "new_period_source_manual_required"}:
            try:
                from official_earnings_auto_capture import capture_discovered_source

                capturer = auto_capturer or capture_discovered_source
                capture_result = capturer(discovered, write_markdown=False)
                row["auto_capture"] = capture_result
                if capture_result.get("status") == "source_verified_manual_reconciliation_pending":
                    row["status"] = "updated_source_verified_pending_reconciliation"
                    row["reason"] = "newer_sec_source_verified_additively_and_requires_source_open_field_reconciliation"
                else:
                    row["status"] = "updated_review_only"
                    row["reason"] = "newer_sec_report_auto_captured_additively_and_requires_downstream_rebuild"
            except Exception as exc:  # preserve queue state; never carry old period silently
                row["auto_capture"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
                row["status"] = "parser_failed_or_manual_required"
                row["reason"] = "newer_sec_report_detected_but_auto_capture_failed"
                findings.append({"severity": "warning", "code": "auto_capture_failed", "ticker": ticker, "error": str(exc)})
        else:
            findings.append({"severity": "warning", "code": "new_source_detected_not_captured", "ticker": ticker, "expected_period_end": expected_period})
        rows.append(row)

    unresolved = [row for row in rows if row.get("status") in {"catch_up_required", "parser_failed_or_manual_required", "discovery_error", "missing_current_capture"}]
    updated = [row for row in rows if row.get("status") == "updated_review_only"]
    source_verified_pending = [row for row in rows if row.get("status") == "updated_source_verified_pending_reconciliation"]
    critical = [finding for finding in findings if finding.get("severity") == "critical"]
    status = "blocked" if critical else "warning" if unresolved or findings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Detect missed/new official earnings periods and create additive review-only catch-up state before stale fundamentals can be treated as current.",
        "scope": {
            "priority_only": priority_only,
            "auto_capture": auto_capture,
            "tracked_ticker_count": len(tracked),
            "source": (
                "official_capture_registry_fallback"
                if tracked and all(row.get("scope_source") == "official_capture_registry_fallback" for row in tracked.values())
                else "portfolio_config"
            ),
        },
        "authority": AUTHORITY,
        "source_artifacts": {
            "portfolio_config": rel(PORTFOLIO_CONFIG),
            "capture_registry": "tmp/wf70-official-capture-period-registry.json",
            "capture_directory": rel(CAPTURE_DIR),
            "sec_submissions": "https://data.sec.gov/submissions/CIK{cik}.json",
        },
        "contract": {
            "scheduler_success_is_not_evidence_current": True,
            "newer_sec_period_requires_validated_capture": True,
            "historical_capture_overwrite_allowed": False,
            "unresolved_period_may_not_be_presented_as_current": True,
            "auto_capture_is_review_only": True,
        },
        "summary": {
            "tracked_ticker_count": len(tracked),
            "current_count": len([row for row in rows if row.get("status") == "current"]),
            "updated_review_only_count": len(updated),
            "source_verified_pending_reconciliation_count": len(source_verified_pending),
            "manual_reconciliation_pending_count": len(source_verified_pending),
            "catch_up_required_count": len([row for row in rows if row.get("status") == "catch_up_required"]),
            "manual_required_count": len([row for row in rows if row.get("status") == "parser_failed_or_manual_required"]),
            "discovery_error_count": len([row for row in rows if row.get("status") == "discovery_error"]),
            "unresolved_count": len(unresolved),
            "critical_finding_count": len(critical),
        },
        "findings": findings,
        "tickers": rows,
        "next_action": (
            "Run the listed review-only capture command(s), validate them, then rebuild reconciliation/bridge/cards."
            if unresolved
            else "Rebuild downstream official reconciliation, bridge, and ticker-card artifacts after additive captures; source-verified metadata remains review-fresh debt until field reconciliation completes."
            if updated or source_verified_pending
            else "No earnings-period gap detected for the selected scope."
        ),
        "validation": {"status": "ok", "errors": [], "warnings": [f["code"] for f in findings]},
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Earnings Rollforward Guard",
        "",
        f"Generated: `{payload.get('generated_at_utc')}`",
        "",
        "Review-only SEC-period freshness guard. It never mutates canon, portfolio, approval, sizing, cash, paper/live orders, accounts, or cron schedules.",
        "",
        "## Summary",
        "",
    ]
    for key, value in (payload.get("summary") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines += ["", "| Ticker | Status | Current period | Expected period | Reason |", "|---|---|---:|---:|---|"]
    for row in payload.get("tickers") or []:
        lines.append(f"| {row.get('ticker')} | {row.get('status')} | {row.get('current_period_end')} | {row.get('expected_period_end', '')} | {row.get('reason')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect and safely catch up missed official earnings periods.")
    parser.add_argument("--ticker", action="append", dest="tickers", help="Limit scope to one or more tickers.")
    parser.add_argument("--all-tracked", action="store_true", help="Check all tracked tickers instead of the priority earnings subset.")
    parser.add_argument("--priority-only", action="store_true", help="Check only timing-sensitive/event-sensitive tracked names.")
    parser.add_argument("--auto-capture", action="store_true", help="Run supported additive review-only official-source capture; unproven field parsers remain source-verified/manual-reconciliation pending.")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(PORTFOLIO_CONFIG)
    explicit_tickers = bool(args.tickers)
    priority_only = bool(args.priority_only or (not args.all_tracked and not explicit_tickers))
    tracked = tracked_universe(config, priority_only=priority_only)
    if args.tickers:
        wanted = {str(ticker).upper() for ticker in args.tickers}
        tracked = {
            ticker: row
            for ticker, row in tracked_universe(config, priority_only=False).items()
            if ticker in wanted
        }
    registry = build_registry(CAPTURE_DIR)
    payload = build_guard(
        tracked=tracked,
        registry=registry,
        discoverer=discover_latest_sec_report,
        priority_only=priority_only,
        auto_capture=args.auto_capture,
        timeout_seconds=max(5, int(args.timeout_seconds)),
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    if args.write:
        write_json(output, payload)
        if args.write_md:
            write_md(md_output, payload)
    print(json.dumps({"status": payload["status"], "output": rel(output), "summary": payload["summary"], "validation": payload["validation"]}, indent=2, sort_keys=True))
    # Discovery/manual queue states are valid review outcomes. Only malformed
    # input or SEC transport failures are hard-blocking; the artifact itself
    # carries the per-ticker fail-closed state for downstream consumers.
    return 0 if not args.validate or payload["validation"]["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
