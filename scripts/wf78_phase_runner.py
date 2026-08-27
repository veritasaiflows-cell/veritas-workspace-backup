#!/usr/bin/env python3
"""Run repeatable WF78 phase passes with one report artifact.

This runner exists to remove manual command choreography from WF78 scaleout.
It is report/review oriented by default. It does not infer owner approval,
promote production answer paths, expand SQL canon/cache authority, mutate
portfolio/canon notes, or grant paper/live/account authority.
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
OUT_JSON = TMP / "wf78-phase-runner-current.json"
OUT_MD = TMP / "wf78-phase-runner-current.md"
PHASE4_PACKET = TMP / "wf78-phase4-recommendation-packet.json"
GO_500_GATE = TMP / "go-sql-500-ticker-expansion-design-gate.json"
SCHEMA = "veritas.wf78_phase_runner.v1"

AUTHORITY = {
    "review_only": True,
    "report_only_default": True,
    "owner_approval_inferred": False,
    "broad_ticker_import_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_authority_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

PHASE4_PILOT = ["AAPL", "ASML", "AVGO", "V", "COST"]
PHASE4_SECOND_WAVE = ["CRM", "PANW", "TSM", "UNH", "WMT"]
PHASE4_DEFER = ["ADBE", "CRWD", "DDOG", "INTU", "MDB"]


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


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def run_step(name: str, command: list[str], *, expected_returncodes: set[int] | None = None, timeout: int = 600) -> dict[str, Any]:
    expected = expected_returncodes or {0}
    started = utc_now()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        ok = proc.returncode in expected
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "expected_returncodes": sorted(expected),
            "ok": ok,
            "stdout_preview": stdout[:4000],
            "stderr_preview": stderr[:2000],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "expected_returncodes": sorted(expected),
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[:4000] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[:2000] if isinstance(exc.stderr, str) else "",
        }


def artifact_step(name: str, path: Path, detail: str) -> dict[str, Any]:
    exists = path.exists()
    return {
        "name": name,
        "command": ["artifact-exists", rel(path)],
        "started_at_utc": utc_now(),
        "completed_at_utc": utc_now(),
        "returncode": 0 if exists else 1,
        "expected_returncodes": [0],
        "ok": exists,
        "stdout_preview": detail if exists else "",
        "stderr_preview": "" if exists else f"missing required artifact: {rel(path)}",
    }


def source_open_cleanup_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    # --write here means write proof/patch artifacts and review-monitor source-open patches.
    # It still does not promote production, mutate portfolio/canon notes, or grant approval.
    write_flag = ["--write"] if args.write else []
    markdown_flag = ["--write-md"] if args.write_md else []
    return [
        run_step(
            "wf78_source_open_patch_orchestrator",
            py_cmd("scripts/wf78_source_open_patch_orchestrator.py", *write_flag, "--validate"),
        ),
        run_step(
            "wf78_sec_reconciliation_scaler",
            py_cmd("scripts/wf78_sec_reconciliation_scaler.py", *write_flag, "--validate"),
        ),
        run_step(
            "wf78_review_monitor_source_open_gate",
            py_cmd("scripts/wf78_review_monitor_source_open_gate.py", "--top", str(args.top), *write_flag, *markdown_flag, "--validate"),
        ),
    ]


def proof_lock_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    go_exe = ROOT / "scripts" / "go" / "bin" / "go-sql-500-expansion-design-gate.exe"
    write_flag = ["--write"] if args.write else []
    steps = [
        run_step(
            "sql_500_ticker_expansion_design_gate",
            py_cmd("scripts/sql_500_ticker_expansion_design_gate.py", *write_flag, "--validate"),
        )
    ]
    if args.write and go_exe.exists():
        steps.append(
            run_step(
                "go_sql_500_expansion_design_gate",
                [str(go_exe), "--root", str(ROOT), "--out", "tmp/go-sql-500-ticker-expansion-design-gate.json"],
            )
        )
    elif args.write:
        steps.append(
            {
                "name": "go_sql_500_expansion_design_gate",
                "command": [str(go_exe)],
                "ok": False,
                "returncode": None,
                "expected_returncodes": [0],
                "stdout_preview": "",
                "stderr_preview": "compiled Go gate missing",
            }
        )
    else:
        steps.append(artifact_step("go_sql_500_expansion_design_gate_existing_artifact", GO_500_GATE, "read-only mode used existing Go proof artifact"))
    steps.append(
        run_step(
            "python_go_sql_500_expansion_gate_parity",
            py_cmd("scripts/python_go_sql_500_expansion_gate_parity.py", *write_flag, "--validate"),
        )
    )
    return steps


def phase4_gate_steps() -> list[dict[str, Any]]:
    # Exit code 2 means the write/import gates correctly failed closed without --apply.
    return [
        run_step(
            "wf78_100_ticker_import_gate_report_only",
            py_cmd("scripts/wf78_100_ticker_import_gate.py", "--pretty"),
            expected_returncodes={2},
        ),
        run_step(
            "wf78_live_pilot_import_gate_report_only",
            py_cmd("scripts/wf78_live_pilot_import_gate.py", "--pretty"),
            expected_returncodes={2},
        ),
    ]


def triage_item_map() -> dict[str, dict[str, Any]]:
    triage = load_dict(ROOT / "tmp" / "wf78-promotion-review-triage-packet.json")
    ready = as_list(triage.get("promotion_review_source_open_ready"))
    return {str(row.get("ticker", "")).upper(): row for row in ready if isinstance(row, dict) and row.get("ticker")}


def recommend_item(ticker: str, group: str, rationale: str, by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = by_ticker.get(ticker, {})
    return {
        "ticker": ticker,
        "name": row.get("name"),
        "sector": row.get("sector"),
        "rank": row.get("rank"),
        "ranking_score": row.get("ranking_score"),
        "reconciliation_route": row.get("reconciliation_route"),
        "blocking_missing_count": row.get("blocking_missing_count"),
        "missing_or_stale_count": row.get("missing_or_stale_count"),
        "recommendation_group": group,
        "rationale": rationale,
        "phase5_allowed_now": False,
    }


def build_phase4_recommendation() -> dict[str, Any]:
    triage = load_dict(ROOT / "tmp" / "wf78-promotion-review-triage-packet.json")
    parity = load_dict(ROOT / "tmp" / "python-go-sql-500-expansion-gate-parity.json")
    by_ticker = triage_item_map()
    summary = as_dict(triage.get("summary"))
    return {
        "generated_at_utc": utc_now(),
        "authority_boundary": {
            "review_only": True,
            "phase5_executed": False,
            "owner_approval_inferred": False,
            "production_answer_path_change_allowed": False,
            "sql_canon_expansion_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_authority_allowed": False,
        },
        "status": "review_ready_no_phase5_execution",
        "phase4_conclusion": "Safe to prepare a Phase 5 approval card for a small review-only promotion/import pilot; not safe to execute Phase 5 without exact owner approval and fresh validation proof.",
        "evidence_summary": {
            "review_monitor_cards": summary.get("review_monitor_cards"),
            "promotion_ready_count": summary.get("promotion_ready_count"),
            "blocked_needs_source_repair_count": summary.get("blocked_needs_source_repair_count"),
            "authority_violation_count": summary.get("authority_violation_count"),
            "python_go_parity_status": parity.get("status"),
            "python_go_parity_checks": as_dict(parity.get("summary")).get("checks"),
            "python_go_parity_critical": as_dict(parity.get("summary")).get("critical"),
            "python_go_parity_warnings": as_dict(parity.get("summary")).get("warnings"),
            "current_active_sql_rows": 100,
            "current_production_answer_path_rows": 42,
            "current_review_monitor_rows": 58,
        },
        "recommended_phase5_pilot": [
            recommend_item("AAPL", "recommended_pilot", "Highest-ranked mega-cap benchmark and production comparison anchor.", by_ticker),
            recommend_item("ASML", "recommended_pilot", "Highest-ranked non-US semiconductor equipment monitor with official IR reconciliation.", by_ticker),
            recommend_item("AVGO", "recommended_pilot", "High-relevance semiconductor/infrastructure software monitor.", by_ticker),
            recommend_item("V", "recommended_pilot", "Adds payments/financials breadth to avoid an all-tech pilot.", by_ticker),
            recommend_item("COST", "recommended_pilot", "Adds defensive consumer-staples breadth to pilot scope.", by_ticker),
        ],
        "second_wave_if_pilot_clean": [
            recommend_item("CRM", "second_wave", "High-ranked enterprise software monitor; hold to reduce initial tech concentration.", by_ticker),
            recommend_item("PANW", "second_wave", "High-ranked cybersecurity monitor after pilot no-regression proof.", by_ticker),
            recommend_item("TSM", "second_wave", "Semiconductor supply-chain monitor after foreign-issuer route is proven.", by_ticker),
            recommend_item("UNH", "second_wave", "Only health-care ready name; deserves separate review context.", by_ticker),
            recommend_item("WMT", "second_wave", "Consumer-staples breadth after COST pilot proof.", by_ticker),
        ],
        "defer_for_now": [
            recommend_item(ticker, "defer_for_now", "Source-open ready but lower ranking score or higher overlap; defer behind pilot/second wave.", by_ticker)
            for ticker in PHASE4_DEFER
        ],
        "required_before_phase5": [
            "exact owner-approved ticker scope",
            "fresh backup/rollback artifact",
            "production-42 A/B no-regression proof",
            "consumer impact diff",
            "post-apply validation plan",
            "explicit approval that this is review/promotion infrastructure only, not capital action",
        ],
        "phase5_approval_card_recommended_scope": {
            "exact_tickers": PHASE4_PILOT,
            "max_scope": "5 tickers",
            "target_action": "review-only promotion/import pilot for comparison; no production answer-path expansion unless separately approved",
            "rollback_required": True,
            "production_42_ab_no_regression_required": True,
            "post_apply_validation_required": True,
        },
        "blocked_actions_without_new_approval": [
            "run wf78_100_ticker_import_gate.py --apply",
            "run wf78_live_pilot_import_gate.py --apply",
            "promote any ticker into production answer path",
            "expand SQL canon/cache authority",
            "mutate portfolio/canon notes",
            "generate capital deployment or trading authority",
            "paper/live brokerage/account action",
        ],
        "next_safe_action": "Ask Randall to approve or modify the exact 5-ticker Phase 5 pilot scope before any --apply/import/promotion action.",
    }


def phase4_recommendation_steps() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    steps = phase4_gate_steps()
    return steps, build_phase4_recommendation()


def run_phase(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    recommendation: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    if args.phase == "source-open-cleanup":
        steps.extend(source_open_cleanup_steps(args))
    elif args.phase == "proof-lock":
        steps.extend(proof_lock_steps(args))
    elif args.phase == "phase4-recommendation":
        phase_steps, recommendation = phase4_recommendation_steps()
        steps.extend(phase_steps)
    elif args.phase == "all-safe":
        steps.extend(source_open_cleanup_steps(args))
        if all(step.get("ok") for step in steps):
            steps.extend(proof_lock_steps(args))
        if all(step.get("ok") for step in steps):
            phase_steps, recommendation = phase4_recommendation_steps()
            steps.extend(phase_steps)
    else:
        raise ValueError(f"unknown phase: {args.phase}")
    return steps, recommendation


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    if args.apply and not args.approval_reference.strip():
        raise SystemExit("--approval-reference is required when --apply is used")
    if args.apply:
        raise SystemExit("--apply mode is intentionally not implemented in wf78_phase_runner.py yet; run exact gate scripts only after scoped approval")
    steps, recommendation = run_phase(args)
    initial_failed = [step for step in steps if not step.get("ok")]
    if not initial_failed and recommendation:
        if args.write:
            atomic_write_json(PHASE4_PACKET, recommendation, ensure_ascii=False)
            source_registry_cmd = py_cmd("scripts/wf78_101_200_candidate_source_registry.py", "--write", "--validate")
            readiness_cmd = py_cmd("scripts/wf78_sql_readiness_index.py", "--write", "--validate")
            manifest_cmd = py_cmd("scripts/wf78_100_to_200_candidate_manifest.py", "--write", "--validate")
            provider_source_cmd = py_cmd("scripts/wf78_101_200_provider_source_validation.py", "--write", "--validate")
            import_decision_cmd = py_cmd("scripts/wf78_101_200_import_decision_packet.py", "--write", "--validate")
            tier_b_evidence_repair_cmd = None
            if args.tier_b_repair_quote:
                tier_b_evidence_repair_cmd = py_cmd(
                    "scripts/wf78_tier_b_evidence_repair.py",
                    *(sum((["--quote", quote] for quote in args.tier_b_repair_quote), [])),
                    *(["--quote-source", args.tier_b_repair_quote_source] if args.tier_b_repair_quote_source else []),
                    *(["--quote-time-utc", args.tier_b_repair_quote_time_utc] if args.tier_b_repair_quote_time_utc else []),
                    "--write",
                    "--write-db",
                    "--validate",
                )
            tier_b_research_packet_cmd = py_cmd("scripts/wf78_tier_b_research_packet.py", "--write", "--write-db", "--validate")
            tier_b_phase2_from_requests_cmd = py_cmd(
                "scripts/wf78_tier_funnel_promotion_gate.py",
                "--requests", "tmp/wf78-tier-b-research-packet-requests.json",
                "--write",
                "--validate",
            )
            tier_label_sync_preview_cmd = py_cmd("scripts/wf78_tier_label_sync_preview.py", "--write", "--validate")
            tier_a_confidence_gate_cmd = py_cmd("scripts/wf78_tier_a_confidence_gate.py", "--write", "--validate")
            tier_c_attention_trigger_cmd = py_cmd("scripts/wf78_tier_c_attention_trigger.py", "--write", "--write-db", "--validate")
            auto_tier_router_cmd = py_cmd("scripts/wf78_auto_tier_router.py", "--write", "--validate")
            clean_tier_roster_cmd = py_cmd("scripts/wf78_clean_tier_roster.py", "--write", "--validate")
            truth_layer_map_cmd = py_cmd("scripts/wf78_truth_layer_map.py", "--write", "--validate")
            tier_semantics_guard_cmd = py_cmd("scripts/wf78_tier_semantics_guard.py", "--write", "--validate")
            production_grade_policy_cmd = py_cmd("scripts/finance_production_grade_policy_gate.py", "--write", "--validate")
            routing_delta_cmd = py_cmd("scripts/wf78_routing_delta.py", "--write", "--validate")
            capital_review_queue_cmd = py_cmd("scripts/wf78_capital_review_queue.py", "--write", "--write-db", "--validate")
            event_rerouting_cmd = py_cmd("scripts/wf78_event_triggered_rerouting.py", "--write", "--write-db", "--validate")
        else:
            source_registry_cmd = py_cmd("scripts/wf78_101_200_candidate_source_registry.py", "--validate")
            readiness_cmd = py_cmd("scripts/wf78_sql_readiness_index.py", "--validate")
            manifest_cmd = py_cmd("scripts/wf78_100_to_200_candidate_manifest.py", "--validate")
            provider_source_cmd = py_cmd("scripts/wf78_101_200_provider_source_validation.py", "--validate")
            import_decision_cmd = py_cmd("scripts/wf78_101_200_import_decision_packet.py", "--validate")
            tier_b_evidence_repair_cmd = None
            if args.tier_b_repair_quote:
                tier_b_evidence_repair_cmd = py_cmd(
                    "scripts/wf78_tier_b_evidence_repair.py",
                    *(sum((["--quote", quote] for quote in args.tier_b_repair_quote), [])),
                    *(["--quote-source", args.tier_b_repair_quote_source] if args.tier_b_repair_quote_source else []),
                    *(["--quote-time-utc", args.tier_b_repair_quote_time_utc] if args.tier_b_repair_quote_time_utc else []),
                    "--validate",
                )
            tier_b_research_packet_cmd = py_cmd("scripts/wf78_tier_b_research_packet.py", "--validate")
            tier_b_phase2_from_requests_cmd = py_cmd(
                "scripts/wf78_tier_funnel_promotion_gate.py",
                "--requests", "tmp/wf78-tier-b-research-packet-requests.json",
                "--validate",
            )
            tier_label_sync_preview_cmd = py_cmd("scripts/wf78_tier_label_sync_preview.py", "--validate")
            tier_a_confidence_gate_cmd = py_cmd("scripts/wf78_tier_a_confidence_gate.py", "--validate")
            tier_c_attention_trigger_cmd = py_cmd("scripts/wf78_tier_c_attention_trigger.py", "--validate")
            auto_tier_router_cmd = py_cmd("scripts/wf78_auto_tier_router.py", "--validate")
            clean_tier_roster_cmd = py_cmd("scripts/wf78_clean_tier_roster.py", "--validate")
            truth_layer_map_cmd = py_cmd("scripts/wf78_truth_layer_map.py", "--validate")
            tier_semantics_guard_cmd = py_cmd("scripts/wf78_tier_semantics_guard.py", "--validate")
            production_grade_policy_cmd = py_cmd("scripts/finance_production_grade_policy_gate.py", "--validate")
            routing_delta_cmd = py_cmd("scripts/wf78_routing_delta.py", "--validate")
            capital_review_queue_cmd = py_cmd("scripts/wf78_capital_review_queue.py", "--validate")
            event_rerouting_cmd = py_cmd("scripts/wf78_event_triggered_rerouting.py", "--validate")
        steps.append(
            run_step(
                "wf78_101_200_candidate_source_registry",
                source_registry_cmd,
            )
        )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_sql_readiness_index",
                    readiness_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_100_to_200_candidate_manifest",
                    manifest_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_101_200_provider_source_validation",
                    provider_source_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_101_200_import_decision_packet",
                    import_decision_cmd,
                )
            )
        if steps[-1].get("ok") and tier_b_evidence_repair_cmd is not None:
            steps.append(
                run_step(
                    "wf78_tier_b_evidence_repair",
                    tier_b_evidence_repair_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_tier_b_research_packet",
                    tier_b_research_packet_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_tier_funnel_promotion_gate_from_repaired_requests",
                    tier_b_phase2_from_requests_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_tier_label_sync_preview",
                    tier_label_sync_preview_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_tier_a_confidence_gate",
                    tier_a_confidence_gate_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_tier_c_attention_trigger",
                    tier_c_attention_trigger_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_auto_tier_router",
                    auto_tier_router_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_clean_tier_roster",
                    clean_tier_roster_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_truth_layer_map",
                    truth_layer_map_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_tier_semantics_guard",
                    tier_semantics_guard_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "finance_production_grade_policy_gate",
                    production_grade_policy_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_routing_delta",
                    routing_delta_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_capital_review_queue",
                    capital_review_queue_cmd,
                )
            )
        if steps[-1].get("ok"):
            steps.append(
                run_step(
                    "wf78_event_triggered_rerouting",
                    event_rerouting_cmd,
                )
            )
    failed = [step for step in steps if not step.get("ok")]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "phase": args.phase,
        "status": "ok" if not failed else "blocked",
        "write_mode": bool(args.write),
        "apply_mode": bool(args.apply),
        "approval_reference": args.approval_reference,
        "authority_boundary": AUTHORITY,
        "summary": {
            "steps": len(steps),
            "failed_steps": len(failed),
            "successful_steps": len(steps) - len(failed),
            "phase5_executed": False,
            "apply_or_import_executed": False,
        },
        "steps": steps,
        "phase4_recommendation": recommendation,
        "validation": {
            "status": "ok" if not failed else "error",
            "errors": [str(step.get("name")) for step in failed],
            "warnings": [],
        },
        "next_safe_action": "Use this runner for repeated report-only WF78 passes. Phase 5 apply/import still requires exact owner scope, backup/rollback, no-regression proof, and post-apply validation.",
        "stop_lines": [
            "No --apply/import/promotion through this runner without a separately implemented approval-gated path.",
            "No production answer-path expansion.",
            "No SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
            "No owner approval inference from clean validation.",
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# WF78 Phase Runner",
        "",
        f"Generated UTC: {report.get('generated_at_utc')}",
        f"Phase: `{report.get('phase')}`",
        f"Status: `{report.get('status')}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in as_dict(report.get("summary")).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Steps", ""])
    for step in as_list(report.get("steps")):
        marker = "PASS" if as_dict(step).get("ok") else "FAIL"
        lines.append(f"- {marker} `{as_dict(step).get('name')}` returncode={as_dict(step).get('returncode')}")
    recommendation = as_dict(report.get("phase4_recommendation"))
    if recommendation:
        lines.extend(["", "## Phase 4 Recommendation", ""])
        lines.append(str(recommendation.get("phase4_conclusion")))
        lines.append("")
        lines.append("Recommended pilot: " + ", ".join(PHASE4_PILOT))
        lines.append("Second wave: " + ", ".join(PHASE4_SECOND_WAVE))
        lines.append("Defer: " + ", ".join(PHASE4_DEFER))
    lines.extend(["", "## Stop Lines", ""])
    lines.extend(f"- {line}" for line in as_list(report.get("stop_lines")))
    lines.append("")
    atomic_write_text(path, "\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["source-open-cleanup", "proof-lock", "phase4-recommendation", "all-safe"], required=True)
    parser.add_argument("--write", action="store_true", help="Write proof artifacts for underlying report-only scripts; never implies production/import authority.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Reserved for future exact approval-gated apply paths; currently blocked.")
    parser.add_argument("--approval-reference", default="")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--tier-b-repair-quote", action="append", help="Optional fresh quote for Tier B evidence repair, as TICKER=PRICE.")
    parser.add_argument("--tier-b-repair-quote-source", default="")
    parser.add_argument("--tier-b-repair-quote-time-utc", default="")
    parser.add_argument("--tier-b-next-batch-offset", type=int, default=0, help="Zero-based offset for phase2_eligible Tier B owner packet generation.")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    parser.add_argument("--md-out", type=Path, default=OUT_MD)
    parser.add_argument("--write-md", action="store_true", help="Optional human-readable Markdown sidecar; JSON remains the default proof surface.")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.out = resolve(args.out)
    args.md_out = resolve(args.md_out)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report, ensure_ascii=False)
        if args.write_md:
            write_markdown(report, args.md_out)
    print(json.dumps({
        "status": report["status"],
        "validation": report["validation"]["status"],
        "phase": report["phase"],
        "steps": report["summary"]["steps"],
        "failed_steps": report["summary"]["failed_steps"],
        "out": rel(args.out) if args.write else None,
        "md_out": rel(args.md_out) if args.write and args.write_md else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
