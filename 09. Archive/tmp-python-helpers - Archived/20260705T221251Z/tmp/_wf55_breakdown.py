import json

p = json.load(open("tmp/wf55-outcome-ledger-preview.json","r",encoding="utf-8"))

# Look for shadow decisions / scoreable decisions
print("KEYS:", list(p.keys()))
print()

# show structure
counts = p.get("scoreable_decision_breakdown") or p.get("scoreable_decisions") or p.get("shadow_decisions")
recs = p.get("recommendation_tracking", {})
sd = p.get("scoreable_decision_breakdown") or p.get("shadow_scoreable") or {}
for k, v in p.items():
    if isinstance(v, list) and v and isinstance(v[0], dict):
        first = v[0]
        keys = list(first.keys())
        print(f"LIST {k} (len={len(v)}) keys={keys[:8]}")
        for x in v[:25]:
            t = x.get("ticker") or x.get("name") or x.get("id") or x.get("decision_id") or "?"
            sc = x.get("scoreable") or x.get("score") or x.get("is_scoreable") or x.get("state") or x.get("scoreable_status") or "?"
            pr = x.get("primary_state") or x.get("decision_state") or x.get("decision") or "?"
            cat = x.get("category") or x.get("classification") or x.get("action") or "?"
            print(f"   - {t:<8} | scoreable={sc} | state={pr} | cat={cat}")
