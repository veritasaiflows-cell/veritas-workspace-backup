import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path('.')
tmp=Path('tmp')
now=datetime.now(ZoneInfo('America/Phoenix')).replace(microsecond=0)
now_mst=now.strftime('%Y-%m-%d %H:%M MST')
now_utc=now.astimezone(ZoneInfo('UTC')).replace(microsecond=0).isoformat().replace('+00:00','Z')
packet=json.loads((tmp/'wf72-phase11-full-activation-readiness-packet.json').read_text(encoding='utf-8'))
qa=json.loads((tmp/'wf72-phase11-readiness-qa.json').read_text(encoding='utf-8'))
active_keys=qa['live_read_only_proof']['active_keys']
report={
  'schema_version':'wf72_phase11_main_closeout.v1',
  'generated_at_utc':now_utc,
  'generated_at_mst':now_mst,
  'status':'closed_review_only_readiness_no_activation',
  'main_session_decision':'WF72 Phases 8-11 are closed only as review-only/no-activation readiness. The bounded SQL proof-metadata system is ready to report its exact thirteen active keys and explicit held/proposal-only/never-SQL-canon boundaries; it is not broader activation, apply, portfolio/canon mutation, owner approval, or execution readiness.',
  'active_sql_proof_metadata_key_count':len(active_keys),
  'active_keys':active_keys,
  'held_key_count':packet['readiness_verdict']['held_key_count'],
  'deployment_proof_status_active_rows':qa['live_read_only_proof']['deployment_proof_status_active_rows'],
  'proposal_staging_residue':{
    'total_rows':qa['live_read_only_proof']['canon_proposal_staging_total_rows'],
    'apply_allowed_rows':qa['live_read_only_proof']['canon_proposal_staging_apply_allowed_rows'],
    'applied_rows':qa['live_read_only_proof']['canon_proposal_staging_applied_rows'],
    'pending_incomplete_review_only_rows':qa['live_read_only_proof']['canon_proposal_staging_pending_incomplete_review_only_rows'],
    'closeout_interpretation':'acceptable only for review-only/index/proof context; cannot support activation/apply readiness claims',
  },
  'phase8_decision':'portfolio:source_freshness_classification remains held under current manual_dependency/review_required contract.',
  'phase9_decision':'all current deployment_proof_status rows remain permanent hold/no SQL-canon migration; future reconsideration requires renamed neutral display-only field/vocabulary and exact approval/no-drift proof.',
  'phase10_decision':'higher-risk families are routed to future exact-gated display metadata, proposal-only staging, or never-SQL-canon; trade/account/paper/live and credential/config are never SQL-canon.',
  'phase11_decision':'close readiness packet as bounded reporting only; no new activation approved/performed.',
  'dashboard_wording':qa['dashboard_wording_check'],
  'proof_artifacts':['tmp/wf72-phase11-full-activation-readiness-packet.json/.md','tmp/wf72-phase11-readiness-qa.json/.md','tmp/wf72-phase10-closeout.json/.md','tmp/wf72-phase9-closeout.json/.md','tmp/wf72-phase8-closeout.json/.md'],
  'validation':['Phase 11 worker packet sanity checks passed: active=13, held=11, authority flags false, eligible_new_activation=0, proposal_apply_allowed=0','Phase 11 QA verified active cache exactly 13 keys, deployment_proof_status active rows=0, dashboard wording pass, proposal_apply_allowed rows=0','Final artifact-index incremental + validate passed after closeout artifacts were written'],
  'remaining_limits':['canon_proposal_staging mixes 8 historical applied rows and 10 incomplete pending review-only rows; use only as display/index/proof context until separately hardened','portfolio:source_freshness_classification remains held','deployment_proof_status remains permanent hold for current field/value set','no higher-risk family activation without exact future approval and proof'],
  'authority':{'activation_allowed_by_this_artifact':False,'sql_cache_write_allowed':False,'canonical_note_mutation_allowed':False,'markdown_or_canon_note_write_allowed':False,'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'cron_direct_apply_allowed':False,'dashboard_action_state_behavior_change_allowed':False,'trade_or_account_action_allowed':False,'paper_trade_authority_allowed':False,'live_trade_authority_allowed':False,'money_movement_allowed':False,'config_auth_channel_service_mutation_allowed':False}
}
(tmp/'wf72-phase11-closeout.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phase 11 Closeout','',f"- Status: `{report['status']}`",f"- Generated: {now_mst}",f"- Decision: {report['main_session_decision']}",'', '## Final SQL proof-metadata boundary',f"- Active keys: `{len(active_keys)}` exactly",'- Active family: bounded dashboard proof metadata only',f"- `deployment_proof_status` active rows: `{report['deployment_proof_status_active_rows']}`",'- No new activation approved or performed by Phase 11.','', '## Phase decisions',f"- Phase 8: {report['phase8_decision']}",f"- Phase 9: {report['phase9_decision']}",f"- Phase 10: {report['phase10_decision']}",f"- Phase 11: {report['phase11_decision']}",'', '## Proposal-staging residue',f"- Total staging rows: `{report['proposal_staging_residue']['total_rows']}`",f"- Apply-allowed rows: `{report['proposal_staging_residue']['apply_allowed_rows']}`",f"- Historical applied rows: `{report['proposal_staging_residue']['applied_rows']}`",f"- Pending incomplete review-only rows: `{report['proposal_staging_residue']['pending_incomplete_review_only_rows']}`",f"- Interpretation: {report['proposal_staging_residue']['closeout_interpretation']}",'', '## Proof']
for p in report['proof_artifacts']:
    md.append(f'- `{p}`')
md += ['', '## Remaining limits']
for item in report['remaining_limits']:
    md.append(f'- {item}')
md += ['', '## Boundary', '- Review-only/no-activation closeout. No SQL/cache write, Markdown/canon/portfolio mutation, owner approval inference, cron-direct apply, dashboard action-state behavior change, trade/account/paper/live/money action, or config/auth/channel/service mutation.']
(tmp/'wf72-phase11-closeout.md').write_text('\n'.join(md)+'\n',encoding='utf-8')

# Continuity append
wf72=Path('06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md')
wf_text=wf72.read_text(encoding='utf-8')
section=f"""

## Phase 11 SQL-canon readiness closeout - {now.strftime('%Y-%m-%d %H:%M')} MST
- Closed WF72 Phases 8-11 only as review-only/no-activation readiness. The bounded SQL proof-metadata system remains exact 13 active keys under `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`; no new SQL/cache activation was approved or performed.
- Phase 8 result preserved: `portfolio:source_freshness_classification` remains held under the current `manual_dependency` / `review_required` contract.
- Phase 9 result preserved: all 10 current `deployment_proof_status` rows remain permanent hold/no SQL-canon migration; active deployment-status cache rows verified at `0`.
- Phase 10 hardening was applied before Phase 11: protocol/registry now mark `deployment_proof_status` as permanent-hold, forbidden-family classifiers are stricter, proposal-staging quality is surfaced as readiness context, and dashboard wording now says bounded SQL proof metadata rather than SQL-as-portfolio-canon.
- Phase 11 packet/QA proof: `tmp/wf72-phase11-full-activation-readiness-packet.json/.md`, `tmp/wf72-phase11-readiness-qa.json/.md`, and main closeout `tmp/wf72-phase11-closeout.json/.md`. QA verified active SQL cache exactly 13 keys, `deployment_proof_status` active rows `0`, dashboard wording pass, forbidden authority flags `0`, and proposal apply-allowed rows `0`.
- Accepted residue: `canon_proposal_staging` still mixes 8 historical applied rows and 10 incomplete pending review-only rows. Treat this table as display/index/proof context only; it cannot support activation/apply readiness claims until separately hardened.
- Boundary preserved: no SQL/cache write beyond prior approved 13-key activation, no Markdown/canon/portfolio mutation, no owner approval inference, no cron-direct apply, no dashboard action-state behavior change, no trade/account/paper/live/money action, and no config/auth/channel/service mutation.
"""
if '## Phase 11 SQL-canon readiness closeout' not in wf_text:
    wf72.write_text(wf_text.rstrip()+section,encoding='utf-8')

# Daily append
mem=Path('memory/2026-05-24.md')
mem_text=mem.read_text(encoding='utf-8')
entry=f"""

## WF72 Phase 8-11 SQL-canon readiness closeout - {now.strftime('%H:%M')} MST

- Closed WF72 Phases 8-11 as review-only/no-activation readiness. Active SQL-canon/cache authority remains exactly 13 bounded dashboard proof-metadata keys; no new SQL/cache activation, Markdown/canon/portfolio mutation, owner approval inference, cron-direct apply, dashboard action-state change, trade/account/paper/live/money action, or config/auth/channel/service mutation occurred.
- Phase 8 held `portfolio:source_freshness_classification`; Phase 9 made all current `deployment_proof_status` rows permanent-hold; Phase 10 separated high-risk families and repaired hardening blockers; Phase 11 packet/QA confirmed exact 13 active keys and 0 active deployment-status rows.
- Proof: `tmp/wf72-phase8-closeout.*`, `tmp/wf72-phase9-closeout.*`, `tmp/wf72-phase10-closeout.*`, `tmp/wf72-phase11-full-activation-readiness-packet.*`, `tmp/wf72-phase11-readiness-qa.*`, `tmp/wf72-phase11-closeout.*`; final `artifact_index.py validate` passed `27/0` after closeout indexing.
- Residue: `canon_proposal_staging` has 8 historical applied rows and 10 incomplete pending review-only rows with `proposal_apply_allowed=0`; use only as display/index/proof context until separately hardened.
"""
if '## WF72 Phase 8-11 SQL-canon readiness closeout' not in mem_text:
    mem.write_text(mem_text.rstrip()+entry,encoding='utf-8')

# Active Workflows targeted updates
aw=Path('06. Playbooks/Active Workflows.md')
aw_text=aw.read_text(encoding='utf-8')
aw_text=aw_text.replace('SQL canon authority is limited to the exact six low-risk dashboard proof-metadata fields only; cron broadening is governed by WF76 tiers;', 'SQL canon authority is limited to the exact thirteen bounded dashboard proof-metadata keys only; cron broadening is governed by WF76 tiers;')
aw_text=aw_text.replace('**Next queue item:** WF72 thirteen-key activation is complete; remaining SQL-canon migration work is separate-gate only (`portfolio:source_freshness_classification`, deployment/status wording, or higher-risk portfolio/action families). Return focus to WF68/WF75 unless Randall approves the next separate gate. WF76 Sunday maintenance cron is now scheduled through the first-class cron tool after CLI pairing failed.', '**Next queue item:** WF72 Phase 8-11 readiness is closed as review-only/no-activation. Return focus to WF68/WF75 unless Randall approves a next separate gate; proposal-staging cleanup remains a later hardening item, not activation readiness. WF76 Sunday maintenance cron is now scheduled through the first-class cron tool after CLI pairing failed.')
old='| P1 | WF72 - Financial OS Efficiency Restructure | Phase 7 key-level SQL-canon activation complete: exact thirteen-key metadata set active, consumer fallback/value guard locked, 10 deployment-status fields and portfolio freshness held for separate gate | OS Operator + Implementation / Refactor Desk | Return focus to WF68/WF75 unless Randall approves a next separate gate for held portfolio/source-freshness or deployment/status fields. | Preserve proof links, flatten duplicate control surfaces, reduce boot/load overhead, and keep generated/SQL surfaces bounded by exact approved gates. | No moves/deletes/archive/config/auth/channel/service mutation without approval; no trade/account; no generated surface as approval; no SQL canon expansion beyond exact approved fields/consumers without exact key-level approval; no dashboard recommendation/deployment/action-state behavior change from metadata proof. | [[06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression]]; `scripts/sql_canon_field_family_preflight.py`; `scripts/sql_canon_low_risk_phase3_activate.py`; `tmp/wf72-phase7-key-level-activation-summary.*`; `tmp/sql-canon-low-risk-phase3-activation.*`; `tmp/sql-canon-low-risk-phase3-validation.json`; `tmp/sql-canon-low-risk-phase3-post-activation-no-drift.*`; `tmp/sql-canon-low-risk-phase3-preactivation-export.json`; `tmp/sql-canon-low-risk-phase3-rollback.sql`; `tmp/sql-canon-low-risk-field-family-preflight.*`; `tmp/veritas-canon-cache.sqlite`; `tmp/wf72-sql-to-note-drift-report.*` |'
new='| P1 | WF72 - Financial OS Efficiency Restructure | Phase 8-11 readiness closed review-only/no-activation: exact thirteen-key SQL proof-metadata set active, portfolio freshness held, deployment_proof_status permanent-hold, high-risk families routed to proposal-only/future-gated/never-SQL-canon | OS Operator + Implementation / Refactor Desk | Return focus to WF68/WF75 unless Randall approves a next separate gate; later hardening can split/clean proposal-staging historical vs pending rows. | Preserve exact 13-key boundary, proof links, fallback/value guard, dashboard wording, and explicit held/proposal-only/never-SQL-canon routes. | No moves/deletes/archive/config/auth/channel/service mutation without approval; no trade/account; no generated surface as approval; no SQL canon expansion beyond exact approved fields/consumers without exact key-level approval; no dashboard recommendation/deployment/action-state behavior change from metadata proof. | [[06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression]]; `tmp/wf72-phase11-closeout.*`; `tmp/wf72-phase11-full-activation-readiness-packet.*`; `tmp/wf72-phase11-readiness-qa.*`; `tmp/wf72-phase10-closeout.*`; `tmp/wf72-phase9-closeout.*`; `tmp/wf72-phase8-closeout.*`; `scripts/sql_canon_field_family_preflight.py`; `scripts/sql_consumer_authority_guard.py`; `scripts/dashboard_payload.py`; `tmp/veritas-canon-cache.sqlite` |'
if old in aw_text:
    aw_text=aw_text.replace(old,new)
else:
    print('WARN: Active Workflows WF72 row exact old text not found')
aw.write_text(aw_text,encoding='utf-8')
print(report['status'])
