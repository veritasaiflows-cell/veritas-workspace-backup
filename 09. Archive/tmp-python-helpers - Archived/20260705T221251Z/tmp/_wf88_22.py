import json
d = json.load(open("tmp/wf88-os2-control-packet.json","r",encoding="utf-8"))
fl = d.get("finance_learning_loop",{})
print("FINANCE_LEARNING_LOOP keys:")
for k, v in fl.items():
    print(" -", k, "=", v if isinstance(v,(int,float,bool,str)) else type(v).__name__)
print()
print("GRADE_HISTORY_PATH:", fl.get("grade_history_path"))
