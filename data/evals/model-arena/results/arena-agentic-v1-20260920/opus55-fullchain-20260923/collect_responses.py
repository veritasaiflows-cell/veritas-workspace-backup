"""Collect only fully verified Surface B receipts, with no replay or transport repair."""
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
rows = json.loads((RUN / "dispatch-execution-summary.json").read_text(encoding="utf-8"))
expected = {p.stem for p in (RUN / "prompts").glob("*.json")}
if len(rows) != 12 or {r["instance_id"] for r in rows} != expected:
    raise SystemExit("incomplete_dispatch: no collection")
responses = {}
receipts = {}
for row in rows:
    iid = row["instance_id"]
    raw = RUN / row["transport_file"]
    err = RUN / row["stderr_file"]
    doc = json.loads(raw.read_text(encoding="utf-8"))
    result = doc["result"]
    meta = result["meta"]
    trace = meta["executionTrace"]
    agent = meta["agentMeta"]
    text = result["payloads"][0]["text"]
    prompt = (RUN / "prompts" / (iid + ".txt")).read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    observed = meta["finalPromptText"].replace("\r\n", "\n")
    intact = "] " in observed and observed.split("] ", 1)[1].rstrip("\n") == prompt
    if not (row["status"] == "ok" and row["exit_code"] == 0 and row["prompt_intact"] is True
            and row["issues"] == [] and doc["status"] == "ok" and intact
            and row["requested_model"] == "anthropic/claude-opus-5-5"
            and agent["model"] == trace["winnerModel"] == row["effective_model"] == "claude-opus-5-5"
            and agent["provider"] == trace["winnerProvider"] == row["provider"] == "claude-cli"
            and trace["fallbackUsed"] is False and len(trace["attempts"]) == 1
            and isinstance(text, str) and text.strip() and len(text) == row["response_chars"]
            and err.exists()):
        raise SystemExit("invalid_transport_stop_zero_retry:" + iid)
    responses[iid] = text
    receipts[iid] = {"requested_model": row["requested_model"], "effective_model": row["effective_model"],
                     "provider": row["provider"], "fallback_used": False, "exit_code": 0,
                     "prompt_intact": True, "transport_file": raw.name, "stderr_file": err.name,
                     "response_chars": len(text)}
(RUN / "responses.json").write_text(json.dumps(responses, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(RUN / "transport-receipts.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"answered": len(responses), "valid_transport": len(receipts), "fallback_used": False}))
