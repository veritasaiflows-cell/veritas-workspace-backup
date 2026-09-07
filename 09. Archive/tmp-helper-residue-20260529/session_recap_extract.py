import json, pathlib
root=pathlib.Path('.')
files=['tmp/deployment-check.json','tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json','tmp/capital-deployment-recommendation-validation.json','tmp/alpaca-paper-readiness/paper-order-reconciliation.ph-tight-limit-2026-05-26T0710.json','tmp/intraday-alerts/delivery-router-status.json']
for f in files:
    p=root/f
    print('\n###',f)
    if not p.exists():
        print('MISSING')
        continue
    d=json.loads(p.read_text(encoding='utf-8'))
    def pick(x, keys): return {k:x.get(k) for k in keys if k in x}
    if 'deployment-check' in f:
        print(json.dumps(pick(d,['generated_at_utc','status','last_trading_day','deployable_now','almost_deployable','blocked','below_stop','warnings','summary']),indent=2))
        for k in ['deployable','deployable_now','almost_deployable','blocked','below_stop','records','qualified']:
            if isinstance(d.get(k),list): print(k, len(d[k]), d[k][:10])
    elif 'current-capital' in f:
        print(json.dumps(pick(d,['generated_at_utc','status','recommendation_count','proposal_count','top_candidates','summary','authority']),indent=2)[:4000])
        props=d.get('proposals') or d.get('recommendations') or []
        print('proposals',len(props))
        for p2 in props[:12]:
            print(json.dumps({k:p2.get(k) for k in ['ticker','proposal_id','status','current_state','proposed_state','owner_decision_required','why_now','recommended_action','priority','rank']},indent=2)[:1200])
    elif 'validation' in f:
        print(json.dumps(d,indent=2)[:5000])
    else:
        print(json.dumps(d,indent=2)[:6000])
