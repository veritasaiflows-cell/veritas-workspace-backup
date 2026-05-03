"""diagnose.py — run this to see the actual yfinance error."""
import yfinance as yf
print(f"yfinance version: {yf.__version__}")
print("Attempting download of ETN (5d)...")
try:
    raw = yf.download("ETN", period="5d", interval="1d", progress=False, auto_adjust=True)
    print(f"  raw type: {type(raw)}")
    print(f"  raw shape: {raw.shape}")
    print(f"  raw columns: {list(raw.columns)}")
    print(f"  raw head:\n{raw}")
except Exception as e:
    print(f"  EXCEPTION: {type(e).__name__}: {e}")

print("\nAttempting Ticker().history for ETN...")
try:
    t = yf.Ticker("ETN")
    hist = t.history(period="5d")
    print(f"  hist type: {type(hist)}")
    print(f"  hist shape: {hist.shape}")
    print(f"  hist columns: {list(hist.columns)}")
    print(f"  hist head:\n{hist}")
except Exception as e:
    print(f"  EXCEPTION: {type(e).__name__}: {e}")
