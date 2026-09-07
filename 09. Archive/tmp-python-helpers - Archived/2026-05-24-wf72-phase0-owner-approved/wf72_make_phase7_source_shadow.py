import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
W=Path.cwd(); tmp=W/'tmp'
def sha(path):
    p=Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
dash=json.loads((tmp/'dashboard-data.json').read_text(encoding='utf-8'))
sources=((dash.get('trust') or {}).get('source_freshness') or {}).get('sources') or []
shadow_keys=['breadth','credit','fundamental_ir','fundamentals','market','policy','technical']
held_keys=['portfolio']
rows_by_key={r.get('source_key'):r for r in sources}
shadow=[]
for key in shadow_keys:
    r=rows_by_key.get(key,{})
    shadow.append({
        'key': f'{key}:source_freshness_classification',
        'scope': key,
        'field_name': 'source_freshness_classification',
        'field_value': r.get('classification'),
        'source_file': 'tmp/dashboard-data.json',
        'source_file_sha256': sha(tmp/'dashboard-data.json'),
        'source_path': r.get('path'),
        'source_path_sha256': sha(W/str(r.get('path','')).replace('/','\\')) if r.get('path') else None,
        'fallback_required': True,
        'activation_allowed_by_this_artifact': False,
        'cache_write_allowed_by_this_artifact': False,
        'blockers': [] if r.get('classification') in {'fresh','current'} else [f"classification={r.get('classification')}"]
    })
held=[]
for key in held_keys:
    r=rows_by_key.get(key,{})
    held.append({'key':f'{key}:source_freshness_classification','classification':r.get('classification'),'hold_reason':'portfolio/manual-dependency freshness can influence owner-truth trust presentation; requires separate owner/canon gate.'})
protected=['tmp/dashboard-data.json','01. Dashboards/Today.md','tmp/morning-run-summary.json','tmp/post-close-run-summary.json','tmp/sunday-run-summary.json']
report={'schema_version':'wf72_phase7_source_freshness_shadow_proof.v1','generated_at_utc':now,'status':'shadow_ready' if all(not r['blockers'] for r in shadow) else 'blocked','authority_boundary':'phase7_review_only_source_freshness_shadow_no_sql_canon_expansion_no_cache_write','activation_allowed_by_this_artifact':False,'sql_canon_cache_write_allowed':False,'canonical_note_mutation_allowed':False,'markdown_mutation_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'candidate_family':'source_freshness_classification_metadata_extension','shadow_ready_keys':[r['key'] for r in shadow if not r['blockers']],'shadow_candidates':shadow,'held_candidates':held,'activation_prerequisites':['exact owner approval for selected future activation keys','guard allowlist/boundary update for exact future set only','fallback value map for every active and proposed key','preactivation export and rollback SQL','temp-copy rollback drill','post-activation no-drift proof for dashboard/Today/run summaries','artifact-index and dashboard acceptance clean'], 'protected_surface_hashes':{p:sha(W/p) for p in protected},'no_drift_statement':'Shadow artifact only; no SQL rows activated and no protected surface was intentionally modified.'}
(tmp/'wf72-phase7-source-freshness-shadow-proof.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 7 Source-Freshness Shadow Proof','',f"- Status: `{report['status']}`",f"- Family: `{report['candidate_family']}`",'- Activation/cache write allowed: `false`','- Boundary: review-only shadow; no authority widening.','','## Shadow-ready keys']
for k in report['shadow_ready_keys']: md.append(f'- `{k}`')
md += ['', '## Held']
for h in held: md.append(f"- `{h['key']}` — {h['hold_reason']}")
(tmp/'wf72-phase7-source-freshness-shadow-proof.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(report['status'], len(report['shadow_ready_keys']))
