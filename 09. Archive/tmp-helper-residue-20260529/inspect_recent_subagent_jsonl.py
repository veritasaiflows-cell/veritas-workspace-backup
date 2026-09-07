import json, pathlib
base=pathlib.Path.home()/'.openclaw/agents/main/sessions'
for sid in ['baec9545-ea31-47fb-ad8f-e4aa44a16a5e','74b32bb4-1c38-4753-a03f-b4e3eaa9683a']:
    p=base/f'{sid}.jsonl'
    print('###', sid, 'size', p.stat().st_size)
    rows=[]
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        try: rows.append(json.loads(line))
        except Exception: pass
    for r in rows[-12:]:
        typ=r.get('type'); msg=r.get('message') or {}; data=r.get('data') or {}
        print({'type':typ,'customType':r.get('customType'),'ts':r.get('timestamp'),'role':msg.get('role'),'stop':msg.get('stopReason'),'error':msg.get('errorMessage') or data.get('error')})
        content=msg.get('content')
        if isinstance(content,list) and content:
            text=' '.join(str(c.get('text','')) if isinstance(c,dict) else str(c) for c in content)[:600]
            if text.strip(): print('  content:', text.replace('\n',' ')[:600])
    print()
