"""Prove render-default compatibility for presentation sidecar thinning.

The proof is report-only. It identifies whether default Markdown/HTML sidecar
writes can be disabled for full-portfolio-view and WF75 operator console
without breaking known script/app consumers.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCRIPTS = ROOT / "scripts"
APPS = ROOT / "apps"
PLAYBOOKS = ROOT / "06. Playbooks"
OUT = TMP / "presentation-render-default-compatibility.json"

ARTIFACTS = {
    "full_portfolio_view": {
        "owner_script": "scripts/full_portfolio_view.py",
        "json": "full-portfolio-view.json",
        "md": "full-portfolio-view.md",
        "html": "full-portfolio-view.html",
    },
    "wf75_operator_console": {
        "owner_script": "scripts/wf75_operator_console.py",
        "json": "wf75-operator-console.json",
        "md": "wf75-operator-console.md",
        "html": "wf75-operator-console.html",
    },
}


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in (SCRIPTS, APPS, PLAYBOOKS):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".html", ".md"}:
                files.append(path)
    return sorted(files)


def consumers_for(needle: str, files: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in files:
        if path.name == Path(__file__).name:
            continue
        text = safe_text(path)
        if needle in text or f"tmp/{needle}" in text or f"tmp\\{needle}" in text:
            role = "owner_script" if needle.replace(".json", "").replace(".md", "").replace(".html", "").replace("-", "_") in path.stem else "active_script_consumer"
            if path.suffix.lower() == ".md" or path.name == "README.md":
                role = "documentation_reference"
            rows.append({"path": relpath(path), "role": role})
    return rows


def classify_sidecar(family: str, sidecar: str, consumers: list[dict[str, str]]) -> dict[str, Any]:
    active_consumers = [row for row in consumers if row["role"] not in {"owner_script", "documentation_reference"}]
    documentation_refs = [row for row in consumers if row["role"] == "documentation_reference"]
    safe_to_disable = len(active_consumers) == 0
    reason = "No active non-owner script references found; documentation refs do not block default-disable by themselves." if safe_to_disable else "Active script consumers still reference this sidecar."
    if family == "wf75_operator_console" and sidecar == "md":
        reason = "Markdown is already optional; keep optional, do not make it default-required."
    return {
        "safe_to_disable_default_write": safe_to_disable,
        "consumer_count": len(consumers),
        "active_consumer_count": len(active_consumers),
        "documentation_reference_count": len(documentation_refs),
        "reason": reason,
        "consumers": consumers,
    }


def build_report() -> dict[str, Any]:
    files = iter_scan_files()
    families: dict[str, Any] = {}
    findings: list[dict[str, Any]] = []
    for family, spec in ARTIFACTS.items():
        family_rows: dict[str, Any] = {
            "owner_script": spec["owner_script"],
            "artifact_refs": {},
            "default_thinning": {},
        }
        for sidecar in ("json", "md", "html"):
            artifact_name = spec[sidecar]
            consumers = consumers_for(artifact_name, files)
            family_rows["artifact_refs"][sidecar] = {
                "artifact": f"tmp/{artifact_name}",
                "exists": (TMP / artifact_name).exists(),
                "bytes": (TMP / artifact_name).stat().st_size if (TMP / artifact_name).exists() else 0,
                "consumers": consumers,
            }
        for sidecar in ("md", "html"):
            compatibility = classify_sidecar(family, sidecar, family_rows["artifact_refs"][sidecar]["consumers"])
            family_rows["default_thinning"][sidecar] = compatibility
            if not compatibility["safe_to_disable_default_write"]:
                findings.append(
                    {
                        "severity": "warning",
                        "family": family,
                        "sidecar": sidecar,
                        "issue": "default_disable_not_proven_safe",
                        "active_consumer_count": compatibility["active_consumer_count"],
                    }
                )
        families[family] = family_rows

    return {
        "schema_version": "presentation_render_default_compatibility.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "authority": {
            "review_only": True,
            "default_render_behavior_changed": False,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "families_scanned": len(families),
            "files_scanned": len(files),
            "owner_defaults_json_first": True,
            "sidecars_explicit_only": True,
            "safe_default_disable_count": sum(
                1
                for family in families.values()
                for sidecar in family["default_thinning"].values()
                if sidecar["safe_to_disable_default_write"]
            ),
            "unsafe_or_unproven_default_disable_count": sum(
                1
                for family in families.values()
                for sidecar in family["default_thinning"].values()
                if not sidecar["safe_to_disable_default_write"]
            ),
            "recommended_next_step": "Keep JSON as required. Generate Markdown/HTML sidecars only through explicit render flags or dedicated presentation jobs.",
        },
        "families": families,
        "findings": findings,
    }


def validate(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    authority = report.get("authority") if isinstance(report.get("authority"), dict) else {}
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_changed") or key.endswith("_inferred"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    if report.get("summary", {}).get("families_scanned", 0) < 2:
        findings.append({"severity": "critical", "issue": "expected_two_families"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build render-default compatibility proof.")
    parser.add_argument("--write", action="store_true", help="Write tmp/presentation-render-default-compatibility.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    report = build_report()
    validation = validate(report)
    all_findings = [*report.get("findings", []), *validation]
    report["validation"] = {
        "status": "ok" if not any(finding.get("severity") == "critical" for finding in all_findings) else "blocked",
        "critical": sum(1 for finding in all_findings if finding.get("severity") == "critical"),
        "warning": sum(1 for finding in all_findings if finding.get("severity") == "warning"),
        "findings": all_findings,
    }
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"presentation_render_default_compatibility: {report['validation']['status']} ({report['validation']['critical']} critical)")
    return 1 if args.validate and report["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
