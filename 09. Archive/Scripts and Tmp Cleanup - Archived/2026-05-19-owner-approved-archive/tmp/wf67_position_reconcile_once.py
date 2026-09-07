from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp'/'alpaca-paper-readiness'/'paper-position-reconciliation.wf67-filled-position-001.json'
PAPER='https://paper-api.alpaca.markets'
KEY='ALPACA_PAPER_API_KEY_ID'; SEC='ALPACA_PAPER_API_SECRET_KEY'
BAD=['ALPACA_API_KEY_ID','ALPACA_SECRET_KEY','APCA_API_KEY_ID','APCA_API_SECRET_KEY','ALPACA_LIVE_API_KEY_ID','ALPACA_LIVE_API_SECRET_KEY','APCA_LIVE_API_KEY_ID','APCA_LIVE_API_SECRET_KEY']
if any(os.environ.get(x) for x in BAD): raise SystemExit('blocked: ambiguous/live credential name present')
if not os.environ.get(KEY) or not os.environ.get(SEC): raise SystemExit('blocked: paper credentials absent')
s=requests.Session(); s.headers.update({'APCA-API-KEY-ID':os.environ[KEY], 'APCA-API-SECRET-KEY':os.environ[SEC], 'Accept':'application/json'})
orders_resp=s.get(PAPER+'/v2/orders', params={'status':'all','limit':50}, timeout=15); orders_resp.raise_for_status()
pos_resp=s.get(PAPER+'/v2/positions', timeout=15); pos_resp.raise_for_status()
orders=[]
for o in orders_resp.json():
    if o.get('symbol')=='MSFT' and o.get('side')=='buy' and o.get('type')=='limit' and o.get('time_in_force')=='day' and str(o.get('limit_price')).rstrip('0').rstrip('.')=='499':
        orders.append({
            'paper_order_id_present': bool(o.get('id')),
            'symbol':o.get('symbol'),'side':o.get('side'),'type':o.get('type'),'time_in_force':o.get('time_in_force'),
            'limit_price':o.get('limit_price'),'qty':o.get('qty'),'status':o.get('status'),'filled_qty':o.get('filled_qty'),
            'filled_avg_price':o.get('filled_avg_price'),'submitted_at':o.get('submitted_at'),'filled_at':o.get('filled_at'),'expires_at':o.get('expires_at')})
positions=[]
for p in pos_resp.json():
    if p.get('symbol')=='MSFT':
        positions.append({'symbol':p.get('symbol'),'qty':p.get('qty'),'avg_entry_price':p.get('avg_entry_price'),'market_value':p.get('market_value'),'unrealized_pl':p.get('unrealized_pl'),'side':p.get('side')})
filled=any(str(o.get('filled_qty')) not in {'0','0.0','0.000000000','None'} and o.get('status') in {'filled','partially_filled'} for o in orders)
report={'schema_version':1,'workflow':'WF67 - Alpaca Paper Execution Guardrail','artifact_type':'wf67_paper_position_reconciliation','pilot_id':'wf67-filled-position-001','generated_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'status':'filled_position_observed' if filled and positions else ('accepted_unfilled' if orders else 'review_required'),'summary':{'matching_orders':len(orders),'matching_positions':len(positions),'filled_observed':filled},'orders_observed_redacted':orders,'positions_observed_redacted':positions,'authority':{'paper_only':True,'live_trading_allowed':False,'live_endpoint_allowed':False,'money_movement_allowed':False,'account_settings_mutation_allowed':False,'no_inferred_approval':True},'redaction':{'secrets_persisted':False,'headers_persisted':False,'raw_response_bodies_persisted':False,'order_id_value_persisted':False},'hold_policy':'If filled, leave the paper position open for monitoring until Randall explicitly instructs close/cancel/sell.'}
OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'output':'tmp/alpaca-paper-readiness/paper-position-reconciliation.wf67-filled-position-001.json','summary':report['summary']},indent=2))
