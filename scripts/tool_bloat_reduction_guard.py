#!/usr/bin/env python3
"""Validate and summarize redacted tool-result bloat reduction posture.

Report-only guard: consumes tmp/redacted-tool-result-telemetry.json and emits a
small policy artifact. It does not mutate transcripts, config, tools, or runtime.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
INPUT = TMP / "redacted-tool-result-telemetry.json"
JSON_OUT = TMP / "tool-bloat-reduction-guard.json"
MD_OUT = TMP / "tool-bloat-reduction-guard.md"
DEFAULT_BASELINE = TMP / "tool-bloat-reduction-baseline.json"

POLICY = [
    "Prefer SQL cockpit/artifact index before reading large generated artifacts.",
    "Use read offset/limit or targeted search after the first locator is known.",
    "For exec commands that can emit large output, write full output to a tmp artifact and print only status plus artifact path.",
    "For web_fetch, lower maxChars and keep URLs/provenance instead of dumping full pages.",
    "For cron/subagent results, return compact closeout plus artifact paths, not full artifact bodies.",
    "Use redacted telemetry and scorecard artifacts as the review surface; do not export raw tool bodies by default.",
]

TOOL_ACTIONS = {
    "read": "Use artifact_index/sql cockpit, then bounded read(offset/limit) only for the exact section needed.",
    "exec": "Redirect verbose command output to tmp artifacts and print status, counts, and artifact path only.",
    "web_fetch": "Lower maxChars and preserve source URL/provenance instead of full extracted page text.",
    "memory_search": "Use lower maxResults for narrow recall and follow with targeted memory_get lines only.",
    "cron": "Return compact job/run summaries and artifact paths; avoid embedding full payload bodies in closeouts.",
    "process": "Use process log limits and write long logs to tmp artifacts before summarizing.",
    "sessions_history": "Use small limits and includeTools=false unless tool history is required for diagnosis.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pct_change(before: int | None, after: int | None) -> float | None:
    if before is None or after is None or before <= 0:
        return None
    return round(((after - before) / before) * 100, 2)


def build_comparison(current_counts: dict[str, int], baseline: dict[str, Any]) -> dict[str, Any] | None:
    if not baseline:
        return None
    base_counts = baseline.get("counts") or baseline.get("baseline_counts") or {}
    if not isinstance(base_counts, dict):
        return None
    out: dict[str, Any] = {"baseline_path_hint": baseline.get("path_hint"), "metrics": {}}
    for key in ["tool_result_events", "medium_events", "high_events", "truncated_events"]:
        before = base_counts.get(key)
        after = current_counts.get(key)
        if isinstance(before, int) and isinstance(after, int):
            out["metrics"][key] = {"baseline": before, "current": after, "delta": after - before, "pct_change": pct_change(before, after)}
    return out


def build_report(data: dict[str, Any], baseline: dict[str, Any] | None = None, target_reduction_pct: float = 25.0) -> dict[str, Any]:
    events = data.get("events") or []
    by_tool = data.get("summary_by_tool") or {}
    high = [e for e in events if isinstance(e, dict) and e.get("severity") == "high"]
    medium = [e for e in events if isinstance(e, dict) and e.get("severity") == "medium"]
    truncated = [e for e in events if isinstance(e, dict) and e.get("truncated") is True]
    # Tools with the largest total output are the first behavior targets.
    top_tools = sorted(
        ((tool, vals) for tool, vals in by_tool.items() if isinstance(vals, dict)),
        key=lambda pair: pair[1].get("total_output_chars", 0),
        reverse=True,
    )[:8]
    counts = {
        "tool_result_events": data.get("events_count", len(events)),
        "medium_events": len(medium),
        "high_events": len(high),
        "truncated_events": len(truncated),
    }
    comparison = build_comparison(counts, baseline or {})
    target = {
        "target_reduction_pct": target_reduction_pct,
        "medium_events_target_max": None,
        "truncated_events_target_max": None,
        "target_met": None,
    }
    if comparison:
        metrics = comparison.get("metrics", {})
        base_medium = metrics.get("medium_events", {}).get("baseline")
        base_truncated = metrics.get("truncated_events", {}).get("baseline")
        if isinstance(base_medium, int):
            target["medium_events_target_max"] = max(0, round(base_medium * (1 - target_reduction_pct / 100)))
            target["medium_target_met"] = counts["medium_events"] <= target["medium_events_target_max"]
        if isinstance(base_truncated, int):
            target["truncated_events_target_max"] = max(0, round(base_truncated * (1 - target_reduction_pct / 100)))
            target["truncated_target_met"] = counts["truncated_events"] <= target["truncated_events_target_max"]
        relevant = [target.get("medium_target_met"), target.get("truncated_target_met")]
        known = [item for item in relevant if item is not None]
        target["target_met"] = all(known) if known else None
    return {
        "generated_at_utc": utc_now(),
        "status": "warning" if medium or truncated else "ok",
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": "No config/auth/runtime/tool mutation; report-only behavior guard for future operator discipline.",
        "thresholds": {
            "hard_fail_high_severity_events": 0,
            "warning_medium_events_present": True,
            "warning_truncated_events_present": True,
        },
        "counts": counts,
        "comparison": comparison,
        "target": target,
        "top_output_tools": [
            {
                "tool": tool,
                "count": vals.get("count"),
                "total_output_chars": vals.get("total_output_chars"),
                "max_output_chars": vals.get("max_output_chars"),
                "next_action": TOOL_ACTIONS.get(tool, "Summarize output and store verbose details in a tmp artifact when practical."),
            }
            for tool, vals in top_tools
        ],
        "policy": POLICY,
        "acceptance": {
            "no_raw_tool_bodies_exported": "inherited from redacted telemetry contract",
            "hard_fail": len(high) > 0,
            "next_target": "reduce medium/truncated events by using bounded reads, capped fetches, and artifact-path closeouts",
        },
    }


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Tool Bloat Reduction Guard",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        "",
        f"Status: **{report['status']}**",
        "",
        "## Counts",
        "",
    ]
    for key, value in report["counts"].items():
        lines.append(f"- {key}: `{value}`")
    if report.get("comparison"):
        lines.extend(["", "## Baseline comparison", "", "| Metric | Baseline | Current | Delta | Pct change |", "|---|---:|---:|---:|---:|"])
        for key, item in report["comparison"].get("metrics", {}).items():
            lines.append(f"| `{key}` | {item.get('baseline')} | {item.get('current')} | {item.get('delta')} | {item.get('pct_change')}% |")
        target = report.get("target") or {}
        lines.extend(["", "## Target", "", f"- Target reduction: `{target.get('target_reduction_pct')}`%", f"- Medium target max: `{target.get('medium_events_target_max')}`", f"- Truncated target max: `{target.get('truncated_events_target_max')}`", f"- Target met: `{target.get('target_met')}`"])
    lines.extend(["", "## Top output tools", "", "| Tool | Count | Total chars | Max chars | Next action |", "|---|---:|---:|---:|---|"])
    for item in report["top_output_tools"]:
        lines.append(f"| `{item['tool']}` | {item['count']} | {item['total_output_chars']} | {item['max_output_chars']} | {item['next_action']} |")
    lines.extend(["", "## Policy", ""])
    lines.extend(f"- {item}" for item in report["policy"])
    lines.extend(["", "## Acceptance", "", f"- hard_fail: `{report['acceptance']['hard_fail']}`", f"- next_target: {report['acceptance']['next_target']}", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate report-only tool bloat reduction guard")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true", help="Also write legacy human-readable 09. Archive/Auto Archive - Generated Residue/WF72 JSON First Legacy Markdown/tool-bloat-reduction-guard.md")
    parser.add_argument("--baseline", type=Path, default=None, help="Optional prior guard/baseline JSON for before/after comparison.")
    parser.add_argument("--save-baseline", action="store_true", help="Write the current compact counts to tmp/tool-bloat-reduction-baseline.json.")
    parser.add_argument("--target-reduction-pct", type=float, default=25.0)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    baseline = load_json(args.baseline) if args.baseline else {}
    report = build_report(load_json(INPUT), baseline=baseline, target_reduction_pct=args.target_reduction_pct)
    if args.validate and report["counts"]["high_events"] > report["thresholds"]["hard_fail_high_severity_events"]:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    if args.save_baseline:
        DEFAULT_BASELINE.write_text(json.dumps({"generated_at_utc": report["generated_at_utc"], "counts": report["counts"], "path_hint": DEFAULT_BASELINE.as_posix()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.write:
        JSON_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.write_md:
            MD_OUT.write_text(render_md(report), encoding="utf-8")
        target_note = ""
        if report.get("target", {}).get("target_met") is not None:
            target_note = f" target_met={report['target']['target_met']}"
        print(f"status={report['status']} high={report['counts']['high_events']} medium={report['counts']['medium_events']} truncated={report['counts']['truncated_events']}{target_note} output={JSON_OUT.as_posix()}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
