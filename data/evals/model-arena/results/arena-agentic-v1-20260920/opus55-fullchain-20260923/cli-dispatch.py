"""Surface B pre-overlay, run-scoped, zero-retry CLI dispatch; do not use elsewhere."""
import json
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RUN = Path(__file__).resolve().parent
MODEL = "anthropic/claude-opus-5-5"
EFFECTIVE = "claude-opus-5-5"
AGENT = "oxalpha-functional-lab"
TIMEOUT = 600
CLI = shutil.which("openclaw")


def case_call(case):
    iid = case["instance_id"]
    prompt = RUN / "prompts" / (iid + ".txt")
    cmd = [CLI, "agent", "--agent", AGENT, "--session-id", "arena-b-opus55-" + iid[:12],
           "--model", MODEL, "--thinking", "high", "--timeout", str(TIMEOUT),
           "--json", "--message-file", str(prompt)]
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 30,
                              encoding="utf-8", errors="replace", shell=False)
        raw, stderr, code = proc.stdout or "", proc.stderr or "", proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        code, timed_out = None, True
    out = RUN / ("transport-" + iid + ".json")
    err = RUN / ("transport-" + iid + ".stderr.txt")
    out.write_text(raw, encoding="utf-8")
    err.write_text(stderr, encoding="utf-8")
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        doc = {}
    result = doc.get("result") if isinstance(doc, dict) else {}
    result = result if isinstance(result, dict) else {}
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    agent = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    trace = meta.get("executionTrace") if isinstance(meta.get("executionTrace"), dict) else {}
    payloads = result.get("payloads") if isinstance(result.get("payloads"), list) else []
    text = payloads[0].get("text") if payloads and isinstance(payloads[0], dict) else ""
    text = text if isinstance(text, str) else ""
    provider = agent.get("provider") or trace.get("winnerProvider")
    effective = agent.get("model") or trace.get("winnerModel")
    fallback = trace.get("fallbackUsed")
    final_prompt = meta.get("finalPromptText")
    expected = prompt.read_text(encoding="utf-8").replace("\r\n", "\n")
    actual = final_prompt.replace("\r\n", "\n") if isinstance(final_prompt, str) else ""
    # Gateway prepends a timestamp on the SAME line and strips the final newline.
    intact = bool(actual and "] " in actual and actual.split("] ", 1)[1].rstrip("\n") == expected.rstrip("\n"))
    issues = []
    if timed_out: issues.append("timeout")
    if code != 0: issues.append("cli_exit_nonzero")
    if not isinstance(doc, dict) or doc.get("status") != "ok": issues.append("cli_status_not_ok")
    if provider != "claude-cli" or effective != EFFECTIVE: issues.append("effective_model_mismatch")
    if fallback is not False or len(trace.get("attempts") or []) != 1: issues.append("fallback_or_multiple_attempts")
    if not text.strip(): issues.append("empty_response")
    if not intact: issues.append("prompt_delivery_unverified")
    return {"instance_id": iid, "family": case["family"], "requested_model": MODEL,
            "provider": provider, "effective_model": effective, "fallback_used": fallback,
            "exit_code": code, "response_chars": len(text), "prompt_intact": intact,
            "status": "ok" if not issues else "invalid_transport", "issues": issues,
            "duration_ms": int((time.perf_counter()-started)*1000),
            "transport_file": out.name, "stderr_file": err.name}


def main():
    auth = json.loads((RUN / "authorization.json").read_text(encoding="utf-8"))
    if not (auth.get("dispatch_ready") is True and auth.get("overlay_version") == "pre-overlay"
            and auth.get("scope") == {"cases":12,"models":[MODEL],"reps":1,"retries":0}
            and auth.get("authorized_at") == "2026-09-23T20:17:00-07:00"):
        raise SystemExit("authorization_mismatch")
    if not CLI: raise SystemExit("openclaw_cli_not_found")
    txts = sorted((RUN / "prompts").glob("*.txt"))
    jsons = sorted((RUN / "prompts").glob("*.json"))
    if len(txts) != 12 or len(jsons) != 12 or {p.stem for p in txts} != {p.stem for p in jsons}:
        raise SystemExit("prompt_set_mismatch")
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in jsons]
    if any(c["instance_id"] != p.stem for c, p in zip(cases, jsons)):
        raise SystemExit("prompt_identity_mismatch")
    rows = []
    prior = RUN / "dispatch-execution-summary.json"
    if prior.exists():
        rows = json.loads(prior.read_text(encoding="utf-8"))
        if len(rows) != 4 or {r["instance_id"] for r in rows} != {c["instance_id"] for c in cases[:4]}:
            raise SystemExit("unexpected_prior_dispatch_zero_retry")
        for row in rows:
            iid = row["instance_id"]
            doc = json.loads((RUN / row["transport_file"]).read_text(encoding="utf-8"))
            meta = doc["result"]["meta"]
            prompt = (RUN / "prompts" / (iid + ".txt")).read_text(encoding="utf-8").replace("\r\n", "\n")
            observed = meta["finalPromptText"].replace("\r\n", "\n")
            intact = "] " in observed and observed.split("] ", 1)[1].rstrip("\n") == prompt.rstrip("\n")
            if not (row["issues"] == ["prompt_delivery_unverified"] and intact and row["exit_code"] == 0
                    and doc["status"] == "ok" and row["requested_model"] == MODEL
                    and row["effective_model"] == EFFECTIVE and row["fallback_used"] is False
                    and row["provider"] == "claude-cli" and row["response_chars"] > 0
                    and len(meta["executionTrace"]["attempts"]) == 1):
                raise SystemExit("invalid_existing_transport_stop_zero_retry:" + iid)
            row.update(issues=[], prompt_intact=True, status="ok")
        prior.write_text(json.dumps(sorted(rows, key=lambda r:r["instance_id"]), indent=2, sort_keys=True)+"\n", encoding="utf-8")
        print("Revalidated existing four receipts; no replay", flush=True)
    elif any((RUN / ("transport-" + c["instance_id"] + ".json")).exists() for c in cases):
        raise SystemExit("existing_transport_without_summary_zero_retry")
    if any((RUN / ("transport-" + c["instance_id"] + ".json")).exists() for c in cases[len(rows):]):
        raise SystemExit("pending_case_has_existing_transport_zero_retry")
    for start in range(len(rows), len(cases), 4):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(case_call, c): c["instance_id"] for c in cases[start:start+4]}
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
        (RUN / "dispatch-execution-summary.json").write_text(
            json.dumps(sorted(rows, key=lambda r: r["instance_id"]), indent=2, sort_keys=True)+"\n", encoding="utf-8")
        if any(row["status"] != "ok" for row in rows):
            print("STOP: invalid transport; remaining cases not submitted", flush=True)
            return 2
    print(json.dumps({"ok": len(rows), "total": len(cases)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
