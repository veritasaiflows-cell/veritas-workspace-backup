"""Dispatch only the two missing T6 overlay-r2 cases for MiniMax M3."""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RUN = Path(__file__).resolve().parent
PLAN = json.loads((RUN / "dispatch-plan.json").read_text(encoding="utf-8"))
MODEL = "ollama-cloud/minimax-m3:cloud"
AGENT = "oxalpha-functional-lab"
TIMEOUT_S = 600
OPENCLAW = Path(r"C:\Users\Veritas\AppData\Roaming\npm\openclaw.cmd")
T6_IDS = {
    "75c25de61ca18168d846f86e84e40de6b807213f547029876cb6ca2bcc99c2b4",
    "ad2161157921538089853178cdb459bbaed40f96fa77329a69e4be635c5af0bc",
}


def run_case(case: dict) -> dict:
    iid = case["instance_id"]
    prompt = RUN / case["prompt_txt_path"]
    out = RUN / f"transport-{iid}.json"
    err = RUN / f"transport-{iid}.stderr.txt"
    cmd = [
        str(OPENCLAW),
        "agent",
        "--agent",
        AGENT,
        "--session-id",
        f"arena-r2-mm3-t6-{iid[:12]}",
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
    if proc.stdout.strip():
        try:
            doc = json.loads(proc.stdout)
            meta = ((doc.get("result") or {}).get("meta") or {})
            agent_meta = meta.get("agentMeta") or {}
            receipt = agent_meta.get("terminalReceipt") or {}
            effective = receipt.get("effective") or {}
            model = effective.get("model") or agent_meta.get("model")
            if doc.get("status") == "ok" and proc.returncode == 0:
                status = "ok"
            elif doc.get("status"):
                status = str(doc.get("status"))
        except json.JSONDecodeError:
            status = "transport_failed"
    row = {
        "instance_id": iid,
        "family": case.get("family"),
        "status": status,
        "exit_code": proc.returncode,
        "effective_model": model,
        "duration_ms": duration_ms,
    }
    print(json.dumps(row, sort_keys=True), flush=True)
    return row


def main() -> int:
    cases = [c for c in PLAN["cases"] if c["instance_id"] in T6_IDS]
    summary = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(run_case, c) for c in cases]
        for fut in as_completed(futs):
            summary.append(fut.result())
    (RUN / "t6-dispatch-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
