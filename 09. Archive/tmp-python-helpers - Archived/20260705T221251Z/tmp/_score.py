import json
for path, label in [
    ('tmp/token-efficiency-scorecard.json','TOKEN EFFICIENCY SCORECARD'),
    ('tmp/model-quality-scorecard.json','MODEL QUALITY SCORECARD'),
    ('tmp/finance-decision-performance-digest.json','FINANCE DECISION PERFORMANCE DIGEST'),
    ('tmp/implementation-token-attribution-bridge.json','IMPLEMENTATION TOKEN ATTRIBUTION BRIDGE'),
    ('tmp/openclaw-cache-efficiency-scorecard.json','OPENCLAW CACHE EFFICIENCY SCORECARD'),
    ('tmp/otel-critical-review-decision-packet.json','OTEL CRITICAL REVIEW DECISION PACKET'),
]:
    try:
        d = json.load(open(path,'r',encoding='utf-8'))
    except Exception as e:
        print(f'{label}: ERROR {e}')
        continue
    print(f'=== {label} ===')
    print(f'  status: {d.get("status")}')
    summ = d.get('summary',{})
    if isinstance(summ, dict):
        for k in list(summ.keys())[:20]:
            v = summ[k]
            if isinstance(v,(str,int,float,bool)):
                print(f'  {k}: {v}')
            elif isinstance(v,list):
                print(f'  {k}: list[{len(v)}] first={str(v[0])[:120]}')
            elif isinstance(v,dict):
                print(f'  {k}: dict keys={list(v.keys())[:6]}')
    print()
