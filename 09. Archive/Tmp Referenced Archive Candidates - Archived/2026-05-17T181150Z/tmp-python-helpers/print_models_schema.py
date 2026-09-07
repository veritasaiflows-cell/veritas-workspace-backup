import json, pprint
s=json.load(open('tmp/openclaw-schema.json',encoding='utf-16'))
pprint.pp(s['properties']['models'], width=140, sort_dicts=False)
