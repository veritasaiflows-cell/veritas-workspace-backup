from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "board-canon-guardrail.json"
OUT_MD = TMP / "board-canon-guardrail.md"

TECHNICAL = TMP / "technical-refresh.json"
DEPLOYMENT = TMP / "deployment-check.json"
TRIGGER = TMP / "trigger-sheet.json"
REGIME = TMP / "regime-scores.json"
CONFIG = TMP / "portfolio-config.json"

EXECUTION_NOTE = WORKSPACE / "03. Portfolio" / "Execution Board.md"
TECHNICAL_NOTE = EXECUTION_NOTE
TRIGGER_NOTE = EXECUTION_NOTE
SNAPSHOT_NOTE = WORKSPACE / "03. Portfolio" / "Portfolio Snapshot.md"
WATCHLIST_NOTE = WORKSPACE / "04. Research" / "Coverage and Watchlist.md"
REGIME_NOTE = WORKSPACE / "02. Markets" / "Regime Scoring Matrix.md"

SCHEMA_VERSION = 1
NEAR_STOP_PCT = 1.0

CONTRADICTORY_STATE_RE = re.compile(
    r"\b(almost deployable|deployable now|active watch|owner-approved but (?:trigger|action state) not live|(?:trigger|action state) not live)\b",
    re.IGNORECASE,
)
SAFE_STOP_RE = re.compile(r"\b(stop[- ]breached|below (?:the )?(?:hard )?stop|below-stop|do not touch|repair|invalidat)", re.IGNORECASE)
HARD_STOP_RE = re.compile(r"\b(stop[- ]breached|below (?:the )?(?:hard )?stop|below-stop|invalidat)", re.IGNORECASE)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def records_by_ticker(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rec in data.get("records", []) or []:
        if isinstance(rec, dict) and rec.get("ticker"):
            out[str(rec["ticker"])] = rec
    return out


def markdown_section(text: str, ticker: str) -> str:
    pattern = re.compile(rf"(?ms)^###\s+{re.escape(ticker)}\b.*?(?=^###\s+|^---\s*$|\Z)")
    match = pattern.search(text)
    return match.group(0) if match else ""


def markdown_table_row(text: str, ticker: str) -> str:
    pattern = re.compile(rf"(?im)^\|\s*(?:\*\*)?{re.escape(ticker)}(?:\*\*)?\s*\|.*$")
    match = pattern.search(text)
    return match.group(0) if match else ""


def contains_stop_truth(text: str, *, hard: bool = False) -> bool:
    if not text:
        return False
    return bool((HARD_STOP_RE if hard else SAFE_STOP_RE).search(text))


def contains_contradiction(text: str) -> bool:
    return bool(text and CONTRADICTORY_STATE_RE.search(text))


def money(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def build_risk_records() -> list[dict[str, Any]]:
    technical = records_by_ticker(load_json(TECHNICAL))
    deployment = records_by_ticker(load_json(DEPLOYMENT))
    config = load_json(CONFIG)
    entry_bands = config.get("entry_bands", {}) if isinstance(config.get("entry_bands"), dict) else {}
    tracked = config.get("tracked_universe", {}) if isinstance(config.get("tracked_universe"), dict) else {}

    tickers = sorted(set(technical) | set(deployment))
    risks: list[dict[str, Any]] = []
    for ticker in tickers:
        tech = technical.get(ticker, {})
        dep = deployment.get(ticker, {})
        close = tech.get("close", dep.get("close"))
        band = entry_bands.get(ticker, {}) if isinstance(entry_bands.get(ticker), dict) else {}
        stop = band.get("stop")
        below_stop = bool(tech.get("below_stop") or dep.get("below_stop") or dep.get("action_state") == "BELOW STOP")
        near_stop = False
        stop_gap = None
        stop_gap_pct = None
        try:
            if close is not None and stop is not None:
                c = float(close)
                s = float(stop)
                stop_gap = round(c - s, 4)
                stop_gap_pct = round(((c - s) / s) * 100, 4) if s else None
                near_stop = (not below_stop) and stop_gap_pct is not None and 0 <= stop_gap_pct <= NEAR_STOP_PCT
        except (TypeError, ValueError):
            pass
        if below_stop or near_stop:
            risks.append({
                "ticker": ticker,
                "risk_state": "below_stop" if below_stop else "near_stop",
                "close": close,
                "stop": stop,
                "band_low": band.get("low"),
                "stop_gap": stop_gap,
                "stop_gap_pct": stop_gap_pct,
                "coverage_lane": (tracked.get(ticker, {}) or {}).get("coverage_lane"),
                "workflow_state": (tracked.get(ticker, {}) or {}).get("workflow_state"),
                "deployment_action_state": dep.get("action_state"),
            })
    return risks


def build_risk_alerts(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for risk in risks:
        ticker = risk["ticker"]
        risk_state = risk.get("risk_state")
        coverage_lane = str(risk.get("coverage_lane") or "")
        workflow_state = str(risk.get("workflow_state") or "")
        deployment_blocking = risk_state == "below_stop" and (
            coverage_lane == "execution" or workflow_state in {"DEPLOYED", "REPAIR"}
        )
        if risk_state == "below_stop":
            alerts.append({
                "severity": "deployment_blocking" if deployment_blocking else "warning",
                "ticker": ticker,
                "risk_state": risk_state,
                "message": f"{ticker} is below its explicit stop; do not treat any softer owner-approved/watch language as deployment authority.",
                "deployment_blocking": deployment_blocking,
                "risk_record": risk,
            })
        elif risk_state == "near_stop":
            alerts.append({
                "severity": "warning",
                "ticker": ticker,
                "risk_state": risk_state,
                "message": f"{ticker} is near its explicit stop; require repair/no-chase language before deployment review.",
                "deployment_blocking": False,
                "risk_record": risk,
            })
    return alerts


def add_issue(issues: list[dict[str, Any]], severity: str, ticker: str, surface: str, code: str, message: str, evidence: str = "") -> None:
    issues.append({
        "severity": severity,
        "ticker": ticker,
        "surface": surface,
        "code": code,
        "message": message,
        "evidence": evidence[:500],
    })


def evaluate() -> dict[str, Any]:
    risks = build_risk_records()
    risk_alerts = build_risk_alerts(risks)
    issues: list[dict[str, Any]] = []

    tech_note = read_text(TECHNICAL_NOTE)
    trigger_note = read_text(TRIGGER_NOTE)
    snapshot_note = read_text(SNAPSHOT_NOTE)
    watchlist_note = read_text(WATCHLIST_NOTE)
    regime_note = read_text(REGIME_NOTE)

    trigger_records = records_by_ticker(load_json(TRIGGER))
    regime_records = records_by_ticker(load_json(REGIME))

    for risk in risks:
        ticker = risk["ticker"]
        below_stop = risk["risk_state"] == "below_stop"
        risk_label = "stop breach" if below_stop else "near-stop condition"

        regime_rec = regime_records.get(ticker, {})
        regime_row = markdown_table_row(regime_note, ticker)
        if below_stop:
            if regime_rec.get("stance") != "Do not touch" or "stop breached" not in str(regime_rec.get("band_note", "")).lower():
                add_issue(issues, "critical", ticker, "tmp/regime-scores.json", "regime_stop_not_hard_overridden", f"{ticker} is below stop but regime score does not force Do not touch + stop-breached note", json.dumps(regime_rec))
            if regime_row and ("do not touch" not in regime_row.lower() or "stop breached" not in regime_row.lower()):
                add_issue(issues, "critical", ticker, str(REGIME_NOTE.relative_to(WORKSPACE)), "regime_note_stop_not_visible", f"{ticker} Regime Matrix row does not visibly show stop-breached / do-not-touch state", regime_row)

        tech_section = markdown_section(tech_note, ticker)
        if not tech_section:
            add_issue(issues, "critical" if below_stop else "warning", ticker, str(TECHNICAL_NOTE.relative_to(WORKSPACE)), "missing_technical_section", f"{ticker} has a {risk_label} but no technical-note section was found")
        elif below_stop and not contains_stop_truth(tech_section, hard=True):
            add_issue(issues, "critical", ticker, str(TECHNICAL_NOTE.relative_to(WORKSPACE)), "technical_note_stop_missing", f"{ticker} is below stop but its technical section does not make stop breach / invalidation explicit", tech_section)
        elif not below_stop and not contains_stop_truth(tech_section):
            add_issue(issues, "warning", ticker, str(TECHNICAL_NOTE.relative_to(WORKSPACE)), "technical_note_near_stop_missing", f"{ticker} is within {NEAR_STOP_PCT:.1f}% of stop but its technical section does not flag stop/repair risk", tech_section)
        if contains_contradiction(tech_section) and not contains_stop_truth(tech_section):
            add_issue(issues, "critical", ticker, str(TECHNICAL_NOTE.relative_to(WORKSPACE)), "technical_note_contradiction", f"{ticker} technical section has softer action language without stop-risk override", tech_section)

        trigger_rec = trigger_records.get(ticker)
        trigger_row = markdown_table_row(trigger_note, ticker)
        if trigger_rec and below_stop and trigger_rec.get("action_state") != "DO NOT TOUCH":
            add_issue(issues, "critical", ticker, "tmp/trigger-sheet.json", "trigger_artifact_not_do_not_touch", f"{ticker} trigger artifact is below stop but action_state is {trigger_rec.get('action_state')}", json.dumps(trigger_rec))
        if trigger_row:
            trigger_lower = trigger_row.lower()
            coverage_lane = str(risk.get("coverage_lane") or "")
            if below_stop:
                if coverage_lane == "execution":
                    if "do not touch" not in trigger_lower or "stop" not in trigger_lower:
                        add_issue(issues, "critical", ticker, str(TRIGGER_NOTE.relative_to(WORKSPACE)), "trigger_note_stop_missing", f"{ticker} execution row does not show do-not-touch stop risk", trigger_row)
                elif "stop" not in trigger_lower and "repair" not in trigger_lower:
                    add_issue(issues, "warning", ticker, str(TRIGGER_NOTE.relative_to(WORKSPACE)), "trigger_note_watch_stop_missing", f"{ticker} watch/non-execution row does not show stop or repair risk", trigger_row)
            if contains_contradiction(trigger_row) and not contains_stop_truth(trigger_row):
                add_issue(issues, "critical", ticker, str(TRIGGER_NOTE.relative_to(WORKSPACE)), "trigger_note_contradiction", f"{ticker} trigger-note row has stale softer state language", trigger_row)

        watch_row = markdown_table_row(watchlist_note, ticker)
        if watch_row and below_stop and contains_contradiction(watch_row) and not contains_stop_truth(watch_row):
            add_issue(issues, "critical", ticker, str(WATCHLIST_NOTE.relative_to(WORKSPACE)), "coverage_watchlist_contradiction", f"{ticker} coverage/watchlist row has stale softer action-state language", watch_row)

        snapshot_row = markdown_table_row(snapshot_note, ticker)
        if snapshot_row and below_stop and contains_contradiction(snapshot_row) and not contains_stop_truth(snapshot_row):
            add_issue(issues, "critical", ticker, str(SNAPSHOT_NOTE.relative_to(WORKSPACE)), "snapshot_contradiction", f"{ticker} snapshot row has stale softer state language", snapshot_row)

    summary = {
        "critical": sum(1 for i in issues if i["severity"] == "critical"),
        "warning": sum(1 for i in issues if i["severity"] == "warning") + len(risk_alerts),
        "note_contradiction_critical": sum(1 for i in issues if i["severity"] == "critical"),
        "note_contradiction_warning": sum(1 for i in issues if i["severity"] == "warning"),
        "risk_alerts": len(risk_alerts),
        "risk_records": len(risks),
        "below_stop": [r["ticker"] for r in risks if r["risk_state"] == "below_stop"],
        "near_stop": [r["ticker"] for r in risks if r["risk_state"] == "near_stop"],
        "deployment_blocking": [a["ticker"] for a in risk_alerts if a.get("deployment_blocking")],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "critical" if summary["critical"] else ("warning" if summary["warning"] else "ok"),
        "authority": {
            "posture": "read_only_guardrail",
            "standing_authority_scope": "main_session_bounded_workspace_canon_portfolio_maintenance",
            "canonical_mutation_allowed": True,
            "canonical_note_mutation_allowed": True,
            "portfolio_mutation_allowed": True,
            "owner_approval_granted": True,
            "artifact_mutation_allowed_by_this_guardrail": False,
            "deployment_authority_allowed": False,
            "trade_execution_allowed": False,
        },
        "summary": summary,
        "risks": risks,
        "risk_alerts": risk_alerts,
        "issues": issues,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Board Canon Guardrail", ""]
    lines.append(f"- Generated: `{report['generated_at_utc']}`")
    lines.append(f"- Status: **{report['status']}**")
    lines.append("- Authority: main-session standing canon/portfolio maintenance authority acknowledged; this guardrail itself is read-only and grants no deployment or trade execution authority")
    summary = report["summary"]
    lines.append(f"- Summary: {summary['critical']} critical / {summary['warning']} warning; below-stop={', '.join(summary['below_stop']) or '-'}; near-stop={', '.join(summary['near_stop']) or '-'}")
    if summary.get("deployment_blocking"):
        lines.append(f"- Deployment-blocking risk alerts: {', '.join(summary['deployment_blocking'])}")
    lines.append("")
    if report.get("risk_alerts"):
        lines.append("## Risk alerts")
        for alert in report["risk_alerts"]:
            lines.append(f"- **{alert['severity'].upper()}** `{alert['ticker']}` — {alert['message']}")
        lines.append("")
    if report["issues"]:
        lines.append("## Issues")
        for issue in report["issues"]:
            lines.append(f"- **{issue['severity'].upper()}** `{issue['ticker']}` `{issue['surface']}` `{issue['code']}` — {issue['message']}")
    else:
        lines.append("No board/canon stop-state contradictions found.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check below-stop / near-stop artifacts against canonical board notes.")
    parser.add_argument("--write", action="store_true", help="Write tmp/board-canon-guardrail.json and .md")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on warnings as well as critical findings")
    args = parser.parse_args()

    report = evaluate()
    if args.write:
        OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
        OUT_MD.write_text(render_md(report), encoding="utf-8")
        print(f"wrote {OUT_JSON}")
        print(f"wrote {OUT_MD}")

    summary = report["summary"]
    print(f"board_canon_guardrail: {report['status']} ({summary['critical']} critical, {summary['warning']} warning)")
    print(f"below_stop: {', '.join(summary['below_stop']) or '-'}")
    print(f"near_stop: {', '.join(summary['near_stop']) or '-'}")
    for issue in report["issues"][:20]:
        print(f"  - [{issue['severity']}] {issue['ticker']} {issue['surface']} {issue['code']}: {issue['message']}")

    if summary["critical"]:
        return 2
    if args.strict and summary["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
