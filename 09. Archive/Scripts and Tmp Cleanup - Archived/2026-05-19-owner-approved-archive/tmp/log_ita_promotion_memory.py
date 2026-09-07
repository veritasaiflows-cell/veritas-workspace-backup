from pathlib import Path
p=Path('memory/2026-05-18.md')
t=p.read_text(encoding='utf-8')
entry = """- Promoted ITA to review-only candidate after Randall instruction at 2026-05-18 08:35 MST. Updated `tmp/portfolio-config.json`, `scripts/intraday_entry_watcher.py`, `03. Portfolio/Execution Board.md`, `04. Research/Coverage and Watchlist.md`, `03. Portfolio/Portfolio Snapshot.md`, combined summary, and ITA/VXUS packet; wrote `tmp/review-packets/ita-candidate-promotion-2026-05-18.md/.json` with authority boundary. Post-validation: JSON/py_compile clean; deployment_check now lists ITA under PROMOTION REVIEW and in band; dashboard validation 0 critical / 1 warning (existing NVDA event-risk band freeze); intraday watcher shows ITA `promotion_review_in_band` review candidate. Portfolio config strict validator still warns on pre-existing VXUS entry-band orphan; not changed in the ITA promotion pass. No paper/live order, sizing, sleeve, cash, brokerage/account action, money movement, or owner approval inferred.
"""
if 'ita-candidate-promotion-2026-05-18' not in t:
    t=t.rstrip()+'\n'+entry
p.write_text(t,encoding='utf-8')
print('memory logged')
