import json
p='C:/Users/Veritas/AppData/Roaming/npm/node_modules/openclaw/dist/extensions/openai/openclaw.plugin.json'
j=json.load(open(p,encoding='utf-8'))
def find_providers(o,path=''):
    if isinstance(o,dict):
        if 'providers' in o and isinstance(o['providers'],dict):
            print('providers at',path, list(o['providers'].keys()))
            for pid,prov in o['providers'].items():
                if isinstance(prov,dict) and 'models' in prov:
                    print('\nPROVIDER',pid,'base',prov.get('baseUrl'),'api',prov.get('api'))
                    for m in prov.get('models',[]):
                        if '5.' in m.get('id','') or m.get('id','') in ['o1','o1-pro']:
                            print({k:m.get(k) for k in ['id','name','api','contextWindow','contextTokens','maxTokens','reasoning','input','cost']})
        for k,v in o.items(): find_providers(v,path+'/'+k)
    elif isinstance(o,list):
        for i,v in enumerate(o): find_providers(v,path+f'[{i}]')
find_providers(j)
