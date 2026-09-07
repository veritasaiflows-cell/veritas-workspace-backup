import json

p = json.load(open("tmp/wf55-outcome-ledger-preview.json","r",encoding="utf-8"))
rows = p.get("preview_rows", [])
print("total preview rows:", len(rows))
print()
# Look at first row to learn structure
print("FIRST ROW SCHEMA:")
print(json.dumps(rows[0], indent=2)[:2500])
