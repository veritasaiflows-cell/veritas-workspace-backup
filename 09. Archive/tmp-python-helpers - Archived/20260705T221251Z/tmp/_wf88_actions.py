import json
d = json.load(open("tmp/wf88-os2-control-packet.json","r",encoding="utf-8"))
cas = d.get("canonical_action_state",[])
print("CANONICAL_ACTION_STATE count:", len(cas))
print()
for i, a in enumerate(cas):
    if isinstance(a, dict):
        keys = list(a.keys())
        print(f"=== row {i} ({len(keys)} keys) ===")
        # Show top-level + first nested
        for k, v in a.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                print(f"  {k}: {v}")
            elif isinstance(v, list):
                if v and isinstance(v[0], dict):
                    inner_keys = list(v[0].keys())[:6]
                    print(f"  {k}: list[{len(v)}] of dict (first row keys={inner_keys})")
                else:
                    print(f"  {k}: list[{len(v)}] {str(v)[:120]}")
            elif isinstance(v, dict):
                inner = list(v.keys())[:6]
                print(f"  {k}: dict(keys={inner})")
            else:
                print(f"  {k}: {type(v).__name__}")
        print()
