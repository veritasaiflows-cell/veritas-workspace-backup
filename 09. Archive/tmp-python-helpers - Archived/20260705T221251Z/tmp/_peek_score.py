import json, collections
# Search for "scoreable" definition in the producer script
with open("scripts/wf55_outcome_ledger_v2.py","r",encoding="utf-8") as f:
    text = f.read()
# Find all lines mentioning "scoreable"
import re
for m in re.finditer(r"scoreable", text, flags=re.IGNORECASE):
    start = max(0, m.start() - 200)
    end = min(len(text), m.end() + 250)
    snip = text[start:end]
    print("===", m.group(), "@", m.start(), "===")
    print(snip)
    print()
