#!/usr/bin/env python3
"""Coordinate quote freshness and bounded entry-band hygiene.

This is the finance OS controller for the "keep bands clean and fresh" lane.
It refreshes read-only quote/technical/band proof, optionally applies only the
existing eligible entry-band maintenance gate, and emits one derived ledger for
the decision sync spine.

It does not approve capital deployment, submit/cancel/sell/modify paper or live
orders, mutate brokerage accounts, move money, infer owner approval, or alter
cash/sizing/sleeve/risk-rule authority.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

OUT = TMP / "band-hygiene-freshness-controller.json"
MD_OUT = TMP / "band-hygiene-freshness-controller.md"

QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
MARKET_HARDENING = TMP / "market-execution-readiness-cron-hardening.json"
TECHNICAL_REFRESH = TMP / "technical-refresh.json"
BAND_PROPOSALS = TMP / "band-proposals.json"
AUTO_BAND_APPLY = TMP / "auto-band-apply.json"
PORTFOLIO_CONFIG = TMP / "portfolio-config.json"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"

SCHEMA = "veritas.band_hygiene_freshness_controller.v1"
QUOTE_FRESH_SECONDS = 15 * 60
TECHNICAL_FRESH_HOURS = 36
BAND_FRESH_HOURS = 36

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "band_hygiene_controller": True,
    "bounded_entry_band_maintenance_allowed": True,
    "uses_existing_auto_apply_gate_only": True,
    "owner_action_required_for_exceptions": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_cancel_sell_modify_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_FLAGS = {
    "review_only",
    "band_hygiene_controller",
    "bounded_entry_band_maintenance_allowed",
    "uses_existing_auto_apply_gate_only",
    "owner_action_required_for_exceptions",
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


def path_age_seconds(path: Path) -> int | None:
    if not path.exists():
        return None
    return max(0, int((datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).total_seconds()))


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def run_step(name: str, command: list[str], timeout: int, *, allow_failure: bool = False) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "allowed_failure": allow_failure,
            "stdout_preview": proc.stdout.strip()[-3000:],
            "stderr_preview": proc.stderr.strip()[-1800:],
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
            "stdout_preview": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1800:] if isinstance(exc.stderr, str) else "",
        }


def index_rows(rows: list[Any], key: str = "ticker") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get(key))
        if symbol:
            out[symbol] = row_dict
    return out


def quote_index() -> dict[str, dict[str, Any]]:
    return index_rows(as_list(load_dict(QUOTE_PROOF).get("snapshots")), key="symbol")


def technical_index() -> dict[str, dict[str, Any]]:
    return index_rows(as_list(load_dict(TECHNICAL_REFRESH).get("records")))


def band_index() -> dict[str, dict[str, Any]]:
    payload = load_dict(BAND_PROPOSALS)
    blocking = {ticker(item) for item in as_list(as_dict(payload.get("summary")).get("blocking_review_tickers"))}
    monitor = {ticker(item) for item in as_list(as_dict(payload.get("summary")).get("monitor_only_review_tickers"))}
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(payload.get("proposals")):
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if not symbol:
            continue
        row_dict["blocking_review"] = symbol in blocking
        row_dict["monitor_only_review"] = symbol in monitor
        out[symbol] = row_dict
    return out


def applied_index() -> dict[str, dict[str, Any]]:
    return index_rows(as_list(load_dict(AUTO_BAND_APPLY).get("applied")))


def skipped_index() -> dict[str, dict[str, Any]]:
    return index_rows(as_list(load_dict(AUTO_BAND_APPLY).get("skipped")))


def clean_quote(snapshot: dict[str, Any]) -> bool:
    age = snapshot.get("age_seconds")
    age_value = int(age) if age is not None else 999999
    return (
        snapshot.get("freshness_status") == "fresh"
        and snapshot.get("price") is not None
        and age_value <= QUOTE_FRESH_SECONDS
    )


def row_state(
    symbol: str,
    proposal: dict[str, Any],
    tech: dict[str, Any],
    quote: dict[str, Any],
    applied: dict[str, Any],
    skipped: dict[str, Any],
) -> tuple[str, list[str], bool]:
    blockers: list[str] = []
    owner_review_required = False

    if not quote:
        blockers.append("missing_quote_snapshot")
    elif not clean_quote(quote):
        blockers.append("quote_not_intraday_fresh")

    if tech.get("below_stop") is True:
        blockers.append("below_stop_or_invalidation")
        owner_review_required = True

    if not proposal:
        blockers.append("missing_band_proposal")
        return "missing_band_context", blockers, True

    if applied:
        if blockers:
            return "applied_auto_maintenance_watch", blockers, owner_review_required
        return "applied_auto_maintenance", blockers, False

    if proposal.get("skip_reason"):
        blockers.append(f"band_refresh_skipped:{proposal.get('skip_reason')}")
        return "band_refresh_skipped", blockers, True

    if str(proposal.get("entry_policy") or "").lower() == "repair_mode":
        blockers.append("repair_mode")
        owner_review_required = True

    if proposal.get("canonical_apply_eligible") is True and proposal.get("needs_review") is True:
        blockers.append("eligible_auto_maintenance_pending")
        return "eligible_auto_maintenance_pending", blockers, owner_review_required

    if proposal.get("blocking_review") is True:
        blockers.append("band_exception_review_required")
        return "exception_owner_review", blockers, True

    if proposal.get("needs_review") is True and proposal.get("blocking_review") is False:
        blockers.append("monitor_only_band_review")
        return "monitor_only_review", blockers, owner_review_required

    if proposal.get("needs_review") is True and proposal.get("canonical_apply_eligible") is not True:
        blockers.append(skipped.get("reason") or "band_review_not_applyable")
        return "exception_owner_review", blockers, True

    if proposal.get("needs_review") is True:
        blockers.append("monitor_only_band_review")
        return "monitor_only_review", blockers, owner_review_required

    if quote and clean_quote(quote) and not blockers:
        return "clean_and_fresh", blockers, False

    return "freshness_or_context_watch", blockers, owner_review_required


def entry_policy_review_candidate(
    symbol: str,
    proposal: dict[str, Any],
    tech: dict[str, Any],
    state: str,
    blockers: list[str],
) -> dict[str, Any]:
    entry_policy = str(proposal.get("entry_policy") or "").lower()
    coverage_lane = str(proposal.get("coverage_lane") or "").lower()
    workflow_state = str(proposal.get("workflow_state") or "").upper()
    band_status = str(proposal.get("band_status") or "").upper()
    reasons = [str(item) for item in as_list(proposal.get("reasons"))]
    has_numeric_band = all(
        proposal.get(key) is not None
        for key in ("current_band_low", "current_band_high", "current_stop")
    )
    tech_in_band = tech.get("in_entry_band")
    surface_conflicts: list[str] = []
    if tech_in_band is False and band_status == "IN_BAND":
        surface_conflicts.append("technical_refresh_not_in_band_but_band_proposals_in_band")
    if tech_in_band is None:
        source_setup_valid = band_status == "IN_BAND"
    else:
        source_setup_valid = tech_in_band is True
    hard_blockers: list[str] = []
    if tech.get("below_stop") is True or "below_stop_or_invalidation" in blockers:
        hard_blockers.append("below_stop_or_invalidation")
    legacy_repair_workflow_blocks = workflow_state == "REPAIR" and state != "monitor_only_review"
    if legacy_repair_workflow_blocks or entry_policy == "repair_mode":
        hard_blockers.append("repair_mode_or_repair_workflow")

    policy_metadata_blocked = (
        entry_policy in {"underdefined", "reference_band", "conditional_requalify", "policy_review_required"}
        or (coverage_lane and coverage_lane != "execution")
        or workflow_state == "WATCH"
        or any("entry policy is not band_defined" in reason for reason in reasons)
        or any("workflow state is not decision-grade" in reason for reason in reasons)
    )
    candidate = bool(
        has_numeric_band
        and source_setup_valid
        and policy_metadata_blocked
        and not hard_blockers
        and not surface_conflicts
    )
    if candidate:
        action = "main_review_required"
    elif hard_blockers:
        action = "repair_or_reclaim_first"
    elif not has_numeric_band:
        action = "missing_numeric_band"
    elif not source_setup_valid:
        action = "monitor_until_setup_valid"
    else:
        action = "no_entry_policy_review_needed"
    visibility_reasons: list[str] = []
    if candidate:
        visibility_reasons.append("existing_surfaces_show_setup_but_policy_metadata_suppresses_visibility")
    if coverage_lane and coverage_lane != "execution":
        visibility_reasons.append(f"coverage_lane={coverage_lane}")
    if entry_policy:
        visibility_reasons.append(f"entry_policy={entry_policy}")
    if workflow_state:
        visibility_reasons.append(f"workflow_state={workflow_state}")
    if hard_blockers:
        visibility_reasons.extend(hard_blockers)
    if surface_conflicts:
        visibility_reasons.extend(surface_conflicts)
    return {
        "candidate": candidate,
        "recommended_entry_policy_action": action,
        "secondary_not_suppressing": True,
        "source_setup_valid": bool(source_setup_valid),
        "has_numeric_band_stop": bool(has_numeric_band),
        "policy_metadata_blocked": bool(policy_metadata_blocked),
        "hard_blockers": hard_blockers,
        "surface_conflicts": surface_conflicts,
        "visibility_reasons": visibility_reasons,
        "source_fields": {
            "technical.in_entry_band": tech.get("in_entry_band"),
            "technical.below_stop": tech.get("below_stop"),
            "technical.ma_posture": tech.get("ma_posture"),
            "band.band_status": proposal.get("band_status"),
            "band.entry_policy": proposal.get("entry_policy"),
            "band.coverage_lane": proposal.get("coverage_lane"),
            "band.workflow_state": proposal.get("workflow_state"),
            "band.canonical_apply_eligible": proposal.get("canonical_apply_eligible"),
            "hygiene.state": state,
        },
    }


def build_rows() -> list[dict[str, Any]]:
    quotes = quote_index()
    technical = technical_index()
    bands = band_index()
    applied = applied_index()
    skipped = skipped_index()
    tickers = sorted(set(quotes) | set(technical) | set(bands) | set(applied) | set(skipped))
    rows: list[dict[str, Any]] = []
    for symbol in tickers:
        proposal = bands.get(symbol, {})
        tech = technical.get(symbol, {})
        quote = quotes.get(symbol, {})
        applied_row = applied.get(symbol, {})
        skipped_row = skipped.get(symbol, {})
        state, blockers, owner_review_required = row_state(symbol, proposal, tech, quote, applied_row, skipped_row)
        entry_policy_review = entry_policy_review_candidate(symbol, proposal, tech, state, blockers)
        rows.append({
            "ticker": symbol,
            "state": state,
            "blockers": blockers,
            "owner_review_required": owner_review_required,
            "entry_policy_review": entry_policy_review,
            "quote": {
                "freshness_status": quote.get("freshness_status"),
                "age_seconds": quote.get("age_seconds"),
                "price": quote.get("price"),
                "source_timestamp_utc": quote.get("source_timestamp_utc"),
            } if quote else None,
            "technical": {
                "status": load_dict(TECHNICAL_REFRESH).get("status"),
                "data_date": tech.get("data_date"),
                "close": tech.get("close"),
                "in_entry_band": tech.get("in_entry_band"),
                "below_stop": tech.get("below_stop"),
                "ma_posture": tech.get("ma_posture"),
            } if tech else None,
            "band": {
                "needs_review": proposal.get("needs_review"),
                "canonical_apply_eligible": proposal.get("canonical_apply_eligible"),
                "blocking_review": proposal.get("blocking_review"),
                "monitor_only_review": proposal.get("monitor_only_review"),
                "band_status": proposal.get("band_status"),
                "entry_policy": proposal.get("entry_policy"),
                "entry_band_method": proposal.get("entry_band_method"),
                "current_band_low": proposal.get("current_band_low"),
                "current_band_high": proposal.get("current_band_high"),
                "current_stop": proposal.get("current_stop"),
                "suggested_band_low": proposal.get("suggested_band_low"),
                "suggested_band_high": proposal.get("suggested_band_high"),
                "suggested_stop": proposal.get("suggested_stop"),
                "data_date": proposal.get("data_date"),
                "reasons": proposal.get("reasons") or [],
            } if proposal else None,
            "auto_apply": {
                "applied": bool(applied_row),
                "applied_date": load_dict(AUTO_BAND_APPLY).get("applied_date"),
                "new_low": applied_row.get("new_low"),
                "new_high": applied_row.get("new_high"),
                "new_stop": applied_row.get("new_stop"),
                "skipped_reason": skipped_row.get("reason"),
            },
            "authority": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return rows


def validate_authority() -> list[str]:
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        expected = True if key in TRUE_FLAGS else False
        if value is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    return errors


def run_refresh_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    if not args.skip_quote_refresh:
        steps.append(run_step("intraday_quote_snapshot_proof", py_cmd("scripts\\intraday_quote_snapshot_proof.py"), 90))
        steps.append(run_step("market_execution_readiness_cron_hardening", py_cmd("scripts\\market_execution_readiness_cron_hardening.py", "--write", "--validate"), 90))
    if not args.skip_technical_refresh:
        steps.append(run_step("technical_refresh", py_cmd("scripts\\technical_refresh.py"), 300))
    if not args.skip_band_refresh:
        steps.append(run_step("band_refresh", py_cmd("scripts\\band_refresh.py"), args.band_refresh_timeout_seconds))
    apply_cmd = py_cmd("scripts\\auto_apply_entry_band_maintenance.py", "--apply" if args.apply_eligible else "--dry-run")
    steps.append(run_step("auto_apply_entry_band_maintenance", apply_cmd, 180))
    if args.apply_eligible:
        steps.append(run_step("band_refresh_post_apply", py_cmd("scripts\\band_refresh.py"), args.band_refresh_timeout_seconds))
        steps.extend([
            run_step("validate_portfolio_config", py_cmd("scripts\\validate_portfolio_config.py", "--strict"), 120),
            run_step("deployment_check", py_cmd("scripts\\deployment_check.py"), 120),
            run_step("generate_dashboard", py_cmd("scripts\\generate_dashboard.py"), 180),
            run_step("validate_dashboard_state", py_cmd("scripts\\validate_dashboard_state.py", "--write"), 180),
        ])
    return steps


def source_status(path: Path, max_age_seconds: int | None = None) -> dict[str, Any]:
    payload = load_dict(path)
    generated_age = age_seconds(payload.get("generated_at_utc"))
    file_age = path_age_seconds(path)
    age = generated_age if generated_age is not None else file_age
    fresh = True if max_age_seconds is None else (age is not None and age <= max_age_seconds)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "age_seconds": age,
        "fresh": fresh,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    steps = run_refresh_steps(args)
    rows = build_rows()
    state_counts: dict[str, int] = {}
    for row in rows:
        state = str(row.get("state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1
    errors = [
        step["name"]
        for step in steps
        if not step.get("ok") and not step.get("allowed_failure")
    ] + validate_authority()
    quote_source = source_status(QUOTE_PROOF, QUOTE_FRESH_SECONDS)
    technical_source = source_status(TECHNICAL_REFRESH, TECHNICAL_FRESH_HOURS * 3600)
    band_source = source_status(BAND_PROPOSALS, BAND_FRESH_HOURS * 3600)
    auto_apply = load_dict(AUTO_BAND_APPLY)
    exception_rows = [row for row in rows if row.get("state") == "exception_owner_review"]
    post_apply_open_rows = [row for row in rows if row.get("state") == "post_apply_review_still_open"]
    pending_rows = [row for row in rows if row.get("state") == "eligible_auto_maintenance_pending"]
    clean_rows = [row for row in rows if row.get("state") == "clean_and_fresh"]
    entry_policy_review_rows = [
        row for row in rows
        if as_dict(row.get("entry_policy_review")).get("candidate") is True
    ]
    status = "blocked" if errors else "needs_review" if exception_rows or post_apply_open_rows or pending_rows else "ok"
    if pending_rows:
        next_safe_action = "Run with --apply-eligible from main-session or approved cron path to clear eligible routine maintenance."
    elif exception_rows or post_apply_open_rows:
        next_safe_action = "Review exception rows; no eligible auto-maintenance is pending."
    else:
        next_safe_action = "No band freshness action pending."
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply_eligible" if args.apply_eligible else "dry_run",
        "purpose": "Cron-backed quote freshness and bounded entry-band hygiene controller for the finance decision sync spine.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "ticker_count": len(rows),
            "state_counts": dict(sorted(state_counts.items())),
            "clean_and_fresh_count": len(clean_rows),
            "clean_and_fresh_tickers": [row["ticker"] for row in clean_rows],
            "applied_auto_maintenance_count": len(as_list(auto_apply.get("applied"))),
            "applied_auto_maintenance_tickers": [ticker(row.get("ticker")) for row in as_list(auto_apply.get("applied"))],
            "eligible_auto_maintenance_pending_count": len(pending_rows),
            "eligible_auto_maintenance_pending_tickers": [row["ticker"] for row in pending_rows],
            "exception_owner_review_count": len(exception_rows),
            "exception_owner_review_tickers": [row["ticker"] for row in exception_rows],
            "entry_policy_review_candidate_count": len(entry_policy_review_rows),
            "entry_policy_review_candidate_tickers": [row["ticker"] for row in entry_policy_review_rows],
            "next_safe_action": next_safe_action,
        },
        "source_artifacts": {
            "quote_snapshot_proof": quote_source,
            "market_execution_readiness": source_status(MARKET_HARDENING),
            "technical_refresh": technical_source,
            "band_proposals": band_source,
            "auto_band_apply": source_status(AUTO_BAND_APPLY),
            "portfolio_config": {"path": rel(PORTFOLIO_CONFIG), "exists": PORTFOLIO_CONFIG.exists()},
            "execution_board": {"path": rel(EXECUTION_BOARD), "exists": EXECUTION_BOARD.exists()},
        },
        "rows": rows,
        "steps": steps,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "Quote and band freshness do not equal capital approval.",
            "Only existing canonical_apply_eligible entry-band maintenance may be applied.",
            "Exceptions require main-session/Randall review.",
            "No paper/live order action, account action, money movement, cash/sizing/sleeve/risk-rule mutation, or owner approval inference is allowed.",
        ],
    }


def markdown(report: dict[str, Any]) -> str:
    summary = as_dict(report.get("summary"))
    lines = [
        "# Band Hygiene and Freshness Controller",
        "",
        f"- Generated UTC: `{report.get('generated_at_utc')}`",
        f"- Status: `{report.get('status')}`",
        f"- Mode: `{report.get('mode')}`",
        f"- Clean and fresh: `{summary.get('clean_and_fresh_count')}`",
        f"- Applied maintenance: `{summary.get('applied_auto_maintenance_count')}`",
        f"- Exception review: `{summary.get('exception_owner_review_count')}`",
        "",
        "| Ticker | State | Quote | Price | Band status | Apply eligible | Main blocker |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in as_list(report.get("rows")):
        row_dict = as_dict(row)
        quote = as_dict(row_dict.get("quote"))
        band = as_dict(row_dict.get("band"))
        blockers = as_list(row_dict.get("blockers"))
        if row_dict.get("state") in {"clean_and_fresh", "freshness_or_context_watch"} and not blockers:
            continue
        lines.append(
            "| {ticker} | {state} | {fresh} | {price} | {band_status} | {eligible} | {blocker} |".format(
                ticker=row_dict.get("ticker"),
                state=row_dict.get("state"),
                fresh=quote.get("freshness_status"),
                price=quote.get("price"),
                band_status=band.get("band_status"),
                eligible=band.get("canonical_apply_eligible"),
                blocker=blockers[0] if blockers else "",
            )
        )
    lines.extend([
        "",
        "Boundary: quote/band hygiene only. No capital approval, no execution, no account action, no owner approval inference.",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--apply-eligible", action="store_true", help="Apply only existing canonical_apply_eligible band proposals via auto_apply_entry_band_maintenance.py.")
    parser.add_argument("--skip-quote-refresh", action="store_true")
    parser.add_argument("--skip-technical-refresh", action="store_true")
    parser.add_argument("--skip-band-refresh", action="store_true")
    parser.add_argument("--band-refresh-timeout-seconds", type=int, default=900)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    report = build_report(args)
    if args.write:
        atomic_write_json(out, report, indent=2, ensure_ascii=True)
    if args.write_md:
        atomic_write_text(md_out, markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": report.get("status"),
        "mode": report.get("mode"),
        "out": rel(out),
        "md_out": rel(md_out) if args.write_md else None,
        "summary": report.get("summary"),
        "validation": report.get("validation"),
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
