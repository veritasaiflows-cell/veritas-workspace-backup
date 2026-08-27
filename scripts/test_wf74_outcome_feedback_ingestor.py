from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf74_outcome_feedback_ingestor.py"
HARNESS = ROOT / "scripts" / "wf74_learning_loop_eval_harness.py"


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
        cases = base / "cases.json"
        out = base / "feedback.json"
        improvement = base / "improvement.json"
        wf88 = base / "wf88.json"
        finance = base / "finance-response.json"
        recurrence = base / "recurrence.json"
        prompt_ledger = base / "prompt-ledger.json"
        harness_out = base / "harness.json"

        write_json(cases, {
            "schema": "veritas.wf74_learning_loop_eval_cases.v1",
            "generated_at_utc": "2026-06-30T05:00:00Z",
            "purpose": "test cases",
            "authority_boundary": {"review_only": True, "eval_only": True, "auto_apply_allowed": False, "owner_approval_inferred": False},
            "cases": [],
        })
        write_json(improvement, {
            "status": "ok",
            "summary": {"unclassified_closed_followup_count": 0},
        })
        write_json(wf88, {
            "status": "ok",
            "summary": {"delete_ready_count": 0},
        })
        write_json(finance, {
            "status": "ok",
            "summary": {"source_open_blocked_count": 0, "source_freshness_blocked_count": 0},
        })
        write_json(recurrence, {
            "status": "ok",
            "summary": {"source_open_step_order_error_count": 0},
        })
        write_json(prompt_ledger, {
            "status": "ok",
            "summary": {"current_prompt_id": "prompt-test", "auto_apply_count": 0},
        })

        cmd = [
            sys.executable,
            str(SCRIPT),
            "--cases",
            str(cases),
            "--out",
            str(out),
            "--improvement-ledger",
            str(improvement),
            "--wf88-control",
            str(wf88),
            "--finance-quality",
            str(finance),
            "--recurrence-guard",
            str(recurrence),
            "--prompt-ledger",
            str(prompt_ledger),
            "--write",
            "--validate",
        ]
        first = run_cmd(cmd)
        if first.returncode != 0:
            errors.append(f"first ingest failed: {first.stdout} {first.stderr}")
        payload = load_json(out)
        if payload.get("status") != "ok":
            errors.append("feedback ingest should be ok")
        if payload.get("summary", {}).get("append_case_count", 0) < 3:
            errors.append("expected reviewed cases to be appended")
        merged = load_json(cases)
        case_ids = {case.get("case_id") for case in merged.get("cases", [])}
        for expected in (
            "wf74_source_open_recurrence_guard_clean_proof",
            "wf74_closed_improvements_need_successor_artifact_or_class",
            "wf74_self_prompt_variant_metadata_only",
        ):
            if expected not in case_ids:
                errors.append(f"missing appended case: {expected}")

        harness = run_cmd([
            sys.executable,
            str(HARNESS),
            "--cases",
            str(cases),
            "--out",
            str(harness_out),
            "--write",
            "--validate",
        ])
        if harness.returncode != 0:
            errors.append(f"merged cases should pass eval harness: {harness.stdout} {harness.stderr}")

        second = run_cmd(cmd)
        if second.returncode != 0:
            errors.append(f"second ingest failed: {second.stdout} {second.stderr}")
        second_payload = load_json(out)
        if second_payload.get("summary", {}).get("append_case_count") != 0:
            errors.append("second run should not duplicate cases")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: WF74 outcome feedback ingestor appends validated eval cases idempotently")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
