import json

with open(r'C:\Users\Veritas\.openclaw\workspace\tmp\vector-memory-index.json') as f:
    d = json.load(f)
s = d.get('summary', d)
if isinstance(s, dict):
    print(json.dumps(s, indent=2)[:2000])
else:
    print(str(s)[:2000])

print("\n---CHECKPOINT---")
with open(r'C:\Users\Veritas\.openclaw\workspace\tmp\wf74-wf88-checkpointed-execution.json') as f:
    d = json.load(f)
s = d.get('summary', d)
if isinstance(s, dict):
    print(json.dumps(s, indent=2)[:2000])
else:
    print(str(s)[:2000])
