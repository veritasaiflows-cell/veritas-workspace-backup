import json, pathlib
# auto-band details
ab=json.loads(pathlib.Path('tmp/auto-band-apply.json').read_text(encoding='utf-8'))
print('AUTO_KEYS', sorted(ab.keys()))
for k in ['status','mode','applied','applied_count','skipped','skipped_count','eligible','canonical_apply_eligible','writes_performed']:
    if k in ab: print(k, ab[k])
items=[]
for k in ['applied_proposals','applied','changes','results']:
    if isinstance(ab.get(k),list): items=ab[k]; print('auto_list',k,len(items)); break
bad=[]
for it in items:
    if isinstance(it,dict):
        if it.get('canonical_apply_eligible') is not True and it.get('proposal',{}).get('canonical_apply_eligible') is not True:
            bad.append(it.get('ticker') or it.get('proposal_id') or it)
print('auto_noneligible_applied', bad)
# capital proposal flags
cap=json.loads(pathlib.Path('tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json').read_text(encoding='utf-8'))
proposals=cap.get('proposals',[])
flag_keys=['owner_approval_granted','apply_allowed','canonical_mutation_allowed','portfolio_mutation_allowed','trade_or_account_action_allowed']
viol=[]
for i,p in enumerate(proposals):
    flags={k:p.get(k) for k in flag_keys}
    if any(v is not False for v in flags.values()): viol.append((i,p.get('proposal_id') or p.get('id') or p.get('ticker_or_scope'),flags))
print('capital_proposals',len(proposals),'per_packet_flag_violations',viol)
print('top_authority',cap.get('authority'))
# dashboard criticals
val=json.loads(pathlib.Path('tmp/dashboard-validation.json').read_text(encoding='utf-8'))
print('dashboard_summary',val.get('summary'))
print('dashboard_critical_findings', [f for f in val.get('findings',[]) if isinstance(f,dict) and f.get('severity')=='critical'][:5])
# chain steps statuses
chain=json.loads(pathlib.Path('tmp/run-chain-post-close.json').read_text(encoding='utf-8'))
steps=chain.get('steps') or chain.get('results') or []
print('chain_status', chain.get('status'), chain.get('exit_code'), 'steps', len(steps))
failed=[s for s in steps if isinstance(s,dict) and s.get('status') not in (None,'ok','warning') and s.get('returncode') not in (None,0)]
print('chain_failed_count',len(failed),failed[:3])
