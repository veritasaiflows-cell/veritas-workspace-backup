from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_approval_artifact_validator as approval_validator

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals" / "templates"
PROPOSAL_ID = "post-close:ETN:capital-deployment-review:2026-05-16"
WINDOW = "post-close"
CATEGORIES = {
    "entry_band": {
        "category_owner": "Execution Board / entry-band discipline",
        "proposal_artifact": "tmp/portfolio-mutation-proposals/exact-patch-material/post-close-ETN-capital-deployment-review-2026-05-16-entry_band.json",
        "preview_artifact": "tmp/portfolio-mutation-proposals/patch-previews/exact-apply-preview-post-close-ETN-capital-deployment-review-2026-05-16-entry_band.json",
    },
    "sleeve": {
        "category_owner": "Portfolio Snapshot / sleeve taxonomy",
        "proposal_artifact": "tmp/portfolio-mutation-proposals/exact-patch-material/post-close-ETN-capital-deployment-review-2026-05-16-sleeve.json",
        "preview_artifact": "tmp/portfolio-mutation-proposals/patch-previews/exact-apply-preview-post-close-ETN-capital-deployment-review-2026-05-16-sleeve.json",
    },
    "sizing": {
        "category_owner": "Portfolio Snapshot / sizing discipline",
        "proposal_artifact": "tmp/portfolio-mutation-proposals/exact-patch-material/post-close-ETN-capital-deployment-review-2026-05-16-sizing.json",
        "preview_artifact": "tmp/portfolio-mutation-proposals/patch-previews/exact-apply-preview-post-close-ETN-capital-deployment-review-2026-05-16-sizing.json",
    },
    "sector_posture": {
        "category_owner": "Portfolio Snapshot / sector posture and concentration rules",
        "proposal_artifact": "tmp/portfolio-mutation-proposals/exact-patch-material/post-close-ETN-capital-deployment-review-2026-05-16-sector_posture.json",
        "preview_artifact": "tmp/portfolio-mutation-proposals/patch-previews/exact-apply-preview-post-close-ETN-capital-deployment-review-2026-05-16-sector_posture.json",
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_json(rel_path: str) -> dict[str, Any]:
    data = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{rel_path} must contain a JSON object")
    return data


def build_template(category: str, generated_at: datetime) -> dict[str, Any]:
    config = CATEGORIES[category]
    proposal = load_json(config["proposal_artifact"])
    preview = load_json(config["preview_artifact"])
    if proposal.get("proposal_id") != PROPOSAL_ID:
        raise ValueError(f"{category}: proposal_id mismatch in proposal artifact")
    if preview.get("proposal_id") != PROPOSAL_ID:
        raise ValueError(f"{category}: proposal_id mismatch in preview artifact")
    if preview.get("status") != "ready_for_scoped_main_session_review":
        raise ValueError(f"{category}: preview is not ready for main-session review")
    patch = proposal.get("exact_patch_preview") or {}
    if patch.get("adjustment_category") != category:
        raise ValueError(f"{category}: proposal adjustment_category mismatch")
    target_files = approval_validator.preview_target_files(preview)
    diff_hash = approval_validator.preview_diff_hash(preview)
    expires_at = generated_at + timedelta(days=2)
    return {
        "schema_version": 1,
        "artifact_type": "wf56_scoped_apply_approval",
        "template_family": "WF64_guarded_apply_category_template",
        "approval_artifact_id": f"template-wf64-{category}-approval-2026-05-16",
        "approval_status": "draft_pending_randall_approval",
        "generated_at_utc": iso(generated_at),
        "approved_by": None,
        "approved_at_utc": None,
        "expires_at_utc": iso(expires_at),
        "expiry_required": True,
        "source_proposal_id": PROPOSAL_ID,
        "proposal_id": PROPOSAL_ID,
        "proposal_artifact": config["proposal_artifact"],
        "preview_artifact": config["preview_artifact"],
        "exact_patch_preview": {
            "source_proposal_id": PROPOSAL_ID,
            "proposal_artifact": config["proposal_artifact"],
            "preview_artifact": config["preview_artifact"],
            "approved_target_files": target_files,
            "approved_diff_sha256": diff_hash,
            "approved_adjustment_categories": [category],
            "preview_status_required": "ready_for_scoped_main_session_review",
            "writes_performed_required": False,
        },
        "approved_target_files": target_files,
        "approved_diff_sha256": diff_hash,
        "category_owner": config["category_owner"],
        "approved_adjustment_categories": [category],
        "owner_approval_granted": False,
        "scoped_owner_file_write_allowed": False,
        "canonical_note_write_allowed": False,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
        "brokerage_order_allowed": False,
        "money_movement_allowed": False,
        "sizing_sleeve_cash_risk_rule_allowed": False,
        "execution_entitlement_allowed": False,
        "owner_approval_inferred": False,
        "apply_allowed_without_valid_approval_artifact": False,
        "validator_proof_requirements": [
            "Validate this approval artifact with scripts/portfolio_mutation_approval_artifact_validator.py after explicit Randall approval flips approval_status, owner_approval_granted, scoped_owner_file_write_allowed, and canonical_note_write_allowed.",
            "The validator must report status=ok and approval_artifact_can_scope_owner_file_write=true before any apply helper can execute.",
            "approved_diff_sha256 must continue to match the named preview_artifact diff hash exactly.",
            "approved_target_files must exactly equal the preview target files.",
            "approved_adjustment_categories must exactly cover the patch adjustment category and must not rely on the legacy sizing_sleeve_cash_risk_rule_allowed field.",
        ],
        "guards": {
            "no_trade": True,
            "no_account_action": True,
            "no_brokerage_order": True,
            "no_money_movement": True,
            "no_inferred_owner_approval": True,
            "no_execution_entitlement_change": True,
            "no_unscoped_portfolio_mutation": True,
        },
        "scope_note": (
            "Template only. It does not approve or apply anything. Use only after explicit Randall approval "
            "for this exact proposal_id, category, target file set, preview artifact, diff hash, and expiry window. "
            "Trade/account actions and inferred approval remain blocked."
        ),
    }


def write_templates() -> list[Path]:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = utc_now()
    paths: list[Path] = []
    for category in sorted(CATEGORIES):
        payload = build_template(category, generated_at)
        path = TEMPLATE_DIR / f"wf64-{category}-approval-template.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main() -> int:
    paths = write_templates()
    print(json.dumps({"status": "ok", "templates_written": [rel(path) for path in paths], "writes_performed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
