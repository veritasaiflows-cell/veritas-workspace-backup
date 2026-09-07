from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp'/'alpaca-paper-readiness'/'paper-submit-reconciliation.wf67-reviewed-packet-001.json'
PAPER='https://paper-api.alpaca.markets'
KEY='ALPACA_PAPER_API_KEY_ID'
SEC='ALPACA_PAPER_API_SECRET_KEY'
BAD=['ALPACA_API_KEY_ID','ALPACA_SECRET_KEY','APCA_API_KEY_ID','APCA_API_SECRET_KEY','ALPACA_LIVE_API_KEY_ID','ALPACA_LIVE_API_SECRET_KEY','APCA_LIVE_API_KEY_ID','APCA_LIVE_API_SECRET_KEY']
if any(os.environ.get(x) for x in BAD):
    raise SystemExit('blocked: ambiguous/live credential name present')
if not os.environ.get(KEY) or not os.environ.get(SEC):
    raise SystemExit('blocked: paper credentials absent')
s=requests.Session(); s.headers.update({'APCA-API-KEY-ID':os.environ[KEY], 'APCA-API-SECRET-KEY':os.environ[SEC], 'Accept':'application/json'})
r=s.get(PAPER+'/v2/orders', params={'status':'open','limit':50}, timeout=15)
r.raise_for_status()
orders=r.json()
matches=[]
for o in orders:
    if o.get('symbol')=='ETN' and o.get('side')=='buy' and o.get('type')=='limit' and o.get('time_in_force')=='day' and str(o.get('limit_price')).rstrip('0').rstrip('.')=='364.49':
        matches.append({
            'paper_order_id_present': bool(o.get('id')),
            'symbol': o.get('symbol'),
            'side': o.get('side'),
            'type': o.get('type'),
            'time_in_force': o.get('time_in_force'),
            'limit_price': o.get('limit_price'),
            'qty': o.get('qty'),
            'status': o.get('status'),
            'filled_qty': o.get('filled_qty'),
            'submitted_at': o.get('submitted_at'),
            'created_at': o.get('created_at'),
            'expires_at': o.get('expires_at'),
        })
report={
 'schema_version':1,
 'workflow':'WF67 - Alpaca Paper Execution Guardrail',
 'artifact_type':'wf67_paper_submit_reconciliation',
 'pilot_id':'wf67-reviewed-packet-001',
 'generated_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
 'status':'ok' if len(matches)==1 and matches[0].get('status') in {'accepted','new'} and str(matches[0].get('filled_qty')) in {'0','0.0','0.000000000'} else 'review_required',
 'summary':{'matching_open_orders':len(matches)},
 'observed_redacted':matches,
 'authority':{'paper_only':True,'live_trading_allowed':False,'live_endpoint_allowed':False,'money_movement_allowed':False,'account_settings_mutation_allowed':False,'no_inferred_approval':True},
 'redaction':{'secrets_persisted':False,'headers_persisted':False,'raw_response_bodies_persisted':False,'order_id_value_persisted':False},
 'source_artifacts':['tmp/alpaca-paper-readiness/paper-trade-request.wf67-reviewed-packet-001.json','tmp/alpaca-paper-readiness/paper-execution-result.json']
}
OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'output':'tmp/alpaca-paper-readiness/paper-submit-reconciliation.wf67-reviewed-packet-001.json','summary':report['summary']},indent=2))
