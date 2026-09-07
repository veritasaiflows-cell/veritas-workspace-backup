import json
from pathlib import Path
close=json.loads(Path('tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.json').read_text(encoding='utf-8'))
# Update JSON packets with additive review-only closeout section
for path in ['tmp/review-packets/ph-lin-execution-readiness-packets.json','tmp/review-packets/ita-vxus-execution-readiness-packets.json']:
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    data['missing_info_closeout_2026_05_18']={
        'source_packet':'tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.json',
        'authority': close['authority'],
        'official_sources': {k:v for k,v in close['official_sources'].items() if (k in ['LIN','PH'] if 'ph-lin' in path else k=='ITA')},
        'current_price_and_band_state': {k:v for k,v in close['current_price_and_band_state'].items() if (k in ['LIN','PH'] if 'ph-lin' in path else k=='ITA')},
        'fundamental_and_issuer_updates': {k:v for k,v in close['fundamental_and_issuer_updates'].items() if (k in ['LIN','PH'] if 'ph-lin' in path else k=='ITA')},
        'concentration_and_overlap': {k:v for k,v in close['concentration_and_overlap'].items() if (k in ['LIN','PH'] if 'ph-lin' in path else k=='ITA')},
        'readiness_verdicts': {k:v for k,v in close['readiness_verdicts'].items() if (k in ['LIN','PH'] if 'ph-lin' in path else k=='ITA')},
    }
    Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8')
# Append to markdown packets if not already present
for path, tickers in [('tmp/review-packets/ph-lin-execution-readiness-packets.md',['LIN','PH']),('tmp/review-packets/ita-vxus-execution-readiness-packets.md',['ITA'])]:
    p=Path(path); txt=p.read_text(encoding='utf-8')
    marker='## 2026-05-18 Missing-info closeout update'
    if marker not in txt:
        add=['\n\n'+marker+'\n\nReview-only update; no order authority, owner approval, sizing, sleeve, cash, brokerage/account action, or paper/live execution is authorized. Full packet: `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md/.json`.\n']
        for t in tickers:
            add.append(f"\n### {t}\n")
            add.append(f"- Verdict: {close['readiness_verdicts'][t]}\n")
            g=close['current_price_and_band_state'][t]
            add.append(f"- Current watcher: price {g.get('price')}; state `{g.get('entry_state')}`; alert `{g.get('alert_level')}`; band {g.get('entry_band',{}).get('label')}; stop {g.get('entry_band',{}).get('stop_label') or g.get('entry_band',{}).get('stop')}.\n")
            add.append(f"- Official proof captured: {', '.join(s['source'] for s in close['official_sources'][t])}.\n")
            add.append(f"- Concentration/overlap: `{json.dumps(close['concentration_and_overlap'][t], separators=(',',':'))}`\n")
        p.write_text(txt+''.join(add),encoding='utf-8')
# Rewrite combined summary targeted sections
p=Path('tmp/review-packets/combined-execution-readiness-summary-2026-05-18.md')
txt=p.read_text(encoding='utf-8')
txt=txt.replace('None of the four is paper-execution ready yet. VXUS\'s two immediate proof gaps are now fixed for review, but execution remains blocked by owner/WF67 gates and remaining pro-forma risk work.', 'None of the four is paper-execution ready yet. VXUS proof gaps were fixed earlier; LIN/ITA/PH now also have review-only missing-info closeout proof, but execution remains blocked by owner/WF67 gates, no-chase/price posture, and promotion/sizing decisions.')
txt=txt.replace('| 2 | **LIN** | Blocked / conditional watch | Best single-name sequencing candidate; near band but above upper edge | No chase; needs official-source earnings/valuation/concentration proof and price inside band. |', '| 2 | **LIN** | Blocked / conditional watch | Official Linde IR source captured; near band but above upper edge | No chase; needs price inside band plus clean table-level official reconciliation and WF67/owner terms. |')
txt=txt.replace('| 3 | **ITA** | Blocked but tactically closer | In reference band, but watch-lane only | Needs official iShares holdings/look-through proof and main-session promotion from watch lane. |', '| 3 | **ITA** | Blocked but tactically closer | Official iShares/BlackRock holdings proof captured; in reference band | Needs main-session promotion and explicit acceptance of GE/RTX/LMT/KTOS look-through concentration. |')
txt=txt.replace('| 4 | **PH** | Blocked / conditional review | In band, but weaker posture vs LIN and ETN overlap hurdle | Needs official-source proof, valuation/concentration math, and stronger incremental case vs ETN/industrial exposure. |', '| 4 | **PH** | Blocked / conditional review | Official Parker IR proof captured; in band, but weaker posture vs LIN and ETN overlap hurdle | Needs owner promotion/sizing and a stronger incremental case vs ETN/industrial exposure. |')
txt=txt.replace('- **Official proof:** `tmp/review-packets/vxus-entry-band-official-proof-2026-05-18.md/.json`; Vanguard fact sheet as of 2026-03-31 captured top holdings, market allocation, sector diversification, 0.05% expense ratio, and non-U.S./currency/EM risk note.', '- **Official proof:** `tmp/review-packets/vxus-entry-band-official-proof-2026-05-18.md/.json`; Vanguard fact sheet as of 2026-03-31 captured top holdings, market allocation, sector diversification, 0.05% expense ratio, and non-U.S./currency/EM risk note.')
txt=txt.replace('- **Required before paper order:**\n  - official company IR / 10-Q / earnings release capture\n  - adjusted EPS/guidance/margin/FCF/leverage bridge', '- **Official proof update:** Linde official IR page and Q1 2026 PDF captured; official snippet shows Q1 2026 net income $1.857B, diluted EPS $3.98, adjusted net income $2.019B, adjusted net income +7% YoY, diluted EPS +13% YoY. PDF table extraction remains manual/dirty, so table-level reconciliation is still required.\n- **Required before paper order:**\n  - clean table-level adjusted EPS/guidance/margin/FCF/leverage bridge')
txt=txt.replace('- **Required before paper order:**\n  - official iShares holdings/fact-sheet capture\n  - top-constituent/contractor concentration and LMT/RTX/GE/KTOS overlap validator', '- **Official proof update:** iShares/BlackRock official product page, fact sheet, and fund data download captured. ITA tracks the Dow Jones U.S. Select Aerospace & Defense Index, expense ratio 0.38%, holdings as of 2026-05-15; top holdings GE 19.01%, RTX 14.79%, Boeing 9.94%, Howmet 5.12%, Rocket Lab 4.98%; LMT 3.93%, KTOS 0.82%.\n- **Required before paper order:**\n  - main-session promotion from watch/reference lane\n  - top-constituent/contractor concentration and LMT/RTX/GE/KTOS overlap acceptance')
txt=txt.replace('- **Required before paper order:**\n  - official company IR / 10-Q / earnings release capture\n  - adjusted EPS/guidance/orders/backlog/margin/FCF/leverage bridge', '- **Official proof update:** Parker official FY2026 Q2 release captured: sales $5.2B (+9%), organic sales +6.6%, adjusted EPS $7.65 (+17%), adjusted segment operating margin 27.1%, backlog $11.7B, aerospace backlog $8.0B, FY2026 adjusted EPS guidance $30.40-$31.00.\n- **Required before paper order:**\n  - valuation/orders/backlog/margin/FCF/leverage bridge')
if 'lin-ita-ph-missing-info-closeout-2026-05-18' not in txt:
    txt += '\n- `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md`\n- `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.json`\n'
p.write_text(txt,encoding='utf-8')
print('updated packet integrations')
