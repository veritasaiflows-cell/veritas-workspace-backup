import json
from pathlib import Path
from datetime import datetime, timezone
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
W=Path.cwd(); tmp=W/'tmp'
adj=json.loads((tmp/'wf72-phase8-portfolio-source-freshness-adjudication.json').read_text(encoding='utf-8'))
qa=json.loads((tmp/'wf72-phase8-portfolio-source-freshness-qa.json').read_text(encoding='utf-8'))
report={
 'schema_version':'wf72_phase8_closeout.v1',
 'generated_at_utc':now,
 'status':'closed_held_no_activation',
 'candidate_key':'portfolio:source_freshness_classification',
 'main_session_decision':'Keep held. Do not activate under current SQL-canon metadata contract.',
 'worker_status':adj.get('status'),
 'qa_status':qa.get('status'),
 'reasons':['classification is manual_dependency, not fresh/current','trust level is review_required','usable_for_presentation=false','usable_for_canonical_mutation=false','source is portfolio-config/manual-review spine','current activator hard-codes freshness_status=fresh and would mislabel degraded manual dependency if reused','no no-drift proof for portfolio manual-dependency exception'],
 'activation_allowed':False,
 'cache_write_allowed':False,
 'future_reconsideration':'Only after a separate degraded portfolio manual-dependency metadata contract, exact approval artifact, guard/test changes, fallback equality, no-drift proof, and rollback/export drill.',
 'proof_artifacts':['tmp/wf72-phase8-portfolio-source-freshness-adjudication.json/.md','tmp/wf72-phase8-portfolio-source-freshness-qa.json/.md'],
 'authority':{'canonical_note_mutation_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'dashboard_recommendation_deployment_action_state_behavior_change_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'config_auth_channel_service_mutation_allowed':False}
}
(tmp/'wf72-phase8-closeout.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 8 Closeout','',f"- Status: `{report['status']}`",f"- Candidate: `{report['candidate_key']}`",f"- Decision: {report['main_session_decision']}",'','## Reasons']
for r in report['reasons']: md.append(f'- {r}')
md += ['', '## Future reconsideration', report['future_reconsideration'], '', '## Boundary', '- No activation/cache write, no Markdown/canon/portfolio mutation, no owner approval inference, no cron-direct apply, no dashboard action-state behavior change, no trade/account/paper/live authority, no money/config/auth/channel/service mutation.']
(tmp/'wf72-phase8-closeout.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(report['status'])
