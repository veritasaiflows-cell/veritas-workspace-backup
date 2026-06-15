"""Prove the compatibility boundary for dashboard presentation DTO promotion.

This is the consumer-by-consumer proof gate for Presentation Artifact
Flattening Phase 1. It does not replace `tmp/dashboard-data.json`; it shows
whether the compact DTO can be promoted as a retrieval/presentation route and
whether it can safely replace the current Command Center payload.

Authority: review/proof only. No dashboard behavior replacement, proof
deletion, canon/portfolio mutation, SQL-canon promotion, customer/public
output, paper/live/account action, or owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCRIPTS = ROOT / "scripts"
APPS = ROOT / "apps"

DASHBOARD = TMP / "dashboard-data.json"
LAST = TMP / "dashboard-last.json"
DELTA = TMP / "dashboard-delta.json"
DTO = TMP / "dashboard-presentation-dto.json"
DESIGN = TMP / "dashboard-presentation-dto-design.json"
OUT = TMP / "dashboard-presentation-compatibility-proof.json"

JS_DIR = SCRIPTS / "dashboard-js"
TEMPLATE = SCRIPTS / "dashboard-template.html"

REQUIRED_AUTHORITY_FALSE = (
    "dashboard_payload_mutated",
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


def safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def direct_data_sections(text: str) -> set[str]:
    sections: set[str] = set()
    # DATA.foo, DATA?.foo, DATA["foo"], DATA['foo']
    for match in re.finditer(r"\bDATA(?:\?\.)?\.([A-Za-z_][A-Za-z0-9_]*)", text):
        sections.add(match.group(1))
    for match in re.finditer(r"\bDATA\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", text):
        sections.add(match.group(1))
    return sections


def direct_delta_sections(text: str) -> set[str]:
    sections: set[str] = set()
    for match in re.finditer(r"\bDELTA(?:\?\.)?\.([A-Za-z_][A-Za-z0-9_]*)", text):
        sections.add(match.group(1))
    for match in re.finditer(r"\bDELTA\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", text):
        sections.add(match.group(1))
    return sections


def static_command_center_consumers(payload: dict[str, Any], dto: dict[str, Any]) -> dict[str, Any]:
    dto_sections = {
        section
        for panel in dto.get("panels") or []
        for section in panel.get("source_sections") or []
    }
    files = [TEMPLATE] + sorted(JS_DIR.glob("*.js"))
    file_rows: list[dict[str, Any]] = []
    all_data_sections: Counter[str] = Counter()
    all_delta_sections: Counter[str] = Counter()
    for path in files:
        text = safe_text(path)
        data_sections = sorted(direct_data_sections(text))
        delta_sections = sorted(direct_delta_sections(text))
        all_data_sections.update(data_sections)
        all_delta_sections.update(delta_sections)
        if data_sections or delta_sections:
            file_rows.append(
                {
                    "path": relpath(path),
                    "data_sections": data_sections,
                    "delta_sections": delta_sections,
                    "data_sections_present_in_payload": sorted(section for section in data_sections if section in payload),
                    "data_sections_missing_from_payload": sorted(section for section in data_sections if section not in payload),
                    "data_sections_covered_by_dto": sorted(section for section in data_sections if section in dto_sections),
                    "data_sections_not_covered_by_dto": sorted(section for section in data_sections if section not in dto_sections),
                }
            )
    required_sections = sorted(all_data_sections)
    return {
        "consumer": "standalone_command_center_html",
        "status": "full_payload_required",
        "reason": "Current dashboard JS modules read the full DATA object directly; compact DTO panels cover summary sections but do not preserve row-level UI tables.",
        "files_scanned": len(files),
        "files_with_data_reads": len(file_rows),
        "required_top_level_data_sections": required_sections,
        "required_delta_sections": sorted(all_delta_sections),
        "data_sections_missing_from_payload": sorted(section for section in required_sections if section not in payload),
        "data_sections_covered_by_dto": sorted(section for section in required_sections if section in dto_sections),
        "data_sections_not_covered_by_dto": sorted(section for section in required_sections if section not in dto_sections),
        "files": file_rows,
    }


def find_literal_consumers() -> list[dict[str, Any]]:
    needles = (
        "dashboard-data.json",
        "dashboard-last.json",
        "dashboard-presentation-dto.json",
        "dashboard-presentation-dto-design.json",
    )
    consumers: dict[str, set[str]] = defaultdict(set)
    for root in (SCRIPTS, APPS):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".html"}:
                continue
            text = safe_text(path)
            for needle in needles:
                if needle in text:
                    consumers[relpath(path)].add(needle)
    return [{"path": path, "matched": sorted(matches)} for path, matches in sorted(consumers.items())]


def repeated_key_count(value: Any, keys: set[str], *, max_depth: int = 6) -> Counter[str]:
    counts: Counter[str] = Counter()

    def walk(node: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                if key in keys:
                    counts[key] += 1
                walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node[:250]:
                walk(child, depth + 1)

    walk(value, 0)
    return counts


def validate(payload: dict[str, Any], dto: dict[str, Any], command_center: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not payload:
        findings.append({"severity": "critical", "issue": "dashboard_payload_missing_or_empty"})
    if not dto:
        findings.append({"severity": "critical", "issue": "dashboard_dto_missing_or_empty"})
    authority = dto.get("authority") if isinstance(dto, dict) else {}
    authority = authority if isinstance(authority, dict) else {}
    for flag in REQUIRED_AUTHORITY_FALSE:
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "dto_authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "dto_review_only_not_true"})
    missing = command_center.get("data_sections_missing_from_payload") or []
    if missing:
        findings.append({"severity": "critical", "issue": "command_center_reads_missing_payload_sections", "sections": missing})
    if not command_center.get("required_top_level_data_sections"):
        findings.append({"severity": "warning", "issue": "no_static_command_center_data_reads_found"})
    return findings


def build_report() -> dict[str, Any]:
    payload = read_json(DASHBOARD) if DASHBOARD.exists() else {}
    dto = read_json(DTO) if DTO.exists() else {}
    design = read_json(DESIGN) if DESIGN.exists() else {}
    command_center = static_command_center_consumers(payload if isinstance(payload, dict) else {}, dto if isinstance(dto, dict) else {})
    literal_consumers = find_literal_consumers()
    repeated_keys = {"authority", "authority_boundary", "source", "sources", "status", "state", "summary", "validation", "warnings", "proof", "metadata"}
    payload_repeated = repeated_key_count(payload, repeated_keys)
    dto_repeated = repeated_key_count(dto, repeated_keys)
    payload_size = DASHBOARD.stat().st_size if DASHBOARD.exists() else 0
    dto_size = DTO.stat().st_size if DTO.exists() else 0
    findings = validate(payload if isinstance(payload, dict) else {}, dto if isinstance(dto, dict) else {}, command_center)
    hard_criticals = [finding for finding in findings if finding.get("severity") == "critical"]
    replacement_ready = (
        not hard_criticals
        and command_center.get("status") != "full_payload_required"
        and not command_center.get("data_sections_not_covered_by_dto")
    )
    return {
        "schema_version": "dashboard_presentation_compatibility_proof.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if not hard_criticals else "blocked",
        "decision": {
            "compact_dto_safe_for_retrieval_route": not hard_criticals,
            "compact_dto_safe_for_current_html_payload_replacement": replacement_ready,
            "next_decision_needed": not replacement_ready,
            "recommended_next_step": "Keep dashboard-presentation-dto.json as compact retrieval/presentation route; do not replace dashboard-data.json for the current HTML until an adapter or UI rewrite has acceptance proof.",
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
        "source_artifacts": {
            "dashboard_payload": relpath(DASHBOARD),
            "dashboard_last": relpath(LAST),
            "dashboard_delta": relpath(DELTA),
            "compact_dto": relpath(DTO),
            "dto_design": relpath(DESIGN),
        },
        "size": {
            "dashboard_payload_bytes": payload_size,
            "compact_dto_bytes": dto_size,
            "compact_dto_pct_of_payload": round((dto_size / payload_size) * 100, 2) if payload_size else None,
            "payload_repeated_key_counts": dict(sorted(payload_repeated.items())),
            "dto_repeated_key_counts": dict(sorted(dto_repeated.items())),
        },
        "command_center_consumer": command_center,
        "literal_consumers": literal_consumers,
        "dto_panel_count": len((dto or {}).get("panels") or []) if isinstance(dto, dict) else 0,
        "design_panel_count": len((design or {}).get("panels") or []) if isinstance(design, dict) else 0,
        "validation": {
            "status": "ok" if not hard_criticals else "blocked",
            "critical": len(hard_criticals),
            "warning": sum(1 for finding in findings if finding.get("severity") == "warning"),
            "findings": findings,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dashboard presentation compatibility proof.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-compatibility-proof.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    decision = report["decision"]
    print(
        "dashboard_presentation_compatibility_proof: "
        f"{report['validation']['status']} "
        f"(retrieval_safe={decision['compact_dto_safe_for_retrieval_route']}, "
        f"html_replacement_safe={decision['compact_dto_safe_for_current_html_payload_replacement']})"
    )
    return 1 if args.validate and report["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
