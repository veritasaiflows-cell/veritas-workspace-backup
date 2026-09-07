import json
d = json.load(open("tmp/wf88-os2-control-packet.json","r",encoding="utf-8"))
print("TOP-LEVEL KEYS:")
for k in sorted(d.keys()):
    print(" -", k)
print()
print("ACTION / PROPOSAL / NEXT KEYS DETAIL:")
for k, v in d.items():
    if isinstance(v, list) and v and any(isinstance(x, dict) for x in v[:3]):
        print("LIST-KEY:", k, "len=", len(v))
    elif isinstance(v, dict) and v:
        sub_keys = list(v.keys())[:8]
        print("DICT-KEY:", k, "sub_keys=", sub_keys)
