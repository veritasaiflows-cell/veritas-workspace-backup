import json,pathlib
p=pathlib.Path('tmp/archive_ref_check_raw.json')
data=json.loads(p.read_text(encoding='utf-16'))
for d in data:
    files=[h['file'] for h in d['hits']]
    live=[f for f in files if not f.startswith('tmp/')]
    print(f"{d['title']}: exists={d['exists']}, refs={d['inbound_reference_files']}, live_refs={len(live)}")
    for f in live[:12]: print('  -',f)
    if len(live)>12: print('  ...',len(live)-12,'more')
