from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_patch_preview_validator as patch_validator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals" / "approval-artifact-validation.json"
SCHEMA_VERSION = 1
ARTIFACT_TYPE = "wf56_scoped_apply_approval"

FORBIDDEN_AUTH_TRUE = (
    "trade_or_account_action_allowed",
    "trade_execution_allowed",
    "brokerage_order_allowed",
    "money_movement_allowed",
    "execution_entitlement_allowed",
    "owner_approval_inferred",
)
ALLOWED_ADJUSTMENT_CATEGORIES = {
    "entry_band",
    "ticker_state",
    "sleeve",
    "sizing",
    "sector_posture",
    "earnings_state",
    "review_note",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def preview_diff_hash(preview: dict[str, Any]) -> str:
    diffs = []
    for item in preview.get("file_previews") or []:
        if isinstance(item, dict):
            diffs.append(str(item.get("path") or ""))
            diffs.append(str(item.get("diff") or ""))
    return sha256_text("\n".join(diffs))


def preview_target_files(preview: dict[str, Any]) -> list[str]:
    files = []
    for item in preview.get("file_previews") or []:
        if isinstance(item, dict) and item.get("path"):
            files.append(str(item["path"]).replace("\\", "/"))
    return sorted(set(files))


def not_expired(value: Any) -> bool:
    if not value:
        return False
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text) > datetime.now(timezone.utc)
    except Exception:
        return False


def validate_approval(approval_path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    try:
        approval = load_json(approval_path)
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "summary": {"critical": 1, "warning": 0}, "findings": [{"severity": "critical", "issue": str(exc)}]}

    def critical(issue: str, **extra: Any) -> None:
        findings.append({"severity": "critical", "issue": issue, **extra})

    if approval.get("schema_version") != SCHEMA_VERSION:
        critical(f"schema_version must be {SCHEMA_VERSION}")
    if approval.get("artifact_type") != ARTIFACT_TYPE:
        critical(f"artifact_type must be {ARTIFACT_TYPE}")
    if approval.get("approval_status") != "approved":
        critical("approval_status must be approved")
    if approval.get("owner_approval_granted") is not True:
        critical("owner_approval_granted must be true on the approval artifact")
    if approval.get("scoped_owner_file_write_allowed") is not True:
        critical("scoped_owner_file_write_allowed must be true")
    if approval.get("canonical_note_write_allowed") is not True:
        critical("canonical_note_write_allowed must be true")
    for field in FORBIDDEN_AUTH_TRUE:
        if approval.get(field) is True:
            critical(f"forbidden authority field must not be true: {field}")
    if approval.get("sizing_sleeve_cash_risk_rule_allowed") is True:
        critical("legacy bundled sizing/sleeve/cash/risk-rule field must remain false; use approved_adjustment_categories for exact gated sizing/sleeve scope")
    categories = approval.get("approved_adjustment_categories") or []
    if categories and not isinstance(categories, list):
        critical("approved_adjustment_categories must be a list when present")
        categories = []
    for category in categories:
        if str(category) not in ALLOWED_ADJUSTMENT_CATEGORIES:
            critical("approved_adjustment_categories contains unsupported category", category=str(category), allowed=sorted(ALLOWED_ADJUSTMENT_CATEGORIES))
    if not not_expired(approval.get("expires_at_utc")):
        critical("expires_at_utc is missing, invalid, or expired")

    proposal_id = str(approval.get("proposal_id") or "")
    proposal_artifact = approval.get("proposal_artifact")
    preview_artifact = approval.get("preview_artifact")
    if not proposal_id:
        critical("proposal_id is required")
    if not proposal_artifact:
        critical("proposal_artifact is required")
    if not preview_artifact:
        critical("preview_artifact is required")

    preview: dict[str, Any] = {}
    packet: dict[str, Any] = {}
    proposal_path = ROOT / str(proposal_artifact or "")
    preview_path = ROOT / str(preview_artifact or "")
    if proposal_artifact:
        try:
            packet = apply_helper.select_proposal(load_json(proposal_path), proposal_id)
        except Exception as exc:  # noqa: BLE001
            critical(f"cannot load proposal artifact: {exc}")
    if preview_artifact:
        try:
            preview = load_json(preview_path)
        except Exception as exc:  # noqa: BLE001
            critical(f"cannot load preview artifact: {exc}")

    if preview:
        if preview.get("status") != "ready_for_scoped_main_session_review":
            critical("preview status must be ready_for_scoped_main_session_review")
        if preview.get("proposal_id") != proposal_id:
            critical("preview proposal_id does not match approval artifact")
        summary = preview.get("summary") or {}
        if summary.get("writes_performed") is not False:
            critical("preview must prove writes_performed=false")
        expected_hash = approval.get("approved_diff_sha256")
        actual_hash = preview_diff_hash(preview)
        if expected_hash != actual_hash:
            critical("approved_diff_sha256 does not match preview diff hash", expected=expected_hash, actual=actual_hash)
        allowed = sorted(str(item).replace("\\", "/") for item in approval.get("approved_target_files") or [])
        targets = preview_target_files(preview)
        if allowed != targets:
            critical("approved_target_files must exactly match preview target files", approved=allowed, preview_targets=targets)

    if packet:
        if packet.get("proposal_id") != proposal_id:
            critical("proposal artifact proposal_id does not match approval artifact")
        for key in ("owner_approval_granted", "apply_allowed", "canonical_mutation_allowed", "portfolio_mutation_allowed", "trade_or_account_action_allowed"):
            if packet.get(key) is not False:
                critical(f"proposal packet authority flag must remain false: {key}")
        semantic_findings, changes = patch_validator.validate_patch_semantics(packet)
        findings.extend(semantic_findings)
        if not changes:
            critical("proposal artifact has no exact patch changes")
        approved_categories = {str(item) for item in categories}
        patch_categories = {
            str(change.get("adjustment_category") or (packet.get("exact_patch_preview") or {}).get("adjustment_category") or "")
            for change in changes
        }
        patch_categories.discard("")
        if changes and not approved_categories:
            critical("approved_adjustment_categories must name every approved patch category")
        missing_categories = sorted(patch_categories - approved_categories)
        if missing_categories:
            critical(
                "approved_adjustment_categories does not cover proposal patch categories",
                missing_categories=missing_categories,
                approved_categories=sorted(approved_categories),
            )

    critical_count = sum(1 for item in findings if item.get("severity") == "critical")
    warning_count = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical_count == 0 else "blocked",
        "input": rel(approval_path),
        "proposal_id": proposal_id or None,
        "authority": {
            "approval_artifact_can_scope_owner_file_write": critical_count == 0,
            "approved_adjustment_categories": [str(item) for item in categories],
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
            "legacy_sizing_sleeve_cash_risk_rule_field_allowed": False,
            "execution_entitlement_allowed": False,
        },
        "summary": {"critical": critical_count, "warning": warning_count},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a WF56 scoped apply approval artifact.")
    parser.add_argument("approval_artifact")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = validate_approval(ROOT / args.approval_artifact)
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(f"portfolio_mutation_approval_artifact_validator: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
