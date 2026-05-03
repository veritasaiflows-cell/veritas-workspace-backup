import json, urllib.request, ssl
symbols=['MSFT','JPM','GOOG','XOM','LMT','ETN','BRK.B','NVDA']
ssl._create_default_https_context = ssl._create_unverified_context
out={}
for sym in symbols:
    url=f'https://api.nasdaq.com/api/quote/{sym}/historical?assetclass=stocks&limit=260&fromdate=2025-04-19&todate=2026-04-19'
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data=json.load(r)
    out[sym]=data['data']['tradesTable']['rows']
print(json.dumps({k: v[:5] for k,v in out.items()}, indent=2))
open(r'C:\Users\Veritas2.0\.openclaw\workspace\tmp\refresh_technicals_raw.json','w',encoding='utf-8').write(json.dumps(out))
