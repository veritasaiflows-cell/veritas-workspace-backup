from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as preview_helper
import portfolio_mutation_approval_artifact_validator as approval_validator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals" / "scoped-apply-result.json"


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def replacement_plan(packet: dict[str, Any]) -> list[dict[str, Any]]:
    plan = []
    for change in preview_helper.extract_changes(packet):
        raw_path = preview_helper.change_path(change)
        target = preview_helper.normalize_path(raw_path)
        old_text = change.get("old_text")
        new_text = change.get("new_text")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            raise ValueError(f"change for {raw_path} requires string old_text and new_text")
        original = target.read_text(encoding="utf-8")
        updated = preview_helper.apply_text_change(original, old_text, new_text, raw_path)
        plan.append({
            "path": rel(target),
            "target": target,
            "old_text": old_text,
            "new_text": new_text,
            "updated_text": updated,
            "rationale": str(change.get("rationale") or "Scoped approved owner-file update."),
        })
    return plan


def run_post_apply_validation(window: str, approval_artifact: str) -> dict[str, Any]:
    cmd = [sys.executable, "scripts/post_apply_validation_chain.py", "--execute", "--write", "--window", window, "--approval-artifact", approval_artifact]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def build_result(approval_artifact: str, execute: bool, window: str, confirm_proposal_id: str | None) -> dict[str, Any]:
    approval_path = ROOT / approval_artifact
    approval_report = approval_validator.validate_approval(approval_path)
    approval = load_json(approval_path) if approval_path.exists() else {}
    proposal_id = str(approval.get("proposal_id") or "")
    if confirm_proposal_id and confirm_proposal_id != proposal_id:
        approval_report.setdefault("findings", []).append({
            "severity": "critical",
            "issue": "confirm_proposal_id does not match approval artifact",
            "expected": proposal_id,
            "actual": confirm_proposal_id,
        })
        approval_report["summary"]["critical"] = approval_report["summary"].get("critical", 0) + 1
        approval_report["status"] = "blocked"

    packet: dict[str, Any] = {}
    plan: list[dict[str, Any]] = []
    plan_errors: list[str] = []
    if approval_report.get("status") == "ok":
        try:
            packet = preview_helper.select_proposal(load_json(ROOT / str(approval["proposal_artifact"])), proposal_id)
            plan = replacement_plan(packet)
        except Exception as exc:  # noqa: BLE001
            plan_errors.append(str(exc))

    status = "planned"
    writes_performed = False
    post_apply = None
    if approval_report.get("status") != "ok" or plan_errors:
        status = "blocked"
    elif execute:
        for item in plan:
            target = item["target"]
            target.write_text(item["updated_text"], encoding="utf-8")
            writes_performed = True
        post_apply = run_post_apply_validation(window, approval_artifact)
        status = "applied_and_validated" if post_apply["status"] == "ok" else "applied_validation_failed"
    else:
        status = "ready_to_apply_with_execute"

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "execute" if execute else "dry_run",
        "approval_artifact": approval_artifact,
        "proposal_id": proposal_id or None,
        "authority": {
            "scoped_owner_file_write_allowed_by_approval": approval_report.get("status") == "ok",
            "approved_adjustment_categories": approval_report.get("authority", {}).get("approved_adjustment_categories", []),
            "writes_performed": writes_performed,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
            "legacy_sizing_sleeve_cash_risk_rule_field_allowed": False,
            "execution_entitlement_allowed": False,
        },
        "summary": {
            "planned_file_changes": len(plan),
            "writes_performed": writes_performed,
            "approval_critical": approval_report.get("summary", {}).get("critical"),
            "plan_errors": len(plan_errors),
        },
        "approval_validation": approval_report,
        "plan_errors": plan_errors,
        "planned_changes": [
            {"path": item["path"], "rationale": item["rationale"], "writes_performed": writes_performed}
            for item in plan
        ],
        "post_apply_validation": post_apply,
        "stop_lines": [
            "This helper only applies exact old_text/new_text replacements named by a valid scoped approval artifact.",
            "The approval artifact authorizes only the named approved_adjustment_categories and target files; trade/account action, cash, risk-rule, unscoped sizing/sleeve/sector, and execution-entitlement changes remain blocked.",
            "Scheduled apply remains blocked; execute mode is manual/main-session only.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WF56 Phase 4 scoped apply helper. Execute requires a valid explicit approval artifact.")
    parser.add_argument("--approval-artifact", required=True)
    parser.add_argument("--confirm-proposal-id")
    parser.add_argument("--window", default="post-close", choices=["morning", "post-close", "sunday"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build_result(args.approval_artifact, args.execute, args.window, args.confirm_proposal_id)
    if args.write or args.execute:
        write_json(OUT, result)
        print(f"wrote {OUT}")
    print(json.dumps({
        "status": result["status"],
        "mode": result["mode"],
        "proposal_id": result["proposal_id"],
        "planned_file_changes": result["summary"]["planned_file_changes"],
        "writes_performed": result["summary"]["writes_performed"],
    }, indent=2))
    return 1 if result["status"] in {"blocked", "applied_validation_failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
