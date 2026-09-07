import json, pathlib, datetime
p=pathlib.Path('tmp/cron-list-20260526T1700.json')
raw=p.read_bytes()
for enc in ('utf-16','utf-8-sig','utf-8'):
    try:
        data=json.loads(raw.decode(enc))
        break
    except Exception:
        data=None
else:
    raise SystemExit('decode failed')
now=datetime.datetime(2026,5,27,0,0,tzinfo=datetime.timezone.utc)
inc=[]
for j in data.get('jobs',[]):
    if not j.get('enabled'): continue
    st=j.get('state') or {}
    bad=[]
    for k in ['lastRunStatus','lastStatus','lastDeliveryStatus','lastFailureNotificationDeliveryStatus']:
        v=st.get(k)
        if v and v not in ('ok','not-requested','not requested'):
            bad.append(f'{k}={v}')
    if st.get('consecutiveErrors',0): bad.append(f"consecutiveErrors={st.get('consecutiveErrors')}")
    if st.get('consecutiveSkipped',0): bad.append(f"consecutiveSkipped={st.get('consecutiveSkipped')}")
    if bad:
        inc.append({'id':j.get('id'),'name':j.get('name'),'bad':bad,'state':st})
print(json.dumps({'enabled_jobs':sum(1 for j in data.get('jobs',[]) if j.get('enabled')),'incidents':inc}, indent=2))
