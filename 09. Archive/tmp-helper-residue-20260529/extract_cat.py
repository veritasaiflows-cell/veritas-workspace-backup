import json, pathlib
files=['tmp/fundamental-metrics-current.json','tmp/technical-refresh.json','tmp/deployment-check.json','tmp/analyst-consensus-current.json','tmp/band-proposals.json','tmp/positioning-ranking.json','tmp/regime-scores.json']
for f in files:
    print('---',f)
    p=pathlib.Path(f)
    if not p.exists():
        print('missing'); continue
    d=json.loads(p.read_text(encoding='utf-8'))
    seen=set()
    def rows(o):
        if isinstance(o, dict):
            if str(o.get('ticker','')).upper()=='CAT':
                s=json.dumps(o, sort_keys=True)
                if s not in seen:
                    seen.add(s); print(json.dumps(o, indent=2))
            for v in o.values(): rows(v)
        elif isinstance(o, list):
            for v in o: rows(v)
    rows(d)
