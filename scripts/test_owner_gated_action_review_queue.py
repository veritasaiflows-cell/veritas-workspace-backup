from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "owner_gated_action_review_queue.py"
REQUIRED_GATES = {"skill_approval", "cron_schedule_mutation", "alert_canon_policy_mutation"}
FORBIDDEN_ACTIVE_TEXT = (
    "finance_canon_portfolio_mutation",
    "capital_deployment",
    "wf67",
    "wf78",
    "wf85",
    "wf87",
    "sizing/staggering",
    "paper position",
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-owner-gated-action-review-queue.json"
    md = ROOT / "tmp" / "test-owner-gated-action-review-queue.md"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--write-md", "--validate", "--json-out", str(out), "--md-out", str(md)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(completed.returncode == 0, f"queue script failed: {completed.stdout} {completed.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.owner_gated_action_review_queue.v1", "schema mismatch", errors)
    expect(payload.get("finance_scope") == "alerts_and_non_executing_recommendations_only", "finance scope mismatch", errors)
    expect(payload.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
    gates = {item.get("gate") for item in payload.get("review_items", [])}
    expect(REQUIRED_GATES.issubset(gates), f"missing gates: {sorted(REQUIRED_GATES - gates)}", errors)
    boundary = payload.get("authority_boundary", {})
    expect(boundary.get("review_only") is True, "queue must stay review-only", errors)
    for key, value in boundary.items():
        if key not in {"review_only", "recommendation_queue_only", "local_only"}:
            expect(value is False, f"queue boundary must stay false: {key}", errors)
    active_text = json.dumps({"gates": list(gates), "items": payload.get("review_items"), "sources": payload.get("source_status")}).lower()
    for term in FORBIDDEN_ACTIVE_TEXT:
        expect(term not in active_text, f"retired finance route leaked into active queue: {term}", errors)
    expect(md.exists(), "markdown output missing", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: owner-gated action review queue is alerts-only and non-authorizing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
