"""Build a compact dashboard presentation view model.

The view model is the UI-facing contract for the compact WF79 route. It is
fed by the dashboard DTO and adapter, not by embedding the full legacy
`dashboard-data.json` payload.

Authority: presentation/retrieval only. No proof deletion, dashboard behavior
replacement, canon/portfolio mutation, SQL-canon promotion, customer/public
output, paper/live/account action, or owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DTO = TMP / "dashboard-presentation-dto.json"
ADAPTER = TMP / "dashboard-presentation-adapter.json"
COMPAT = TMP / "dashboard-presentation-compatibility-proof.json"
OUT = TMP / "dashboard-presentation-view-model.json"

AUTHORITY_FALSE_FLAGS = (
    "dashboard_payload_replaced",
    "proof_deletion_allowed",
    "archive_or_cleanup_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "sql_canon_promotion_allowed",
    "customer_or_public_output_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "owner_approval_inferred",
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


def tone_for(severity: str, state: str) -> str:
    value = f"{severity} {state}".lower()
    if "critical" in value or "blocked" in value or "stale" in value:
        return "bad"
    if "warning" in value or "review" in value or "caution" in value:
        return "warn"
    if "ok" in value or "fresh" in value:
        return "ok"
    return "info"


def route_map(adapter: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_panel: dict[str, list[dict[str, Any]]] = {}
    for route in as_list(adapter.get("routes")):
        if not isinstance(route, dict):
            continue
        panel_id = route.get("compact_panel_id") or "_metadata"
        by_panel.setdefault(str(panel_id), []).append(route)
    return by_panel


def compact_panel(panel: dict[str, Any], routes: list[dict[str, Any]]) -> dict[str, Any]:
    severity = str(panel.get("severity") or "info")
    state = str(panel.get("state") or "unknown")
    proof_refs = [str(ref) for ref in as_list(panel.get("proof_ref")) if ref]
    route_sections = [str(route.get("section")) for route in routes if route.get("section")]
    return {
        "id": panel.get("id"),
        "headline": panel.get("headline"),
        "state": state,
        "freshness": panel.get("freshness"),
        "severity": severity,
        "tone": tone_for(severity, state),
        "primary_reason": panel.get("primary_reason"),
        "owner_action_required": panel.get("owner_action_required"),
        "authority_summary": panel.get("authority_summary"),
        "source_sections": as_list(panel.get("source_sections")),
        "route_sections": route_sections,
        "route_count": len(routes),
        "source_row_count": panel.get("source_row_count"),
        "proof_ref": proof_refs,
        "drilldown": {
            "source_ref": panel.get("source_ref"),
            "proof_ref": proof_refs,
            "legacy_passthrough_available": any(route.get("source_ref") for route in routes),
        },
    }


def build_view_model() -> dict[str, Any]:
    dto = as_dict(read_json(DTO)) if DTO.exists() else {}
    adapter = as_dict(read_json(ADAPTER)) if ADAPTER.exists() else {}
    compat = as_dict(read_json(COMPAT)) if COMPAT.exists() else {}
    routes_by_panel = route_map(adapter)
    panels = [
        compact_panel(panel, routes_by_panel.get(str(panel.get("id")), []))
        for panel in as_list(dto.get("panels"))
        if isinstance(panel, dict)
    ]
    metadata_routes = routes_by_panel.get("_metadata", [])
    route_counts = as_dict(as_dict(adapter.get("summary")).get("route_counts"))
    return {
        "schema_version": "dashboard_presentation_view_model.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "title": "Veritas Command Center Compact View",
        "source_payload_embedded": False,
        "source_artifacts": {
            "dto": relpath(DTO),
            "adapter": relpath(ADAPTER),
            "compatibility_proof": relpath(COMPAT),
        },
        "authority": {
            "review_only": True,
            "dashboard_payload_replaced": False,
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
        "summary": {
            "panel_count": len(panels),
            "critical": sum(1 for panel in panels if panel.get("severity") == "critical"),
            "warning": sum(1 for panel in panels if panel.get("severity") == "warning"),
            "info": sum(1 for panel in panels if panel.get("severity") == "info"),
            "adapter_mode": adapter.get("adapter_mode"),
            "route_counts": route_counts,
            "metadata_route_count": len(metadata_routes),
            "compact_dto_pct_of_payload": as_dict(compat.get("size")).get("compact_dto_pct_of_payload"),
            "current_html_replacement_safe": False,
            "compact_route_default_ready": True,
        },
        "metadata_strip": [
            {
                "section": route.get("section"),
                "route_kind": route.get("route_kind"),
                "source_ref": route.get("source_ref"),
                "reason": route.get("reason"),
            }
            for route in metadata_routes
        ],
        "panels": panels,
        "next_gate": {
            "required_before_legacy_payload_replacement": [
                "parallel renderer proof stays green",
                "view model acceptance stays green",
                "current dashboard acceptance stays green",
                "rollback route remains documented",
            ],
            "rollback": "Keep tmp/dashboard-data.json and tmp/veritas-command-center.html as the stable legacy route.",
        },
    }


def validate(model: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    authority = as_dict(model.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for flag in AUTHORITY_FALSE_FLAGS:
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    if model.get("source_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "source_payload_embedded"})
    panels = as_list(model.get("panels"))
    if len(panels) < 8:
        findings.append({"severity": "critical", "issue": "expected_eight_panels", "actual": len(panels)})
    for panel in panels:
        panel = as_dict(panel)
        for key in ("id", "headline", "state", "freshness", "severity", "primary_reason", "authority_summary"):
            if panel.get(key) in {None, ""}:
                findings.append({"severity": "critical", "issue": "panel_missing_field", "panel": panel.get("id"), "field": key})
        if panel.get("authority_summary") != "review_only_no_approval_no_execution":
            findings.append({"severity": "critical", "issue": "panel_authority_not_clamped", "panel": panel.get("id")})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact dashboard presentation view model.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-view-model.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    model = build_view_model()
    findings = validate(model) if args.validate else []
    model["validation"] = {
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "findings": findings,
    }
    if args.write:
        OUT.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(
        "dashboard_presentation_view_model: "
        f"{model['validation']['status']} ({model['summary']['panel_count']} panels)"
    )
    return 1 if args.validate and model["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
