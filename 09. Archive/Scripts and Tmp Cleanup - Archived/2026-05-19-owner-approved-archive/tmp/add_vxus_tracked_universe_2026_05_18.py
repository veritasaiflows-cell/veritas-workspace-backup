import json
from pathlib import Path

root = Path('.')
config_path = root / 'tmp/portfolio-config.json'
backup = root / 'tmp/portfolio-config.before-vxus-tracked-universe-2026-05-18.json'
config = json.loads(config_path.read_text(encoding='utf-8'))
backup.write_text(json.dumps(config, indent=2), encoding='utf-8')
if 'VXUS' in config.get('tracked_universe', {}):
    raise SystemExit('VXUS already in tracked_universe')
config['tracked_universe']['VXUS'] = {
    'yfinance': 'VXUS',
    'coverage_tier': 'watch',
    'portfolio_role': 'etf_monitor',
    'sector': 'International Equity',
    'sizing_tier': 'No sizing; review-only international ETF candidate; separate approved model/sleeve/sizing/cash gate required for any allocation',
    'workflow_state': 'WATCH',
    'daily_technical_priority': True,
    'entry_policy': 'band_defined',
    'earnings_policy': 'none',
    'repair_mode': False,
    'thesis_status': 'Added 2026-05-18 to tracked_universe to close entry-band orphan after official Vanguard proof and review-only band fix; not execution-ready and no allocation/sizing/trade authority.',
    'macro_fit': 'Core ex-U.S. diversification candidate to reduce U.S. large-cap/AI/quality concentration; carries currency, EM, China/Taiwan/Korea, and non-U.S. equity risk.',
    'trigger_condition': 'Review-only watch target: reference band 80.88 to 83.36 with stop/reference 78.15; no chase above upper band; no deployment, sizing, sleeve, cash, approval, paper/live order, brokerage, account, or trade authority.',
    'coverage_lane': 'watch',
    'machine_tracking_promoted_at': '2026-05-18T08:45:00-07:00',
    'promotion_scope': 'tracked_universe_cleanup_review_only_no_deployment_sizing_sleeve_cash_or_trade_authority',
    'technical_setup_defined_at': '2026-05-18T08:15:00-07:00',
    'official_proof_packet': 'tmp/review-packets/vxus-entry-band-official-proof-2026-05-18.md',
    'readiness_packet': 'tmp/review-packets/ita-vxus-execution-readiness-packets.md'
}
config['last_updated_by'] = 'Veritas - added VXUS to tracked_universe on 2026-05-18 to close entry-band orphan after official Vanguard proof/band fix; review-only, no execution/sizing/sleeve/cash/trade authority.'
config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

# Execution Board: add a VXUS row in ETF/watch section if absent.
exec_path = root / '03. Portfolio/Execution Board.md'
text = exec_path.read_text(encoding='utf-8')
if '| VXUS |' not in text:
    anchor = '| VAW | ETF monitor | **Watch-only / ETF technical monitor** | 225.44-233.7 | 220.85 | Underdefined | Reference levels now defined; still requires review/promotion discipline before any deployment proposal. | Broad Materials ETF alternative to XLB; needs fresh technicals and holdings review. | tmp/portfolio-config.json + band-proposals/Veritas level pass 2026-05-15 | ETF Coverage Promotion Review 2026-05-15 |'
    row = anchor + '\n| VXUS | ETF monitor / international diversification | **Review-only / ETF watch target** | 80.88-83.36 | 78.15 | Near/in band; no-chase above upper band | Added to tracked_universe 2026-05-18 to close band orphan after official Vanguard proof; still needs pro-forma country/currency/EM/overlap review before any paper order. | Core ex-U.S. diversification candidate; review-only and no deployment, sizing, sleeve, cash, approval, paper/live order, brokerage, account, or trade authority. | tmp/portfolio-config.json + VXUS official proof 2026-05-18 | tmp/review-packets/vxus-entry-band-official-proof-2026-05-18 + ITA/VXUS readiness packet |'
    if anchor not in text:
        raise SystemExit('Execution Board VAW anchor not found')
    text = text.replace(anchor, row)
    exec_path.write_text(text, encoding='utf-8')

# Coverage and Watchlist: add index row and parser-compatible section/quick references.
cov_path = root / '04. Research/Coverage and Watchlist.md'
text = cov_path.read_text(encoding='utf-8')
if '| VXUS |' not in text:
    anchor = '| VAW | ETF / Materials | ETF monitor | [[04. Research/ETF Coverage Promotion Review - 2026-05-15#VAW--Vanguard-Materials-ETF|Review section]] | [[03. Portfolio/Execution Board|Execution Board]] | ETF coverage promotion 2026-05-15 |'
    row = anchor + '\n| VXUS | ETF / International Equity | ETF monitor / review target | `tmp/review-packets/vxus-entry-band-official-proof-2026-05-18.md` | [[03. Portfolio/Execution Board|Execution Board]] | Added tracked-universe cleanup 2026-05-18; review-only |'
    if anchor not in text:
        raise SystemExit('Coverage index VAW anchor not found')
    text = text.replace(anchor, row)
    section_anchor = '### VAW — Vanguard Materials ETF\n- **Tier:** ETF monitor\n- **Status:** Active Materials ETF monitor — review-only, no allocation authority\n- **Thesis:** Alternative broad Materials proxy for comparing sector exposure, quality mix, and cost structure against XLB and single-name Materials candidates.\n- **Key risk:** Commodity cyclicality, lower single-name quality control, construction/industrial demand sensitivity, and overlap with LIN/ECL/VMC-style candidates.\n- **Act when:** Use only as a comparison or diversified Materials candidate after valuation, liquidity, sector breadth, and risk-rule checks support a separate proposal.'
    section = section_anchor + '\n\n---\n\n### VXUS — Vanguard Total International Stock ETF\n- **Tier:** ETF monitor / international diversification review target\n- **Status:** Added to tracked universe 2026-05-18 after official Vanguard proof and review-only band fix; no allocation, sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.\n- **Thesis:** One-ticket ex-U.S. equity diversifier that can reduce U.S. large-cap/AI/quality concentration if country, currency, EM, and overlap risks are accepted.\n- **Key evidence:** Official Vanguard fact sheet F3369 as of 2026-03-31; expense ratio 0.05%; top-ten holdings 11.7% of assets; key markets Japan 15.3%, UK 9.0%, Canada 8.3%, China 8.0%, Taiwan 7.0%; reference band 80.88-83.36, stop/reference 78.15.\n- **Key risk:** Currency, EM, China/Taiwan/Korea/geopolitical, lower non-U.S. profitability/shareholder-return profile, and hidden overlap with global financials/semis/industrials/materials.\n- **Act when:** Consider only after pro-forma country/currency/sector/overlap review, fresh in-band/no-chase quote, WF67 dry run/guard validation, and exact owner order terms.'
    if section_anchor not in text:
        raise SystemExit('Coverage VAW section anchor not found')
    text = text.replace(section_anchor, section)
    quick_anchor = '| VAW | ETF / Materials | Broad Materials ETF monitor | Promote only if broader Materials breadth is preferable to XLB concentration |'
    quick_row = quick_anchor + '\n| VXUS | ETF / International Equity | Core ex-U.S. diversification ETF monitor | Review after country/currency/EM/overlap validation; no execution authority |'
    if quick_anchor not in text:
        raise SystemExit('Coverage quick VAW anchor not found')
    text = text.replace(quick_anchor, quick_row)
    final_anchor = '| VAW | ETF / Materials | ETF monitor | Covered / monitoring only |'
    final_row = final_anchor + '\n| VXUS | ETF / International Equity | ETF monitor / review target | Covered / review-only; no execution authority |'
    if final_anchor not in text:
        raise SystemExit('Coverage final VAW anchor not found')
    text = text.replace(final_anchor, final_row)
    cov_path.write_text(text, encoding='utf-8')

# Portfolio Snapshot: add VXUS to watch now and update no model authority.
snap_path = root / '03. Portfolio/Portfolio Snapshot.md'
text = snap_path.read_text(encoding='utf-8')
if '| VXUS |' not in text:
    anchor = '| RTX | Defense below-stop repair monitor; no deployment entitlement | Coverage + Execution Board |'
    row = anchor + '\n| VXUS | International diversification ETF review target; official proof/band exist but pro-forma currency/EM/overlap review required | Coverage + Execution Board |'
    if anchor not in text:
        raise SystemExit('Snapshot watch anchor not found')
    text = text.replace(anchor, row)
    snap_path.write_text(text, encoding='utf-8')

print('VXUS tracked_universe cleanup applied; backup:', backup)
