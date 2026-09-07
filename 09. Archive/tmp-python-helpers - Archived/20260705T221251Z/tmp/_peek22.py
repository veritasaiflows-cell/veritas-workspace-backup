import json, collections
dpath = "data/state-history/outcome-ledger-v2.jsonl"
lines = [l for l in open(dpath,"r",encoding="utf-8").read().splitlines() if l.strip()]
print("Total durable rows:", len(lines))
print()

# Scoreable = non-recommendation_tracking events (these are decisions, not metadata)
fams = collections.Counter()
tickers = collections.Counter()
scoreable = []
all_decisions = []
for i, line in enumerate(lines):
    j = json.loads(line)
    ef = j.get("event_family") or j.get("family") or "?"
    sub = j.get("event_subtype") or j.get("subtype") or "?"
    tk = j.get("ticker") or "?"
    fams[(ef, sub)] += 1
    tickers[tk] += 1
    if ef != "recommendation_tracking":
        scoreable.append({"row_index": i, "ticker": tk, "ef": ef, "sub": sub, "rid": j.get("ledger_event_id","?"), "ts": j.get("recorded_at_utc","?")})
    all_decisions.append({"row_index": i, "ticker": tk, "ef": ef, "sub": sub, "ts": j.get("recorded_at_utc","?")})

print("FAMILY / SUBTYPE breakdown (ALL 32):")
for (f, s), c in fams.most_common():
    print(f"  ({c:>3}) {f} / {s}")

print()
print("Ticker breakdown:")
for t, c in tickers.most_common():
    print(f"  ({c:>3}) {t}")

print()
print("SCOREABLE rows (excluding recommendation_tracking):", len(scoreable))
print()
for r in scoreable:
    print(f"  [{r['row_index']:>2}] {r['ticker']:<6} | {r['ef']:<22} | {r['sub']:<32} | {r['ts'][:10]} | {r['rid'][:14]}...")
