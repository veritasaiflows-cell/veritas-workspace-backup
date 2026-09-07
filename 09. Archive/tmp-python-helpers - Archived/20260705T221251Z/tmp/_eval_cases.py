import json
with open(r'C:\Users\Veritas\.openclaw\workspace\data\wf74-learning-loop-evals\cases.json') as f:
    d = json.load(f)
for c in d.get('cases', []):
    print(f"{c.get('id','?')}: {c.get('state','?')} — {c.get('title','?')}")
