import json
from pathlib import Path

run = Path(__file__).resolve().parent
plan = json.loads((run / "dispatch-plan.json").read_text(encoding="utf-8"))
timeout_id = "75c25de61ca18168d846f86e84e40de6b807213f547029876cb6ca2bcc99c2b4"
responses = {}
receipts = {}
summary = []
for case in plan["cases"]:
    iid = case["instance_id"]
    p = run / f"transport-{iid}.json"
    if iid == timeout_id and not p.exists():
        responses[iid] = ""
        receipts[iid] = {
            "status": "timeout",
            "requested": {
                "provider": "ollama-cloud",
                "model": "glm-5.3-flash:cloud",
            },
            "effective": None,
            "rerouted": False,
            "fallback_used": False,
            "successful_tool_names": [],
            "duration_ms": 630000,
            "response_chars": 0,
            "note": "subprocess.TimeoutExpired after 630s; recorded empty fail-closed",
        }
        summary.append(
            {
                "instance_id": iid,
                "family": case.get("family"),
                "status": "timeout",
                "exit_code": None,
                "effective_model": None,
                "response_chars": 0,
                "duration_ms": 630000,
            }
        )
        continue
    doc = json.loads(p.read_text(encoding="utf-8"))
    payloads = ((doc.get("result") or {}).get("payloads") or [])
    text = (payloads[0].get("text") if payloads else "") or ""
    responses[iid] = text
    meta = ((doc.get("result") or {}).get("meta") or {})
    am = meta.get("agentMeta") or {}
    rec = am.get("terminalReceipt") or {}
    receipts[iid] = {
        "status": doc.get("status"),
        "requested": rec.get("requested") or {},
        "effective": rec.get("effective") or {},
        "rerouted": rec.get("rerouted"),
        "run_id": rec.get("runId") or doc.get("runId"),
        "session_id": rec.get("sessionId") or am.get("sessionId"),
        "provider": am.get("provider"),
        "model": am.get("model"),
        "successful_tool_names": rec.get("successfulToolNames") or [],
        "usage": am.get("usage") or {},
        "duration_ms": meta.get("durationMs"),
        "fallback_used": ((meta.get("executionTrace") or {}).get("fallbackUsed")),
        "response_chars": len(text),
    }
    summary.append(
        {
            "instance_id": iid,
            "family": case.get("family"),
            "status": "ok" if doc.get("status") == "ok" else "transport_failed",
            "exit_code": 0,
            "effective_model": (rec.get("effective") or {}).get("model"),
            "response_chars": len(text),
            "duration_ms": meta.get("durationMs"),
        }
    )
(run / "responses.partial.json").write_text(
    json.dumps(responses, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
(run / "transport-receipts.json").write_text(
    json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
summary.sort(key=lambda r: r["instance_id"])
(run / "dispatch-execution-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print("n", len(responses), "empty", sum(1 for v in responses.values() if not v.strip()))
print(
    "models",
    sorted(
        {
            (r.get("effective") or {}).get("provider"),
            (r.get("effective") or {}).get("model"),
        }
        for r in receipts.values()
        if r.get("effective")
    ),
)
