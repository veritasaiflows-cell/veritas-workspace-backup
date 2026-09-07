import json, pathlib
bp=json.loads(pathlib.Path('tmp/band-proposals.json').read_text(encoding='utf-8'))
props=bp.get('proposals',[])
by={p.get('ticker'):p for p in props if isinstance(p,dict)}
for t in ['VRT','GS']:
    p=by.get(t,{})
    print(t, 'canonical_apply_eligible=', p.get('canonical_apply_eligible'), 'status=',p.get('status'), 'method=',p.get('method'), 'band_status=',p.get('band_status'))
PY
