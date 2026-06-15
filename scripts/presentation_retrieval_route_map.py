"""Build retrieval-first route map for flattened presentation artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "presentation-retrieval-route-map.json"
WF75_OPERATOR_CONSOLE_JSON = "tmp/wf75-operator-console.json"
WF75_OPERATOR_CONSOLE_HTML = str(Path(WF75_OPERATOR_CONSOLE_JSON).with_suffix(".html")).replace("\\", "/")

ROUTES = [
    {
        "route": "wf79_command_center_active",
        "first_read": "tmp/veritas-command-center-compact-reader.json",
        "secondary": ["tmp/veritas-command-center-compact.html", "tmp/dashboard-presentation-view-model.json"],
        "proof": ["tmp/veritas-command-center.html", "tmp/dashboard-data.json", "tmp/dashboard-compact-shell-acceptance.json"],
        "status": "active_compact_reader_randall_full_detail_retained",
    },
    {
        "route": "wf79_dashboard_summary",
        "first_read": "tmp/dashboard-presentation-view-model.json",
        "secondary": ["tmp/dashboard-data-thin-preview.json", "tmp/dashboard-presentation-adapter.json"],
        "proof": ["tmp/dashboard-data.json", "tmp/dashboard-presentation-compatibility-proof.json", "tmp/dashboard-presentation-acceptance.json"],
        "status": "compact_view_model_supporting_route",
    },
    {
        "route": "wf79_randall_full_detail_dashboard",
        "first_read": "tmp/veritas-command-center.html",
        "secondary": ["tmp/dashboard-data.json", "tmp/veritas-command-center-compact.html"],
        "proof": ["tmp/dashboard-presentation-acceptance.json", "tmp/dashboard-shrink-readiness-score.json"],
        "status": "randall_full_detail_legacy_retained_by_design",
    },
    {
        "route": "portfolio_view_summary",
        "first_read": "tmp/full-portfolio-view.json",
        "secondary": ["tmp/full-portfolio-view-validation.json"],
        "proof": ["tmp/full-portfolio-view-validation.json"],
        "status": "json_required_html_optional_render",
    },
    {
        "route": "wf75_operator_console",
        "first_read": WF75_OPERATOR_CONSOLE_JSON,
        "secondary": ["tmp/wf75-operator-queue.json", "tmp/wf75-service-state-current.json"],
        "proof": [WF75_OPERATOR_CONSOLE_HTML, "tmp/veritas-pm-department-validation.json"],
        "status": "json_first_html_optional_proof",
    },
    {
        "route": "wf78_routing_packet_summary",
        "first_read": "tmp/wf78-auto-tier-routing.json",
        "secondary": ["tmp/wf78-packet-summary-consolidation.json", "tmp/wf78-routing-dashboard.json"],
        "proof": ["tmp/wf78-tier-a-final-promotion-packet.json", "tmp/wf78-tier-b-final-promotion-packet.next-batch.json"],
        "status": "derived_non_capital_routing_first",
    },
]


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def path_state(path_text: str) -> dict[str, Any]:
    path = ROOT / path_text
    return {
        "path": path_text,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def build_report() -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for route in ROUTES:
        row = dict(route)
        row["first_read_state"] = path_state(route["first_read"])
        row["secondary_state"] = [path_state(path) for path in route["secondary"]]
        row["proof_state"] = [path_state(path) for path in route["proof"]]
        enriched.append(row)
    return {
        "schema_version": "presentation_retrieval_route_map.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "authority": {
            "review_only": True,
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
            "route_count": len(enriched),
            "compact_first_routes": sum(1 for route in enriched if "compact" in route["status"] or "json_first" in route["status"] or "routing_first" in route["status"]),
            "active_command_center_route": "wf79_command_center_active",
            "veritas_first_read": "tmp/veritas-command-center-compact-reader.json",
            "randall_full_detail_view": "tmp/veritas-command-center.html",
            "legacy_payload_retained_by_design": True,
            "proof_hidden": False,
            "proof_opened_on": ["material answer", "stale source", "disputed route", "audit request", "decision-grade finance claim"],
        },
        "routes": enriched,
    }


def validate(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    authority = report.get("authority") if isinstance(report.get("authority"), dict) else {}
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_inferred"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    missing_first = [route["first_read"] for route in report.get("routes", []) if not route.get("first_read_state", {}).get("exists")]
    if missing_first:
        findings.append({"severity": "critical", "issue": "missing_first_read_artifacts", "paths": missing_first})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build presentation retrieval route map.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    findings = validate(report)
    report["validation"] = {
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "findings": findings,
    }
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"presentation_retrieval_route_map: {report['validation']['status']} ({report['validation']['critical']} critical)")
    return 1 if args.validate and report["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
