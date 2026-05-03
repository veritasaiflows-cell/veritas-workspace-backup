import json, statistics
from pathlib import Path
p=Path(r'C:\Users\Veritas2.0\.openclaw\workspace\tmp\refresh_technicals_raw.json')
data=json.loads(p.read_text())
for sym, rows in data.items():
    closes=[]
    highs=[]
    lows=[]
    for r in rows:
        closes.append(float(r['close'].replace('$','').replace(',','')))
        highs.append(float(r['high'].replace('$','').replace(',','')))
        lows.append(float(r['low'].replace('$','').replace(',','')))
    def sma(n): return round(sum(closes[:n])/n,2)
    print(sym, {'close': closes[0], 'sma20': sma(20), 'sma50': sma(50), 'sma200': sma(200), 'high5': round(max(highs[:5]),2), 'low5': round(min(lows[:5]),2), 'high20': round(max(highs[:20]),2), 'low20': round(min(lows[:20]),2)})
