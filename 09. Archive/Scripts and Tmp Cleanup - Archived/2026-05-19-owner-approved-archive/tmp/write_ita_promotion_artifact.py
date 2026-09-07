import json
from pathlib import Path
from datetime import datetime, timezone
cfg=json.loads(Path('tmp/portfolio-config.json').read_text(encoding='utf-8'))
watch=json.loads(Path('tmp/intraday-entry-watch.json').read_text(encoding='utf-8'))
close=json.loads(Path('tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.json').read_text(encoding='utf-8'))
ita_cfg=cfg['tracked_universe']['ITA']
ita_watch=next((x for x in watch.get('targets',[]) if x.get('ticker')=='ITA'),{})
packet={
  'schema_version':1,
  'generated_at_utc':datetime.now(timezone.utc).isoformat(),
  'ticker':'ITA',
  'action':'promoted_to_review_only_candidate',
  'owner_instruction':'Randall: Okay, promote ITA as a candidate',
  'owner_instruction_time_local':'2026-05-18T08:35:00-07:00',
  'authority':{
    'review_only':True,
    'paper_order_authorized':False,
    'live_order_authorized':False,
    'brokerage_or_account_action_allowed':False,
    'money_movement_allowed':False,
    'sizing_sleeve_cash_authorized':False,
    'owner_approval_inferred':False,
    'wf67_required_before_any_paper_execution':True,
    'exact_owner_order_terms_required':['ticker','side','quantity_or_notional','limit_price','time_in_force']
  },
  'config_state_after':{
    'coverage_tier':ita_cfg.get('coverage_tier'),
    'portfolio_role':ita_cfg.get('portfolio_role'),
    'workflow_state':ita_cfg.get('workflow_state'),
    'coverage_lane':ita_cfg.get('coverage_lane'),
    'daily_technical_priority':ita_cfg.get('daily_technical_priority'),
    'sizing_tier':ita_cfg.get('sizing_tier'),
    'promotion_scope':ita_cfg.get('promotion_scope')
  },
  'band_and_price_after':{
    'band':cfg['entry_bands']['ITA'],
    'watcher_price':ita_watch.get('price'),
    'watcher_entry_state':ita_watch.get('entry_state'),
    'watcher_alert_level':ita_watch.get('alert_level'),
    'watcher_reasons':ita_watch.get('reasons')
  },
  'official_evidence':close['fundamental_and_issuer_updates']['ITA']['official_ishares'],
  'remaining_blockers':['explicit look-through concentration acceptance','fresh quote still inside band','WF67 dry run / guard validation / kill switch','exact owner paper-order terms if execution is desired']
}
Path('tmp/review-packets/ita-candidate-promotion-2026-05-18.json').write_text(json.dumps(packet,indent=2),encoding='utf-8')
md=f"""# ITA Candidate Promotion - Review Only\n\nGenerated UTC: {packet['generated_at_utc']}\n\n## Decision\nRandall promoted **ITA** to a review-only candidate on 2026-05-18 08:35 MST. This is **not** execution approval.\n\n## State after promotion\n- Coverage tier: `{ita_cfg.get('coverage_tier')}`\n- Portfolio role: `{ita_cfg.get('portfolio_role')}`\n- Workflow state: `{ita_cfg.get('workflow_state')}`\n- Coverage lane: `{ita_cfg.get('coverage_lane')}` — kept as `watch` because the config validator only allows execution/macro/speculative/watch lanes.\n- Sizing: `{ita_cfg.get('sizing_tier')}`\n- Band/stop: {cfg['entry_bands']['ITA'].get('label')} / {cfg['entry_bands']['ITA'].get('stop_label')}\n- Watcher: price {ita_watch.get('price')}, state `{ita_watch.get('entry_state')}`, alert `{ita_watch.get('alert_level')}`\n\n## Official evidence\n- Expense ratio: 0.38%\n- Benchmark: Dow Jones U.S. Select Aerospace & Defense Index\n- Holdings as of: 2026-05-15\n- Top 5 sum: 53.84%; top 10 sum: 74.76%\n- Key holdings: GE 19.01%, RTX 14.79%, BA 9.94%, LMT 3.93%, KTOS 0.82%\n\n## Remaining blockers\n- Explicit look-through concentration acceptance\n- Fresh quote still inside band\n- WF67 dry run / guard validation / kill switch\n- Exact owner paper-order terms if execution is desired\n\n## Authority boundary\nNo paper/live order, brokerage/account action, money movement, model sizing, sleeve, cash, or execution authority is granted or inferred.\n"""
Path('tmp/review-packets/ita-candidate-promotion-2026-05-18.md').write_text(md,encoding='utf-8')
print('wrote ITA promotion artifact')
