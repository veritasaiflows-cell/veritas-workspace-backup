import json
from pathlib import Path
from datetime import datetime, timezone
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
tmp=Path('tmp')
adj=json.loads((tmp/'wf72-phase9-deployment-status-adjudication.json').read_text(encoding='utf-8'))
qa=json.loads((tmp/'wf72-phase9-deployment-status-qa.json').read_text(encoding='utf-8'))
rows=adj.get('held_rows') or []
report={
 'schema_version':'wf72_phase9_closeout.v1',
 'generated_at_utc':now,
 'status':'closed_permanent_hold_no_activation',
 'family':'deployment_proof_status',
 'main_session_decision':'Permanent hold for current deployment_proof_status field/value set; do not migrate to SQL-canon.',
 'row_count':len(rows),
 'keys':[r.get('key') for r in rows],
 'values_seen':(adj.get('inventory_summary') or {}).get('exact_values'),
 'value_counts':(adj.get('inventory_summary') or {}).get('value_counts'),
 'worker_status':adj.get('status'),
 'qa_status':qa.get('status'),
 'neutral_contract_feasible_current_field':False,
 'reasons':['field name and values are action/deployment semantic','values feed dashboard buckets/cards/action-state behavior','deployment_readiness_surface.py is an action-state producer, not neutral proof metadata','current guard allowlist excludes deployment_proof_status','current SQL cache has 13 approved rows and zero deployment_proof_status rows','BRK.B/LMT still carry review-needed/prework blockers'],
 'future_reconsideration':'Only via a different neutral display-only field/vocabulary with exact approval, full dashboard/Today/run-summary no-drift proof, negative fail-closed tests, and manual authority review.',
 'activation_allowed':False,
 'cache_write_allowed':False,
 'proof_artifacts':['tmp/wf72-phase9-deployment-status-adjudication.json/.md','tmp/wf72-phase9-deployment-status-qa.json/.md'],
 'authority':{'sql_canon_expansion_allowed':False,'canonical_note_mutation_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'dashboard_recommendation_deployment_action_state_behavior_change_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'config_auth_channel_service_mutation_allowed':False}
}
(tmp/'wf72-phase9-closeout.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 9 Closeout','',f"- Status: `{report['status']}`",f"- Family: `{report['family']}`",f"- Decision: {report['main_session_decision']}",f"- Rows: `{report['row_count']}`",'', '## Values seen']
for k,v in (report['value_counts'] or {}).items(): md.append(f'- `{k}`: {v}')
md += ['', '## Reasons']
for r in report['reasons']: md.append(f'- {r}')
md += ['', '## Future reconsideration', report['future_reconsideration'], '', '## Boundary', '- No activation/cache write, no Markdown/canon/portfolio mutation, no owner approval inference, no dashboard action-state behavior change, no trade/account/paper/live authority, no money/config/auth/channel/service mutation.']
(tmp/'wf72-phase9-closeout.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(report['status'])
