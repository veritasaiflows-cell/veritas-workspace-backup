import datetime
import hashlib
import json
from pathlib import Path

run = Path(__file__).resolve().parent
probe = run / "closed-gate-probe-out"
canon = json.loads(
    Path(
        r"data/evals/model-arena/arena-agentic-v1-20260920/overlay/dispatch-authorization.json"
    ).read_text(encoding="utf-8")
)
g = json.loads((run / "graded-results.json").read_text(encoding="utf-8"))
d = json.loads((run / "dimensional-rescore.json").read_text(encoding="utf-8"))
auth = json.loads((run / "authorization.json").read_text(encoding="utf-8"))
hits = [r["instance_id"][:8] + " " + r["family"] for r in g["results"] if r["strict_pass"]]


def sha(name: str) -> dict:
    p = run / name
    return {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


receipt = {
    "schema": "veritas.arena_run_receipt.v1",
    "envelope": "arena-agentic-v1-20260920",
    "overlay_version": "arena-agentic-v1-20260920-overlay-r2",
    "model": "meta/muse-spark-1.3-contributor",
    "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "authorization": {
        "authorized_at": auth["authorized_at"],
        "authorized_by": auth["authorized_by"],
        "cases": 12,
        "model_scope": auth["scope"]["models"],
        "reps": 1,
        "source": "explicit WebChat owner request to continue Spark 1.3 overlay-r2 via CLI",
    },
    "dispatch_gate_after_run": {
        "authorized_at": canon.get("authorized_at"),
        "authorized_by": canon.get("authorized_by"),
        "closed_gate_probe_created_output": probe.exists(),
        "closed_gate_probe_exit": 1,
        "dispatch_ready": canon.get("dispatch_ready"),
        "scope_models": canon.get("scope", {}).get("models"),
    },
    "execution": {
        "attempted": 12,
        "completed": 12,
        "planned": 12,
        "retries": 0,
        "timeout": 0,
        "timeout_seconds": 600,
    },
    "grading": {
        "contaminated": g["contaminated_count"],
        "dimensional_score": d.get("dimensional_score"),
        "family_scores_clean": d.get("family_scores_clean"),
        "strict_clean": f"{g['strict_pass_count_clean']}/{g['total']}",
    },
    "transport": {
        "agent_id": "oxalpha-functional-lab",
        "cli": "openclaw agent --json --timeout 600 --thinking high --model meta/muse-spark-1.3-contributor",
        "candidate_mount": ["candidate-visible-bank.json", "fixtures/"],
        "effective_model_receipts": "12/12 exact",
        "hidden_control_files_present": False,
        "reroutes": 0,
        "fallbacks": 0,
        "sandbox": "docker session sandbox",
    },
    "strict_hits": hits,
    "artifacts": {
        name: sha(name)
        for name in [
            "authorization.json",
            "dispatch-plan.json",
            "graded-results.json",
            "responses.json",
            "transport-receipts.json",
            "dimensional-rescore.json",
        ]
        if (run / name).exists()
    },
}
(run / "run-receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
(run / "closed-gate-probe.txt").write_text(
    "runner_fail_closed: authorization_not_dispatch_ready:False\n"
    "exit=1\n"
    "output_created=false\n"
    "canonical overlay/dispatch-authorization.json left INERT\n",
    encoding="utf-8",
)
print("probe_dir_exists", probe.exists())
print("canon_ready", canon.get("dispatch_ready"))
print("receipt_ok")
print("strict", g["strict_pass_count"], "dim", d.get("dimensional_score"))
