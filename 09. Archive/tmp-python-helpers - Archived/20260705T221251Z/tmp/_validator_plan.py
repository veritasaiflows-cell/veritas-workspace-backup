import json

d = json.load(open("tmp/validator-bundle-router.json", encoding="utf-8"))
plan = d.get("plan", [])
print(f"Plan commands: {len(plan)}")
cats = {}
for c in plan:
    cat = c.get("category", "?")
    cats[cat] = cats.get(cat, 0) + 1
for k, v in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== FIRST 40 COMMANDS ===")
for c in plan[:40]:
    print(f'{c.get("category","?")} | {c.get("command","?")}')
