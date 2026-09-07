import sys
sys.path.insert(0, 'scripts')
import test_dashboard_acceptance as t
import copy, json

with t.preserved_tmp_files():
    base = t.load_sources()
    now = t.datetime.now(t.timezone.utc).isoformat()
    for src in base.values():
        if isinstance(src, dict) and 'generated_at_utc' in src:
            src['generated_at_utc'] = now
    local = {k: copy.deepcopy(v) if v is not None else None for k, v in base.items()}
    t._mutate_state_transition(local)
    for name, payload in local.items():
        if payload is not None:
            t.write_source(name, payload)
    built = t.build_payload(t.load_sources())
    print(json.dumps({
        'exec_freshness': built.get('exec_freshness'),
        'summary': built.get('validation', {}).get('summary'),
        'critical': built.get('validation', {}).get('critical'),
        'warnings': built.get('validation', {}).get('warnings'),
        'etn': next((r for r in built.get('technical', []) if r.get('ticker') == 'ETN'), None),
    }, indent=2))
