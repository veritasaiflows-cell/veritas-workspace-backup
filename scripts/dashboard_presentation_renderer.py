"""Render the compact dashboard presentation view model to an HTML proof.

This is a parallel renderer proof. It does not replace
`tmp/veritas-command-center.html` and does not read/embed the full legacy
dashboard payload.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
MODEL = TMP / "dashboard-presentation-view-model.json"
OUT = TMP / "dashboard-presentation-view-model.html"
VALIDATION = TMP / "dashboard-presentation-renderer-validation.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def badge(value: Any, tone: str = "info") -> str:
    return f'<span class="badge {esc(tone)}">{esc(value)}</span>'


def render_panel(panel: dict[str, Any]) -> str:
    proof_refs = as_list(panel.get("proof_ref"))[:4]
    sections = as_list(panel.get("route_sections"))[:8]
    return f"""
    <article class="panel {esc(panel.get('tone') or 'info')}">
      <div class="panel-head">
        <h2>{esc(panel.get('label') or panel.get('headline'))}</h2>
        {badge(panel.get('severity'), panel.get('tone') or 'info')}
      </div>
      <p class="summary">{esc(panel.get('headline'))}</p>
      <dl>
        <dt>State</dt><dd>{esc(panel.get('state'))}</dd>
        <dt>Freshness</dt><dd>{esc(panel.get('freshness'))}</dd>
        <dt>Reason</dt><dd>{esc(panel.get('primary_reason'))}</dd>
        <dt>Action</dt><dd>{esc(panel.get('owner_action_required'))}</dd>
        <dt>Authority</dt><dd>{esc(panel.get('authority_summary'))}</dd>
      </dl>
      <div class="mini">
        <strong>Routes:</strong> {esc(', '.join(str(item) for item in sections) or 'none')}
      </div>
      <div class="mini">
        <strong>Proof:</strong> {esc(', '.join(str(item) for item in proof_refs) or 'none')}
      </div>
    </article>
    """


def render_html(model: dict[str, Any]) -> str:
    summary = as_dict(model.get("summary"))
    panels = [as_dict(panel) for panel in as_list(model.get("panels"))]
    metadata = as_list(model.get("metadata_strip"))
    actionability = as_dict(model.get("daily_actionability"))
    pm_route = as_dict(model.get("pm_cockpit_route"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(model.get('title'))}</title>
<style>
:root {{
  --bg:#0b1120; --panel:#111827; --card:#172033; --border:#2d3a52;
  --text:#eef3fb; --muted:#b6c2d4; --ok:#10b981; --warn:#f59e0b; --bad:#ef4444; --info:#38bdf8;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--text); }}
header {{ padding:18px 24px; border-bottom:1px solid var(--border); background:#0f172a; }}
h1 {{ margin:0; font-size:22px; }}
.sub {{ color:var(--muted); font-size:12px; margin-top:4px; }}
.wrap {{ padding:18px 24px 32px; }}
.strip {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-bottom:16px; }}
.metric {{ background:var(--panel); border:1px solid var(--border); padding:12px; border-radius:8px; }}
.metric b {{ display:block; font-size:20px; margin-top:4px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:14px; }}
.panel {{ background:var(--card); border:1px solid var(--border); border-left:4px solid var(--info); border-radius:8px; padding:14px; min-height:260px; }}
.panel.warn {{ border-left-color:var(--warn); }} .panel.bad {{ border-left-color:var(--bad); }} .panel.ok {{ border-left-color:var(--ok); }}
.panel-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:12px; }}
h2 {{ margin:0; font-size:14px; line-height:1.35; }}
dl {{ display:grid; grid-template-columns:92px 1fr; gap:7px 12px; margin:0; font-size:12px; line-height:1.45; }}
dt {{ color:var(--muted); text-transform:uppercase; font-size:10px; letter-spacing:.4px; }}
dd {{ margin:0; overflow-wrap:anywhere; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; font-size:10px; font-weight:700; text-transform:uppercase; }}
.badge.info {{ color:var(--info); background:rgba(56,189,248,.12); }} .badge.warn {{ color:var(--warn); background:rgba(245,158,11,.12); }}
.badge.bad {{ color:var(--bad); background:rgba(239,68,68,.12); }} .badge.ok {{ color:var(--ok); background:rgba(16,185,129,.12); }}
.summary {{ margin:0 0 12px; color:var(--muted); font-size:12px; line-height:1.45; }}
.mini {{ margin-top:10px; padding-top:8px; border-top:1px solid rgba(148,163,184,.14); color:var(--muted); font-size:11px; line-height:1.45; overflow-wrap:anywhere; }}
.meta {{ margin-top:16px; color:var(--muted); font-size:11px; line-height:1.5; }}
a {{ color:var(--info); }}
@media(max-width:720px) {{ header,.wrap {{ padding-left:14px; padding-right:14px; }} dl {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>{esc(model.get('title'))}</h1>
  <div class="sub">Compact presentation proof. Legacy Command Center remains the stable route.</div>
</header>
<main class="wrap">
  <section class="strip">
    <div class="metric">Panels<b>{esc(summary.get('panel_count'))}</b></div>
    <div class="metric">Actionability<b>{esc(actionability.get('actionability_status'))}</b></div>
    <div class="metric">Window<b>{esc(actionability.get('operating_window'))}</b></div>
    <div class="metric">Warnings<b>{esc(summary.get('warning'))}</b></div>
    <div class="metric">Critical<b>{esc(summary.get('critical'))}</b></div>
  </section>
  <section class="meta">
    Finance actionability snapshot: {esc(actionability.get('snapshot'))}. Workflows and non-finance operating state: <a href="{esc(pm_route.get('url'))}">{esc(pm_route.get('label'))}</a>.
  </section>
  <section class="grid">
    {''.join(render_panel(panel) for panel in panels)}
  </section>
  <section class="meta">
    <strong>Metadata routes:</strong> {esc(', '.join(str(as_dict(item).get('section')) for item in metadata))}
    <br><strong>Generated:</strong> {esc(model.get('generated_at_utc'))}
    <br><strong>Authority:</strong> review-only; no approval, mutation, account, paper/live execution, or customer/public authority.
  </section>
</main>
</body>
</html>
"""


def validate(model: dict[str, Any], html_text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if "dashboard-data.json" in html_text:
        findings.append({"severity": "warning", "issue": "html_mentions_legacy_payload_ref_for_drilldown"})
    forbidden = ("undefined", "paper orders ready", "trading is enabled", "owner approved")
    lowered = html_text.lower()
    for phrase in forbidden:
        if phrase in lowered:
            findings.append({"severity": "critical", "issue": "forbidden_phrase_in_renderer", "phrase": phrase})
    if re.search(r"(?<![a-z0-9])nan(?![a-z0-9])", lowered):
        findings.append({"severity": "critical", "issue": "forbidden_phrase_in_renderer", "phrase": "nan"})
    if "review-only" not in lowered:
        findings.append({"severity": "critical", "issue": "review_only_boundary_missing"})
    if len(as_list(model.get("panels"))) != 7:
        findings.append({"severity": "critical", "issue": "missing_panels"})
    if "workflow_pm" in html_text:
        findings.append({"severity": "critical", "issue": "workflow_pm_rendered_in_finance_route"})
    if "finance-daily-actionability-snapshot.json" not in html_text:
        findings.append({"severity": "critical", "issue": "actionability_snapshot_missing"})
    if "127.0.0.1:8765" not in html_text:
        findings.append({"severity": "critical", "issue": "pm_cockpit_route_missing"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Render compact dashboard view model HTML proof.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-view-model.html.")
    parser.add_argument("--validate", action="store_true", help="Write validation JSON and return nonzero on critical failures.")
    args = parser.parse_args()
    model = as_dict(json.loads(MODEL.read_text(encoding="utf-8")))
    html_text = render_html(model)
    findings = validate(model, html_text) if args.validate else []
    validation = {
        "schema_version": "dashboard_presentation_renderer_validation.v1",
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "output": relpath(OUT),
        "source_view_model": relpath(MODEL),
        "findings": findings,
    }
    if args.write:
        OUT.write_text(html_text, encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    if args.validate:
        VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(VALIDATION)}")
    print(f"dashboard_presentation_renderer: {validation['status']} ({validation['critical']} critical)")
    return 1 if args.validate and validation["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
