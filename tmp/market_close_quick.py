import json
from datetime import datetime
try:
    import yfinance as yf
except Exception as e:
    print(json.dumps({'error': f'yfinance import failed: {e}'}))
    raise SystemExit(0)

tickers = {
    '^GSPC':'S&P 500','^IXIC':'Nasdaq Composite','^DJI':'Dow','^RUT':'Russell 2000','SPY':'SPY','QQQ':'QQQ','IWM':'IWM','XLK':'Technology','XLF':'Financials','XLI':'Industrials','XLE':'Energy','XLV':'Health Care','XLY':'Consumer Disc.','XLP':'Consumer Staples','XLU':'Utilities','XLC':'Communication Svcs','XLB':'Materials','XLRE':'Real Estate','ETN':'ETN','JPM':'JPM','GS':'GS','GOOG':'GOOG','MSFT':'MSFT','NVDA':'NVDA','BRK-B':'BRK.B','LMT':'LMT','XOM':'XOM','LLY':'LLY','CAT':'CAT','VRT':'VRT','LNG':'LNG'
}
out = {'generated_at_utc': datetime.utcnow().isoformat()+'Z', 'records': []}
for t,label in tickers.items():
    try:
        hist = yf.Ticker(t).history(period='7d', interval='1d', auto_adjust=False)
        if hist is None or len(hist) < 2:
            out['records'].append({'ticker': t, 'label': label, 'error': 'insufficient history'})
            continue
        hist = hist.dropna(subset=['Close'])
        last = hist.iloc[-1]
        prev = hist.iloc[-2]
        close = float(last['Close'])
        prev_close = float(prev['Close'])
        out['records'].append({
            'ticker': t, 'label': label,
            'date': str(hist.index[-1].date()),
            'close': round(close, 4),
            'prev_close': round(prev_close, 4),
            'change': round(close-prev_close, 4),
            'change_pct': round((close/prev_close-1)*100, 2),
            'volume': None if 'Volume' not in hist.columns else int(last['Volume'])
        })
    except Exception as e:
        out['records'].append({'ticker': t, 'label': label, 'error': str(e)})
print(json.dumps(out, indent=2))
