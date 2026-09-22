import datetime
import hashlib
import json
from pathlib import Path

run = Path(__file__).resolve().parent
canon = json.loads(
    Path(
        r"data/evals/model-arena/arena-agentic-v1-20260920/overlay/dispatch-authorization.json"
    ).read_text(encoding="utf-8")
)
g = json.loads((run / "graded-results.json").read_text(encoding="utf-8"))
d = json.loads((run / "dimensional-rescore.json").read_text(encoding="utf-8"))
auth = json.loads((run / "authorization.json").read_text(encoding="utf-8"))
hits = [
    r["instance_id"][:8] + " " + r["family"]
    for r in g["results"]
    if r["strict_pass"]
]
misses = [
    r["instance_id"][:8]
    + " "
    + r["family"]
    + " "
    + (r.get("operational_outcome") or "")
    for r in g["results"]
    if not r["strict_pass"]
]


def sha(name: str) -> dict:
    p = run / name
    return {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


receipt = {
    "schema": "veritas.arena_run_receipt.v1",
    "envelope": "arena-agentic-v1-20260920",
    "overlay_version": "arena-agentic-v1-20260920-overlay-r2",
    "model": "ollama-cloud/glm-5.3-flash:cloud",
    "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "authorization": {
        "authorized_at": auth["authorized_at"],
        "authorized_by": auth["authorized_by"],
        "cases": 12,
        "model_scope": auth["scope"]["models"],
        "reps": 1,
        "source": "explicit WebChat owner request to rerun GLM Flash on functional-lab CLI",
    },
    "dispatch_gate_after_run": {
        "authorized_at": canon.get("authorized_at"),
        "authorized_by": canon.get("authorized_by"),
        "dispatch_ready": canon.get("dispatch_ready"),
        "scope_models": canon.get("scope", {}).get("models"),
    },
    "execution": {
        "attempted": 12,
        "completed": 11,
        "planned": 12,
        "retries": 0,
        "timeout": 1,
        "timeout_case": "75c25de61ca18168d846f86e84e40de6b807213f547029876cb6ca2bcc99c2b4",
        "timeout_seconds": 600,
    },
    "grading": {
        "contaminated": g["contaminated_count"],
        "dimensional_score": d.get("dimensional_score"),
        "family_scores_clean": d.get("family_scores_clean"),
        "strict_clean": f"{g['strict_pass_count_clean']}/{g['total']}",
        "misses": misses,
    },
    "transport": {
        "agent_id": "oxalpha-functional-lab",
        "cli": "openclaw agent --json --timeout 600 --thinking high --model ollama-cloud/glm-5.3-flash:cloud",
        "candidate_mount": ["candidate-visible-bank.json", "fixtures/"],
        "effective_model_receipts": "11/11 exact; 1 timeout empty",
        "reroutes": 0,
        "fallbacks": 0,
        "sandbox": "docker session sandbox",
        "prior_collector_run": "glm53flash-overlay-r2-20260920 (4/12) left untouched",
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
print("canon_ready", canon.get("dispatch_ready"))
print("strict", g["strict_pass_count"], "dim", d.get("dimensional_score"))
print("misses", misses)
