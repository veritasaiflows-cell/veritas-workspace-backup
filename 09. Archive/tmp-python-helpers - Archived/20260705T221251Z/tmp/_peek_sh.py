import json
# Check the actual durable v2 ledger path from p
import os
p = json.load(open("tmp/wf55-outcome-ledger-preview.json","r",encoding="utf-8"))
print("Preview keys:")
for k,v in p.items():
    print(" -", k, "=", type(v).__name__)

# Try the durable path it referenced (data/state-history/outcome-ledger-v2.jsonl)
dpath = "data/state-history/outcome-ledger-v2.jsonl"
print()
print("path exists:", os.path.exists(dpath))
print()
if os.path.exists(dpath):
    lines = [l for l in open(dpath,"r",encoding="utf-8").read().splitlines() if l.strip()]
    print("row count:", len(lines))
    for i, l in enumerate(lines[:3]):
        j = json.loads(l)
        print(json.dumps(j, indent=2)[:800])
        print("---")
