import json, hashlib, sqlite3
from pathlib import Path
from datetime import datetime, timezone
W=Path.cwd(); tmp=W/'tmp'
def load(rel): return json.loads((W/rel).read_text(encoding='utf-8'))
def sha(rel):
    p=W/rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
activation=load('tmp/sql-canon-low-risk-phase3-activation.json')
validation=load('tmp/sql-canon-low-risk-phase3-validation.json')
preflight=load('tmp/sql-canon-low-risk-field-family-preflight.json')
con=sqlite3.connect(tmp/'veritas-canon-cache.sqlite')
rows=[{'key': f'{r[0]}:{r[1]}', 'value': r[2]} for r in con.execute('select scope,field_name,field_value from canon_cache_fields order by scope, field_name')]
meta=dict(con.execute('select key,value from canon_cache_meta'))
con.close()
report={
 'schema_version':'wf72_phase7_key_level_activation_summary.v1',
 'generated_at_utc':now,
 'status':'ok' if validation.get('status')=='ok' and len(rows)==13 else 'blocked',
 'user_approval':'Randall explicitly approved key-level full migration and activation for the seven shadow-ready source-freshness metadata keys on 2026-05-24 11:08 MST.',
 'authority_boundary':activation.get('authority_boundary'),
 'active_sql_canon_key_count':len(rows),
 'active_sql_canon_keys':[r['key'] for r in rows],
 'newly_activated_keys':activation.get('approved_new_keys'),
 'preserved_keys':[k for k in activation.get('approved_final_key_set',[]) if k not in set(activation.get('approved_new_keys',[]))],
 'cache_meta':meta,
 'validation_summary':validation.get('summary'),
 'preflight_summary':preflight.get('candidate_summary'),
 'still_held':{
   'portfolio_source_freshness':'portfolio:source_freshness_classification',
   'deployment_proof_status_count':10,
   'reason':'portfolio/manual-dependency and deployment/status wording can imply owner-truth or action state; separate gate required.'
 },
 'rejected_or_out_of_scope':['entry/stop metadata','sizing/sleeve/cash/weight metadata','trade/paper/live/account execution metadata','credential/config metadata'],
 'authority':{'markdown_or_canon_note_write_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'dashboard_recommendation_deployment_action_state_behavior_change_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'config_auth_channel_service_mutation_allowed':False},
 'proof':['python -m py_compile changed scripts','python scripts\\sql_canon_low_risk_phase3_activate.py --write -> status=ok rows=13 failed=0','python scripts\\sql_canon_field_family_preflight.py --write -> status=ok already_active=13 held=11','python scripts\\test_artifact_index.py -> passed','python scripts\\test_dashboard_acceptance.py -> 28/28','python scripts\\artifact_index.py incremental','python scripts\\artifact_index.py validate -> ok checks=27 failed=0','direct consumer guard -> ok sql_read_allowed=True approved_keys=13'],
 'proof_artifacts':['tmp/sql-canon-low-risk-phase3-approval-context.json','tmp/sql-canon-low-risk-phase3-activation.json/.md','tmp/sql-canon-low-risk-phase3-validation.json','tmp/sql-canon-low-risk-phase3-post-activation-no-drift.json/.md','tmp/sql-canon-low-risk-phase3-preactivation-export.json','tmp/sql-canon-low-risk-phase3-rollback.sql','tmp/sql-canon-low-risk-field-family-preflight.json/.md'],
 'file_hashes':{rel:sha(rel) for rel in ['scripts/sql_canon_low_risk_phase3_activate.py','scripts/sql_consumer_authority_guard.py','scripts/dashboard_payload.py','scripts/sql_canon_field_family_preflight.py','scripts/test_artifact_index.py']}
}
(tmp/'wf72-phase7-key-level-activation-summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 7 Key-Level SQL-Canon Activation Summary','',f"- Status: `{report['status']}`",f"- Active SQL-canon key count: `{report['active_sql_canon_key_count']}`",f"- Boundary: `{report['authority_boundary']}`",'- Randall approved exact key-level activation for the seven source-freshness extension keys; activation completed with rollback/export and validation proof.','', '## Newly activated keys']
for k in report['newly_activated_keys']: md.append(f'- `{k}`')
md += ['', '## Still held']
md.append('- `portfolio:source_freshness_classification`')
md.append('- 10 `*:deployment_proof_status` rows')
md += ['', '## Proof']
for p in report['proof']: md.append(f'- {p}')
md += ['', '## Boundary']
md.append('- Metadata/proof migration only. No Markdown/canon/portfolio mutation, approval inference, cron-direct apply, dashboard action-state behavior change, trade/account/paper/live authority, money movement, or config/auth/channel/service mutation.')
(tmp/'wf72-phase7-key-level-activation-summary.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(report['status'])
