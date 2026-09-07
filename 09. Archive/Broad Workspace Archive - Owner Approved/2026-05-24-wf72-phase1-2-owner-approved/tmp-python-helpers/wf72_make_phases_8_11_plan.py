import json
from pathlib import Path
from datetime import datetime, timezone
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
plan={
  'schema_version':'wf72_phases_8_11_full_activation_readiness_plan.v1',
  'generated_at_utc':now,
  'status':'ready_for_bounded_phase_8_start',
  'current_active_sql_canon':{
    'key_count':13,
    'boundary':'phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority',
    'scope':'dashboard_proof_metadata_only_fallback_required_no_execution_authority'
  },
  'resolved_pre_phase_residue':{
    'opportunity_2_note_drift':'scheduled_review_only_under_WF76_weekly_maintenance; not demand_only; no auto_apply',
    'opportunity_7_fts5':'code_and_procedure_resolved; SQLite skill patched with FTS5/hyphen/alias/source-open guidance'
  },
  'phases':[
    {
      'phase':'8',
      'name':'Portfolio source-freshness separate-gate adjudication',
      'goal':'Decide whether portfolio:source_freshness_classification can migrate as non-authoritative proof metadata or must remain permanently held.',
      'candidate_keys':['portfolio:source_freshness_classification'],
      'work_packages':['prove source value is freshness/trust metadata only, not portfolio state or owner approval','build fallback/current-source extraction','run no-drift compare across dashboard/Today/run summaries','update guard/test allowlist only if no owner-truth/action drift'],
      'acceptance':['activation packet names exact key','manual-dependency/owner-truth wording cannot imply approval or canonical portfolio mutation','guard blocks on missing/mismatched fallback','artifact-index validate and dashboard acceptance pass'],
      'stop_lines':['portfolio mutation implication','owner approval inference','manual dependency being treated as canonical truth','dashboard action/recommendation behavior drift']
    },
    {
      'phase':'9',
      'name':'Deployment/status wording redesign or permanent hold',
      'goal':'Normalize deployment_proof_status into non-authoritative display metadata or keep it outside SQL-canon.',
      'candidate_keys':'10 deployment_proof_status rows currently held',
      'work_packages':['inventory exact values and action-wording risks','design neutral display vocabulary if feasible','prove dashboard/decision queue wording stays review-only','independent challenge for authority leakage'],
      'acceptance':['either reject/permanent hold with proof, or exact normalized non-action metadata contract exists','no DEPLOYABLE/DO NOT TOUCH/PROMOTION REVIEW wording can be read as instruction or owner approval','no dashboard action-state behavior drift'],
      'stop_lines':['any wording implying buy/sell/deploy/do-not-touch authority','portfolio/cash/sizing/risk-rule linkage','trade/account/paper/live implication']
    },
    {
      'phase':'10',
      'name':'Higher-risk family separation and activation taxonomy',
      'goal':'Classify remaining families into never-SQL-canon, proposal-only SQL staging, or future exact-gated metadata candidates.',
      'candidate_families':['entry/stop metadata','sizing/sleeve/cash/weight metadata','risk-rule metadata','trade/account/paper/live execution metadata','credential/config metadata'],
      'work_packages':['separate proof metadata from canonical/apply/execution surfaces','map each family to owner surface and validator','define exact stop lines and allowed output types','avoid broad full-migration language for unsafe families'],
      'acceptance':['taxonomy artifact has per-family authority class, owner, validator, and route','no execution/account/config/credential family enters SQL-canon authority','portfolio mutation families remain gated apply/proposal only'],
      'stop_lines':['SQL row as approval/apply source','credential/config exposure','execution entitlement']
    },
    {
      'phase':'11',
      'name':'Full activation readiness packet',
      'goal':'Assemble final readiness proof for all approved/held/rejected SQL-canon families without silently widening authority.',
      'candidate_outputs':['full activation readiness matrix','guard/test coverage matrix','rollback/export drills','dashboard/Today/run-summary no-drift proof','continuity/Active Workflows update'],
      'acceptance':['all active keys have fallback map and value-equality guard','all held/rejected keys named with reasons','all validators pass','rollback drill uses temp copy','no authority flags widened','next phase requires exact approval if any new family moves'],
      'stop_lines':['unbounded full migration claim','cron-direct canon/apply','Markdown/canon/portfolio mutation without gated apply','trade/account/paper/live authority']
    }
  ],
  'global_boundaries':{
    'canonical_note_mutation_allowed':False,
    'portfolio_mutation_allowed':False,
    'owner_approval_inferred':False,
    'cron_direct_apply_allowed':False,
    'dashboard_recommendation_deployment_action_state_behavior_change_allowed':False,
    'trade_or_account_action_allowed':False,
    'paper_trade_authority_allowed':False,
    'live_trade_authority_allowed':False,
    'money_movement_allowed':False,
    'config_auth_channel_service_mutation_allowed':False
  },
  'recommended_next_action':'Start Phase 8 with a bounded adjudication/proof lane for portfolio:source_freshness_classification only; do not touch deployment/status or higher-risk families in the same write pass.'
}
Path('tmp/wf72-phases-8-11-full-activation-readiness-plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n',encoding='utf-8')
md=['# WF72 Phases 8-11 Full Activation Readiness Plan','',f"- Status: `{plan['status']}`",f"- Current active SQL-canon keys: `{plan['current_active_sql_canon']['key_count']}`",f"- Boundary: `{plan['current_active_sql_canon']['boundary']}`",'', '## Phases']
for ph in plan['phases']:
    md += ['', f"### Phase {ph['phase']} - {ph['name']}", '', f"Goal: {ph['goal']}", '', '**Acceptance**']
    for a in ph['acceptance']:
        md.append(f'- {a}')
    md += ['', '**Stop lines**']
    for s in ph['stop_lines']:
        md.append(f'- {s}')
md += ['', '## Recommended next action', '', plan['recommended_next_action']]
Path('tmp/wf72-phases-8-11-full-activation-readiness-plan.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print(plan['status'])
