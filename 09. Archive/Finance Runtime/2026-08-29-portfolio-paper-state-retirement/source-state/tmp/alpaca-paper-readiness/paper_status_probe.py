import json, os, sys, urllib.request
from datetime import datetime, timezone
BASE='https://paper-api.alpaca.markets'
KEY='ALPACA_PAPER_API_KEY_ID'; SECRET='ALPACA_PAPER_API_SECRET_KEY'
if not os.environ.get(KEY) or not os.environ.get(SECRET):
    print(json.dumps({'status':'blocked','reason':'paper_credentials_absent'})); sys.exit(2)
headers={'APCA-API-KEY-ID':os.environ[KEY],'APCA-API-SECRET-KEY':os.environ[SECRET],'Accept':'application/json'}
def get(path):
    req=urllib.request.Request(BASE+path, headers=headers, method='GET')
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))
def pick_order(o):
    return {k:o.get(k) for k in ['symbol','side','qty','filled_qty','type','time_in_force','limit_price','status','submitted_at','filled_at','canceled_at','expired_at','created_at']}
def pick_pos(p):
    return {k:p.get(k) for k in ['symbol','qty','market_value','cost_basis','unrealized_pl','unrealized_plpc','current_price']}
orders=get('/v2/orders?status=all&limit=50&direction=desc')
positions=get('/v2/positions')
print(json.dumps({'status':'ok','generated_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'base_url':BASE,'orders':[pick_order(o) for o in orders],'positions':[pick_pos(p) for p in positions],'secrets_redacted':True,'raw_response_persisted':False}, indent=2, sort_keys=True))
