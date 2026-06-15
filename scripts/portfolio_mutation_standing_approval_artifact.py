from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_approval_artifact_validator as approval_validator
import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_patch_preview_validator as patch_validator

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals" / "standing-approved"
POLICY_VERSION = "2026-05-16-randall-workspace-portfolio-maintenance"
STANDING_APPROVED_CATEGORIES = {
    "entry_band",
    "ticker_state",
    "earnings_state",
    "sleeve",
    "sizing",
    "sector_posture",
    "review_note",
}
FORBIDDEN_TRUE = (
    "trade_or_account_action_allowed",
    "trade_execution_allowed",
    "brokerage_order_allowed",
    "money_movement_allowed",
    "execution_entitlement_allowed",
    "owner_approval_inferred",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def packet_categories(packet: dict[str, Any]) -> set[str]:
    semantic, changes = patch_validator.validate_patch_semantics(packet)
    critical = [item for item in semantic if item.get("severity") == "critical"]
    if critical:
        raise ValueError(f"patch semantic validation failed: {critical[:3]}")
    categories = set()
    patch = packet.get("exact_patch_preview") or packet.get("proposed_patch") or packet.get("patch") or {}
    if isinstance(patch, dict) and patch.get("adjustment_category"):
        categories.add(str(patch["adjustment_category"]))
    for change in changes:
        category = str(change.get("adjustment_category") or "")
        if category:
            categories.add(category)
    if not categories:
        raise ValueError("proposal packet contains no adjustment category")
    return categories


def build_artifact(proposal_artifact: str, preview_artifact: str, proposal_id: str | None, expires_hours: int, approved_by: str) -> dict[str, Any]:
    proposal_path = ROOT / proposal_artifact
    preview_path = ROOT / preview_artifact
    bundle = load_json(proposal_path)
    packet = apply_helper.select_proposal(bundle, proposal_id)
    proposal_id = str(packet.get("proposal_id") or proposal_id or "")
    if not proposal_id:
        raise ValueError("proposal_id is required or must exist in proposal artifact")
    preview = load_json(preview_path)
    if preview.get("status") != "ready_for_scoped_main_session_review":
        raise ValueError("preview must be ready_for_scoped_main_session_review")
    if preview.get("proposal_id") != proposal_id:
        raise ValueError("preview proposal_id mismatch")
    for key in ("owner_approval_granted", "apply_allowed", "canonical_mutation_allowed", "portfolio_mutation_allowed", "trade_or_account_action_allowed"):
        if packet.get(key) is not False:
            raise ValueError(f"proposal packet must keep {key}=false; approval artifact carries write authority")
    categories = packet_categories(packet)
    unsupported = sorted(categories - STANDING_APPROVED_CATEGORIES)
    if unsupported:
        raise ValueError(f"unsupported standing-approved categories: {unsupported}")
    now = utc_now()
    artifact = {
        "schema_version": 1,
        "artifact_type": "wf56_scoped_apply_approval",
        "approval_artifact_id": f"standing-{apply_helper.safe_slug(proposal_id)}-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "approval_status": "approved",
        "standing_approval_policy_version": POLICY_VERSION,
        "standing_approval_source": "Randall explicit 2026-05-16 approval for autonomous workspace portfolio/canon maintenance; trading remains owner-gated.",
        "approved_by": approved_by,
        "approved_at_utc": iso(now),
        "expires_at_utc": iso(now + timedelta(hours=expires_hours)),
        "expiry_required": True,
        "proposal_id": proposal_id,
        "proposal_artifact": proposal_artifact,
        "preview_artifact": preview_artifact,
        "approved_target_files": approval_validator.preview_target_files(preview),
        "approved_diff_sha256": approval_validator.preview_diff_hash(preview),
        "approved_adjustment_categories": sorted(categories),
        "owner_approval_granted": True,
        "scoped_owner_file_write_allowed": True,
        "canonical_note_write_allowed": True,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
        "brokerage_order_allowed": False,
        "money_movement_allowed": False,
        "sizing_sleeve_cash_risk_rule_allowed": False,
        "execution_entitlement_allowed": False,
        "owner_approval_inferred": False,
        "apply_allowed_without_valid_approval_artifact": False,
        "guards": {
            "no_trade": True,
            "no_account_action": True,
            "no_brokerage_order": True,
            "no_money_movement": True,
            "no_external_execution_entitlement": True,
            "exact_diff_only": True,
            "post_apply_validation_required": True,
        },
        "scope_note": "Standing-approved workspace portfolio/canon maintenance artifact. It authorizes only the exact validated diff/category/target files named here. It does not authorize trading, accounts, brokerage orders, money movement, credentials, or external execution.",
    }
    for key in FORBIDDEN_TRUE:
        if artifact.get(key) is True:
            raise ValueError(f"forbidden true authority: {key}")
    report = approval_validator.validate_approval_dict(artifact, ROOT / "__standing_approval_candidate__.json") if hasattr(approval_validator, "validate_approval_dict") else None
    return artifact


def write_artifact(payload: dict[str, Any]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{payload['approval_artifact_id']}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an exact scoped approval artifact under Randall's standing workspace portfolio-maintenance approval.")
    parser.add_argument("--proposal-artifact", required=True)
    parser.add_argument("--preview-artifact", required=True)
    parser.add_argument("--proposal-id")
    parser.add_argument("--expires-hours", type=int, default=24)
    parser.add_argument("--approved-by", default="Randall-standing-approval-2026-05-16")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        payload = build_artifact(args.proposal_artifact, args.preview_artifact, args.proposal_id, args.expires_hours, args.approved_by)
        path = write_artifact(payload) if args.write else None
        validation_path = path
        validation = approval_validator.validate_approval(validation_path) if validation_path else {"status": "not_written", "summary": {"critical": None, "warning": None}}
        print(json.dumps({
            "status": "ok" if validation.get("status") in {"ok", "not_written"} else "blocked",
            "approval_artifact": rel(path) if path else None,
            "proposal_id": payload["proposal_id"],
            "approved_adjustment_categories": payload["approved_adjustment_categories"],
            "trade_or_account_action_allowed": False,
            "validation_status": validation.get("status"),
            "validation_summary": validation.get("summary"),
        }, indent=2))
        return 0 if validation.get("status") in {"ok", "not_written"} else 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
