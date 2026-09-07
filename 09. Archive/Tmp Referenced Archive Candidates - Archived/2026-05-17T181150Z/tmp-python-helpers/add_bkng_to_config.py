import json
from collections import OrderedDict
from pathlib import Path
p=Path('tmp/portfolio-config.json')
data=json.loads(p.read_text(), object_pairs_hook=OrderedDict)
data['generated_at_utc']='2026-05-10T22:49:00Z'
data['last_updated_by']='Veritas - BKNG watchlist add approved by Randall on 2026-05-10'
tracked=data['tracked_universe']
bkng=OrderedDict([
    ('yfinance','BKNG'),
    ('coverage_tier','event'),
    ('portfolio_role','watch_only'),
    ('sector','Consumer Discretionary'),
    ('sizing_tier','Tier 1 only after technical repair and explicit promotion'),
    ('workflow_state','REPAIR'),
    ('daily_technical_priority',False),
    ('entry_policy','repair_mode'),
    ('earnings_policy','normal'),
    ('repair_mode',True),
    ('thesis_status','Consumer Discretionary Tier 1 research candidate approved for watchlist on 2026-05-10; no deployment authority'),
    ('macro_fit','Clean non-Tech Consumer Discretionary diversification candidate versus current Tech/AI-power concentration'),
    ('trigger_condition','No deployment while below the 20/50/200DMA structure; promotion-review requires reclaim and hold of 174-177 plus preserved 161-164 support and debt maturity / interest coverage review'),
    ('coverage_lane','watch'),
    ('post_research_review_date','2026-05-10'),
    ('last_earnings_date','2026-04-28'),
    ('next_earnings_date_provider_estimate','2026-07-29'),
    ('earnings_date_ir_confirmed',False),
    ('source_note','tmp/bkng-deep-dive.md')
])
if 'BKNG' not in tracked:
    new=OrderedDict()
    inserted=False
    for k,v in tracked.items():
        new[k]=v
        if k=='AMZN':
            new['BKNG']=bkng
            inserted=True
    if not inserted:
        new['BKNG']=bkng
    data['tracked_universe']=new
else:
    tracked['BKNG']=bkng
bands=data['entry_bands']
bands['BKNG']=OrderedDict([
    ('low',164.05),
    ('high',170.91),
    ('stop',155.97),
    ('label','164.05–170.91 watch/rebuild only'),
    ('stop_label','155.97'),
    ('band_last_set','2026-05-10'),
    ('note','Watch/rebuild zone only from BKNG deep dive; not deployable until reclaim/hold of 174-177 and repair from below 20/50/200DMA posture.')
])
p.write_text(json.dumps(data, indent=2)+"\n")
print('updated BKNG in tmp/portfolio-config.json')
