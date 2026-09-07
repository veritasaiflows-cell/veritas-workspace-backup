import json, pathlib
for f in ['tmp/sector-expansion-board.json','tmp/market-state.json','tmp/breadth-state.json','tmp/sector-correlation-check.json','tmp/ticker-monitoring-performance.json']:
    p=pathlib.Path(f)
    print('\n---', f, 'exists=', p.exists())
    if p.exists():
        try:
            d=json.loads(p.read_text(encoding='utf-8'))
            for k in ['status','generated_at_utc','window','market_data_as_of','as_of','summary','warnings','source_confidence','confidence']:
                if k in d:
                    v=d[k]
                    if k=='summary' and isinstance(v,dict):
                        print(k, {kk:v.get(kk) for kk in list(v)[:10]})
                    else:
                        print(k, v)
        except Exception as e:
            print('err', e)
