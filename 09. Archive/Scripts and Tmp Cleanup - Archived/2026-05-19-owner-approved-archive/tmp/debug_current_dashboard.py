import sys, json
sys.path.insert(0, 'scripts')
from generate_dashboard import build_payload, load_sources
payload = build_payload(load_sources())
print(json.dumps({
  'exec_freshness': payload.get('exec_freshness'),
  'summary': payload.get('validation', {}).get('summary'),
  'warnings': payload.get('validation', {}).get('warnings'),
  'portfolio': payload.get('portfolio'),
}, indent=2))
