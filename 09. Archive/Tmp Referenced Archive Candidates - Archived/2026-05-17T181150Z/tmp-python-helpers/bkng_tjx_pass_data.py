import json, math
from pathlib import Path
import yfinance as yf

out={}
for t in ['BKNG','TJX']:
    tk=yf.Ticker(t)
    info=tk.get_info()
    hist=tk.history(period='1y', auto_adjust=False)
    close=float(hist['Close'].iloc[-1])
    def f(x):
        if x is None: return None
        try:
            if math.isnan(x) or math.isinf(x): return None
        except TypeError:
            pass
        return float(x) if isinstance(x,(int,float)) else x
    closes=hist['Close']
    highs=hist['High']; lows=hist['Low']
    def ma(n): return float(closes.tail(n).mean())
    def slope(n,lag=10):
        if len(closes)<n+lag: return None
        return float(closes.tail(n).mean() - closes.iloc[-(n+lag):-lag].mean())
    recent20_low=float(lows.tail(20).min()); recent20_high=float(highs.tail(20).max())
    recent50_low=float(lows.tail(50).min()); recent50_high=float(highs.tail(50).max())
    # entry band: near support cluster, bounded by recent low and 50dma/200dma context
    if t=='BKNG':
        entry_low=round(max(recent20_low, close*0.965),2)
        entry_high=round(min(ma(50), close*1.03),2)
        stop=round(min(recent50_low, close*0.94),2)
    else:
        entry_low=round(max(ma(200), recent20_low, close*0.97),2)
        entry_high=round(min(ma(50), close*1.025),2)
        stop=round(min(ma(200)*0.97, recent50_low),2)
    try:
        cal=tk.calendar
        calendar=str(cal)
    except Exception as e:
        calendar=f'calendar_error: {e}'
    out[t]={
        'name':info.get('longName'), 'exchange': info.get('exchange'), 'country': info.get('country'),
        'sector':info.get('sector'),'industry':info.get('industry'),
        'market_cap':f(info.get('marketCap')),'trailing_pe':f(info.get('trailingPE')),'forward_pe':f(info.get('forwardPE')),'ps_ttm':f(info.get('priceToSalesTrailing12Months')),
        'profit_margin':f(info.get('profitMargins')),'operating_margin':f(info.get('operatingMargins')),'roe':f(info.get('returnOnEquity')),'roa':f(info.get('returnOnAssets')),
        'total_debt':f(info.get('totalDebt')),'total_cash':f(info.get('totalCash')),'operating_cashflow':f(info.get('operatingCashflow')),'free_cashflow':f(info.get('freeCashflow')),
        'revenue_growth':f(info.get('revenueGrowth')),'earnings_growth':f(info.get('earningsGrowth')),
        'last_date':str(hist.index[-1].date()),'close':close,
        'ma20':ma(20),'ma50':ma(50),'ma200':ma(200),
        'ma20_slope_10d':slope(20),'ma50_slope_10d':slope(50),'ma200_slope_10d':slope(200) if len(closes)>=210 else None,
        'above20':close>ma(20),'above50':close>ma(50),'above200':close>ma(200),
        'ret5_pct':float((close/closes.iloc[-6]-1)*100),'ret20_pct':float((close/closes.iloc[-21]-1)*100),'ret63_pct':float((close/closes.iloc[-64]-1)*100),
        'recent20_low':recent20_low,'recent20_high':recent20_high,'recent50_low':recent50_low,'recent50_high':recent50_high,
        'proposed_entry_low':entry_low,'proposed_entry_high':entry_high,'proposed_stop':stop,
        'calendar_raw': calendar[:1000]
    }
Path('tmp/bkng-tjx-fundamental-technical-data.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
