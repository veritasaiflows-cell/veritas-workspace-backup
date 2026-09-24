"""Run-scoped, zero-retry Surface C dispatcher for Claude Opus 5.5."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RUN = Path(__file__).resolve().parent
PLAN = json.loads((RUN / "dispatch-plan.json").read_text(encoding="utf-8"))
MODEL = "anthropic/claude-opus-5-5"
AGENT = "oxalpha-functional-lab"
TIMEOUT_S = 600
MAX_WORKERS = 4
OPENCLAW = shutil.which("openclaw")


def run_case(case: dict) -> dict:
    iid = case["instance_id"]
    prompt = RUN / case["prompt_txt_path"]
    out = RUN / f"transport-{iid}.json"
    err = RUN / f"transport-{iid}.stderr.txt"
    cmd = [
        str(OPENCLAW), "agent", "--agent", AGENT,
        "--session-id", f"arena-r2-opus55-{iid[:12]}",
        "--model", MODEL, "--thinking", "high", "--timeout", str(TIMEOUT_S),
        "--json", "--message-file", str(prompt),
    ]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S + 30,
            encoding="utf-8", errors="replace", shell=False,
        )
        stdout, stderr, code = proc.stdout or "", proc.stderr or "", proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        code, timed_out = None, True
    duration_ms = int((time.perf_counter() - started) * 1000)
    out.write_text(stdout, encoding="utf-8")
    err.write_text(stderr, encoding="utf-8")
    parsed: dict = {}
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = {}
    result = parsed.get("result") if isinstance(parsed, dict) else {}
    result = result if isinstance(result, dict) else {}
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    agent_meta = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    trace = meta.get("executionTrace") if isinstance(meta.get("executionTrace"), dict) else {}
    payloads = result.get("payloads") if isinstance(result.get("payloads"), list) else []
    text = (payloads[0].get("text") if payloads and isinstance(payloads[0], dict) else "") or ""
    provider = agent_meta.get("provider") or trace.get("winnerProvider")
    effective_model = agent_meta.get("model") or trace.get("winnerModel")
    fallback_used = trace.get("fallbackUsed")
    status = "timeout" if timed_out else ("ok" if code == 0 and parsed.get("status") == "ok" else "transport_failed")
    return {
        "instance_id": iid,
        "family": case.get("family"),
        "requested_model": MODEL,
        "provider": provider,
        "effective_model": effective_model,
        "fallback_used": fallback_used,
        "status": status,
        "exit_code": code,
        "response_chars": len(text),
        "duration_ms": duration_ms,
        "transport_file": out.name,
        "stderr_file": err.name,
    }


def main() -> int:
    if not OPENCLAW:
        raise SystemExit("openclaw_cli_not_found")
    cases = PLAN["cases"]
    summary: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(run_case, case): case["instance_id"] for case in cases}
        for future in as_completed(futures):
            row = future.result()
            summary.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    summary.sort(key=lambda row: row["instance_id"])
    (RUN / "dispatch-execution-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": sum(row["status"] == "ok" for row in summary), "total": len(summary)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
