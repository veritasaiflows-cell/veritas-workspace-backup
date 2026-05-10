from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"

RUN_SUMMARY = TMP / "run-summary-post-close.json"
POSTCLOSE_BRIEF_INPUT = TMP / "postclose-brief-input.json"
POSTMARKET_SNAPSHOT = TMP / "postmarket-snapshot.json"
DAILY_EXECUTIVE_BRIEF = TMP / "daily-executive-brief.json"
CONSISTENCY_REPORT = TMP / "pipeline-state-consistency.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def artifact_authority(data: dict[str, Any]) -> dict[str, bool]:
    return {
        "canonical_mutation_allowed": bool(data.get("canonical_mutation_allowed", False)),
        "presentation_allowed": bool(data.get("presentation_allowed", False)),
        "portfolio_mutation_allowed": bool(data.get("portfolio_mutation_allowed", False)),
        "deployment_state_mutation_allowed": bool(data.get("deployment_state_mutation_allowed", False)),
        "trade_execution_allowed": bool(data.get("trade_execution_allowed", False)),
        "owner_approval_granted": any(
            bool(data.get(key, False))
            for key in ("owner_approval_granted", "owner_approval_inferred", "owner_approved")
        ),
    }


def main() -> int:
    errors: list[str] = []
    for path in (RUN_SUMMARY, POSTCLOSE_BRIEF_INPUT, POSTMARKET_SNAPSHOT, DAILY_EXECUTIVE_BRIEF):
        expect(path.exists(), f"missing required artifact: {path.relative_to(WORKSPACE)}", errors)
    if errors:
        print("post-close authority test failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    run_summary = load_json(RUN_SUMMARY)
    ceiling = (run_summary.get("downstream") or {})
    expect(ceiling.get("canonical_note_mutation_allowed") is False, "run summary must keep canonical note mutation disabled", errors)
    expect(ceiling.get("presentation_allowed") is False, "run summary must keep presentation disabled", errors)

    artifacts = {
        "postclose_brief_input": load_json(POSTCLOSE_BRIEF_INPUT),
        "postmarket_snapshot": load_json(POSTMARKET_SNAPSHOT),
        "daily_executive_brief": load_json(DAILY_EXECUTIVE_BRIEF),
    }
    for name, data in artifacts.items():
        authority = artifact_authority(data)
        for field, value in authority.items():
            expect(value is False, f"{name} must not claim {field}=true", errors)

    expect(artifacts["postclose_brief_input"].get("consumer_posture") == "review_only", "postclose packet must remain review_only", errors)
    for name in ("postmarket_snapshot", "daily_executive_brief"):
        expect(
            artifacts[name].get("consumer_posture") == "generated_dashboard_archive",
            f"{name} must declare generated_dashboard_archive posture",
            errors,
        )

    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "pipeline_state_consistency_check.py")],
        cwd=WORKSPACE,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append("pipeline_state_consistency_check.py must pass without authority contradictions")
        if result.stdout:
            errors.append(result.stdout.strip())
        if result.stderr:
            errors.append(result.stderr.strip())
    elif CONSISTENCY_REPORT.exists():
        report = load_json(CONSISTENCY_REPORT)
        expect(report.get("authority_findings_count") == 0, "authority validator must report zero authority findings", errors)

    if errors:
        print("post-close authority test failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("post-close authority test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
