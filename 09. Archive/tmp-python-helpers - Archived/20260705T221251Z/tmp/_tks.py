import json
d = json.load(open('tmp/model-quality-scorecard.json','r',encoding='utf-8'))
metric_keys = ['implementation_quality','performance','learning_capture','decision_quality']
for name in metric_keys:
    t = d.get('tracks',{}).get(name,{})
    met = t.get('metrics',{})
    if isinstance(met,dict):
        print(f'=== {name}.metrics ===')
        for k,v in met.items():
            if isinstance(v,(int,float,bool,str)):
                print(f'  {k}: {v}')
            elif isinstance(v,list):
                print(f'  {k}: list[{len(v)}]')
            elif isinstance(v,dict):
                print(f'  {k}: dict keys={list(v.keys())[:6]}')
        print()

d2 = json.load(open('tmp/token-efficiency-scorecard.json','r',encoding='utf-8'))
s = d2.get('summary',{})
print('=== TOKEN EFFICIENCY TOP-LEVEL ===')
for k in list(s.keys())[:25]:
    v = s[k]
    if isinstance(v,(int,float,bool,str)):
        print(f'  {k}: {v}')
print()
print(f'  cron_candidate_count: {s.get("cron_candidate_count")}')
