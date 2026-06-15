from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]


def read_json(path: Path, required: bool, findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.exists():
        findings.append({"severity": "critical" if required else "warning", "code": "missing_artifact", "path": str(path.relative_to(WORKSPACE))})
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        findings.append({"severity": "critical", "code": "unparseable_json", "path": str(path.relative_to(WORKSPACE)), "detail": str(exc)})
        return {}


def parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def add(f: list[dict[str, Any]], severity: str, code: str, detail: str, **extra: Any) -> None:
    row = {"severity": severity, "code": code, "detail": detail}
    row.update(extra)
    f.append(row)


def build(args: argparse.Namespace) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    deployment = read_json(WORKSPACE / args.deployment, True, findings)
    recs = read_json(WORKSPACE / args.recommendations, True, findings)
    rec_val = read_json(WORKSPACE / args.recommendation_validation, True, findings)
    current_window = read_json(WORKSPACE / args.current_window, False, findings)
    dashboard_validation = read_json(WORKSPACE / args.dashboard_validation, False, findings)
    official = read_json(WORKSPACE / args.official_reconciliation, False, findings)

    system = deployment.get("system", {}) if isinstance(deployment, dict) else {}
    presentation_allowed = bool(system.get("presentation_allowed"))
    macro_gate = system.get("macro_gate")
    timestamp_gap = system.get("timestamp_gap_hours")
    warning_codes = system.get("warning_codes") or []

    if not presentation_allowed:
        add(findings, "critical", "presentation_disallowed", "Deployment readiness surface blocks clean advisor presentation.")
    if macro_gate and macro_gate != "CLEAN":
        add(findings, "warning", "macro_gate_degraded", f"Macro/deployment gate is {macro_gate}.")
    if isinstance(timestamp_gap, (int, float)):
        if timestamp_gap > 6:
            add(findings, "critical", "timestamp_lineage_gap", f"Run-summary/trigger timestamp gap is {timestamp_gap}h (>6h clean-display stop).", hours=timestamp_gap)
        elif timestamp_gap > 2:
            add(findings, "warning", "timestamp_lineage_gap", f"Run-summary/trigger timestamp gap is {timestamp_gap}h (>2h warning).", hours=timestamp_gap)
    if warning_codes:
        add(findings, "warning", "deployment_warning_propagated", "Deployment readiness has warning codes.", warning_codes=warning_codes)

    proposals = recs.get("proposals", []) if isinstance(recs, dict) else []
    packet_results = []
    partial_count = 0
    capital_blocked_count = 0
    for packet in proposals:
        freshness = packet.get("source_freshness", {}) if isinstance(packet, dict) else {}
        ticker = packet.get("ticker_or_scope") or packet.get("ticker") or "UNKNOWN"
        partial = freshness.get("overall_classification") != "current"
        blocked = freshness.get("capital_action_allowed") is not True
        if partial:
            partial_count += 1
        if blocked:
            capital_blocked_count += 1
        packet_results.append({
            "ticker_or_scope": ticker,
            "source_freshness": freshness.get("overall_classification"),
            "explicit_blocker": freshness.get("explicit_blocker"),
            "capital_action_allowed": freshness.get("capital_action_allowed"),
            "trust_posture": "blocked_or_review_required" if partial or blocked else "review_display_ok",
        })
    if partial_count:
        add(findings, "warning", "source_freshness_partial", f"{partial_count} recommendation packet(s) are not current/clean.", count=partial_count)
    if capital_blocked_count:
        add(findings, "warning", "capital_action_blocked", f"{capital_blocked_count} recommendation packet(s) have capital_action_allowed=false.", count=capital_blocked_count)

    authority = recs.get("authority", {}) if isinstance(recs, dict) else {}
    forbidden_true = []
    for key in ["apply_allowed", "proposal_apply_allowed", "trade_or_account_action_allowed", "trade_execution_allowed", "per_packet_owner_approval_inferred"]:
        if authority.get(key) is True or recs.get(key) is True:
            forbidden_true.append(key)
    if forbidden_true:
        add(findings, "critical", "authority_conflict", "Forbidden authority flag(s) true.", flags=forbidden_true)

    val_summary = rec_val.get("summary", {}) if isinstance(rec_val, dict) else {}
    if rec_val.get("status") != "ok" or val_summary.get("critical", 0) not in (0, None):
        add(findings, "critical", "capital_validator_not_clean", "Capital recommendation validator is not clean.", status=rec_val.get("status"), summary=val_summary)

    cw_summary = current_window.get("summary", {}) if isinstance(current_window, dict) else {}
    missing_roles = cw_summary.get("missing_required_roles") or []
    if missing_roles:
        add(findings, "critical", "current_window_missing_required_roles", "Current-window index is missing required roles.", roles=missing_roles)

    dash_counts = dashboard_validation.get("counts", {}) if isinstance(dashboard_validation, dict) else {}
    dash_warnings = dash_counts.get("warnings") or dashboard_validation.get("summary", {}).get("warning")
    if dash_warnings:
        add(findings, "warning", "dashboard_warning_propagated", "Dashboard validation has warning(s).", warnings=dash_warnings)

    official_summary = official.get("summary", {}) if isinstance(official, dict) else {}
    manual_required = official_summary.get("manual_required")
    sec_counts = official_summary.get("sec_reconciliation_status_counts") or {}
    if manual_required:
        add(findings, "warning", "official_reconciliation_manual_required", f"{manual_required} official-source packet(s) require manual review.", count=manual_required)
    if sec_counts.get("no_period_match", 0):
        add(findings, "warning", "official_sec_no_period_match", "SEC reconciliation has no-period-match packet(s).", counts=sec_counts)

    critical = sum(1 for x in findings if x["severity"] == "critical")
    warning = sum(1 for x in findings if x["severity"] == "warning")
    status = "critical" if critical else ("warning" if warning else "ok")
    display_pref = "degraded_with_red_trust_banner" if args.allow_degraded_banner else "artifact_only_until_clean"
    presentation_posture = "clean_review_display" if status == "ok" else (display_pref if args.allow_degraded_banner and critical == 0 else "artifact_only_red_trust_banner")
    if critical and args.allow_degraded_banner:
        presentation_posture = "degraded_artifact_display_with_red_trust_banner"

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "severity_counts": {"critical": critical, "warning": warning, "info": sum(1 for x in findings if x["severity"] == "info")},
        "presentation_posture": presentation_posture,
        "dashboard_banner": "RED TRUST BANNER: advisor packets are degraded/review-only; do not treat as approval, execution authority, or clean capital-action readiness." if status != "ok" else "Trust gate clean for review display only; execution/apply authority remains false.",
        "capital_action_allowed": False,
        "apply_allowed": False,
        "proposal_apply_allowed": False,
        "trade_or_account_action_allowed": False,
        "owner_approval_inferred": False,
        "findings": findings,
        "lineage": {
            "deployment_generated_at_utc": deployment.get("generated_at_utc"),
            "recommendations_generated_at_utc": recs.get("generated_at_utc"),
            "recommendation_validation_generated_at_utc": rec_val.get("generated_at_utc"),
            "current_window_generated_at_utc": current_window.get("generated_at_utc"),
            "official_reconciliation_generated_at_utc": official.get("generated_at_utc"),
            "run_summary_generated_at_utc": system.get("run_summary_generated_at_utc"),
            "trigger_generated_at_utc": system.get("trigger_generated_at_utc"),
            "timestamp_gap_hours": timestamp_gap,
        },
        "packet_results": packet_results,
        "boundary": "review/display trust gate only; no canon/portfolio mutation, owner approval inference, trading/account/paper/live authority, or money movement",
    }


def write_md(report: dict[str, Any], path: Path) -> None:
    lines = ["# Advisor Packet Trust-Coherence Gate", "", f"- Generated UTC: `{report['generated_at_utc']}`", f"- Status: **{report['status']}**", f"- Presentation posture: **{report['presentation_posture']}**", "", "## Dashboard banner", "", report["dashboard_banner"], "", "## Findings", ""]
    for f in report["findings"]:
        lines.append(f"- **{f['severity']} / {f['code']}**: {f['detail']}")
    lines += ["", "## Packet results", "", "| Ticker/scope | Freshness | Explicit blocker | Capital action allowed | Trust posture |", "|---|---|---:|---:|---|"]
    for p in report["packet_results"]:
        lines.append(f"| {p['ticker_or_scope']} | {p.get('source_freshness')} | {p.get('explicit_blocker')} | {p.get('capital_action_allowed')} | {p.get('trust_posture')} |")
    lines += ["", "## Boundary", "", report["boundary"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deployment", default="tmp/deployment-readiness-surface.json")
    ap.add_argument("--recommendations", default="tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    ap.add_argument("--recommendation-validation", default="tmp/capital-deployment-recommendation-validation.json")
    ap.add_argument("--current-window", default="tmp/current-window-artifacts.json")
    ap.add_argument("--dashboard-validation", default="tmp/dashboard-validation.json")
    ap.add_argument("--official-reconciliation", default="tmp/fundamental-ir-reconciliation-packets.json")
    ap.add_argument("--out", default="tmp/advisor-packet-trust-coherence-gate.json")
    ap.add_argument("--md", default=None, help="Optional Markdown output path; JSON is the default proof contract.")
    ap.add_argument("--allow-degraded-banner", action="store_true", default=True)
    args = ap.parse_args()
    report = build(args)
    out = WORKSPACE / args.out
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.md:
        md = WORKSPACE / args.md
        write_md(report, md)
    print(json.dumps({"status": report["status"], "critical": report["severity_counts"]["critical"], "warning": report["severity_counts"]["warning"], "presentation_posture": report["presentation_posture"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
