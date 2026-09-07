import json, pathlib, pprint
for f in ['tmp/run-summary-post-close.json','tmp/dashboard-validation.json']:
    d=json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
    print('\n',f)
    for key in ['warnings','findings','critical_findings']:
        v=d.get(key)
        if isinstance(v,list):
            print(key,len(v))
            for item in v[:5]: print(item)
