from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf74_prompt_variant_ledger.py"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        self_prompt = base / "self-prompt.json"
        autopilot = base / "autopilot.json"
        proposer = base / "proposer.json"
        eval_harness = base / "eval.json"
        improvement = base / "improvement.json"
        ledger = base / "ledger.jsonl"
        out = base / "out.json"

        write_json(self_prompt, {
            "schema": "veritas.wf74_self_prompt_review_packet.v1",
            "generated_at_utc": "2026-06-30T05:00:00Z",
            "status": "ok",
            "self_prompt": {
                "prompt_id": "wf74-self-prompt-20260630-test",
                "variant_id": "variant-test",
                "full_text": "Did you verify freshness? Did you avoid approval inference?",
                "source_critique_categories": ["response_quality"],
                "source_opportunity_ids": ["response-recommendation-gap"],
                "source_open_improvement_ids": ["wf74-open-1"],
                "sections": [
                    {
                        "section_id": "truth_first",
                        "questions": [
                            {"question": "Did you verify freshness?", "focus": "freshness"},
                            {"question": "Did you avoid approval inference?", "focus": "authority"},
                        ],
                    }
                ],
            },
        })
        write_json(autopilot, {
            "status": "ok",
            "generated_at_utc": "2026-06-30T05:01:00Z",
            "summary": {"proposal_count": 2, "owner_decision_required_count": 0, "auto_apply_count": 0},
        })
        write_json(proposer, {
            "status": "ok",
            "generated_at_utc": "2026-06-30T05:02:00Z",
            "summary": {"patch_plan_count": 1, "skill_workshop_request_count": 1, "auto_apply_count": 0, "auto_apply_candidate_count": 0},
        })
        write_json(eval_harness, {
            "status": "ok",
            "generated_at_utc": "2026-06-30T05:03:00Z",
            "summary": {"case_count": 7, "failed_count": 0},
        })
        write_json(improvement, {
            "status": "ok",
            "generated_at_utc": "2026-06-30T05:04:00Z",
            "summary": {"latest_open_count": 1, "latest_closed_count": 3, "appended_event_count": 0},
        })

        cmd = [
            sys.executable,
            str(SCRIPT),
            "--self-prompt",
            str(self_prompt),
            "--proposal-autopilot",
            str(autopilot),
            "--auto-patch-proposer",
            str(proposer),
            "--eval-harness",
            str(eval_harness),
            "--improvement-ledger",
            str(improvement),
            "--ledger",
            str(ledger),
            "--out",
            str(out),
            "--write",
            "--validate",
        ]
        first = run_cmd(cmd)
        if first.returncode != 0:
            errors.append(f"first run failed: {first.stdout} {first.stderr}")
        payload = load_json(out)
        if payload.get("status") != "ok":
            errors.append("payload status should be ok")
        event = payload.get("current_event", {})
        if event.get("self_prompt", {}).get("self_prompt_sha256") is None:
            errors.append("self prompt hash missing")
        serialized = json.dumps(payload, sort_keys=True)
        if "Did you verify freshness?" in serialized:
            errors.append("raw self-prompt text leaked into summary payload")
        if "full_text" in serialized:
            errors.append("full_text key leaked into summary payload")
        if payload.get("summary", {}).get("appended_event_count") != 1:
            errors.append("first run should append exactly one event")
        if not ledger.exists() or len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]) != 1:
            errors.append("ledger should contain one event after first run")

        second = run_cmd(cmd)
        if second.returncode != 0:
            errors.append(f"second run failed: {second.stdout} {second.stderr}")
        second_payload = load_json(out)
        if second_payload.get("summary", {}).get("appended_event_count") != 0:
            errors.append("second run should be idempotent for same prompt variant")
        if len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]) != 1:
            errors.append("idempotent run changed ledger length")

        dirty = json.loads(self_prompt.read_text(encoding="utf-8"))
        dirty["self_prompt"]["prompt_id"] = "wf74-self-prompt-dirty"
        write_json(self_prompt, dirty)
        dirty_proposer = json.loads(proposer.read_text(encoding="utf-8"))
        dirty_proposer["summary"]["auto_apply_count"] = 1
        write_json(proposer, dirty_proposer)
        dirty_run = run_cmd(cmd)
        if dirty_run.returncode == 0:
            errors.append("auto-apply count should fail validation")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: WF74 prompt variant ledger is metadata-only and idempotent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
