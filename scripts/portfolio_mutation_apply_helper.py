from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_proposal_schema_validator as schema_validator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "portfolio-mutation-proposals"
PREVIEW_DIR = OUT_DIR / "patch-previews"
APPLY_RESULT_DIR = OUT_DIR / "apply-results"
BACKUP_DIR = OUT_DIR / "apply-backups"
SCHEMA_VERSION = 1
SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")

AUTHORITY = {
    "phase": "WF56 Phase 3 dry-run scoped patch helper",
    "dry_run_patch_preview_allowed": True,
    "apply_allowed": False,
    "owner_approval_granted": False,
    "main_session_final_action_required": True,
    "write_owner_files_allowed": False,
    "apply_allowed_by_this_helper": False,
    "portfolio_mutation_allowed_by_this_helper": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "trade_execution_allowed": False,
}

APPLY_AUTHORITY = {
    "phase": "WF64 approval-gated atomic apply foundation",
    "apply_allowed_without_valid_approval_artifact": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "trade_execution_allowed": False,
    "brokerage_order_allowed": False,
    "money_movement_allowed": False,
    "rollback_required_on_failure": True,
    "post_apply_validation_required": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def safe_slug(value: str) -> str:
    slug = SAFE_ID.sub("-", value.strip())[:140].strip("-._")
    return slug or "proposal"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def preview_diff_hash(preview: dict[str, Any]) -> str:
    diffs: list[str] = []
    for item in preview.get("file_previews") or []:
        if isinstance(item, dict):
            diffs.append(str(item.get("path") or ""))
            diffs.append(str(item.get("diff") or ""))
    return sha256_text("\n".join(diffs))


def preview_target_files(preview: dict[str, Any]) -> list[str]:
    return sorted({str(item.get("path")).replace("\\", "/") for item in preview.get("file_previews") or [] if isinstance(item, dict) and item.get("path")})


def atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_name(f".{path.name}.{safe_slug(utc_now())}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def proposal_packets(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    proposals = bundle.get("proposals")
    if isinstance(proposals, list):
        return [item for item in proposals if isinstance(item, dict)]
    return [bundle]


def select_proposal(bundle: dict[str, Any], proposal_id: str | None) -> dict[str, Any]:
    packets = proposal_packets(bundle)
    if not packets:
        raise ValueError("proposal bundle contains no proposal packets")
    if proposal_id:
        for packet in packets:
            if packet.get("proposal_id") == proposal_id:
                return packet
        raise ValueError(f"proposal_id not found: {proposal_id}")
    if len(packets) != 1:
        ids = ", ".join(str(item.get("proposal_id")) for item in packets[:8])
        raise ValueError(f"proposal bundle has {len(packets)} packets; pass --proposal-id. Available: {ids}")
    return packets[0]


def normalize_path(raw: str) -> Path:
    path_text = str(raw).replace("\\", "/").strip()
    if not path_text:
        raise ValueError("empty patch path")
    if path_text.startswith("/") or (len(path_text) > 2 and path_text[1] == ":"):
        raise ValueError(f"absolute patch path is not allowed: {path_text}")
    candidate = (ROOT / path_text).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"patch path escapes workspace: {path_text}") from exc
    return candidate


def extract_changes(packet: dict[str, Any]) -> list[dict[str, Any]]:
    patch = packet.get("exact_patch_preview") or packet.get("proposed_patch") or packet.get("patch") or {}
    if not isinstance(patch, dict):
        return []
    changes = patch.get("changes")
    if isinstance(changes, list):
        return [item for item in changes if isinstance(item, dict)]
    if any(key in patch for key in ("path", "file", "target_file", "old_text", "new_text")):
        return [patch]
    return []


def change_path(change: dict[str, Any]) -> str:
    for key in ("path", "file", "target_file", "target"):
        if change.get(key):
            return str(change[key])
    raise ValueError("patch change missing path/file/target_file")


def apply_text_change(original: str, old_text: str, new_text: str, path: str) -> str:
    if old_text == new_text:
        raise ValueError(f"no-op text replacement for {path}")
    matches = original.count(old_text)
    if matches != 1:
        raise ValueError(f"old_text must match exactly once in {path}; matched {matches}")
    return original.replace(old_text, new_text, 1)


def build_file_preview(change: dict[str, Any]) -> dict[str, Any]:
    raw_path = change_path(change)
    target = normalize_path(raw_path)
    if not target.exists():
        raise ValueError(f"target file does not exist: {raw_path}")
    if not target.is_file():
        raise ValueError(f"target path is not a file: {raw_path}")
    old_text = change.get("old_text")
    new_text = change.get("new_text")
    if not isinstance(old_text, str) or not isinstance(new_text, str):
        raise ValueError(f"patch change for {raw_path} requires string old_text and new_text")
    original = target.read_text(encoding="utf-8")
    updated = apply_text_change(original, old_text, new_text, raw_path)
    before = original.splitlines()
    after = updated.splitlines()
    diff = "\n".join(difflib.unified_diff(before, after, fromfile=f"a/{rel(target)}", tofile=f"b/{rel(target)}", lineterm="")) + "\n"
    return {
        "path": rel(target),
        "change_type": "exact_text_replace",
        "old_text_sha256_hint": None,
        "old_text_match_count": 1,
        "writes_performed": False,
        "diff": diff,
        "rationale": str(change.get("rationale") or "Scoped owner-review patch preview."),
    }


def validate_scope_for_packet(packet: dict[str, Any], source: Path) -> list[dict[str, Any]]:
    return scope_validator.validate_packet(source, packet)


def build_preview(bundle_path: Path, proposal_id: str | None, window: str) -> dict[str, Any]:
    bundle = load_json(bundle_path)
    packet = select_proposal(bundle, proposal_id)
    selected_id = str(packet.get("proposal_id") or proposal_id or "proposal")
    schema_result = schema_validator.validate_packet(packet)
    scope_findings = validate_scope_for_packet(packet, bundle_path)
    critical_scope = [item for item in scope_findings if item.get("severity") == "critical"]
    changes = extract_changes(packet)
    file_previews: list[dict[str, Any]] = []
    build_errors: list[str] = []

    if schema_result.get("ok") and not critical_scope:
        for change in changes:
            try:
                file_previews.append(build_file_preview(change))
            except Exception as exc:  # noqa: BLE001 - report fail-closed preview errors
                build_errors.append(str(exc))

    status = "ready_for_scoped_main_session_review"
    if not schema_result.get("ok") or critical_scope or build_errors:
        status = "blocked"
    elif not changes:
        status = "blocked_missing_exact_patch_material"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "window": window,
        "input_bundle": rel(bundle_path),
        "proposal_id": selected_id,
        "apply_allowed": False,
        "owner_approval_granted": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "authority": dict(AUTHORITY),
        "validation": {
            "schema_validator_ok": bool(schema_result.get("ok")),
            "schema_errors": schema_result.get("errors") or [],
            "schema_blockers": schema_result.get("blockers") or [],
            "patch_scope_findings": scope_findings,
            "patch_scope_critical": len(critical_scope),
            "build_errors": build_errors,
        },
        "summary": {
            "requested_changes": len(changes),
            "previewed_file_changes": len(file_previews),
            "writes_performed": False,
            "apply_ready": False,
            "approval_artifact_required": True,
            "ready_for_main_session_portfolio_mutation_review": status == "ready_for_scoped_main_session_review",
        },
        "file_previews": file_previews,
        "stop_lines": [
            "This artifact is an exact patch preview only; it does not mutate owner notes or portfolio config.",
            "Main-session portfolio mutation still requires explicit scoped Randall approval for the proposal id and exact diff.",
            "A clean preview does not grant owner approval, sizing, sleeve, cash, risk-rule, execution-entitlement, trade, or account authority.",
            "Phase 4 apply mode must be a separate approval-gated path and must run the post-apply validation chain.",
        ],
    }


def _load_valid_approval(approval_path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    import portfolio_mutation_approval_artifact_validator as approval_validator

    validation = approval_validator.validate_approval(approval_path)
    if validation.get("status") != "ok":
        return None, validation
    return load_json(approval_path), validation


def _approval_paths(approval: dict[str, Any]) -> tuple[Path, Path, str]:
    proposal_id = str(approval.get("proposal_id") or "")
    proposal_path = normalize_path(str(approval.get("proposal_artifact") or ""))
    preview_path = normalize_path(str(approval.get("preview_artifact") or ""))
    return proposal_path, preview_path, proposal_id


def _approved_categories(approval: dict[str, Any]) -> set[str]:
    return {str(item) for item in approval.get("approved_adjustment_categories") or []}


def _change_category(packet: dict[str, Any], change: dict[str, Any]) -> str:
    patch = packet.get("exact_patch_preview") or packet.get("proposed_patch") or packet.get("patch") or {}
    return str(change.get("adjustment_category") or (patch if isinstance(patch, dict) else {}).get("adjustment_category") or "")


def _build_file_operations(packet: dict[str, Any], approval: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    categories = _approved_categories(approval)
    by_path: dict[Path, dict[str, Any]] = {}
    for change in extract_changes(packet):
        try:
            raw_path = change_path(change)
            target = normalize_path(raw_path)
            category = _change_category(packet, change)
            if categories and category not in categories:
                errors.append(f"change category is not approved for {raw_path}: {category}")
                continue
            old_text = change.get("old_text")
            new_text = change.get("new_text")
            if not isinstance(old_text, str) or not isinstance(new_text, str):
                errors.append(f"change requires string old_text/new_text: {raw_path}")
                continue
            if target not in by_path:
                original = target.read_text(encoding="utf-8")
                by_path[target] = {"path": target, "original": original, "updated": original, "changes": []}
            entry = by_path[target]
            updated = apply_text_change(str(entry["updated"]), old_text, new_text, raw_path)
            entry["updated"] = updated
            entry["changes"].append({
                "change_type": "exact_text_replace",
                "adjustment_category": category,
                "old_text_sha256": sha256_text(old_text),
                "new_text_sha256": sha256_text(new_text),
            })
        except Exception as exc:  # noqa: BLE001 - fail closed into apply report
            errors.append(str(exc))
    operations: list[dict[str, Any]] = []
    for target, entry in by_path.items():
        if entry["original"] == entry["updated"]:
            errors.append(f"no effective update for {rel(target)}")
            continue
        operations.append({
            "path": target,
            "relative_path": rel(target),
            "original": entry["original"],
            "updated": entry["updated"],
            "original_sha256": sha256_text(entry["original"]),
            "updated_sha256": sha256_text(entry["updated"]),
            "changes": entry["changes"],
        })
    return operations, errors


def build_apply_plan(approval_path: Path, window: str) -> dict[str, Any]:
    approval, validation = _load_valid_approval(approval_path)
    proposal_id = None
    operations: list[dict[str, Any]] = []
    build_errors: list[str] = []
    backup_root = None
    if approval:
        proposal_path, _preview_path, proposal_id = _approval_paths(approval)
        packet = select_proposal(load_json(proposal_path), proposal_id)
        rebuilt_preview = build_preview(proposal_path, proposal_id, window)
        if approval.get("approved_diff_sha256") != preview_diff_hash(rebuilt_preview):
            build_errors.append("approved diff hash no longer matches regenerated preview from proposal artifact")
        if sorted(str(item).replace("\\", "/") for item in approval.get("approved_target_files") or []) != preview_target_files(rebuilt_preview):
            build_errors.append("approved target files no longer match regenerated preview from proposal artifact")
        operations, operation_errors = _build_file_operations(packet, approval)
        build_errors.extend(operation_errors)
        backup_root = BACKUP_DIR / f"{safe_slug(utc_now())}-{safe_slug(proposal_id)}"
    status = "ready_for_approval_gated_apply" if approval and operations and not build_errors else "blocked"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "window": window,
        "approval_artifact": rel(approval_path),
        "proposal_id": proposal_id,
        "authority": {
            **APPLY_AUTHORITY,
            "valid_approval_artifact": bool(approval),
            "apply_allowed": status == "ready_for_approval_gated_apply",
            "scoped_owner_file_write_allowed": status == "ready_for_approval_gated_apply",
        },
        "validation": validation,
        "summary": {
            "files_to_write": len(operations),
            "writes_performed": False,
            "rollback_plan_created": bool(backup_root and operations),
            "post_apply_validation_required": True,
        },
        "build_errors": build_errors,
        "rollback_plan": {
            "backup_root": rel(backup_root) if backup_root else None,
            "restore_method": "copy each backup file back to its original relative path using atomic replace; apply helper also restores from backups automatically on failure",
            "files": [
                {
                    "path": op["relative_path"],
                    "backup_path": rel((backup_root / op["relative_path"]).with_suffix(Path(op["relative_path"]).suffix + ".bak")) if backup_root else None,
                    "original_sha256": op["original_sha256"],
                    "updated_sha256": op["updated_sha256"],
                    "changes": op["changes"],
                }
                for op in operations
            ],
        },
        "stop_lines": [
            "Apply is blocked unless the approval artifact validator returns ok for an unexpired, hash-matched, target-file-matched approval artifact.",
            "Proposal packet authority flags remain false; this helper grants only scoped owner-file write mechanics for the approved exact diff.",
            "No trade, order, brokerage, account, money-movement, owner-approval inference, or execution authority is granted.",
            "Post-apply validators remain required before any workflow closure claim.",
        ],
        "_operations": operations,
    }


def execute_apply(approval_path: Path, window: str) -> dict[str, Any]:
    plan = build_apply_plan(approval_path, window)
    operations = plan.pop("_operations", [])
    if plan["status"] != "ready_for_approval_gated_apply":
        plan["status"] = "blocked"
        return plan
    backup_root = ROOT / str(plan["rollback_plan"]["backup_root"])
    applied: list[dict[str, Any]] = []
    rollback_performed = False
    failure: str | None = None
    try:
        for op in operations:
            target: Path = op["path"]
            backup_path = (backup_root / op["relative_path"]).with_suffix(target.suffix + ".bak")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(str(op["original"]), encoding="utf-8")
            current = target.read_text(encoding="utf-8")
            if sha256_text(current) != op["original_sha256"]:
                raise RuntimeError(f"target changed before write: {op['relative_path']}")
            atomic_write_text(target, str(op["updated"]))
            applied.append({"path": op["relative_path"], "backup_path": rel(backup_path), "updated_sha256": op["updated_sha256"]})
    except Exception as exc:  # noqa: BLE001 - rollback and report exact failure
        failure = str(exc)
        rollback_performed = True
        for item in reversed(applied):
            backup_path = ROOT / item["backup_path"]
            target = ROOT / item["path"]
            if backup_path.exists():
                atomic_write_text(target, backup_path.read_text(encoding="utf-8"))
        plan["status"] = "failed_rolled_back"
    else:
        plan["status"] = "applied_pending_post_apply_validation"
    plan["summary"].update({
        "writes_performed": failure is None,
        "files_written": len(applied) if failure is None else 0,
        "rollback_performed": rollback_performed,
        "failure": failure,
    })
    plan["applied_files"] = applied
    return plan


def write_apply_result(result: dict[str, Any]) -> Path:
    APPLY_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(str(result.get("proposal_id") or Path(str(result.get("approval_artifact") or "approval")).stem))
    path = APPLY_RESULT_DIR / f"scoped-apply-result-{slug}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def write_outputs(preview: dict[str, Any]) -> tuple[Path, Path]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    source_slug = ""
    try:
        source_slug = Path(str(preview.get("input_bundle") or "")).stem
    except Exception:
        source_slug = ""
    slug_source = source_slug or str(preview.get("proposal_id") or "proposal")
    slug = safe_slug(slug_source)
    json_path = PREVIEW_DIR / f"exact-apply-preview-{slug}.json"
    md_path = PREVIEW_DIR / f"exact-apply-preview-{slug}.md"
    json_path.write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Exact Apply Preview - {preview.get('proposal_id')}",
        "",
        f"- Generated: `{preview.get('generated_at_utc')}`",
        f"- Status: **{preview.get('status')}**",
        f"- Input: `{preview.get('input_bundle')}`",
        "- Authority: dry-run patch preview only; no owner-file writes, no portfolio mutation, no trade/account action.",
        "",
        "## Summary",
        "",
        f"- Requested changes: {preview.get('summary', {}).get('requested_changes')}",
        f"- Previewed file changes: {preview.get('summary', {}).get('previewed_file_changes')}",
        f"- Ready for main-session review: {preview.get('summary', {}).get('ready_for_main_session_portfolio_mutation_review')}",
        f"- Apply ready: {preview.get('summary', {}).get('apply_ready')}",
        f"- Approval artifact required: {preview.get('summary', {}).get('approval_artifact_required')}",
        "",
        "## Stop lines",
        "",
    ]
    lines.extend(f"- {item}" for item in preview.get("stop_lines") or [])
    if preview.get("validation", {}).get("build_errors"):
        lines.extend(["", "## Build errors", ""])
        lines.extend(f"- {item}" for item in preview["validation"]["build_errors"])
    for item in preview.get("file_previews") or []:
        lines.extend(["", f"## `{item.get('path')}`", "", "```diff", item.get("diff") or "", "```"])
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="WF56/WF64 scoped patch preview and approval-gated atomic apply helper.")
    parser.add_argument("--proposal-bundle", default="tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    parser.add_argument("--proposal-id", help="Required when bundle contains multiple proposals")
    parser.add_argument("--window", default="post-close", choices=["morning", "post-close", "post-earnings", "sunday"])
    parser.add_argument("--write", action="store_true", help="Write preview artifacts under tmp/portfolio-mutation-proposals/")
    parser.add_argument("--apply", action="store_true", help="Execute an approval-gated scoped apply. Requires --approval-artifact.")
    parser.add_argument("--approval-artifact", help="WF56 scoped apply approval artifact for --apply or apply-plan mode.")
    parser.add_argument("--plan-apply", action="store_true", help="Build an apply/rollback plan without writing owner files. Requires --approval-artifact.")
    args = parser.parse_args()

    if args.apply or args.plan_apply:
        if not args.approval_artifact:
            print("portfolio_mutation_apply_helper: blocked (--apply/--plan-apply requires --approval-artifact)")
            return 2
        result = execute_apply(ROOT / args.approval_artifact, args.window) if args.apply else build_apply_plan(ROOT / args.approval_artifact, args.window)
        result.pop("_operations", None)
        if args.write or args.apply:
            result_path = write_apply_result(result)
            print(f"wrote {result_path}")
        print(json.dumps({
            "status": result["status"],
            "proposal_id": result.get("proposal_id"),
            "files_to_write": result["summary"]["files_to_write"],
            "writes_performed": result["summary"].get("writes_performed", False),
            "rollback_performed": result["summary"].get("rollback_performed", False),
        }, indent=2))
        return 0 if result["status"] in {"ready_for_approval_gated_apply", "applied_pending_post_apply_validation"} else 1

    preview = build_preview(ROOT / args.proposal_bundle, args.proposal_id, args.window)
    if args.write:
        json_path, md_path = write_outputs(preview)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
    print(json.dumps({
        "status": preview["status"],
        "proposal_id": preview["proposal_id"],
        "requested_changes": preview["summary"]["requested_changes"],
        "previewed_file_changes": preview["summary"]["previewed_file_changes"],
        "writes_performed": False,
    }, indent=2))
    return 1 if str(preview["status"]).startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
