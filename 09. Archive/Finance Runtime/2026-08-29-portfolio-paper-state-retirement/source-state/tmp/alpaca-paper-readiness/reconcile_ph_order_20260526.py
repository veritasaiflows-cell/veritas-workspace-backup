import json, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path
BASE='https://paper-api.alpaca.markets'
KEY='ALPACA_PAPER_API_KEY_ID'; SECRET='ALPACA_PAPER_API_SECRET_KEY'
OUT=Path(r'C:\Users\Veritas\.openclaw\workspace\tmp\alpaca-paper-readiness\paper-order-reconciliation.ph-tight-limit-2026-05-26T0710.json')
headers={'APCA-API-KEY-ID':os.environ[KEY],'APCA-API-SECRET-KEY':os.environ[SECRET],'Accept':'application/json'}
def get(path):
    req=urllib.request.Request(BASE+path,headers=headers,method='GET')
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))
def pick_order(o):
    return {k:o.get(k) for k in ['symbol','side','qty','filled_qty','type','time_in_force','limit_price','status','submitted_at','filled_at','canceled_at','expired_at','created_at']}
def pick_pos(p):
    return {k:p.get(k) for k in ['symbol','qty','market_value','cost_basis','unrealized_pl','unrealized_plpc','current_price']}
orders=get('/v2/orders?status=all&limit=50&direction=desc')
positions=get('/v2/positions')
ph_orders=[pick_order(o) for o in orders if o.get('symbol')=='PH']
ph_positions=[pick_pos(p) for p in positions if p.get('symbol')=='PH']
out={'schema_version':1,'artifact_type':'wf67_paper_order_reconciliation','generated_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'status':'ok','base_url':BASE,'live_endpoint_used':False,'secrets_redacted':True,'raw_response_persisted':False,'ph_orders':ph_orders,'ph_positions':ph_positions,'authority':{'paper_only':True,'live_trading_allowed':False,'money_movement_allowed':False,'account_settings_mutation_allowed':False}}
OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'status':'ok','output':str(OUT),'ph_orders':ph_orders[:3],'ph_positions':ph_positions},indent=2))
