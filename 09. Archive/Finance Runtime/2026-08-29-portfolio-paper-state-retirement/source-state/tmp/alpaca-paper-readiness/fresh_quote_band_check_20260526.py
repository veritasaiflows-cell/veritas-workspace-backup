import json
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

ROOT = Path(r'C:\Users\Veritas\.openclaw\workspace')
requests = [
    ROOT / 'tmp/alpaca-paper-readiness/paper-trade-request.cme-starter-pending-2026-05-26.json',
    ROOT / 'tmp/alpaca-paper-readiness/paper-trade-request.ph-starter-pending-2026-05-26.json',
]

def safe_float(x):
    try:
        if x is None: return None
        return float(x)
    except Exception:
        return None

results=[]
for path in requests:
    req=json.loads(path.read_text(encoding='utf-8'))
    sym=req['order']['symbol']
    t=yf.Ticker(sym)
    hist=t.history(period='5d', interval='1m', prepost=True)
    source='1m_prepost'
    if hist.empty:
        hist=t.history(period='5d', interval='1d')
        source='1d'
    quote={}
    if not hist.empty:
        last=hist.iloc[-1]
        quote={
            'last_price': safe_float(last.get('Close')),
            'last_timestamp': str(hist.index[-1]),
            'last_open': safe_float(last.get('Open')),
            'last_high': safe_float(last.get('High')),
            'last_low': safe_float(last.get('Low')),
            'last_volume': safe_float(last.get('Volume')),
            'source': source,
        }
    info={}
    try:
        fast=t.fast_info
        info={k:safe_float(getattr(fast,k,None) if hasattr(fast,k) else fast.get(k)) for k in ['last_price','regular_market_previous_close','day_high','day_low','year_high','year_low']}
    except Exception as e:
        info={'error': type(e).__name__}
    price=quote.get('last_price') or info.get('last_price')
    low=safe_float(req['risk_check']['entry_band_low']); high=safe_float(req['risk_check']['entry_band_high']); stop=safe_float(req['risk_check']['stop'])
    if price is None:
        status='QUOTE_UNAVAILABLE'
    elif price < stop:
        status='STOP_BREACHED_BLOCK'
    elif price < low:
        status='BELOW_ENTRY_BAND_WAIT_FOR_RECLAIM'
    elif price <= high:
        status='IN_ENTRY_BAND'
    else:
        status='ABOVE_ENTRY_BAND_NO_CHASE'
    limit=safe_float(req['order']['limit_price'])
    results.append({
        'symbol': sym,
        'request_path': str(path.relative_to(ROOT)).replace('\\','/'),
        'fresh_quote': quote,
        'fast_info_redacted': info,
        'band': {'low': low, 'high': high, 'stop': stop},
        'proposed_order': {'side': req['order']['side'], 'type': req['order']['type'], 'time_in_force': req['order']['time_in_force'], 'limit_price': limit, 'qty': safe_float(req['order']['qty']), 'estimated_notional_from_limit': (safe_float(req['order']['qty']) or 0) * (limit or 0)},
        'band_status': status,
        'distance_to_band_low_pct': None if price is None or low is None else (price-low)/low,
        'distance_to_band_high_pct': None if price is None or high is None else (price-high)/high,
        'distance_to_stop_pct': None if price is None or stop is None else (price-stop)/stop,
        'ready_for_approval_card': status == 'IN_ENTRY_BAND',
    })
out={
    'artifact_type':'fresh_quote_band_check',
    'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
    'status':'ok' if all(r['fresh_quote'].get('last_price') for r in results) else 'partial',
    'paper_live_boundary': {'paper_only_readiness_check': True, 'submitted_order': False, 'cancelled_order': False, 'live_endpoint_used': False, 'account_mutation': False},
    'results': results,
}
print(json.dumps(out, indent=2, sort_keys=True))
