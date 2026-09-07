import json
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(r'C:\Users\Veritas\.openclaw\workspace')
ledger=ROOT/'tmp/alpaca-paper-readiness/paper-trading-feedback-ledger.json'
recon=ROOT/'tmp/alpaca-paper-readiness/paper-order-reconciliation.ph-tight-limit-2026-05-26T0710.json'
d=json.loads(ledger.read_text(encoding='utf-8'))
r=json.loads(recon.read_text(encoding='utf-8'))
order=r['ph_orders'][0]
pos=r['ph_positions'][0]
entry={
  'ledger_id':'paper-feedback-ph-2026-05-26-tight-limit',
  'symbol':'PH',
  'company':'Parker-Hannifin Corporation',
  'paper_account_only':True,
  'status':'open_paper_position_observed_from_read_only_check',
  'side':'buy',
  'qty':float(order['qty']),
  'order_type':order['type'],
  'time_in_force':order['time_in_force'],
  'submitted_at_utc':order['submitted_at'],
  'filled_at_utc':order['filled_at'],
  'limit_price':float(order['limit_price']),
  'cost_basis':float(pos['cost_basis']),
  'entry_reference':{
    'fresh_quote_before_execution':873.92,
    'gated_band_low':851.36,
    'gated_band_high':908.98,
    'explicit_stop':819.35,
    'band_status_at_entry':'IN_ENTRY_BAND',
    'below_stop_at_entry':False,
    'limit_preserved_no_chase_vs_upper_band':True
  },
  'source_artifacts':{
    'order_card':'tmp/alpaca-paper-readiness/order-card.ph-tight-limit-2026-05-26T0659.json',
    'request':'tmp/alpaca-paper-readiness/paper-trade-request.ph-tight-limit-2026-05-26T0659.json',
    'dry_run':'tmp/alpaca-paper-readiness/paper-execution-dry-run-result.ph-tight-limit-2026-05-26T0708.json',
    'guard_validation_pre_submit':'tmp/alpaca-paper-readiness/paper-execution-guard-validation.ph-tight-limit-2026-05-26T0708.json',
    'execution_result':'tmp/alpaca-paper-readiness/paper-execution-result.ph-tight-limit-2026-05-26T0709.json',
    'guard_validation_post_submit':'tmp/alpaca-paper-readiness/paper-execution-guard-validation.ph-tight-limit-2026-05-26T0709-post-submit.json',
    'reconciliation':'tmp/alpaca-paper-readiness/paper-order-reconciliation.ph-tight-limit-2026-05-26T0710.json'
  },
  'thesis_at_entry':{
    'summary':'PH is a quality industrial diversifier candidate; starter is intentionally small because it overlaps Industrials and sits behind stronger priority candidates.',
    'portfolio_role':'Paper simulation only; not live capital, not authority to scale, and not a canonical portfolio mutation.'
  },
  'stop_behavior':{
    'paper_stop_level':819.35,
    'paper_stop_policy':'Review if PH closes below stop or breaks materially below stop intraday. This ledger does not auto-submit a paper sell/close.'
  },
  'feedback_metrics':{
    'current_unrealized_pnl_usd':float(pos['unrealized_pl']),
    'current_unrealized_pnl_pct':float(pos['unrealized_plpc']),
    'last_price_checked':float(pos['current_price']),
    'last_price_checked_at_utc':r['generated_at_utc']
  },
  'authority_boundary':'Review-only paper feedback. No live trade/account action, money movement, portfolio/canon/sizing/cash/risk-rule mutation, owner approval inference, or auto-exit authority.'
}
d['positions']=[p for p in d.get('positions',[]) if p.get('ledger_id')!=entry['ledger_id']]
d['positions'].append(entry)
d['generated_at_utc']=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
ledger.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'tmp/alpaca-paper-readiness/paper-trading-feedback-ledger-2026-05-26.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'status':'ok','positions':len(d['positions']),'added':entry['ledger_id']},indent=2))
