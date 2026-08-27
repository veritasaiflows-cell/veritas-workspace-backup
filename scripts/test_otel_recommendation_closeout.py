from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "otel_recommendation_closeout.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-otel-recommendation-closeout.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json-out", str(out), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"script failed: {result.stdout} {result.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.otel_recommendation_closeout.v1", "schema mismatch", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "cron_schedule_mutation_allowed",
        "cron_payload_mutation_allowed",
        "runtime_config_mutation_allowed",
        "collector_config_mutation_allowed",
        "destructive_cleanup_allowed",
        "archive_or_delete_allowed",
        "external_export_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    recommendations = payload.get("recommendations", {})
    for key in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
        expect(key in recommendations, f"missing recommendation status: {key}", errors)
    expect(payload.get("r5_stale_scorecard_dry_run", {}).get("destructive_action_taken") is False, "R5 must stay dry-run", errors)
    expect(payload.get("r8_dead_collector_hygiene_dry_run", {}).get("destructive_action_taken") is False, "R8 must stay dry-run", errors)
    steps = payload.get("cron_migration_next_steps", [])
    expect(len(steps) >= 6, "cron migration steps missing", errors)
    expect(any(step.get("mutation_allowed") == "explicit_owner_approval_required" for step in steps), "owner approval step missing", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: otel recommendation closeout is review-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
