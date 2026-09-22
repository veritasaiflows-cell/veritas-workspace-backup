"""Run-scoped overlay-r2 dispatcher: invokes `openclaw agent` CLI per case.

GLM 5.3 Flash full-chain Surface C. 4-wide waves per lane cap. Does not flip the canonical spend gate.
"""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RUN = Path(__file__).resolve().parent
PLAN = json.loads((RUN / "dispatch-plan.json").read_text(encoding="utf-8"))
MODEL = "ollama-cloud/glm-5.3-flash:cloud"
AGENT = "oxalpha-functional-lab"
TIMEOUT_S = 600
OPENCLAW = Path(r"C:\Users\Veritas\AppData\Roaming\npm\openclaw.cmd")


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
        f"arena-r2-glmchain-{iid[:12]}",
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
    if proc.returncode == 0 and proc.stdout.strip():
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
            if doc.get("status") == "ok":
                status = "ok"
        except json.JSONDecodeError:
            status = "transport_failed"
    return {
        "instance_id": iid,
        "family": case.get("family"),
        "status": status,
        "exit_code": proc.returncode,
        "effective_model": model,
        "response_chars": len(text),
        "duration_ms": duration_ms,
    }


def main() -> int:
    cases = PLAN["cases"]
    summary = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(run_case, c): c["instance_id"] for c in cases}
        for fut in as_completed(futs):
            row = fut.result()
            summary.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    summary.sort(key=lambda r: r["instance_id"])
    (RUN / "dispatch-execution-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ok = sum(1 for r in summary if r["status"] == "ok")
    print(json.dumps({"ok": ok, "total": len(summary)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
