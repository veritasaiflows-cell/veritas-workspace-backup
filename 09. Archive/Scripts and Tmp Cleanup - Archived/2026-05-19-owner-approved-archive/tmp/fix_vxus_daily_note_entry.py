from pathlib import Path
p = Path('memory/2026-05-18.md')
t = p.read_text(encoding='utf-8')
start = t.find('- Added VXUS to')
if start == -1:
    raise SystemExit('VXUS entry not found')
end = t.find('\n-', start + 1)
if end == -1:
    end = len(t)
new = """- Added VXUS to `tmp/portfolio-config.json.tracked_universe` as review-only international ETF monitor/watch target after Randall approved closing the orphan. Updated Execution Board, Coverage and Watchlist, and Portfolio Snapshot with VXUS review-only status. Validation: `validate_portfolio_config.py --strict` now status ok with 0 warnings across 42 tickers; deployment_check/dashboard/watcher reran clean except dashboard's existing NVDA event-risk band freeze warning. Intraday watcher now shows ETN entry candidate; VXUS/PH/ITA review candidates; LIN near-band; warning_count 0. Boundary unchanged: no order, no sizing/sleeve/cash, no brokerage/account/money action, no owner approval inferred.
"""
t = t[:start] + new + (t[end+1:] if end < len(t) and t[end] == '\n' else t[end:])
p.write_text(t, encoding='utf-8')
print('fixed VXUS daily note entry')
