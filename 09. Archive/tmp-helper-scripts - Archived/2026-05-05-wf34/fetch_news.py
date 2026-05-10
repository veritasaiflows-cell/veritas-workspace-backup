import yfinance as yf
for t in ['ETN','AMD','SMCI']:
    print('---',t)
    tk=yf.Ticker(t)
    try:
        news=(tk.news or [])[:8]
        for n in news:
            c=n.get('content') or {}
            title=c.get('title') or n.get('title')
            url=(c.get('canonicalUrl') or {}).get('url') or n.get('link')
            pub=c.get('pubDate') or n.get('providerPublishTime')
            print(pub, title, url)
    except Exception as e:
        print('ERR',type(e).__name__,e)
