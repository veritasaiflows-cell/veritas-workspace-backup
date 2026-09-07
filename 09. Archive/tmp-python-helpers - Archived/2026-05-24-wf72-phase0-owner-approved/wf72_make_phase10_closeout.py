import json
from pathlib import Path
from datetime import datetime, timezone
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
tmp=Path('tmp')
tax=json.loads((tmp/'wf72-phase10-higher-risk-family-taxonomy.json').read_text(encoding='utf-8'))
qa=json.loads((tmp/'wf72-phase10-hardening-qa.json').read_text(encoding='utf-8'))
protocol=json.loads((tmp/'sql-canon-field-family-migration-protocol.json').read_text(encoding='utf-8'))
registry=json.loads((tmp/'sql-canon-field-registry.json').read_text(encoding='utf-8'))
dash=json.loads((tmp/'dashboard-data.json').read_text(encoding='utf-8'))
sql= dash.get('sql_canon') or (dash.get('trust') or {}).get('sql_canon') or {}
report={
 'schema_version':'wf72_phase10_closeout.v1',
 'generated_at_utc':now,
 'status':'closed_after_hardening_no_activation',
 'worker_taxonomy_status':tax.get('status'),
 'qa_original_status':qa.get('status'),
 'qa_original_verdict':qa.get('verdict'),
 'main_session_decision':'Phase 10 is closed after repairing the enforceability/wording blockers. Phase 11 may assemble a readiness packet, but only for exact 13-key active SQL proof-metadata plus explicit held/never/proposal-only boundaries; no broader activation is authorized.',
 'current_active_sql_canon_key_count':len((tax.get('current_active_sql_canon_metadata') or {}).get('approved_keys') or []),
 'hardening_repairs':[ 
   'Protocol now marks deployment_proof_status as rejected_current_field_permanent_hold with allowed_fields empty.',
   'Field registry marks deployment_proof_status as rejected_current_field_permanent_hold_phase9_no_sql_canon_migration.',
   'Consumer/preflight forbidden-family classifiers expanded for stop, sleeve, sector, execution, config, owner approval, entitlement, order, broker, allocation, target_weight, trim/add/buy/sell aliases.',
   'Consumer guard now reports proposal staging quality counts and incomplete review-only rows as Phase 11 gate context.',
   'Dashboard payload no longer sets sqlIsCanon=true on successful SQL proof-cache reads; it uses sqlReadAllowed/proofMetadataAuthority and explicit bounded proof-cache wording.'
 ],
 'dashboard_sql_wording':{k:sql.get(k) for k in ['status','sqlIsCanon','sqlReadAllowed','proofMetadataAuthority','boundedSqlProofCache','authorityWording']},
 'protocol_deployment_status_family':[f for f in protocol.get('family_order',[]) if f.get('family')=='deployment_status_metadata'],
 'registry_deployment_status_decision':registry.get('deployment_proof_status_phase9_decision'),
 'phase11_allowed_scope':'readiness packet only; exact active 13 keys, held/permanent-hold rows, proposal-only staging limitations, never-SQL-canon classes, guard/test/rollback/no-drift proof.',
 'phase11_not_allowed':['new SQL/cache activation','portfolio source freshness activation','deployment_proof_status activation','higher-risk family activation','Markdown/canon/portfolio mutation','owner approval inference','cron-direct apply','dashboard action-state behavior change','trade/account/paper/live/money/config/auth/channel/service mutation'],
 'proof':[
   'python -m py_compile scripts\\sql_canon_field_family_preflight.py scripts\\sql_consumer_authority_guard.py scripts\\dashboard_payload.py',
   'python scripts\\sql_canon_field_family_preflight.py --write -> status=ok; active=13; held=11; eligible=0; blocked=0',
   'python scripts\\test_dashboard_acceptance.py -> 28/28',
   'python scripts\\test_artifact_index.py -> passed',
   'python scripts\\generate_dashboard.py -> dashboard-data/html written; 0 critical, 1 existing warning',
   'python scripts\\artifact_index.py incremental',
   'python scripts\\artifact_index.py validate -> status=ok checks=27 failed=0'
 ],
 'authority':{'sql_cache_write_allowed':False,'activation_allowed_by_this_artifact':False,'canonical_note_mutation_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'dashboard_action_state_behavior_change_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'config_auth_channel_service_mutation_allowed':False}
}
(tmp/'wf72-phase10-closeout.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 10 Closeout','',f"- Status: `{report['status']}`",f"- Decision: {report['main_session_decision']}",f"- Active SQL proof-metadata keys: `{report['current_active_sql_canon_key_count']}`",'', '## Hardening repairs']
for r in report['hardening_repairs']: md.append(f'- {r}')
md += ['', '## Dashboard SQL wording', f"- `sqlIsCanon`: `{report['dashboard_sql_wording'].get('sqlIsCanon')}`", f"- `sqlReadAllowed`: `{report['dashboard_sql_wording'].get('sqlReadAllowed')}`", f"- `proofMetadataAuthority`: `{report['dashboard_sql_wording'].get('proofMetadataAuthority')}`", f"- Wording: {report['dashboard_sql_wording'].get('authorityWording')}", '', '## Phase 11 allowed scope', report['phase11_allowed_scope'], '', '## Not allowed']
for x in report['phase11_not_allowed']: md.append(f'- {x}')
md += ['', '## Proof']
for p in report['proof']: md.append(f'- `{p}`')
(tmp/'wf72-phase10-closeout.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(report['status'])
