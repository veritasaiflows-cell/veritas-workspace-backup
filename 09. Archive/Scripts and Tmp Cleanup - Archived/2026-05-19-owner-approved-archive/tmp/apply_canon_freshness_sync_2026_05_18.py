import json
import re
from pathlib import Path

ROOT = Path(r'C:\Users\Veritas\.openclaw\workspace')
board_path = ROOT / '03. Portfolio' / 'Execution Board.md'
snapshot_path = ROOT / '03. Portfolio' / 'Portfolio Snapshot.md'
config_path = ROOT / 'tmp' / 'portfolio-config.json'
tech_path = ROOT / 'tmp' / 'technical-refresh.json'

config = json.loads(config_path.read_text(encoding='utf-8'))
tech = json.loads(tech_path.read_text(encoding='utf-8'))

tech_recs = {}
def walk(x):
    if isinstance(x, dict):
        t = x.get('ticker') or x.get('symbol')
        if isinstance(t, str):
            if len(x) >= len(tech_recs.get(t, {})):
                tech_recs[t] = x
        for v in x.values():
            walk(v)
    elif isinstance(x, list):
        for v in x:
            walk(v)
walk(tech)

# Repair stale numeric prose in portfolio-config without changing authority/sizing/sleeves.
tracked = config.get('tracked_universe', {})
updates = {
    'GOOG': 'Pullback into 354.05 to 377.00 with the post-print structure holding; no chase after the earnings gap; no automatic execution or sizing authority.',
    'VRT': 'Reference band 306.85 to 338.33 with stop 291.11; ETN remains the primary AI-power execution name, and VRT requires research/promotion before any deployment, sizing, sleeve, cash, or trade authority.',
    'GS': 'Pullback into 894.64 to 935.77 with stop 866.76; secondary to JPM until promoted/sized, with bank-specific fundamentals review required before any Financials execution promotion; no automatic execution or sizing authority.',
}
for ticker, text in updates.items():
    if ticker in tracked:
        tracked[ticker]['trigger_condition'] = text
        tracked[ticker]['last_text_sync'] = '2026-05-18 trigger prose synced to current numeric entry_bands after canon drift freshness gate finding.'
config['last_updated_by'] = 'Veritas canon freshness sync 2026-05-18 (trigger prose only; no portfolio allocation/trade authority)'
config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

# Rebuild current execution table volatile technical columns from current artifacts.
text = board_path.read_text(encoding='utf-8')
lines = text.splitlines()
start = next(i for i, line in enumerate(lines) if line.strip() == '## Current execution table')
header = next(i for i in range(start, len(lines)) if lines[i].startswith('| Ticker | Lane | Action state |'))
end = header + 2
while end < len(lines) and lines[end].startswith('|'):
    end += 1

headers = [c.strip() for c in lines[header].strip('|').split('|')]
old_rows = []
for line in lines[header+2:end]:
    cells = [c.strip() for c in line.strip('|').split('|')]
    if len(cells) < len(headers):
        cells += [''] * (len(headers) - len(cells))
    old_rows.append(dict(zip(headers, cells[:len(headers)])))

def money(v):
    if isinstance(v, (int, float)):
        return f'{v:.2f}'
    try:
        return f'{float(v):.2f}'
    except Exception:
        return str(v) if v is not None else 'Underdefined'

def band_label(b):
    if not isinstance(b, dict):
        return 'Underdefined'
    return f"{money(b.get('low'))}-{money(b.get('high'))}"

def stop_label(b):
    if not isinstance(b, dict):
        return 'Underdefined'
    return money(b.get('stop'))

new_lines = lines[:header+2]
for row in old_rows:
    ticker = re.sub(r'[*`\s]', '', row.get('Ticker', ''))
    rec = tech_recs.get(ticker, {})
    band = config.get('entry_bands', {}).get(ticker)
    if rec:
        close = money(rec.get('close'))
        d = rec.get('data_date') or '2026-05-18'
        row['Close/date'] = f'{close} / {d}'
        row['Technical posture'] = rec.get('ma_posture') or row.get('Technical posture') or 'Underdefined'
    if band:
        row['Band'] = band_label(band)
        row['Stop'] = stop_label(band)
    if rec or band:
        date = rec.get('data_date') if rec else '2026-05-18'
        row['Source/freshness'] = f'tmp/technical-refresh.json + tmp/portfolio-config.json {date}; canon freshness sync 2026-05-18'
    # Preserve action/blocker/authority exactly; only volatile proof/date/level columns are refreshed.
    new_lines.append('| ' + ' | '.join(row.get(h, '') for h in headers) + ' |')
new_lines.extend(lines[end:])
board_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')

# Refresh Snapshot header only; posture/weights/cash remain unchanged and Execution Board owns levels.
snap = snapshot_path.read_text(encoding='utf-8')
snap = re.sub(r'- \*\*Date:\*\* 20\d{2}-\d{2}-\d{2}', '- **Date:** 2026-05-18', snap, count=1)
snap = re.sub(r'- \*\*Data as of:\*\* 20\d{2}-\d{2}-\d{2} close', '- **Data as of:** 2026-05-18 close', snap, count=1)
snapshot_path.write_text(snap, encoding='utf-8')

print('canon freshness sync applied: board volatile columns, snapshot header dates, config trigger prose for GOOG/VRT/GS')
