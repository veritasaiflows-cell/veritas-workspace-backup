import json, pathlib
files=[
 'tmp/run-chain-post-close.json','tmp/run-summary-post-close.json','tmp/auto-band-apply.json','tmp/band-proposals.json','tmp/dashboard-validation.json','tmp/daily-review-objects-post-close.json','tmp/deployment-readiness-surface.json','tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json','tmp/capital-deployment-recommendation-validation.json','tmp/post-apply-validation-chain.json'
]
keys=['status','ok','result','chain_status','exit_code','stop_line','acceptance_passed','window','mode','summary','critical_count','warning_count','validation_status','writes_performed','applied_count','skipped_count','canonical_apply_eligible_count','eligible_count']
for f in files:
    p=pathlib.Path(f)
    print('\n###',f)
    print('exists',p.exists(),'size',p.stat().st_size if p.exists() else None,'mtime',p.stat().st_mtime if p.exists() else None)
    if not p.exists(): continue
    try:
        data=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print('json_error',e); continue
    if isinstance(data,dict):
        for k in keys:
            if k in data: print(k,':',data[k])
        for ak in ['authority','authority_flags','trust_boundary','automation_authority','capital_recommendation_authority','authority_boundary']:
            if ak in data: print(ak,':',data[ak])
        if isinstance(data.get('proposals'),list): print('proposals_len',len(data['proposals']))
        if isinstance(data.get('packets'),list): print('packets_len',len(data['packets']))
        if isinstance(data.get('findings'),list): print('findings_len',len(data['findings']))
        if isinstance(data.get('critical_findings'),list): print('critical_findings_len',len(data['critical_findings']))
        if isinstance(data.get('warnings'),list): print('warnings_len',len(data['warnings']))
    else:
        print(type(data).__name__,len(data) if hasattr(data,'__len__') else '')
