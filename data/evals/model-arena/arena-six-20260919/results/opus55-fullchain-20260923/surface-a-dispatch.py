"""Run-scoped Surface A dispatcher: sequential user turns, four trajectories per wave."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

RUN = Path(__file__).resolve().parent
ARENA = RUN.parents[1]
ENVELOPE = json.loads((ARENA / "envelope.json").read_text(encoding="utf-8"))
MODEL = "anthropic/claude-opus-5-5"
EFFECTIVE_MODEL = "claude-opus-5-5"
AGENT = "oxalpha-lab"
TIMEOUT_S = 600
MAX_WORKERS = 4
STAGGER_S = 60
PROMPT_ROOT = RUN / "candidate-mount" / "arena-six-inputs-20260919" / "prompts"
NATIVE_WORKSPACE = Path(r"C:\Users\Veritas\.openclaw\workspaces\oxalpha-lab")
NATIVE_LOG_ROOT = Path(r"C:\Users\Veritas\.claude\projects\C--Users-Veritas--openclaw-workspaces-oxalpha-lab")
OPENCLAW = shutil.which("openclaw")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def native_trace(session_id: str) -> dict[str, Any]:
    """Extract only user provenance and tool names/relative paths from native JSONL."""
    path = NATIVE_LOG_ROOT / f"{session_id}.jsonl"
    result: dict[str, Any] = {
        "native_log": path.name,
        "native_log_found": path.exists(),
        "user_role": None,
        "user_type": None,
        "entrypoint": None,
        "user_content_sha256": None,
        "tool_calls": [],
    }
    if not path.exists():
        return result
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "user":
            message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, str):
                result["user_content_sha256"] = sha256_text(content)
            result["user_role"] = message.get("role")
            result["user_type"] = obj.get("userType")
            result["entrypoint"] = obj.get("entrypoint")
        if obj.get("type") != "assistant":
            continue
        message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            raw_input = item.get("input") if isinstance(item.get("input"), dict) else {}
            raw_path = raw_input.get("file_path") or raw_input.get("path") or raw_input.get("target_file")
            normalized_path = None
            if isinstance(raw_path, str):
                try:
                    rel = Path(raw_path).resolve().relative_to(NATIVE_WORKSPACE.resolve())
                    normalized_path = rel.as_posix()
                    prefix = "arena-six-inputs-20260919/"
                    if normalized_path.startswith(prefix):
                        normalized_path = normalized_path[len(prefix):]
                except (OSError, ValueError):
                    normalized_path = "outside_workspace"
            result["tool_calls"].append({"name": item.get("name"), "path": normalized_path})
    return result


def call_turn(case_id: str, rep: int, turn_number: int, prompt_rel: str) -> dict[str, Any]:
    prompt_path = PROMPT_ROOT / Path(prompt_rel).name
    expected = prompt_path.read_text(encoding="utf-8")
    stem = f"{case_id}-r{rep}-t{turn_number}"
    out_path = RUN / f"transport-{stem}.json"
    err_path = RUN / f"transport-{stem}.stderr.txt"
    session_key = f"arena-a-opus55-{case_id.lower().replace('_', '-')}-r{rep}"
    cmd = [
        str(OPENCLAW), "agent", "--agent", AGENT, "--session-key", session_key,
        "--model", MODEL, "--thinking", "high", "--timeout", str(TIMEOUT_S),
        "--json", "--message-file", str(prompt_path),
    ]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_S + 30, shell=False,
        )
        stdout, stderr, code, timeout = proc.stdout or "", proc.stderr or "", proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        code, timeout = None, True
    duration_ms = int((time.perf_counter() - started) * 1000)
    out_path.write_text(stdout, encoding="utf-8")
    err_path.write_text(stderr, encoding="utf-8")
    try:
        doc = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        doc = {}
    result = doc.get("result") if isinstance(doc, dict) else {}
    result = result if isinstance(result, dict) else {}
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    payloads = result.get("payloads") if isinstance(result.get("payloads"), list) else []
    response_text = (payloads[0].get("text") if payloads and isinstance(payloads[0], dict) else "") or ""
    system_report = meta.get("systemPromptReport") if isinstance(meta.get("systemPromptReport"), dict) else {}
    trace = meta.get("executionTrace") if isinstance(meta.get("executionTrace"), dict) else {}
    agent_meta = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    native_session_id = agent_meta.get("sessionId")
    native = native_trace(str(native_session_id)) if isinstance(native_session_id, str) else native_trace("")
    final_prompt = meta.get("finalPromptText") if isinstance(meta.get("finalPromptText"), str) else ""
    payload_suffix_exact = bool(final_prompt) and final_prompt.endswith(expected)
    expected_sha = sha256_text(expected)
    expected_tool_calls = 0 if case_id != "T4-multihop-read-recovery" else None
    tool_calls = native.get("tool_calls") or []
    tool_violation = expected_tool_calls == 0 and len(tool_calls) != 0
    exact_model = (
        str(agent_meta.get("model") or system_report.get("model") or "") == EFFECTIVE_MODEL
        and str(agent_meta.get("provider") or system_report.get("provider") or "") == "claude-cli"
        and trace.get("fallbackUsed") is False
    )
    user_provenance = (
        native.get("user_role") == "user"
        and native.get("user_type") == "external"
        and native.get("entrypoint") == "sdk-cli"
    )
    status = "timeout" if timeout else ("ok" if code == 0 and doc.get("status") == "ok" else "transport_failed")
    if status == "ok" and (not exact_model or not payload_suffix_exact or not user_provenance or tool_violation):
        status = "transport_invalid"
    return {
        "turn": turn_number,
        "response_text": response_text,
        "operational_status": status,
        "transport": {
            "requested_model": MODEL,
            "provider": agent_meta.get("provider") or system_report.get("provider"),
            "effective_model": agent_meta.get("model") or system_report.get("model"),
            "fallback_used": trace.get("fallbackUsed"),
            "session_key": session_key,
            "native_session_id": native_session_id,
            "exit_code": code,
            "duration_ms": duration_ms,
            "expected_prompt_sha256": expected_sha,
            "final_prompt_sha256": sha256_text(final_prompt) if final_prompt else None,
            "delivery_match": "timestamp_wrapper_suffix_exact" if payload_suffix_exact else "mismatch",
            "stored_user_provenance": {
                "role": native.get("user_role"),
                "user_type": native.get("user_type"),
                "entrypoint": native.get("entrypoint"),
                "user_content_sha256": native.get("user_content_sha256"),
            },
            "tool_calls": tool_calls,
            "tool_violation": tool_violation,
            "raw_transport_file": out_path.name,
            "stderr_file": err_path.name,
        },
    }


def run_trajectory(task: dict[str, Any], rep: int) -> dict[str, Any]:
    case_id = str(task["id"])
    turns: list[dict[str, Any]] = []
    for number, prompt_rel in enumerate(task["turns"], start=1):
        turn = call_turn(case_id, rep, number, str(prompt_rel))
        turns.append(turn)
        if turn["operational_status"] != "ok":
            break
    all_tool_calls = [call for turn in turns for call in turn["transport"]["tool_calls"]]
    trajectory_status = "ok" if len(turns) == len(task["turns"]) and all(t["operational_status"] == "ok" for t in turns) else "operational_incomplete"
    return {
        "case": case_id,
        "rep": rep,
        "operational_status": trajectory_status,
        "tool_trace": [call.get("path") for call in all_tool_calls if call.get("name") == "Read" and call.get("path")],
        "turns": turns,
    }


def main() -> int:
    if not OPENCLAW:
        raise SystemExit("openclaw_cli_not_found")
    tasks = ENVELOPE["tasks"]
    waves = [
        [(tasks[0], 1), (tasks[0], 2), (tasks[1], 1), (tasks[1], 2)],
        [(tasks[2], 1), (tasks[2], 2), (tasks[3], 1), (tasks[3], 2)],
        [(tasks[4], 1), (tasks[4], 2), (tasks[5], 1), (tasks[5], 2)],
    ]
    trajectories: list[dict[str, Any]] = []
    for wave_index, wave in enumerate(waves, start=1):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(run_trajectory, task, rep): (task["id"], rep) for task, rep in wave}
            for future in as_completed(futures):
                row = future.result()
                trajectories.append(row)
                print(json.dumps({"wave": wave_index, "case": row["case"], "rep": row["rep"], "status": row["operational_status"]}, sort_keys=True), flush=True)
        if wave_index < len(waves):
            time.sleep(STAGGER_S)
    trajectories.sort(key=lambda row: (row["case"], row["rep"]))
    output = {
        "model": MODEL,
        "run": "opus55-fullchain-20260923",
        "operation": "Claude Opus 5.5 Surface A, Gateway CLI external user turns, three four-trajectory waves",
        "retry_policy": "zero retries",
        "trajectories": trajectories,
    }
    (RUN / "A-responses.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipts = [
        {"case": row["case"], "rep": row["rep"], "turn": turn["turn"], **turn["transport"]}
        for row in trajectories for turn in row["turns"]
    ]
    (RUN / "transport-receipts.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"trajectories": len(trajectories), "complete": sum(r["operational_status"] == "ok" for r in trajectories)}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
