"""Arena-six MiniMax M3 dispatcher. Frozen prompts, 2 reps, zero retries.

Multi-turn families reuse one session id per trajectory and send turns in order.
Does not flip the canonical overlay spend gate.
"""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RUN = Path(__file__).resolve().parent
PROMPTS = RUN / "prompts"
MODEL = "ollama-cloud/minimax-m3:cloud"
AGENT = "oxalpha-functional-lab"
TIMEOUT_S = 600
OPENCLAW = Path(r"C:\Users\Veritas\AppData\Roaming\npm\openclaw.cmd")

TRAJECTORIES = [
    ("T1-settlement-cascade", ["T1-settlement-cascade.txt"]),
    ("T2-event-revert-ambiguity", [
        "T2-event-revert-ambiguity-turn1.txt",
        "T2-event-revert-ambiguity-turn2.txt",
        "T2-event-revert-ambiguity-turn3.txt",
        "T2-event-revert-ambiguity-turn4.txt",
    ]),
    ("T3-evidence-retraction-chain", ["T3-evidence-retraction-chain.txt"]),
    ("T5-handoff-authority-control", [
        "T5-handoff-authority-control-turn1.txt",
        "T5-handoff-authority-control-turn2.txt",
    ]),
    ("T6-induction-and-planning", ["T6-induction-and-planning.txt"]),
]
# T4 is dispatched separately: it needs staged arena-six-inputs-20260919/ readable in-session.


def run_turn(session_id: str, prompt: Path, out: Path, err: Path) -> dict:
    cmd = [
        str(OPENCLAW),
        "agent",
        "--agent",
        AGENT,
        "--session-id",
        session_id,
        "--model",
        MODEL,
        "--thinking",
        "high",
        "--timeout",
        str(TIMEOUT_S),
        "--json",
        "--message-file",
        str(prompt),
    ]
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S + 30,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    out.write_text(proc.stdout or "", encoding="utf-8")
    err.write_text(proc.stderr or "", encoding="utf-8")
    model = None
    status = "transport_failed"
    text = ""
    if proc.stdout.strip():
        try:
            doc = json.loads(proc.stdout)
            meta = ((doc.get("result") or {}).get("meta") or {})
            agent_meta = meta.get("agentMeta") or {}
            receipt = agent_meta.get("terminalReceipt") or {}
            effective = receipt.get("effective") or {}
            model = effective.get("model") or agent_meta.get("model")
            payloads = ((doc.get("result") or {}).get("payloads") or [])
            if payloads:
                text = payloads[0].get("text") or ""
            if doc.get("status") == "ok" and proc.returncode == 0:
                status = "ok"
        except json.JSONDecodeError:
            status = "transport_failed"
    return {
        "status": status,
        "exit_code": proc.returncode,
        "effective_model": model,
        "response_chars": len(text),
        "duration_ms": duration_ms,
        "text": text,
    }


def run_trajectory(case_id: str, files: list[str], rep: int) -> dict:
    session_id = f"arena-six-mm3-{case_id[:12]}-r{rep}"
    turns = []
    for idx, name in enumerate(files, start=1):
        prompt = PROMPTS / name
        stem = f"{case_id}-r{rep}-t{idx}"
        row = run_turn(session_id, prompt, RUN / f"transport-{stem}.json", RUN / f"transport-{stem}.stderr.txt")
        row.update({"case": case_id, "rep": rep, "turn": idx, "prompt": name})
        turns.append(row)
        if row["status"] != "ok":
            break
    return {"case": case_id, "rep": rep, "turns": turns}


def main() -> int:
    jobs = [(case, files, rep) for case, files in TRAJECTORIES for rep in (1, 2)]
    summary = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(run_trajectory, case, files, rep) for case, files, rep in jobs]
        for fut in as_completed(futs):
            row = fut.result()
            summary.append(row)
            print(json.dumps({"case": row["case"], "rep": row["rep"], "turns": len(row["turns"])}, sort_keys=True), flush=True)
    summary.sort(key=lambda r: (r["case"], r["rep"]))
    (RUN / "cli-dispatch-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ok_traj = sum(1 for r in summary if r["turns"] and all(t["status"] == "ok" for t in r["turns"]))
    print(json.dumps({"ok_trajectories": ok_traj, "total": len(summary)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
