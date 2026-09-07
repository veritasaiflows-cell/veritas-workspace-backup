import json

with open('tmp/technical-refresh.json') as f:
    d = json.load(f)

tier_a = ['BRK.B','CME','ETN','GOOG','GS','ITA','JPM','LIN','LMT','META','MSFT','NVDA','PH','VRT','XOM']

print(f"Technical refresh generated: {d['generated_at_utc']}")
print(f"Last trading day: {d['last_trading_day']}")
print()
for r in d['records']:
    if r['ticker'] in tier_a:
        print(f"{r['ticker']}: close={r['close']} date={r['data_date']} in_band={r['in_entry_band']} below_stop={r['below_stop']} ma20={r['ma20']} ma50={r['ma50']} ma200={r['ma200']} posture={r['ma_posture']}")