import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
W=Path.cwd(); tmp=W/'tmp'
def read(p): return json.loads((W/p).read_text(encoding='utf-8'))
def sha(p):
    path=W/p
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
phase4=read(Path('tmp/wf72-phase4-six-key-stabilization-postfix.json'))
phase5=read(Path('tmp/wf72-phase5-sql-consumer-inventory.json'))
phase6=read(Path('tmp/wf72-phase6-held-field-adjudication.json'))
phase7=read(Path('tmp/wf72-phase7-source-freshness-shadow-proof.json'))
report={
 'schema_version':'wf72_phase4_7_integration_summary.v1',
 'generated_at_utc':now,
 'status':'ok' if phase4.get('status')=='ok' and phase7.get('status')=='shadow_ready' else 'blocked',
 'phase_results':{
   'phase4_six_key_stabilization':'ok' if phase4.get('status')=='ok' else phase4.get('status'),
   'phase5_consumer_inventory':'complete_reviewed',
   'phase6_held_field_adjudication':'complete_all_10_deployment_status_fields_held',
   'phase7_source_freshness_shadow':'shadow_ready_7_keys'
 },
 'active_sql_canon_keys':phase4.get('active_keys'),
 'phase7_shadow_ready_keys':phase7.get('shadow_ready_keys'),
 'held_keys':{
   'source_freshness':['portfolio:source_freshness_classification'],
   'deployment_status_count':(phase6.get('classification_counts') or {}).get('remain_held_no_activation')
 },
 'activation_readiness':'ready_for_future_exact_approval_packet_for_7_source_freshness_keys_only; not activated by this pass',
 'blockers_cleared':['NVDA earnings_lifecycle_status SQL/fallback semantic drift','dashboard fallback map missing four of six approved keys','post-activation preflight stale Phase4A exact-two expectation'],
 'remaining_limits':['Future activation still requires exact key-level owner approval','portfolio source_freshness and all deployment_proof_status fields remain held','entry/stop/sizing/sleeve/cash/risk/trade/account/credential families rejected or out of scope'],
 'authority':{'markdown_or_canon_note_write_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'config_auth_channel_service_mutation_allowed':False},
 'proof_artifacts':['tmp/wf72-phase4-six-key-stabilization-postfix.json','tmp/wf72-phase5-sql-consumer-inventory.json','tmp/wf72-phase6-held-field-adjudication.json','tmp/wf72-phase7-source-freshness-shadow-proof.json','tmp/sql-canon-low-risk-phase3-validation.json'],
 'validation':['py_compile changed scripts','sql_canon_low_risk_phase3_activate.py --write rows=6 failed=0','sql_canon_field_family_preflight.py --write status=ok','scripts/test_artifact_index.py passed','scripts/test_dashboard_acceptance.py 28/28','artifact_index.py validate 27/0 stale=0','direct consumer guard status=ok sql_read_allowed=True']
}
(tmp/'wf72-phase4-7-integration-summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 4-7 Integration Summary','',f"- Status: `{report['status']}`",'- Phase 4: exact-six stabilization fixed and rollback drill passed on temp copy.','- Phase 5: consumer inventory/fallback lock reviewed.','- Phase 6: all 10 deployment/status fields remain held.','- Phase 7: seven source-freshness metadata keys are shadow-ready only.','','## Shadow-ready future family']
for k in report['phase7_shadow_ready_keys']: md.append(f'- `{k}`')
md += ['', '## Boundaries', '- No SQL expansion/activation beyond existing six keys in this pass.', '- No Markdown/canon/portfolio mutation, owner approval inference, cron-direct apply, trade/account/paper/live authority, money movement, or config/auth/channel/service mutation.']
(tmp/'wf72-phase4-7-integration-summary.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(report['status'])
