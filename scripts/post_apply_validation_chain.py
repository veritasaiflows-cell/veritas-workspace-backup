from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_approval_artifact_validator as approval_validator

ROOT = Path(__file__).resolve().parents[1]
APPLY_RESULTS_ROOT = ROOT / "tmp" / "portfolio-mutation-proposals" / "apply-results"
OUT = ROOT / "tmp" / "post-apply-validation-chain.json"
APPROVAL_ROOT = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals"
def chain(window: str, approval_artifact: str | None = None) -> list[list[str]]:
    coherence_cmd = [sys.executable, "scripts/post_apply_board_snapshot_config_coherence.py", "--write"]
    if approval_artifact:
        coherence_cmd.extend(["--approval-artifact", approval_artifact])
    return [
        [sys.executable, "scripts/validate_canonical_ownership.py"],
        [sys.executable, "scripts/validate_portfolio_config.py"],
        [sys.executable, "scripts/validate_dashboard_state.py", "--write"],
        [sys.executable, "scripts/pipeline_state_consistency_check.py", "--window", window],
        [sys.executable, "scripts/full_portfolio_view.py", "--window", window, "--write"],
        [sys.executable, "scripts/full_portfolio_view_validate.py", "--window", window, "--write"],
        coherence_cmd,
        [sys.executable, "scripts/board_canon_guardrail.py", "--write"],
        [sys.executable, "scripts/stale_intelligence_guardrail.py", "--write"],
        [sys.executable, "scripts/proposal_patch_scope_validator.py", "--write"],
        [sys.executable, "scripts/canonical_status_invariant_validator.py", "--write"],
        [sys.executable, "scripts/portfolio_pro_forma_risk_validator.py", "--write"],
        [sys.executable, "scripts/authority_vocabulary_consistency_check.py", "--write"],
    ]


def validation_failed_only_because_applied(approval_validation: dict | None) -> bool:
    if not approval_validation or approval_validation.get("status") == "ok":
        return False
    findings = approval_validation.get("findings") or []
    if not findings:
        return False
    for item in findings:
        issue = str(item.get("issue") or "")
        if "old_text must match exactly once; matched 0" not in issue:
            return False
    proposal_id = approval_validation.get("proposal_id")
    if not proposal_id or not APPLY_RESULTS_ROOT.exists():
        return False
    for path in sorted(APPLY_RESULTS_ROOT.glob("scoped-apply-result-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("proposal_id") != proposal_id:
            continue
        if data.get("status") in {"applied_pending_post_apply_validation", "applied_and_validated"} and (data.get("summary") or {}).get("writes_performed") is True:
            return True
    return False


def run_step(cmd: list[str], execute: bool) -> dict:
    if not execute:
        return {"cmd": cmd, "status": "planned", "returncode": None, "stdout_tail": "", "stderr_tail": ""}
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-apply validation chain after bounded note sync.")
    parser.add_argument("--execute", action="store_true", help="Run validators. Without this flag, writes a dry-run plan only.")
    parser.add_argument("--window", default="post-close", choices=["morning", "post-close", "sunday"], help="Window to validate when executing after a bounded note sync.")
    parser.add_argument("--approval-artifact", help="Required for --execute; must live under tmp/portfolio-mutation-proposals/approvals/.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    approval_blocker = None
    approval_validation = None
    if args.execute:
        if not args.approval_artifact:
            approval_blocker = "--execute requires --approval-artifact"
        else:
            approval_path = (ROOT / args.approval_artifact).resolve()
            try:
                approval_path.relative_to(APPROVAL_ROOT.resolve())
            except ValueError:
                approval_blocker = "approval artifact must live under tmp/portfolio-mutation-proposals/approvals/"
            if approval_blocker is None and not approval_path.exists():
                approval_blocker = f"approval artifact not found: {args.approval_artifact}"
            if approval_blocker is None:
                approval_validation = approval_validator.validate_approval(approval_path)
                if approval_validation.get("status") != "ok":
                    if validation_failed_only_because_applied(approval_validation):
                        approval_validation["post_apply_preapply_validation_note"] = "Approval artifact no longer pre-validates because the exact old_text was already applied; proceeding with post-apply validators based on the recorded successful apply result."
                    else:
                        approval_blocker = "approval artifact validation failed"
    steps = [] if approval_blocker else [run_step(cmd, args.execute) for cmd in chain(args.window, args.approval_artifact)]
    failures = [step for step in steps if step["status"] == "failed"]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "execute" if args.execute else "dry_run",
        "window": args.window,
        "approval_artifact": args.approval_artifact,
        "status": "blocked" if approval_blocker else ("ok" if not failures else "failed"),
        "authority": {
            "gated_portfolio_note_model_mutation_allowed": True,
            "validation_chain_apply_allowed": bool(args.execute and not approval_blocker),
            "portfolio_mutation_allowed_by_this_artifact": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {"steps": len(steps), "failed": len(failures), "approval_blocker": approval_blocker},
        "approval_validation": approval_validation,
        "steps": steps,
    }
    if args.write or args.execute:
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(f"post_apply_validation_chain: {payload['status']} ({len(failures)} failed, mode={payload['mode']})")
    return 1 if approval_blocker or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
