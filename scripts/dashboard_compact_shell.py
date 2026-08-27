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
RETAIL_AUTOMATION = TMP / "retail-automation-control-plane.json"
RETAIL_HARNESS = TMP / "retail-answer-harness.json"
RETAIL_DECISION = TMP / "retail-customer-output-decision-packet.json"
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


def compact_values(values: Any, *, limit: int = 8) -> str:
    items = [str(item) for item in as_list(values) if item]
    if not items:
        return "none"
    shown = items[:limit]
    suffix = f" (+{len(items) - limit} more)" if len(items) > limit else ""
    return ", ".join(shown) + suffix


def render_bucket_cards(actionability: dict[str, Any]) -> str:
    buckets = as_dict(actionability.get("capital_buckets"))
    definitions = [
        ("deployable_now", "Deployable Now", "tickers"),
        ("owner_review", "Owner Review", "tickers"),
        ("pullback_only", "Pullback / No-Chase", "tickers"),
        ("below_stop", "Below Stop", "tickers"),
        ("blocked_or_stale", "Blocked / Stale", "items"),
        ("watch_research", "Watch / Research", "tickers"),
    ]
    cards = []
    for key, label, value_key in definitions:
        bucket = as_dict(buckets.get(key))
        cards.append(
            f"""
      <div class="bucket">
        <span>{esc(label)}</span>
        <b>{esc(bucket.get('count', 0))}</b>
        <small>{esc(compact_values(bucket.get(value_key)))}</small>
      </div>
            """
        )
    return "".join(cards)


def render_caveat_cards(actionability: dict[str, Any]) -> str:
    fundamentals = compact_values(
        [f"{as_dict(item).get('code')}: {compact_values(as_dict(item).get('tickers'), limit=5)}" for item in as_list(actionability.get("fundamentals_caveats"))],
        limit=3,
    )
    return f"""
    <div class="caveat"><span>Fundamentals</span><b>{esc(actionability.get('fundamentals_status'))} / {esc(actionability.get('fundamentals_warning_count'))} warning(s)</b><small>{esc(fundamentals)}</small></div>
    <div class="caveat"><span>Macro</span><b>{esc(actionability.get('macro_status'))} / {esc(actionability.get('macro_posture'))}</b><small>{esc(actionability.get('macro_caveat'))}</small></div>
    <div class="caveat"><span>Energy</span><b>{esc(actionability.get('energy_status'))}</b><small>{esc(actionability.get('energy_caveat'))}</small></div>
    """


def render_proof_routes(actionability: dict[str, Any]) -> str:
    proof = as_dict(actionability.get("proof_artifacts"))
    if not proof:
        return "<li>none</li>"
    return "".join(f"<li><span>{esc(key)}</span><code>{esc(path)}</code></li>" for key, path in sorted(proof.items()))


def retail_summary(automation: dict[str, Any], harness: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    regression = as_dict(automation.get("seeded_bad_regression"))
    categories = as_dict(regression.get("categories"))
    return {
        "status": automation.get("status") or "missing",
        "decision": decision.get("decision") or as_dict(automation.get("customer_output_decision")).get("decision") or "customer_output_blocked",
        "customer_output_allowed": decision.get("customer_output_allowed") is True,
        "internal_answer_safety_ready": decision.get("internal_answer_safety_ready") is True,
        "blockers": as_list(decision.get("customer_output_blockers")) or as_list(as_dict(automation.get("customer_output_decision")).get("blockers")),
        "seeded_bad_cases": regression.get("seeded_bad_cases") or as_dict(harness.get("summary")).get("seeded_bad_cases"),
        "blocked_as_expected": regression.get("blocked_as_expected"),
        "category_count": regression.get("category_count") or len(categories),
        "covered_category_count": regression.get("covered_category_count") or sum(1 for value in categories.values() if value),
        "categories": categories,
        "proof_artifacts": {
            "automation": relpath(RETAIL_AUTOMATION),
            "harness": relpath(RETAIL_HARNESS),
            "decision": relpath(RETAIL_DECISION),
        },
        "authority": {
            "review_only": True,
            "customer_output_allowed": False,
            "external_delivery_allowed": False,
            "real_customer_data_allowed": False,
            "personalized_advice_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def render_retail_gate(retail: dict[str, Any]) -> str:
    blockers = as_list(retail.get("blockers"))
    categories = as_dict(retail.get("categories"))
    category_text = compact_values([key for key, value in sorted(categories.items()) if value], limit=8)
    return f"""
  <h2 class="subhead">Retail Truth Routing Gate</h2>
  <div class="retail-gate">
    <div class="metric"><span>Retail Routing</span><b>{esc(retail.get('status'))}</b></div>
    <div class="metric"><span>Output Decision</span><b>{esc(retail.get('decision'))}</b></div>
    <div class="metric"><span>Internal Safety</span><b>{esc('ready' if retail.get('internal_answer_safety_ready') else 'not_ready')}</b></div>
    <div class="metric"><span>Customer Output</span><b>{esc('allowed' if retail.get('customer_output_allowed') else 'blocked')}</b></div>
    <div class="metric"><span>Unsafe Prompts</span><b>{esc(retail.get('blocked_as_expected'))} / {esc(retail.get('seeded_bad_cases'))}</b></div>
    <div class="metric"><span>Unsafe Categories</span><b>{esc(retail.get('covered_category_count'))} / {esc(retail.get('category_count'))}</b></div>
  </div>
  <div class="gate gate-bad"><strong>Customer output remains blocked.</strong><span>{esc(compact_values(blockers, limit=8))}</span></div>
  <div class="meta">Unsafe coverage: {esc(category_text)}</div>
  <ul class="proof-list">{render_proof_routes({'proof_artifacts': retail.get('proof_artifacts')})}</ul>
    """


def render_panel(panel: dict[str, Any]) -> str:
    tone = panel.get("tone") or "info"
    routes = ", ".join(esc(route) for route in as_list(panel.get("route_sections"))) or "none"
    proofs = ", ".join(esc(ref) for ref in as_list(panel.get("proof_ref"))) or "none"
    return f"""
    <article class="panel tone-{esc(tone)}">
      <div class="panel-head">
        <h2>{esc(panel.get('label') or panel.get('id'))}</h2>
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


def render_html(view_model: dict[str, Any], v2_reader: dict[str, Any], retail: dict[str, Any]) -> str:
    panels = as_list(view_model.get("panels"))
    summary = as_dict(view_model.get("summary"))
    migrated = as_dict(v2_reader.get("summary"))
    actionability = as_dict(view_model.get("daily_actionability"))
    pm_route = as_dict(view_model.get("pm_cockpit_route"))
    buckets = as_dict(actionability.get("capital_buckets"))
    refresh_blockers = as_list(actionability.get("refresh_blockers"))
    blocker_html = (
        f"""<div class="gate gate-bad"><strong>Refresh required before relying on actionability.</strong><span>{esc(compact_values(refresh_blockers, limit=6))}</span></div>"""
        if actionability.get("actionability_allowed") is False
        else f"""<div class="gate gate-warn"><strong>Review-only actionability.</strong><span>{esc(actionability.get('actionability_reason'))}</span></div>"""
    )
    nav = "".join(f"<a href=\"#{esc(as_dict(panel).get('id'))}\">{esc(as_dict(panel).get('label') or as_dict(panel).get('id'))}</a>" for panel in panels)
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
<title>Veritas Finance Command Center</title>
<style>
:root {{ color-scheme: dark; --bg:#0b1120; --panel:#111827; --line:#334155; --text:#e5e7eb; --muted:#94a3b8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; --info:#38bdf8; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family:Segoe UI,Arial,sans-serif; }}
header {{ padding:20px 24px 12px; border-bottom:1px solid var(--line); position:sticky; top:0; background:rgba(11,17,32,.96); backdrop-filter: blur(8px); z-index:2; }}
h1 {{ margin:0; font-size:22px; }}
.meta {{ color:var(--muted); font-size:12px; margin-top:6px; }}
nav {{ display:flex; flex-wrap:wrap; gap:8px; padding-top:12px; }}
nav a {{ color:var(--text); text-decoration:none; border:1px solid var(--line); border-radius:6px; padding:6px 9px; font-size:12px; }}
main {{ padding:18px 24px 28px; }}
.hero {{ border-bottom:1px solid var(--line); padding:18px 24px; background:#0f172a; }}
.status-strip {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-top:14px; }}
.retail-gate {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
.metric {{ border:1px solid var(--line); background:rgba(17,24,39,.72); border-radius:8px; padding:10px 12px; }}
.metric span {{ color:var(--muted); display:block; font-size:11px; text-transform:uppercase; }}
.metric b {{ display:block; margin-top:4px; font-size:16px; overflow-wrap:anywhere; }}
.gate {{ margin-top:14px; border:1px solid var(--line); border-radius:8px; padding:11px 12px; display:grid; gap:4px; }}
.gate strong {{ font-size:14px; }}
.gate span {{ color:var(--muted); font-size:13px; overflow-wrap:anywhere; }}
.gate-bad {{ border-color:rgba(239,68,68,.55); background:rgba(127,29,29,.22); }}
.gate-warn {{ border-color:rgba(245,158,11,.55); background:rgba(120,53,15,.18); }}
.subhead {{ margin:18px 0 9px; font-size:13px; color:var(--muted); text-transform:uppercase; }}
.bucket-grid, .caveat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
.bucket, .caveat {{ border:1px solid var(--line); background:rgba(17,24,39,.72); border-radius:8px; padding:10px 12px; min-height:92px; }}
.bucket span, .caveat span {{ color:var(--muted); display:block; font-size:11px; text-transform:uppercase; }}
.bucket b, .caveat b {{ display:block; margin-top:4px; font-size:18px; }}
.bucket small, .caveat small {{ display:block; margin-top:6px; color:var(--muted); font-size:12px; overflow-wrap:anywhere; }}
.proof-list {{ margin:8px 0 0; padding:0; list-style:none; display:grid; gap:6px; }}
.proof-list li {{ display:grid; grid-template-columns:minmax(120px,.28fr) 1fr; gap:8px; border-bottom:1px solid rgba(51,65,85,.7); padding-bottom:6px; }}
.proof-list span {{ color:var(--muted); font-size:12px; }}
.proof-list code {{ color:var(--text); font-size:12px; overflow-wrap:anywhere; white-space:normal; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; }}
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
  <h1>Veritas Finance Command Center</h1>
  <div class="meta">Generated {esc(view_model.get('generated_at_utc'))} | finance panels {len(panels)} | migrated {esc(migrated.get('migrated_panel_count'))}/{esc(migrated.get('target_panel_count'))} | review-only compact route</div>
  <div class="meta">Legacy dashboard remains available for row-level drilldown. This shell is not canon, approval, or execution authority.</div>
  <div class="meta"><a href="veritas-command-center.html">Open Randall Full Detail Dashboard</a> | <a href="dashboard-presentation-view-model.json">Open compact view model JSON</a> | <a href="veritas-command-center-compact-reader.json">Open Veritas compact reader JSON</a> | <a href="{esc(pm_route.get('url'))}">{esc(pm_route.get('label'))}</a></div>
  <nav>{nav}</nav>
</header>
<section class="hero">
  <div class="meta">Daily finance actionability snapshot: {esc(actionability.get('snapshot'))}</div>
  <div class="status-strip">
    <div class="metric"><span>Actionability</span><b>{esc(actionability.get('actionability_status'))}</b></div>
    <div class="metric"><span>Permission</span><b>{esc(actionability.get('actionability_permission'))}</b></div>
    <div class="metric"><span>Window</span><b>{esc(actionability.get('operating_window'))}</b></div>
    <div class="metric"><span>Market Data As Of</span><b>{esc(actionability.get('market_data_as_of'))}</b></div>
    <div class="metric"><span>Next Refresh</span><b>{esc(actionability.get('next_refresh_due'))}</b></div>
    <div class="metric"><span>Deployable Now</span><b>{esc(as_dict(buckets.get('deployable_now')).get('count'))}</b></div>
    <div class="metric"><span>Capital Review</span><b>{esc(as_dict(buckets.get('owner_review')).get('count'))}</b></div>
    <div class="metric"><span>Pullback Only</span><b>{esc(as_dict(buckets.get('pullback_only')).get('count'))}</b></div>
    <div class="metric"><span>Below Stop</span><b>{esc(as_dict(buckets.get('below_stop')).get('count'))}</b></div>
    <div class="metric"><span>Blocked / Stale</span><b>{esc(as_dict(buckets.get('blocked_or_stale')).get('count'))}</b></div>
    <div class="metric"><span>Trust</span><b>{esc(actionability.get('source_freshness_status'))}</b></div>
    <div class="metric"><span>Fundamentals</span><b>{esc(actionability.get('fundamentals_status'))} / {esc(actionability.get('fundamentals_warning_count'))}</b></div>
    <div class="metric"><span>Macro/Energy</span><b>{esc(actionability.get('macro_status'))} / {esc(actionability.get('energy_status'))}</b></div>
  </div>
  {blocker_html}
  <h2 class="subhead">Capital Decision Funnel</h2>
  <div class="bucket-grid">{render_bucket_cards(actionability)}</div>
  <h2 class="subhead">Fundamentals And Macro Caveats</h2>
  <div class="caveat-grid">{render_caveat_cards(actionability)}</div>
  <h2 class="subhead">Proof Routes</h2>
  <ul class="proof-list">{render_proof_routes(actionability)}</ul>
  {render_retail_gate(retail)}
  <div class="meta">Reason: {esc(actionability.get('actionability_reason'))}</div>
  <div class="meta">Non-finance workflows, lanes, handoffs, sources, closeout, SMB/Retail/Academy/SQL, and notes route to {esc(pm_route.get('label'))}: <a href="{esc(pm_route.get('url'))}">{esc(pm_route.get('url'))}</a></div>
</section>
<main>
<section class="grid">
{''.join(cards)}
</section>
</main>
</body>
</html>
"""


def build_reader(view_model: dict[str, Any], v2_reader: dict[str, Any], validation: dict[str, Any], retail: dict[str, Any]) -> dict[str, Any]:
    panels = [as_dict(panel) for panel in as_list(view_model.get("panels"))]
    actionability = as_dict(view_model.get("daily_actionability"))
    top_actions: list[dict[str, Any]] = []
    blocked_items: list[dict[str, Any]] = []
    stale_inputs: list[dict[str, Any]] = []
    finance_review_queue: list[dict[str, Any]] = []
    proof_links: set[str] = set()
    owner_approval_required = False
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    for panel in panels:
        panel_id = str(panel.get("id") or "")
        if panel_id == "workflow_pm":
            continue
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
        if panel_id in {"deployment", "portfolio", "technical", "command_today", "market_macro", "fundamentals_earnings"}:
            finance_review_queue.append(row)
    for blocker in as_list(actionability.get("refresh_blockers")):
        stale_inputs.append(
            {
                "panel_id": "daily_actionability",
                "headline": "Refresh blocker",
                "severity": "critical",
                "state": "refresh_required_before_actionability",
                "freshness": actionability.get("source_freshness_status"),
                "reason": blocker,
                "owner_action_required": "Refresh required before relying on actionability.",
                "proof_ref": [actionability.get("snapshot")],
            }
        )
    proof_links.update(str(path) for path in as_dict(actionability.get("proof_artifacts")).values() if path)

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
            "finance_panel_count": len([panel for panel in panels if as_dict(panel).get("id") != "workflow_pm"]),
            "top_action_count": len(top_actions),
            "blocked_item_count": len(blocked_items),
            "stale_input_count": len(stale_inputs),
            "stale_required_source_count": len(as_list(actionability.get("stale_required_sources"))),
            "refresh_blocker_count": len(as_list(actionability.get("refresh_blockers"))),
            "finance_review_queue_count": len(finance_review_queue),
            "owner_approval_required": owner_approval_required,
            "actionability_status": actionability.get("actionability_status"),
            "actionability_permission": actionability.get("actionability_permission"),
            "all_finance_panels_migrated": migrated.get("all_finance_panels_migrated") is True,
            "workflow_pm_migrated_to_pm_cockpit": migrated.get("workflow_pm_migrated_to_pm_cockpit") is True,
            "legacy_payload_retained_by_design": True,
            "legacy_dashboard_replaced": False,
            "next_safe_action": "Use finance Command Center for daily capital/actionability review; use PM cockpit for workflows/non-finance state.",
        },
        "daily_actionability": view_model.get("daily_actionability"),
        "retail_truth_routing": retail,
        "pm_cockpit_route": view_model.get("pm_cockpit_route"),
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


def validate(view_model: dict[str, Any], v2_reader: dict[str, Any], html: str, retail: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not VIEW_MODEL.exists():
        findings.append({"severity": "critical", "issue": "missing_view_model"})
    if not V2_READER.exists():
        findings.append({"severity": "critical", "issue": "missing_v2_reader"})
    for path in (RETAIL_AUTOMATION, RETAIL_HARNESS, RETAIL_DECISION):
        if not path.exists():
            findings.append({"severity": "critical", "issue": "missing_retail_artifact", "path": relpath(path)})
    panels = as_list(view_model.get("panels"))
    if len(panels) != 7:
        findings.append({"severity": "critical", "issue": "finance_panel_count_wrong", "panel_count": len(panels)})
    if any(as_dict(panel).get("id") == "workflow_pm" for panel in panels):
        findings.append({"severity": "critical", "issue": "workflow_pm_present_in_finance_route"})
    if as_dict(v2_reader.get("summary")).get("all_finance_panels_migrated") is not True:
        findings.append({"severity": "critical", "issue": "v2_reader_not_all_finance_panels"})
    for token in ("Veritas Finance Command Center", "review-only compact route", "Legacy dashboard remains available", "Daily finance actionability snapshot", "Retail Truth Routing Gate", "Customer output remains blocked"):
        if token not in html:
            findings.append({"severity": "critical", "issue": "missing_shell_token", "token": token})
    for token in ("Open Randall Full Detail Dashboard", "Open Veritas compact reader JSON", "127.0.0.1:8765"):
        if token not in html:
            findings.append({"severity": "critical", "issue": "missing_route_link_token", "token": token})
    if "workflow_pm" in html:
        findings.append({"severity": "critical", "issue": "workflow_pm_rendered_in_finance_shell"})
    if retail.get("customer_output_allowed") is not False:
        findings.append({"severity": "critical", "issue": "retail_customer_output_not_blocked"})
    if retail.get("internal_answer_safety_ready") is not True:
        findings.append({"severity": "critical", "issue": "retail_internal_answer_safety_not_ready"})
    return findings


def write_outputs() -> tuple[str, dict[str, Any]]:
    view_model = as_dict(read_json(VIEW_MODEL)) if VIEW_MODEL.exists() else {}
    v2_reader = as_dict(read_json(V2_READER)) if V2_READER.exists() else {}
    retail = retail_summary(
        as_dict(read_json(RETAIL_AUTOMATION)) if RETAIL_AUTOMATION.exists() else {},
        as_dict(read_json(RETAIL_HARNESS)) if RETAIL_HARNESS.exists() else {},
        as_dict(read_json(RETAIL_DECISION)) if RETAIL_DECISION.exists() else {},
    )
    html = render_html(view_model, v2_reader, retail)
    findings = validate(view_model, v2_reader, html, retail)
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
    reader = build_reader(view_model, v2_reader, validation, retail)
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
