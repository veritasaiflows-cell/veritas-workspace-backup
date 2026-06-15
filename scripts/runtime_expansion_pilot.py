#!/usr/bin/env python3
"""WF68/WF72 local-only runtime expansion pilot runner.

Refreshes the finance-stack snapshot, inspects validator/advisor readiness artifacts,
compares against the previous compact state, and emits a main-session handoff
surface only when material state changed or validation blocks.

Review/report only. No config/auth/channel/runtime mutation, no external delivery,
no canon/portfolio mutation, no paper/live orders, no brokerage/account action,
no money movement, no owner approval inference, and no probability/win-rate claims.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_DIR = ROOT / "data" / "state-history"
LATEST_STATE = STATE_DIR / "runtime-expansion-pilot-latest.json"
HISTORY = STATE_DIR / "runtime-expansion-pilot-history.jsonl"
OUT_JSON = TMP / "runtime-expansion-pilot-status.json"
OUT_MD = TMP / "runtime-expansion-pilot-status.md"

AUTHORITY_FALSE = {
    "config_auth_channel_runtime_mutation_allowed": False,
    "external_delivery_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "paper_order_submission_allowed": False,
    "paper_order_cancellation_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "probability_or_win_rate_claims_allowed": False,
    "gateway_v1_or_native_codex_migration_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path)


def run_cmd(command: list[str], timeout: int = 240) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return {
        "command": " ".join(command),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def load_dict(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def compact_state(snapshot: dict[str, Any], runtime: dict[str, Any], advisor_validation: dict[str, Any]) -> dict[str, Any]:
    rows = snapshot.get("ticker_rows") if isinstance(snapshot.get("ticker_rows"), list) else []
    focus = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        t = row.get("ticker")
        if t in {"ETN", "VRT", "CME", "PH", "NVDA", "GOOG", "JPM", "MSFT", "GS"}:
            focus[t] = {
                "readiness": row.get("readiness"),
                "band_status": row.get("band_status"),
                "close_reference": row.get("close_reference"),
                "next_action": row.get("next_action"),
            }
    return {
        "snapshot_status": snapshot.get("status"),
        "freshness_grade": snapshot.get("freshness_grade"),
        "deployable_now": snapshot.get("readiness_summary", {}).get("deployable_now"),
        "promotion_review": snapshot.get("readiness_summary", {}).get("promotion_review"),
        "no_chase_or_above_band": snapshot.get("readiness_summary", {}).get("no_chase_or_above_band"),
        "runtime_handoff_status": runtime.get("handoff_status"),
        "runtime_action_needed": runtime.get("action_needed"),
        "advisor_validation_status": advisor_validation.get("status"),
        "advisor_validation_summary": advisor_validation.get("summary"),
        "focus_tickers": focus,
    }


def diff_states(prev: dict[str, Any] | None, curr: dict[str, Any]) -> list[dict[str, Any]]:
    if not prev:
        return [{"field": "baseline", "previous": None, "current": "established", "material": False}]
    changes: list[dict[str, Any]] = []
    material_fields = {"snapshot_status", "freshness_grade", "deployable_now", "promotion_review", "no_chase_or_above_band", "runtime_handoff_status", "runtime_action_needed", "advisor_validation_status"}
    for field in sorted(material_fields):
        if prev.get(field) != curr.get(field):
            changes.append({"field": field, "previous": prev.get(field), "current": curr.get(field), "material": True})
    prev_focus = prev.get("focus_tickers") if isinstance(prev.get("focus_tickers"), dict) else {}
    curr_focus = curr.get("focus_tickers") if isinstance(curr.get("focus_tickers"), dict) else {}
    for ticker in sorted(set(prev_focus) | set(curr_focus)):
        if prev_focus.get(ticker) != curr_focus.get(ticker):
            changes.append({"field": f"focus_tickers.{ticker}", "previous": prev_focus.get(ticker), "current": curr_focus.get(ticker), "material": ticker in {"ETN", "VRT", "CME", "PH", "NVDA"}})
    return changes


def validate_authority(snapshot: dict[str, Any], runtime: dict[str, Any], advisor_validation: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for key, expected in AUTHORITY_FALSE.items():
        if expected is not False:
            findings.append({"severity": "critical", "code": "local_authority_contract_bug", "message": key})
    trust = snapshot.get("trust_and_authority", {}) if isinstance(snapshot.get("trust_and_authority"), dict) else {}
    auth = trust.get("authority", {}) if isinstance(trust.get("authority"), dict) else {}
    for forbidden in ["trade_or_account_action_allowed", "live_trade_allowed", "paper_order_execution_allowed", "owner_approval_inferred", "probability_or_win_rate_claim_allowed"]:
        if auth.get(forbidden) is not False:
            findings.append({"severity": "critical", "code": "snapshot_authority_drift", "message": f"snapshot authority {forbidden} is not false"})
    runtime_auth = runtime.get("authority", {}) if isinstance(runtime.get("authority"), dict) else {}
    for forbidden in ["live_trade_or_account_action_allowed", "paper_trade_allowed", "owner_approval_inferred", "canonical_note_mutation_allowed", "portfolio_mutation_allowed", "probability_claims_allowed"]:
        if runtime_auth.get(forbidden) is not False:
            findings.append({"severity": "critical", "code": "runtime_authority_drift", "message": f"runtime authority {forbidden} is not false"})
    advisor_auth = advisor_validation.get("authority", {}) if isinstance(advisor_validation.get("authority"), dict) else {}
    for forbidden in ["live_trade_or_account_action_allowed", "paper_trade_allowed", "owner_approval_inferred", "canonical_note_mutation_allowed", "portfolio_mutation_allowed"]:
        if advisor_auth.get(forbidden) is not False:
            findings.append({"severity": "critical", "code": "advisor_authority_drift", "message": f"advisor validation authority {forbidden} is not false"})
    return findings


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Runtime Expansion Pilot Status",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Status: **{report['status']}**",
        f"Handoff status: **{report['handoff_status']}**",
        f"Action needed: `{report['action_needed']}`",
        "",
        "## Summary",
        report["summary"],
        "",
        "## Proof",
    ]
    for item in report["proof"]:
        lines.append(f"- {item}")
    lines += ["", "## Material changes"]
    if report["material_changes"]:
        for ch in report["material_changes"]:
            lines.append(f"- `{ch['field']}`: `{ch.get('previous')}` -> `{ch.get('current')}`")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Boundary",
        "Local-only report/runtime handoff pilot. No external channels, config/auth/network exposure, live trading/account/money movement, paper execution, owner-approval inference, probability/win-rate claims, Gateway `/v1`, or native Codex migration.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()

    steps = [run_cmd([sys.executable, "scripts\\finance_stack_snapshot.py", "--write", "--validate"], timeout=300)]
    snapshot = load_dict(TMP / "finance-stack-snapshot.json")
    runtime = load_dict(TMP / "intraday-alerts" / "runtime-handoff-status.json")
    advisor_validation = load_dict(TMP / "intraday-alerts" / "advisor-alert-packet-validation.json")
    current = compact_state(snapshot, runtime, advisor_validation)
    previous = load_dict(LATEST_STATE) if LATEST_STATE.exists() else None
    changes = diff_states(previous, current)
    material_changes = [c for c in changes if c.get("material")]
    findings = validate_authority(snapshot, runtime, advisor_validation)
    if any(not s["ok"] for s in steps):
        findings.append({"severity": "critical", "code": "snapshot_refresh_failed", "message": "finance_stack_snapshot refresh/validate command failed"})

    critical = [f for f in findings if f.get("severity") == "critical"]
    if critical:
        handoff_status = "BLOCKED_VALIDATION_ERROR"
        action_needed = True
        status = "critical"
        summary = "Runtime expansion pilot blocked by validation/authority finding; main session should inspect proof and stop expansion."
    elif material_changes:
        handoff_status = "MATERIAL_CHANGE_READY"
        action_needed = True
        status = "ok"
        summary = "Material finance/advisor state changed; main session should provide a compact review-only handoff."
    elif previous is None:
        handoff_status = "BASELINE_ESTABLISHED"
        action_needed = False
        status = "ok"
        summary = "Runtime expansion pilot baseline established; no interrupt needed unless explicitly requested."
    else:
        handoff_status = "NO_REPLY"
        action_needed = False
        status = "ok"
        summary = "No material finance/advisor state change; main session should stay quiet."

    report = {
        "schema_version": "wf68_wf72.runtime_expansion_pilot.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "handoff_status": handoff_status,
        "action_needed": action_needed,
        "summary": summary,
        "current_state": current,
        "material_changes": material_changes,
        "all_changes": changes,
        "validation": {"status": "critical" if critical else "ok", "findings": findings},
        "steps": steps,
        "proof": [
            "tmp/finance-stack-snapshot.json",
            "tmp/finance-stack-snapshot.json",
            "tmp/finance-stack-snapshot.sqlite",
            "tmp/intraday-alerts/runtime-handoff-status.json",
            "tmp/intraday-alerts/advisor-alert-packet-validation.json",
            rel(OUT_JSON),
        ],
        "authority": AUTHORITY_FALSE | {"local_review_handoff_allowed": True, "state_history_append_allowed": True},
    }

    if args.write:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(OUT_JSON, report)
        atomic_write_text(OUT_MD, render_md(report))
        atomic_write_json(LATEST_STATE, current | {"generated_at_utc": report["generated_at_utc"]})
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"generated_at_utc": report["generated_at_utc"], "handoff_status": handoff_status, "status": status, "state": current}, sort_keys=True) + "\n")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    if args.validate:
        validation = {"status": "ok" if not critical else "critical", "handoff_status": handoff_status, "findings": findings, "material_change_count": len(material_changes)}
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0 if not critical else 1
    return 0 if not critical else 1


if __name__ == "__main__":
    raise SystemExit(main())
