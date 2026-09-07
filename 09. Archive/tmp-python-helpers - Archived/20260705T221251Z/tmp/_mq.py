import json
d = json.load(open('tmp/model-quality-scorecard.json','r',encoding='utf-8'))
print('TRACKS:')
for name, t in d.get('tracks',{}).items():
    if isinstance(t, dict):
        st = t.get('status', '?')
        stt = t.get('state','?')
        cat = t.get('category','?')
        ts  = t.get('top_signal', t.get('signal','?'))
        print(f'  {name:>22} | status={st} | state={stt} | cat={cat} | signal={str(ts)[:140]}')
print()
print('ATTRIBUTION:')
m = d.get('model_attribution',{})
for k in list(m.keys())[:10]:
    if isinstance(m[k],(int,float,bool,str)):
        print(f'  {k}: {m[k]}')
print()
print('READINESS GATES:')
for g in d.get('readiness_gates', []):
    if isinstance(g,dict):
        keep = {k:v for k,v in g.items() if k in ('gate','status','blocks_claim','track_status','detail')}
        print(' -', json.dumps(keep, default=str)[:300])
print()
print('AUTHORITY BOUNDARY:')
ab = d.get('authority_boundary',{})
for k,v in ab.items():
    print(f'  {k}: {v}')
print()
print('EFFICIENCY LOOPS status:')
e = d.get('efficiency_loops',{})
print('  status:', e.get("status"))
print('  meaning:', e.get("meaning"))
smry = e.get('summary',{})
if isinstance(smry,dict):
    for k,v in smry.items():
        if isinstance(v,(int,str,bool,list)):
            print('  smry', k, '=', str(v)[:200])
