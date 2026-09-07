from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

base = Path.home() / '.openclaw' / 'agents' / 'main' / 'sessions'
store = base / 'sessions.json'
data = json.loads(store.read_text(encoding='utf-8-sig'))
referenced = {v.get('sessionId') for v in data.values() if isinstance(v, dict) and v.get('sessionId')}
uuid_re = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\.jsonl$')
ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
manifest = {
    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    'base': str(base),
    'store': str(store),
    'referenced_session_count': len(referenced),
    'dry_run': '--apply' not in __import__('sys').argv,
    'archived': [],
    'skipped_count': 0,
}
for p in sorted(base.glob('*.jsonl')):
    if not uuid_re.match(p.name):
        manifest['skipped_count'] += 1
        continue
    sid = p.stem
    if sid in referenced:
        manifest['skipped_count'] += 1
        continue
    target = p.with_name(p.name + f'.deleted.{ts}')
    row = {'from': str(p), 'to': str(target), 'bytes': p.stat().st_size}
    manifest['archived'].append(row)
    if not manifest['dry_run']:
        p.rename(target)

out = Path('tmp') / f'orphan-transcript-archive-{ts}.json'
out.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'dry_run': manifest['dry_run'], 'archive_count': len(manifest['archived']), 'archive_bytes': sum(r['bytes'] for r in manifest['archived']), 'manifest': str(out)}, indent=2))
