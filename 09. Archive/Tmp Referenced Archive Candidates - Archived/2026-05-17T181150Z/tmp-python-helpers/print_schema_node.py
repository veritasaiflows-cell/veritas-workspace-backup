import json, pprint
s=json.load(open('tmp/openclaw-schema.json',encoding='utf-16'))
node=s['properties']['models']['properties']['providers']['additionalProperties']
pprint.pp(node, width=120, sort_dicts=False)
