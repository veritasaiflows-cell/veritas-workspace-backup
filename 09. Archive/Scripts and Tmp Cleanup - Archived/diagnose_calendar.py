"""diagnose_calendar.py -- temporary diagnostic

Dumps the raw yf.Ticker().calendar output for a few tickers so we can
see exactly what yfinance 1.3.0 returns and fix the parser.
"""
import yfinance as yf
import pprint

TEST_TICKERS = {"LMT": "LMT", "MSFT": "MSFT", "AMZN": "AMZN"}

for display, yt in TEST_TICKERS.items():
    print("=" * 60)
    print(f"  {display} ({yt})")
    print("=" * 60)
    t = yf.Ticker(yt)

    cal = t.calendar
    print(f"  type(calendar): {type(cal)}")
    print(f"  calendar value:")
    pprint.pprint(cal, indent=4)

    # Also try earnings_dates
    try:
        ed = t.earnings_dates
        print(f"\n  type(earnings_dates): {type(ed)}")
        if ed is not None and not (hasattr(ed, "empty") and ed.empty):
            print("  earnings_dates (first 3 rows):")
            print(ed.head(3))
        else:
            print("  earnings_dates: empty or None")
    except Exception as e:
        print(f"  earnings_dates error: {e}")

    print()
