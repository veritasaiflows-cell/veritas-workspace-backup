"""Deterministic runner for the "Runtime - OS Audit Companion Packets Refresh" cron job.

Purpose (token-efficiency pilot, approved 2026-08-26):
- Collapse six fixed refresh commands into one deterministic subprocess runner so the
  cron agent turn spends one tool call instead of orchestrating six.
- Capture input/output fingerprints so a future changed-input skip gate can be
  evaluated with real evidence before any zero-spawn trigger is requested.

Authority boundary: review/proof only. No cleanup apply, no cron/config/runtime
mutation, no finance/canon/portfolio mutation, no paper/live action, no approval
inference. Runs the exact six commands the cron job already runs today.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
MEMORY = ROOT / "memory"
PROOF_PATH = TMP / "os-audit-companion-refresh-proof.json"
STATE_PATH = STATE / "os-audit-companion-refresh-runner-state.json"

COMMANDS = [
    ["python", "scripts/tmp_lifecycle_guard.py", "--write", "--validate"],
    ["python", "scripts/token_budget_status.py", "--write", "--validate"],
    ["python", "scripts/security_warning_ledger.py", "--write", "--validate"],
    ["python", "scripts/wf78_promotion_visibility_top10.py", "--write", "--validate"],
    ["python", "scripts/pm_autonomy_verifier.py", "--health-check", "--validate"],
    ["python", "scripts/status_card_packet.py", "--write", "--validate"],
]

# High-signal output artifacts written by the six commands (best-effort; missing is ok).
OUTPUT_ARTIFACTS = [
    "tmp/tmp-lifecycle-guard.json",
    "tmp/token-budget-status.json",
    "tmp/security-warning-ledger.json",
    "tmp/wf78-promotion-visibility-top10.json",
    "tmp/pm-autonomy-verifier-health.json",
    "tmp/veritas-status-card-frontdoor.json",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _inventory_fingerprint() -> dict:
    """Fingerprint tmp/state/memory file inventory (path|size|mtime_ns).

    Uses os.scandir recursion so stat data comes from the directory listing
    (cached on Windows), keeping the walk cheap even for a large tmp tree.
    This is the cheap pre-model signal: if this fingerprint is unchanged between
    scheduled runs, a future skip gate would have produced identical output.
    """
    import os

    h = hashlib.sha256()
    count = 0
    skip_dirs = {"__pycache__"}

    def walk(base: Path, rel_base: str) -> None:
        nonlocal count
        stack = [(base, rel_base)]
        while stack:
            current, rel = stack.pop()
            try:
                entries = sorted(os.scandir(current), key=lambda e: e.name)
            except OSError:
                continue
            for entry in entries:
                entry_rel = f"{rel}/{entry.name}" if rel else entry.name
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in skip_dirs:
                            continue
                        stack.append((Path(entry.path), entry_rel))
                    elif entry.is_file(follow_symlinks=False):
                        st = entry.stat(follow_symlinks=False)
                        h.update(f"{entry_rel}|{st.st_size}|{st.st_mtime_ns}\n".encode("utf-8"))
                        count += 1
                except OSError:
                    continue

    for root_dir, rel_root in ((TMP, "tmp"), (STATE, "state"), (MEMORY, "memory")):
        if root_dir.exists():
            walk(root_dir, rel_root)
    return {"sha256": h.hexdigest(), "file_count": count}


def _output_fingerprint() -> dict:
    h = hashlib.sha256()
    present = 0
    for rel in OUTPUT_ARTIFACTS:
        path = ROOT / rel
        if not path.exists():
            h.update(f"{rel}|MISSING\n".encode("utf-8"))
            continue
        h.update(rel.encode("utf-8"))
        h.update(path.read_bytes())
        present += 1
    return {"sha256": h.hexdigest(), "artifacts_present": present, "artifacts_total": len(OUTPUT_ARTIFACTS)}


def _load_previous_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def run_commands() -> tuple[list[dict], int]:
    results: list[dict] = []
    failed_at = -1
    for index, argv in enumerate(COMMANDS):
        started = datetime.now(timezone.utc)
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        finished = datetime.now(timezone.utc)
        entry = {
            "index": index + 1,
            "argv": argv,
            "exit_code": proc.returncode,
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }
        results.append(entry)
        if proc.returncode != 0:
            failed_at = index + 1
            break
    return results, failed_at


def main() -> int:
    parser = argparse.ArgumentParser(description="OS audit companion deterministic refresh runner")
    parser.add_argument("--write", action="store_true", help="write proof artifact (default true; kept for parity)")
    parser.add_argument("--validate", action="store_true", help="validate proof after write")
    parser.add_argument("--dry-run", action="store_true", help="plan only; do not execute commands")
    args = parser.parse_args()

    previous = _load_previous_state()
    input_fp_before = _inventory_fingerprint()

    proof = {
        "schema": "veritas.os_audit_companion_refresh_runner.v1",
        "generated_at_utc": _utc_now(),
        "authority_boundary": "review_proof_only_no_cleanup_no_cron_config_runtime_finance_portfolio_paper_live_or_approval_mutation",
        "pilot": "token_efficiency_candidate_1_changed_input_prefilter_20260826",
        "commands_planned": [list(argv) for argv in COMMANDS],
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        proof["status"] = "dry_run"
        proof["input_fingerprint_before"] = input_fp_before
        PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "dry_run", "proof": str(PROOF_PATH)}))
        return 0

    results, failed_at = run_commands()
    input_fp_after = _inventory_fingerprint()
    output_fp = _output_fingerprint()

    prev_input = previous.get("input_fingerprint_after", {})
    prev_output = previous.get("output_fingerprint", {})
    would_have_skipped = bool(prev_input) and prev_input.get("sha256") == input_fp_before.get("sha256")
    outputs_changed = output_fp.get("sha256") != prev_output.get("sha256")

    proof.update(
        {
            "status": "ok" if failed_at == -1 else "error",
            "failed_at_step": failed_at if failed_at != -1 else None,
            "results": results,
            "input_fingerprint_before": input_fp_before,
            "input_fingerprint_after": input_fp_after,
            "output_fingerprint": output_fp,
            "skip_gate_evidence": {
                "would_have_skipped_this_run": would_have_skipped,
                "outputs_changed_vs_previous_run": outputs_changed,
                "previous_run_at_utc": previous.get("generated_at_utc"),
                "note": "would_have_skipped=true means inputs were identical to the end of the previous run; a pre-spawn skip gate would have made this run unnecessary.",
            },
        }
    )

    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")

    if failed_at == -1:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(
                {
                    "generated_at_utc": proof["generated_at_utc"],
                    "input_fingerprint_after": input_fp_after,
                    "output_fingerprint": output_fp,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.validate:
        loaded = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
        assert loaded["schema"] == proof["schema"], "proof schema mismatch"
        assert loaded["status"] == proof["status"], "proof status mismatch"

    print(
        json.dumps(
            {
                "status": proof["status"],
                "failed_at_step": proof["failed_at_step"],
                "would_have_skipped_this_run": would_have_skipped,
                "outputs_changed_vs_previous_run": outputs_changed,
                "proof": str(PROOF_PATH),
            }
        )
    )
    return 0 if failed_at == -1 else 1


if __name__ == "__main__":
    sys.exit(main())
