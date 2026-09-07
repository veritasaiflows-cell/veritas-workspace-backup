import json, re, html
from pathlib import Path
from datetime import datetime, timezone

# Load existing artifacts
watch=json.loads(Path('tmp/intraday-entry-watch.json').read_text(encoding='utf-8'))
cfg=json.loads(Path('tmp/portfolio-config.json').read_text(encoding='utf-8'))
ph_lin=json.loads(Path('tmp/review-packets/ph-lin-execution-readiness-packets.json').read_text(encoding='utf-8'))
ita_vxus=json.loads(Path('tmp/review-packets/ita-vxus-execution-readiness-packets.json').read_text(encoding='utf-8'))

# Parse ITA official BlackRock Excel-XML download with tolerant regex because the workbook has raw ampersands.
xml_text=Path('tmp/ita-blackrock-data-download.xlsx').read_text(encoding='utf-8',errors='ignore')
rows=[]
for row_m in re.finditer(r'<ss:Row>(.*?)</ss:Row>', xml_text, re.S):
    row_xml=row_m.group(1)
    vals=[]
    for data_m in re.finditer(r'<ss:Data[^>]*>(.*?)</ss:Data>', row_xml, re.S):
        vals.append(html.unescape(re.sub(r'<[^>]+>','',data_m.group(1)).strip()))
    if vals:
        rows.append(vals)
header_i=next((i for i,r in enumerate(rows) if r and r[0]=='Ticker'), None)
if header_i is None:
    raise RuntimeError('Could not locate ITA holdings header in BlackRock data download')
header=rows[header_i]
holdings=[]
for r in rows[header_i+1:]:
    if len(r) >= 6 and r[0] and r[0] not in ['Ticker']:
        try: weight=float(r[5])
        except Exception: continue
        holdings.append(dict(zip(header,r), Weight_pct=weight))
# Sort and extract
holdings=sorted(holdings, key=lambda x: x['Weight_pct'], reverse=True)
top10=holdings[:10]
lookup={h.get('Ticker'):h for h in holdings}
tracked_overlap={t: lookup[t]['Weight_pct'] for t in ['GE','RTX','LMT','KTOS'] if t in lookup}
top5_sum=sum(h['Weight_pct'] for h in holdings[:5])
top10_sum=sum(h['Weight_pct'] for h in holdings[:10])

# Current watch rows
watch_by_ticker={t['ticker']:t for t in watch.get('targets',[])}

def gate_state(ticker):
    w=watch_by_ticker.get(ticker,{})
    band=cfg.get('entry_bands',{}).get(ticker,{})
    tracked=cfg.get('tracked_universe',{}).get(ticker,{})
    return {
        'ticker': ticker,
        'price': w.get('price'),
        'price_source': w.get('price_source'),
        'entry_state': w.get('entry_state'),
        'alert_level': w.get('alert_level'),
        'distance_to_band_pct': w.get('distance_to_band_pct'),
        'entry_band': band,
        'workflow_state': tracked.get('workflow_state'),
        'coverage_lane': tracked.get('coverage_lane'),
        'portfolio_role': tracked.get('portfolio_role'),
        'deployment_or_trade_authority': False,
    }

# Official source notes captured via web_fetch/search and local downloads
official_sources={
    'LIN': [
        {'source':'Linde official IR/news page','url':'https://www.linde.com/news-and-media/2026/linde-reports-first-quarter-2026-results','captured':'web_fetch 2026-05-18'},
        {'source':'Linde official Q1 2026 release/tables PDF','url':'https://assets.linde.com/-/media/global/corporate/corporate/documents/press-releases/2026/linde-1q26-earnings-release-tables.pdf','local_file':'tmp/linde-1q26-earnings-release-tables.pdf'}
    ],
    'PH': [
        {'source':'Parker-Hannifin official IR press release','url':'https://investors.parker.com/news-events/press-releases/detail/499/parker-reports-fiscal-2026-second-quarter-results','captured':'web_fetch 2026-05-18'}
    ],
    'ITA': [
        {'source':'iShares official product page','url':'https://www.ishares.com/us/products/239502/ishares-us-aerospace-defense-etf','captured':'web_fetch + official BlackRock data download 2026-05-18'},
        {'source':'BlackRock official fund data download','url':'https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId=239502&component=fundDownload&userType=individual','local_file':'tmp/ita-blackrock-data-download.xlsx'},
        {'source':'iShares official fact sheet PDF','url':'https://www.ishares.com/us/literature/fact-sheet/ita-ishares-u-s-aerospace-defense-etf-fund-fact-sheet-en-us.pdf','local_file':'tmp/ita-ishares-fact-sheet.pdf'}
    ]
}

# Fundamental facts from official source excerpts already fetched in transcript
fundamental_updates={
    'LIN': {
        'official_q1_2026': {
            'reported_date':'2026-05-01',
            'net_income_millions':1857,
            'diluted_eps':3.98,
            'adjusted_net_income_millions':2019,
            'adjusted_net_income_yoy_pct':7,
            'diluted_eps_yoy_pct':13,
            'source_note':'DuckDuckGo snippet from Linde official PDF plus Linde official IR page; PDF locally captured but raw extraction is poor/encrypted-like, so retain manual-confirm flag for table-level reconciliation.'
        },
        '2025_sales_billions':34,
        'missing_or_manual': ['Full adjusted EPS/guidance table extraction from PDF remains manual because raw PDF extraction failed; official source captured, but table parsing is not clean.']
    },
    'PH': {
        'official_fy2026_q2': {
            'reported_date':'2026-01-29',
            'sales_billions':5.2,
            'sales_yoy_pct':9,
            'organic_sales_yoy_pct':6.6,
            'adjusted_eps':7.65,
            'adjusted_eps_yoy_pct':17,
            'segment_operating_margin_pct':23.9,
            'adjusted_segment_operating_margin_pct':27.1,
            'backlog_billions':11.7,
            'aerospace_backlog_billions':8.0,
            'orders_yoy_pct':9,
            'fy2026_adjusted_eps_guidance':'30.40-31.00',
            'fy2026_reported_sales_growth_guidance_pct':'5.5-7.5',
            'source_note':'Official Parker-Hannifin IR press release fetched 2026-05-18.'
        }
    },
    'ITA': {
        'official_ishares': {
            'objective':'Tracks an index of U.S. equities in the aerospace and defense sector; targeted exposure to domestic aerospace and defense companies.',
            'benchmark':'Dow Jones U.S. Select Aerospace & Defense Index',
            'expense_ratio_pct':0.38,
            'top_holdings_as_of':'2026-05-15',
            'top10_holdings':[{'ticker':h.get('Ticker'),'name':h.get('Name'),'weight_pct':round(h['Weight_pct'],4)} for h in top10],
            'top5_sum_pct':round(top5_sum,4),
            'top10_sum_pct':round(top10_sum,4),
            'overlap_watchlist_weights_pct':{k:round(v,4) for k,v in tracked_overlap.items()},
            'full_holding_count': len(holdings),
            'source_note':'Official BlackRock product page and data download captured 2026-05-18.'
        }
    }
}

# Portfolio concentration math under review-only planning sizes
planning_sizes={'LIN':5.4,'PH':5.0,'ITA':5.0}
current_industrials=7.0 # ETN per tmp/portfolio-config tactical
current_defense=12.0 # LMT 10 + KTOS 2 per tmp/portfolio-config
concentration={
    'LIN': {
        'planning_add_pct':5.4,
        'materials_pro_forma_pct':'current model materials not explicitly allocated in config; LIN would add 5.4% new Materials quality sleeve subject to 25% sector cap',
        'single_name_ceiling_check':'5.4% below 15% normal single-name ceiling; still requires owner sizing/sleeve/cash approval.'
    },
    'PH': {
        'planning_add_pct':5.0,
        'current_industrials_pct_from_config':current_industrials,
        'pro_forma_industrials_pct_if_ph_added':current_industrials+5.0,
        'incremental_overlap_note':'PH adds another industrial compounder beside ETN; ETN remains first-call because it is already deployable/in-band and directly tied to AI power/electrification.'
    },
    'ITA': {
        'planning_add_pct':5.0,
        'current_defense_pct_from_config':current_defense,
        'pro_forma_defense_aerospace_pct_if_ita_added':current_defense+5.0,
        'lookthrough_incremental_pct_at_5pct_notional':{k:round(v*0.05,4) for k,v in tracked_overlap.items()},
        'notable_top5_incremental_pct_at_5pct_notional':{h.get('Ticker'):round(h['Weight_pct']*0.05,4) for h in holdings[:5]},
        'sector_cap_check':'17% pro-forma Defense/Aerospace is below 25% sector cap, but LMT+KTOS+ITA look-through must remain explicitly accepted before any promotion.'
    }
}

verdicts={
    'LIN':'NOT PAPER-EXECUTION READY TODAY: official source captured and concentration is acceptable at review size, but current watcher says near/above band; no-chase. Needs price back inside approved band, clean table-level official reconciliation, fresh WF67 dry run, and exact owner order terms.',
    'PH':'NOT PAPER-EXECUTION READY TODAY: official PH IR evidence materially improves fundamental proof, and price is in band, but PH remains lower priority than ETN/LIN due to weaker technical posture/opportunity cost and industrial overlap. Needs owner promotion/sizing and WF67.',
    'ITA':'NOT PAPER-EXECUTION READY TODAY: official iShares holdings/expense/benchmark proof is now captured and the in-band state is real, but ITA remains watch-lane until main promotes it and accepts GE/RTX/LMT/KTOS look-through concentration. Needs WF67 and exact owner order terms.'
}

packet={
    'schema_version':1,
    'generated_at_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'LIN, ITA, and PH missing-info closeout for review-only paper-trade readiness preparation',
    'authority':{
        'review_only': True,
        'paper_order_authorized': False,
        'live_order_authorized': False,
        'brokerage_or_account_action_allowed': False,
        'money_movement_allowed': False,
        'canonical_portfolio_mutation_allowed': False,
        'owner_approval_inferred': False,
        'wf67_required_before_any_paper_execution': True,
        'exact_owner_order_terms_required': ['ticker','side','quantity_or_notional','limit_price','time_in_force']
    },
    'official_sources': official_sources,
    'current_price_and_band_state': {t:gate_state(t) for t in ['LIN','ITA','PH']},
    'fundamental_and_issuer_updates': fundamental_updates,
    'concentration_and_overlap': concentration,
    'readiness_verdicts': verdicts,
    'next_gate_to_be_tradable':{
        'LIN':['price at/below 506.11 upper band or fresh approved band','manual table-level Linde official PDF reconciliation','refresh quote/band','WF67 guard validation/dry run','explicit owner order terms'],
        'PH':['owner promotes PH over/alongside ETN industrial exposure','refresh quote/band and technical posture','confirm concentration/sizing/cash','WF67 guard validation/dry run','explicit owner order terms'],
        'ITA':['main-session promotion from ETF monitor/watch to paper candidate','accept official look-through concentration','refresh quote/band','WF67 guard validation/dry run','explicit owner order terms']
    }
}

Path('tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.json').write_text(json.dumps(packet,indent=2),encoding='utf-8')

md=[]
md.append('# LIN / ITA / PH Missing-Info Closeout - Review Only\n')
md.append(f"Generated UTC: {packet['generated_at_utc']}\n")
md.append('## Authority\n- Review-only readiness preparation. No paper/live order, brokerage/account action, money movement, canonical portfolio mutation, sizing/cash/sleeve approval, or owner approval is authorized or inferred.\n- Any future paper trade still requires WF67 guard validation/dry run plus exact owner order terms.\n')
for t in ['LIN','PH','ITA']:
    md.append(f'## {t}\n')
    md.append(f"**Verdict:** {verdicts[t]}\n")
    md.append('### Current price/band state\n')
    g=gate_state(t)
    md.append(f"- Watcher price/state: {g.get('price')} / `{g.get('entry_state')}` / alert `{g.get('alert_level')}`; distance_to_band_pct={g.get('distance_to_band_pct')}\n")
    b=g.get('entry_band') or {}
    md.append(f"- Band/stop: {b.get('label')} / stop {b.get('stop_label') or b.get('stop')} (review/reference only).\n")
    md.append(f"- Workflow: {g.get('workflow_state')} / lane `{g.get('coverage_lane')}`; trade authority = false.\n")
    md.append('### Official evidence captured\n')
    for s in official_sources[t]:
        md.append(f"- {s['source']}: {s.get('url','')} {('('+s.get('local_file','')+')') if s.get('local_file') else ''}\n")
    md.append('### New evidence / concentration math\n')
    md.append('```json\n'+json.dumps(fundamental_updates[t],indent=2)+'\n```\n')
    md.append('```json\n'+json.dumps(concentration[t],indent=2)+'\n```\n')
    md.append('### Remaining gate to be tradable\n')
    for x in packet['next_gate_to_be_tradable'][t]: md.append(f'- {x}\n')
    md.append('\n')
md.append('## ITA official holdings look-through detail\n')
md.append(f"- Full holdings parsed from official BlackRock data download: {len(holdings)} rows. Top 5 sum {top5_sum:.2f}%; top 10 sum {top10_sum:.2f}%.\n")
md.append('| Rank | Ticker | Holding | Weight % |\n|---:|---|---|---:|\n')
for i,h in enumerate(top10,1): md.append(f"| {i} | {h.get('Ticker')} | {h.get('Name')} | {h['Weight_pct']:.2f} |\n")
md.append('\n')
Path('tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md').write_text(''.join(md),encoding='utf-8')

print('wrote closeout json/md')
print('ITA top10', [(h.get('Ticker'), h.get('Name'), round(h['Weight_pct'],2)) for h in top10])
