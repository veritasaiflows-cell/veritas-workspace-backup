import json
from pathlib import Path
ROOT=Path(r'C:\Users\Veritas\.openclaw\workspace')
files=[
 'tmp/run-summary-morning.json','tmp/current-window-artifacts.md','tmp/dashboard-validation.json','tmp/stale-intelligence-guardrail.json','tmp/technical-refresh.json','tmp/fundamental-metrics-current.json','tmp/fundamental-metrics-validation.json','tmp/fundamental-ir-reconciliation-packets.json','tmp/fundamental-ir-reconciliation-validation.json','tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json','tmp/capital-deployment-recommendation-validation.json']
out={}
for f in files:
 p=ROOT/f
 rec={'exists':p.exists(),'mtime':p.stat().st_mtime if p.exists() else None,'size':p.stat().st_size if p.exists() else None}
 if p.exists() and p.suffix=='.json':
  try:
   d=json.loads(p.read_text(encoding='utf-8-sig'))
   rec['status']=d.get('status')
   rec['generated_at_utc']=d.get('generated_at_utc') or d.get('generated_at')
   rec['summary']=d.get('summary')
   rec['validation']=d.get('validation')
   rec['findings']=(d.get('findings') or [])[:8]
   if f.endswith('capital-deployment-recommendation-validation.json'):
    rec['ready']=d.get('recommendation_ready') or d.get('capital_recommendation_ready')
    rec['authority']=d.get('authority')
   if 'current-capital-deployment-recommendations' in f:
    rec['recommendation_summary']={k:d.get(k) for k in ['status','decision','recommended_action','primary_candidate','generated_at_utc','owner_action_required']}
    rec['top_keys']=list(d.keys())[:30]
   if f.endswith('technical-refresh.json'):
    rec['top_keys']=list(d.keys())[:30]
    rec['count_fields']={k:len(v) for k,v in d.items() if isinstance(v,(list,dict))}
   if 'fundamental' in f:
    rec['top_keys']=list(d.keys())[:30]
  except Exception as e:
   rec['json_error']=repr(e)
 out[f]=rec
print(json.dumps(out,indent=2,sort_keys=True))
