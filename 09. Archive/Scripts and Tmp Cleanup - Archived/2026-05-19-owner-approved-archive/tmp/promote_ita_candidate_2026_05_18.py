import json
from pathlib import Path
from datetime import datetime, timezone

# Bounded review-only promotion for ITA after Randall explicit instruction 2026-05-18 08:35 MST.
# No execution/sizing/cash/sleeve/order authority is granted.

root = Path('.')
config_path = root / 'tmp/portfolio-config.json'
backup = root / 'tmp/portfolio-config.before-ita-candidate-promotion-2026-05-18.json'
config = json.loads(config_path.read_text(encoding='utf-8'))
backup.write_text(json.dumps(config, indent=2), encoding='utf-8')
ita = config['tracked_universe']['ITA']
ita.update({
    'coverage_tier': 'event',
    'portfolio_role': 'portfolio_review_candidate',
    'sizing_tier': 'No sizing; portfolio-review candidate only; separate approved model/sleeve/sizing/cash gate required for any allocation',
    'workflow_state': 'PROMOTION REVIEW',
    'daily_technical_priority': True,
    'thesis_status': 'Owner-promoted 2026-05-18 to review-only paper-candidate queue after official iShares/BlackRock holdings proof; not execution-ready and no allocation/sizing/trade authority.',
    'macro_fit': 'Aerospace/defense ETF gap candidate while LMT/RTX/GE single-name paths remain repair/watch or unvalidated',
    'trigger_condition': 'Promotion-review only: reference band 212.15 to 223.44 with stop 205.88; in-band state supports candidate review but does not grant deployment, sizing, sleeve, cash, approval, paper/live order, brokerage, account, or trade authority.',
    'coverage_lane': 'promotion_review',
    'candidate_promoted_at': '2026-05-18T08:35:00-07:00',
    'candidate_promotion_source': 'Randall explicit instruction: promote ITA as a candidate',
    'promotion_scope': 'review_only_paper_candidate_no_deployment_sizing_sleeve_cash_or_trade_authority',
    'official_proof_packet': 'tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md',
    'lookthrough_summary': 'Official BlackRock holdings as of 2026-05-15: GE 19.01%, RTX 14.79%, BA 9.94%, LMT 3.93%, KTOS 0.82%; top 5 53.84%, top 10 74.76%; concentration acceptance required before any paper order.'
})
config['last_updated_by'] = 'Veritas - promoted ITA to review-only promotion-review/paper-candidate queue on 2026-05-18 after Randall instruction and official iShares/BlackRock holdings proof; no execution/sizing/sleeve/cash/trade authority.'
config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

# Intraday watcher queue should treat ITA as promotion_review rather than generic watch target.
script_path = root / 'scripts/intraday_entry_watcher.py'
script = script_path.read_text(encoding='utf-8')
old = '{"rank": 7, "ticker": "ITA", "role": "defense/aerospace ETF before GE", "mode": "watch_for_band"}'
new = '{"rank": 7, "ticker": "ITA", "role": "defense/aerospace ETF candidate before GE", "mode": "promotion_review"}'
if old not in script:
    raise SystemExit('ITA watcher queue line not found or already changed')
script_path.write_text(script.replace(old, new), encoding='utf-8')

# Execution Board table row.
exec_path = root / '03. Portfolio/Execution Board.md'
text = exec_path.read_text(encoding='utf-8')
old = '| ITA | ETF monitor | **Watch-only / ETF technical monitor** | 212.15-223.44 | 205.88 | Underdefined | Reference levels now defined; still requires review/promotion discipline before any deployment proposal. | Aerospace/defense gap monitor while LMT/RTX remain repair/watch. | tmp/portfolio-config.json + band-proposals/Veritas level pass 2026-05-15 | ETF Coverage Promotion Review 2026-05-15 |'
new = '| ITA | ETF candidate / promotion-review | **Portfolio-review only / ETF candidate in band** | 212.15-223.44 | 205.88 | In band; concentration-heavy | Randall promoted to candidate 2026-05-18 after official iShares/BlackRock holdings proof; still no execution entitlement. | Aerospace/defense gap candidate while LMT/RTX/GE single-name paths remain repair/watch; GE/RTX/BA concentration and LMT/KTOS look-through must be accepted before any paper order. | tmp/portfolio-config.json + ITA closeout proof 2026-05-18 | Randall instruction 2026-05-18 08:35 + tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18 |'
if old not in text:
    raise SystemExit('Execution Board ITA row not found or already changed')
exec_path.write_text(text.replace(old, new), encoding='utf-8')

# Coverage and Watchlist index/status/quick reference.
cov_path = root / '04. Research/Coverage and Watchlist.md'
text = cov_path.read_text(encoding='utf-8')
repls = {
'| ITA | ETF / Aerospace & Defense | ETF monitor | [[04. Research/ETF Coverage Promotion Review - 2026-05-15#ITA--iShares-US-Aerospace--Defense-ETF|Review section]] | [[03. Portfolio/Execution Board|Execution Board]] | ETF coverage promotion 2026-05-15 |':
'| ITA | ETF / Aerospace & Defense | Portfolio review candidate | [[04. Research/ETF Coverage Promotion Review - 2026-05-15#ITA--iShares-US-Aerospace--Defense-ETF|Review section]] + `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md` | [[03. Portfolio/Execution Board|Execution Board]] | Randall promoted candidate 2026-05-18; review-only |',
'### ITA — iShares US Aerospace & Defense ETF\n- **Tier:** ETF monitor\n- **Status:** Active aerospace/defense ETF monitor — review-only, no allocation authority\n- **Thesis:** Defense/aerospace proxy for monitoring the defense gap while LMT/RTX are repair or watch-state names and GE/other aerospace candidates are under review.\n- **Key risk:** Defense-budget politics, supply-chain execution, valuation, and overlap with existing defense/aerospace candidates.\n- **Act when:** Consider only after defense-gap review, risk-rule impact, and a separate proposal show ETF exposure is preferable to single-name repair risk.':
'### ITA — iShares US Aerospace & Defense ETF\n- **Tier:** Portfolio review candidate / ETF candidate\n- **Status:** Owner-promoted 2026-05-18 to review-only aerospace/defense ETF candidate; no allocation, sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.\n- **Thesis:** Defense/aerospace proxy for filling the defense gap while LMT/RTX/GE single-name paths remain repair/watch or unvalidated. Official iShares/BlackRock proof is captured.\n- **Key evidence:** Expense ratio 0.38%; tracks Dow Jones U.S. Select Aerospace & Defense Index; holdings as of 2026-05-15 include GE 19.01%, RTX 14.79%, BA 9.94%, LMT 3.93%, KTOS 0.82%; top 5 53.84%, top 10 74.76%.\n- **Key risk:** Concentrated top holdings, GE/RTX/BA exposure, defense-budget politics, supply-chain execution, valuation, and overlap with existing LMT/KTOS/RTX/GE watch paths.\n- **Act when:** Candidate review may proceed, but any paper order still requires concentration acceptance, fresh in-band quote, WF67 dry run/guard validation, and exact owner order terms.',
'| ITA | ETF / Aerospace & Defense | Aerospace/defense gap ETF monitor | Promote only after defense concentration and valuation review |':
'| ITA | ETF / Aerospace & Defense | Aerospace/defense gap ETF candidate | Promoted 2026-05-18 to review-only candidate after official holdings proof; still requires concentration acceptance and WF67/owner terms before any paper order |',
'**ETF coverage review completed:** [[04. Research/ETF Coverage Promotion Review - 2026-05-15]]. XLI, XLB, XLC, PAVE, XLF, XLE, ITA, and VAW are now coverage-monitor ETFs only; technical levels remain underdefined until a fresh ETF technical refresh is run.':
'**ETF coverage review completed:** [[04. Research/ETF Coverage Promotion Review - 2026-05-15]]. XLI, XLB, XLC, PAVE, XLF, XLE, and VAW remain coverage-monitor ETFs only. **ITA was promoted by Randall on 2026-05-18 to review-only portfolio candidate** after official holdings proof; it remains non-executable without concentration acceptance, WF67 validation, and exact owner order terms.',
'| ITA | ETF / Aerospace & Defense | ETF monitor | Covered / monitoring only |':
'| ITA | ETF / Aerospace & Defense | Portfolio review candidate | Candidate / review-only; no execution authority |'
}
for old,new in repls.items():
    if old not in text:
        raise SystemExit(f'Coverage replacement not found: {old[:80]}')
    text = text.replace(old,new)
cov_path.write_text(text, encoding='utf-8')

# Portfolio Snapshot: add ITA to review queue and defense gap note.
snap_path = root / '03. Portfolio/Portfolio Snapshot.md'
text = snap_path.read_text(encoding='utf-8')
old = '| CME | Financial infrastructure diversifier | Valuation/rate-volatility regime fit; entry discipline required | [[04. Research/Sector Expansion Portfolio Promotion Review - 2026-05-15]] + Execution Board |'
new = old + '\n| ITA | Defense/aerospace ETF candidate | Concentrated GE/RTX/BA exposure; look-through acceptance required; no execution authority | `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md` + Execution Board |'
if old not in text:
    raise SystemExit('Portfolio Snapshot review queue anchor not found')
text = text.replace(old,new)
old = "- Defense has a named gap: LMT's 10% draft weight is suspended while in repair. Audit-remediation default recommendation is planning-only: LMT active model role 0% pending repair, validate a Defense/aerospace ETF role, and cap KTOS as a small speculative placeholder unless Randall chooses otherwise. No canonical model apply has occurred."
new = "- Defense has a named gap: LMT's 10% draft weight is suspended while in repair. Randall promoted ITA on 2026-05-18 to review-only Defense/aerospace ETF candidate after official holdings proof, but no canonical model apply, sizing, sleeve, cash, paper/live order, brokerage/account action, or execution authority has occurred; concentration acceptance remains required."
if old not in text:
    raise SystemExit('Portfolio Snapshot defense gap note not found')
text = text.replace(old,new)
snap_path.write_text(text, encoding='utf-8')
print('ITA candidate promotion applied; backup:', backup)
