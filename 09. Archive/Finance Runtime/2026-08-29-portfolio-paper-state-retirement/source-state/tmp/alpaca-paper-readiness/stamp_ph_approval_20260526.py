import json
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(r'C:\Users\Veritas\.openclaw\workspace')
approval_text='Approved: buy 0.3 PH, limit day, limit 876.00 or better, max notional 300, source tmp/alpaca-paper-readiness/order-card.ph-tight-limit-2026-05-26T0659.json, after WF67 guards pass.'
paths=[
 'tmp/alpaca-paper-readiness/order-card.ph-tight-limit-2026-05-26T0659.json',
 'tmp/alpaca-paper-readiness/paper-trade-request.ph-tight-limit-2026-05-26T0659.json',
]
for rel in paths:
    p=ROOT/rel
    d=json.loads(p.read_text(encoding='utf-8'))
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    d['approved_at_utc']=now
    if 'order-card.' in rel:
        d['status']='approved_exact_order_pending_wf67_guards'
        d.setdefault('owner_approval',{})
        d['owner_approval'].update({'status':'approved_exact_order','approved_by':'Randall','approval_text':approval_text,'approved_at_utc':now})
    else:
        d.setdefault('source',{})
        d['source'].update({'exact_order_owner_approval_status':'approved_exact_order','approved_by':'Randall','exact_order_owner_approval_text':approval_text,'exact_order_owner_approval_at_utc':now})
    p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(rel, 'stamped')
