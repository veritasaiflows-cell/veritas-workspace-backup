import json, collections

p = json.load(open("tmp/wf55-outcome-ledger-preview.json","r",encoding="utf-8"))
rows = p.get("preview_rows", [])

# Try to find the actual 22 from the durable v2 ledger first
dv = p.get("durable_v2_ledger", {})
print("DURABLE LEDGER row_count:", dv.get("row_count"))
print("DURABLE LEDGER ticker_count:", dv.get("ticker_count"))
print()

# Check data/state-history
import os
sh_path = p.get("state_history_path")
print("state_history_path:", sh_path)
if sh_path and os.path.exists(sh_path):
    lines = [l for l in open(sh_path,"r",encoding="utf-8").read().splitlines() if l.strip()]
    print("file rows:", len(lines))
    fams = collections.Counter()
    tickers = set()
    paper_rows = []
    rec_rows = []
    call_rows = []
    for line in lines:
        j = json.loads(line)
        fams[(j.get("event_family","?"), j.get("event_subtype","?"))] += 1
        t = j.get("ticker") or "?"
        tickers.add(t)
        ef = j.get("event_family","")
        if "paper" in ef.lower(): paper_rows.append(j)
        elif "recommend" in ef.lower(): rec_rows.append(j)
        elif "call" in ef.lower(): call_rows.append(j)
    print()
    print("DURABLE row breakdown by (family, subtype):")
    for (f,s), c in fams.most_common():
        print(f"  ({c:>3}) {f} / {s}")
    print()
    print("Unique tickers:", sorted(tickers), "count:", len(tickers))
    print()
    # The "scoreable" definition: typically paper_lifecycle events with outcome state
    print("PAPER lifecyle event tickers:")
    for r in paper_rows:
        print(f"  - {r.get('ticker')} | {r.get('event_subtype')} | {r.get('recorded_at_utc')} | {r.get('ledger_event_id','?')[:16]}")
    print()
    print("RECOMMENDATION TRACKING tickers (for context):")
    rec_tickers = collections.Counter(r["ticker"] for r in rec_rows)
    for t, c in rec_tickers.most_common():
        print(f"  ({c}) {t}")
