import json
p=json.load(open('tmp/portfolio-config.json',encoding='utf-8'))
for t,b in p.get('entry_bands',{}).items():
    print(f"{t:6} low={b.get('low')} high={b.get('high')} stop={b.get('stop')} set={b.get('band_last_set')}")
