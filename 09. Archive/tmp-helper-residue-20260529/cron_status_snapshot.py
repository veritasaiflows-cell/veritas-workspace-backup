import json, pathlib, glob
paths = [
 'tmp/run-summary-morning.json','tmp/run-summary-post-close.json','tmp/dashboard-validation.json','tmp/dashboard-acceptance-report.json','tmp/canon-drift-freshness-gate.json','tmp/current-window-artifacts.json',
 'tmp/research-freshness-opportunity-review.json','tmp/small-mid-cap-regime-feed.json','tmp/sector-expansion-board.json','tmp/full-portfolio-view-validation.json',
 'tmp/cyber-security-daily-audit-cron-proof.json','tmp/cyber-security-daily-audit.json',
 'tmp/intraday-alerts/runtime-handoff-status.json','tmp/intraday-alerts/delivery-router-status.json',
 'tmp/capital-deployment-recommendation-validation.json','tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json',
 'tmp/auto-band-apply.json','tmp/artifact-index-validation.json','tmp/workspace-index-report.json'
]
for p in paths:
    path=pathlib.Path(p)
    print('---',p)
    if not path.exists():
        print('MISSING'); continue
    try:
        d=json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        print('BADJSON',e); continue
    keys=['status','summary_status','window','generated_at_utc','failed_step','exit_code','proof_status','audit_status','operator_action_required','handoff_status']
    print({k:d.get(k) for k in keys if k in d})
    for k in ['summary','validation','authority','findings','errors','warnings','counts']:
        if k in d:
            v=d[k]
            if isinstance(v,(list,tuple)):
                print(k, 'len=',len(v), v[:3])
            elif isinstance(v,dict):
                print(k, {kk:v.get(kk) for kk in list(v)[:12]})
            else: print(k,v)
print('--- exec recommendation md files')
for p in sorted(glob.glob('tmp/intraday-alerts/execution-recommendations/*.md')):
    print(p, pathlib.Path(p).stat().st_mtime, pathlib.Path(p).stat().st_size)
