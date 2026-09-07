import json
s=json.load(open('tmp/openclaw-schema.json',encoding='utf-16'))
print(list(s['properties']['models']['properties'].keys()))
for k,v in s['properties']['models']['properties'].items():
    print('\n',k,':',v.get('description'), 'enum=', v.get('enum'), 'anyOf=', v.get('anyOf'))
