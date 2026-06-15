"""Render the compact WF79 dashboard shell from the presentation view model."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

VIEW_MODEL = TMP / "dashboard-presentation-view-model.json"
V2_READER = TMP / "dashboard-v2-reader-migration.json"
OUT = TMP / "veritas-command-center-compact.html"
READER_OUT = TMP / "veritas-command-center-compact-reader.json"
VALIDATION = TMP / "dashboard-compact-shell-validation.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def esc(value: Any) -> str:
    return str(value if value is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_panel(panel: dict[str, Any]) -> str:
    tone = panel.get("tone") or "info"
    routes = ", ".join(esc(route) for route in as_list(panel.get("route_sections"))) or "none"
    proofs = ", ".join(esc(ref) for ref in as_list(panel.get("proof_ref"))) or "none"
    return f"""
    <article class="panel tone-{esc(tone)}">
      <div class="panel-head">
        <h2>{esc(panel.get('id'))}</h2>
        <span>{esc(panel.get('severity'))}</span>
      </div>
      <p class="headline">{esc(panel.get('headline'))}</p>
      <dl>
        <div><dt>State</dt><dd>{esc(panel.get('state'))}</dd></div>
        <div><dt>Freshness</dt><dd>{esc(panel.get('freshness'))}</dd></div>
        <div><dt>Reason</dt><dd>{esc(panel.get('primary_reason'))}</dd></div>
        <div><dt>Owner action</dt><dd>{esc(panel.get('owner_action_required'))}</dd></div>
        <div><dt>Routes</dt><dd>{routes}</dd></div>
        <div><dt>Proof refs</dt><dd>{proofs}</dd></div>
      </dl>
    </article>
    """


def render_html(view_model: dict[str, Any], v2_reader: dict[str, Any]) -> str:
    panels = as_list(view_model.get("panels"))
    summary = as_dict(view_model.get("summary"))
    migrated = as_dict(v2_reader.get("summary"))
    nav = "".join(f"<a href=\"#{esc(as_dict(panel).get('id'))}\">{esc(as_dict(panel).get('id'))}</a>" for panel in panels)
    cards = []
    for panel in panels:
        panel = as_dict(panel)
        html = render_panel(panel).replace("<article", f"<article id=\"{esc(panel.get('id'))}\"", 1)
        cards.append(html)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Veritas Compact Command Center</title>
<style>
:root {{ color-scheme: dark; --bg:#0b1120; --panel:#111827; --line:#334155; --text:#e5e7eb; --muted:#94a3b8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; --info:#38bdf8; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family:Segoe UI,Arial,sans-serif; }}
header {{ padding:20px 24px 12px; border-bottom:1px solid var(--line); position:sticky; top:0; background:rgba(11,17,32,.96); backdrop-filter: blur(8px); z-index:2; }}
h1 {{ margin:0; font-size:22px; }}
.meta {{ color:var(--muted); font-size:12px; margin-top:6px; }}
nav {{ display:flex; flex-wrap:wrap; gap:8px; padding-top:12px; }}
nav a {{ color:var(--text); text-decoration:none; border:1px solid var(--line); border-radius:6px; padding:6px 9px; font-size:12px; }}
main {{ padding:18px 24px 28px; display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; }}
.panel {{ background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--info); border-radius:8px; padding:14px; }}
.tone-ok {{ border-left-color:var(--ok); }} .tone-warn {{ border-left-color:var(--warn); }} .tone-bad {{ border-left-color:var(--bad); }}
.panel-head {{ display:flex; justify-content:space-between; gap:10px; align-items:center; }}
h2 {{ margin:0; font-size:15px; }}
.panel-head span {{ border:1px solid var(--line); border-radius:999px; padding:3px 8px; color:var(--muted); font-size:11px; }}
.headline {{ color:var(--text); margin:10px 0; }}
dl {{ display:grid; gap:8px; margin:0; }}
dt {{ color:var(--muted); font-size:11px; text-transform:uppercase; }}
dd {{ margin:2px 0 0; font-size:13px; word-break:break-word; }}
</style>
</head>
<body>
<header>
  <h1>Veritas Compact Command Center</h1>
  <div class="meta">Generated {esc(view_model.get('generated_at_utc'))} | panels {len(panels)} | migrated {esc(migrated.get('migrated_panel_count'))}/{esc(migrated.get('target_panel_count'))} | review-only compact route</div>
  <div class="meta">Legacy dashboard remains available for row-level drilldown. This shell is not canon, approval, or execution authority.</div>
  <div class="meta"><a href="veritas-command-center.html">Open Randall Full Detail Dashboard</a> | <a href="dashboard-presentation-view-model.json">Open compact view model JSON</a> | <a href="veritas-command-center-compact-reader.json">Open Veritas compact reader JSON</a></div>
  <nav>{nav}</nav>
</header>
<main>
{''.join(cards)}
</main>
</body>
</html>
"""


def build_reader(view_model: dict[str, Any], v2_reader: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    panels = [as_dict(panel) for panel in as_list(view_model.get("panels"))]
    top_actions: list[dict[str, Any]] = []
    blocked_items: list[dict[str, Any]] = []
    stale_inputs: list[dict[str, Any]] = []
    finance_review_queue: list[dict[str, Any]] = []
    proof_links: set[str] = set()
    owner_approval_required = False
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    for panel in panels:
        panel_id = str(panel.get("id") or "")
        severity = str(panel.get("severity") or "info")
        state = str(panel.get("state") or "unknown")
        reason = str(panel.get("primary_reason") or "")
        owner_action = str(panel.get("owner_action_required") or "")
        proofs = [str(ref) for ref in as_list(panel.get("proof_ref")) if ref]
        proof_links.update(proofs)
        row = {
            "panel_id": panel_id,
            "headline": panel.get("headline"),
            "severity": severity,
            "state": state,
            "freshness": panel.get("freshness"),
            "reason": reason,
            "owner_action_required": owner_action,
            "proof_ref": proofs,
        }
        if "approval" in owner_action.lower() or "owner" in owner_action.lower():
            owner_approval_required = True
        if severity in {"critical", "warning"}:
            top_actions.append(row)
        if "blocked" in state.lower() or "blocked" in reason.lower() or severity == "critical":
            blocked_items.append(row)
        if str(panel.get("freshness") or "").lower() == "stale" or "stale" in state.lower():
            stale_inputs.append(row)
        if panel_id in {"deployment", "portfolio", "technical", "command_today"}:
            finance_review_queue.append(row)

    top_actions = sorted(top_actions, key=lambda item: severity_order.get(str(item.get("severity")), 9))[:10]
    migrated = as_dict(v2_reader.get("summary"))
    return {
        "schema_version": "veritas_command_center_compact_reader.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": validation.get("status", "unknown"),
        "purpose": "Machine-readable first-read route for Veritas; Randall full-detail dashboard is retained separately.",
        "routes": {
            "veritas_primary_reader": relpath(READER_OUT),
            "veritas_primary_html": relpath(OUT),
            "randall_full_detail_html": "tmp/veritas-command-center.html",
            "legacy_payload": "tmp/dashboard-data.json",
            "compact_view_model": relpath(VIEW_MODEL),
            "v2_reader_migration": relpath(V2_READER),
        },
        "summary": {
            "panel_count": len(panels),
            "top_action_count": len(top_actions),
            "blocked_item_count": len(blocked_items),
            "stale_input_count": len(stale_inputs),
            "finance_review_queue_count": len(finance_review_queue),
            "owner_approval_required": owner_approval_required,
            "all_compact_panels_migrated": migrated.get("all_compact_panels_migrated") is True,
            "legacy_payload_retained_by_design": True,
            "legacy_dashboard_replaced": False,
            "next_safe_action": "Use compact reader/shell as the first-read route; open Randall full detail dashboard for row-level drilldown.",
        },
        "top_actions": top_actions,
        "blocked_items": blocked_items,
        "stale_inputs": stale_inputs,
        "finance_review_queue": finance_review_queue,
        "proof_links": sorted(proof_links),
        "authority": {
            "review_only": True,
            "legacy_dashboard_replaced": False,
            "legacy_payload_retained_by_design": True,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def validate(view_model: dict[str, Any], v2_reader: dict[str, Any], html: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not VIEW_MODEL.exists():
        findings.append({"severity": "critical", "issue": "missing_view_model"})
    if not V2_READER.exists():
        findings.append({"severity": "critical", "issue": "missing_v2_reader"})
    panels = as_list(view_model.get("panels"))
    if len(panels) < 8:
        findings.append({"severity": "critical", "issue": "panel_count_low", "panel_count": len(panels)})
    if as_dict(v2_reader.get("summary")).get("all_compact_panels_migrated") is not True:
        findings.append({"severity": "critical", "issue": "v2_reader_not_all_panels"})
    for token in ("Veritas Compact Command Center", "review-only compact route", "Legacy dashboard remains available"):
        if token not in html:
            findings.append({"severity": "critical", "issue": "missing_shell_token", "token": token})
    for token in ("Open Randall Full Detail Dashboard", "Open Veritas compact reader JSON"):
        if token not in html:
            findings.append({"severity": "critical", "issue": "missing_route_link_token", "token": token})
    return findings


def write_outputs() -> tuple[str, dict[str, Any]]:
    view_model = as_dict(read_json(VIEW_MODEL)) if VIEW_MODEL.exists() else {}
    v2_reader = as_dict(read_json(V2_READER)) if V2_READER.exists() else {}
    html = render_html(view_model, v2_reader)
    findings = validate(view_model, v2_reader, html)
    validation = {
        "schema_version": "dashboard_compact_shell_validation.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "output": relpath(OUT),
        "reader_output": relpath(READER_OUT),
        "source_view_model": relpath(VIEW_MODEL),
        "source_v2_reader": relpath(V2_READER),
        "findings": findings,
    }
    reader = build_reader(view_model, v2_reader, validation)
    OUT.write_text(html, encoding="utf-8")
    READER_OUT.write_text(json.dumps(reader, indent=2) + "\n", encoding="utf-8")
    VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    return html, validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Render compact WF79 dashboard shell.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    html, validation = write_outputs() if args.write else ("", {"status": "ok", "critical": 0})
    if args.write:
        print(f"wrote {relpath(OUT)}")
        print(f"wrote {relpath(VALIDATION)}")
    print(f"dashboard_compact_shell: {validation['status']} ({validation['critical']} critical)")
    return 1 if args.validate and validation["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
