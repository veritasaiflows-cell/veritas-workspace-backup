import json, glob, os
caps = sorted(glob.glob("state/workflows/*.json"), key=os.path.getmtime, reverse=True)
print("count:", len(caps))
print()
for p in caps[:60]:
    name = os.path.basename(p).replace(".json","")
    try:
        j = json.load(open(p,"r",encoding="utf-8"))
        pri = j.get("priority") or j.get("tier") or j.get("wf_priority") or "?"
        st  = j.get("status") or j.get("workflow_status") or "?"
        phase = j.get("phase") or j.get("current_phase") or ""
        nb = j.get("next_blocker") or j.get("next_action") or ""
        print("%-22s | pri=%-3s | %-12s | %-18s | %s" % (name, str(pri), st, phase, str(nb)[:60]))
    except Exception as e:
        print(name, "err:", str(e)[:60])
