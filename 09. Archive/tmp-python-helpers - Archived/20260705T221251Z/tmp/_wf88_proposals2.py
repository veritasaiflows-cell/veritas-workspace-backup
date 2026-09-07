import json

rcp = json.load(open("tmp/wf88-route-contraction-packet.json","r",encoding="utf-8"))
print("=== Route-contraction files (10) ===")
files = rcp.get("route_contraction_files", [])
print("count:", len(files))
for i, f in enumerate(files[:12]):
    if isinstance(f, dict):
        print(f"  [{i}]", list(f.keys())[:8])
        for k,v in f.items():
            if isinstance(v,(str,int,bool)):
                print(f"      {k}: {v}")
            elif isinstance(v,list):
                print(f"      {k}: list[{len(v)}] first={str(v[0])[:120]}" if v else f"      {k}: empty")

print()
print("=== summary ===")
print(json.dumps(rcp.get("summary",{}), indent=2)[:1500])
print()

# Source-open rows detail
src = json.load(open("tmp/wf88-source-open-residue-classifier.json","r",encoding="utf-8"))
print("=== Source-open rows (key fields) ===")
for r in src.get("rows",[])[:8]:
    if isinstance(r, dict):
        keys = list(r.keys())
        print(f"row: keys={keys[:8]}")
        for k in keys[:10]:
            v = r[k]
            if isinstance(v,(str,int,float,bool)):
                print(f"  {k}: {v}")
            elif isinstance(v, list):
                print(f"  {k}: list[{len(v)}] first={str(v[0])[:160]}" if v else f"  {k}: empty")
        print()
