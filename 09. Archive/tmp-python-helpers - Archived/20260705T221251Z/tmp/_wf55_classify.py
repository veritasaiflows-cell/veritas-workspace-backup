import json, collections

p = json.load(open("tmp/wf55-outcome-ledger-preview.json","r",encoding="utf-8"))
rows = p.get("preview_rows", [])
print("Total preview rows:", len(rows))
print()

# Group: (ticker, event_family, event_subtype) — these are the scoreable decisions when durable
fam_sub = collections.Counter()
fam_tickers = collections.defaultdict(list)
scoreable_rows = []
all_rows = []

for r in rows:
    fam = r.get("event_family","?")
    sub = r.get("event_subtype","?")
    tk = r.get("ticker","?")
    key = f"{fam} / {sub}"
    fam_sub[key] += 1
    fam_tickers[key].append(tk)
    all_rows.append((tk, key, r.get("recorded_at_utc","?"), r.get("ledger_event_id","?")))
    # Consider scoreable if paper_lifecycle or recommendation (real decisions)
    if "paper" in fam.lower() or "decision" in fam.lower() or "outcome" in fam.lower() or "recommend" in fam.lower():
        scoreable_rows.append(r)

print("EVENT_FAMILY / EVENT_SUBTYPE counts:")
for k, c in fam_sub.most_common():
    print(f"  ({c:>3}) {k}")
    print(f"        tickers ({len(set(fam_tickers[k]))} unique): {sorted(set(fam_tickers[k]))}")

print()
print("SCOREABLE rows counted (paper/decision/outcome/recommend families):", len(scoreable_rows))
print()
# unique scoreable tickers
scoreable_tickers = sorted(set(r["ticker"] for r in scoreable_rows if r.get("ticker")))
print(f"SCOREABLE unique tickers ({len(scoreable_tickers)}): {scoreable_tickers}")
