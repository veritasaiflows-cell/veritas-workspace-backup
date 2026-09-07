import yfinance as yf, pandas as pd, json, sys

def rsi(tkr, period=14):
    df = yf.download(tkr, period='3mo', interval='1d', progress=False, auto_adjust=True)
    if df.empty or 'Close' not in df.columns:
        return None
    close = df['Close'].squeeze()
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return round((100 - (100 / (1 + rs))).iloc[-1], 2)

tickers = sys.argv[1:]
out = {}
for t in tickers:
    try:
        out[t] = rsi(t)
    except Exception as e:
        out[t] = str(e)
print(json.dumps(out, indent=2))
