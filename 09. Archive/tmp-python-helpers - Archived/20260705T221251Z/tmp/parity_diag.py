import re, sqlite3, pathlib
root = pathlib.Path(".")
board = (root/"03. Portfolio"/"Execution Board.md").read_text(encoding="utf-8")
band_re = re.compile(r"(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)")
num_re = re.compile(r"-?\d+(?:\.\d+)?")
def strip_md(v): return " ".join(v.replace("**","").replace("__","").split())
def parse_band(v):
    v=strip_md(v).replace(" to ","-"); m=band_re.search(v)
    return (float(m.group(1)),float(m.group(2))) if m else (None,None)
def parse_num(v):
    m=num_re.search(v.replace(",","")); return float(m.group()) if m else None
rows={}
in_table=False
for line in board.split("\n"):
    if line.startswith("| Ticker | Lane | Action state | Close/date | Band | Stop |"):
        in_table=True; continue
    if not in_table: continue
    if line.startswith("|---"): continue
    if not line.startswith("|"): break
    cells=[c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells)<10: continue
    t=strip_md(cells[0]).upper()
    bl,bh=parse_band(cells[4]); st=parse_num(cells[5])
    rows[t]=(bl,bh,st)
fin={}
for t,lo,hi,sp in sqlite3.connect("tmp/finance-intelligence-state.sqlite").execute("SELECT ticker,entry_band_low,entry_band_high,stop_or_invalidation FROM latest_valid_entry_stop_refs"):
    fin[t.upper()]=(lo,hi,sp)
canon={}
for scope,fn,fv in sqlite3.connect("tmp/veritas-canon-cache.sqlite").execute("SELECT scope,field_name,field_value FROM canon_cache_fields WHERE field_name IN ('reference_price_low','reference_price_high','reference_invalidation_level')"):
    canon.setdefault(scope.upper(),{})[fn]=fv
def close(a,b,tol=0.005):
    if a is None or b is None: return a is None and b is None
    try: b=float(b)
    except: return False
    return abs(a-b)<=tol
mismatch=[]
for t,(bl,bh,st) in sorted(rows.items()):
    f=fin.get(t); c=canon.get(t,{})
    bad=[]
    if not f: bad.append("MISSING_FINANCE")
    else:
        if not close(bl,f[0]): bad.append(f"fin_low md={bl} sql={f[0]}")
        if not close(bh,f[1]): bad.append(f"fin_high md={bh} sql={f[1]}")
        if not close(st,f[2]): bad.append(f"fin_stop md={st} sql={f[2]}")
    if not c: bad.append("MISSING_CANON")
    else:
        if not close(bl,c.get("reference_price_low")): bad.append(f"canon_low md={bl} sql={c.get('reference_price_low')}")
        if not close(bh,c.get("reference_price_high")): bad.append(f"canon_high md={bh} sql={c.get('reference_price_high')}")
        if not close(st,c.get("reference_invalidation_level")): bad.append(f"canon_stop md={st} sql={c.get('reference_invalidation_level')}")
    if bad: mismatch.append((t,bad))
print(f"markdown_rows={len(rows)} finance_rows={len(fin)} canon_tickers={len(canon)} mismatch_rows={len(mismatch)}")
for t,bad in mismatch:
    print(f"  {t}: "+" | ".join(bad))
