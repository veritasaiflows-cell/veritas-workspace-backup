from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_patch_preview_validator as patch_validator
import portfolio_mutation_proposal_schema_validator as schema_validator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "exact-patch-material"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
PORTFOLIO_SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
SCHEMA_VERSION = 1
SUPPORTED_TARGETS = {
    "etn_execution_board_review_note",
    "entry_band",
    "sleeve",
    "sizing",
    "sector_posture",
}
CATEGORY_BY_TARGET = {
    "etn_execution_board_review_note": "review_note",
    "entry_band": "entry_band",
    "sleeve": "sleeve",
    "sizing": "sizing",
    "sector_posture": "sector_posture",
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


def safe_slug(value: str) -> str:
    return apply_helper.safe_slug(value)


def select_packet(bundle_path: Path, proposal_id: str) -> dict[str, Any]:
    bundle = load_json(bundle_path)
    return deepcopy(apply_helper.select_proposal(bundle, proposal_id))


def require_review_only(packet: dict[str, Any]) -> None:
    expected_false = (
        "owner_approval_granted",
        "apply_allowed",
        "canonical_mutation_allowed",
        "portfolio_mutation_allowed",
        "trade_or_account_action_allowed",
    )
    if packet.get("owner_decision_required") is not True:
        raise ValueError("packet must keep owner_decision_required=true")
    for key in expected_false:
        if packet.get(key) is not False:
            raise ValueError(f"packet must keep {key}=false")
    packet["main_session_final_action_required"] = True


def etn_execution_board_change(packet: dict[str, Any]) -> dict[str, Any]:
    ticker = str(packet.get("ticker_or_scope") or packet.get("ticker") or "").upper()
    if ticker != "ETN":
        raise ValueError("first scoped exact-patch generator only supports ETN")
    board_text = EXECUTION_BOARD.read_text(encoding="utf-8")
    anchor = "- Entry-distance context: **inside the preferred band, near the upper/no-chase zone**.\n- **POST-EARNINGS FOLLOW-UP.**"
    match_count = board_text.count(anchor)
    if match_count != 1:
        raise ValueError(f"ETN insertion anchor must match exactly once; matched {match_count}")
    proposal_id = str(packet.get("proposal_id"))
    insert = (
        "- Entry-distance context: **inside the preferred band, near the upper/no-chase zone**.\n"
        f"- WF56 capital packet: review-only packet `{proposal_id}` is linked for manual review; it does not authorize any sizing, sleeve, cash, or automated owner-surface change.\n"
        "- **POST-EARNINGS FOLLOW-UP.**"
    )
    return {
        "target_file": rel(EXECUTION_BOARD),
        "operation": "exact_text_replace",
        "old_text": anchor,
        "new_text": insert,
        "mutation_class": "bounded_status_visibility_sync",
        "adjustment_category": "review_note",
        "owner_surface": "execution_board",
        "rationale": "Link the validated WF56 ETN capital-review packet into the ETN canonical execution section without changing sizing, sleeve, cash, or authority state.",
    }


def category_change(packet: dict[str, Any], category: str) -> dict[str, Any]:
    ticker = str(packet.get("ticker_or_scope") or packet.get("ticker") or "").upper()
    proposal_id = str(packet.get("proposal_id"))
    if category == "entry_band":
        if ticker != "ETN":
            raise ValueError("bounded WF64 entry_band preview currently supports the ETN capital-review packet only")
        board_text = EXECUTION_BOARD.read_text(encoding="utf-8")
        anchor = "- Entry-distance context: **inside the preferred band, near the upper/no-chase zone**.\n- **POST-EARNINGS FOLLOW-UP.**"
        match_count = board_text.count(anchor)
        if match_count != 1:
            raise ValueError(f"ETN entry-band anchor must match exactly once; matched {match_count}")
        insert = (
            "- Entry-distance context: **inside the preferred band, near the upper/no-chase zone**.\n"
            f"- WF64 entry-band proposal preview: packet `{proposal_id}` is review-only; apply_allowed=false, owner_approval_granted=false, trade_or_account_action_allowed=false, and main-session final action is required.\n"
            "- **POST-EARNINGS FOLLOW-UP.**"
        )
        return {
            "target_file": rel(EXECUTION_BOARD),
            "operation": "exact_text_replace",
            "old_text": anchor,
            "new_text": insert,
            "mutation_class": "entry_band_review_visibility",
            "adjustment_category": "entry_band",
            "owner_surface": "execution_board",
            "rationale": "Preview an entry-band review note without changing levels, stop, sizing, sleeve, cash, or execution authority.",
        }

    snapshot_text = PORTFOLIO_SNAPSHOT.read_text(encoding="utf-8")
    if category == "sizing":
        anchor = "- MSFT is owner-promoted as a deployable-now / staged manual candidate, but below-200-day repair risk argues against full initial sizing."
        insert = anchor + f"\n- WF64 sizing proposal preview: `{proposal_id}` is review-only; it does not change draft weights, live allocations, cash, or external action authority."
    elif category == "sleeve":
        anchor = "- This is still a model draft, not an execution-ready account snapshot."
        insert = anchor + f"\n- WF64 sleeve proposal preview: `{proposal_id}` is review-only; it does not create, remove, or resize any sleeve without a separate approved apply artifact."
    elif category == "sector_posture":
        anchor = "**Concentration action rule:** direct Tech exposure is now already at the 25% single-sector cap, and the broader AI-power correlated sleeve still rises to 32% once ETN is included. MSFT is deployable-now, but deployment sequencing is unresolved: reduce another Tech weight first, keep any MSFT tranche within verified remaining headroom, or approve a written Tech-cap exception. Quality is not an exception to concentration discipline."
        insert = anchor + f"\n\n**WF64 sector-posture proposal preview:** `{proposal_id}` is review-only; it does not change sector caps, sleeve posture, or deployment sequencing without a separate approved apply artifact."
    else:  # pragma: no cover - protected by target choices
        raise ValueError(category)
    match_count = snapshot_text.count(anchor)
    if match_count != 1:
        raise ValueError(f"Portfolio Snapshot {category} anchor must match exactly once; matched {match_count}")
    return {
        "target_file": rel(PORTFOLIO_SNAPSHOT),
        "operation": "exact_text_replace",
        "old_text": anchor,
        "new_text": insert,
        "mutation_class": f"{category}_review_visibility",
        "adjustment_category": category,
        "owner_surface": "portfolio_snapshot",
        "rationale": f"Preview a {category} review note without changing canonical sizing, sleeve, sector, cash, risk-rule, or external action authority.",
    }


def build_augmented_packet(bundle_path: Path, proposal_id: str, target: str) -> dict[str, Any]:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    packet = select_packet(bundle_path, proposal_id)
    require_review_only(packet)
    if target == "etn_execution_board_review_note":
        change = etn_execution_board_change(packet)
    else:
        change = category_change(packet, CATEGORY_BY_TARGET[target])

    paths = [str(item).replace("\\", "/") for item in packet.get("proposed_files_to_edit") or []]
    if change["target_file"] not in paths:
        paths.append(change["target_file"])
    packet["proposed_files_to_edit"] = paths
    packet["exact_patch_preview"] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "generator": "portfolio_mutation_exact_patch_generator.py",
        "generation_target": target,
        "adjustment_category": CATEGORY_BY_TARGET[target],
        "apply_allowed": False,
        "owner_approval_granted": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "apply_ready": False,
        "approval_artifact_required": True,
        "writes_performed": False,
        "changes": [change],
        "stop_lines": [
            "Exact patch material is for dry-run preview only.",
            "This generated packet does not grant owner approval or apply authority.",
            "No sizing, sleeve, cash, risk-rule, execution-entitlement, or automated owner-surface change is authorized.",
        ],
    }
    packet["rollback_or_reversal_note"] = (
        str(packet.get("rollback_or_reversal_note") or "Delete or ignore generated packet.").rstrip()
        + " Exact patch material remains preview-only until a separate scoped approval artifact exists."
    )
    return packet


def validation_summary(packet: dict[str, Any], source_path: Path) -> dict[str, Any]:
    schema = schema_validator.validate_packet(packet)
    scope = scope_validator.validate_packet(source_path, packet)
    semantic, changes = patch_validator.validate_patch_semantics(packet)
    critical_scope = [item for item in scope if item.get("severity") == "critical"]
    critical_semantic = [item for item in semantic if item.get("severity") == "critical"]
    return {
        "schema_ok": bool(schema.get("ok")),
        "schema_errors": schema.get("errors") or [],
        "schema_blockers": schema.get("blockers") or [],
        "scope_findings": scope,
        "patch_semantic_findings": semantic,
        "changes_checked": len(changes),
        "critical_count": len(schema.get("errors") or []) + len(schema.get("blockers") or []) + len(critical_scope) + len(critical_semantic),
    }


def write_outputs(packet: dict[str, Any], target: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(f"{packet.get('proposal_id')}-{target}")
    json_path = OUT_DIR / f"{slug}.json"
    md_path = OUT_DIR / f"{slug}.md"
    json_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    change = (packet.get("exact_patch_preview") or {}).get("changes", [{}])[0]
    lines = [
        f"# Exact Patch Material - {packet.get('proposal_id')}",
        "",
        f"- Category: {CATEGORY_BY_TARGET[target]}",
        "- Authority: dry-run patch material only; apply_allowed=false, owner_approval_granted=false, trade_or_account_action_allowed=false, main_session_final_action_required=true",
        f"- Target file: `{change.get('target_file')}`",
        "",
        "## Proposed old/new material",
        "",
        "### old_text",
        "```markdown",
        str(change.get("old_text") or ""),
        "```",
        "",
        "### new_text",
        "```markdown",
        str(change.get("new_text") or ""),
        "```",
    ]
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate exact patch material for one scoped WF56 proposal packet.")
    parser.add_argument("--proposal-bundle", default="tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--target", default="etn_execution_board_review_note", choices=sorted(SUPPORTED_TARGETS))
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle_path = ROOT / args.proposal_bundle
    packet = build_augmented_packet(bundle_path, args.proposal_id, args.target)
    validation = validation_summary(packet, bundle_path)
    json_path = md_path = None
    if args.write:
        json_path, md_path = write_outputs(packet, args.target)
    print(json.dumps({
        "status": "ok" if validation["critical_count"] == 0 else "blocked",
        "proposal_id": packet.get("proposal_id"),
        "target": args.target,
        "changes": validation["changes_checked"],
        "critical": validation["critical_count"],
        "output_json": rel(json_path) if json_path else None,
        "output_md": rel(md_path) if md_path else None,
        "writes_performed": False,
    }, indent=2))
    return 1 if validation["critical_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
