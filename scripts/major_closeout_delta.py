#!/usr/bin/env python3
"""Generate a compact major-work closeout delta from automation health trends.

Report-only helper for WF72. It reads the dashboard trend artifact and bloat guard
and writes a small closeout snippet that can be pasted into future major-work
summaries without re-reading large telemetry artifacts.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
TREND = TMP / "automation-health-dashboard-trends.json"
BLOAT = TMP / "tool-bloat-reduction-guard.json"
OTEL = TMP / "telemetry-audit-window-closeout.json"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
JSON_OUT = TMP / "major-closeout-telemetry-delta.json"
MD_OUT = JSON_OUT.with_suffix(".md")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build() -> dict[str, Any]:
    trend = load(TREND)
    bloat = load(BLOAT)
    otel = load(OTEL)
    active_config = load(OPENCLAW_CONFIG)
    active_otel = (active_config.get("diagnostics") or {}).get("otel") or {}
    metrics = trend.get("metric_changes") or trend.get("metrics") or {}
    # trend artifact stores metric_changes as dict in JSON; tolerate list forms too.
    if isinstance(metrics, list):
        metrics = {m.get("metric"): m for m in metrics if isinstance(m, dict)}
    counts = bloat.get("counts") or {}
    current_otel = active_otel or (otel.get("current_diagnostics_otel") or otel.get("audit_window") or {})
    capture = current_otel.get("captureContent") or current_otel.get("captureContent_now") or {}
    return {
        "generated_at_utc": utc_now(),
        "status": "ready",
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": "Closeout summary only; no config/runtime/canon/finance mutation authority.",
        "summary": {
            "overall_trend": trend.get("overall_direction") or trend.get("overall") or trend.get("snapshot_trend", {}).get("direction"),
            "current_overall_status": trend.get("current_overall_status") or trend.get("current", {}).get("overall_status"),
            "medium_tool_events": counts.get("medium_events"),
            "high_tool_events": counts.get("high_events"),
            "truncated_tool_events": counts.get("truncated_events"),
            "otel_logs_enabled": current_otel.get("logs") if "logs" in current_otel else otel.get("audit_window", {}).get("logs_now"),
            "otel_capture_enabled": capture.get("enabled") if isinstance(capture, dict) else otel.get("audit_window", {}).get("captureContent_now", {}).get("enabled"),
            "otel_tool_inputs_enabled": capture.get("toolInputs") if isinstance(capture, dict) else None,
            "otel_tool_outputs_enabled": capture.get("toolOutputs") if isinstance(capture, dict) else None,
            "external_export": False,
        },
        "closeout_bullets": [
            "Telemetry baseline: local metrics/traces remain enabled; logs/content capture should be off outside explicit audit windows.",
            "Tool-bloat trend: include medium/high/truncated event counts and top offender tools in major closeouts.",
            "If bloat worsened, next run should use SQL/artifact-index routing, bounded reads, capped web_fetch, and artifact-path exec output.",
            "Dashboard trend is review-only evidence; it does not authorize finance/canon/trade/account/paper actions.",
        ],
    }


def render(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Major Closeout Telemetry Delta",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        "",
        f"Status: **{report['status']}**",
        "",
        "## Compact closeout fields",
        "",
        f"- Overall trend: `{s.get('overall_trend')}`",
        f"- Current overall status: `{s.get('current_overall_status')}`",
        f"- Medium tool events: `{s.get('medium_tool_events')}`",
        f"- High tool events: `{s.get('high_tool_events')}`",
        f"- Truncated tool events: `{s.get('truncated_tool_events')}`",
        f"- OTEL logs enabled now: `{s.get('otel_logs_enabled')}`",
        f"- OTEL content capture enabled now: `{s.get('otel_capture_enabled')}`",
        f"- OTEL tool inputs enabled now: `{s.get('otel_tool_inputs_enabled')}`",
        f"- OTEL tool outputs enabled now: `{s.get('otel_tool_outputs_enabled')}`",
        f"- External export: `{s.get('external_export')}`",
        "",
        "## Required closeout bullets",
        "",
    ]
    lines.extend(f"- {b}" for b in report["closeout_bullets"])
    lines.append("")
    return "\n".join(lines)


def validate(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("report_only") is not True:
        errors.append("report_only must be true")
    if report.get("mutations_performed") is not False:
        errors.append("mutations_performed must be false")
    if report["summary"].get("external_export") is not False:
        errors.append("external_export must remain false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest beside the JSON report.")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build()
    errors = validate(report)
    if args.validate and errors:
        print(json.dumps({"status": "failed", "errors": errors}, indent=2))
        return 1
    if args.write:
        JSON_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.write_md:
            MD_OUT.write_text(render(report), encoding="utf-8")
        print(f"status={report['status']} output={JSON_OUT.as_posix()}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
