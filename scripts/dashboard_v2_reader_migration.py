"""Build the first compact-reader migration proof for WF79 Command Center V2.

This is Phase 1 proof: selected V2 panels render from the compact view-model
and thin-preview contract only. The live legacy Command Center remains intact.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

VIEW_MODEL = TMP / "dashboard-presentation-view-model.json"
THIN_PREVIEW = TMP / "dashboard-data-thin-preview.json"
LEGACY_DASHBOARD = TMP / "dashboard-data.json"
OUT = TMP / "dashboard-v2-reader-migration.json"
HTML = TMP / "dashboard-v2-reader-migration.html"

MIGRATION_PANELS = (
    "command_today",
    "trust_and_freshness",
    "deployment",
    "portfolio",
    "technical",
    "fundamentals_earnings",
    "market_macro",
    "workflow_pm",
)


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


def panel_by_id(view_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(panel.get("id")): panel for panel in as_list(view_model.get("panels")) if isinstance(panel, dict)}


def build_report() -> dict[str, Any]:
    view_model = as_dict(read_json(VIEW_MODEL)) if VIEW_MODEL.exists() else {}
    thin_preview = as_dict(read_json(THIN_PREVIEW)) if THIN_PREVIEW.exists() else {}
    panels = panel_by_id(view_model)
    migrated: list[dict[str, Any]] = []
    for panel_id in MIGRATION_PANELS:
        panel = as_dict(panels.get(panel_id))
        migrated.append(
            {
                "panel_id": panel_id,
                "headline": panel.get("headline"),
                "state": panel.get("state"),
                "freshness": panel.get("freshness"),
                "severity": panel.get("severity"),
                "source_sections": as_list(panel.get("source_sections")),
                "route_sections": as_list(panel.get("route_sections")),
                "proof_ref": as_list(panel.get("proof_ref")),
                "legacy_detail_available": as_dict(panel.get("drilldown")).get("legacy_passthrough_available") is True,
                "reader_contract": "compact_view_model_panel",
            }
        )
    return {
        "schema_version": "dashboard_v2_reader_migration.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "preview_ready",
        "source_payload_embedded": False,
        "legacy_dashboard_replaced": False,
        "authority": {
            "review_only": True,
            "legacy_dashboard_replaced": False,
            "legacy_payload_embedded": False,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "source_artifacts": {
            "view_model": relpath(VIEW_MODEL),
            "thin_preview": relpath(THIN_PREVIEW),
            "legacy_dashboard_ref": relpath(LEGACY_DASHBOARD),
        },
        "summary": {
            "migrated_panel_count": len(migrated),
            "target_panel_count": len(MIGRATION_PANELS),
            "thin_preview_status": thin_preview.get("status"),
            "all_compact_panels_migrated": len(migrated) == len(MIGRATION_PANELS),
            "ready_for_parallel_v2_reader": True,
            "legacy_dashboard_replacement_ready": False,
        },
        "migrated_panels": migrated,
        "next_batch_candidates": [],
    }


def validate(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in (VIEW_MODEL, THIN_PREVIEW, LEGACY_DASHBOARD):
        if not path.exists():
            findings.append({"severity": "critical", "issue": "missing_required_artifact", "path": relpath(path)})
    authority = as_dict(report.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_embedded") or key.endswith("_replaced") or key.endswith("_inferred"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    panels = as_list(report.get("migrated_panels"))
    if len(panels) != len(MIGRATION_PANELS):
        findings.append({"severity": "critical", "issue": "missing_migrated_panel", "actual": len(panels), "expected": len(MIGRATION_PANELS)})
    if as_dict(report.get("summary")).get("all_compact_panels_migrated") is not True:
        findings.append({"severity": "critical", "issue": "all_compact_panels_not_migrated"})
    for panel in panels:
        panel = as_dict(panel)
        if not panel.get("headline") or not panel.get("route_sections"):
            findings.append({"severity": "critical", "issue": "panel_missing_compact_contract", "panel": panel.get("panel_id")})
    if report.get("source_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "source_payload_embedded"})
    return findings


def render_html(report: dict[str, Any]) -> str:
    cards = []
    for panel in as_list(report.get("migrated_panels")):
        panel = as_dict(panel)
        cards.append(
            "<section class=\"card\">"
            f"<h2>{panel.get('panel_id')}</h2>"
            f"<p>{panel.get('headline') or ''}</p>"
            f"<dl><dt>State</dt><dd>{panel.get('state')}</dd>"
            f"<dt>Freshness</dt><dd>{panel.get('freshness')}</dd>"
            f"<dt>Severity</dt><dd>{panel.get('severity')}</dd>"
            f"<dt>Routes</dt><dd>{', '.join(str(x) for x in as_list(panel.get('route_sections')))}</dd></dl>"
            "</section>"
        )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>WF79 V2 Reader Migration</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e5e7eb;margin:24px}"
        ".card{border:1px solid #334155;border-radius:8px;padding:16px;margin:12px 0;background:#111827}"
        "h1,h2{margin:.2rem 0}.meta{color:#94a3b8}dt{color:#94a3b8;margin-top:8px}dd{margin-left:0}</style></head>"
        "<body><h1>WF79 V2 Compact Reader Migration</h1>"
        "<p class=\"meta\">Parallel proof only. Live legacy Command Center remains stable.</p>"
        + "".join(cards)
        + "</body></html>"
    )


def write_outputs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report = build_report()
    findings = validate(report)
    report["validation"] = {
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "findings": findings,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    HTML.write_text(render_html(report), encoding="utf-8")
    return report, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build WF79 V2 compact reader migration proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    findings = validate(report)
    if args.write:
        report, findings = write_outputs()
        print(f"wrote {relpath(OUT)}")
        print(f"wrote {relpath(HTML)}")
    critical = sum(1 for finding in findings if finding.get("severity") == "critical")
    print(f"dashboard_v2_reader_migration: {'ok' if critical == 0 else 'blocked'} ({critical} critical)")
    return 1 if args.validate and critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
