"""Validate compact/JSON-first presentation retrieval routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

ROUTE_MAP = TMP / "presentation-retrieval-route-map.json"
OUT = TMP / "presentation-retrieval-enforcement.json"


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


def build_report() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    route_map = as_dict(read_json(ROUTE_MAP)) if ROUTE_MAP.exists() else {}
    if not ROUTE_MAP.exists():
        findings.append({"severity": "critical", "issue": "route_map_missing", "path": relpath(ROUTE_MAP)})
    routes = as_list(route_map.get("routes"))
    for route in routes:
        route = as_dict(route)
        first = ROOT / str(route.get("first_read", ""))
        if not first.exists():
            findings.append({"severity": "critical", "issue": "first_read_missing", "route": route.get("route"), "path": route.get("first_read")})
        if not as_list(route.get("proof")):
            findings.append({"severity": "critical", "issue": "proof_refs_missing", "route": route.get("route")})
        if route.get("route") == "wf79_dashboard_summary" and "dashboard-presentation-view-model.json" not in str(route.get("first_read")):
            findings.append({"severity": "critical", "issue": "wf79_not_compact_first", "first_read": route.get("first_read")})
    authority = as_dict(route_map.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "route_map_review_only_not_true"})
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_inferred"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    critical = sum(1 for finding in findings if finding.get("severity") == "critical")
    return {
        "schema_version": "presentation_retrieval_enforcement.v1",
        "status": "ok" if critical == 0 else "blocked",
        "critical": critical,
        "warning": sum(1 for finding in findings if finding.get("severity") == "warning"),
        "summary": {
            "route_count": len(routes),
            "route_map": relpath(ROUTE_MAP),
            "compact_first_enforced": critical == 0,
            "proof_refs_preserved": all(as_list(as_dict(route).get("proof")) for route in routes),
        },
        "authority": {
            "review_only": True,
            "proof_deletion_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compact/JSON-first retrieval route enforcement.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"presentation_retrieval_enforcement: {report['status']} ({report['critical']} critical)")
    return 1 if args.validate and report["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
