from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cron_cadence_reduction_plan.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-cron-cadence-reduction-plan.json"
    cmd = [sys.executable, str(SCRIPT), "--write", "--validate", "--json-out", str(out)]
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    expect(completed.returncode == 0, f"script failed: {completed.stdout} {completed.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.cron_cadence_reduction_plan.v1", "schema mismatch", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "cron_state_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "runtime_config_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    policy = payload.get("policy", {})
    expect(policy.get("openai/gpt-5.6-luna") == "low for proven deterministic agentTurn cron/status/proof jobs", "Luna policy should be low and deterministic-only", errors)
    expect(policy.get("openai/gpt-5.6-terra") == "medium for reasoning or tool-heavy cron helpers", "Terra cron-helper policy should be medium", errors)
    expect(payload.get("summary", {}).get("live_job_count", 0) > 0, "expected live jobs", errors)
    expect(isinstance(payload.get("effort_patches"), list), "effort patches should be a list", errors)
    expect(isinstance(payload.get("non_agent_jobs_to_preserve"), list), "non-agent preservation list missing", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: cron cadence reduction plan is review-only and policy-aware")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
