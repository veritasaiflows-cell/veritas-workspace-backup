from __future__ import annotations

import json
from typing import Any

from dashboard_core import TMP, SCRIPTS, load_sources, write_json
from dashboard_payload import build_payload, compute_delta
from dashboard_presentation_acceptance import OUT as PRESENTATION_ACCEPTANCE_PATH, build_report as build_presentation_acceptance
from dashboard_presentation_adapter import OUT as PRESENTATION_ADAPTER_PATH, build_report as build_presentation_adapter
from dashboard_presentation_compatibility_proof import OUT as PRESENTATION_COMPATIBILITY_PATH, build_report as build_presentation_compatibility
from dashboard_presentation_dto import OUT as PRESENTATION_DTO_PATH, build_dto, validate as validate_presentation_dto
from dashboard_presentation_dto_design import OUT as PRESENTATION_DTO_DESIGN_PATH, build_design
from dashboard_presentation_renderer import (
    OUT as PRESENTATION_RENDERER_PATH,
    VALIDATION as PRESENTATION_RENDERER_VALIDATION_PATH,
    render_html as render_presentation_html,
    validate as validate_presentation_html,
)
from dashboard_presentation_view_model import OUT as PRESENTATION_VIEW_MODEL_PATH, build_view_model, validate as validate_presentation_view_model
from dashboard_thin_payload_preview import write_outputs as write_thin_payload_preview
from dashboard_v2_reader_migration import write_outputs as write_v2_reader_migration
from dashboard_compatibility_payload import write_outputs as write_compatibility_payload
from dashboard_compact_shell import write_outputs as write_compact_shell
from dashboard_compact_shell_acceptance import OUT as COMPACT_SHELL_ACCEPTANCE_PATH, build_report as build_compact_shell_acceptance
from dashboard_shrink_readiness_score import OUT as SHRINK_SCORE_PATH, build_report as build_shrink_score

TEMPLATE_PATH = SCRIPTS / "dashboard-template.html"
OUT_PATH = TMP / "veritas-command-center.html"
DATA_PATH = TMP / "dashboard-data.json"
DELTA_PATH = TMP / "dashboard-delta.json"
LAST_PATH = TMP / "dashboard-last.json"
VALIDATION_PATH = TMP / "dashboard-validation.json"


def write_compact_presentation_route() -> None:
    design = build_design()
    write_json(PRESENTATION_DTO_DESIGN_PATH, design)

    dto = build_dto()
    dto_findings = validate_presentation_dto(dto)
    dto["validation"] = {
        "status": "ok" if not dto_findings else "blocked",
        "critical": sum(1 for finding in dto_findings if finding.get("severity") == "critical"),
        "findings": dto_findings,
    }
    write_json(PRESENTATION_DTO_PATH, dto)

    compatibility = build_presentation_compatibility()
    write_json(PRESENTATION_COMPATIBILITY_PATH, compatibility)

    adapter = build_presentation_adapter()
    write_json(PRESENTATION_ADAPTER_PATH, adapter)

    view_model = build_view_model()
    view_findings = validate_presentation_view_model(view_model)
    view_model["validation"] = {
        "status": "ok" if not any(finding.get("severity") == "critical" for finding in view_findings) else "blocked",
        "critical": sum(1 for finding in view_findings if finding.get("severity") == "critical"),
        "warning": sum(1 for finding in view_findings if finding.get("severity") == "warning"),
        "findings": view_findings,
    }
    write_json(PRESENTATION_VIEW_MODEL_PATH, view_model)

    compact_html = render_presentation_html(view_model)
    render_findings = validate_presentation_html(view_model, compact_html)
    render_validation = {
        "schema_version": "dashboard_presentation_renderer_validation.v1",
        "status": "ok" if not any(finding.get("severity") == "critical" for finding in render_findings) else "blocked",
        "critical": sum(1 for finding in render_findings if finding.get("severity") == "critical"),
        "warning": sum(1 for finding in render_findings if finding.get("severity") == "warning"),
        "output": "tmp/dashboard-presentation-view-model.html",
        "source_view_model": "tmp/dashboard-presentation-view-model.json",
        "findings": render_findings,
    }
    PRESENTATION_RENDERER_PATH.write_text(compact_html, encoding="utf-8")
    write_json(PRESENTATION_RENDERER_VALIDATION_PATH, render_validation)

    acceptance = build_presentation_acceptance()
    write_json(PRESENTATION_ACCEPTANCE_PATH, acceptance)
    write_thin_payload_preview()
    write_v2_reader_migration()
    write_compact_shell()
    write_compatibility_payload()
    write_json(COMPACT_SHELL_ACCEPTANCE_PATH, build_compact_shell_acceptance())
    acceptance = build_presentation_acceptance()
    write_json(PRESENTATION_ACCEPTANCE_PATH, acceptance)
    write_json(SHRINK_SCORE_PATH, build_shrink_score())


def inject_into_template(payload: dict[str, Any], delta: dict[str, Any]) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Dashboard template not found at {TEMPLATE_PATH}")
    styles_path = SCRIPTS / "dashboard-styles.css"
    js_dir = SCRIPTS / "dashboard-js"
    css = f"<style>\n{styles_path.read_text(encoding='utf-8')}\n</style>" if styles_path.exists() else ""
    js_files = sorted(js_dir.glob("*.js")) if js_dir.exists() else []
    js_content = "\n\n".join(f.read_text(encoding="utf-8") for f in js_files)
    js = f"<script>\n{js_content}\n</script>" if js_content else ""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("%%STYLES%%", css)
    template = template.replace("%%SCRIPTS%%", js)
    html = template.replace("%%DASHBOARD_DATA%%", json.dumps(payload, indent=2, default=str))
    html = html.replace("%%DASHBOARD_DELTA%%", json.dumps(delta, indent=2, default=str))
    compact_link = (
        '<div style="padding:8px 24px;border-bottom:1px solid rgba(148,163,184,.22);'
        'background:rgba(15,23,42,.96);font-size:12px">'
        '<a href="veritas-command-center-compact.html" style="color:#38bdf8;text-decoration:none">'
        "Open Veritas Compact Command View"
        "</a>"
        '<span style="color:#94a3b8"> | Full detail dashboard retained for Randall row-level drilldown; '
        "not canon, approval, or execution authority.</span>"
        "</div>"
    )
    html = html.replace("<div class=\"exec-banner\" id=\"execBanner\"></div>", compact_link + "\n<div class=\"exec-banner\" id=\"execBanner\"></div>", 1)
    return html


def generate() -> None:
    sources = load_sources()
    payload = build_payload(sources)

    previous = None
    if LAST_PATH.exists():
        try:
            previous = json.loads(LAST_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  WARN: Could not load prior snapshot: {exc}")

    delta = compute_delta(payload, previous)
    write_json(DATA_PATH, payload)
    write_json(DELTA_PATH, delta)
    write_json(VALIDATION_PATH, payload["validation"])

    html = inject_into_template(payload, delta)
    OUT_PATH.write_text(html, encoding="utf-8")
    write_json(LAST_PATH, payload)
    write_compact_presentation_route()

    print(f"  [ok] dashboard-data.json written ({len(payload.get('technical', []))} tech records)")
    print(f"  [ok] dashboard-delta.json written ({len(delta.get('changes', []))} changes: {delta.get('summary', '')})")
    print(f"  [ok] dashboard-validation.json written ({payload['validation']['summary']['critical']} critical, {payload['validation']['summary']['warning']} warning)")
    print(f"  [ok] Dashboard written to {OUT_PATH}")
    print(f"  [ok] Compact dashboard view-model written to {PRESENTATION_VIEW_MODEL_PATH}")
    print(f"  [ok] Generated at {payload['generated_at']}")
    print(f"  [ok] Data from: {payload['last_trade_date']}")
    print(f"  [ok] Exec freshness: {payload['exec_freshness']}")


if __name__ == "__main__":
    generate()
