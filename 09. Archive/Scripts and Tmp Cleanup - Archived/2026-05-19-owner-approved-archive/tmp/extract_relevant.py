import json
from pathlib import Path
cfg=json.loads(Path('tmp/portfolio-config.json').read_text(encoding='utf-8'))
# inspect keys relevant
print(cfg.keys())
print('entry_bands', cfg.get('entry_bands',{}).keys() if isinstance(cfg.get('entry_bands'),dict) else type(cfg.get('entry_bands')))
for k in ['LIN','PH','ITA','ETN','VXUS']:
    print('\nTICKER',k)
    for section in ['tracked_universe','entry_bands','sector_map']:
        data=cfg.get(section)
        print(section, data.get(k) if isinstance(data,dict) else 'not dict')
# portfolio holdings
for sec in ['core','tactical','speculative']:
 print('\n',sec)
 for item in cfg.get('portfolio',{}).get(sec,[]):
  if item.get('ticker') in ['LIN','PH','ITA','ETN','LMT','RTX','GE','KTOS','MSFT','JPM','BRK.B','XOM']:
   print(item)
