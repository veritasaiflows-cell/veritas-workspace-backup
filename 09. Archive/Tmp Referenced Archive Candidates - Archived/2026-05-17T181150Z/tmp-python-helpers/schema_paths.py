import json
s=json.load(open('tmp/openclaw-schema.json',encoding='utf-16'))
paths=[]
seen=set()
def walk(o,path=''):
    oid=id(o)
    if oid in seen:
        return
    seen.add(oid)
    if isinstance(o,dict):
        props=o.get('properties')
        if isinstance(props,dict):
            for k,v in props.items():
                p=(path+'.'+k).strip('.')
                if k in ('contextTokens','contextWindow','contextLimits','models','providers','modelCatalog','catalog'):
                    paths.append(p)
                walk(v,p)
        for key in ('$defs','definitions','items','additionalProperties','oneOf','anyOf','allOf'):
            v=o.get(key)
            if isinstance(v,dict):
                walk(v,path+'#'+key)
            elif isinstance(v,list):
                for i,x in enumerate(v):
                    walk(x,path+f'#{key}[{i}]')
walk(s)
print('\n'.join(paths))
