import json, pathlib, sys
sym=sys.argv[1].upper()
files=sys.argv[2:]
for f in files:
    print('---',f)
    p=pathlib.Path(f)
    if not p.exists(): print('missing'); continue
    try: d=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: print('badjson',e); continue
    seen=set()
    def walk(o):
        if isinstance(o, dict):
            if str(o.get('ticker','')).upper()==sym or str(o.get('symbol','')).upper()==sym:
                s=json.dumps(o, sort_keys=True)
                if s not in seen:
                    seen.add(s); print(json.dumps(o, indent=2))
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(d)
