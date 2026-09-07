import json
import re
from pathlib import Path

ROOT = Path(r'C:\Users\Veritas\.openclaw\workspace')
board_path = ROOT / '03. Portfolio' / 'Execution Board.md'
config = json.loads((ROOT / 'tmp' / 'portfolio-config.json').read_text(encoding='utf-8'))
tech = json.loads((ROOT / 'tmp' / 'technical-refresh.json').read_text(encoding='utf-8'))

missing = ['PH','ITA','VXUS','PAVE','VAW','XLB','XLC','XLE','XLI']
tech_recs = {}
def walk(x):
    if isinstance(x, dict):
        t = x.get('ticker') or x.get('symbol')
        if isinstance(t, str) and len(x) >= len(tech_recs.get(t, {})):
            tech_recs[t] = x
        for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
walk(tech)

def money(v):
    try: return f'{float(v):.2f}'
    except Exception: return 'Underdefined'

def status_for(ticker, rec, meta):
    role = str(meta.get('portfolio_role',''))
    lane = str(meta.get('coverage_lane','watch'))
    if ticker == 'ITA':
        return 'Portfolio-review / promotion-review only; candidate review does not grant deployment, sizing, sleeve, cash, paper/live order, brokerage, account, or trade authority.'
    if ticker == 'VXUS':
        return 'ETF monitor / review-only international diversification target; no deployment, sizing, sleeve, cash, paper/live order, brokerage, account, or trade authority.'
    if role == 'portfolio_review_candidate':
        return 'Portfolio-review only; no deployment, sizing, sleeve, cash, paper/live order, brokerage, account, or trade authority.'
    if role == 'etf_monitor':
        return 'ETF monitor / watch-only; no deployment, sizing, sleeve, cash, paper/live order, brokerage, account, or trade authority.'
    return f'{lane or "watch"} lane / watch-only; no deployment, sizing, sleeve, cash, paper/live order, brokerage, account, or trade authority.'

text = board_path.read_text(encoding='utf-8')
existing = set(re.findall(r'^###\s+([A-Z][A-Z0-9.]*)\s*$', text, re.M))
sections = []
for ticker in missing:
    if ticker in existing:
        continue
    rec = tech_recs.get(ticker, {})
    band = config.get('entry_bands', {}).get(ticker, {})
    meta = config.get('tracked_universe', {}).get(ticker, {})
    close = money(rec.get('close'))
    d = rec.get('data_date') or '2026-05-18'
    low, high, stop = money(band.get('low')), money(band.get('high')), money(band.get('stop'))
    in_band = rec.get('in_entry_band')
    below_stop = rec.get('below_stop')
    if below_stop:
        setup = 'BELOW_STOP / repair reference'
    elif in_band:
        setup = 'IN_BAND / review reference'
    else:
        setup = 'OUT_OF_BAND / watch reference'
    sections.append(f'''---

### {ticker}
- Close: **{close}** *(technical refresh; {d} close)*
- 20 / 50 / 200-day: **{money(rec.get('ma20'))} / {money(rec.get('ma50'))} / {money(rec.get('ma200'))}**
- MA posture: **{rec.get('ma_posture') or 'Underdefined'}**.
- Reference entry band: **{low} to {high}** *(portfolio-config reference band; latest canon freshness sync 2026-05-18)*
- Explicit stop / invalidation: **{stop}**
- Reference-band authority: **reference only / no execution entitlement — {setup}**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **{status_for(ticker, rec, meta)}**
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **{d}**; parser-compatible section added by canon freshness sync 2026-05-18.
''')
if sections:
    text = text.rstrip() + '\n\n' + ''.join(sections).rstrip() + '\n'
    board_path.write_text(text, encoding='utf-8')
print(f'added_sections={len(sections)}')
