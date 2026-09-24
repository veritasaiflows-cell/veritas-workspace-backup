"""Run-scoped collector for the Opus 5.5 Surface C CLI take.

Reads the twelve transport-*.json files this run actually produced, extracts the
candidate response text for each frozen instance_id, and writes responses.json
plus a transport receipt map. A missing or failed transport is recorded as an
empty string (fail-closed), never retried and never invented.
"""
import datetime
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
PLAN = json.loads((RUN / "dispatch-plan.json").read_text(encoding="utf-8"))

responses: dict[str, str] = {}
receipts: dict[str, dict] = {}
summary: list[dict] = []

for case in PLAN["cases"]:
    iid = case["instance_id"]
    tpath = RUN / f"transport-{iid}.json"
    if not tpath.exists():
        responses[iid] = ""
        receipts[iid] = {"status": "missing_transport", "effective": None,
                         "fallback_used": None, "response_chars": 0}
        summary.append({"instance_id": iid, "family": case.get("family"),
                        "status": "missing_transport", "response_chars": 0})
        continue
    doc = json.loads(tpath.read_text(encoding="utf-8"))
    result = doc.get("result") if isinstance(doc.get("result"), dict) else {}
    payloads = result.get("payloads") if isinstance(result.get("payloads"), list) else []
    text = ""
    if payloads and isinstance(payloads[0], dict):
        text = payloads[0].get("text") or ""
    responses[iid] = text
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    agent_meta = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    trace = meta.get("executionTrace") if isinstance(meta.get("executionTrace"), dict) else {}
    receipts[iid] = {
        "status": doc.get("status"),
        "provider": agent_meta.get("provider") or trace.get("winnerProvider"),
        "effective_model": agent_meta.get("model") or trace.get("winnerModel"),
        "requested_model": PLAN.get("model"),
        "model_applied": bool((agent_meta.get("model") or trace.get("winnerModel")) == PLAN.get("model")),
        "fallback_used": trace.get("fallbackUsed"),
        "reroutes": [a for a in (trace.get("attempts") or []) if isinstance(a, dict)],
        "response_chars": len(text),
    }
    summary.append({
        "instance_id": iid,
        "family": case.get("family"),
        "status": doc.get("status"),
        "effective_model": receipts[iid]["effective_model"],
        "fallback_used": receipts[iid]["fallback_used"],
        "response_chars": len(text),
    })

(RUN / "responses.json").write_text(
    json.dumps(responses, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(RUN / "transport-receipts.json").write_text(
    json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
summary.sort(key=lambda r: r["instance_id"])
(RUN / "dispatch-execution-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

print(json.dumps({
    "collected_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "n": len(responses),
    "empty": sum(1 for v in responses.values() if not v.strip()),
    "effective_models": sorted({r.get("effective_model") for r in receipts.values()}),
    "fallback_used_values": sorted({str(r.get("fallback_used")) for r in receipts.values()}),
}, indent=2))
