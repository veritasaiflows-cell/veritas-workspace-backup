from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as helper
import portfolio_mutation_proposal_schema_validator as schema_validator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "patch-previews"
OUT = OUT_DIR / "patch-preview-validation.json"
ALLOWED_OPERATIONS = {"replace", "exact_text_replace"}
FORBIDDEN_TEXT = (
    "trade execution allowed",
    "owner approval granted",
    "apply allowed",
    "brokerage",
    "account order",
)
FALSE_AUTHORITY_FLAGS = (
    "apply_allowed",
    "owner_approval_granted",
    "trade_or_account_action_allowed",
)
DECISION_CRITICAL_FRESHNESS = {"stale", "partial", "missing", "contradictory", "manual_dependency"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_bundle(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("proposal bundle must be a JSON object")
    return data


def validate_patch_semantics(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    for key in FALSE_AUTHORITY_FLAGS:
        if packet.get(key) is not False:
            findings.append({"severity": "critical", "issue": f"packet must keep {key}=false"})
    if packet.get("main_session_final_action_required") is not True:
        findings.append({"severity": "critical", "issue": "packet must keep main_session_final_action_required=true"})
    source = packet.get("source_freshness") or {}
    classification = source.get("overall_classification") or source.get("classification")
    if classification in DECISION_CRITICAL_FRESHNESS and not (source.get("explicit_blocker") or source.get("owner_review_required") or source.get("review_required")):
        findings.append({"severity": "critical", "issue": f"source freshness {classification} requires explicit blocker/review flag"})
    changes = helper.extract_changes(packet)
    if not changes:
        findings.append({
            "severity": "critical",
            "issue": "missing exact patch material",
            "detail": "Phase 3 dry-run helper requires exact_patch_preview/proposed_patch/patch changes with target path, old_text, and new_text.",
        })
        return findings, changes

    seen_ranges: dict[str, list[str]] = {}
    for idx, change in enumerate(changes, start=1):
        operation = str(change.get("operation") or change.get("change_type") or "exact_text_replace")
        category = change.get("adjustment_category") or (packet.get("exact_patch_preview") or {}).get("adjustment_category")
        if not category:
            findings.append({"severity": "critical", "change": idx, "issue": "patch change missing adjustment_category"})
        if operation not in ALLOWED_OPERATIONS:
            findings.append({"severity": "critical", "change": idx, "issue": f"unsupported operation: {operation}"})
        try:
            raw_path = helper.change_path(change)
            target = helper.normalize_path(raw_path)
        except Exception as exc:  # noqa: BLE001 - validator reports exact reason
            findings.append({"severity": "critical", "change": idx, "issue": str(exc)})
            continue
        old_text = change.get("old_text")
        new_text = change.get("new_text")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            findings.append({"severity": "critical", "change": idx, "path": rel(target), "issue": "old_text and new_text must be strings"})
            continue
        if old_text == new_text:
            findings.append({"severity": "critical", "change": idx, "path": rel(target), "issue": "old_text and new_text are identical"})
        lowered_new = new_text.lower()
        for forbidden in FORBIDDEN_TEXT:
            if forbidden in lowered_new:
                findings.append({"severity": "critical", "change": idx, "path": rel(target), "issue": f"forbidden authority/account text in new_text: {forbidden}"})
        if not target.exists() or not target.is_file():
            findings.append({"severity": "critical", "change": idx, "path": rel(target), "issue": "target file missing or not a file"})
            continue
        content = target.read_text(encoding="utf-8")
        match_count = content.count(old_text)
        if match_count != 1:
            findings.append({"severity": "critical", "change": idx, "path": rel(target), "issue": f"old_text must match exactly once; matched {match_count}"})
        key = rel(target)
        if old_text in seen_ranges.setdefault(key, []):
            findings.append({"severity": "critical", "change": idx, "path": key, "issue": "duplicate old_text replacement in same target file"})
        seen_ranges[key].append(old_text)
    return findings, changes


def build_report(bundle_path: Path, proposal_id: str | None = None) -> dict[str, Any]:
    bundle = load_bundle(bundle_path)
    packet = helper.select_proposal(bundle, proposal_id)
    schema_result = schema_validator.validate_packet(packet)
    scope_findings = scope_validator.validate_packet(bundle_path, packet)
    semantic_findings, changes = validate_patch_semantics(packet)
    findings: list[dict[str, Any]] = []
    for item in schema_result.get("errors") or []:
        findings.append({"severity": "critical", "source": "schema", "issue": item})
    for item in schema_result.get("blockers") or []:
        findings.append({"severity": "critical", "source": "schema", "issue": item})
    findings.extend(scope_findings)
    findings.extend(semantic_findings)
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "input_bundle": rel(bundle_path),
        "proposal_id": packet.get("proposal_id"),
        "authority": {
            "dry_run_patch_preview_allowed": True,
            "apply_ready": False,
            "approval_artifact_required": True,
            "write_owner_files_allowed": False,
            "portfolio_mutation_allowed_by_this_artifact": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {"changes_checked": len(changes), "critical": critical, "warning": warning},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exact patch material for WF56 Phase 3 dry-run previews.")
    parser.add_argument("--proposal-bundle", default="tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    parser.add_argument("--proposal-id")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report(ROOT / args.proposal_bundle, args.proposal_id)
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(f"portfolio_mutation_patch_preview_validator: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
