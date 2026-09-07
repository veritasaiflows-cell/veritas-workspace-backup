import json
d = json.load(open("tmp/wf88-os2-control-packet.json","r",encoding="utf-8"))

# Pull proposal-ready / owner-decision items
print("=== A. WF67 paper-guardrail row 1 (PH action + monday_open detail) ===")
w67 = d["canonical_action_state"][1].get("next_action",{})
print(json.dumps(w67, indent=2))
print()

print("=== B. Route-contraction packet summary (10 files) ===")
rcp = json.load(open("tmp/wf88-route-contraction-packet.json","r",encoding="utf-8"))
print("keys:", list(rcp.keys())[:20])
if "candidates" in rcp:
    cands = rcp["candidates"]
    print("candidates:", len(cands) if isinstance(cands,list) else "(dict)")
    if isinstance(cands, list):
        for c in cands[:8]:
            if isinstance(c, dict):
                print(" -", c.get("file") or c.get("path") or c.get("name") or json.dumps(c)[:150])
print()

print("=== C. WF88 source-open-residue-classifier (top 10 blockers) ===")
src = json.load(open("tmp/wf88-source-open-residue-classifier.json","r",encoding="utf-8"))
# try to find ticker/residue rows
for k in src.keys():
    print(" key:", k, "type:", type(src[k]).__name__)
arr = src.get("blocker_rows") or src.get("rows") or src.get("residue_classified") or src.get("candidates") or src.get("items")
if isinstance(arr, list):
    print(f"  {len(arr)} items - first 8:")
    for x in arr[:8]:
        if isinstance(x, dict):
            t = x.get("ticker") or x.get("name") or x.get("source") or x.get("id") or "?"
            bk = x.get("blocker") or x.get("reason") or x.get("category") or x.get("class") or "?"
            print(f"   - {t}: {bk}")
